"""Real confined continuous events on owned roots; gaps are explicit and terminal."""
import base64,json,os,select,subprocess,sys,tempfile,time
from pathlib import Path
worker,fault=sys.argv[1:];os.umask(0o077)
class Watch:
    def __init__(self,root,**extra):
        self.proc=subprocess.Popen([worker,'--root',str(root),'--events'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={**os.environ,**extra})
        self.buffer=bytearray();self.proc.stdin.write(b'G');self.proc.stdin.flush()
    def read(self):
        deadline=time.monotonic()+3
        while b'\n' not in self.buffer:
            assert select.select([self.proc.stdout],[],[],max(0,deadline-time.monotonic()))[0],('event timeout',self.proc.poll())
            chunk=os.read(self.proc.stdout.fileno(),65536);assert chunk,('event EOF',self.proc.stderr.read());self.buffer.extend(chunk)
        line,_,rest=self.buffer.partition(b'\n');self.buffer=bytearray(rest);return json.loads(line)
    def ready(self):
        assert self.read()['status']=='ready'
        assert self.read()=={'schema_version':1,'status':'coverage','reconciliation_required':True,'reason':'startup_gap'}
    def stop(self):
        if self.proc.poll() is None:self.proc.terminate()
        self.proc.wait(timeout=3)
with tempfile.TemporaryDirectory(prefix='fsearch-events-') as tmp:
    root=Path(tmp)/'owned';(root/'nested').mkdir(parents=True)
    outside=Path(tmp)/'outside';outside.mkdir();(outside/'secret.txt').touch()
    watch=Watch(root)
    try:
        watch.ready();name=b'raw-\xff.txt';path=os.fsencode(root/'nested')+b'/'+name
        fd=os.open(path,os.O_CREAT|os.O_WRONLY,0o600);os.close(fd)
        created=watch.read();assert created['mask']&0x100 and created['sequence']==1
        assert base64.b64decode(created['parent_b64'])==b'nested' and base64.b64decode(created['name_b64'])==name
        dest=os.fsencode(root/'nested')+b'/renamed.txt';os.rename(path,dest)
        old,new=watch.read(),watch.read();assert old['mask']&0x40 and new['mask']&0x80 and old['cookie']==new['cookie']!=0
        assert (old['sequence'],new['sequence'])==(2,3)
        os.symlink(outside/'secret.txt',root/'nested'/'excluded-link')
        os.link(dest,root/'nested'/'hardlink.txt')
        linked=watch.read();assert linked['sequence']==4 and base64.b64decode(linked['name_b64'])==b'hardlink.txt'
        os.unlink(root/'nested'/'hardlink.txt');deleted=watch.read();assert deleted['mask']&0x200 and deleted['sequence']==5
        (root/'new-directory').mkdir();gap=watch.read();assert gap['status']=='gap' and gap['reason']=='directory_topology'
        assert watch.proc.wait(timeout=3)==4
    finally:watch.stop()
    watch=Watch(root)
    try:
        watch.ready();os.rename(root,Path(tmp)/'relocated');gap=watch.read()
        assert gap['status']=='gap' and gap['reason']=='root_offline';assert watch.proc.wait(timeout=3)==4
    finally:watch.stop()
    root.mkdir();watch=Watch(root,LD_PRELOAD=fault,FSEARCH_MONITOR_FIXTURE_OVERFLOW='1')
    try:
        watch.ready();assert watch.read()['reason']=='overflow';assert watch.proc.wait(timeout=3)==4
    finally:watch.stop()
    watch=Watch(root,LD_PRELOAD=fault,FSEARCH_MONITOR_FIXTURE_WATCH_FAILURE='1')
    try:
        assert watch.read()['error']['code']=='coverage_incomplete';assert watch.proc.wait(timeout=3)==3
    finally:watch.stop()
print(json.dumps({'result':'pass','events':5,'checks':['raw-byte create','paired file rename','hard links','excluded symlinks','delete','startup gap','directory topology gap and watch release','root relocation','overflow injection','watch exhaustion'],'scope':'owned fixture roots, native Landlock/openat2 worker'}))
