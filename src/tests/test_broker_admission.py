"""Directory identity/lifetime tests; native owned fixtures run separately."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fsearch_fanotify_events import Gap, Handle
from fsearch_broker_admission import DirectoryMap, ContainedAdmission


def handle(value, fsid=b'12345678', kind=1):
    return Handle(fsid, kind, value)


class MapTests(unittest.TestCase):
    def setUp(self):
        self.map = DirectoryMap()
        self.map.add(handle(b'root'), 0, None, b'')

    def tearDown(self):
        self.map.close()

    def test_zero_based_root_and_raw_parent_linked_rename(self):
        self.map.add(handle(b'ancestor'), 1, 0, b'old')
        self.map.add(handle(b'child'), 2, 1, b'raw-\xff')
        self.assertEqual(self.map.get(0), b'')
        self.assertEqual(self.map.admitted(handle(b'child')), 2)
        self.map.reparent(1, 0, b'new')
        self.assertEqual(self.map.get(2), b'new/raw-\xff')
        self.assertIsNone(self.map.admitted(handle(b'child', fsid=b'87654321')))

    def test_recursive_retirement_revokes_descendants(self):
        self.map.add(handle(b'ancestor'), 1, 0, b'old')
        self.map.add(handle(b'child'), 2, 1, b'child')
        self.map.retire(1)
        self.assertIsNone(self.map.admitted(handle(b'ancestor')))
        self.assertIsNone(self.map.admitted(handle(b'child')))
        self.assertIsNone(self.map.get(2))
        self.assertEqual(self.map.count, 1)

    def test_cycles_collisions_and_entry_reuse_rejected(self):
        self.map.add(handle(b'ancestor'), 1, 0, b'old')
        self.map.add(handle(b'child'), 2, 1, b'child')
        with self.assertRaisesRegex(Gap, 'map_cycle'):
            self.map.reparent(1, 2, b'loop')
        with self.assertRaisesRegex(Gap, 'map_identity_collision'):
            self.map.add(handle(b'child'), 3, 0, b'other')
        with self.assertRaisesRegex(Gap, 'map_identity_changed'):
            self.map.add(handle(b'new-handle'), 2, 1, b'child')
        self.assertEqual(self.map.count, 3)
        self.assertEqual(self.map.get(2), b'old/child')

    def test_configuration_map_budget_and_invalid_names(self):
        with self.assertRaises(ValueError): DirectoryMap(max_directories=True)
        self.map.max_directories = 1
        with self.assertRaisesRegex(Gap, 'map_limit'):
            self.map.add(handle(b'child'), 1, 0, b'child')
        for name in (b'', b'..', b'a/b', b'null\0'):
            with self.assertRaisesRegex(Gap, 'map_entry_invalid'):
                self.map.add(handle(b'child'), 1, 0, name)

    def test_unknown_parent_does_not_call_boundary(self):
        class Forbidden:
            def __getattr__(self, name):
                raise AssertionError('unknown handle must not be resolved')
        admission = ContainedAdmission(Forbidden(), None, None, b'/owned', 1, self.map)
        self.assertIsNone(admission.validate(handle(b'outside'), 1))
        with self.assertRaisesRegex(Gap, 'root_generation_changed'):
            admission.validate(handle(b'root'), 2)


if __name__ == '__main__': unittest.main()
