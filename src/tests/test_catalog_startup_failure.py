"""Durable startup EOF must not spawn a fresh worker on every query, without source probes."""
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
mode = sys.argv[2] if len(sys.argv) > 2 else 'eof'
assert mode in ('eof', 'protocol', 'timeout', 'replay')
expected_error = {'eof': 'worker_failed', 'protocol': 'worker_protocol_failed', 'timeout': 'startup_deadline', 'replay': 'worker_failed'}[mode]
with tempfile.TemporaryDirectory(prefix='fsearch-startup-failure-') as temporary:
    work = Path(temporary)
    root = work / 'owned'; root.mkdir(); (root / 'initial.txt').touch()
    database = work / 'snapshot'; endpoint = work / 'q.sock'
    subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], check=True, capture_output=True, timeout=10)
    def call(op='catalog_status', **fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(3); channel.connect(str(endpoint))
            channel.sendall((json.dumps({'schema_version': 1, 'request_id': 'startup-failure', 'op': op, **fields}) + '\n').encode())
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
        (root / 'initial.txt').unlink(); root.rmdir(); database.unlink()
        import shutil
        original_runtime = runtime
        runtime = work / 'failed-runtime'; runtime.mkdir()
        for name in ('fsearch-service', 'fsearch_catalog_journal.py'):
            shutil.copyfile(original_runtime / name, runtime / name)
        launches = work / 'worker-launches'
        worker = runtime / 'fsearch-worker'
        ready_body = json.dumps({'status': 'ready', 'snapshot_id': identity, 'checkpoint_sequence': 1}).encode()
        ready_frame = len(ready_body).to_bytes(4, 'big') + ready_body
        replay_fault = f'sys.stdout.buffer.write({ready_frame!r});sys.stdout.buffer.flush();sys.stdin.buffer.read(28);os._exit(86)\n'
        worker.write_text('#!/usr/bin/python3\nimport os,sys\n'+
            f'with open({str(launches)!r},"a") as log:log.write(str(os.getpid())+"\\n")\n'+
            'sys.stdin.buffer.read(1)\n'+
            ({'eof': 'os._exit(86)\n', 'protocol': 'sys.stdout.buffer.write(bytes(4));sys.stdout.buffer.flush();os._exit(86)\n', 'timeout': 'import time;time.sleep(10)\n', 'replay': replay_fault}[mode]))
        worker.chmod(0o700)
        server = subprocess.Popen([sys.executable, str(runtime / 'fsearch-service'), 'serve', '--catalog-journal', '--socket', str(endpoint), '--database', str(database)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env={**os.environ, 'FSEARCH_WORKER_STARTUP_TIMEOUT_MS': '300'})
        deadline = time.monotonic() + 5
        while not endpoint.exists():
            assert server.poll() is None
            assert time.monotonic() < deadline
            time.sleep(.01)
        for attempt in range(6):
            result = call('query', query='acknowledged-', limit=100)
            assert result['status'] == 'error' and result['error']['code'] == expected_error, result
            time.sleep(.05)
            count = len(launches.read_text().splitlines())
            assert count == 1, ('query-triggered durable startup restart', attempt, count, result)
            assert Path('/proc', str(server.pid), 'task', str(server.pid), 'children').read_text().strip() == ''
        call('stop'); assert server.wait(timeout=5) == 0; server = None
        runtime = original_runtime
        server, recovered = start()
        assert recovered['snapshot_id'] == identity and recovered['sequence'] == 2, recovered
        assert call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(root) + b'/acknowledged-\xff.txt').decode())['entry_id'] == first['entry_id']
        assert call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(root) + b'/second-acknowledged.txt').decode())['entry_id'] == second['entry_id']
        assert call('query', query='acknowledged-', limit=100)['incremental_coverage']['reason'] == 'catalog_recovered_source_gap'
        print(json.dumps({'result': 'durable_startup_failure_bounded', 'mode': mode, 'queries': 6, 'worker_launches': count, 'explicit_restart_recovers_sequence': 2}))
    finally:
        if server:
            try: call('stop')
            except OSError: server.terminate()
            server.wait(timeout=5)
