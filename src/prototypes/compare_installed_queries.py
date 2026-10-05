#!/usr/bin/env python3
"""Paired alternating queries, preserved/current runtimes, one owned fixture."""
import hashlib,json,shlex,socket,subprocess,tempfile,time
from pathlib import Path
from benchmark_trigram import percentiles
REPO=Path(__file__).resolve().parents[2]
EVIDENCE=REPO/'docs/research/refresh-evidence'
RUNTIMES={'previous':Path.home()/'.local/share/fsearch/runtimes/f3e98fb06012ac8d250549d1cb0b491d93454c3e/bin',
          'current':Path.home()/'.local/share/fsearch/runtimes/3d0bfaf2312b2e9bf4536c8592cc8aff769094ca/bin'}

def main():
    receipt={'accepted':False,'samples_per_runtime_per_case':100,'order':'alternating AB/BA pairs','files':1000000,'frozen_selective_p95_ms':10,'cases':[]}
    with tempfile.TemporaryDirectory(prefix='fsearch-paired-owned-') as temporary:
        work=Path(temporary);fixture=work/'fixture';snapshot=work/'snapshot.db'
        command=shlex.split((REPO/'docs/research/trigram-evidence/compile.txt').read_text().splitlines()[0])
        command=[arg for arg in command if not arg.endswith('fsearch_utf-prototype-fixed.c')]
        source=next(arg for arg in command if arg.endswith('trigram-probe.generated.c'))
        command[command.index(source)]=str(EVIDENCE/'entropy-fixture.generated.c');command[command.index('-o')+1]=str(fixture)
        built=subprocess.run(command,capture_output=True,text=True)
        if built.returncode:raise RuntimeError(built.stdout+built.stderr)
        built=subprocess.run([str(fixture),'build',str(snapshot),'1000000'],capture_output=True,text=True,timeout=30)
        if built.returncode:raise RuntimeError(built.stdout+built.stderr)
        snapshot.chmod(0o600)
        receipt['fixture_sha256']=hashlib.sha256(snapshot.read_bytes()).hexdigest()
        servers={};identities={}
        def request(label,query):
            sock=work/(label+'.sock');deadline=time.monotonic()+5
            while True:
                connection=socket.socket(socket.AF_UNIX);connection.settimeout(5)
                try:connection.connect(str(sock));break
                except (FileNotFoundError,ConnectionRefusedError):
                    connection.close()
                    if time.monotonic()>deadline:raise
                    time.sleep(.005)
            started=time.perf_counter()
            with connection:
                connection.sendall((json.dumps({'schema_version':1,'request_id':'paired','query':query,'kind':'files'})+'\n').encode());raw=bytearray()
                while b'\n' not in raw:
                    data=connection.recv(65536)
                    if not data:raise RuntimeError('socket EOF')
                    raw.extend(data)
            return json.loads(raw),(time.perf_counter()-started)*1000
        try:
            for label,runtime in RUNTIMES.items():
                servers[label]=subprocess.Popen([str(runtime/'fsearch-service'),'serve','--socket',str(work/(label+'.sock')),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                response,_=request(label,'invoice-unique-zqx');assert response['complete'],response
                identities[label]=response['snapshot']['identity']
            for case,query in [('false_grams','abcd'),('rare','invoice-unique-zqx'),('late','zz-last-rare-qvt'),('absent','never-exists-jkm')]:
                first={label:request(label,query)[0] for label in RUNTIMES}
                assert first['previous']['results']==first['current']['results']
                samples={label:[] for label in RUNTIMES};pairs=[]
                for iteration in range(100):
                    pair={}
                    for label in (('previous','current') if iteration%2==0 else ('current','previous')):
                        response,elapsed=request(label,query)
                        assert response['complete'] and response['results']==first[label]['results'] and response['snapshot']['identity']==identities[label],response
                        samples[label].append(elapsed);pair[label]=elapsed
                    pairs.append(pair)
                result={'case':case,'query':query,'timings':{label:percentiles(values) for label,values in samples.items()},'pairs':pairs}
                receipt['cases'].append(result);print(json.dumps({key:value for key,value in result.items() if key!='pairs'}),flush=True)
        finally:
            receipt['process_exit_codes']={}
            for label,server in servers.items():
                server.terminate();output,error=server.communicate(timeout=5)
                receipt['process_exit_codes'][label]=server.returncode
                (EVIDENCE/f'paired-{label}.stderr.txt').write_bytes(error)
        receipt['gate_pass']={label:all(row['timings'][label]['p95_ms']<10 for row in receipt['cases']) for label in RUNTIMES}
        receipt['hashes']={str(runtime/name):hashlib.sha256((runtime/name).read_bytes()).hexdigest() for runtime in RUNTIMES.values() for name in ('fsearch-worker','fsearch-service')}
        (EVIDENCE/'paired-installed-queries.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
