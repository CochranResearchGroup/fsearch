"""Synthetic ABI fixtures only: never initialize fanotify or inspect real roots."""
import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fsearch_fanotify_events as f


def info(role, opaque=b'inside', name=b'name', fsid=b'12345678', kind=1):
    tail = fsid + struct.pack('=Ii', len(opaque), kind) + opaque
    if role != 1:
        tail += name + b'\0'
    return struct.pack('=BBH', role, 0, len(tail) + 4) + tail


def event(mask=f.CREATE, records=None):
    if records is None:
        records = [info(2), info(1, b'target')]
    tail = b''.join(records)
    return f.META.pack(24 + len(tail), 3, 0, 24, mask, -1, 12345) + tail


class Fixtures(unittest.TestCase):
    def admit(self, handle, generation):
        return 7 if handle == f.Handle(b'12345678', 1, b'inside') else None

    def test_raw_name_and_no_identifiers_in_repr(self):
        data = event(records=[info(2, name=b'\xffsecret'), info(1)])
        decoded = f.decode(data)
        output = f.ExportFilter(1).consume(data, 1, self.admit)
        self.assertEqual(output[0].sides, ((2, 7, b'\xffsecret'),))
        for obj in (decoded[0], decoded[0].sides[0], decoded[0].target, output[0]):
            self.assertNotIn('secret', repr(obj))

    def test_rename_filters_each_side(self):
        for old, new, roles in ((b'inside', b'outside', (10,)), (b'outside', b'inside', (12,)),
                                (b'inside', b'inside', (10, 12)), (b'outside', b'outside', ())):
            data = event(f.RENAME, [info(10, old, b'old-secret'), info(12, new, b'new-secret'), info(1)])
            result = f.ExportFilter(1).consume(data, 1, self.admit)
            self.assertEqual(tuple(x[0] for x in result[0].sides) if result else (), roles)
            if roles == (10,):
                self.assertNotIn(b'new-secret', tuple(x[2] for x in result[0].sides))

    def test_handle_identity_not_inode_or_bytes_alone(self):
        for fsid, kind in ((b'87654321', 1), (b'12345678', 2)):
            self.assertEqual(f.ExportFilter(1).consume(event(records=[info(2, fsid=fsid, kind=kind), info(1)]), 1, self.admit), ())

    def test_revalidate_every_event_and_revoke(self):
        calls = []
        def validate(handle, generation):
            calls.append(handle)
            return 7 if len(calls) == 1 else None
        result = f.ExportFilter(1).consume(event() * 2, 1, validate)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(result), 1)

    def test_root_move_is_gap_even_when_both_parents_are_outside(self):
        broker = f.ExportFilter(1)
        broker.root_handle = f.Handle(b'12345678', 1, b'root')
        data = event(f.RENAME | f.ONDIR, [info(10, b'outside-old'), info(12, b'outside-new'), info(1, b'root')])
        with self.assertRaisesRegex(f.Gap, 'root_identity_changed'):
            broker.consume(data, 1, lambda *args: None)
        self.assertEqual(broker.sequence, 0)

    def test_malformed_batch_never_exports_valid_prefix(self):
        original = event()
        for cut in range(1, len(original)):
            broker = f.ExportFilter(1)
            with self.assertRaises(f.Gap):
                broker.consume(original + original[:cut], 1, self.admit)
            self.assertEqual(broker.sequence, 0)
            with self.assertRaises(f.Gap):
                broker.consume(original, 1, self.admit)

    def test_coalesced_outside_namespace_is_discarded(self):
        data = event(f.CREATE | f.DELETE, [info(2, b'outside'), info(1)])
        broker = f.ExportFilter(1)
        self.assertEqual(broker.consume(data, 1, self.admit), ())
        self.assertEqual(broker.sequence, 0)
        self.assertIsNone(broker.reason)

    def test_coalesced_admitted_namespace_remains_gap(self):
        broker = f.ExportFilter(1)
        with self.assertRaisesRegex(f.Gap, '^ambiguous_operation$'):
            broker.consume(event(f.CREATE | f.DELETE), 1, self.admit)
        self.assertEqual(broker.sequence, 0)
        with self.assertRaisesRegex(f.Gap, '^ambiguous_operation$'):
            broker.consume(event(), 1, self.admit)

    def test_coalesced_bootstrap_records_still_detect_dirty_parent(self):
        inside = f.Handle(b'12345678', 1, b'inside')
        for parent, dirty in ((b'outside', False), (b'inside', True)):
            sketch = f.BootstrapChanges()
            sketch.observe(f.decode(event(f.CREATE | f.DELETE, [info(2, parent), info(1)])))
            if dirty:
                with self.assertRaisesRegex(f.Gap, 'bootstrap_dirty'):
                    sketch.qualify([inside], lambda handle: 7 if handle == inside else None, lambda: None)
            else:
                sketch.qualify([inside], lambda handle: 7 if handle == inside else None, lambda: None)
                self.assertTrue(sketch.qualified)

    def test_invalid_abi(self):
        cases = [event(f.OVERFLOW, []), event(0x10000),
                 event(records=[info(2)]), event(records=[info(2), info(2), info(1)]),
                 event(records=[info(99), info(1)]), event(records=[info(2, name=b'../escape'), info(1)]),
                 event(records=[info(2, name=b''), info(1)]), event(records=[info(2, name=b'.'), info(1)]),
                 event(records=[info(2, opaque=b'x'*129), info(1)])]
        wrong_version = bytearray(event()); wrong_version[4] = 4
        wrong_fd = bytearray(event()); struct.pack_into('=i', wrong_fd, 16, 5)
        wrong_length = bytearray(event()); struct.pack_into('=H', wrong_length, 26, 0)
        for data in cases + [bytes(wrong_version), bytes(wrong_fd), bytes(wrong_length)]:
            with self.assertRaises(f.Gap): f.decode(data)

    def test_limits_atomic_and_identifier_free_errors(self):
        broker = f.ExportFilter(1, max_exports=1)
        with self.assertRaisesRegex(f.Gap, '^export_limit$'):
            broker.consume(event() * 2, 1, self.admit)
        self.assertEqual(broker.sequence, 0)
        with self.assertRaises(f.Gap): f.decode(event(), max_bytes=1)
        with self.assertRaises(f.Gap): f.decode(event() * 2, max_events=1)
        for error_type in (RuntimeError, f.Gap):
            def bad(*args): raise error_type('outside-secret')
            with self.assertRaisesRegex(f.Gap, '^admission_failed$'):
                f.ExportFilter(1).consume(event(), 1, bad)

    def test_invalid_clock_and_admission(self):
        for now in (float('nan'), float('inf'), -1, True):
            with self.assertRaisesRegex(f.Gap, 'clock_invalid'):
                f.ExportFilter(1).progress(now)
        with self.assertRaisesRegex(f.Gap, 'admission_invalid'):
            f.ExportFilter(1).consume(event(), 1, lambda *args: True)
        output = f.ExportFilter(1).consume(event(), 1, lambda *args: 0)
        self.assertEqual(output[0].sides, ((2, 0, b'name'),))

    def test_sequence_generation_and_lease(self):
        broker = f.ExportFilter(5)
        broker.progress(10)
        broker.check_lease(12)
        a = broker.consume(event(), 5, self.admit)
        b = broker.consume(event(), 5, self.admit)
        self.assertEqual((a[0].sequence, b[0].sequence), (1, 2))
        with self.assertRaisesRegex(f.Gap, 'root_generation_changed'):
            broker.consume(event(), 6, self.admit)
        broker = f.ExportFilter(1)
        broker.progress(10)
        with self.assertRaisesRegex(f.Gap, 'source_progress_timeout'): broker.check_lease(12.001)
        with self.assertRaises(f.Gap): broker.progress(13)
        broker = f.ExportFilter(1); broker.progress(10)
        with self.assertRaisesRegex(f.Gap, 'clock_regressed'): broker.progress(9)


class BootstrapFixtures(unittest.TestCase):
    def session(self, **kwargs):
        session = f.BootstrapSession(1, **kwargs)
        session.progress(10)
        return session

    def ready(self, **kwargs):
        session = self.session(**kwargs)
        session.finish_baseline(1)
        session.drained(1, 0, 10)
        return session

    def test_clean_cut_then_mutation_and_ack(self):
        session = self.ready()
        self.assertEqual(session.state, 'watching')
        exports = session.receive(event(), 1, 1, lambda *args: 7)
        self.assertEqual(session.state, 'pending')
        session.drained(1, 1, 10)
        self.assertEqual(session.state, 'pending')
        session.applied(exports[0].sequence)
        self.assertEqual(session.state, 'pending')
        session.drained(1, 1, 10)
        self.assertEqual(session.state, 'watching')

    def test_dirty_inventory_never_calls_admission(self):
        for finish_first in (False, True):
            session = self.session()
            if finish_first: session.finish_baseline(1)
            def forbidden(*args): self.fail('dirty bootstrap must not probe')
            with self.assertRaisesRegex(f.Gap, 'bootstrap_dirty'):
                session.receive(event(), 1, 1, forbidden)
            self.assertEqual(session.state, 'deferred')
            self.assertEqual(session.pending, [])
            with self.assertRaises(f.Gap): session.drained(1, 1, 10)

    def test_cut_and_source_identity_failures(self):
        session = self.session()
        with self.assertRaisesRegex(f.Gap, 'baseline_not_finished'): session.drained(1, 0, 10)
        session = self.ready()
        with self.assertRaisesRegex(f.Gap, 'source_sequence_gap'):
            session.receive(event(), 1, 2, lambda *args: 7)
        session = self.ready()
        with self.assertRaisesRegex(f.Gap, 'drain_identity_invalid'): session.drained(2, 0, 10)
        session = self.ready()
        with self.assertRaisesRegex(f.Gap, 'drain_identity_invalid'): session.drained(1, 1, 10)

    def test_backpressure_and_out_of_order_ack(self):
        session = self.ready(max_pending=1)
        session.receive(event(), 1, 1, lambda *args: 7)
        with self.assertRaisesRegex(f.Gap, 'pending_limit'):
            session.receive(event(), 1, 2, lambda *args: 7)
        self.assertEqual(session.pending, [])
        session = self.ready()
        session.receive(event(), 1, 1, lambda *args: 7)
        with self.assertRaisesRegex(f.Gap, 'apply_sequence_gap'): session.applied(2)

    def test_inventory_blocks_freshness_until_completion_and_cut(self):
        session = self.ready()
        session.inventory_started(42, 1)
        session.drained(1, 0, 10)
        self.assertEqual(session.state, 'pending')
        session.inventory_finished(42, 1)
        self.assertEqual(session.state, 'pending')
        session.drained(1, 0, 10)
        self.assertEqual(session.state, 'watching')
        session = self.ready(max_pending=1)
        session.inventory_started(1, 1)
        with self.assertRaisesRegex(f.Gap, 'inventory_limit'): session.inventory_started(2, 1)
        self.assertEqual(session.inventory_work, set())

    def test_outside_churn_and_failure_after_ready(self):
        session = self.ready()
        self.assertEqual(session.receive(event(), 1, 1, lambda *args: None), ())
        self.assertEqual(session.source_sequence, 1)
        with self.assertRaisesRegex(f.Gap, 'queue_overflow'):
            session.receive(event(f.OVERFLOW, []), 1, 2, lambda *args: None)
        self.assertEqual(session.state, 'deferred')
        session = self.ready()
        with self.assertRaisesRegex(f.Gap, 'source_progress_timeout'): session.check_lease(13)
        self.assertEqual(session.state, 'deferred')


class BootstrapSketchFixtures(unittest.TestCase):
    inside = f.Handle(b'12345678', 1, b'inside')

    def session(self, **limits):
        session = f.BootstrapSession(1, bootstrap_changes=f.BootstrapChanges(**limits))
        session.progress(10)
        return session

    def test_outside_churn_does_not_publish_or_reject_clean_baseline(self):
        session = self.session()
        outside = event(records=[info(2, b'outside', b'outside-secret'), info(1)])
        self.assertEqual(session.receive(outside, 1, 1, lambda *args: self.fail('no early lookup')), ())
        self.assertEqual((session.state, session.pending), ('reconciling', []))
        session.qualify_baseline([self.inside], lambda handle: 0 if handle == self.inside else None, lambda: None)
        session.finish_baseline(1)
        self.assertEqual(session.state, 'reconciling')
        session.drained(1, 1, 10)
        self.assertEqual(session.state, 'watching')
        self.assertIsNone(session.bootstrap_changes)

    def test_dirty_parent_detected_after_its_identity_becomes_known(self):
        session = self.session()
        session.receive(event(), 1, 1, lambda *args: self.fail('no early lookup'))
        with self.assertRaisesRegex(f.Gap, 'bootstrap_dirty'):
            session.qualify_baseline([self.inside], lambda handle: 0, lambda: None)
        self.assertEqual(session.state, 'deferred')
        self.assertIsNone(session.bootstrap_changes)

    def test_event_during_validation_cannot_slip_past_scanned_parent(self):
        session = self.session()
        def incoming():
            session.receive(event(), 1, 1, lambda *args: self.fail('no metadata lookup'))
        with self.assertRaisesRegex(f.Gap, 'bootstrap_dirty'):
            session.qualify_baseline([self.inside], lambda handle: 0 if handle == self.inside else None, incoming)
        self.assertEqual(session.state, 'deferred')

    def test_root_move_detected_even_when_event_parents_are_outside(self):
        session = self.session()
        data = event(f.RENAME | f.ONDIR, [info(10, b'outside-a'), info(12, b'outside-b'), info(1, b'inside')])
        session.receive(data, 1, 1, lambda *args: None)
        with self.assertRaisesRegex(f.Gap, 'bootstrap_dirty'):
            session.qualify_baseline([self.inside], lambda handle: 0, lambda: None)

    def test_unqualified_collision_and_observation_budget_never_certify_fresh(self):
        session = self.session()
        with self.assertRaisesRegex(f.Gap, 'bootstrap_not_qualified'):
            session.finish_baseline(1)
        session = self.session(bytes_limit=1)
        session.bootstrap_changes.bits[:] = b'\xff'
        with self.assertRaisesRegex(f.Gap, 'bootstrap_dirty'):
            session.qualify_baseline([self.inside], lambda handle: None, lambda: None)
        session = self.session(max_observations=1)
        with self.assertRaisesRegex(f.Gap, 'bootstrap_change_budget'):
            session.receive(event() * 2, 1, 1, lambda *args: None)
        self.assertEqual(session.state, 'deferred')


if __name__ == '__main__': unittest.main()
