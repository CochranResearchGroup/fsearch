"""Actual supervisor crash at a journal durability boundary, without source probes."""
import base64
import ctypes
import json
import os
from pathlib import Path
import socket
import select
import subprocess
import sys
import tempfile
import time

assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0
runtime = Path(sys.argv[1]); os.umask(0o077)
cut = sys.argv[2] if len(sys.argv) > 2 else 'normal'
assert cut in ('normal', 'log_fsync', 'cursor_pre_rename', 'cursor_published', 'pause_cursor', 'native_error', 'native_deferred', 'bounds')
with tempfile.TemporaryDirectory(prefix='fsearch-group-crash-') as temporary:
    work = Path(temporary)
    root = work / 'owned'; root.mkdir(); (root / 'initial.txt').touch()
    database = work / 'snapshot'; endpoint = work / 'q.sock'
    subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], check=True, capture_output=True, timeout=10)
    wrapper = work / 'crash.py'
    wrapper.write_text('''import os,runpy,sys,time,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import fsearch_catalog_journal as journal
original_append=journal.CatalogJournal.append_batch
original_rename=os.rename
original_fsync=os.fsync
original_publish=journal.CatalogJournal.publish_commit
cut=sys.argv.pop(2)
armed_fd=None
original_loads=json.loads
def loads(*args,**kwargs):
    result=original_loads(*args,**kwargs)
    if cut=='native_deferred' and isinstance(result,dict) and result.get('status')=='catalog_applied' and result.get('sequence')==2:
        result['deferred_reason']='batch_fixture_gap'
    return result
json.loads=loads
def fsync(fd):
    result=original_fsync(fd)
    if cut=='log_fsync' and fd==armed_fd:os._exit(86)
    return result
def append(self,records):
    global armed_fd
    if records[0][0]['sequence']==2:armed_fd=self.fd
    return original_append(self,records)
def publish(self,size,sequence,chain):
    if cut=='pause_cursor' and sequence==9:
        Path(os.environ['FSEARCH_BATCH_PAUSE']).touch()
        deadline=time.monotonic()+1.5
        while not Path(os.environ['FSEARCH_BATCH_RELEASE']).exists():
            if time.monotonic()>deadline:os._exit(87)
            time.sleep(.01)
    result=original_publish(self,size,sequence,chain)
    if cut=='cursor_published' and sequence==9:os._exit(86)
    return result
journal.CatalogJournal.publish_commit=publish
def rename(source,target,**kwargs):
    if cut=='cursor_pre_rename' and armed_fd is not None and target.endswith('.commit'):os._exit(86)
    return original_rename(source,target,**kwargs)
os.rename=rename
os.fsync=fsync
journal.CatalogJournal.append_batch=append
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
        server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                  env={**os.environ, 'FSEARCH_BATCH_PAUSE': str(work / 'paused'), 'FSEARCH_BATCH_RELEASE': str(work / 'release')})
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
        server, state = start(cut in ('log_fsync', 'cursor_pre_rename', 'cursor_published', 'pause_cursor', 'native_deferred')); identity = state['snapshot_id']
        first = call('catalog_apply', expected_snapshot_id=identity, sequence=1, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'acknowledged-\xff.txt').decode())
        assert first['durable'] and first['sequence'] == 1, first
        assert call('catalog_compact', expected_snapshot_id=identity)['status'] == 'catalog_compacting'
        deadline = time.monotonic() + 5
        while call().get('building'):
            assert time.monotonic() < deadline
            time.sleep(.01)
        previous_worker = json.loads(Path(str(endpoint) + '.state').read_text())['worker']['pid']
        mutations = [{'sequence': sequence, 'parent_id': 0, 'entry_kind': 1,
                      'name_b64': base64.b64encode(f'batch-{sequence}.txt'.encode() if sequence != 9 else b'batch-\xff.txt').decode()}
                     for sequence in range(2, 10)]
        if cut == 'bounds':
            for invalid in ([], mutations + [dict(mutations[-1], sequence=10)],
                            mutations[:-1] + [dict(mutations[-1], sequence=10)],
                            [dict(mutations[0], sequence=True)]):
                rejected=call('catalog_apply_batch', expected_snapshot_id=identity, mutations=invalid)
                assert rejected['status']=='error' and rejected['error']['code']=='invalid_request', rejected
                assert call()['sequence']==1
            rejected=call('catalog_apply_batch', expected_snapshot_id='different', mutations=mutations)
            assert rejected['error']['code']=='snapshot_conflict' and call()['sequence']==1, rejected
            for begin in range(2,1026,8):
                group=[{'sequence': sequence, 'parent_id': 0, 'entry_kind': 1,
                        'name_b64': base64.b64encode(f'limit-{sequence}.txt'.encode()).decode()} for sequence in range(begin,begin+8)]
                accepted=call('catalog_apply_batch', expected_snapshot_id=identity, mutations=group)
                assert accepted['status']=='catalog_batch_applied' and accepted['durable'] and accepted['sequence']==begin+7, accepted
            assert accepted['journal_remaining']==0, accepted
            group=[dict(group[0], sequence=1026,name_b64=base64.b64encode(b'limit-after-rollover.txt').decode())]
            rejected=call('catalog_apply_batch', expected_snapshot_id=identity, mutations=group)
            assert rejected['error']['code']=='journal_checkpoint_required' and call()['sequence']==1025, rejected
            assert call('catalog_compact', expected_snapshot_id=identity)['status']=='catalog_compacting'
            deadline=time.monotonic()+5
            while call().get('building'):
                assert time.monotonic()<deadline;time.sleep(.01)
            accepted=call('catalog_apply_batch', expected_snapshot_id=identity, mutations=group)
            assert accepted['durable'] and accepted['sequence']==1026, accepted
            print(json.dumps({'result':'batch_exact_production_record_limit', 'records':1024, 'oversized_sequence_identity_rejected':True}))
            raise SystemExit(0)
        if cut in ('native_error','native_deferred'):
            invalid=mutations if cut=='native_deferred' else [mutations[0],dict(mutations[1],parent_id=2**32-1)]
            rejected=call('catalog_apply_batch', expected_snapshot_id=identity, mutations=invalid)
            assert rejected['status']=='error' and rejected['error']['code']=='catalog_batch_apply_failed', rejected
            deadline=time.monotonic()+5
            while True:
                state=call()
                if state['status']=='catalog_status':break
                assert time.monotonic()<deadline;time.sleep(.01)
            assert state['sequence']==1 and not call('query',query='batch-',limit=100)['results'], state
            call('stop');server.wait(timeout=5);server=None
        elif cut in ('normal','pause_cursor'):
            if cut=='pause_cursor':
                channels=[]
                try:
                    channel=socket.socket(socket.AF_UNIX);channels.append(channel);channel.settimeout(3);channel.connect(str(endpoint))
                    channel.sendall((json.dumps({'schema_version':1,'request_id':'pause-batch','op':'catalog_apply_batch','expected_snapshot_id':identity,'mutations':mutations})+'\n').encode())
                    deadline=time.monotonic()+3
                    while not (work/'paused').exists():
                        assert server.poll() is None and time.monotonic()<deadline;time.sleep(.01)
                    query=socket.socket(socket.AF_UNIX);channels.append(query);query.settimeout(3);query.connect(str(endpoint))
                    query.sendall((json.dumps({'schema_version':1,'request_id':'pause-query','query':'batch-','limit':100})+'\n').encode())
                    assert not select.select(channels,[],[],.1)[0], 'response before committed cursor publication'
                    (work/'release').touch()
                    def receive(stream):
                        data=b''
                        while b'\n' not in data:
                            block=stream.recv(65536);assert block;data+=block
                        return json.loads(data)
                    result=receive(channel); visible=receive(query)
                    assert visible['complete'] and visible['durable'] and len(visible['results'])==8, visible
                finally:
                    (work/'release').touch()
                    for channel in channels:channel.close()
            else:result = call('catalog_apply_batch', expected_snapshot_id=identity, mutations=mutations)
            assert result['status'] == 'catalog_batch_applied' and result['durable'] and result['sequence'] == 9, result
            assert len(result['entry_ids']) == 8 and len(set(result['entry_ids'])) == 8, result
            call('stop'); server.wait(timeout=5); server = None
        else:
            try:
                result = call('catalog_apply_batch', expected_snapshot_id=identity, mutations=mutations)
            except EOFError: pass
            else: raise AssertionError(('batch acknowledged before selected crash boundary', result))
            assert server.wait(timeout=5) == 86; server = None
        deadline = time.monotonic() + 3
        while Path('/proc', str(previous_worker)).exists():
            try:
                if os.waitpid(previous_worker, os.WNOHANG)[0]: break
            except ChildProcessError: pass
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert not Path('/proc', str(previous_worker)).exists()
        if cut not in ('normal','pause_cursor','native_error','native_deferred'):
            subprocess.run([sys.executable, str(runtime / 'fsearch-service'), 'recover', '--socket', str(endpoint)], check=True, capture_output=True, timeout=3)
        (root / 'initial.txt').unlink(); root.rmdir(); database.unlink()
        server, recovered = start()
        published=cut in ('normal','pause_cursor','cursor_published')
        assert recovered['snapshot_id'] == identity and recovered['sequence'] == (9 if published else 1), recovered
        retained = call('query', query='acknowledged-', limit=100)
        assert base64.b64decode(retained['results'][0]['path_bytes_base64']) == os.fsencode(root) + b'/acknowledged-\xff.txt', retained
        assert retained['incremental_coverage']['state'] == 'deferred', retained
        if cut in ('log_fsync','cursor_pre_rename'):
            assert retained['incremental_coverage']['reason'] == 'catalog_journal_tail_uncommitted', retained
        batch_paths = call('query', query='batch-', limit=100)['results']
        assert len(batch_paths) == (8 if published else 0), batch_paths
        if cut in ('normal','pause_cursor'):
            recovered_ids=[call('catalog_lookup',path_b64=base64.b64encode(os.fsencode(root)+b'/'+base64.b64decode(mutation['name_b64'])).decode())['entry_id'] for mutation in mutations]
            assert recovered_ids==result['entry_ids'], (recovered_ids,result)
        assert call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(root) + b'/acknowledged-\xff.txt').decode())['entry_id'] == first['entry_id']
        if cut in ('log_fsync','cursor_pre_rename'):
            refused = call('catalog_apply', expected_snapshot_id=identity, sequence=2, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'forbidden.txt').decode())
            assert refused['status'] == 'error' and refused['error']['code'] == 'journal_tail_uncommitted', refused
        print(json.dumps({'result': 'actual_batch_crash_pass', 'cut': cut, 'acknowledged_sequence': 1, 'uncommitted_tail_read_only': cut in ('log_fsync','cursor_pre_rename'), 'recovered_sequence': recovered['sequence'], 'root_and_original_snapshot_absent': True, 'raw_bytes_and_entry_id_preserved': True, 'power_loss_qualified': False}))
    finally:
        if server:
            try: call('stop')
            except OSError: server.terminate()
            server.wait(timeout=5)
