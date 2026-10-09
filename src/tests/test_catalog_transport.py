"""Exercise the actual private supervisor/worker mutation interface on owned data."""
import base64,json,os,shutil,socket,subprocess,sys,tempfile,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
service,fixture=sys.argv[1:];os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='fsearch-catalog-transport-') as tmp:
    work=Path(tmp);root=work/'owned';root.mkdir();(root/'initial.txt').touch()
    database=work/'snapshot.db';subprocess.run([fixture,'build',str(database),str(root)],check=True,stdout=subprocess.DEVNULL)
    sock=work/'q.sock';server=subprocess.Popen([sys.executable,service,'serve','--socket',str(sock),'--database',str(database)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    def call(op='catalog_status',**fields):
        with socket.socket(socket.AF_UNIX) as stream:
            stream.settimeout(5);stream.connect(str(sock));request={'schema_version':1,'request_id':'catalog-test','op':op,**fields}
            stream.sendall(json.dumps(request).encode()+b'\n');data=b''
            while b'\n' not in data:
                chunk=stream.recv(65536);assert chunk;data+=chunk
            return json.loads(data)
    def query(text):return call('query',query=text,limit=1000)
    try:
        deadline=time.monotonic()+5
        while True:
            try:
                first=call()
                if first['status']=='catalog_status':break
            except (OSError,AssertionError):pass
            assert time.monotonic()<deadline,('service readiness',server.poll())
            time.sleep(.02)
        identity=first['snapshot_id'];assert first['sequence']==0 and first['durable'] is False
        def lookup(path):return call('catalog_lookup',path_b64=base64.b64encode(os.fsencode(path)).decode(),expected_snapshot_id=identity)
        located=lookup(root);assert located['status']=='catalog_located';parent=located['entry_id']
        found=lookup(root/'initial.txt');original=found['entry_id']
        assert lookup(work/'outside')['status']=='catalog_missing'
        def apply(seq,name,kind=1,entry=None,parent_id=parent,expected=identity):
            fields={'sequence':seq,'parent_id':parent_id,'entry_kind':kind,'name_b64':base64.b64encode(name).decode(),'expected_snapshot_id':expected}
            if entry is not None:fields['entry_id']=entry
            return call('catalog_apply',**fields)
        rejected=apply(1,b'wrong.txt',expected='wrong-generation');assert rejected['error']['code']=='snapshot_conflict'
        assert call()['sequence']==0
        answer=apply(1,b'literal*wild?.txt');assert answer['status']=='catalog_applied';new=answer['entry_id']
        assert query('*')['results'][0]['path']==str(root/'literal*wild?.txt')
        assert apply(3,b'gap.txt')['error']['code']=='sequence_gap'
        assert apply(2,b'initial.txt')['error']['code']=='namespace_collision'
        assert apply(2,b'folder',kind=2,entry=original)['error']['code']=='type_transition_requires_new_identity'
        assert apply(2,b'raw-\xff.txt')['status']=='catalog_applied'
        raw=query('raw')['results'][0];assert raw['path'] is None and base64.b64decode(raw['path_bytes_base64'])==os.fsencode(root)+b'/raw-\xff.txt'
        assert call('catalog_compact',expected_snapshot_id=identity)['status']=='catalog_compacting'
        for seq in range(3,53):assert apply(seq,f'churn-{seq}.txt'.encode())['status']=='catalog_applied'
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies=list(pool.map(lambda _:query('churn-'),range(20)))
        assert all(r['complete'] and len(r['results'])==50 for r in replies)
        deadline=time.monotonic()+5
        while True:
            state=call()
            if not state['building']:break
            assert time.monotonic()<deadline;time.sleep(.01)
        assert state['generation']>=1 and state['sequence']==52
        assert apply(53,b'',kind=0,entry=new)['status']=='catalog_applied'
        assert apply(54,b'resurrected.txt',entry=new)['error']['code']=='retired_identity'
        assert not query('*')['results']
        shutil.rmtree(root)
        assert lookup(root/'initial.txt')['entry_id']==original
        assert query('initial')['results'][0]['path']==str(root/'initial.txt')
        print(json.dumps({'result':'pass','accepted_events':53,'concurrent_queries':20,'generation':state['generation'],'checks':['snapshot identity guard','cached lookup confinement','literal names','raw bytes','sequence gap','namespace collision','type transition','retired identity','background compaction','four concurrent clients','cached queries/lookup after root removal'],'durable_updates':False},indent=2))
    finally:
        try:call('stop')
        except OSError:pass
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait()
        assert server.returncode==0,server.stderr.read().decode(errors='replace')[-1000:]
