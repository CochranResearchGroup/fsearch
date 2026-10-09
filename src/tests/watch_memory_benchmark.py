"""Bounded owned-directory measurement of real inotify/kernel and process costs."""
import json,os,select,shutil,signal,subprocess,sys,time
from pathlib import Path
worker,count_text,root_text=sys.argv[1:];count=int(count_text);root=Path(root_text)
assert count in (10000,100000,300000,618761) and root.is_dir() and not list(root.iterdir())
if os.statvfs(root).f_bavail*os.statvfs(root).f_frsize<2*1024**3:raise SystemExit('disk preflight below2GiB')
relative=next(line.split(':',2)[2].strip() for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
cgroup=Path('/sys/fs/cgroup')/relative.lstrip('/')
def metrics():
    result={}
    for key in ('memory.current','memory.peak','memory.swap.current'):
        try:result[key]=int((cgroup/key).read_text())
        except (OSError,ValueError):pass
    try:result['memory.stat']={k:int(v) for k,v in (line.split() for line in (cgroup/'memory.stat').read_text().splitlines())}
    except OSError:pass
    return result
proc=None;start=time.monotonic();groups=[];reclaim=[]
try:
    for group in range((count+999)//1000):
        parent=root/f'project-{group:05}-synthetic-owned';parent.mkdir();groups.append(parent)
        for number in range(min(1000,count-group*1000)):(parent/f'directory-{number:05}').mkdir()
    created=metrics();built=time.monotonic()
    proc=subprocess.Popen([worker,'--root',str(root),'--events'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    proc.stdin.write(b'G');proc.stdin.flush()
    assert select.select([proc.stdout],[],[],60)[0],'watch startup timeout'
    ready=json.loads(proc.stdout.readline());assert ready['status']=='ready',ready
    assert json.loads(proc.stdout.readline())['reason']=='startup_gap'
    armed_at=time.monotonic();armed=metrics()
    for label in ('watching','after_stop'):
        if label=='after_stop':proc.terminate();proc.wait(timeout=3)
        try:
            (cgroup/'memory.reclaim').write_text(str(512*1024*1024))
            reclaim.append({'phase':label,'result':'requested_512MiB'})
        except OSError as exc:reclaim.append({'phase':label,'result':'reclaim_returned_error','errno':exc.errno})
        if label=='watching':steady=metrics()
        else:stopped=metrics()
    print(json.dumps({'result':'pass','requested_directories':count,'watches':ready['watches'],'creation_seconds':built-start,'watch_start_seconds':armed_at-built,'created':created,'armed':armed,'watching_after_reclaim':steady,'after_stop_reclaim':stopped,'reclaim':reclaim,'scope':'owned synthetic directories; same cgroup includes creator, watcher, pinned kernel objects and cached fixture metadata; no catalog/query processes'},indent=2),flush=True)
except Exception as exc:
    print(json.dumps({'result':'failed','requested_directories':count,'error_type':type(exc).__name__,'error':str(exc),'elapsed_seconds':time.monotonic()-start,'observed':metrics()},indent=2),flush=True)
    raise
finally:
    if proc and proc.poll() is None:proc.kill();proc.wait(timeout=3)
    shutil.rmtree(root)
