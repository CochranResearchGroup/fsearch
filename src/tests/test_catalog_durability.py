"""Actual supervisor/worker restart preserves acknowledged cached mutations."""
import base64
import ctypes
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0
runtime = Path(sys.argv[1]); os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='fsearch-durable-') as temporary:
    work = Path(temporary); root = work/'owned'; root.mkdir(); (root/'initial.txt').touch()
    database=work/'snapshot'; endpoint=work/'q.sock'
    subprocess.run([sys.executable,str(runtime/'fsearch-refresh'),'refresh','--root',str(root),'--database',str(database)],check=True,capture_output=True,timeout=10)
    def call(op='catalog_status',**fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(3); channel.connect(str(endpoint))
            channel.sendall((json.dumps({'schema_version':1,'request_id':'durable-test','op':op,**fields})+'\n').encode())
            data=b''
            while b'\n' not in data:
                chunk=channel.recv(65536);assert chunk;data+=chunk
            return json.loads(data)
    def start():
        server=subprocess.Popen([sys.executable,str(runtime/'fsearch-service'),'serve','--catalog-journal','--socket',str(endpoint),'--database',str(database)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        deadline=time.monotonic()+5
        while True:
            assert server.poll() is None, server.stderr.read().decode()
            try:
                result=call()
                if result['status']=='catalog_status':return server,result
            except OSError:pass
            assert time.monotonic()<deadline;time.sleep(.01)
    server=None
    try:
        server,state=start(); identity=state['snapshot_id']
        located=call('catalog_lookup',path_b64=base64.b64encode(os.fsencode(root)).decode())
        for sequence,name in enumerate((b'committed.txt',b'raw-\xff.txt'),1):
            result=call('catalog_apply',expected_snapshot_id=identity,sequence=sequence,parent_id=located['entry_id'],entry_kind=1,name_b64=base64.b64encode(name).decode())
            assert result['status']=='catalog_applied' and result['durable'] is True,result
        previous_worker=json.loads(Path(str(endpoint)+'.state').read_text())['worker']['pid']
        server.kill();server.wait(timeout=5);server=None
        # Cached recovery must not touch the indexed root or require it to exist.
        (root/'initial.txt').unlink();root.rmdir()
        deadline=time.monotonic()+3
        while Path('/proc',str(previous_worker)).exists() and time.monotonic()<deadline:time.sleep(.01)
        try: os.waitpid(previous_worker, 0)
        except ChildProcessError: pass
        assert not Path('/proc', str(previous_worker)).exists()
        # reconcile() owns exact identity/reap; no blind worker restart.
        subprocess.run([sys.executable, str(runtime/'fsearch-service'), 'recover', '--socket', str(endpoint)], check=True, capture_output=True, timeout=3)
        server,state=start();assert state['sequence']==2,state
        result=call('query',query='committed',limit=100)
        assert result['results'][0]['path']==str(root/'committed.txt'),result
        assert result['incremental_coverage']['state']=='deferred',result
        assert result['incremental_coverage']['reason']=='catalog_recovered_source_gap',result
        raw=call('query',query='raw-',limit=100)['results'][0]
        assert base64.b64decode(raw['path_bytes_base64'])==os.fsencode(root)+b'/raw-\xff.txt'
        call('stop'); server.wait(timeout=5); server=None
        journal=Path(str(endpoint)+'.catalog-journal')
        data=journal.read_bytes()
        with journal.open('ab') as stream: stream.write(b'\x00\x00')
        server,state=start();assert state['sequence']==2,state
        retained=call('query',query='committed',limit=100)
        assert retained['results'][0]['path']==str(root/'committed.txt'),retained
        assert retained['incremental_coverage']['reason']=='catalog_journal_tail_uncommitted',retained
        blocked=call('catalog_apply',expected_snapshot_id=identity,sequence=3,parent_id=located['entry_id'],entry_kind=1,name_b64=base64.b64encode(b'blocked.txt').decode())
        assert blocked['error']['code']=='journal_tail_uncommitted',blocked
        call('stop');server.wait(timeout=5);server=None
        journal.write_bytes(data[:-1])
        server,state=start(); assert state['sequence']==0 and state['durable'] is False,state
        baseline=call('query',query='initial',limit=100)
        assert baseline['results'][0]['path']==str(root/'initial.txt'),baseline
        assert baseline['incremental_coverage']['state']=='deferred' and baseline['incremental_coverage']['reason']=='catalog_journal_invalid',baseline
        rejected=call('catalog_apply',expected_snapshot_id=identity,sequence=1,parent_id=located['entry_id'],entry_kind=1,name_b64=base64.b64encode(b'forbidden.txt').decode())
        assert rejected['status']=='error' and rejected['error']['code']=='catalog_journal_invalid',rejected
        assert not call('query',query='committed',limit=100)['results']
        print(json.dumps({'result':'durable_catalog_replay_pass','sequence':2,'indexed_root_absent':True,'watching_claimed':False,'uncommitted_tail':'acknowledged_view_retained_read_only','truncated_committed_replay':'baseline_served_deferred_and_mutation_refused'}))
    finally:
        if server:
            try:call('stop')
            except OSError:server.terminate()
            server.wait(timeout=5)
