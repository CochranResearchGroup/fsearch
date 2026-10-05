#!/usr/bin/env python3
"""Supplement exact duplicate-basename ordering parity on owned virtual records."""
import hashlib,json,subprocess,tempfile,sys
from pathlib import Path
from benchmark_trigram import compile_probe,readline,request,normalize
build,evidence=map(lambda x:Path(x).resolve(),sys.argv[1:3])
binary=compile_probe(build,evidence,duplicate_fixture=True)
summary={'fixture':'1024 virtual files; first four identical basenames in different parents','cases':[],'generated_source_sha256':hashlib.sha256((evidence/'duplicate-trigram-probe.generated.c').read_bytes()).hexdigest()}
with tempfile.TemporaryDirectory(prefix='fsearch-trigram-duplicate-') as t:
 snapshot=Path(t)/'fixture.db';subprocess.run([str(binary),'build',str(snapshot),'1024'],check=True);snapshot.chmod(0o600)
 oracle={}
 for mode in ('linear','native','sqlite'):
  p=subprocess.Popen([str(binary),mode,str(snapshot),'unused'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   assert readline(p)['ready']
   for query,options in [('duplicate-common',{}),('DUPLICATE',{}),('duplicate',{'extension':'pdf'}),('duplicate',{'limit':1}),('duplicate',{'max_bytes':512}),('duplicate',{'kind':2}),('department-03',{'flags':1})]:
    r=request(p,query,options)['response'];key=(query,tuple(options.items()))
    if mode=='linear':oracle[key]=r
    assert normalize(r)==normalize(oracle[key]),(mode,query,r,oracle[key])
    if query=='duplicate-common':assert len(r['results'])==4 and r['complete'],r
    summary['cases'].append({'mode':mode,'query':query,'options':options,'response':r})
  finally:p.stdin.close();p.wait(timeout=3);p.stdout.close();p.stderr.close()
(evidence/'duplicate-parity.json').write_text(json.dumps(summary,indent=2)+'\n');print('21 duplicate fixture cases passed')
