"""Cross two production journal limits, then recover immutable entry identities."""
import base64,ctypes,json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
runtime=Path(sys.argv[1]);os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='fsearch-capacity-') as temporary:
    work=Path(temporary);root=work/'owned';root.mkdir();(root/'initial').touch();database=work/'snapshot';endpoint=work/'q.sock'
    subprocess.run([sys.executable,str(runtime/'fsearch-refresh'),'refresh','--root',str(root),'--database',str(database)],check=True,capture_output=True,timeout=10)
    def call(op='catalog_status',**fields):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(3);connection.connect(str(endpoint));connection.sendall((json.dumps({'schema_version':1,'request_id':'capacity','op':op,**fields})+'\n').encode())
            data=b''
            while b'\n' not in data:
                block=connection.recv(65536);assert block;data+=block
            return json.loads(data)
    def start():
        process=subprocess.Popen([sys.executable,str(runtime/'fsearch-service'),'serve','--catalog-journal','--socket',str(endpoint),'--database',str(database)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+5
            while True:
                assert process.poll() is None,process.stderr.read().decode()
                try:
                    result=call()
                    if result['status']=='catalog_status':return process,result
                except OSError:pass
                assert time.monotonic()<deadline;time.sleep(.01)
        except BaseException:process.terminate();process.wait(timeout=5);raise
    process=None
    try:
        process,state=start();identity=state['snapshot_id'];retired=None
        started=time.monotonic();batch_started=started;batch_max_seconds=0.0
        for sequence in range(1,2051):
            mutation_started=time.monotonic()
            result=call('catalog_apply',expected_snapshot_id=identity,sequence=sequence,parent_id=0,entry_kind=1,name_b64=base64.b64encode(f'capacity-{sequence:04d}'.encode()).decode())
            assert result['status']=='catalog_applied' and result['durable'] and result['sequence']==sequence,result
            retired=result['entry_id']
            batch_max_seconds=max(batch_max_seconds,time.monotonic()-mutation_started)
            if sequence % 64 == 0:
                now=time.monotonic()
                print(json.dumps({'accepted_sequence':sequence,'elapsed_seconds':now-started,'batch_seconds':now-batch_started,'batch_max_mutation_seconds':batch_max_seconds}),flush=True)
                batch_started=now;batch_max_seconds=0.0
            if sequence in (1024,2048):assert call('catalog_compact',expected_snapshot_id=identity)['status']=='catalog_compacting'
        assert call('catalog_apply',expected_snapshot_id=identity,sequence=2051,entry_id=retired,parent_id=0,entry_kind=0,name_b64='')['durable']
        fresh=call('catalog_apply',expected_snapshot_id=identity,sequence=2052,parent_id=0,entry_kind=1,name_b64=base64.b64encode(b'fresh-after-retired').decode())
        assert fresh['durable'] and fresh['entry_id']>retired,fresh
        deadline=time.monotonic()+5
        while call()['building']:
            assert time.monotonic()<deadline;time.sleep(.01)
        before=call();generation=json.loads(Path(str(endpoint)+'.catalog-generation').read_text())
        assert before['sequence']==2052 and generation['sequence']>=2048,(before,generation)
        worker=json.loads(Path(str(endpoint)+'.state').read_text())['worker']['pid']
        process.kill();process.wait(timeout=5);process=None
        deadline=time.monotonic()+3
        while Path('/proc',str(worker)).exists():
            try:
                if os.waitpid(worker,os.WNOHANG)[0]:break
            except ChildProcessError:pass
            assert time.monotonic()<deadline;time.sleep(.01)
        subprocess.run([sys.executable,str(runtime/'fsearch-service'),'recover','--socket',str(endpoint)],check=True,capture_output=True,timeout=3)
        (root/'initial').unlink();root.rmdir();database.unlink()
        process,recovered=start();assert recovered['sequence']==2052 and recovered['generation']==before['generation'],(before,recovered)
        for name in (b'capacity-0001',b'capacity-2048',b'fresh-after-retired'):
            assert call('catalog_lookup',path_b64=base64.b64encode(os.fsencode(root)+b'/'+name).decode())['status']=='catalog_located'
        assert call('catalog_lookup',path_b64=base64.b64encode(os.fsencode(root)+b'/capacity-2050').decode())['status']=='catalog_missing'
        restored=call('catalog_lookup',path_b64=base64.b64encode(os.fsencode(root)+b'/fresh-after-retired').decode())
        assert restored['entry_id']==fresh['entry_id'],(restored,fresh)
        print(json.dumps({'result':'two_production_journal_rollovers_pass','sequence':2052,'checkpoint_sequence':generation['sequence'],'generation':recovered['generation'],'retired_id_reuse':False,'original_snapshot_and_root_absent':True}))
    finally:
        if process:
            try:call('stop')
            except OSError:process.terminate()
            process.wait(timeout=5)
