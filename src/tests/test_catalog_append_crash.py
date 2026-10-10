"""Actual supervisor crash at a journal durability boundary, without source probes."""
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
cut = sys.argv[2] if len(sys.argv) > 2 else 'log_fsync'
assert cut in ('log_fsync', 'cursor_pre_rename', 'cursor_published')
with tempfile.TemporaryDirectory(prefix='fsearch-append-crash-') as temporary:
    work = Path(temporary)
    root = work / 'owned'; root.mkdir(); (root / 'initial.txt').touch()
    database = work / 'snapshot'; endpoint = work / 'q.sock'
    subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], check=True, capture_output=True, timeout=10)
    wrapper = work / 'crash.py'
    wrapper.write_text('''import os,runpy,sys
sys.path.insert(0,sys.argv[1])
import fsearch_catalog_journal as journal
original_append=journal.CatalogJournal.append
original_rename=os.rename
original_fsync=os.fsync
original_publish=journal.CatalogJournal.publish_commit
cut=sys.argv.pop(2)
armed_fd=None
def fsync(fd):
    result=original_fsync(fd)
    if cut=='log_fsync' and fd==armed_fd:os._exit(86)
    return result
def append(self,request,entry_id):
    global armed_fd
    if request['sequence']==2:armed_fd=self.fd
    return original_append(self,request,entry_id)
def publish(self,size,sequence,chain):
    result=original_publish(self,size,sequence,chain)
    if cut=='cursor_published' and sequence==2:os._exit(86)
    return result
journal.CatalogJournal.publish_commit=publish
def rename(source,target,**kwargs):
    if cut=='cursor_pre_rename' and armed_fd is not None and target.endswith('.commit'):os._exit(86)
    return original_rename(source,target,**kwargs)
os.rename=rename
os.fsync=fsync
journal.CatalogJournal.append=append
sys.argv=sys.argv[2:]
runpy.run_path(sys.argv[0],run_name='__main__')
''')

    def call(op='catalog_status', **fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(3); channel.connect(str(endpoint))
            channel.sendall((json.dumps({'schema_version': 1, 'request_id': 'append-crash', 'op': op, **fields}) + '\n').encode())
            data = b''
            while b'\n' not in data:
                block = channel.recv(65536)
                if not block: raise EOFError('supervisor died before acknowledgement')
                data += block
            return json.loads(data)

    def start(inject=False):
        command = [sys.executable, str(runtime / 'fsearch-service'), 'serve', '--catalog-journal', '--socket', str(endpoint), '--database', str(database)]
        if inject: command = [sys.executable, str(wrapper), str(runtime), cut, *command[1:]]
        server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
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
        try:
            result = call('catalog_apply', expected_snapshot_id=identity, sequence=2, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'unacknowledged.txt').decode())
        except EOFError: pass
        else: raise AssertionError(('mutation acknowledged before selected crash boundary', result))
        assert server.wait(timeout=5) == 86; server = None
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
        assert recovered['snapshot_id'] == identity and recovered['sequence'] == (1 if cut != 'cursor_published' else 2), recovered
        retained = call('query', query='acknowledged-', limit=100)
        assert base64.b64decode(retained['results'][0]['path_bytes_base64']) == os.fsencode(root) + b'/acknowledged-\xff.txt', retained
        assert retained['incremental_coverage']['state'] == 'deferred', retained
        if cut != 'cursor_published':
            assert retained['incremental_coverage']['reason'] == 'catalog_journal_tail_uncommitted', retained
        assert bool(call('query', query='unacknowledged', limit=100)['results']) == (cut == 'cursor_published')
        assert call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(root) + b'/acknowledged-\xff.txt').decode())['entry_id'] == first['entry_id']
        if cut != 'cursor_published':
            refused = call('catalog_apply', expected_snapshot_id=identity, sequence=2, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'forbidden.txt').decode())
            assert refused['status'] == 'error' and refused['error']['code'] == 'journal_tail_uncommitted', refused
        print(json.dumps({'result': 'actual_append_crash_pass', 'cut': cut, 'acknowledged_sequence': 1, 'uncommitted_tail_read_only': cut != 'cursor_published', 'recovered_sequence': recovered['sequence'], 'root_and_original_snapshot_absent': True, 'raw_bytes_and_entry_id_preserved': True, 'power_loss_qualified': False}))
    finally:
        if server:
            try: call('stop')
            except OSError: server.terminate()
            server.wait(timeout=5)
