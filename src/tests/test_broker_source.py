"""Owned ordinary descriptors only; no fanotify or root observation."""
import array
import os
from pathlib import Path
import socket
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fsearch_broker_source as b
import fsearch_fanotify_events as f
from test_fanotify_events import event, info


class Transport(unittest.TestCase):
    def setUp(self):
        self.left, self.right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.read, self.write = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        self.token = b'x' * 32

    def tearDown(self):
        self.left.close(); self.right.close()
        os.close(self.read); os.close(self.write)

    def receive(self, **fields):
        return b.receive_source(self.right, peer_uid=os.geteuid(), generation=3, token=self.token, **fields)

    def test_transfer_ownership_and_cloexec(self):
        b.send_source(self.left, self.read, peer_uid=os.geteuid(), generation=3, token=self.token)
        received = self.receive()
        try:
            self.assertFalse(os.get_inheritable(received))
            os.write(self.write, b'owned')
            self.assertEqual(os.read(received, 5), b'owned')
        finally:
            os.close(received)
        # Receiver closure must not close the sender's retained descriptor.
        os.fstat(self.read)

    def test_bad_identity_and_multiple_descriptors_are_reaped(self):
        baseline = len(os.listdir('/proc/self/fd'))
        for count, payload in ((1, b'wrong'), (2, b._identity(3, self.token, (0, 0))), (20, b._identity(3, self.token, (0, 0)))):
            self.left.sendmsg([payload], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [self.read] * count))])
            with self.assertRaisesRegex(f.Gap, 'handoff_invalid'):
                self.receive()
            self.assertEqual(len(os.listdir('/proc/self/fd')), baseline)

    def test_peer_refused_before_receiving(self):
        with self.assertRaisesRegex(f.Gap, 'handoff_peer'):
            b.receive_source(self.right, peer_uid=os.geteuid() + 1, generation=3, token=self.token)

    def test_blocking_source_refused_and_closed(self):
        os.set_blocking(self.read, True)
        baseline = len(os.listdir('/proc/self/fd'))
        b.send_source(self.left, self.read, peer_uid=os.geteuid(), generation=3, token=self.token)
        with self.assertRaisesRegex(f.Gap, 'source_blocking'):
            self.receive()
        self.assertEqual(len(os.listdir('/proc/self/fd')), baseline)

    def test_root_binding_and_production_authority(self):
        baseline = len(os.listdir('/proc/self/fd'))
        b.send_source(self.left, self.read, peer_uid=os.geteuid(), generation=3, token=self.token, root_identity=(7, 8))
        with self.assertRaisesRegex(f.Gap, 'handoff_invalid'):
            b.receive_source(self.right, peer_uid=os.geteuid(), generation=3, token=self.token, root_identity=(7, 9))
        self.assertEqual(len(os.listdir('/proc/self/fd')), baseline)
        with self.assertRaisesRegex(f.Gap, 'handoff_authority'):
            b.receive_source(self.right, peer_uid=os.geteuid(), generation=3, token=self.token, source_kind='fanotify')


class Reader(unittest.TestCase):
    def setUp(self):
        # SOCK_SEQPACKET stands in for atomic complete kernel read batches.
        self.input, self.output = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.input.setblocking(False)
        self.session = f.BootstrapSession(1)
        self.reader = b.SourceReader(self.input.detach(), self.session)
        self.applied = []

    def tearDown(self):
        self.reader.close(); self.output.close()

    def pump(self):
        return self.reader.pump(lambda handle, generation: 7 if handle.opaque == b'inside' else None, self.applied.append)

    def ready(self):
        self.session.finish_baseline(1)
        self.assertTrue(self.pump())
        self.assertEqual(self.session.state, 'watching')

    def test_drain_then_apply_and_source_cut(self):
        self.ready()
        self.output.send(event())
        self.assertTrue(self.pump())
        self.assertEqual(self.applied[0].sides, ((2, 7, b'name'),))
        self.assertEqual(self.session.applied_sequence, 1)
        self.assertEqual(self.session.source_sequence, 1)
        self.assertEqual(self.session.state, 'watching')

    def test_bootstrap_drain_does_not_complete_inventory(self):
        self.assertTrue(self.pump())
        self.assertEqual(self.session.state, 'reconciling')
        self.session.finish_baseline(1)
        self.assertTrue(self.pump())
        self.assertEqual(self.session.state, 'watching')

    def test_budget_exhaustion_does_not_manufacture_drain(self):
        self.ready(); self.reader.max_batches = 1
        self.output.send(event())
        self.assertFalse(self.pump())
        self.assertEqual(self.session.state, 'pending')
        self.assertTrue(self.pump())
        self.assertEqual(self.session.state, 'watching')

    def test_outside_churn_is_bounded_without_export(self):
        self.ready(); self.reader.max_batches = 2
        for _ in range(3):
            self.output.send(event(records=[info(2, b'outside', b'outside-secret'), info(1)]))
        self.assertFalse(self.pump())
        self.assertEqual(self.applied, [])
        self.assertEqual(self.session.state, 'pending')
        self.assertTrue(self.pump())
        self.assertEqual(self.session.source_sequence, 3)

    def test_dirty_bootstrap_overflow_and_partial_batch_defer(self):
        self.output.send(event())
        with self.assertRaisesRegex(f.Gap, 'bootstrap_dirty'):
            self.pump()
        self.assertEqual(self.session.state, 'deferred')
        self.assertEqual(self.applied, [])

    def test_malformed_batch_does_not_apply_prefix(self):
        self.ready(); self.output.send(event() + event()[:12])
        with self.assertRaisesRegex(f.Gap, 'metadata_truncated'):
            self.pump()
        self.assertEqual(self.applied, [])
        self.assertEqual(self.session.state, 'deferred')

    def test_apply_failure_is_sticky_and_identifier_free(self):
        self.ready(); self.output.send(event())
        def failed(export):
            raise RuntimeError('private-path')
        with self.assertRaisesRegex(f.Gap, '^catalog_apply_failed$'):
            self.reader.pump(lambda *args: 7, failed)
        self.assertEqual(self.session.state, 'deferred')
        self.assertEqual(self.session.pending, [])

    def test_eof_preserves_deferred_state(self):
        self.ready(); self.output.close()
        with self.assertRaisesRegex(f.Gap, 'source_eof'):
            self.pump()
        self.assertEqual(self.session.state, 'deferred')


if __name__ == '__main__':
    unittest.main()
