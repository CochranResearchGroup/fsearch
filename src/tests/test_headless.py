"""Public CLI behavior against owned snapshots; no user config or real-root scans."""
import json
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import signal
import unittest

BINARY = str(Path(sys.argv.pop(1)).resolve())
FIXTURE = str(Path(sys.argv.pop(1)).resolve())
FAULTS = str(Path(sys.argv.pop(1)).resolve())

class HeadlessCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='fsearch-cli-test-')
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.root = self.work / 'owned-index-root'
        self.root.mkdir()
        for name in ['invoice-one.pdf', 'invoice-two.pdf', 'notes.txt', 'Résumé.pdf', 'quote\"file.pdf', 'line\nbreak.pdf', 'star*.pdf', 'contenttype:pdf-report.txt']:
            (self.root / name).write_text('fixture\n')
        (self.root / 'child-folder').mkdir()
        raw_path = os.fsencode(self.root) + b'/raw-\xff.bin'
        with open(raw_path, 'wb') as stream:
            stream.write(b'fixture')
        self.database = self.work / 'snapshot.db'
        subprocess.run([FIXTURE, 'build', str(self.database), str(self.root)], check=True, timeout=15)
        self.database.chmod(0o600)
        shutil.rmtree(self.root)
        self.env = dict(os.environ)
        for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'G_MESSAGES_DEBUG'):
            self.env.pop(key, None)

    def query(self, *args, expected_exit=0, extra_env=None):
        result = subprocess.run([BINARY, '--database', str(self.database), *args],
                                env=dict(self.env, **(extra_env or {})), capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected_exit, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_searches_saved_names_after_root_is_removed(self):
        response = self.query('--query', 'invoice')
        self.assertEqual(response['schema_version'], 1)
        self.assertEqual(response['status'], 'ok')
        self.assertTrue(response['complete'])
        self.assertEqual([Path(row['path']).name for row in response['results']],
                         ['invoice-one.pdf', 'invoice-two.pdf'])
        self.assertEqual(response['visibility'], 'cached')

    def test_reports_observation_age_without_probing_the_root(self):
        response = self.query('--query', 'invoice')
        root = response['snapshot']['roots'][0]
        self.assertEqual(root['path'], str(self.root))
        self.assertGreater(root['last_scan_unix'], 0)
        self.assertGreaterEqual(root['age_seconds'], 0)
        self.assertEqual(root['last_error_code'], 0)

    def test_deadline_bounds_snapshot_open_and_reaps_worker(self):
        marker = self.work / 'worker.pid'
        started = time.monotonic()
        response = self.query('--query', 'invoice', '--timeout-ms', '50', expected_exit=1,
                              extra_env={'LD_PRELOAD': FAULTS, 'FSEARCH_FIXTURE_OPEN_DELAY_MS': '500',
                                         'FSEARCH_FIXTURE_MARKER': str(marker)})
        self.assertLess(time.monotonic() - started, 0.4)
        self.assertEqual(response['error']['code'], 'deadline')
        self.assertTrue(response['worker']['reaped'])
        pid = int(marker.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_result_and_work_limits_report_incomplete_results(self):
        limited = self.query('--query', 'invoice', '--limit', '1')
        self.assertEqual(limited['status'], 'result_limit')
        self.assertFalse(limited['complete'])
        self.assertTrue(limited['truncated'])
        self.assertEqual(len(limited['results']), 1)
        self.assertLessEqual(limited['examined'], 10)
        # Path queries exercise the exact-verification cap without basename pruning.
        work = self.query('--query', 'needle/not-present', '--path', '--max-candidates', '1')
        self.assertEqual(work['status'], 'work_limit')
        self.assertFalse(work['complete'])
        self.assertEqual(work['examined'], 1)

    def test_extension_kind_and_cached_path_filters(self):
        extension = self.query('--query', 'invoice', '--extension', 'PDF', '--kind', 'files')
        self.assertEqual(len(extension['results']), 2)
        folders = self.query('--query', 'child-folder', '--kind', 'folders')
        self.assertEqual([Path(row['path']).name for row in folders['results']], ['child-folder'])
        self.assertEqual(self.query('--query', 'owned-index-root/', '--path', '--kind', 'files')['status'], 'ok')
        self.assertEqual(self.query('--query', 'owned-index-root/', '--kind', 'files')['results'], [])

    def test_gui_syntax_and_globs_are_literal_and_unicode_round_trips(self):
        for query, name in [('contenttype:pdf', 'contenttype:pdf-report.txt'), ('*', 'star*.pdf'),
                            ('résumé', 'Résumé.pdf'), ('quote"', 'quote"file.pdf'), ('line\nbreak', 'line\nbreak.pdf')]:
            with self.subTest(query=query):
                response = self.query('--query', query)
                self.assertEqual([Path(row['path']).name for row in response['results']], [name])
        self.assertEqual(self.query('--query', 'résumé', '--match-case')['results'], [])
        response = self.query('--query', 'raw-')
        row = response['results'][0]
        self.assertIsNone(row['path'])
        self.assertEqual(base64.b64decode(row['path_bytes_base64']), os.fsencode(self.root) + b'/raw-\xff.bin')

    def test_empty_results_are_complete(self):
        response = self.query('--query', 'no-such-needle')
        self.assertEqual(response['status'], 'ok')
        self.assertTrue(response['complete'])
        self.assertEqual(response['results'], [])

    def test_missing_corrupt_public_symlink_and_fifo_snapshots_fail(self):
        original = self.database.read_bytes()
        self.database.unlink()
        self.assertEqual(self.query('--query', 'invoice', expected_exit=1)['error']['code'], 'snapshot_unavailable')
        self.database.write_bytes(b'invalid database')
        self.database.chmod(0o600)
        self.assertEqual(self.query('--query', 'invoice', expected_exit=1)['error']['code'], 'snapshot_load_failed')
        self.database.write_bytes(original)
        self.database.chmod(0o644)
        self.assertEqual(self.query('--query', 'invoice', expected_exit=1)['error']['code'], 'snapshot_not_private')
        self.database.chmod(0o600)
        target = self.work / 'private.db'
        self.database.rename(target)
        self.database.symlink_to(target)
        self.assertEqual(self.query('--query', 'invoice', expected_exit=1)['error']['code'], 'snapshot_unavailable')
        self.database.unlink()
        os.mkfifo(self.database)
        self.assertEqual(self.query('--query', 'invoice', expected_exit=1)['error']['code'], 'snapshot_not_private')

    def test_sparse_oversize_snapshot_is_rejected_before_load(self):
        with self.database.open('wb') as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        self.assertEqual(self.query('--query', 'invoice', expected_exit=1)['error']['code'], 'snapshot_size_limit')

    def test_request_and_response_limits(self):
        for args in [('--limit', '0'), ('--limit', '1001'), ('--regex',), ('--timeout-ms', '0'),
                     ('--max-candidates', '500001'), ('--query', 'x' * 4097)]:
            self.assertEqual(self.query('--query', 'invoice', *args, expected_exit=1)['error']['code'], 'invalid_request')
        result = subprocess.run([BINARY, '--database', str(self.database), '--query', '', '--max-bytes', '512'],
                                env=self.env, capture_output=True, timeout=15)
        self.assertLessEqual(len(result.stdout), 512)
        response = json.loads(result.stdout)
        self.assertFalse(response['complete'])

    def test_cancellation_returns_structured_failure_and_reaps_worker(self):
        marker = self.work / 'worker.pid'
        env = dict(self.env, LD_PRELOAD=FAULTS, FSEARCH_FIXTURE_OPEN_DELAY_MS='1000',
                   FSEARCH_FIXTURE_MARKER=str(marker))
        process = subprocess.Popen([BINARY, '--database', str(self.database), '--query', 'invoice'],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        until = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < until:
            time.sleep(0.005)
        self.assertTrue(marker.exists())
        process.send_signal(signal.SIGTERM)
        output, errors = process.communicate(timeout=2)
        self.assertEqual(process.returncode, 1, errors)
        response = json.loads(output)
        self.assertEqual(response['error']['code'], 'cancelled')
        self.assertTrue(response['worker']['reaped'])
        with self.assertRaises(ProcessLookupError):
            os.kill(int(marker.read_text()), 0)

    @unittest.skipUnless(shutil.which('strace'), 'strace required for filesystem isolation evidence')
    def test_query_only_lifecycle_has_no_index_probes_or_background_threads(self):
        trace = self.work / 'query.trace'
        marker = self.work / 'worker.pid'
        env = dict(self.env, LD_PRELOAD=FAULTS, FSEARCH_FIXTURE_AFTER_LOAD_DELAY_MS='6000',
                   FSEARCH_FIXTURE_MARKER=str(marker))
        started = time.monotonic()
        process = subprocess.Popen(['strace', '-f', '-e', 'trace=%file', '-o', str(trace), BINARY,
                                    '--database', str(self.database), '--query', 'contenttype:pdf',
                                    '--timeout-ms', '10000'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        until = time.monotonic() + 2
        marker_pid = ''
        while time.monotonic() < until:
            if marker.exists():
                marker_pid = marker.read_text()
                if marker_pid.isdecimal(): break
            time.sleep(0.005)
        self.assertTrue(marker_pid.isdecimal(), 'Worker marker never contained a complete PID')
        pid = int(marker_pid)
        self.assertEqual(len(list(Path(f'/proc/{pid}/task').iterdir())), 1)
        output, errors = process.communicate(timeout=12)
        self.assertGreaterEqual(time.monotonic() - started, 5.9)
        self.assertEqual(process.returncode, 0, errors)
        self.assertEqual(len(json.loads(output)['results']), 1)
        self.assertNotIn(str(self.root), trace.read_text())

    def test_worker_memory_cap_denies_large_allocation(self):
        marker = self.work / 'memory.txt'
        response = self.query('--query', 'invoice', extra_env={
            'LD_PRELOAD': FAULTS, 'FSEARCH_FIXTURE_MEMORY_MARKER': str(marker)})
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(marker.read_text(), 'denied')

    def test_validated_snapshot_fd_survives_atomic_path_replacement(self):
        replacement = self.work / 'replacement.db'
        replacement.write_bytes(b'invalid replacement')
        replacement.chmod(0o600)
        response = self.query('--query', 'invoice', extra_env={
            'LD_PRELOAD': FAULTS, 'FSEARCH_FIXTURE_REPLACE_WITH': str(replacement)})
        self.assertEqual(len(response['results']), 2)
        self.assertEqual(self.database.read_bytes(), b'invalid replacement')

    def test_utf8_query_is_locale_independent_and_logs_do_not_pollute_json(self):
        response = self.query('--query', 'résumé', extra_env={'LC_ALL': 'C', 'G_MESSAGES_DEBUG': 'all'})
        self.assertEqual([Path(row['path']).name for row in response['results']], ['Résumé.pdf'])

if __name__ == '__main__':
    unittest.main()
