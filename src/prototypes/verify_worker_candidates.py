#!/usr/bin/env python3
"""Actual CLI/socket parity against the fixed-point exhaustive literal matcher."""
import hashlib,json,os,shlex,signal,socket,subprocess,tempfile,time
from pathlib import Path
from benchmark_trigram import CASES,readline,request
REPO=Path(__file__).resolve().parents[2];BUILD=Path('/tmp/fsearch-warm-release-build');EVIDENCE=REPO/'docs/research/production-evidence'

def canonical(value):
    if isinstance(value,dict):
        if isinstance(value.get('error'),str):return {'error':value['error']}
        if value.get('status')=='error':return {'error':value['error']['code']}
        return {key:canonical(item) for key,item in value.items() if key not in ('examined','age_seconds','request_id')}
    if isinstance(value,list):return [canonical(item) for item in value]
    return value

def socket_request(sock,query,options):
    kind={0:'all',1:'files',2:'folders'}
    payload={'schema_version':1,'request_id':'parity','query':query,'path':bool(options.get('flags',0)&1),'match_case':bool(options.get('flags',0)&2),'kind':kind[options.get('kind',0)],'max_candidates':options.get('max_candidates',500000),'max_bytes':options.get('max_bytes',1048576),'limit':options.get('limit',100)}
    if 'extension' in options:payload['extension']=options['extension']
    deadline=time.monotonic()+5
    while True:
        c=socket.socket(socket.AF_UNIX);c.settimeout(5)
        try:c.connect(str(sock));break
        except (ConnectionRefusedError,FileNotFoundError):
            c.close()
            if time.monotonic()>deadline:raise
            time.sleep(.005)
    with c:
        c.sendall((json.dumps(payload)+'\n').encode());raw=bytearray()
        while b'\n' not in raw:
            chunk=c.recv(65536)
            if not chunk:raise RuntimeError('socket EOF')
            raw.extend(chunk)
    return json.loads(raw)

def main():
    cases_all=CASES+[('unicode_sensitive','École',{'flags':2}),('unicode_sensitive_absent','école',{'flags':2}),('fold_kelvin','Kelvin',{}),('normalization_decomposed','café',{})]
    receipt={'fixed_point':'5ec26bab','oracle':'Original literal search with test-only exhaustive verification cap; actual repaired UTF library.','seams':['actual CLI','actual Unix socket'],'cases':[],'isolation':[]}
    receipt['hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sorted((REPO/'src').glob('fsearch_database*.c')),REPO/'src/fsearch_headless.c',REPO/'src/fsearch_utf.c',BUILD/'src/fsearch-cli',BUILD/'src/fsearch-service',BUILD/'src/fsearch-worker',Path(__file__)]}
    def save(): (EVIDENCE/'candidate-parity.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='fsearch-candidate-parity-') as temporary:
        work=Path(temporary)
        baseline=subprocess.check_output(['git','show','5ec26bab:src/fsearch_headless.c'],cwd=REPO,text=True)
        (EVIDENCE/'candidate-oracle-headless.c').write_text(baseline);core=work/'baseline_headless.c';core.write_text(baseline)
        measured=(REPO/'docs/research/trigram-evidence/trigram-probe.generated.c').read_text()
        source=measured.replace('#include "fsearch_headless.c"','#include "'+str(core)+'"')
        generated=work/'oracle.c';generated.write_text(source)
        command=shlex.split((REPO/'docs/research/trigram-evidence/compile.txt').read_text().splitlines()[0])
        command=[arg for arg in command if not arg.endswith('fsearch_utf-prototype-fixed.c')];command[command.index(str(REPO/'docs/research/trigram-evidence/trigram-probe.generated.c'))]=str(generated);binary=work/'oracle';command[command.index('-o')+1]=str(binary)
        subprocess.run(command,check=True,capture_output=True)
        receipt['oracle_source_sha256']=hashlib.sha256(baseline.encode()).hexdigest();save()
        for duplicate in (False,True):
            if duplicate:
                changed=source.replace('if(i<specials)snprintf(name,sizeof(name),"%s",special[i]);','if(i<4)snprintf(name,sizeof(name),"duplicate-common.pdf");else if(i<specials)snprintf(name,sizeof(name),"%s",special[i]);')
                generated.write_text(changed);subprocess.run(command,check=True,capture_output=True)
            snapshot=work/('duplicates.db' if duplicate else 'ordinary.db');subprocess.run([str(binary),'build',str(snapshot),'1000000'],check=True,capture_output=True);snapshot.chmod(0o600)
            oracle=subprocess.Popen([str(binary),'oracle',str(snapshot),'unused'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            sock=work/('duplicates.sock' if duplicate else 'ordinary.sock')
            server=subprocess.Popen([str(BUILD/'src/fsearch-service'),'serve','--socket',str(sock),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                assert readline(oracle,35).get('ready')
                cases=cases_all if not duplicate else [('duplicate','duplicate-common',{}),('duplicate_cap','duplicate-common',{'limit':1}),('duplicate_path','department-02',{'flags':1}),('duplicate_extension','duplicate-common',{'extension':'pdf'})]
                for label,query,options in cases:
                    expected=request(oracle,query,dict(options,max_candidates=1000065))['response']
                    actual=socket_request(sock,query,options)
                    args=[str(BUILD/'src/fsearch-cli'),'--database',str(snapshot),'--query',query,'--kind',{0:'all',1:'files',2:'folders'}[options.get('kind',0)]]
                    for key in ('max_candidates','max_bytes','limit'):
                        if key in options:args+=['--'+key.replace('_','-'),str(options[key])]
                    if options.get('flags',0)&1:args+=['--path']
                    if options.get('flags',0)&2:args+=['--match-case']
                    if 'extension' in options:args+=['--extension',options['extension']]
                    trace_direct=EVIDENCE/('direct-'+('duplicate-' if duplicate else '')+label+'.trace')
                    cold=subprocess.run(['strace','-f','-e','trace=%file','-o',str(trace_direct),*args],capture_output=True,text=True,timeout=5);direct=json.loads(cold.stdout)
                    probes=[line for line in trace_direct.read_text().splitlines() if '/__fsearch_trigram_virtual_owned__' in line]
                    assert not probes,probes
                    receipt['isolation'].append({'seam':'direct CLI','case':label,'duplicate_fixture':duplicate,'trace':str(trace_direct),'indexed_root_file_syscalls':len(probes)})
                    assert canonical(actual)==canonical(direct),(label,'direct/socket mismatch',actual,direct)
                    incomplete=actual.get('status')=='work_limit'
                    assert not incomplete or options.get('max_candidates')==2,(label,'unexpected incomplete',actual)
                    assert incomplete or canonical(actual)==canonical(expected),(label,'oracle mismatch',actual,expected)
                    receipt['cases'].append({'duplicate_fixture':duplicate,'label':label,'socket':actual,'direct':direct,'oracle':expected,'oracle_parity':not incomplete,'deliberate_work_cap':incomplete and options.get('max_candidates')==2});save()
            finally:
                oracle.stdin.close();oracle.stdin=None;oracle.communicate(timeout=5);server.terminate();server.communicate(timeout=5)
            if not duplicate:
                trace=EVIDENCE/'candidate-query.trace';trace_sock=work/'trace.sock'
                traced=subprocess.Popen(['strace','-f','-e','trace=%file','-o',str(trace),str(BUILD/'src/fsearch-service'),'serve','--socket',str(trace_sock),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
                try:
                    for label,query,options in cases_all:socket_request(trace_sock,query,options)
                finally:
                    os.killpg(traced.pid,signal.SIGTERM);traced.communicate(timeout=5)
                lines=trace.read_text().splitlines();probes=[line for line in lines if '/__fsearch_trigram_virtual_owned__' in line]
                assert not probes,probes
                receipt['isolation'].append({'cases':len(cases_all),'all_process_trace':str(trace),'indexed_root_file_syscalls':len(probes),'trace_returncode':traced.returncode});save()
        receipt['complete']=True;save()
    print('verified',len(receipt['cases']),'cases',flush=True)
if __name__=='__main__':main()
