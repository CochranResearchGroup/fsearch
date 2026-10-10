"""Owned-filesystem lifecycle controls; never invokes systemd or grants caps."""
import importlib.util
import pathlib
import os
import json
import subprocess
from unittest import mock
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('manage', pathlib.Path(__file__).with_name('manage.py'))
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.binary = self.base / 'setup'
        self.binary.write_bytes(b'\x7fELFfixture')
        self.bundle = self.base / 'bundle'
        self.root = self.base / 'dest'
        self.root.mkdir()
        manage.stage(self.binary, 1000, 1000, pathlib.Path('/owned'), self.bundle)

    def test_install_remove_and_preserve_other_data(self):
        unrelated = self.root / 'unrelated'
        unrelated.write_text('keep')
        m = manage.install(self.bundle, self.root)
        binary = manage.destination(self.root, manage.BASE / m['version'] / 'fsearch-broker-setup')
        self.assertEqual(binary.stat().st_mode & 0o777, 0o555)
        service = manage.destination(self.root, manage.UNITS / manage.SERVICE).read_text()
        self.assertIn('CapabilityBoundingSet=CAP_SYS_ADMIN', service)
        self.assertIn('Restart=no', service)
        manage.remove(self.root)
        self.assertEqual(list(self.root.iterdir()), [unrelated])

    def test_existing_config_refused_without_writes(self):
        config = manage.destination(self.root, manage.CONFIG)
        config.parent.mkdir(parents=True)
        config.write_text('preserve')
        with self.assertRaises(ValueError):
            manage.install(self.bundle, self.root)
        self.assertEqual(config.read_text(), 'preserve')
        self.assertFalse(manage.destination(self.root, manage.BASE).exists())

    def test_payload_drift_refused(self):
        (self.bundle / 'payload-0').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            manage.install(self.bundle, self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_installed_drift_preserved(self):
        manage.install(self.bundle, self.root)
        config = manage.destination(self.root, manage.CONFIG)
        config.write_text('administrator change')
        with self.assertRaises(ValueError):
            manage.remove(self.root)
        self.assertTrue(manage.destination(self.root, manage.RECEIPT).exists())
        self.assertEqual(config.read_text(), 'administrator change')

    def test_symlink_parent_refused(self):
        elsewhere = self.base / 'elsewhere'
        elsewhere.mkdir()
        (self.root / 'usr').symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(ValueError):
            manage.install(self.bundle, self.root)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_restrictive_umask_does_not_hide_new_directories(self):
        previous = os.umask(0o077)
        try:
            metadata = manage.install(self.bundle, self.root)
        finally:
            os.umask(previous)
        for name in metadata['created_directories']:
            self.assertEqual((self.root / name).stat().st_mode & 0o777, 0o755)
        manage.remove(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def fail_write(self, filename, mode):
        original = pathlib.Path.open
        class Broken:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def write(self, data):
                self.stream.write(data[:2])
                self.stream.flush()
                raise OSError('injected disk-full')
            def __exit__(self, *args):
                self.stream.close()
        def opened(path, *args, **kwargs):
            stream = original(path, *args, **kwargs)
            if args and args[0] == mode and path.name == filename:
                return Broken(stream)
            return stream
        return mock.patch.object(pathlib.Path, 'open', opened)

    def test_partial_binary_write_removed_and_retry_succeeds(self):
        with self.fail_write('fsearch-broker-setup', 'xb'):
            with self.assertRaisesRegex(OSError, 'injected disk-full'):
                manage.install(self.bundle, self.root)
        self.assertEqual(list(self.root.iterdir()), [])
        manage.install(self.bundle, self.root)
        manage.remove(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_partial_receipt_write_removed(self):
        with self.fail_write('installation.json', 'x'):
            with self.assertRaisesRegex(OSError, 'injected disk-full'):
                manage.install(self.bundle, self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cleanup_failure_preserves_original_and_continues(self):
        original = pathlib.Path.unlink
        def unlink(path, *args, **kwargs):
            if path.name == 'installation.json':
                raise OSError('injected cleanup failure')
            return original(path, *args, **kwargs)
        with self.fail_write('installation.json', 'x'), mock.patch.object(pathlib.Path, 'unlink', unlink):
            with self.assertRaisesRegex(OSError, 'injected disk-full') as caught:
                manage.install(self.bundle, self.root)
        self.assertTrue(any('injected cleanup failure' in note for note in caught.exception.__notes__))
        survivors = [p for p in self.root.rglob('*') if p.is_file()]
        self.assertEqual([p.name for p in survivors], ['installation.json'])

    def test_receipt_separates_activation_request_from_result(self):
        metadata = manage.install(self.bundle, self.root, listen=True)
        receipt = json.loads(manage.destination(self.root, manage.RECEIPT).read_text())
        self.assertNotIn('activation', receipt)
        self.assertEqual(metadata['socket_activation'], {'requested': True, 'result': 'not_attempted'})
        self.assertEqual(receipt['socket_activation'], metadata['socket_activation'])

    def test_systemd_rollback_timeout_does_not_skip_file_cleanup(self):
        real_destination = manage.destination
        real_parent = manage.safe_parent
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if command[1] == 'show':
                return subprocess.CompletedProcess(command, 0, stdout='not-found\n')
            if command[1] in ('enable', 'disable'):
                raise subprocess.TimeoutExpired(command, kwargs['timeout'])
            return subprocess.CompletedProcess(command, 0)
        # Route root-mode files into the owned fixture and mock every systemctl call.
        with mock.patch.object(manage, 'destination', lambda prefix, target: real_destination(self.root, target)), \
             mock.patch.object(manage, 'safe_parent', lambda path, prefix, made: real_parent(path, self.root, made)), \
             mock.patch.object(manage.subprocess, 'run', run):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                manage.install(self.bundle, pathlib.Path('/'), listen=True)
        self.assertEqual(caught.exception.cmd[1], 'enable')
        self.assertTrue(any('Rollback incomplete' in note for note in caught.exception.__notes__))
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertIn(['systemctl', 'stop', manage.SERVICE], calls)


if __name__ == '__main__':
    unittest.main()
