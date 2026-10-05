#!/usr/bin/env python3
"""Owned virtual million-name snapshots; measure actual replacement overlap."""
import argparse,base64,hashlib,json,shlex,shutil,socket,subprocess,tempfile,threading,time
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
RUNTIME=Path('/tmp/fsearch-warm-release-build/src')
EVIDENCE=REPO/'docs/research/refresh-evidence'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--corpus',choices=['varied','repetitive','unicode-heavy'],default='varied');parser.add_argument('--runtime',type=Path);args=parser.parse_args()
    runtime=(args.runtime or RUNTIME).resolve();prefix='installed-' if args.runtime else ''
    receipt={'accepted':False,'runtime':str(runtime),'corpus':args.corpus,'files_per_snapshot':1000000,'frozen_overlap_rss_kib':262144,
             'single_worker_gate_unchanged_kib':131072,'samples':[]}
    with tempfile.TemporaryDirectory(prefix='fsearch-overlap-owned-') as temporary:
        work=Path(temporary);fixture=work/'fixture'
        command=shlex.split((REPO/'docs/research/trigram-evidence/compile.txt').read_text().splitlines()[0])
        command=[arg for arg in command if not arg.endswith('fsearch_utf-prototype-fixed.c')]
        source=next(arg for arg in command if arg.endswith('trigram-probe.generated.c'))
        if args.corpus!='repetitive':
            generated='entropy-fixture.generated.c' if args.corpus=='varied' else 'unicode-heavy-fixture.generated.c'
            command[command.index(source)]=str(REPO/'docs/research/production-evidence'/generated)
        command[command.index('-o')+1]=str(fixture)
        built=subprocess.run(command,capture_output=True,text=True)
        if built.returncode:raise RuntimeError(built.stdout+built.stderr)
        snapshot=work/'snapshot.db';candidate=work/'candidate.db';sock=work/'search.sock';state_path=Path(str(sock)+'.state')
        built=subprocess.run([str(fixture),'build',str(snapshot),'1000000'],capture_output=True,text=True,timeout=30)
        if built.returncode:raise RuntimeError(built.stdout+built.stderr)
        snapshot.chmod(0o600);shutil.copyfile(snapshot,candidate);candidate.chmod(0o600)
        server=subprocess.Popen([str(runtime/'fsearch-service'),'serve','--socket',str(sock),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        done=threading.Event()
        def monitor():
            while not done.is_set():
                try:
                    state=json.loads(state_path.read_text());rows={}
                    for key in ('supervisor','worker','candidate_worker','retiring_worker'):
                        record=state.get(key)
                        if not record or record['pid'] in rows:continue
                        status=Path('/proc',str(record['pid']),'status').read_text().splitlines()
                        rows[record['pid']]={label:int(next(line.split()[1] for line in status if line.startswith(label+':'))) for label in ('VmRSS','VmHWM')}
                    receipt['samples'].append({'time':time.monotonic(),'processes':rows,'rss_kib':sum(row['VmRSS'] for row in rows.values()),'sum_hwm_kib':sum(row['VmHWM'] for row in rows.values())})
                except (OSError,ValueError,KeyError,StopIteration):pass
                done.wait(.002)
        watcher=threading.Thread(target=monitor);watcher.start()
        def request(payload):
            deadline=time.monotonic()+5
            while True:
                connection=socket.socket(socket.AF_UNIX);connection.settimeout(5)
                try:connection.connect(str(sock));break
                except (FileNotFoundError,ConnectionRefusedError):
                    connection.close()
                    if time.monotonic()>deadline:raise
                    time.sleep(.005)
            with connection:
                connection.sendall((json.dumps(payload)+'\n').encode());raw=bytearray()
                while b'\n' not in raw:
                    chunk=connection.recv(65536)
                    if not chunk:raise RuntimeError('socket EOF')
                    raw.extend(chunk)
                return json.loads(raw)
        query={'schema_version':1,'request_id':'overlap-query','query':'invoice-unique-zqx','kind':'files'}
        try:
            before=request(query);assert before['complete'],before
            replaced=request({'schema_version':1,'request_id':'overlap-replace','op':'replace','candidate_database_b64':base64.b64encode(bytes(candidate)).decode()})
            assert replaced['status']=='replaced',replaced
            after=request(query);assert after['results']==before['results'],after
            assert after['snapshot']['identity']==replaced['snapshot_id']!=before['snapshot']['identity']
            receipt['identities']=[before['snapshot']['identity'],after['snapshot']['identity']]
        finally:
            done.set();watcher.join();server.terminate();output,error=server.communicate(timeout=5)
            receipt['service_returncode']=server.returncode
            (EVIDENCE/f'{prefix}replacement-overlap-{args.corpus}.stderr.txt').write_bytes(error)
        receipt['overlap_samples']=sum(len(sample['processes'])==3 for sample in receipt['samples'])
        receipt['max_processes']=max(len(sample['processes']) for sample in receipt['samples'])
        receipt['peak_rss_kib']=max(sample['rss_kib'] for sample in receipt['samples'])
        receipt['peak_sum_hwm_kib']=max(sample['sum_hwm_kib'] for sample in receipt['samples'])
        receipt['gate_pass']=receipt['overlap_samples']>0 and receipt['max_processes']==3 and receipt['peak_sum_hwm_kib']<=receipt['frozen_overlap_rss_kib']
        receipt['hashes']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (runtime/'fsearch-service',runtime/'fsearch-worker',Path(__file__))}
        (EVIDENCE/f'{prefix}replacement-overlap-{args.corpus}.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps({key:value for key,value in receipt.items() if key!='samples'},indent=2))
if __name__=='__main__':main()
