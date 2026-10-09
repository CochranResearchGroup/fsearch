"""Owned synthetic native experiment; never invokes installed runtime or scans roots."""
import base64,itertools,json,subprocess,sys,tempfile,time,resource,os
from pathlib import Path
binary=sys.argv[1];mode=sys.argv[2];count=int(sys.argv[3]) if len(sys.argv)>3 else 128
startup=time.monotonic()
p=subprocess.Popen([binary,str(count)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def read():
 line=p.stdout.readline()
 if not line:raise RuntimeError('native worker EOF: '+p.stderr.read()[-2000:])
 return json.loads(line)
def send(line):p.stdin.write(line+'\n');p.stdin.flush();return read()
def update(i,parent,kind,name):return send(f'U\t{i}\t{parent}\t{kind}\t'+base64.b64encode(name.encode()).decode())
def query(text,path=False,case=False,kind='all',extension='-',limit=1000):
 return send(f'Q\t{int(path)}\t{int(case)}\t{kind}\t{extension}\t'+base64.b64encode(text.encode()).decode()+f'\t{limit}')
assert read()['ready']
startup_seconds=time.monotonic()-startup
started=time.monotonic();comparisons=0;exact_order_differences=0;prefix_checks=0
try:
 if mode=='correctness':
  phases=[]
  with tempfile.TemporaryDirectory(prefix='PROTOTYPE-native-incremental-') as tmp:
   def parity(label):
    global comparisons,exact_order_differences,prefix_checks
    assert send('S\t'+str(Path(tmp)/'PROTOTYPE-snapshot.db'))['saved']
    for text,path,case,kind,extension in itertools.product(['','file','café','ÉCOLE','STRASSE','İ','[x]','*','?','alpha','moved','raw','😀','quote'],[False,True],[False,True],['all','files','folders'],['-','txt','pdf']):
     actual=query(text,path,case,kind,extension);expected=read();assert expected['status']=='ok',(label,expected.get('status'))
     gold=[base64.b64decode(row['path_bytes_base64']) if row.get('path_bytes_base64') else os.fsencode(row['path']) for row in expected['results']]
     got=[base64.b64decode(x) for x in actual['paths_b64']]
     assert sorted(got)==sorted(gold),(label,text,path,case,kind,extension,got[:3],gold[:3])
     offset=0
     for size in actual['order_group_sizes']:
      assert sorted(got[offset:offset+size])==sorted(gold[offset:offset+size]),('order',label,text,offset,size)
      offset+=size
     assert offset==len(got)
     exact_order_differences+=got!=gold;comparisons+=1
     # Exercise native bounded responses and the candidate's actual merge prefix.
     if text in ('','file','quote') and not path and not case and kind=='all' and extension=='-':
      for limit in (1,7,31):
       short=query(text,path,case,kind,extension,limit);native=read()
       nativepaths=[base64.b64decode(row['path_bytes_base64']) if row.get('path_bytes_base64') else os.fsencode(row['path']) for row in native['results']]
       shortpaths=[base64.b64decode(x) for x in short['paths_b64']]
       assert shortpaths==got[:limit]
       assert nativepaths==gold[:limit]
       # At a tied cutoff the full equivalence group defines admissible members.
       offset=0
       for size in actual['order_group_sizes']:
        taken=min(size,max(0,limit-offset))
        if taken==size:assert sorted(shortpaths[offset:offset+size])==sorted(nativepaths[offset:offset+size])
        elif taken:assert set(shortpaths[offset:offset+taken])<=set(gold[offset:offset+size])
        offset+=size
       prefix_checks+=1
    phases.append(label)
   parity('base')
   assert update(count+3,2,1,'new*quote?.txt')['accepted'];parity('create literal filename')
   assert update(3,1,1,'école-renamed.pdf')['accepted'];parity('Unicode file rename')
   assert update(1,0,2,'moved')['accepted'];parity('ancestor rename')
   assert not update(1,2,2,'cycle')['accepted'];assert not update(count+4,9999999,1,'escape')['accepted']
   assert update(14,0,1,'STRASSE.txt')['accepted'];parity('duplicate basename tied group')
   assert update(15,0,1,'aaa-first.txt')['accepted'];parity('move across parent and sort position')
   assert update(1,0,0,'deleted')['accepted'];parity('ancestor delete')
   assert not update(1,0,2,'moved')['accepted']
   assert update(count+4,0,2,'moved')['accepted'];parity('recreate name with new identity')
   assert update(count+5,count+4,1,'fresh.txt')['accepted'];parity('new child, no resurrected descendants')
   before=query('fresh');read()
   # Fill capacity; first failure must preserve previous accepted results.
   deferred_at=None
   for i in range(3000):
    if not update(count+6+i,0,1,f'budget-{i}')['accepted']:deferred_at=i;break
   assert deferred_at is not None
   after=query('fresh');read();assert after['coverage']=='deferred' and after['paths_b64']==before['paths_b64']
  result={'mode':mode,'comparisons':comparisons,'ordered_prefix_checks':prefix_checks,'exact_sequence_differences_within_ties':exact_order_differences,'phases':phases,'deferred_at':deferred_at,'result':'pass','memory':send('R'),'elapsed_seconds':time.monotonic()-started,'ordering':'native files-then-folders comparator group parity; equal-name tie order unspecified'}
 else:
  def rss():
   line=next(s for s in Path('/proc',str(p.pid),'status').read_text().splitlines() if s.startswith('VmRSS:'));return int(line.split()[1])*1024
  base_rss=rss();normal=[]
  for i in range(20):
   t=time.monotonic();time.sleep(.1);assert update(count+3+i,2,1,f'normal-{i}.txt')['accepted'];q=query(f'normal-{i}.txt');assert len(q['paths_b64'])==1;normal.append((time.monotonic()-t)*1000)
  t=time.monotonic();time.sleep(.25)
  for i in range(1000):assert update(count+23+i,2,1,f'batch-{i}.txt')['accepted']
  q=query('batch-');assert len(q['paths_b64'])==1000
  heavy=(time.monotonic()-t)*1000
  name_samples=[];path_samples=[];name_examined=[]
  for i in range(20):
   q=query('normal-19.txt');name_samples.append(q['elapsed_ms']);name_examined.append(q['examined'])
  for i in range(5):q=query('normal-19.txt',True);path_samples.append(q['elapsed_ms'])
  result={'mode':mode,'startup_seconds':startup_seconds,'max_name_query_examined':max(name_examined),'entries':count+3,'normal_events':20,'normal_visibility_ms':{'p95':sorted(normal)[18],'max':max(normal)},'heavy_events':1000,'heavy_visibility_ms':heavy,'base_worker_rss_bytes':base_rss,'final_worker_rss_bytes':rss(),'worker_memory':send('R'),'driver_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'last_query_examined':q['examined'],'last_query_candidate_blocks':q['candidate_blocks'],'native_name_query_p95_ms':sorted(name_samples)[18],'native_path_query_max_ms':max(path_samples),'elapsed_seconds':time.monotonic()-started,'scope':'native matcher plus synthetic records and full-path fixture oracle; shared native signature helpers and immutable base bitplanes; no real watcher, compaction or installed service; heavy events sent serially'}
 print(json.dumps(result,indent=2))
finally:
 p.stdin.close()
 try:p.wait(timeout=2)
 except subprocess.TimeoutExpired:p.kill();p.wait()
