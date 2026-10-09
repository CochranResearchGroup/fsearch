#!/usr/bin/env python3
"""Run an owned process group with time, aggregate RSS and host pressure stops.

Receipts report sampled RSS separately from cgroup figures; this runner
never treats sampled tree RSS as proof of an exact peak or uses it to accept M5.
"""
import argparse,json,os,signal,subprocess,time
from pathlib import Path

def host():
    memory={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.split(':')[0] in ('MemAvailable','SwapFree')}
    for kind in ('memory','io'):
        for row in Path('/proc/pressure',kind).read_text().splitlines():
            parts=row.split();memory[kind+'_'+parts[0]+'_avg10']=float(parts[1].split('=')[1])
    return memory

def tree(root,known):
    processes={}
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal():continue
        try:
            stat=(path/'stat').read_text();fields=stat[stat.rindex(')')+2:].split()
            processes[int(path.name)]=(int(fields[1]),int(fields[2]),int(fields[19]),path)
        except (OSError,ValueError):pass
    selected={pid for pid,(_,group,started,_) in processes.items() if group==root or known.get(pid)==started}
    changed=True
    while changed:
        added={pid for pid,(parent,_,_,_) in processes.items() if parent in selected}-selected
        changed=bool(added);selected.update(added)
    rows=[]
    for pid in selected:
        _,_,started,path=processes[pid];known[pid]=started
        try:
            values={}
            for line in (path/'status').read_text().splitlines():
                if line.startswith(('VmRSS:','VmSwap:')):values[line.split(':')[0]]=int(line.split()[1])*1024
            # smaps_rollup can wait on the target's mmap lock during reclaim.
            # Never put that blocking PSS read on the pressure/deadline path.
            rows.append({'pid':pid,**values})
        except (OSError,ValueError,ProcessLookupError):pass
    return rows

def cgroup():
    try:
        relative=next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
        root=Path('/sys/fs/cgroup')/relative.lstrip('/')
        return {'path':relative,**{name:int((root/name).read_text()) for name in ('memory.current','memory.peak','memory.max','memory.swap.current','memory.swap.peak','memory.swap.max')}}
    except (OSError,ValueError,StopIteration):return None

p=argparse.ArgumentParser();p.add_argument('--receipt',required=True);p.add_argument('--seconds',type=float,default=60);p.add_argument('--rss-mib',type=int,default=1280);p.add_argument('command',nargs=argparse.REMAINDER);args=p.parse_args()
command=args.command[1:] if args.command[:1]==['--'] else args.command
if not command:p.error('missing command')
start=time.monotonic();initial=host();samples=[];reason=None;bad_since=None;known={};last_sample=start;max_sample_gap=0
if initial['MemAvailable']<8*1024**3 or initial['memory_full_avg10']>2 or initial['io_full_avg10']>15:
    reason='host_pressure_preflight';proc=None
else:
    try:proc=subprocess.Popen(command,start_new_session=True)
    except OSError as exc:reason="spawn_error: "+str(exc);proc=None
try:
    while proc is not None:
        now=time.monotonic();metrics=host();rows=tree(proc.pid,known)
        rss=sum(x.get('VmRSS',0) for x in rows);swap=sum(x.get('VmSwap',0) for x in rows)
        completed=time.monotonic();sample_gap=completed-last_sample;max_sample_gap=max(max_sample_gap,sample_gap);last_sample=completed
        samples.append({'seconds':completed-start,'host':metrics,'rss_bytes':rss,'pss_bytes':None,'sample_duration_seconds':completed-now,'swap_bytes':swap,'pids':[x['pid'] for x in rows]})
        bad=metrics['MemAvailable']<8*1024**3 or metrics['memory_full_avg10']>2 or metrics['io_full_avg10']>15
        if bad and bad_since is None:bad_since=now
        if not bad:bad_since=None
        if sample_gap>1:reason='monitor_sample_gap'
        elif rss>args.rss_mib*1024**2:reason='aggregate_rss_budget'
        elif swap>0:reason='owned_tree_swapped'
        elif completed-start>args.seconds:reason='deadline'
        elif bad_since is not None and now-bad_since>=10:reason='sustained_host_pressure'
        if reason or proc.poll() is not None:break
        time.sleep(.2)
finally:
    if proc is not None:
        # Stop only this runner's process group, including any escaped test-parent orphans.
        try:os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:proc.wait(timeout=2)
        except subprocess.TimeoutExpired:pass
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proc.wait()
        # Children that started their own session are still owned descendants.
        for row in tree(proc.pid,known):
            try:os.kill(row['pid'],signal.SIGKILL)
            except ProcessLookupError:pass
    result={'command':command,'reason':reason,'exit_code':proc.returncode if proc else None,'elapsed_seconds':time.monotonic()-start,'sample_interval_seconds':.2,'peak_sampled_rss_bytes':max((x['rss_bytes'] for x in samples),default=0),'peak_sampled_pss_bytes':None,'max_sample_gap_seconds':max_sample_gap,'initial_host':initial,'final_host':host(),'samples':samples,'cgroup':cgroup(),'qualification':'dedicated cgroup peak when present; sampled owned descendant RSS otherwise; PSS omitted to avoid blocking monitor'}
    destination=Path(args.receipt);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(1 if reason else proc.returncode)
