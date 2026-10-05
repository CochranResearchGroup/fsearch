#!/usr/bin/env python3
"""Isolated native/SQLite prototype; generated snapshots, never scan real roots."""
import argparse, hashlib, json, math, os, resource, selectors, shlex, statistics, subprocess, tempfile, time
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
CASES=[
 ('rare','invoice-unique-zqx',{}),('late','zz-last-rare-qvt',{}),('absent','never-exists-jkm',{}),
 ('present_grams_absent','abcd',{}),('common','common',{}),('one_char','a',{}),('two_char','ab',{}),
 ('literal_star','literal*wild?',{}),('literal_percent','100%_',{}),('literal_quote','a"b',{}),('brackets','[x]',{}),
 ('case','INVOICE',{}),('sensitive','INVOICE',{'flags':2}),('unicode','école',{}),('fold','straße',{}),
 ('normalization','café',{}),('raw_bytes','raw-',{}),('path_parent','department-63-invoice-path',{'flags':1}),
 ('files_extension','invoice',{'kind':1,'extension':'pdf'}),('folders','invoice',{'kind':2}),
 ('empty_extension','noextension',{'extension':''}),('empty','',{}),('byte_cap','invoice',{'max_bytes':512}),
 ('result_cap','invoice',{'limit':1}),('work_cap','zz-last-rare-qvt',{'max_candidates':2}),
 ('long_name','shared-report',{}),('line_name','line',{}),('overlap_grams','ababa',{}),
 ('leading_space',' invoice',{}),('all_common_rare','report-0099999',{})]
BENCH={'rare','late','absent','present_grams_absent','common','one_char','two_char','unicode','path_parent'}
def percentiles(values):
 s=sorted(values)
 return {f'p{p}_ms':s[max(0,math.ceil(len(s)*p/100)-1)] for p in (50,95,99)}
def normalize(response):
 # Examined counts are intentionally different, but all result/coverage fields remain exact.
 return {k:(normalize(v) if isinstance(v,dict) else [normalize(x) if isinstance(x,dict) else x for x in v] if isinstance(v,list) else v) for k,v in response.items() if k not in ('examined','age_seconds')}
def readline(process,timeout=35):
 with selectors.DefaultSelector() as selector:
  selector.register(process.stdout,selectors.EVENT_READ)
  if not selector.select(timeout): raise TimeoutError('prototype response deadline')
 raw=process.stdout.readline()
 if not raw: raise RuntimeError(f'prototype EOF, return code {process.poll()}')
 return json.loads(raw)
def request(process,query,options):
 payload=f"{options.get('flags',0)} {options.get('kind',0)} {options.get('max_candidates',500000)} {options.get('max_bytes',1048576)} {options.get('limit',100)}\t{query}"
 if 'extension' in options:payload+='\t'+options['extension']
 begin=time.perf_counter();process.stdin.write((payload+'\n').encode());process.stdin.flush()
 response=readline(process,3);response['pipe_ms']=(time.perf_counter()-begin)*1000;return response
def compile_probe(build,evidence):
 core=(REPO/'src/fsearch_headless.c').read_text();body=core[core.index('GString *fsearch_headless_search('):]
 body=body.replace('fsearch_headless_search(', 'prototype_filtered_search(',1)
 needle='        const unsigned count = entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;'
 assert body.count(needle)==1
 body=body.replace(needle,"        g_autoptr(GArray) candidates = candidate_ranks(options,type);\n        if(candidate_limited){*error=\"candidate_work_limit\";return NULL;}\n        const unsigned count = candidates ? candidates->len : entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;")
 needle='fsearch_database_chunked_array_get_entry(entries, i)';assert body.count(needle)==1
 body=body.replace(needle,'fsearch_database_chunked_array_get_entry(entries, candidates ? g_array_index(candidates,uint32_t,i) : i)')
 source=(REPO/'src/prototypes/trigram_probe.c').read_text().replace('/* GENERATED_FILTERED_SEARCH */',body)
 generated=evidence/'trigram-probe.generated.c';generated.write_text(source)
 pkg=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-3.0','gio-unix-2.0','libpcre2-8','icu-uc','sqlite3'],text=True))
 utf=(REPO/'src/fsearch_utf.c').read_text()
 needle='    builder->string = g_strdup(string);';assert utf.count(needle)==1
 repaired=evidence/'fsearch_utf-prototype-fixed.c';repaired.write_text(utf.replace(needle,'    g_clear_pointer(&builder->string,free);\n'+needle))
 binary=evidence/'trigram-probe'
 command=['/usr/bin/gcc','-O3','-g','-Wall','-Wextra','-std=gnu11','-D_GNU_SOURCE','-D_FILE_OFFSET_BITS=64','-DHAVE_CONFIG_H','-I'+str(REPO/'src'),'-I'+str(build),'-I'+str(build/'src'),str(generated),str(repaired),str(build/'src/libfsearch.a'),*pkg,'-lm','-pthread','-o',str(binary)]
 result=subprocess.run(command,capture_output=True,text=True);(evidence/'compile.txt').write_text(shlex.join(command)+'\n'+result.stdout+result.stderr)
 result.check_returncode();return binary

def main():
 parser=argparse.ArgumentParser();parser.add_argument('build',type=Path);parser.add_argument('evidence',type=Path);parser.add_argument('--samples',type=int,default=100);args=parser.parse_args()
 evidence=args.evidence.resolve();evidence.mkdir(parents=True,exist_ok=True);binary=compile_probe(args.build.resolve(),evidence)
 summary={'matcher_lifetime_fix':'Prototype-only: free previous UTF builder string before replacement, identical for all engines. Production remains unchanged.', 'broad_query_strategy':'Native pivot >4096 or SQLite >4096 candidates => sequential fallback, preserving caps and output semantics.', 'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'samples':args.samples,'prototype_only':True,'boundaries':'Virtual filename records only; 256 MiB AS; 64 MiB snapshot; 500k verification and separate posting-operation cap. Matcher/stdio latency, not public socket or installed acceptance.','cases':[],'resources':[],'failures':[]}
 summary['hashes']={str(p.relative_to(REPO)) if p.is_relative_to(REPO) else p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (REPO/'src/fsearch_headless.c',REPO/'src/fsearch_utf.c',evidence/'fsearch_utf-prototype-fixed.c',REPO/'src/prototypes/trigram_probe.c',REPO/'src/prototypes/benchmark_trigram.py',evidence/'trigram-probe.generated.c',binary)}
 def save(): (evidence/'benchmark.json').write_text(json.dumps(summary,indent=2,ensure_ascii=True)+'\n')
 with tempfile.TemporaryDirectory(prefix='fsearch-trigram-owned-') as temporary:
  work=Path(temporary)
  for count in (100000,1000000):
   print(f'Building {count} virtual records',flush=True);snapshot=work/f'fixture-{count}.db'
   started=time.perf_counter();built=subprocess.run([str(binary),'build',str(snapshot),str(count)],capture_output=True,timeout=90)
   (evidence/f'build-{count}.txt').write_bytes(built.stdout+built.stderr)
   if built.returncode:
    summary['failures'].append({'files':count,'stage':'fixture_build','returncode':built.returncode,'stderr':built.stderr.decode(errors='replace')});save();continue
   snapshot.chmod(0o600);summary.setdefault('fixtures',[]).append({'files':count,'snapshot_bytes':snapshot.stat().st_size,'build_ms':(time.perf_counter()-started)*1000,'sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest()})
   oracle={};exhaustive={}
   with (evidence/f'oracle-{count}.stderr.txt').open('wb') as err:
    oracle_process=subprocess.Popen([str(binary),'oracle',str(snapshot),'unused'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err)
    try:
     oracle_ready=readline(oracle_process,35)
     assert oracle_ready.get('ready'),oracle_ready
     for label,query,options in CASES:
      exhaustive[label]=request(oracle_process,query,dict(options,max_candidates=count+65))['response']
    finally:
     oracle_process.stdin.close()
     try:oracle_process.wait(timeout=3)
     except subprocess.TimeoutExpired:oracle_process.kill();oracle_process.wait(timeout=3)
     oracle_process.stdout.close()
   summary.setdefault('exhaustive_oracles',[]).append({'files':count,'cases':exhaustive,'note':'Test-only exhaustive verification cap; no public or installed cap was changed.'})
   for mode in ('linear','native','sqlite'):
    print(f'{count}: {mode}',flush=True)
    errors=evidence/f'{mode}-{count}.stderr.txt'
    with errors.open('wb') as err:
     process=subprocess.Popen([str(binary),mode,str(snapshot),'unused'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err)
     try:
      ready=readline(process,35)
      if not ready.get('ready'):summary['failures'].append({'files':count,'mode':mode,'stage':'load','response':ready});continue
      ready.update(files=count,mode=mode,startup_within_2s=ready['load_ms']+ready['build_ms']<=2000);summary['resources'].append(ready);save()
      for label,query,options in CASES:
       first=request(process,query,options)
       if mode=='linear':oracle[label]=first['response']
       expected=oracle[label]
       comparison='exact_parity' if normalize(first['response'])==normalize(expected) else 'bounded_candidate_rejection' if first['candidate_limited'] else 'linear_work_cap_incomparable' if expected.get('status')=='work_limit' else 'MISMATCH'
       if first['response'].get('status') not in ('work_limit',None):
        assert normalize(first['response'])==normalize(exhaustive[label]),(count,mode,label,'exhaustive oracle mismatch')
       assert comparison!='MISMATCH',(count,mode,label,first,expected)
       row={'files':count,'mode':mode,'label':label,'query':query,'options':options,'comparison':comparison,'first':first,'oracle':expected}
       if label in BENCH:
        samples=[];pipe=[];cpu=[]
        for _ in range(3):request(process,query,options)
        for _ in range(args.samples):
         r=request(process,query,options)
         assert normalize(r['response'])==normalize(first['response']),(label,'unstable result')
         samples.append(r['elapsed_ms']);pipe.append(r['pipe_ms']);cpu.append(r['cpu_ms'])
        row.update(matcher_ms=percentiles(samples),pipe_ms=percentiles(pipe),cpu_ms=percentiles(cpu),raw_matcher_ms=samples,raw_pipe_ms=pipe)
       summary['cases'].append(row);save()
     except (RuntimeError,TimeoutError,json.JSONDecodeError) as exc:
      summary['failures'].append({'files':count,'mode':mode,'stage':'bounded_execution','error':str(exc)});save()
     finally:
      if process.poll() is None:process.stdin.close()
      try:process.wait(timeout=3)
      except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
      process.stdout.close()
   # Query trace is separate from latency, with explicit requests after READY.
   trace=evidence/f'query-{count}.trace'
   traced=subprocess.run(['strace','-f','-e','trace=%file','-o',str(trace),str(binary),'native',str(snapshot),'unused'],input=b'0 0 500000 1048576 100\tinvoice-unique-zqx\n0 0 500000 1048576 100\tdepartment-63-invoice-path\n',capture_output=True,timeout=40)
   summary.setdefault('isolation',[]).append({'files':count,'returncode':traced.returncode,'indexed_root_file_syscalls':sum('/__fsearch_trigram_virtual_owned__' in line for line in trace.read_text().splitlines())})
   save()
 summary['completed']=True;save();print('Complete:',evidence/'benchmark.json',flush=True)
if __name__=='__main__':main()
