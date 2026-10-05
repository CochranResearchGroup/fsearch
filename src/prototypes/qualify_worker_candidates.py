#!/usr/bin/env python3
"""Measure actual private socket/worker on a virtual million-name snapshot."""
import argparse,hashlib,json,shlex,socket,subprocess,tempfile,threading,time
from pathlib import Path
from benchmark_trigram import percentiles,readline,request as native_request
REPO=Path(__file__).resolve().parents[2]
BUILD=Path('/tmp/fsearch-warm-release-build')
EVIDENCE=REPO/'docs/research/production-evidence'

def main():
    global EVIDENCE
    parser=argparse.ArgumentParser();parser.add_argument('--selective',action='store_true');parser.add_argument('--entropy',action='store_true');parser.add_argument('--unicode-heavy',action='store_true');parser.add_argument('--runtime',type=Path);parser.add_argument('--evidence-dir',type=Path);args=parser.parse_args()
    if args.evidence_dir:EVIDENCE=args.evidence_dir.resolve();EVIDENCE.mkdir(parents=True,exist_ok=True)
    runtime=args.runtime or BUILD/'src'
    output_prefix='installed-' if args.runtime else ''
    receipt={'runtime':str(runtime),'fixture':'unicode-heavy' if args.unicode_heavy else 'varied' if args.entropy else 'repetitive','accepted':False,'seam':'actual Unix socket and compiled resident worker','files':1000000,'samples':100,'frozen_rss_kib':131072,'queries':[]}
    receipt['hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [REPO/'src/fsearch_headless.c',REPO/'src/fsearch_utf.c',REPO/'src/fsearch_database_file.c',REPO/'src/fsearch_database_index_store.c',REPO/'src/fsearch_database_index.c',REPO/'src/fsearch_database_entry.c',REPO/'src/fsearch_database_entry.h',REPO/'src/fsearch_database_entry_flags.h',REPO/'src/fsearch_database_file.h',REPO/'src/fsearch_database_index.h',REPO/'src/fsearch_database_index_store.h',runtime/'fsearch-worker',runtime/'fsearch-service',REPO/'src/prototypes/qualify_worker_candidates.py']}
    with tempfile.TemporaryDirectory(prefix='fsearch-candidates-owned-') as temporary:
        work=Path(temporary);binary=work/'fixture-probe'
        command=shlex.split((REPO/'docs/research/trigram-evidence/compile.txt').read_text().splitlines()[0])
        command=[arg for arg in command if not arg.endswith('fsearch_utf-prototype-fixed.c')];command[command.index('-o')+1]=str(binary)
        if args.entropy or args.unicode_heavy:
            source_path=next(Path(arg) for arg in command if arg.endswith('trigram-probe.generated.c'))
            source=source_path.read_text()
            ordinary='else snprintf(name,sizeof(name),"%s-%07u-common.%s",categories[i%8],i,i%3==0 ? "pdf" : i%3==1 ? "txt" : "csv");'
            assert source.count(ordinary)==1
            source=source.replace(ordinary, 'else {uint32_t state=i+1;for(unsigned k=0;k<40;++k){state^=state<<13;state^=state>>17;state^=state<<5;name[k]="abcdefghijklmnopqrstuvwxyz0123456789"[state%36];}snprintf(name+40,sizeof(name)-40,"-%07u.txt",i);}')
            if args.unicode_heavy:
                source=source.replace('else {uint32_t state=i+1;', 'else if(i%5==0)snprintf(name,sizeof(name),"обычный-%07u.txt",i);else {uint32_t state=i+1;')
            generated=work/'entropy-fixture.c';generated.write_text(source);command[command.index(str(source_path))]=str(generated)
            (EVIDENCE/('unicode-heavy-fixture.generated.c' if args.unicode_heavy else 'entropy-fixture.generated.c')).write_text(source)
        subprocess.run(command,check=True,capture_output=True)
        snapshot=work/'snapshot.db';subprocess.run([str(binary),'build',str(snapshot),'1000000'],check=True,capture_output=True);snapshot.chmod(0o600)
        sock=work/'search.sock';state_path=Path(str(sock)+'.state')
        server=subprocess.Popen([str(runtime/'fsearch-service'),'serve','--socket',str(sock),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
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
            cases=[('rare','invoice-unique-zqx',False),('late','zz-last-rare-qvt',False),('absent','never-exists-jkm',False),('false_grams','abcd',False),('two_char','ab',False),('unicode','école',False),('path','department-63-invoice-path',True),('short_complete','??',False),('path_complete','zz-last-rare-qvt',True)]
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
            receipt['gate_readback']={'rss_pass':None,'selective_pass':all(q['first']['complete'] and q['socket_ms']['p95_ms']<10 for q in receipt['queries'] if q['label'] in ('rare','late','absent','false_grams')),'complete_short_unicode_path_pass':all(q['first']['complete'] and q['socket_ms']['p95_ms']<30 for q in receipt['queries'] if q['label'] in ('short_complete','unicode','path_complete')),'broad_result_limits_qualify_complete_search':False}
            receipt['steady_aggregate_rss_kib']=sum(rss(final[key]['pid']) for key in ('supervisor','worker'))
            receipt['conservative_sum_hwm_kib']=sum(int(next(line.split()[1] for line in Path(f'/proc/{final[key]["pid"]}/status').read_text().splitlines() if line.startswith('VmHWM:'))) for key in ('supervisor','worker'))
            receipt['gate_readback']['rss_pass']=receipt['conservative_sum_hwm_kib']<=receipt['frozen_rss_kib']
        finally:
            done.set();watcher.join();server.terminate();out,err=server.communicate(timeout=5)
            receipt['sampled_peak_aggregate_rss_kib']=max(peaks,default=0);receipt['rss_samples']=len(peaks)
            receipt['service_returncode']=server.returncode

            (EVIDENCE/'candidate-worker.stderr.txt').write_bytes(err)
            (EVIDENCE/(output_prefix+('candidate-worker-unicode-heavy.json' if args.unicode_heavy else 'candidate-worker-entropy.json' if args.entropy else 'candidate-worker-selective.json' if args.selective else 'candidate-worker-full.json'))).write_text(json.dumps(receipt,indent=2)+'\n')
        native=subprocess.Popen([str(binary),'oracle',str(snapshot),'unused'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            receipt['native_ready']=readline(native,5)
            receipt['native_queries']=[]
            for label,query,path in cases:
                options={'kind':1,'flags':int(path)}
                for _ in range(3):native_request(native,query,options)
                samples=[native_request(native,query,options)['elapsed_ms'] for _ in range(100)]
                receipt['native_queries'].append({'label':label,'native_ms':percentiles(samples),'raw_native_ms':samples})
        finally:
            native.stdin.close();native.stdin=None;native.communicate(timeout=5)
        receipt['fresh_cli_queries']=[]
        for label,query,path in cases:
            samples=[]
            for _ in range(3):
                started=time.perf_counter()
                command=[str(runtime/'fsearch-cli'),'--database',str(snapshot),'--query',query,'--kind','files']
                if path:command+=['--path']
                result=subprocess.run(command,capture_output=True,text=True,timeout=5)
                assert json.loads(result.stdout)['status'] in ('ok','result_limit'),result.stdout
                samples.append((time.perf_counter()-started)*1000)
            receipt['fresh_cli_queries'].append({'label':label,'samples':3,'cold_cli_ms':percentiles(samples),'raw_cold_cli_ms':samples})
        (EVIDENCE/(output_prefix+('candidate-worker-unicode-heavy.json' if args.unicode_heavy else 'candidate-worker-entropy.json' if args.entropy else 'candidate-worker-selective.json' if args.selective else 'candidate-worker-full.json'))).write_text(json.dumps(receipt,indent=2)+'\n')
    print('sampled peak aggregate',receipt['sampled_peak_aggregate_rss_kib'],flush=True)
if __name__=='__main__':main()
