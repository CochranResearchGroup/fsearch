#!/usr/bin/env python3
"""Measure actual private socket/worker on a virtual million-name snapshot."""
import argparse,hashlib,json,shlex,socket,subprocess,tempfile,threading,time
from pathlib import Path
from benchmark_trigram import percentiles
REPO=Path(__file__).resolve().parents[2]
BUILD=Path('/tmp/fsearch-warm-release-build')
EVIDENCE=REPO/'docs/research/production-evidence'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--selective',action='store_true');args=parser.parse_args()
    receipt={'accepted':False,'seam':'actual Unix socket and compiled resident worker','files':1000000,'samples':100,'frozen_rss_kib':131072,'queries':[]}
    with tempfile.TemporaryDirectory(prefix='fsearch-candidates-owned-') as temporary:
        work=Path(temporary);binary=work/'fixture-probe'
        command=shlex.split((REPO/'docs/research/trigram-evidence/compile.txt').read_text().splitlines()[0])
        command=[arg for arg in command if not arg.endswith('fsearch_utf-prototype-fixed.c')];command[command.index('-o')+1]=str(binary)
        subprocess.run(command,check=True,capture_output=True)
        snapshot=work/'snapshot.db';subprocess.run([str(binary),'build',str(snapshot),'1000000'],check=True,capture_output=True);snapshot.chmod(0o600)
        sock=work/'search.sock';state_path=Path(str(sock)+'.state')
        server=subprocess.Popen([str(BUILD/'src/fsearch-service'),'serve','--socket',str(sock),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        done=threading.Event();peaks=[]
        def state(): return json.loads(state_path.read_text())
        def rss(pid):
            return int(next(line.split()[1] for line in Path(f'/proc/{pid}/status').read_text().splitlines() if line.startswith('VmRSS:')))
        def monitor():
            while not done.is_set():
                try:
                    s=state();peaks.append(sum(rss(s[key]['pid']) for key in ('supervisor','worker') if s.get(key) and s[key].get('pid')))
                except (OSError,ValueError,KeyError,StopIteration):pass
                done.wait(.002)
        watcher=threading.Thread(target=monitor);watcher.start()
        def request(query,flags=False):
            deadline=time.monotonic()+5
            while True:
                c=socket.socket(socket.AF_UNIX);c.settimeout(5)
                try:c.connect(str(sock));break
                except (ConnectionRefusedError,FileNotFoundError):
                    c.close()
                    if time.monotonic()>deadline:raise
                    time.sleep(.005)
            start=time.perf_counter()
            with c:
                c.sendall((json.dumps({'schema_version':1,'request_id':'qualification','query':query,'kind':'files','path':flags})+'\n').encode());raw=bytearray()
                while b'\n' not in raw:
                    chunk=c.recv(65536)
                    if not chunk:raise RuntimeError('socket EOF')
                    raw.extend(chunk)
            return json.loads(raw),(time.perf_counter()-start)*1000
        try:
            initial,elapsed=request('invoice-unique-zqx');receipt['startup_request_ms']=elapsed
            assert 'results' in initial,initial
            worker=state()['worker']
            cases=[('rare','invoice-unique-zqx',False),('late','zz-last-rare-qvt',False),('absent','never-exists-jkm',False),('false_grams','abcd',False),('two_char','ab',False),('unicode','école',False),('path','department-63-invoice-path',True)]
            for label,query,path in (cases[:4] if args.selective else cases):
                first,_=request(query,path)
                for _ in range(3):request(query,path)
                samples=[]
                for _ in range(100):
                    result,elapsed=request(query,path);samples.append(elapsed)
                    assert result['results']==first['results'] and result['status']==first['status'],(label,result)
                receipt['queries'].append({'label':label,'query':query,'path':path,'first':first,'socket_ms':percentiles(samples),'raw_socket_ms':samples})
                print(label,receipt['queries'][-1]['socket_ms'],first['status'],flush=True)
            final=state();receipt['same_worker']=worker==final['worker']
            receipt['steady_aggregate_rss_kib']=sum(rss(final[key]['pid']) for key in ('supervisor','worker'))
        finally:
            done.set();watcher.join();server.terminate();out,err=server.communicate(timeout=5)
            receipt['sampled_peak_aggregate_rss_kib']=max(peaks,default=0);receipt['rss_samples']=len(peaks)
            receipt['service_returncode']=server.returncode
            receipt['hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [REPO/'src/fsearch_headless.c',REPO/'src/fsearch_utf.c',BUILD/'src/fsearch-worker',BUILD/'src/fsearch-service',REPO/'src/prototypes/qualify_worker_candidates.py']}
            (EVIDENCE/'candidate-worker.stderr.txt').write_bytes(err)
            (EVIDENCE/('candidate-worker-selective.json' if args.selective else 'candidate-worker-full.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print('sampled peak aggregate',receipt['sampled_peak_aggregate_rss_kib'],flush=True)
if __name__=='__main__':main()
