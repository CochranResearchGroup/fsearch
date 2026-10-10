"""Recover a previously accepted private view when the selected checkpoint is corrupt."""
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
runtime = Path(sys.argv[1])
os.umask(0o077)
fault = sys.argv[2] if len(sys.argv) > 2 else 'checkpoint'
assert fault in ('checkpoint', 'both', 'binding', 'sequence', 'metadata', 'manifest')
with tempfile.TemporaryDirectory(prefix='fsearch-corrupt-pair-') as temporary:
    work = Path(temporary)
    root = work / 'owned'; root.mkdir(); (root / 'initial.txt').touch()
    database = work / 'snapshot'; endpoint = work / 'q.sock'
    subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], check=True, capture_output=True, timeout=10)

    def call(op='catalog_status', **fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(3); channel.connect(str(endpoint))
            channel.sendall((json.dumps({'schema_version': 1, 'request_id': 'corrupt-pair', 'op': op, **fields}) + '\n').encode())
            data = b''
            while b'\n' not in data:
                block = channel.recv(65536); assert block; data += block
            return json.loads(data)

    def start():
        server = subprocess.Popen([sys.executable, str(runtime / 'fsearch-service'), 'serve', '--catalog-journal', '--socket', str(endpoint), '--database', str(database)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            result = None
            while True:
                assert server.poll() is None, server.stderr.read().decode()
                try:
                    result = call()
                    if result['status'] == 'catalog_status': return server, result
                except OSError: pass
                assert time.monotonic() < deadline, ('no accepted fallback became query-ready', result)
                time.sleep(.01)
        except BaseException:
            server.terminate(); server.wait(timeout=5); raise

    def checkpoint(identity):
        assert call('catalog_compact', expected_snapshot_id=identity)['status'] == 'catalog_compacting'
        deadline = time.monotonic() + 5
        while True:
            result = call()
            if not result.get('building'): return result
            assert time.monotonic() < deadline, result
            time.sleep(.01)

    server = None
    try:
        server, state = start(); identity = state['snapshot_id']
        committed = call('catalog_apply', expected_snapshot_id=identity, sequence=1, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'previous-accepted.txt').decode())
        assert committed['durable'], committed
        assert checkpoint(identity)['sequence'] == 1
        latest = call('catalog_apply', expected_snapshot_id=identity, sequence=2, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'latest-view.txt').decode())
        assert latest['durable'], latest
        assert checkpoint(identity)['sequence'] == 2
        call('stop'); server.wait(timeout=5); server = None
        # Two accepted private generations exist. Damage only the newer image;
        # keep the older complete pair and remove both original sources.
        selected = Path(str(endpoint) + '.catalog-checkpoint-b')
        if fault == 'manifest':
            manifest = Path(str(endpoint) + '.catalog-generation')
            generation = json.loads(manifest.read_text()); generation['generations'][1]['slot'] = generation['generations'][0]['slot']
            manifest.write_text(json.dumps(generation))
        elif fault == 'sequence':
            manifest = Path(str(endpoint) + '.catalog-generation')
            generation = json.loads(manifest.read_text()); generation['generations'][0]['sequence'] += 1
            manifest.write_text(json.dumps(generation))
        else:
            if fault == 'metadata': selected = Path(str(selected) + '.metadata')
            data = selected.read_bytes(); selected.write_bytes(data[:-1])
        (root / 'initial.txt').unlink(); root.rmdir()
        if fault == 'binding':
            different = work / 'different-owned'; different.mkdir(); (different / 'unaccepted-baseline.txt').touch()
            subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(different), '--database', str(database)], check=True, capture_output=True, timeout=10)
        else:
            database.unlink()
        if fault in ('both', 'binding', 'manifest'):
            expected_error = 'snapshot_conflict' if fault == 'binding' else 'catalog_checkpoint_unavailable'
            older = Path(str(endpoint) + '.catalog-checkpoint-a')
            if fault != 'manifest':
                old_data = older.read_bytes(); older.write_bytes(old_data[:-1])
            server = subprocess.Popen([sys.executable, str(runtime / 'fsearch-service'), 'serve', '--catalog-journal', '--socket', str(endpoint), '--database', str(database)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            deadline = time.monotonic() + 5
            while True:
                try:
                    unavailable = call()
                    if unavailable.get('error', {}).get('code') == expected_error: break
                except OSError: pass
                assert time.monotonic() < deadline, ('corrupt pairs did not enter bounded unavailable state', locals().get('unavailable'))
                time.sleep(.01)
            for _ in range(10):
                assert call()['error']['code'] == expected_error
                assert not Path(f'/proc/{server.pid}/task/{server.pid}/children').read_text().strip(), 'unavailable view keeps spawning workers'
                time.sleep(.12)
            print(json.dumps({'result': 'all_pairs_invalid_refuses_without_restart_storm', 'fault': fault, 'original_root_absent': True, 'unaccepted_baseline_refused': fault == 'binding'}))
            raise SystemExit(0)
        server, recovered = start()
        assert recovered['snapshot_id'] == identity and recovered['sequence'] == 1, recovered
        assert not recovered['durable'], recovered
        retained = call('query', query='previous-accepted', limit=100)
        assert retained['results'][0]['path'] == str(root / 'previous-accepted.txt'), retained
        assert retained['incremental_coverage']['state'] == 'deferred', retained
        assert retained['incremental_coverage']['reason'] == 'catalog_checkpoint_fallback', retained
        assert not call('query', query='latest-view', limit=100)['results']
        refused = call('catalog_apply', expected_snapshot_id=identity, sequence=2, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'forbidden.txt').decode())
        assert refused['status'] == 'error', refused
        print(json.dumps({'result': 'corrupt_selected_pair_fallback_pass', 'sequence': 1, 'selected_sequence': 2, 'original_snapshot_and_root_absent': True, 'mutation_refused': True}))
    finally:
        if server:
            try: call('stop')
            except OSError: server.terminate()
            server.wait(timeout=5)
