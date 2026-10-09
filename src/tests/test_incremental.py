"""Actual filesystem-to-catalog visibility through confined watcher and updater."""
import base64,io,json,os,runpy,signal,socket,subprocess,sys,tempfile,time,types
from pathlib import Path
service,incremental,fixture=sys.argv[1:];os.umask(0o077)
# A watcher may pause while traversing an admitted populated subtree. Idle
# heartbeats must retain pending coverage until its explicit end marker.
implementation=runpy.run_path(incremental)
class InventoryWatcher:
    def __init__(self):self.messages=iter([{'status':'inventory','phase':'begin','sequence':0,'observed_monotonic_us':time.monotonic_ns()//1000-5_000_000},None,{'status':'inventory','phase':'end','sequence':0,'observed_monotonic_us':time.monotonic_ns()//1000},None])
    def message(self,timeout):
        message=next(self.messages)
        if message is None:time.sleep(.51)
        return message
class CoverageClient:
    def __init__(self):self.frames=[]
    def coverage(self,*args,**kwargs):self.frames.append((args,kwargs))
coverage_client=CoverageClient();before_inventory_unix_ms=int(time.time()*1000)
try:implementation['ingest'](InventoryWatcher(),coverage_client,b'/owned-fixture')
except StopIteration:pass
frames=coverage_client.frames
assert len(frames)==4,frames
assert frames[0][0][0]==frames[1][0][0]=='pending' and frames[0][0][3]==frames[1][0][3] is not None,frames
assert frames[1][1]['reason']=='subtree_inventory',frames
assert frames[0][0][3]<=before_inventory_unix_ms-4900,('watcher backlog age was reset at receipt',frames)
assert frames[-1][0][0]=='watching' and frames[-1][0][3] is None,frames
class EventWatcher:
    def __init__(self,stamp):self.messages=iter([{'status':'event','sequence':1,'observed_monotonic_us':stamp,'mask':0x100,'cookie':0,'kind':1,'parent_b64':'','name_b64':'YWdlZC50eHQ='}])
    def message(self,timeout):return next(self.messages)
class EventClient(CoverageClient):
    def lookup(self,path):raise StopIteration
aged_client=EventClient();before_event_unix_ms=int(time.time()*1000)
try:implementation['ingest'](EventWatcher(time.monotonic_ns()//1000-5_000_000),aged_client,b'/owned-fixture')
except StopIteration:pass
assert aged_client.frames[0][0][3]<=before_event_unix_ms-4900,aged_client.frames
for stamp in (None,True,-1,'invalid',time.monotonic_ns()//1000+1_000_000_000):
    try:implementation['ingest'](EventWatcher(stamp),EventClient(),b'/owned-fixture')
    except implementation['BoundaryError'] as exc:assert str(exc)=='event_observation_time',exc
    else:raise AssertionError(('invalid source observation accepted',stamp))
class BarrierWatcher:
    def __init__(self,messages):self.messages=iter(messages);self.worker=types.SimpleNamespace(stdin=io.BytesIO())
    def message(self,timeout):return next(self.messages)
barrier_stamp=time.monotonic_ns()//1000
clean_barrier=BarrierWatcher([{'status':'heartbeat','sequence':0,'observed_monotonic_us':barrier_stamp},{'status':'barrier','sequence':0,'observed_monotonic_us':barrier_stamp}])
implementation['ContinuousWatcher'].barrier(clean_barrier,1)
assert clean_barrier.worker.stdin.getvalue()==b'B'
try:implementation['ContinuousWatcher'].barrier(BarrierWatcher([{'status':'event','sequence':1}]),1)
except implementation['monitor'].GenerationChanged:pass
else:raise AssertionError('dirty startup barrier accepted')
try:implementation['ContinuousWatcher'].barrier(BarrierWatcher([None]),1)
except implementation['BoundaryError'] as exc:assert str(exc)=='watcher_barrier_timeout',exc
else:raise AssertionError('unacknowledged startup barrier accepted')
# A healthy updater must not conceal a watcher that has stopped making progress.
clock=[time.monotonic()]
class SilentWatcher:
    def __init__(self):self.calls=0
    def message(self,timeout):
        self.calls+=1
        if self.calls>12:raise StopIteration
        clock[0]+=.25;return None
silent_client=CoverageClient();globals_=implementation['ingest'].__globals__;real_time=globals_['time']
globals_['time']=types.SimpleNamespace(monotonic=lambda:clock[0],monotonic_ns=lambda:int(clock[0]*1e9),time=time.time)
try:
    try:implementation['ingest'](SilentWatcher(),silent_client,b'/owned-fixture')
    except implementation['BoundaryError'] as exc:assert str(exc)=='watcher_progress_timeout',exc
    else:raise AssertionError('silent watcher was accepted as healthy')
finally:globals_['time']=real_time
assert silent_client.frames[-1][0][0]=='deferred' and silent_client.frames[-1][1]['reason']=='watcher_progress_timeout',silent_client.frames
with tempfile.TemporaryDirectory(prefix='fsearch-incremental-') as tmp:
    work=Path(tmp);root=work/'owned';(root/'nested').mkdir(parents=True);(root/'initial.txt').touch()
    database=work/'snapshot.db';sock=work/'q.sock'
    subprocess.run([fixture,'build',str(database),str(root)],check=True,stdout=subprocess.DEVNULL)
    server=subprocess.Popen([sys.executable,service,'serve','--socket',str(sock),'--database',str(database)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
    updater=None;latencies={'normal':[],'heavy':[],'reconciliation':[]}
    def query(text):
        with socket.socket(socket.AF_UNIX) as stream:
            stream.settimeout(3);stream.connect(str(sock));stream.sendall(json.dumps({'schema_version':1,'request_id':'freshness','query':text,'limit':1000}).encode()+b'\n');data=b''
            while b'\n' not in data:
                chunk=stream.recv(65536);assert chunk;data+=chunk
            return json.loads(data)
    def visible(text,present=True,deadline=1,started=None,category="normal",expected_path=None):
        started=time.monotonic() if started is None else started
        while True:
            result=query(text)
            if result.get('status')=='ok' and bool(result['results'])==present and (expected_path is None or len(result['results'])==1 and result['results'][0]['path']==str(expected_path)):latencies[category].append(time.monotonic()-started);return result
            assert time.monotonic()-started<deadline,(text,present,result)
            time.sleep(.005)
    try:
        limit=time.monotonic()+5
        while True:
            try:
                if query('initial').get('status')=='ok':break
            except OSError:pass
            assert time.monotonic()<limit;time.sleep(.01)
        log=work/'updater.log'
        with log.open('wb') as output:
            updater=subprocess.Popen([sys.executable,incremental,'--root',str(root),'--database',str(database),'--socket',str(sock)],stdout=output,stderr=subprocess.PIPE,start_new_session=True)
            limit=time.monotonic()+5
            while '"status": "watching"' not in log.read_text():
                assert updater.poll() is None,log.read_text()+updater.stderr.read().decode()
                assert time.monotonic()<limit;time.sleep(.01)
            initial=query('initial')['incremental_coverage'];assert initial['state'] in ('watching','pending') and initial['last_reconciled_unix_ms'] is not None
            assert base64.b64decode(initial['root_b64'])==os.fsencode(root)
            start=time.monotonic();(root/'created.txt').touch();visible('created',started=start)
            start=time.monotonic();os.rename(root/'created.txt',root/'nested'/'renamed.txt');visible('renamed',started=start);visible('created',False)
            (root/'victim.txt').touch();visible('victim');start=time.monotonic();os.rename(root/'nested'/'renamed.txt',root/'victim.txt');visible('renamed',False,started=start);visible('victim')
            start=time.monotonic();os.link(root/'victim.txt',root/'hardlink.txt');visible('hardlink',started=start)
            start=time.monotonic();os.unlink(root/'hardlink.txt');visible('hardlink',False,started=start)
            raw=os.fsencode(root)+b'/raw-\xff.txt';start=time.monotonic();fd=os.open(raw,os.O_CREAT|os.O_WRONLY,0o600);os.close(fd)
            reply=visible('raw-',started=start);assert base64.b64decode(reply['results'][0]['path_bytes_base64'])==raw
            os.symlink(work/'outside',root/'excluded-link');assert not query('excluded-link')['results']
            start=time.monotonic()
            for i in range(1100):(root/f'burst-{i:04}.txt').touch()
            visible('burst-1099',deadline=10,started=start,category='heavy')
            assert '"catalog_sequence": 1024' in log.read_text()
            before=query('initial')['snapshot']['identity']
            start=time.monotonic();(root/'new-directory').mkdir();(root/'new-directory'/'early-child.txt').touch();visible('early-child',deadline=1,started=start)
            assert query('initial')['snapshot']['identity']==before
            start=time.monotonic();os.rename(root/'new-directory',root/'moved-directory');reply=visible('early-child',started=start,expected_path=root/'moved-directory'/'early-child.txt')
            assert query('initial')['snapshot']['identity']==before
            (root/'empty-victim').mkdir();visible('empty-victim');start=time.monotonic();os.rename(root/'moved-directory',root/'empty-victim')
            reply=visible('early-child',started=start,expected_path=root/'empty-victim'/'early-child.txt')
            assert query('initial')['snapshot']['identity']==before
            incoming=work/'incoming';(incoming/'deep').mkdir(parents=True);(incoming/'deep'/'imported.txt').touch()
            start=time.monotonic();os.rename(incoming,root/'incoming');visible('imported',started=start)
            assert query('initial')['snapshot']['identity']==before
            start=time.monotonic();os.rename(root/'incoming',work/'outgoing');visible('imported',False,started=start)
            (work/'outgoing'/'private-outside-name.txt').touch();assert not query('private-outside-name')['results']
            assert 'directory_topology' not in log.read_text()
            limit=time.monotonic()+3
            while query('initial')['incremental_coverage']['state']!='watching':
                assert time.monotonic()<limit;time.sleep(.01)
            # Pause only the current recorded child, before any abrupt parent
            # death. Never restart a quarantined previous updater to run a test.
            record=json.loads(Path(str(database)+'.incremental.state').read_text())['worker']
            watcher_pid=record['pid']
            status=Path(f'/proc/{watcher_pid}/status').read_text()
            assert int(next(line.split()[1] for line in status.splitlines() if line.startswith('PPid:')))==updater.pid
            started=time.monotonic();os.kill(watcher_pid,signal.SIGSTOP);limit=started+5
            while True:
                retained=query('burst-1099');health=retained['incremental_coverage']
                if health['reason']=='watcher_progress_timeout':break
                assert time.monotonic()<limit,(retained,log.read_text());time.sleep(.02)
            assert retained['results'] and retained['complete'] and health['state']=='deferred'
            assert updater.wait(timeout=3)==1
            assert not Path(f'/proc/{watcher_pid}').exists(),'stopped watcher was not reaped'
            watcher_stall_seconds=time.monotonic()-started
            with (work/'updater-restarted.log').open('wb') as restarted_output:
                updater=subprocess.Popen([sys.executable,incremental,'--root',str(root),'--database',str(database),'--socket',str(sock)],stdout=restarted_output,stderr=subprocess.PIPE,start_new_session=True)
                limit=time.monotonic()+5
                while '"status": "watching"' not in (work/'updater-restarted.log').read_text():
                    assert updater.poll() is None and time.monotonic()<limit,((work/'updater-restarted.log').read_text(),updater.stderr.read().decode() if updater.poll() is not None else 'still running');time.sleep(.01)
                os.kill(updater.pid,signal.SIGKILL);updater.wait(timeout=3)
                limit=time.monotonic()+3
                while True:
                    cached=query('burst-1099');coverage=cached['incremental_coverage']
                    if coverage['reason']=='watcher_lease_expired':break
                    assert time.monotonic()<limit;time.sleep(.02)
                assert cached['results'] and cached['complete'] and coverage['state']=='deferred'
            print(json.dumps({'result':'pass','normal_max_seconds':max(latencies['normal']),'heavy_seconds':latencies['heavy'][0],'watcher_stall_deferred_seconds':watcher_stall_seconds,'topology_reconciliation_seconds':None,'burst_events':1100,'checks':['create','cross-parent rename','replace rename','hardlink','delete','raw bytes','excluded symlink','background compaction threshold','clean/dirty/unacknowledged startup drain barriers','source observation age survives queued inventory/events','invalid observation clocks fail closed','idle inventory heartbeat stays pending','directory create inventory','directory ancestor rename','directory replacement rename','subtree import','subtree move out without outside indexing','no snapshot replacement for directory changes','query-visible exact root/last reconciliation','abrupt updater death expires coverage lease and retains cached view','paused native watcher fails deferred while updater is alive and cached queries remain complete','paused watcher is killed and reaped'],'scope':'owned fixture actual mutation to native socket query'}))
    finally:
        for proc in (updater,server):
            if proc:
                if proc.poll() is None:os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
