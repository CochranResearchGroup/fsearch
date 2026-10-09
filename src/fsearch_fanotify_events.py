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
        # Coalesced/mixed namespace operations cannot be guessed safely.
        operation = mask & (CREATE | DELETE | RENAME)
        if operation not in (CREATE, DELETE, RENAME):
            raise Gap('ambiguous_operation')
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
        required = {10, 12} if operation == RENAME else {2}
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
                admitted = []
                for side in event.sides:
                    try:
                        parent_id = validate(side.parent, generation)
                    except Exception:
                        raise Gap('admission_failed') from None
                    if parent_id is not None:
                        if type(parent_id) is not int or parent_id < 1:
                            raise Gap('admission_invalid')
                        admitted.append((side.role, parent_id, side.name))
                if admitted:
                    if len(result) >= self.max_exports:
                        raise Gap('export_limit')
                    result.append(Export(self.sequence + len(result) + 1, generation, event.mask, tuple(admitted)))
            self.sequence += len(result)
            return tuple(result)
        except Gap as error:
            self.fail(str(error))
        except Exception:
            self.fail('admission_failed')
