"""Filesystem journal boundaries, bounded replay and owner-private custody."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fsearch_catalog_journal import CatalogJournal, JournalError
import fsearch_catalog_journal as journal_module
import fsearch_service as service

class JournalBoundaries(unittest.TestCase):
    def setUp(self):
        previous_umask=os.umask(0o077);self.addCleanup(os.umask,previous_umask)
        self.temp=tempfile.TemporaryDirectory(prefix='fsearch-journal-');self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name);self.work.chmod(0o700)
        self.directory=service.PrivateDirectory(self.work/'q.sock');self.addCleanup(self.directory.close)
        self.log=CatalogJournal(self.directory,'base-1');self.addCleanup(self.log.close)
    def request(self,sequence):
        return {'schema_version':1,'request_id':'journal','op':'catalog_apply','expected_snapshot_id':'base-1','sequence':sequence,'parent_id':0,'entry_kind':1,'name_b64':'cmF3Lf8='}
    def test_fsynced_chain_reopens_and_preserves_bytes(self):
        self.log.append(self.request(1),7);self.log.append(self.request(2),8)
        self.log.close();self.log=CatalogJournal(self.directory,'base-1');self.addCleanup(self.log.close)
        records=list(self.log.records());self.assertEqual([r['entry_id'] for r in records],[7,8]);self.assertEqual(self.log.count,2)
        self.assertEqual((self.work/'q.sock.catalog-journal').stat().st_mode&0o777,0o600)
    def test_rollover_preserves_sequence_and_publishes_matching_pair(self):
        self.log.append(self.request(1),7)
        checkpoint=self.log.prepare_checkpoint()
        fd=self.directory.open_private(checkpoint,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        os.write(fd,b'owned native checkpoint already validated');os.fsync(fd);os.close(fd)
        (self.work/(checkpoint+'.metadata')).write_bytes(b'validated metadata')
        self.log=self.log.rollover(checkpoint,1);self.addCleanup(self.log.close)
        self.assertEqual(self.log.count,1);self.assertEqual(list(self.log.records()),[])
        self.log.append(self.request(2),8)
        self.log.close();reopened=CatalogJournal(self.directory,'base-1');self.addCleanup(reopened.close)
        self.assertEqual(reopened.checkpoint_name,checkpoint)
        self.assertEqual(reopened.base_sequence,1)
        self.assertEqual([r['request']['sequence'] for r in reopened.records()],[2])
        self.assertTrue((self.work/'q.sock.catalog-journal').exists())

    def test_replacement_stage_keeps_both_source_identities_recoverable(self):
        self.log.append(self.request(1),7)
        self.log=self.log.rollover(self.checkpoint(),1);self.addCleanup(self.log.close)
        name=self.log.prepare_checkpoint()
        (self.work/name).write_bytes(b'validated replacement checkpoint')
        (self.work/(name+'.metadata')).write_bytes(b'validated replacement metadata')
        staged=self.log.prepare_replacement('base-2',name);self.addCleanup(staged.close)
        previous=CatalogJournal(self.directory,'base-1');self.addCleanup(previous.close)
        successor=CatalogJournal(self.directory,'base-2');self.addCleanup(successor.close)
        self.assertEqual(previous.count,1);self.assertEqual(successor.count,0)
        self.assertNotEqual(previous.checkpoint_name,successor.checkpoint_name)
    def test_rollover_replays_mutations_accepted_after_capture(self):
        self.log.append(self.request(1),7);name=self.checkpoint()
        self.log.append(self.request(2),8)
        self.log=self.log.rollover(name,1);self.addCleanup(self.log.close)
        self.assertEqual(self.log.base_sequence,1);self.assertEqual(self.log.count,2)
        self.assertEqual([r['entry_id'] for r in self.log.records()],[8])
        self.log.append(self.request(3),9)
    def checkpoint(self):
        name=self.log.prepare_checkpoint()
        fd=self.directory.open_private(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        os.write(fd,b'validated owned checkpoint');os.fsync(fd);os.close(fd)
        (self.work/(name+'.metadata')).write_bytes(b'validated metadata')
        return name
    def test_rollover_manifest_failure_retains_old_accepted_log(self):
        self.log.append(self.request(1),7);name=self.checkpoint()
        original=journal_module.os.rename
        def fail_manifest(source,target,**fields):
            if target.endswith('.catalog-generation'):raise OSError('injected manifest failure')
            return original(source,target,**fields)
        with mock.patch.object(journal_module.os,'rename',fail_manifest):
            with self.assertRaises(OSError):self.log.rollover(name,1)
        reopened=CatalogJournal(self.directory,'base-1');self.addCleanup(reopened.close)
        self.assertIsNone(reopened.checkpoint_name)
        self.assertEqual([r['entry_id'] for r in reopened.records()],[7])
    def test_manifest_directory_fsync_failure_recovers_matching_new_pair(self):
        self.log.append(self.request(1),7);name=self.checkpoint()
        original_rename,original_fsync=journal_module.os.rename,journal_module.os.fsync
        renamed=False
        def rename(source,target,**fields):
            nonlocal renamed
            result=original_rename(source,target,**fields)
            if target.endswith('.catalog-generation'):renamed=True
            return result
        def fsync(fd):
            if renamed and fd==self.directory.fd:raise OSError('injected manifest directory fsync failure')
            return original_fsync(fd)
        with mock.patch.object(journal_module.os,'rename',rename),mock.patch.object(journal_module.os,'fsync',fsync):
            with self.assertRaises(OSError):self.log.rollover(name,1)
        reopened=CatalogJournal(self.directory,'base-1');self.addCleanup(reopened.close)
        self.assertEqual(reopened.base_sequence,1);self.assertEqual(reopened.count,1)
        self.assertEqual(list(reopened.records()),[]);self.assertEqual(reopened.checkpoint_name,name)
    def test_repeated_rollover_bounds_retained_names_and_resets_record_budget(self):
        for sequence in range(1,7):
            self.log.append(self.request(sequence),sequence+7)
            self.log=self.log.rollover(self.checkpoint(),sequence);self.addCleanup(self.log.close)
            self.assertEqual(self.log.count,sequence)
            self.assertEqual(list(self.log.records()),[])
        names=list(self.work.iterdir())
        self.assertEqual(len(names),11) # legacy log/cursor + two checkpoint/log/cursor slots + manifest

    def test_sequence_gap_refused_before_write(self):
        before=(self.work/'q.sock.catalog-journal').read_bytes()
        with self.assertRaisesRegex(JournalError,'journal_sequence'):self.log.append(self.request(2),7)
        self.assertEqual((self.work/'q.sock.catalog-journal').read_bytes(),before)
    def test_header_identity_cannot_be_rebound(self):
        with self.assertRaisesRegex(JournalError,'journal_snapshot_conflict'):CatalogJournal(self.directory,'other-base')
    def test_corrupt_and_truncated_chain_fail_before_replay(self):
        self.log.append(self.request(1),7);path=self.work/'q.sock.catalog-journal';original=path.read_bytes()
        for damaged in (original[:-1], original[:-1]+bytes([original[-1]^1])):
            path.write_bytes(damaged)
            with self.assertRaisesRegex(JournalError,'journal_corrupt|journal_invalid'):CatalogJournal(self.directory,'base-1')
        path.write_bytes(original)
    def test_partial_header_and_oversized_frame_rejected(self):
        path=self.work/'q.sock.catalog-journal';original=path.read_bytes()
        for damaged in (b'FSCJ0001\x00',b'FSCJ0001\xff\xff\xff\xff'):
            path.write_bytes(damaged)
            with self.assertRaises(JournalError):CatalogJournal(self.directory,'base-1')
        path.write_bytes(original)
    def test_fsync_failure_does_not_advance_acknowledged_cursor(self):
        with mock.patch.object(journal_module.os,'fsync',side_effect=OSError('injected fsync failure')):
            with self.assertRaisesRegex(OSError,'injected fsync failure'):self.log.append(self.request(1),7)
        self.assertEqual(self.log.count,0)
    def test_record_budget_refuses_before_dispatch(self):
        with mock.patch.object(journal_module,'MAX_RECORDS',2):
            self.log.append(self.request(1),7);self.log.append(self.request(2),8)
            before=(self.work/'q.sock.catalog-journal').read_bytes()
            with self.assertRaisesRegex(JournalError,'journal_checkpoint_required'):self.log.reserve(self.request(3))
            self.assertEqual((self.work/'q.sock.catalog-journal').read_bytes(),before)
    def test_partial_tail_preserves_previously_acknowledged_view(self):
        self.log.append(self.request(1),7)
        original=journal_module.os.write
        def partial(fd,data):
            original(fd,data[:2]);raise OSError('injected partial append')
        with mock.patch.object(journal_module.os,'write',partial):
            with self.assertRaises(OSError):self.log.append(self.request(2),8)
        self.log.close()
        reopened=CatalogJournal(self.directory,'base-1');self.addCleanup(reopened.close)
        self.assertEqual([r['entry_id'] for r in reopened.records()],[7])
        self.assertTrue(reopened.tail_uncommitted)
        with self.assertRaisesRegex(JournalError,'journal_tail_uncommitted'):reopened.reserve(self.request(2))

    def test_partial_append_is_preserved_and_not_committed(self):
        original=journal_module.os.write
        def partial(fd,data):
            original(fd,data[:2]);raise OSError('injected partial append')
        with mock.patch.object(journal_module.os,'write',partial):
            with self.assertRaises(OSError):self.log.append(self.request(1),7)
        self.log.close()
        reopened=CatalogJournal(self.directory,'base-1');self.addCleanup(reopened.close)
        self.assertEqual(list(reopened.records()),[])
        self.assertTrue(reopened.tail_uncommitted)

if __name__=='__main__':unittest.main()
