import json,hashlib,shlex,subprocess,tempfile,socket,time,os
from pathlib import Path
repo=Path('/home/ecochran76/workspace.local/fsearch');e=repo/'docs/research/production-evidence';build=Path('/tmp/fsearch-warm-release-build')
with tempfile.TemporaryDirectory(prefix='fsearch-unicode-production-') as t:
 work=Path(t);binary=work/'fixture-probe';command=shlex.split((repo/'docs/research/trigram-evidence/compile.txt').read_text().splitlines()[0]);command=[arg for arg in command if not arg.endswith('fsearch_utf-prototype-fixed.c')];command[command.index('-o')+1]=str(binary)
 r=subprocess.run(command,capture_output=True,text=True);r.check_returncode()
 snapshot=work/'snapshot.db';subprocess.run([str(binary),'build',str(snapshot),'100000'],check=True);snapshot.chmod(0o600);sock=work/'search.sock'
 server=subprocess.Popen([str(build/'src/fsearch-service'),'serve','--socket',str(sock),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def query(i):
  deadline=time.monotonic()+5
  while True:
   c=socket.socket(socket.AF_UNIX);c.settimeout(5)
   try:c.connect(str(sock));break
   except (ConnectionRefusedError,FileNotFoundError):
    c.close()
    if time.monotonic()>deadline:raise
    time.sleep(.005)
  with c:
   c.sendall((json.dumps({'schema_version':1,'request_id':str(i),'query':'école','kind':'files'})+'\n').encode());raw=bytearray()
   while b'\n' not in raw:raw.extend(c.recv(65536))
  result=json.loads(raw);assert result['complete'] and len(result['results'])==1,result
  assert result['results'][0]['path'].endswith('/CAFÉ-ÉCOLE.pdf'),result
  return result
 def worker_state():return json.loads(Path(str(sock)+'.state').read_text())['worker']
 def rss(pid):return int(next(line.split()[1] for line in Path(f'/proc/{pid}/status').read_text().splitlines() if line.startswith('VmRSS:')))
 try:
  for i in range(5):query(i)
  state=worker_state();before=rss(state['pid']);start=time.monotonic()
  for i in range(100):query(i+5)
  after=rss(state['pid']);assert worker_state()==state;assert after-before<=4096,(before,after)
  receipt={'snapshot_files':100000,'unicode_queries_after_warmup':100,'same_worker':True,'worker_before_rss_kib':before,'worker_after_rss_kib':after,'growth_kib':after-before,'elapsed_seconds':time.monotonic()-start,'prototype_matcher_override':False,'source_utf_sha256':hashlib.sha256((repo/'src/fsearch_utf.c').read_bytes()).hexdigest(),'worker_sha256':hashlib.sha256((build/'src/fsearch-worker').read_bytes()).hexdigest()}
  (e/'unicode-original-workload-green.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
 finally:
  server.terminate();server.communicate(timeout=5)
