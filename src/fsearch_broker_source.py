"""Private descriptor handoff and bounded event-source adapter.

No group creation, marks, privilege acquisition or root access lives here.
Ordinary-descriptor tests establish transport/wiring, not fanotify authority.
"""
import array
import fcntl
import os
import socket
import struct
import time

from fsearch_fanotify_events import BootstrapSession, Gap, CREATE, DELETE, RENAME, ONDIR

HANDOFF = struct.Struct('!8sQ32sQQ')
MAGIC = b'FSBRK002'


def _peer(channel, uid):
    if channel.family != socket.AF_UNIX or channel.type & 0xf != socket.SOCK_SEQPACKET:
        raise Gap('handoff_transport')
    _, actual, _ = struct.unpack('3i', channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if type(uid) is not int or actual != uid:
        raise Gap('handoff_peer')


def _identity(generation, token, root_identity):
    if type(generation) is not int or not 1 <= generation < 2**64 or not isinstance(token, bytes) or len(token) != 32 or not isinstance(root_identity, tuple) or len(root_identity) != 2 or any(type(value) is not int or not 0 <= value < 2**64 for value in root_identity):
        raise Gap('handoff_identity')
    return HANDOFF.pack(MAGIC, generation, token, *root_identity)


def send_source(channel, fd, *, peer_uid, generation, token, root_identity=(0, 0)):
    """Transfer one descriptor; caller retains ownership until explicit close."""
    _peer(channel, peer_uid)
    payload = _identity(generation, token, root_identity)
    if channel.sendmsg([payload], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))]) != len(payload):
        raise Gap('handoff_short_write')


def receive_source(channel, *, peer_uid, generation, token, root_identity=(0, 0), source_kind='fixture'):
    """Authenticate and adopt exactly one nonblocking descriptor, CLOEXEC.

    A malformed packet closes every received descriptor, including excess ones.
    Production handoff requires pinned root identity and a fanotify descriptor.
    Fixture mode accepts ordinary descriptors; it is explicitly unqualified.
    """
    _peer(channel, peer_uid)
    expected = _identity(generation, token, root_identity)
    if source_kind not in ('fixture', 'fanotify') or source_kind == 'fanotify' and (not all(root_identity) or peer_uid != 0):
        raise Gap('handoff_authority')
    descriptors = []
    try:
        data, controls, flags, _ = channel.recvmsg(HANDOFF.size + 1, socket.CMSG_SPACE(16 * array.array('i').itemsize), socket.MSG_CMSG_CLOEXEC)
        unexpected = False
        for level, kind, body in controls:
            if (level, kind) != (socket.SOL_SOCKET, socket.SCM_RIGHTS):
                unexpected = True
                continue
            values = array.array('i')
            values.frombytes(body[:len(body) - len(body) % values.itemsize])
            descriptors.extend(values)
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or unexpected or data != expected or len(descriptors) != 1:
            raise Gap('handoff_invalid')
        fd = descriptors[0]
        if not fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_NONBLOCK:
            raise Gap('source_blocking')
        if os.get_inheritable(fd):
            raise Gap('source_inheritable')
        if source_kind == 'fanotify' and os.readlink('/proc/self/fd/' + str(fd)) != 'anon_inode:[fanotify]':
            raise Gap('source_kind')
        descriptors.clear()
        return fd
    finally:
        for fd in descriptors:
            os.close(fd)


class SourceReader:
    """Own a nonblocking source; only EAGAIN establishes a drain cut.

    Each pump has byte/batch bounds, including dropped outside events, and
    yields between reads/applications at its cooperative time bound. Individual
    admission/application callbacks retain their own containment deadlines.
    Reaching any work bound leaves coverage pending, never falsely drained.
    Only bounded admitted exports can carry over; no raw batch is retained.
    Admission remains an explicit
    security dependency supplied by the contained broker, not this reader.
    """
    def __init__(self, fd, session, *, max_batches=16, max_bytes=1048576, max_seconds=.05):
        if not isinstance(session, BootstrapSession) or type(max_batches) is not int or max_batches < 1 or type(max_bytes) is not int or max_bytes < 65536 or not 0 < max_seconds <= 1:
            raise ValueError('reader_configuration')
        if not fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_NONBLOCK:
            raise Gap('source_blocking')
        os.set_inheritable(fd, False)
        self.fd = fd
        self.session = session
        self.max_batches = max_batches
        self.max_bytes = max_bytes
        self.max_seconds = max_seconds

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def pump(self, validate, apply):
        if self.fd is None:
            self.session.fail('source_closed')
        started = time.monotonic()
        consumed = 0
        def apply_pending():
            while self.session.pending:
                if time.monotonic() - started >= self.max_seconds:
                    return False
                export = self.session.pending[0]
                try:
                    batch=getattr(apply,'batch',None)
                    count=batch(self.session.pending[:8],started+self.max_seconds) if batch else 1
                    if not batch:apply(export)
                    if type(count) is not int or not 1<=count<=min(8,len(self.session.pending)):
                        raise Gap('catalog_batch_protocol')
                except Exception:
                    self.session.fail('catalog_apply_failed')
                for export in self.session.pending[:count]:
                    self.session.applied(export.sequence)
                # Application is real progress through already admitted data.
                # It renews liveness, but only a later EAGAIN can prove drain.
                self.session.progress(time.monotonic())
            return True
        # Reading begins a new observation interval, so old drain proof cannot
        # certify events not yet read. Bootstrap remains reconciling.
        if self.session.state == 'watching':
            self.session.state = 'pending'
        try:
            if not apply_pending():
                return False
            for _ in range(self.max_batches):
                if consumed >= self.max_bytes or time.monotonic() - started >= self.max_seconds:
                    return False
                try:
                    data = os.read(self.fd, min(65536, self.max_bytes - consumed))
                except BlockingIOError:
                    now = time.monotonic()
                    self.session.progress(now)
                    # Bootstrap checks may drain while inventory/building is
                    # incomplete. That observation cannot publish watching.
                    if self.session.baseline_finished:
                        self.session.drained(self.session.filter.generation, self.session.source_sequence, now)
                    return True
                except InterruptedError:
                    return False
                if not data:
                    self.session.fail('source_eof')
                consumed += len(data)
                self.session.progress(time.monotonic())
                self.session.receive(data, self.session.filter.generation, self.session.source_sequence + 1, validate)
                if not apply_pending():
                    return False
            return False
        except Gap:
            raise
        except OSError:
            self.session.fail('source_read_failed')


class CatalogSink:
    """Apply admitted namespace sides through the production catalog client.

    Parent paths are cached catalog paths, never filesystem authority. The
    reader's admission callback must validate containment before these reach
    this sink. Directory insertion requires a bounded inventory implementation;
    absence/failure defers, rather than publishing an incomplete fresh view.
    """
    def __init__(self, client, session, root, parent_paths, inventory=None, entry_kind=None):
        self.client, self.session, self.root = client, session, root
        self.parent_paths = parent_paths
        self.inventory = inventory
        self.entry_kind = entry_kind

    def _side(self, side):
        role, parent_id, name = side
        relative = self.parent_paths.get(parent_id)
        if relative is None or not isinstance(relative, bytes) or relative.startswith(b'/') or any(part in (b'.', b'..') for part in relative.split(b'/')):
            raise Gap('catalog_parent_missing')
        parent_path = self.root + (b'/' + relative if relative else b'')
        parent = self.client.lookup(parent_path)
        if not parent or parent['entry_id'] != parent_id or parent['entry_kind'] != 2:
            raise Gap('catalog_parent_changed')
        return role, parent_id, name, parent_path + b'/' + name

    def _remove(self, located):
        if located:
            self.client.apply(located['parent_id'], b'', located['entry_id'], 0)
            if hasattr(self.parent_paths, 'retire'):
                self.parent_paths.retire(located['entry_id'])
                return
            relative = self.parent_paths.pop(located['entry_id'], None)
            if relative is not None:
                for entry, path in list(self.parent_paths.items()):
                    if path.startswith(relative + b'/'):
                        del self.parent_paths[entry]

    def __call__(self, export):
        sides = {side[0]: self._side(side) for side in export.sides}
        kind = 2 if export.mask & ONDIR else 1
        operation = export.mask & (CREATE | DELETE | RENAME)
        old = sides.get(10 if operation == RENAME else 2)
        new = sides.get(12 if operation == RENAME else 2)
        if operation == DELETE:
            self._remove(self.client.lookup(old[3]))
            return
        previous = self.client.lookup(old[3]) if operation == RENAME and old else None
        if operation == RENAME and new is None:
            self._remove(previous)
            return
        if new is None:
            raise Gap('catalog_namespace_missing')
        _, parent, name, path = new
        existing = self.client.lookup(path)
        if self.entry_kind is not None:
            eligible = self.entry_kind(parent, name, export.generation)
            if eligible == 0:
                self._remove(previous)
                if existing and (not previous or existing['entry_id'] != previous['entry_id']):
                    self._remove(existing)
                return
            if eligible != kind:
                raise Gap('catalog_kind_changed')
        if previous and previous['entry_kind'] != kind:
            raise Gap('catalog_kind_changed')
        if existing and (not previous or existing['entry_id'] != previous['entry_id']):
            if operation == CREATE and existing['entry_kind'] == kind:
                return
            self._remove(existing)
        entry = self.client.apply(parent, name, previous['entry_id'] if previous else None, kind)
        if kind == 2:
            # Refresh relative ancestry for every admitted directory descendant
            # after a rename; retired IDs are not reused by the native catalog.
            if previous:
                if hasattr(self.parent_paths, 'reparent'):
                    self.parent_paths.reparent(entry, parent, name)
                    return
                old_relative = old[3][len(self.root) + 1:]
                new_relative = path[len(self.root) + 1:]
                for directory_id, relative in list(self.parent_paths.items()):
                    if relative == old_relative or relative.startswith(old_relative + b'/'):
                        self.parent_paths[directory_id] = new_relative + relative[len(old_relative):]
            else:
                if not hasattr(self.parent_paths, 'admitted'):
                    self.parent_paths[entry] = path[len(self.root) + 1:]
                self.session.inventory_started(entry, export.generation)
                if self.inventory is None:
                    raise Gap('directory_inventory_unavailable')
                self.inventory(entry, path)
                self.session.inventory_finished(entry, export.generation)

    def batch(self, exports, deadline):
        """Group only independent regular entries; acknowledge after commit.

        Preparation yields at the source turn bound. Namespace dependencies,
        directory work, replacements and exclusions retain the single path.
        """
        limit=min(8,getattr(self.client,'batch_remaining',0),len(exports))
        mutations=[];names=set();count=0
        for export in exports[:limit]:
            if mutations and time.monotonic()>=deadline:break
            operation=export.mask & (CREATE|DELETE|RENAME)
            if export.mask & ONDIR or operation not in (CREATE,RENAME):break
            sides={side[0]:self._side(side) for side in export.sides}
            old=sides.get(10) if operation==RENAME else None
            new=sides.get(12 if operation==RENAME else 2)
            if new is None:break
            paths={side[3] for side in (old,new) if side is not None}
            if paths & names or old is not None and old[3]==new[3]:break
            _,parent,name,path=new
            if self.entry_kind is None or self.entry_kind(parent,name,export.generation)!=1:break
            previous=self.client.lookup(old[3]) if old else None
            existing=self.client.lookup(path)
            if previous and previous['entry_kind']!=1 or existing:break
            mutations.append((parent,name,previous['entry_id'] if previous else None,1))
            names.update(paths);count+=1
        if mutations:
            self.client.apply_batch(mutations)
            return count
        self(exports[0])
        return 1


class CatalogBroker:
    """Run one bounded source turn, exposing sticky gaps in actual query JSON."""
    def __init__(self, reader, client, root, validate, parent_paths, inventory=None, entry_kind=None):
        self.reader, self.client, self.root, self.validate = reader, client, root, validate
        self.sink = CatalogSink(client, reader.session, root, parent_paths, inventory, entry_kind)
        self.oldest = None

    def pump(self):
        session = self.reader.session
        if self.oldest is None:
            self.oldest = int(time.time() * 1000)
        self.client.coverage('pending' if session.baseline_finished else 'reconciling', self.root,
                             session.filter.sequence, self.oldest, reason='source_read')
        try:
            drained = self.reader.pump(self.validate, self.sink)
            if drained and session.state == 'watching':
                self.client.last_reconciled = int(time.time() * 1000)
                self.oldest = None
            self.client.coverage(session.state, self.root, session.filter.sequence,
                                 self.oldest,
                                 reason='source_drained' if drained else 'source_budget')
            return drained
        except Gap as error:
            self.client.coverage('deferred', self.root, session.filter.sequence, reason=str(error))
            raise
