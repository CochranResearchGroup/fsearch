import ctypes
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)  # Adopt owned workers for fault teardown.

MONITOR, CLI, FAULT_DIR = sys.argv[1:4]
del sys.argv[1:4]


def reply(process):
    deadline = time.monotonic() + 5
    data = bytearray()
    while time.monotonic() < deadline:
        if not select.select([process.stdout], [], [], .05)[0]: continue
        byte = os.read(process.stdout.fileno(), 1)
        if not byte: raise AssertionError('EOF: ' + data.decode(errors='replace'))
        data.extend(byte)
        if byte == b'\n': return json.loads(data)
    raise AssertionError('monitor reply deadline')


class Monitor(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='fsearch-monitor-supervisor-')
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name); self.root = self.work/'approved'; self.root.mkdir()
        self.database = self.work/'accepted.db'

    def start(self, env=None, socket=None, timeout_ms=None):
        command = ['python3', MONITOR, 'watch', '--root', str(self.root),
                   '--database', str(self.database)]
        if socket: command.extend(['--socket', str(socket)])
        if timeout_ms: command.extend(['--timeout-ms', str(timeout_ms)])
        process = subprocess.Popen(command,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.addCleanup(self.stop, process)
        return process

    def stop(self, process):
        if process.poll() is None: process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
        process.stdout.close(); process.stderr.close()

    def published(self, process):
        for _ in range(20):
            message = reply(process)
            if message['status'] == 'published': return message
            self.assertNotEqual(message['status'], 'error', message)
        self.fail('no accepted publication')

    def query(self, text):
        result = subprocess.run([CLI, '--database', str(self.database), '--query', text,
                                 '--kind', 'files'], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_missing_or_relative_root_rejected_before_state(self):
        for arguments in ([], ['--root', 'relative'], ['--root', '/'+'x'*4096]):
            result = subprocess.run(['python3', MONITOR, 'watch', '--database', str(self.database),
                                     *arguments], capture_output=True, text=True, timeout=3)
            self.assertEqual(json.loads(result.stdout)['error']['code'], 'invalid_request')
            self.assertFalse(Path(str(self.database)+'.monitor.state').exists())

    def test_create_rename_delete_reaches_accepted_snapshot(self):
        process = self.start(); self.published(process)
        nested = self.root/'new-directory'; nested.mkdir(); file = nested/'invoice.pdf'; file.touch()
        self.published(process); self.assertEqual(len(self.query('invoice')['results']), 1)
        file.rename(nested/'renamed.pdf'); self.published(process)
        self.assertEqual(self.query('invoice')['results'], [])
        self.assertEqual(len(self.query('renamed')['results']), 1)
        (nested/'renamed.pdf').unlink(); self.published(process)
        self.assertEqual(self.query('renamed')['results'], [])

    def test_offline_root_preserves_snapshot(self):
        (self.root/'invoice.pdf').touch(); process = self.start(); self.published(process)
        before = self.database.read_bytes(); self.root.rename(self.work/'offline')
        while True:
            message = reply(process)
            if message['status'] == 'error': break
        self.assertEqual(message['error']['code'], 'root_offline')
        self.assertNotEqual(process.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(len(self.query('invoice')['results']), 1)

    def test_competing_monitor_is_rejected(self):
        process = self.start(); self.published(process); before = self.database.read_bytes()
        second = self.start(); message = reply(second)
        self.assertEqual(message['error']['code'], 'already_running')
        self.assertNotEqual(second.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)

    def test_failed_watcher_preserves_snapshot_without_restart(self):
        (self.root/'invoice.pdf').touch(); process = self.start(); self.published(process)
        before = self.database.read_bytes()
        state = json.loads(Path(str(self.database)+'.monitor.state').read_text())
        os.kill(state['worker']['pid'], signal.SIGKILL)
        message = reply(process)
        self.assertEqual(message['error']['code'], 'failed_worker')
        self.assertNotEqual(process.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(len(self.query('invoice')['results']), 1)

    def test_monitor_cannot_bypass_refresh_quarantine(self):
        state = {'phase': 'quarantined', 'reason': 'owned_fault', 'worker': None}
        Path(str(self.database)+'.refresh.state').write_text(json.dumps(state))
        process = self.start()
        while True:
            message = reply(process)
            if message['status'] == 'error': break
        self.assertEqual(message['error']['code'], 'quarantined')
        self.assertNotEqual(process.wait(timeout=3), 0)
        self.assertFalse(self.database.exists())
        self.assertEqual(json.loads(Path(str(self.database)+'.refresh.state').read_text()), state)

    def test_change_during_refresh_is_not_published_as_clean_generation(self):
        process = self.start(); self.published(process); self.stop(process)
        before = self.database.read_bytes()
        fault = str(Path(FAULT_DIR)/'librefresh_fault_fixture.so')
        env = dict(os.environ, LD_PRELOAD=fault, FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='350')
        process = self.start(env); self.assertEqual(reply(process)['status'], 'armed')
        time.sleep(.05); (self.root/'invoice.pdf').touch()
        message = reply(process)
        self.assertEqual(message['status'], 'dirty')
        self.assertEqual(self.database.read_bytes(), before)
        self.published(process); self.assertEqual(len(self.query('invoice')['results']), 1)

    def test_orderly_restart_uses_original_approved_root(self):
        process = self.start(); self.published(process); self.stop(process)
        (self.root/'invoice.pdf').touch(); second = self.start(); self.published(second)
        self.assertEqual(len(self.query('invoice')['results']), 1)

    def reap_owned(self, pid):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try: reaped, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError: return
            if reaped: return
            time.sleep(.005)
        self.fail('owned worker did not exit')

    def test_uncertain_cleanup_blocks_restart_until_explicit_recovery(self):
        block = self.work/'blocked'
        fault = str(Path(FAULT_DIR)/'libheadless_fault_fixture.so')
        env = dict(os.environ, LD_PRELOAD=fault, FSEARCH_FIXTURE_WAITPID_BLOCK_FILE=str(block))
        process = self.start(env); self.published(process); before = self.database.read_bytes()
        state_path = Path(str(self.database)+'.monitor.state')
        pid = json.loads(state_path.read_text())['worker']['pid']
        block.touch(); process.terminate()
        # The native child is killed, but reap evidence remains unavailable.
        deadline = time.monotonic()+.08
        while time.monotonic() < deadline:
            if '\nState:\tZ' in Path('/proc', str(pid), 'status').read_text(): break
            time.sleep(.001)
        else: self.fail('owned watcher was not killed before second shutdown signal')
        process.terminate()
        message = reply(process)
        self.assertEqual(message['error']['code'], 'cleanup_unproved')
        self.assertNotEqual(process.wait(timeout=3), 0)
        self.assertEqual(json.loads(state_path.read_text())['phase'], 'quarantined')
        block.unlink(); self.reap_owned(pid)
        second = self.start(); self.assertEqual(reply(second)['error']['code'], 'quarantined')
        self.assertNotEqual(second.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)
        recovered = subprocess.run(['python3', MONITOR, 'recover', '--database', str(self.database)],
                                   capture_output=True, text=True, timeout=3)
        self.assertEqual(json.loads(recovered.stdout)['status'], 'recovered')
        self.assertEqual(recovered.returncode, 0)
        self.assertEqual(json.loads(state_path.read_text())['phase'], 'stopped')
        self.assertEqual(self.database.read_bytes(), before)

    def test_abrupt_supervisor_exit_requires_recovery_after_parent_death(self):
        process = self.start(); self.published(process); before = self.database.read_bytes()
        pid = json.loads(Path(str(self.database)+'.monitor.state').read_text())['worker']['pid']
        process.kill(); process.wait(timeout=3); self.reap_owned(pid)
        second = self.start(); self.assertEqual(reply(second)['error']['code'], 'quarantined')
        self.assertNotEqual(second.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)
        recovered = subprocess.run(['python3', MONITOR, 'recover', '--database', str(self.database)],
                                   capture_output=True, text=True, timeout=3)
        self.assertEqual(recovered.returncode, 0, recovered.stdout+recovered.stderr)

    def test_overflow_reconciliation_is_bounded_and_preserves_snapshot(self):
        initial = self.start(); self.published(initial); self.stop(initial)
        before = self.database.read_bytes()
        fault = str(Path(FAULT_DIR)/'libmonitor_fault_fixture.so')
        env = dict(os.environ, LD_PRELOAD=fault, FSEARCH_MONITOR_FIXTURE_OVERFLOW='1')
        process = self.start(env); overflows = 0
        for _ in range(20):
            message = reply(process)
            if message['status'] == 'overflow': overflows += 1
            if message['status'] == 'error': break
        self.assertEqual(message['error']['code'], 'reconciliation_limit')
        self.assertEqual(overflows, 8)
        self.assertNotEqual(process.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)

    def warm_query(self, socket, text):
        result = subprocess.run([CLI, '--socket', str(socket), '--query', text, '--kind', 'files'],
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_monitor_replaces_warm_snapshot_with_acknowledged_identity(self):
        initial = self.start(); self.published(initial); self.stop(initial)
        socket = self.work/'query.sock'
        service = Path(CLI).parent/'fsearch-service'
        server = subprocess.Popen(['python3', str(service), 'serve', '--socket', str(socket),
                                   '--database', str(self.database)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop, server)
        deadline = time.monotonic()+3
        while not socket.exists() and time.monotonic() < deadline: time.sleep(.005)
        old = self.warm_query(socket, 'invoice')
        monitor = self.start(socket=socket); self.published(monitor)
        acknowledged = reply(monitor)
        self.assertEqual(acknowledged['status'], 'serving_replaced')
        self.assertEqual(self.warm_query(socket, 'invoice')['snapshot']['identity'], acknowledged['snapshot_id'])
        self.assertNotEqual(acknowledged['snapshot_id'], old['snapshot']['identity'])
        (self.root/'invoice.pdf').touch(); published = self.published(monitor)
        acknowledged = reply(monitor)
        self.assertEqual(acknowledged['status'], 'serving_replaced')
        found = self.warm_query(socket, 'invoice')
        self.assertEqual(len(found['results']), 1)
        self.assertEqual(found['snapshot']['identity'], acknowledged['snapshot_id'])
        self.assertEqual(published['snapshot_id'], acknowledged['snapshot_id'])

    def test_unavailable_service_does_not_fabricate_replacement_ack(self):
        monitor = self.start(socket=self.work/'absent.sock')
        self.published(monitor)
        message = reply(monitor)
        self.assertEqual(message['status'], 'error')
        self.assertEqual(message['error']['code'], 'service_unavailable')
        self.assertNotEqual(monitor.wait(timeout=3), 0)
        self.assertTrue(self.database.exists())

    def test_watch_startup_deadline_preserves_accepted_snapshot(self):
        initial = self.start(); self.published(initial); self.stop(initial)
        before = self.database.read_bytes()
        fault = str(Path(FAULT_DIR)/'librefresh_fault_fixture.so')
        env = dict(os.environ, LD_PRELOAD=fault, FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='400')
        monitor = self.start(env=env, timeout_ms=30)
        message = reply(monitor)
        self.assertEqual(message['error']['code'], 'watch_deadline')
        self.assertNotEqual(monitor.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)
        state = json.loads(Path(str(self.database)+'.monitor.state').read_text())
        self.assertEqual(state['phase'], 'stopped')
        self.assertIsNone(state['worker'])

    def test_watch_admission_failure_preserves_accepted_snapshot(self):
        initial = self.start(); self.published(initial); self.stop(initial)
        before = self.database.read_bytes()
        fault = str(Path(FAULT_DIR)/'libmonitor_fault_fixture.so')
        env = dict(os.environ, LD_PRELOAD=fault, FSEARCH_MONITOR_FIXTURE_WATCH_FAILURE='1')
        monitor = self.start(env=env)
        self.assertEqual(reply(monitor)['error']['code'], 'coverage_incomplete')
        self.assertNotEqual(monitor.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)

    def test_supervisor_and_two_owned_children_have_address_space_bounds(self):
        fault = str(Path(FAULT_DIR)/'librefresh_fault_fixture.so')
        env = dict(os.environ, LD_PRELOAD=fault, FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='500')
        monitor = self.start(env=env)
        self.assertEqual(reply(monitor)['status'], 'armed')
        state_path = Path(str(self.database)+'.refresh.state')
        deadline = time.monotonic()+.4
        while time.monotonic() < deadline:
            try:
                state = json.loads(state_path.read_text())
                if state.get('worker'): break
            except FileNotFoundError: pass
            time.sleep(.005)
        else: self.fail('no gated refresh child')
        watch_pid = json.loads(Path(str(self.database)+'.monitor.state').read_text())['worker']['pid']
        scanner_pid = state['worker']['pid']
        children = set(map(int, Path('/proc', str(monitor.pid), 'task', str(monitor.pid), 'children').read_text().split()))
        self.assertEqual(children, {watch_pid, scanner_pid})
        for pid, soft in ((monitor.pid, 64), (watch_pid, 256), (scanner_pid, 256)):
            limits = Path('/proc', str(pid), 'limits').read_text()
            address = next(line.split() for line in limits.splitlines() if line.startswith('Max address space'))
            self.assertEqual(address[-3:-1], [str(soft*1024*1024), str(256*1024*1024)])
        self.published(monitor)

    def test_monitor_cannot_overlap_an_admitted_explicit_refresh(self):
        initial = self.start(); self.published(initial); self.stop(initial)
        before = self.database.read_bytes()
        fault = str(Path(FAULT_DIR)/'librefresh_fault_fixture.so')
        env = dict(os.environ, LD_PRELOAD=fault, FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='500')
        refresh = Path(CLI).parent/'fsearch-refresh'
        writer = subprocess.Popen(['python3', str(refresh), 'refresh', '--root', str(self.root),
                                   '--database', str(self.database)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env)
        self.addCleanup(self.stop, writer)
        state_path = Path(str(self.database)+'.refresh.state'); deadline = time.monotonic()+.4
        while time.monotonic() < deadline:
            state = json.loads(state_path.read_text())
            if state.get('worker'): break
            time.sleep(.005)
        else: self.fail('no admitted competing refresh')
        monitor = self.start()
        while True:
            message = reply(monitor)
            if message['status'] == 'error': break
        self.assertEqual(message['error']['code'], 'already_running')
        self.assertNotEqual(monitor.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(writer.wait(timeout=3), 0)

    def paused_child(self, state_path):
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            try:
                state = json.loads(state_path.read_text()); record = state.get('worker')
                if record and '\nState:\tT' in Path('/proc', str(record['pid']), 'status').read_text():
                    return record['pid']
            except FileNotFoundError: pass
            time.sleep(.005)
        self.fail('owned race pause was not reached')

    def test_directory_moved_during_watch_setup_preserves_accepted_snapshot(self):
        (self.root/'invoice.pdf').touch(); initial = self.start(); self.published(initial); self.stop(initial)
        before = self.database.read_bytes(); nested = self.root/'nested'; nested.mkdir()
        (nested/'race-probe.pdf').touch()
        env = dict(os.environ, LD_PRELOAD=str(Path(FAULT_DIR)/'librefresh_fault_fixture.so'),
                   FSEARCH_FIXTURE_RACE_PAUSE='1')
        monitor = self.start(env=env)
        pid = self.paused_child(Path(str(self.database)+'.monitor.state'))
        nested.rename(self.work/'outside'); os.kill(pid, signal.SIGCONT)
        self.assertEqual(reply(monitor)['error']['code'], 'coverage_incomplete')
        self.assertNotEqual(monitor.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(len(self.query('invoice')['results']), 1)

    def test_directory_moved_during_explicit_refresh_preserves_accepted_snapshot(self):
        (self.root/'invoice.pdf').touch(); initial = self.start(); self.published(initial); self.stop(initial)
        before = self.database.read_bytes(); nested = self.root/'nested'; nested.mkdir()
        (nested/'race-probe.pdf').touch()
        env = dict(os.environ, LD_PRELOAD=str(Path(FAULT_DIR)/'librefresh_fault_fixture.so'),
                   FSEARCH_FIXTURE_RACE_PAUSE='1')
        refresh = Path(CLI).parent/'fsearch-refresh'
        writer = subprocess.Popen(['python3', str(refresh), 'refresh', '--root', str(self.root),
                                   '--database', str(self.database)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env)
        self.addCleanup(self.stop, writer)
        pid = self.paused_child(Path(str(self.database)+'.refresh.state'))
        nested.rename(self.work/'outside'); os.kill(pid, signal.SIGCONT)
        self.assertEqual(reply(writer)['error']['code'], 'refresh_failed')
        self.assertNotEqual(writer.wait(timeout=3), 0)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(len(self.query('invoice')['results']), 1)

    def test_shutdown_proves_worker_cleanup(self):
        process = self.start(); self.published(process)
        state_path = Path(str(self.database)+'.monitor.state')
        state = json.loads(state_path.read_text()); pid = state['worker']['pid']
        process.terminate(); self.assertEqual(process.wait(timeout=3), 0)
        self.assertFalse(Path('/proc', str(pid)).exists())
        self.assertEqual(json.loads(state_path.read_text())['phase'], 'stopped')


if __name__ == '__main__': unittest.main()
