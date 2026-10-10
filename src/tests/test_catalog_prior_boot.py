"""Actual prior-boot state recovery through the durable catalog public seam, without source probes."""
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
phase = sys.argv[2] if len(sys.argv) > 2 else 'ready'
assert phase in ('ready', 'starting', 'quarantined', 'current_boot', 'mixed_boot')
with tempfile.TemporaryDirectory(prefix='fsearch-prior-boot-') as temporary:
    work = Path(temporary)
    root = work / 'owned'; root.mkdir(); (root / 'initial.txt').touch()
    database = work / 'snapshot'; endpoint = work / 'q.sock'
    subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], check=True, capture_output=True, timeout=10)
    def call(op='catalog_status', **fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(3); channel.connect(str(endpoint))
            channel.sendall((json.dumps({'schema_version': 1, 'request_id': 'prior-boot', 'op': op, **fields}) + '\n').encode())
            data = b''
            while b'\n' not in data:
                block = channel.recv(65536)
                if not block: raise EOFError('supervisor died before acknowledgement')
                data += block
            return json.loads(data)

    def start():
        command = [sys.executable, str(runtime / 'fsearch-service'), 'serve', '--catalog-journal', '--socket', str(endpoint), '--database', str(database)]
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
        server, state = start(); identity = state['snapshot_id']
        first = call('catalog_apply', expected_snapshot_id=identity, sequence=1, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'acknowledged-\xff.txt').decode())
        assert first['durable'] and first['sequence'] == 1, first
        assert call('catalog_compact', expected_snapshot_id=identity)['status'] == 'catalog_compacting'
        deadline = time.monotonic() + 5
        while call().get('building'):
            assert time.monotonic() < deadline
            time.sleep(.01)
        second = call('catalog_apply', expected_snapshot_id=identity, sequence=2, parent_id=0, entry_kind=1, name_b64=base64.b64encode(b'second-acknowledged.txt').decode())
        assert second['durable'] and second['sequence'] == 2, second
        state_path = Path(str(endpoint) + '.state')
        state = json.loads(state_path.read_text())
        previous_worker = state['worker']['pid']
        call('stop')
        assert server.wait(timeout=5) == 0; server = None
        assert not Path('/proc', str(previous_worker)).exists()
        # Owned state fixture only: valid same-prior-boot identities referencing this
        # still-live test PID ensure recovery relies on boot proof, not PID absence.
        import uuid
        prior_boot = str(uuid.uuid4())
        raw_stat = Path('/proc/self/stat').read_text()
        record = {'pid': os.getpid(), 'start': raw_stat.rsplit(')', 1)[1].split()[19], 'boot': prior_boot}
        state.update(phase=phase if phase in ('ready', 'starting', 'quarantined') else 'quarantined', supervisor=record, worker=record, candidate_worker=record, retiring_worker=record)
        state_path.write_text(json.dumps(state)); state_path.chmod(0o600)
        (root / 'initial.txt').unlink(); root.rmdir(); database.unlink()
        if phase in ('current_boot', 'mixed_boot'):
            current_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            if phase == 'current_boot':
                for key in ('supervisor', 'worker', 'candidate_worker', 'retiring_worker'):
                    state[key] = dict(record, boot=current_boot)
            else:
                state['candidate_worker'] = dict(record, boot=current_boot)
            state_path.write_text(json.dumps(state))
            saved = state_path.read_bytes()
            for command in ('serve', 'recover', 'serve'):
                args = [sys.executable, str(runtime / 'fsearch-service'), command, '--socket', str(endpoint)]
                if command == 'serve': args += ['--catalog-journal', '--database', str(database)]
                result = subprocess.run(args, capture_output=True, timeout=3)
                assert result.returncode == 1, result
                refusal = json.loads(result.stdout)
                assert refusal['status'] == 'error' and refusal['error']['code'] == 'quarantined', refusal
                assert state_path.read_bytes() == saved
                assert Path('/proc/self/task', str(os.getpid()), 'children').read_text().strip() == ''
            # Rebaseline only the owned synthetic fixture to a coherent prior boot.
            state.update(supervisor=record, worker=record, candidate_worker=record, retiring_worker=record)
            state_path.write_text(json.dumps(state))
        server, recovered = start()
        assert recovered['snapshot_id'] == identity and recovered['sequence'] == 2, recovered
        retained = call('query', query='acknowledged-', limit=100)
        assert base64.b64decode(retained['results'][0]['path_bytes_base64']) == os.fsencode(root) + b'/acknowledged-\xff.txt', retained
        assert retained['incremental_coverage']['state'] == 'deferred' and retained['incremental_coverage']['reason'] == 'catalog_recovered_source_gap', retained
        assert call('query', query='second-acknowledged', limit=100)['results']
        assert call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(root) + b'/acknowledged-\xff.txt').decode())['entry_id'] == first['entry_id']
        assert call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(root) + b'/second-acknowledged.txt').decode())['entry_id'] == second['entry_id']
        print(json.dumps({'result': 'actual_prior_boot_catalog_recovery_pass', 'phase': phase, 'real_reboot_qualified': False, 'acknowledged_sequence': 2, 'root_and_original_snapshot_absent': True, 'raw_bytes_and_entry_ids_preserved': True, 'power_loss_qualified': False}))
    finally:
        if server:
            try: call('stop')
            except OSError: server.terminate()
            server.wait(timeout=5)
