"""Bounded owner-private accepted-mutation journal, bound to one base identity.

Streaming replay validates the whole log before any worker mutation. No indexed
root access, filename resolution, observation or automatic repair lives here.
"""
import hashlib
import json
import os
import struct
import uuid

MAGIC = b'FSCJ0001'
MAX_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 1024
MAX_FRAME = 8192
MAX_BATCH_RECORDS = 8


class JournalError(ValueError):
    pass


class CatalogJournal:
    def __init__(self, directory, snapshot_id, *, generation=None):
        self.directory = directory
        self.snapshot_id = snapshot_id
        self.slot = None
        self.base_sequence = 0
        self.checkpoint_name = None
        self.manifest_name = directory.name + '.catalog-generation'
        selected = generation if generation is not None else self.read_generation()
        if selected is not None:
            self.slot, self.base_sequence = selected['slot'], selected['sequence']
            self.checkpoint_name = directory.name + '.catalog-checkpoint-' + self.slot
        self.name = directory.name + '.catalog-journal' + ('-' + self.slot if self.slot else '')
        self.fd = None
        self.count = self.base_sequence
        self.committed_bytes = 0
        self.committed_chain = bytes(32)
        self.committed_count = self.base_sequence
        self.tail_uncommitted = False
        self.chain = bytes(32)
        try:
            self.fd = directory.open_private(self.name, os.O_RDWR | os.O_APPEND)
        except FileNotFoundError:
            if selected is not None and generation is None:
                raise JournalError('journal_generation_missing')
            fd = directory.open_private(self.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            try:
                self.write_all(fd, MAGIC + self.frame(self.header()))
                os.fsync(fd)
                os.fsync(directory.fd)
                self.publish_commit(os.fstat(fd).st_size, self.base_sequence, bytes(32))
            finally:
                os.close(fd)
            self.fd = directory.open_private(self.name, os.O_RDWR | os.O_APPEND)
        try:
            if os.fstat(self.fd).st_nlink != 1:
                raise JournalError('journal_custody')
            self.read_commit()
            self.verify()
        except BaseException:
            self.close()
            raise

    @classmethod
    def checkpoint_selection(cls, directory, snapshot_id, *, fallback=False):
        probe = cls.__new__(cls)
        probe.directory, probe.snapshot_id = directory, snapshot_id
        probe.manifest_name = directory.name + '.catalog-generation'
        generation = probe.read_generation(fallback=fallback)
        if generation is None:
            return None
        return directory.name + '.catalog-checkpoint-' + generation['slot'], generation['sequence']

    def header(self):
        result = {'snapshot_id': self.snapshot_id}
        if self.slot is not None:
            result['base_sequence'] = self.base_sequence
        return result

    def read_generation(self, *, fallback=False):
        try:
            fd = self.directory.open_private(self.manifest_name, os.O_RDONLY)
        except FileNotFoundError:
            return None
        try:
            if os.fstat(fd).st_nlink != 1: raise JournalError('journal_custody')
            data = os.read(fd, 2049)
            envelope = json.loads(data)
            if len(data) > 2048 or not isinstance(envelope, dict):
                raise JournalError('journal_generation_invalid')
            if set(envelope) == {'schema_version', 'generations'} and type(envelope['schema_version']) is int and envelope['schema_version'] in (2, 3):
                records = envelope['generations']
                if not isinstance(records, list) or len(records) != 2:
                    raise JournalError('journal_generation_invalid')
            else:
                records = [envelope]
            for record in records:
                if not isinstance(record, dict) or set(record) != {'schema_version', 'snapshot_id', 'slot', 'sequence'}:
                    raise JournalError('journal_generation_invalid')
                if type(record['schema_version']) is not int or record['schema_version'] != 1 or not isinstance(record['snapshot_id'], str) or not record['snapshot_id'] or len(record['snapshot_id']) > 256 or record['slot'] not in ('a', 'b') or type(record['sequence']) is not int or not 0 <= record['sequence'] < 2**64:
                    raise JournalError('journal_generation_invalid')
            same_identity_history = envelope.get('schema_version') == 3
            if len({record['slot'] for record in records}) != len(records) or (not same_identity_history and len({record['snapshot_id'] for record in records}) != len(records)) or (same_identity_history and (len({record['snapshot_id'] for record in records}) != 1 or records[0]['sequence'] < records[1]['sequence'])):
                raise JournalError('journal_generation_invalid')
            matching = [record for record in records if record['snapshot_id'] == self.snapshot_id]
            if not matching or (not same_identity_history and len(matching) != 1):
                raise JournalError('journal_generation_invalid')
            if fallback:
                return matching[1] if same_identity_history else None
            return matching[0]
        except (ValueError, TypeError) as error:
            raise JournalError('journal_generation_invalid') from error
        finally:
            os.close(fd)

    def remove_inactive(self, name):
        try:
            fd = self.directory.open_private(name, os.O_RDONLY)
        except FileNotFoundError:
            return
        try:
            if os.fstat(fd).st_nlink != 1: raise JournalError('journal_custody')
        finally:
            os.close(fd)
        os.unlink(name, dir_fd=self.directory.fd)
        os.fsync(self.directory.fd)

    def prepare_checkpoint(self):
        # Two fixed slots bound retention, including interrupted publications.
        # Only the inactive owned cache is reusable; the selected pair stays intact.
        slot = 'b' if self.slot == 'a' else 'a'
        name = self.directory.name + '.catalog-checkpoint-' + slot
        self.remove_inactive(name)
        self.remove_inactive(name + '.metadata')
        return name

    def prepare_replacement(self, snapshot_id, checkpoint_name):
        if self.checkpoint_name is None or self.tail_uncommitted or snapshot_id == self.snapshot_id:
            raise JournalError('journal_checkpoint_required')
        slot = 'b' if self.slot == 'a' else 'a'
        if checkpoint_name != self.directory.name + '.catalog-checkpoint-' + slot:
            raise JournalError('journal_checkpoint_name')
        self.checkpoint_custody(checkpoint_name)
        name = self.directory.name + '.catalog-journal-' + slot
        self.remove_inactive(name)
        self.remove_inactive(name + '.commit')
        previous = {'schema_version': 1, 'snapshot_id': self.snapshot_id, 'slot': self.slot, 'sequence': self.base_sequence}
        generation = {'schema_version': 1, 'snapshot_id': snapshot_id, 'slot': slot, 'sequence': 0}
        next_log = CatalogJournal(self.directory, snapshot_id, generation=generation)
        try:
            # The accepted service state selects the identity. Before and after
            # its atomic publication, a complete matching private pair exists.
            self.publish_json(self.manifest_name, {'schema_version': 2, 'generations': [previous, generation]})
        except BaseException:
            next_log.close()
            raise
        return next_log

    def checkpoint_custody(self, checkpoint_name):
        for name in (checkpoint_name, checkpoint_name + '.metadata'):
            fd = self.directory.open_private(name, os.O_RDONLY)
            try:
                if os.fstat(fd).st_nlink != 1: raise JournalError('journal_custody')
                os.fsync(fd)
            finally:
                os.close(fd)

    def rollover(self, checkpoint_name, sequence):
        if self.tail_uncommitted or not self.base_sequence <= sequence <= self.count:
            raise JournalError('journal_checkpoint_sequence')
        slot = 'b' if self.slot == 'a' else 'a'
        if checkpoint_name != self.directory.name + '.catalog-checkpoint-' + slot:
            raise JournalError('journal_checkpoint_name')
        self.checkpoint_custody(checkpoint_name)
        name = self.directory.name + '.catalog-journal-' + slot
        self.remove_inactive(name)
        self.remove_inactive(name + '.commit')
        generation = {'schema_version': 1, 'snapshot_id': self.snapshot_id, 'slot': slot, 'sequence': sequence}
        next_log = CatalogJournal(self.directory, self.snapshot_id, generation=generation)
        try:
            # Copy only post-capture accepted records. The new pair is unpublished,
            # so one log fsync/cursor publication commits the bounded batch.
            for record in self.records():
                if record['request']['sequence'] <= sequence:
                    continue
                frame = self.frame(record)
                chain = hashlib.sha256(next_log.chain + frame).digest()
                if next_log.count - next_log.base_sequence >= MAX_RECORDS or os.fstat(next_log.fd).st_size + len(frame) + 32 > MAX_BYTES:
                    raise JournalError('journal_byte_budget')
                self.write_all(next_log.fd, frame + chain)
                next_log.count += 1
                next_log.chain = chain
            os.fsync(next_log.fd)
            size = os.fstat(next_log.fd).st_size
            next_log.publish_commit(size, next_log.count, next_log.chain)
            next_log.committed_bytes, next_log.committed_count, next_log.committed_chain = size, next_log.count, next_log.chain
            previous = {'schema_version': 1, 'snapshot_id': self.snapshot_id, 'slot': self.slot, 'sequence': self.base_sequence}
            manifest = {'schema_version': 3, 'generations': [generation, previous]} if self.slot is not None else generation
            self.publish_json(self.manifest_name, manifest)
        except BaseException:
            next_log.close()
            raise
        self.close()
        return next_log

    def publish_json(self, name, value):
        body = json.dumps(value, separators=(',', ':')).encode()
        temporary = name + '.' + uuid.uuid4().hex
        fd = self.directory.open_private(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            self.write_all(fd, body)
            os.fsync(fd)
            os.rename(temporary, name, src_dir_fd=self.directory.fd, dst_dir_fd=self.directory.fd)
            os.fsync(self.directory.fd)
        finally:
            os.close(fd)
            try: os.unlink(temporary, dir_fd=self.directory.fd)
            except FileNotFoundError: pass

    def publish_commit(self, size, sequence, chain):
        self.publish_json(self.name + '.commit', {'snapshot_id': self.snapshot_id, 'bytes': size,
                                                  'sequence': sequence, 'chain': chain.hex()})

    def read_commit(self):
        try:
            fd = self.directory.open_private(self.name + '.commit', os.O_RDONLY)
            try:
                if os.fstat(fd).st_nlink != 1: raise JournalError('journal_custody')
                body = os.read(fd, 1025)
            finally:
                os.close(fd)
            record = json.loads(body)
            if len(body) > 1024 or not isinstance(record, dict) or set(record) != {'snapshot_id', 'bytes', 'sequence', 'chain'} :
                raise JournalError('journal_commit_invalid')
            if record['snapshot_id'] != self.snapshot_id: raise JournalError('journal_snapshot_conflict')
            if type(record['bytes']) is not int or not len(MAGIC) < record['bytes'] <= MAX_BYTES or type(record['sequence']) is not int or not self.base_sequence <= record['sequence'] <= self.base_sequence + MAX_RECORDS:
                raise JournalError('journal_commit_invalid')
            chain = bytes.fromhex(record['chain'])
            if len(chain) != 32: raise JournalError('journal_commit_invalid')
            self.committed_bytes, self.committed_count, self.committed_chain = record['bytes'], record['sequence'], chain
        except JournalError:
            raise
        except (OSError, ValueError, TypeError) as error:
            raise JournalError('journal_commit_invalid') from error

    @staticmethod
    def write_all(fd, data):
        while data:
            written = os.write(fd, data)
            if written <= 0:
                raise JournalError('journal_short_write')
            data = data[written:]

    @staticmethod
    def frame(record):
        data = json.dumps(record, separators=(',', ':'), sort_keys=True).encode()
        if len(data) > MAX_FRAME:
            raise JournalError('journal_frame_budget')
        return struct.pack('!I', len(data)) + data

    def records(self):
        actual_size = os.fstat(self.fd).st_size
        size = self.committed_bytes
        self.tail_uncommitted = actual_size > size
        if actual_size < size or actual_size > MAX_BYTES or os.pread(self.fd, len(MAGIC), 0) != MAGIC:
            raise JournalError('journal_invalid')
        offset = len(MAGIC)
        chain = bytes(32)
        number = 0
        while offset < size:
            prefix = os.pread(self.fd, 4, offset)
            if len(prefix) != 4:
                raise JournalError('journal_truncated')
            length = struct.unpack('!I', prefix)[0]
            if not 0 < length <= MAX_FRAME:
                raise JournalError('journal_frame_budget')
            data = os.pread(self.fd, length, offset + 4)
            if len(data) != length:
                raise JournalError('journal_truncated')
            offset += 4 + length
            try:
                record = json.loads(data)
            except (ValueError, UnicodeError):
                raise JournalError('journal_corrupt') from None
            if number == 0:
                if record != self.header():
                    raise JournalError('journal_snapshot_conflict')
            else:
                check = os.pread(self.fd, 32, offset)
                chain = hashlib.sha256(chain + prefix + data).digest()
                if check != chain:
                    raise JournalError('journal_corrupt')
                offset += 32
                if number > MAX_RECORDS or not isinstance(record, dict) or set(record) != {'request', 'entry_id'}:
                    raise JournalError('journal_invalid')
                request = record['request']
                if not isinstance(request, dict) or request.get('sequence') != self.base_sequence + number or request.get('expected_snapshot_id') != self.snapshot_id:
                    raise JournalError('journal_sequence')
                if type(record['entry_id']) is not int or not 0 <= record['entry_id'] < 2**32:
                    raise JournalError('journal_invalid')
                yield record
            number += 1
        if number == 0:
            raise JournalError('journal_truncated')
        if self.base_sequence + number - 1 != self.committed_count or chain != self.committed_chain:
            raise JournalError('journal_commit_invalid')
        self.count = self.base_sequence + number - 1
        self.chain = chain

    def verify(self):
        for _ in self.records():
            pass

    def checkpoint_required(self):
        return self.count - self.base_sequence >= MAX_RECORDS

    def reserve(self, request):
        if self.tail_uncommitted or os.fstat(self.fd).st_size != self.committed_bytes:
            raise JournalError('journal_tail_uncommitted')
        if self.checkpoint_required():
            raise JournalError('journal_checkpoint_required')
        # Reserve worst-case numeric entry ID before dispatching a mutation.
        size = len(self.frame({'request': request, 'entry_id': 2**32 - 1})) + 32
        if os.fstat(self.fd).st_size + size > MAX_BYTES:
            raise JournalError('journal_byte_budget')

    def append(self, request, entry_id):
        self.append_batch([(request, entry_id)])

    def reserve_batch(self, requests):
        if not 1 <= len(requests) <= MAX_BATCH_RECORDS:
            raise JournalError('journal_batch_limit')
        self.reserve(requests[0])
        if self.count - self.base_sequence + len(requests) > MAX_RECORDS:
            raise JournalError('journal_checkpoint_required')
        size = os.fstat(self.fd).st_size
        for offset, request in enumerate(requests, 1):
            if request['sequence'] != self.count + offset:
                raise JournalError('journal_sequence')
            size += len(self.frame({'request': request, 'entry_id': 2**32 - 1})) + 32
        if size > MAX_BYTES:
            raise JournalError('journal_byte_budget')

    def append_batch(self, records):
        self.reserve_batch([request for request, entry in records])
        chain = self.chain
        for request, entry_id in records:
            frame = self.frame({'request': request, 'entry_id': entry_id})
            chain = hashlib.sha256(chain + frame).digest()
            self.write_all(self.fd, frame + chain)
        os.fsync(self.fd)
        size = os.fstat(self.fd).st_size
        count = self.count + len(records)
        self.publish_commit(size, count, chain)
        self.committed_bytes, self.committed_count, self.committed_chain = size, count, chain
        self.count = count
        self.chain = chain

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
