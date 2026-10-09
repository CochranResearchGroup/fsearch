"""Actual filesystem-to-catalog visibility through confined watcher and updater."""
import base64,json,os,signal,socket,subprocess,sys,tempfile,time
from pathlib import Path
service,incremental,fixture=sys.argv[1:];os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='fsearch-incremental-') as tmp:
    work=Path(tmp);root=work/'owned';(root/'nested').mkdir(parents=True);(root/'initial.txt').touch()
    database=work/'snapshot.db';sock=work/'q.sock'
    subprocess.run([fixture,'build',str(database),str(root)],check=True,stdout=subprocess.DEVNULL)
    server=subprocess.Popen([sys.executable,service,'serve','--socket',str(sock),'--database',str(database)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
    updater=None;latencies=[]
    def query(text):
        with socket.socket(socket.AF_UNIX) as stream:
            stream.settimeout(3);stream.connect(str(sock));stream.sendall(json.dumps({'schema_version':1,'request_id':'freshness','query':text,'limit':1000}).encode()+b'\n');data=b''
            while b'\n' not in data:
                chunk=stream.recv(65536);assert chunk;data+=chunk
            return json.loads(data)
    def visible(text,present=True,deadline=1,started=None):
        started=time.monotonic() if started is None else started
        while True:
            result=query(text)
            if result.get('status')=='ok' and bool(result['results'])==present:latencies.append(time.monotonic()-started);return result
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
            visible('burst-1099',deadline=10,started=start)
            assert '"catalog_sequence": 1024' in log.read_text()
            start=time.monotonic();(root/'new-directory').mkdir();visible('new-directory',deadline=5,started=start)
            assert 'directory_topology' in log.read_text()
            limit=time.monotonic()+3
            while query('initial')['incremental_coverage']['state']!='watching':
                assert time.monotonic()<limit;time.sleep(.01)
            os.kill(updater.pid,signal.SIGKILL);updater.wait(timeout=3)
            limit=time.monotonic()+3
            while True:
                cached=query('burst-1099');coverage=cached['incremental_coverage']
                if coverage['reason']=='watcher_lease_expired':break
                assert time.monotonic()<limit;time.sleep(.02)
            assert cached['results'] and cached['complete'] and coverage['state']=='deferred'
            print(json.dumps({'result':'pass','normal_max_seconds':max(latencies[:-2]),'heavy_seconds':latencies[-2],'topology_reconciliation_seconds':latencies[-1],'burst_events':1100,'checks':['create','cross-parent rename','replace rename','hardlink','delete','raw bytes','excluded symlink','background compaction threshold','directory gap reconciliation','query-visible exact root/last reconciliation','abrupt updater death expires coverage lease and retains cached view'],'scope':'owned fixture actual mutation to native socket query'}))
    finally:
        for proc in (updater,server):
            if proc:
                if proc.poll() is None:os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
