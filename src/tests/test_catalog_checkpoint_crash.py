"""Actual supervisor crash during checkpoint manifest publication, without source probes."""
import base64
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0
runtime = Path(sys.argv[1]); os.umask(0o077)
cut = sys.argv[2] if len(sys.argv) > 2 else 'manifest_pre_rename'
assert cut in ('manifest_pre_rename', 'manifest_published', 'checkpoint_write')
with tempfile.TemporaryDirectory(prefix='fsearch-checkpoint-crash-') as temporary:
    work = Path(temporary)
    gate = work / 'writer-gate'
    fault = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    assert cut != 'checkpoint_write' or fault is not None
    root = work / 'owned'; root.mkdir(); (root / 'initial.txt').touch()
    database = work / 'snapshot'; endpoint = work / 'q.sock'
    subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], check=True, capture_output=True, timeout=10)
    wrapper = work / 'crash.py'
    wrapper.write_text('''import os,runpy,sys
sys.path.insert(0,sys.argv[1])
import fsearch_catalog_journal as journal
original_rename=os.rename
original_publish=journal.CatalogJournal.publish_json
cut=sys.argv.pop(2)
armed=False
def rename(source,target,**kwargs):
    if armed and cut=='manifest_pre_rename' and target.endswith('.catalog-generation'):os._exit(86)
    return original_rename(source,target,**kwargs)
def publish(self,name,value):
    global armed
    if name==self.manifest_name:
        generations=value.get('generations',[value])
        if generations[0]['sequence']==2:
            armed=True
            result=original_publish(self,name,value)
            if cut=='manifest_published':os._exit(86)
            return result
    return original_publish(self,name,value)
os.rename=rename
journal.CatalogJournal.publish_json=publish
sys.argv=sys.argv[2:]
runpy.run_path(sys.argv[0],run_name='__main__')
''')

    def call(op='catalog_status', **fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(3); channel.connect(str(endpoint))
            channel.sendall((json.dumps({'schema_version': 1, 'request_id': 'checkpoint-crash', 'op': op, **fields}) + '\n').encode())
            data = b''
            while b'\n' not in data:
                block = channel.recv(65536)
                if not block: raise EOFError('supervisor died before acknowledgement')
                data += block
            return json.loads(data)

    def start(inject=False):
        command = [sys.executable, str(runtime / 'fsearch-service'), 'serve', '--catalog-journal', '--socket', str(endpoint), '--database', str(database)]
        if inject: command = [sys.executable, str(wrapper), str(runtime), cut, *command[1:]]
        server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env={**os.environ, **({'LD_PRELOAD': str(fault), 'FSEARCH_CHECKPOINT_TEST_GATE': str(gate)} if cut == 'checkpoint_write' else {})})
        try:
            deadline = time.monotonic() + 5
            while True:
                assert server.poll() is None, server.stderr.read().decode()
                try:
                    result = call()
                    if result['status'] == 'catalog_status': return server, result
                except OSError: pass
                assert time.monotonic() < deadline
                time.sleep(.01)
        except BaseException:
            server.terminate(); server.wait(timeout=5); raise

    server = None
    try:
        server, state = start(True); identity = state['snapshot_id']
        first = call('catalog_apply', expected_snapshot_id=identity, sequence=1, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'acknowledged-\xff.txt').decode())
        assert first['durable'] and first['sequence'] == 1, first
        assert call('catalog_compact', expected_snapshot_id=identity)['status'] == 'catalog_compacting'
        deadline = time.monotonic() + 5
        while call().get('building'):
            assert time.monotonic() < deadline
            time.sleep(.01)
        previous_worker = json.loads(Path(str(endpoint) + '.state').read_text())['worker']['pid']
        second = call('catalog_apply', expected_snapshot_id=identity, sequence=2, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'second-acknowledged.txt').decode())
        assert second['durable'] and second['sequence'] == 2, second
        if cut == 'checkpoint_write': gate.touch()
        try:
            assert call('catalog_compact', expected_snapshot_id=identity)['status'] == 'catalog_compacting'
            deadline = time.monotonic() + 5
            while server.poll() is None:
                if cut == 'checkpoint_write':
                    pending = Path(str(endpoint) + '.catalog-checkpoint-b')
                    if pending.exists():
                        assert pending.stat().st_size == 0
                        assert call('query', query='second-acknowledged', limit=100)['results']
                        server.kill()
                        break
                try: call()
                except (OSError, EOFError): pass
                assert time.monotonic() < deadline, 'selected manifest crash boundary was not reached'
                time.sleep(.01)
        except EOFError: pass
        assert server.wait(timeout=5) == (-9 if cut == 'checkpoint_write' else 86); server = None
        gate.unlink(missing_ok=True)
        deadline = time.monotonic() + 3
        while Path('/proc', str(previous_worker)).exists():
            try:
                if os.waitpid(previous_worker, os.WNOHANG)[0]: break
            except ChildProcessError: pass
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert not Path('/proc', str(previous_worker)).exists()
        subprocess.run([sys.executable, str(runtime / 'fsearch-service'), 'recover', '--socket', str(endpoint)], check=True, capture_output=True, timeout=3)
        (root / 'initial.txt').unlink(); root.rmdir(); database.unlink()
        server, recovered = start()
        assert recovered['snapshot_id'] == identity and recovered['sequence'] == 2, recovered
        retained = call('query', query='acknowledged-', limit=100)
        assert base64.b64decode(retained['results'][0]['path_bytes_base64']) == os.fsencode(root) + b'/acknowledged-\xff.txt', retained
        assert retained['incremental_coverage']['state'] == 'deferred', retained
        assert call('query', query='second-acknowledged', limit=100)['results']
        assert call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(root) + b'/acknowledged-\xff.txt').decode())['entry_id'] == first['entry_id']
        assert call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(root) + b'/second-acknowledged.txt').decode())['entry_id'] == second['entry_id']
        print(json.dumps({'result': 'actual_checkpoint_manifest_crash_pass', 'cut': cut, 'acknowledged_sequence': 2, 'root_and_original_snapshot_absent': True, 'raw_bytes_and_entry_ids_preserved': True, 'power_loss_qualified': False}))
    finally:
        if server:
            try: call('stop')
            except OSError: server.terminate()
            server.wait(timeout=5)
