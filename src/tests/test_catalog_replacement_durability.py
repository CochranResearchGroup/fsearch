"""Native replacement pairs remain recoverable across accepted-state publication."""
import base64,ctypes,json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
runtime=Path(sys.argv[1]);os.umask(0o077)
for fault in (None,'before','after'):
    with tempfile.TemporaryDirectory(prefix='fsearch-durable-replacement-') as temporary:
        work=Path(temporary);root=work/'owned';root.mkdir();(root/'initial.txt').touch();database=work/'snapshot';endpoint=work/'q.sock'
        def refresh():subprocess.run([sys.executable,str(runtime/'fsearch-refresh'),'refresh','--root',str(root),'--database',str(database)],check=True,capture_output=True,timeout=10)
        def call(op='catalog_status',**fields):
            with socket.socket(socket.AF_UNIX) as channel:
                channel.settimeout(5);channel.connect(str(endpoint));channel.sendall((json.dumps({'schema_version':1,'request_id':'replacement-test','op':op,'timeout_ms':5000,**fields})+'\n').encode())
                data=b''
                while b'\n' not in data:
                    block=channel.recv(65536)
                    if not block:raise EOFError('owned service ended before acknowledgement')
                    data+=block
                return json.loads(data)
        def start(injected=None):
            arguments=[sys.executable,str(runtime/'fsearch-service'),'serve','--catalog-journal','--socket',str(endpoint),'--database',str(database)]
            if injected:
                wrapper=work/'fault.py';wrapper.write_text('import os,runpy,sys\n'+
                    'def trace(frame,event,arg):\n'+
                    ' if event=="call" and frame.f_code.co_name=="save" and frame.f_locals.get("value",{}).get("reason")=="retiring_previous":\n'+
                    ('  os._exit(86)\n' if injected=='before' else '  def done(frame,event,arg):\n   if event=="return":os._exit(86)\n   return done\n  return done\n')+
                    ' return trace\n'+f'sys.path.insert(0,{str(runtime)!r});sys.settrace(trace);sys.argv={arguments[1:]!r};runpy.run_path(sys.argv[0],run_name="__main__")\n')
                arguments=[sys.executable,str(wrapper)]
            server=subprocess.Popen(arguments,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+5
                while True:
                    assert server.poll() is None,server.stderr.read().decode()
                    try:
                        result=call()
                        if result['status']=='catalog_status':return server,result
                    except OSError:pass
                    assert time.monotonic()<deadline;time.sleep(.01)
            except BaseException:server.terminate();server.wait(timeout=5);raise
        def reap_previous():
            state=json.loads(Path(str(endpoint)+'.state').read_text())
            for key in ('worker','candidate_worker','retiring_worker'):
                record=state.get(key)
                if not record:continue
                deadline=time.monotonic()+3
                while Path('/proc',str(record['pid'])).exists():
                    try:
                        if os.waitpid(record['pid'],os.WNOHANG)[0]:break
                    except ChildProcessError:pass
                    assert time.monotonic()<deadline;time.sleep(.01)
                assert not Path('/proc',str(record['pid'])).exists()
            subprocess.run([sys.executable,str(runtime/'fsearch-service'),'recover','--socket',str(endpoint)],check=True,capture_output=True,timeout=3)
            return state
        server=None
        try:
            refresh();server,state=start(fault);old_identity=state['snapshot_id']
            assert call('catalog_apply',expected_snapshot_id=old_identity,sequence=1,parent_id=0,entry_kind=1,name_b64=base64.b64encode(b'only-old.txt').decode())['durable']
            (root/'initial.txt').unlink();(root/'new-baseline.txt').touch();refresh()
            try:
                result=call('replace',candidate_database_b64=base64.b64encode(os.fsencode(database)).decode())
                assert fault is None and result['status']=='replaced' and result['durable'],result
                new_identity=result['snapshot_id'];assert new_identity!=old_identity
                assert not call('query',query='only-old',limit=100)['results']
                assert call('query',query='new-baseline',limit=100)['results']
                assert call('catalog_apply',expected_snapshot_id=new_identity,sequence=1,parent_id=0,entry_kind=1,name_b64=base64.b64encode(b'post-replace.txt').decode())['durable']
                stale=call('catalog_apply',expected_snapshot_id=old_identity,sequence=2,parent_id=0,entry_kind=1,name_b64=base64.b64encode(b'stale.txt').decode())
                assert stale['error']['code']=='snapshot_conflict',stale
                server.kill();server.wait(timeout=5)
            except EOFError:
                assert fault is not None;assert server.wait(timeout=5)==86
            server=None;state=reap_previous()
            (root/'new-baseline.txt').unlink();root.rmdir();database.unlink()
            server,recovered=start()
            old_selected=fault=='before'
            assert recovered['snapshot_id']==state['snapshot_id'],(recovered,state)
            assert recovered['sequence']==(1 if fault is None or old_selected else 0),recovered
            assert bool(call('query',query='only-old',limit=100)['results'])==old_selected
            assert bool(call('query',query='new-baseline',limit=100)['results'])==(not old_selected)
            if fault is None:assert call('query',query='post-replace',limit=100)['results']
            assert call('query',query='initial',limit=100)['incremental_coverage']['state']=='deferred'
            print(json.dumps({'result':'durable_replacement_pass','fault':fault,'selected':'old' if old_selected else 'new','source_snapshot_absent':True,'indexed_root_absent':True}))
        finally:
            if server:
                try:call('stop')
                except OSError:server.terminate()
                server.wait(timeout=5)
