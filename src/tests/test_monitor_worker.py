import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest

WORKER = sys.argv.pop(1)
FAULT = sys.argv.pop(1)
REFRESH_FAULT = sys.argv.pop(1)


def reply(process):
    data = bytearray()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not select.select([process.stdout], [], [], .05)[0]:
            continue
        byte = os.read(process.stdout.fileno(), 1)
        if not byte:
            raise AssertionError('worker EOF: ' + data.decode(errors='replace'))
        data.extend(byte)
        if byte == b'\n':
            return json.loads(data)
    raise AssertionError('worker reply deadline')


class MonitorWorker(unittest.TestCase):
    def start(self, root):
        worker = subprocess.Popen([WORKER, '--root', str(root)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop, worker)
        worker.stdin.write(b'G'); worker.stdin.flush()
        self.assertEqual(reply(worker)['status'], 'ready')
        return worker

    def stop(self, worker):
        if worker.poll() is None:
            worker.kill()
        worker.wait(timeout=3)
        for stream in (worker.stdin, worker.stdout, worker.stderr):
            stream.close()

    def test_missing_or_relative_root_is_structured(self):
        for arguments in ([], ['--root', 'relative']):
            result = subprocess.run([WORKER, *arguments], input=b'G', capture_output=True, timeout=3)
            self.assertEqual(json.loads(result.stdout)['error']['code'], 'invalid_request')
            self.assertNotEqual(result.returncode, 0)

    def test_gate_precedes_root_access(self):
        result = subprocess.run([WORKER, '--root', '/__fsearch_missing_gate_fixture__'],
                                input=b'X', capture_output=True, timeout=3)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'admission_denied')

    def test_create_rename_delete_in_nested_directory(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-monitor-owned-') as temporary:
            root = Path(temporary); nested = root/'nested'; nested.mkdir(); file = nested/'old.pdf'
            for action in ('create', 'rename', 'delete'):
                worker = self.start(root)
                if action == 'create': file.touch()
                elif action == 'rename': file.rename(nested/'new.pdf'); file = nested/'new.pdf'
                else: file.unlink()
                message = reply(worker)
                self.assertEqual(message['status'], 'dirty')
                self.assertNotIn('name', message)
                self.assertEqual(worker.wait(timeout=3), 0)

    def test_symlink_target_is_not_watched(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-monitor-owned-') as temporary:
            work = Path(temporary); root = work/'approved'; outside = work/'outside'
            root.mkdir(); outside.mkdir(); (root/'alias').symlink_to(outside, target_is_directory=True)
            worker = self.start(root); (outside/'private.pdf').touch()
            self.assertFalse(select.select([worker.stdout], [], [], .1)[0])
            (root/'visible.pdf').touch(); self.assertEqual(reply(worker)['status'], 'dirty')
            self.assertEqual(worker.wait(timeout=3), 0)

    def test_overflow_is_explicit_and_worker_exits(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-monitor-overflow-') as temporary:
            env = dict(os.environ, LD_PRELOAD=FAULT, FSEARCH_MONITOR_FIXTURE_OVERFLOW='1')
            result = subprocess.run([WORKER, '--root', temporary], input=b'G',
                                    env=env, capture_output=True, timeout=3)
            messages = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([m['status'] for m in messages], ['ready', 'overflow'])
            self.assertEqual(result.returncode, 0)

    def test_watch_admission_failure_never_reports_ready(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-monitor-watch-limit-') as temporary:
            env = dict(os.environ, LD_PRELOAD=FAULT, FSEARCH_MONITOR_FIXTURE_WATCH_FAILURE='1')
            result = subprocess.run([WORKER, '--root', temporary], input=b'G',
                                    env=env, capture_output=True, timeout=3)
            self.assertEqual(json.loads(result.stdout)['error']['code'], 'coverage_incomplete')
            self.assertNotEqual(result.returncode, 0)

    def test_native_memory_and_core_bounds(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-monitor-limits-') as temporary:
            worker = self.start(Path(temporary))
            limits = Path('/proc', str(worker.pid), 'limits').read_text()
            address = next(line.split() for line in limits.splitlines() if line.startswith('Max address space'))
            self.assertEqual(address[-3:-1], [str(256*1024*1024)]*2)
            core = next(line.split() for line in limits.splitlines() if line.startswith('Max core file size'))
            self.assertEqual(core[-3:-1], ['0', '0'])

    def test_unsupported_confinement_fails_before_root_open(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-monitor-no-landlock-') as temporary:
            root = Path(temporary)/'approved'; root.mkdir(); trace = Path(temporary)/'denied.trace'
            env = dict(os.environ, LD_PRELOAD=REFRESH_FAULT, FSEARCH_REFRESH_FIXTURE_NO_LANDLOCK='1')
            result = subprocess.run(['strace', '-f', '-e', 'trace=openat2', '-o', str(trace),
                                     WORKER, '--root', str(root)], input=b'G', env=env,
                                    capture_output=True, timeout=3)
            self.assertEqual(json.loads(result.stdout)['error']['code'], 'confinement_unavailable')
            self.assertNotIn(str(root), trace.read_text())

    def test_injected_mount_is_excluded_before_watch_installation(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-monitor-mount-') as temporary:
            root = Path(temporary); excluded = root/'excluded-mount'; excluded.mkdir()
            env = dict(os.environ, LD_PRELOAD=REFRESH_FAULT, FSEARCH_REFRESH_FIXTURE_MOUNT='1')
            process = subprocess.Popen([WORKER, '--root', str(root)], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            self.addCleanup(self.stop, process)
            process.stdin.write(b'G'); process.stdin.flush()
            self.assertEqual(reply(process)['watches'], 1)
            (excluded/'private.pdf').touch()
            self.assertFalse(select.select([process.stdout], [], [], .1)[0])
            (root/'visible.pdf').touch(); self.assertEqual(reply(process)['status'], 'dirty')
            self.assertEqual(process.wait(timeout=3), 0)
            error = process.stderr.read()
            self.assertIn(b'injected_EXDEV', error)
            self.assertNotIn(b'FORBIDDEN_METADATA', error)

    def test_moved_root_invalidates_watch_generation(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-monitor-owned-') as temporary:
            work = Path(temporary); root = work/'approved'; root.mkdir()
            worker = self.start(root); root.rename(work/'moved')
            self.assertEqual(reply(worker)['status'], 'offline')
            self.assertEqual(worker.wait(timeout=3), 0)


if __name__ == '__main__':
    unittest.main()
