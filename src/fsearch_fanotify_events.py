"""Bounded fanotify ABI decoder and export filter; no observation syscalls.

Not connected to a production broker. Admission must validate live containment;
a handle map alone is insufficient. Exceptions deliberately contain no raw data.
"""
from dataclasses import dataclass
import struct
import math

META = struct.Struct('=IBBHQii')
INFO = struct.Struct('=BBH')
HANDLE = struct.Struct('=Ii')
CREATE, DELETE, RENAME, OVERFLOW = 0x100, 0x200, 0x10000000, 0x4000
ONDIR = 0x40000000
SUPPORTED = CREATE | DELETE | RENAME | ONDIR
NAME_TYPES = (2, 10, 12)


class Gap(ValueError):
    """An identifier-free reason invalidating source coverage."""


@dataclass(frozen=True, repr=False)
class Handle:
    fsid: bytes
    kind: int
    opaque: bytes


@dataclass(frozen=True, repr=False)
class Side:
    role: int
    parent: Handle
    name: bytes


@dataclass(frozen=True, repr=False)
class Event:
    mask: int
    sides: tuple
    target: Handle | None


def decode(data, *, max_bytes=65536, max_events=1024):
    """Decode one complete read batch atomically, never a partial valid prefix."""
    if not isinstance(data, bytes) or len(data) > max_bytes:
        raise Gap('batch_limit')
    events = []
    offset = 0
    while offset < len(data):
        if len(events) >= max_events:
            raise Gap('event_limit')
        if len(data) - offset < META.size:
            raise Gap('metadata_truncated')
        size, version, _, header, mask, fd, _ = META.unpack_from(data, offset)
        if version != 3 or header != META.size or size < header or size > len(data) - offset:
            raise Gap('metadata_invalid')
        if fd != -1:
            raise Gap('unexpected_descriptor')
        if mask & OVERFLOW:
            raise Gap('queue_overflow')
        if mask & ~SUPPORTED or not mask & (CREATE | DELETE | RENAME):
            raise Gap('unsupported_mask')
        # Decode merged masks so outside churn can be admitted/discarded first.
        # Ambiguous admitted operations remain a sticky gap in ExportFilter.
        operation = mask & (CREATE | DELETE | RENAME)
        end = offset + size
        cursor = offset + header
        sides, target, seen = [], None, set()
        while cursor < end:
            if end - cursor < INFO.size:
                raise Gap('info_truncated')
            role, _, length = INFO.unpack_from(data, cursor)
            if length < 20 or length > end - cursor:
                raise Gap('info_length')
            if role not in (1, *NAME_TYPES) or role in seen:
                raise Gap('unsupported_or_duplicate_info')
            seen.add(role)
            count, kind = HANDLE.unpack_from(data, cursor + 12)
            if count == 0 or count > 128 or 20 + count > length:
                raise Gap('handle_length')
            handle_end = cursor + 20 + count
            handle = Handle(data[cursor + 4:cursor + 12], kind, data[cursor + 20:handle_end])
            remainder = data[handle_end:cursor + length]
            if role == 1:
                if remainder:
                    raise Gap('target_trailing_bytes')
                target = handle
            else:
                terminator = remainder.find(b'\0')
                if terminator <= 0 or any(remainder[terminator + 1:]):
                    raise Gap('name_encoding')
                name = remainder[:terminator]
                if len(name) > 255 or b'/' in name or name in (b'.', b'..'):
                    raise Gap('name_invalid')
                sides.append(Side(role, handle, name))
            cursor += length
        required = {10, 12} if operation & RENAME else {2}
        if {side.role for side in sides} != required or target is None:
            raise Gap('namespace_identity_missing')
        events.append(Event(mask, tuple(sides), target))
        offset = end
    return tuple(events)


@dataclass(frozen=True, repr=False)
class Export:
    sequence: int
    generation: int
    mask: int
    # Each tuple: role, validated stable parent entry ID, raw basename.
    sides: tuple


class ExportFilter:
    """Bounded stateless batch admission plus sticky failure/lease state.

    validate(parent, generation) returns an admitted stable parent ID or None.
    It MUST freshly check ancestry/identity; this class performs no filesystem
    probes and cannot establish that security invariant itself.
    """
    def __init__(self, generation, *, max_exports=1024, lease_seconds=2.0):
        if type(generation) is not int or generation < 1 or max_exports < 1 or lease_seconds <= 0:
            raise ValueError('configuration_invalid')
        self.generation = generation
        self.max_exports = max_exports
        self.lease_seconds = lease_seconds
        self.sequence = 0
        self.reason = None
        self.last_progress = None
        self.root_handle = None

    def fail(self, reason):
        self.reason = self.reason or reason
        raise Gap(self.reason) from None

    def progress(self, now):
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            self.fail('clock_invalid')
        if self.reason:
            raise Gap(self.reason)
        if self.last_progress is not None and now < self.last_progress:
            self.fail('clock_regressed')
        self.last_progress = now

    def check_lease(self, now):
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            self.fail('clock_invalid')
        if self.reason:
            raise Gap(self.reason)
        if self.last_progress is None or now - self.last_progress > self.lease_seconds:
            self.fail('source_progress_timeout')
        if now < self.last_progress:
            self.fail('clock_regressed')

    def consume(self, data, generation, validate):
        if self.reason:
            raise Gap(self.reason)
        if generation != self.generation:
            self.fail('root_generation_changed')
        try:
            events = decode(data)
            result = []
            for event in events:
                if self.root_handle is not None and event.target == self.root_handle and event.mask & ONDIR and event.mask & (RENAME | DELETE):
                    raise Gap('root_identity_changed')
                admitted = []
                for side in event.sides:
                    try:
                        parent_id = validate(side.parent, generation)
                    except Exception:
                        raise Gap('admission_failed') from None
                    if parent_id is not None:
                        # Native catalog IDs are zero-based: the root is ID 0.
                        if type(parent_id) is not int or parent_id < 0:
                            raise Gap('admission_invalid')
                        admitted.append((side.role, parent_id, side.name))
                if admitted:
                    if event.mask & (CREATE | DELETE | RENAME) not in (CREATE, DELETE, RENAME):
                        raise Gap('ambiguous_operation')
                    if len(result) >= self.max_exports:
                        raise Gap('export_limit')
                    result.append(Export(self.sequence + len(result) + 1, generation, event.mask, tuple(admitted)))
            self.sequence += len(result)
            return tuple(result)
        except Gap as error:
            self.fail(str(error))
        except Exception:
            self.fail('admission_failed')


class BootstrapChanges:
    """Bounded ephemeral dirty-set sketch; no names or handle list retained.

    Every namespace parent and removed/renamed directory target contributes
    keyed bitmap positions. Query only admitted handles once inventory exists.
    Collisions may reject a clean baseline; they cannot certify a dirty one.
    Outside events contribute bits, never replayable identifiers or raw records.
    """
    def __init__(self, *, bytes_limit=1048576, max_observations=1000000):
        import os
        if type(bytes_limit) is not int or not 1 <= bytes_limit <= 1048576 or type(max_observations) is not int or max_observations < 1:
            raise ValueError('bootstrap_sketch_configuration')
        self.bits = bytearray(bytes_limit)
        self.key = os.urandom(32)
        self.max_observations = max_observations
        self.observations = 0
        self.admitted = None
        self.qualified = False

    def positions(self, handle):
        import hashlib
        digest = hashlib.blake2b(handle.fsid + struct.pack('!i', handle.kind) + handle.opaque,
                                 key=self.key, digest_size=16).digest()
        return tuple(value % (len(self.bits) * 8) for value in struct.unpack('!4I', digest))

    def changed(self, handle):
        return all(self.bits[position // 8] & (1 << (position % 8)) for position in self.positions(handle))

    def observe(self, events):
        for event in events:
            handles = [side.parent for side in event.sides]
            if event.mask & ONDIR and event.mask & (RENAME | DELETE):
                handles.append(event.target)
            for handle in handles:
                self.observations += 1
                if self.observations > self.max_observations:
                    raise Gap('bootstrap_change_budget')
                if self.admitted is not None and self.admitted(handle) is not None:
                    raise Gap('bootstrap_dirty')
                for position in self.positions(handle):
                    self.bits[position // 8] |= 1 << (position % 8)

    def qualify(self, handles, admitted, source_check):
        self.admitted = admitted
        for index, handle in enumerate(handles):
            if self.changed(handle):
                raise Gap('bootstrap_dirty')
            if index % 256 == 0:
                source_check()
        source_check()
        self.qualified = True


class BootstrapSession:
    """Conservative clean-baseline cut and bounded admitted replay controller.

    A source adapter must supply ordered read-batch numbers and drain barriers.
    This controller cannot manufacture a kernel drain proof. Dirty bootstrap is
    rejected instead of retaining filesystem-wide raw events. No automatic retry.
    """
    def __init__(self, generation, *, max_pending=1024, bootstrap_changes=None):
        if type(max_pending) is not int or max_pending < 1:
            raise ValueError('configuration_invalid')
        self.filter = ExportFilter(generation, max_exports=max_pending)
        self.max_pending = max_pending
        self.state = 'reconciling'
        self.source_sequence = 0
        self.pending = []
        self.applied_sequence = 0
        self.baseline_finished = False
        self.inventory_work = set()
        self.bootstrap_changes = bootstrap_changes

    def fail(self, reason):
        self.state = 'deferred'
        self.pending.clear()
        self.inventory_work.clear()
        self.bootstrap_changes = None
        self.filter.fail(reason)

    def receive(self, data, generation, source_sequence, validate):
        if self.state == 'deferred':
            raise Gap(self.filter.reason)
        if type(source_sequence) is not int or source_sequence != self.source_sequence + 1:
            self.fail('source_sequence_gap')
        try:
            # Decode before treating a batch as dirty: retain original gap reason.
            events = decode(data)
            if self.state == 'reconciling' and events:
                if self.bootstrap_changes is None:
                    self.fail('bootstrap_dirty')
                if generation != self.filter.generation:
                    self.fail('root_generation_changed')
                self.bootstrap_changes.observe(events)
                self.source_sequence = source_sequence
                return ()
            exports = self.filter.consume(data, generation, validate)
            if len(exports) + len(self.pending) > self.max_pending:
                self.fail('pending_limit')
            self.pending.extend(exports)
            self.source_sequence = source_sequence
            if self.pending:
                self.state = 'pending'
            return exports
        except Gap as error:
            self.fail(str(error))

    def qualify_baseline(self, handles, admitted, source_check):
        if self.state != 'reconciling' or self.bootstrap_changes is None:
            self.fail('baseline_identity_invalid')
        try:
            self.bootstrap_changes.qualify(handles, admitted, source_check)
        except Gap as error:
            self.fail(str(error))

    def finish_baseline(self, generation):
        if self.state != 'reconciling' or generation != self.filter.generation:
            self.fail('baseline_identity_invalid')
        if self.bootstrap_changes is not None and not self.bootstrap_changes.qualified:
            self.fail('bootstrap_not_qualified')
        self.baseline_finished = True
        if self.bootstrap_changes is not None:
            # Qualification defines the baseline cut; later events are replay,
            # while only a subsequent drain can establish watching.
            self.state = 'pending'

    def drained(self, generation, source_sequence, now):
        if self.state == 'deferred':
            raise Gap(self.filter.reason)
        if generation != self.filter.generation or type(source_sequence) is not int or source_sequence != self.source_sequence:
            self.fail('drain_identity_invalid')
        try:
            self.filter.check_lease(now)
        except Gap as error:
            self.fail(str(error))
        if self.state == 'reconciling' and not self.baseline_finished:
            self.fail('baseline_not_finished')
        if self.pending or self.inventory_work:
            self.state = 'pending'
        else:
            self.state = 'watching'
            self.bootstrap_changes = None

    def applied(self, sequence):
        if self.state == 'deferred':
            raise Gap(self.filter.reason)
        if not self.pending or type(sequence) is not int or sequence != self.pending[0].sequence:
            self.fail('apply_sequence_gap')
        self.pending.pop(0)
        self.applied_sequence = sequence
        # Even after application, a fresh drain proof is required for watching.
        self.state = 'pending'

    def progress(self, now):
        try:
            self.filter.progress(now)
        except Gap as error:
            self.fail(str(error))

    def check_lease(self, now):
        try:
            self.filter.check_lease(now)
        except Gap as error:
            self.fail(str(error))

    def inventory_started(self, token, generation):
        if self.state == 'deferred':
            raise Gap(self.filter.reason)
        if generation != self.filter.generation or type(token) is not int or token < 1 or token in self.inventory_work:
            self.fail('inventory_identity_invalid')
        if len(self.inventory_work) >= self.max_pending:
            self.fail('inventory_limit')
        self.inventory_work.add(token)
        if self.state != 'reconciling':
            self.state = 'pending'

    def inventory_finished(self, token, generation):
        if self.state == 'deferred':
            raise Gap(self.filter.reason)
        if generation != self.filter.generation or token not in self.inventory_work:
            self.fail('inventory_identity_invalid')
        self.inventory_work.remove(token)
        # Completion alone does not prove the source queue is drained.
