#!/usr/bin/env python3
"""Source-service acceptance on owned native fixtures; no installation or real-root scan."""
import json, os, shutil, socket, statistics, subprocess, sys, tempfile, time
from pathlib import Path
build=Path(sys.argv[1]).resolve(); output=Path(sys.argv[2]).resolve()
service=build/'src/fsearch-service'; cli=build/'src/fsearch-cli'; fixture=build/'src/tests/snapshot_fixture'
def request(sock,query,number):
    started=time.perf_counter()
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(4); connection.connect(str(sock))
        connection.sendall((json.dumps({'schema_version':1,'request_id':str(number),'query':query,'kind':'files'})+'\n').encode())
        raw=bytearray()
        while b'\n' not in raw:
            chunk=connection.recv(65536)
            if not chunk: raise RuntimeError('premature EOF')
            raw.extend(chunk)
        result=json.loads(raw)
        assert result['complete'] and result['request_id']==str(number),result
    return (time.perf_counter()-started)*1000,result

def stats(samples):
    ordered=sorted(samples[1:]);return {'first_ms':samples[0],'p50_ms':statistics.median(ordered),'p95_ms':ordered[28]}
def process_info(pid):
    info=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    cpu=(int(info[11])+int(info[12]))/os.sysconf('SC_CLK_TCK')
    rss=int(next(line.split()[1] for line in Path(f'/proc/{pid}/status').read_text().splitlines() if line.startswith('VmRSS:')))
    return cpu,rss
summary={'workloads':[],'limits':'Owned flat native fixtures, potentially warm OS caches; source release build. Summed observed RSS, not measured peak. No real-root/installed/MCP/default-adoption claim.'}
with tempfile.TemporaryDirectory(prefix='fsearch-service-benchmark-') as temporary:
    work=Path(temporary)
    for count in (10000,100000):
        root=work/f'owned-{count}';root.mkdir()
        for i in range(count): (root/f'entry{i:06d}.txt').touch()
        database=work/f'snapshot-{count}.db'
        subprocess.run([str(fixture),'build',str(database),str(root)],check=True,capture_output=True,timeout=60);database.chmod(0o600)
        shutil.rmtree(root)
        directory=work/f'instance-{count}';directory.mkdir(mode=0o700);sock=directory/'search.sock'
        trace=work/f'trace-{count}.txt'
        command=[str(service),'serve','--socket',str(sock),'--database',str(database)]
        # Trace isolation separately from latency: tracing changes process timings.
        server=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for _ in range(300):
                if server.poll() is not None:raise RuntimeError(server.communicate())
                try:
                    with socket.socket(socket.AF_UNIX) as c: c.connect(str(sock))
                    break
                except (FileNotFoundError,ConnectionRefusedError):time.sleep(.01)
            for query in ('entry00000','absent-literal'):
                samples=[]
                for number in range(31):
                    elapsed,payload=request(sock,query,number);samples.append(elapsed)
                    expected={f'entry{i:06d}.txt' for i in range(10)} if query=='entry00000' else set()
                    assert {Path(row['path']).name for row in payload['results']}==expected
                summary['workloads'].append({'files':count,'query':query,'socket_ms':stats(samples),'gate_pass':stats(samples)['p95_ms']<=(5 if count==10000 else 30),'raw_ms':samples})
            state=json.loads((directory/'search.sock.state').read_text());pids=[state[key]['pid'] for key in ('supervisor','worker')]
            before=[process_info(pid) for pid in pids];time.sleep(6);after=[process_info(pid) for pid in pids]
            rss=sum(row[1] for row in after);cpu=sum(after[i][0]-before[i][0] for i in range(2))
            same=json.loads((directory/'search.sock.state').read_text())['worker']==state['worker']
            summary.setdefault('resources',[]).append({'files':count,'aggregate_rss_kib':rss,'idle_seconds':6,'idle_cpu_seconds':cpu,'worker_identity_unchanged':same,'gate_pass':rss<=131072 and cpu<=.25 and same})
            samples=[]
            for _ in range(31):
                started=time.perf_counter();r=subprocess.run([str(cli),'--socket',str(sock),'--query','entry00000','--kind','files'],check=True,capture_output=True,text=True,timeout=5)
                samples.append((time.perf_counter()-started)*1000);assert len(json.loads(r.stdout)['results'])==10
            summary.setdefault('fresh_cli_client',[]).append({'files':count,'ms':stats(samples),'note':'Fresh native CLI process; warm socket transport avoids Python startup.'})
            subprocess.run([str(service),'stop','--socket',str(sock)],check=True,capture_output=True,timeout=5);server.communicate(timeout=5)
            assert not Path(f'/proc/{state["worker"]["pid"]}').exists()
        finally:
            if server.poll() is None:server.terminate();server.communicate(timeout=5)
        server=subprocess.Popen(['strace','-f','-e','trace=%file','-o',str(trace),*command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        try:
            for _ in range(300):
                try:
                    with socket.socket(socket.AF_UNIX) as c:c.connect(str(sock))
                    break
                except (FileNotFoundError,ConnectionRefusedError):time.sleep(.01)
            request(sock,'entry00000',100);time.sleep(6);request(sock,'entry00000',101)
            subprocess.run([str(service),'stop','--socket',str(sock)],check=True,capture_output=True,timeout=5);server.communicate(timeout=5)
            contents=trace.read_text();assert str(root) not in contents
            output.parent.mkdir(parents=True,exist_ok=True);(output.parent/f'service-{count}.trace').write_text(contents)
            summary.setdefault('isolation',[]).append({'files':count,'indexed_root_syscalls':0,'idle_seconds':6,'root_removed':True})
        finally:
            if server.poll() is None:
                os.killpg(server.pid,15)
                try:server.communicate(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(server.pid,9);server.communicate(timeout=5)
summary['all_gates_pass']=all(row['gate_pass'] for row in summary['workloads']+summary['resources'])
output.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({**summary,'workloads':[{k:v for k,v in row.items() if k!='raw_ms'} for row in summary['workloads']]},indent=2))
