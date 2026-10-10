#!/usr/bin/env python3
"""Owner-private FSearch supervisor/client. GPL-2.0-or-later; see COPYING."""
import argparse
import base64
import collections
import fcntl
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
import uuid
from fsearch_catalog_journal import CatalogJournal, JournalError

MAX_FRAME = 65536
MAX_RESPONSE = 1048576
MAX_CONNECTIONS = 16
MAX_QUEUE = 8

def error(code, request_id=None):
    result = {'schema_version': 1, 'status': 'error', 'complete': False, 'error': {'code': code}, 'results': []}
    if request_id is not None: result['request_id'] = request_id
    return result

def encoded(value):
    return (json.dumps(value, separators=(',', ':'), ensure_ascii=True) + '\n').encode()

class BoundaryError(Exception):
    pass

class PrivateDirectory:
    def __init__(self, socket_path):
        path = Path(socket_path)
        if len(os.fsencode(str(path))) >= 104 or not path.name: raise BoundaryError('unsafe_socket')
        self.name = path.name
        self.fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(self.fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            os.close(self.fd); raise BoundaryError('unsafe_directory')
        self.address = f'/proc/self/fd/{self.fd}/{self.name}'
        if len(os.fsencode(self.address)) >= 108:
            os.close(self.fd); raise BoundaryError('unsafe_socket')
        self.lock_fd = None
    def open_private(self, name, flags):
        fd = os.open(name, flags | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600, dir_fd=self.fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            os.close(fd); raise BoundaryError('unsafe_state')
        return fd
    def lock(self):
        self.lock_fd = self.open_private(self.name + '.lock', os.O_RDWR | os.O_CREAT)
        try: fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise BoundaryError('already_running')
    def state(self):
        try: fd = self.open_private(self.name + '.state', os.O_RDONLY)
        except FileNotFoundError: return None
        with os.fdopen(fd, 'rb') as stream:
            raw = stream.read(4097)
        if len(raw) > 4096: raise BoundaryError('unsafe_state')
        try:
            value = json.loads(raw)
            if not isinstance(value, dict): raise ValueError()
            return value
        except (ValueError, UnicodeError): raise BoundaryError('unsafe_state')
    def save(self, value):
        body=encoded(value)
        if len(body)>4096:raise BoundaryError('unsafe_state')
        name = self.name + '.state.' + uuid.uuid4().hex
        fd = self.open_private(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body); stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.name + '.state', src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try: os.unlink(name, dir_fd=self.fd)
            except FileNotFoundError: pass
    def socket_info(self):
        try: info = os.stat(self.name, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError: return None
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise BoundaryError('unsafe_socket')
        return info
    def close(self):
        if self.lock_fd is not None: os.close(self.lock_fd)
        os.close(self.fd)

def identity(pid):
    raw = Path(f'/proc/{pid}/stat').read_text()
    return {'pid': pid, 'start': raw.rsplit(')', 1)[1].split()[19],
            'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}

def proved_absent(record):
    if not record: return True
    try:
        if not isinstance(record, dict) or set(record) != {'pid', 'start', 'boot'}: return False
        if type(record['pid']) is not int or record['pid'] <= 0 or not isinstance(record['start'], str) or not record['start'].isdigit() or not isinstance(record['boot'], str) or len(record['boot']) != 36: return False
        if str(int(record['start'])) != record['start']: return False
        uuid.UUID(record['boot'])
        current = identity(record['pid'])
        return current != record
    except FileNotFoundError as exc: return exc.filename == f"/proc/{record['pid']}/stat"
    except (OSError, ValueError, IndexError, AttributeError): return False

def previous_boot_generation(previous, workers):
    # A verified boot change proves these processes cannot survive in this kernel.
    # Never use PID absence, elapsed time, or partial identity as boot evidence.
    try:
        current = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if str(uuid.UUID(current)) != current: return False
        records = workers + [previous.get('supervisor')]
        boots = set()
        for record in records:
            if not isinstance(record, dict) or set(record) != {'pid', 'start', 'boot'}: return False
            if type(record['pid']) is not int or record['pid'] <= 0: return False
            start = record['start']
            if not isinstance(start, str) or not start.isdigit() or str(int(start)) != start: return False
            boot = record['boot']
            if not isinstance(boot, str) or str(uuid.UUID(boot)) != boot: return False
            boots.add(boot)
        return bool(workers) and len(boots) == 1 and current not in boots
    except (OSError, ValueError, AttributeError): return False

def reconcile(directory, recover=False):
    previous = directory.state()
    if not previous: return
    phase = previous.get('phase')
    if phase not in ('stopped', 'ready', 'starting', 'quarantined'): raise BoundaryError('unsafe_state')
    workers = [previous.get(key) for key in ('worker','candidate_worker','retiring_worker') if previous.get(key) is not None]
    if phase == 'stopped' and workers: raise BoundaryError('quarantined')
    prior_boot = phase != 'stopped' and previous_boot_generation(previous, workers)
    if phase != 'stopped' and not prior_boot and (not workers or any(not proved_absent(worker) for worker in workers)):
        raise BoundaryError('quarantined')
    if phase != 'stopped' and not recover and not prior_boot: raise BoundaryError('quarantined')
    if recover or prior_boot:
        recovered={key:previous[key] for key in ('database','accepted_database','snapshot_id') if key in previous}
        recovered.update({'phase':'stopped','worker':None,'reason':'previous_boot_recovery' if prior_boot and not recover else 'explicit_recovery'})
        directory.save(recovered)

def validate_request(request):
    if not isinstance(request, dict): raise BoundaryError('invalid_request')
    allowed = {'schema_version', 'request_id', 'query', 'extension', 'kind', 'path', 'match_case', 'limit', 'max_candidates', 'max_bytes', 'timeout_ms', 'op', 'expected_database_b64', 'candidate_database_b64', 'expected_snapshot_id', 'sequence', 'entry_id', 'parent_id', 'entry_kind', 'name_b64', 'path_b64', 'coverage'}
    if set(request) - allowed or type(request.get('schema_version')) is not int or request.get('schema_version') != 1: raise BoundaryError('invalid_request')
    request_id = request.get('request_id')
    if not isinstance(request_id, str) or len(request_id.encode('utf-8')) > 64: raise BoundaryError('invalid_request')
    if request.get('op') not in (None, 'query', 'stop', 'replace', 'catalog_apply', 'catalog_lookup', 'catalog_compact', 'catalog_status', 'catalog_coverage'): raise BoundaryError('invalid_request')
    if (request.get('op') or '').startswith('catalog_'):
        op=request['op'];keys={'schema_version','request_id','op','timeout_ms','expected_snapshot_id'}
        if op=='catalog_apply':keys|={'sequence','entry_id','parent_id','entry_kind','name_b64'}
        if op=='catalog_lookup':keys.add('path_b64')
        if op=='catalog_coverage':keys.add('coverage')
        if set(request)-keys:raise BoundaryError('invalid_request')
        expected=request.get('expected_snapshot_id')
        if expected is not None and (not isinstance(expected,str) or not expected or len(expected)>256):raise BoundaryError('invalid_request')
        if op in ('catalog_apply','catalog_compact','catalog_coverage') and expected is None:raise BoundaryError('invalid_request')
        timeout=request.setdefault('timeout_ms',2000)
        if type(timeout) is not int or not 1<=timeout<=10000:raise BoundaryError('invalid_request')
        if op=='catalog_coverage':
            coverage=request.get('coverage')
            keys={'state','root_b64','event_sequence','catalog_sequence','last_reconciled_unix_ms','oldest_unapplied_unix_ms','reason'}
            if not isinstance(coverage,dict) or set(coverage)!=keys or coverage['state'] not in ('reconciling','watching','pending','deferred','offline','stopped'):raise BoundaryError('invalid_request')
            if not isinstance(coverage['reason'],str) or len(coverage['reason'])>128:raise BoundaryError('invalid_request')
            for key in ('event_sequence','catalog_sequence','last_reconciled_unix_ms','oldest_unapplied_unix_ms'):
                value=coverage[key]
                if value is not None and (type(value) is not int or not 0<=value<2**63):raise BoundaryError('invalid_request')
            value=coverage['root_b64']
            if not isinstance(value,str) or len(value)>5464:raise BoundaryError('invalid_request')
            try:raw=base64.b64decode(value,validate=True)
            except ValueError:raise BoundaryError('invalid_request')
            if not raw.startswith(b'/') or len(raw)>4096 or b'\0' in raw:raise BoundaryError('invalid_request')
        if op=='catalog_apply':
            for key,minimum,maximum in (('sequence',1,2**64-1),('parent_id',0,2**32-1),('entry_kind',0,2)):
                value=request.get(key)
                if type(value) is not int or not minimum<=value<=maximum:raise BoundaryError('invalid_request')
            if 'entry_id' in request and (type(request['entry_id']) is not int or not 0<=request['entry_id']<=2**32-1):raise BoundaryError('invalid_request')
            if request['entry_kind']==0 and 'entry_id' not in request:raise BoundaryError('invalid_request')
        if op in ('catalog_apply','catalog_lookup'):
            key='name_b64' if op=='catalog_apply' else 'path_b64';value=request.get(key)
            if not isinstance(value,str) or len(value)>5464:raise BoundaryError('invalid_request')
            try:raw=base64.b64decode(value,validate=True)
            except ValueError:raise BoundaryError('invalid_request')
            if len(raw)>4096 or b'\0' in raw or (op=='catalog_lookup' and (not raw or not raw.startswith(b'/'))) or (op=='catalog_apply' and request['entry_kind'] and not raw):raise BoundaryError('invalid_request')
        return request
    if request.get('op') == 'stop': return request
    if request.get('op') == 'replace':
        if set(request)-{'schema_version','request_id','op','candidate_database_b64','timeout_ms'}:raise BoundaryError('invalid_request')
        value=request.get('candidate_database_b64')
        if not isinstance(value,str) or len(value)>5464:raise BoundaryError('invalid_request')
        try:path=base64.b64decode(value,validate=True)
        except ValueError:raise BoundaryError('invalid_request')
        if not path or len(path)>4096 or b'\0' in path or not path.startswith(b'/'):raise BoundaryError('invalid_request')
        timeout=request.setdefault('timeout_ms',2000)
        if type(timeout) is not int or not 1<=timeout<=10000:raise BoundaryError('invalid_request')
        return request
    if 'expected_database_b64' in request:
        value = request['expected_database_b64']
        if not isinstance(value, str) or len(value) > 5464: raise BoundaryError('invalid_request')
        try: expected = base64.b64decode(value, validate=True)
        except ValueError: raise BoundaryError('invalid_request')
        if not expected or len(expected) > 4096 or b'\0' in expected: raise BoundaryError('invalid_request')
    for key, maximum in (('query', 4096), ('extension', 512)):
        value = request.get(key)
        if key == 'extension' and value is None: request[key] = None; continue
        if not isinstance(value, str) or '\0' in value or len(value.encode('utf-8')) > maximum: raise BoundaryError('invalid_request')
        request[key] = value
    defaults = {'kind': 'all', 'path': False, 'match_case': False, 'limit': 100, 'max_candidates': 500000, 'max_bytes': MAX_RESPONSE, 'timeout_ms': 2000}
    for key, value in defaults.items(): request.setdefault(key, value)
    if request['kind'] not in ('all', 'files', 'folders'): raise BoundaryError('invalid_request')
    if type(request['path']) is not bool or type(request['match_case']) is not bool: raise BoundaryError('invalid_request')
    for key, low, high in (('limit', 1, 1000), ('max_candidates', 1, 500000), ('max_bytes', 512, MAX_RESPONSE), ('timeout_ms', 1, 10000)):
        if type(request[key]) is not int or not low <= request[key] <= high: raise BoundaryError('invalid_request')
    return request

def worker_startup_timeout():
    try:
        milliseconds = int(os.environ.get('FSEARCH_WORKER_STARTUP_TIMEOUT_MS', '2000'))
    except ValueError:
        raise BoundaryError('invalid_request') from None
    if not 1 <= milliseconds <= 30000: raise BoundaryError('invalid_request')
    return milliseconds / 1000

def worker_limits():
    for key, ceiling in ((resource.RLIMIT_AS, 2048*1024*1024), (resource.RLIMIT_CORE, 0)):
        soft, hard = resource.getrlimit(key)
        limit = ceiling if hard == resource.RLIM_INFINITY else min(hard, ceiling)
        resource.setrlimit(key, (limit, limit))

class Supervisor:
    def __init__(self, directory, database, catalog_journal=False):
        self.catalog_journal_enabled = catalog_journal
        self.journal = self.replay = self.replay_record = None
        self.journal_failure = None
        self.checkpoint_action = None
        self.internal_checkpoint = False
        self.checkpoint_poll_after = 0
        self.worker_checkpoint_sequence = None
        self.checkpoint_fallback = False
        self.checkpoint_baseline = False
        self.startup_exhausted = None
        self.recovery_gap = None
        self.recovered_sequence = 0
        self.incremental_coverage = None
        self.coverage_deadline = 0
        self.startup_timeout = worker_startup_timeout()
        self.directory, self.database = directory, database
        self.selector = selectors.DefaultSelector()
        self.clients = {}
        self.queue = collections.deque()
        self.active = None
        self.worker = None
        self.record = None
        self.worker_ready = False
        self.worker_read = bytearray()
        self.worker_write = b''
        self.start_deadline = 0
        self.next_start = 0
        self.stranded = None
        self.quarantined = False
        self.candidate = None
        self.pending_replacement = None
        self.candidate_record = None
        self.candidate_stranded = None
        self.retiring_record = None
        self.retiring_stranded = None
        previous=directory.state() or {}
        self.worker_database = database
        self.accepted_identity = None
        if previous.get('database')==os.path.abspath(database) and previous.get('accepted_database') is not None:
            accepted=previous['accepted_database']
            if not isinstance(accepted,str) or not os.path.isabs(accepted) or '\0' in accepted or len(os.fsencode(accepted))>4096:raise BoundaryError('unsafe_state')
            self.worker_database=accepted
            self.accepted_identity=previous.get('snapshot_id')
        self.stopping = False
        self.save('stopped', 'initialized')
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        existing = directory.socket_info()
        if existing: os.unlink(directory.name, dir_fd=directory.fd)
        previous = os.umask(0o077)
        try: self.listener.bind(directory.address)
        finally: os.umask(previous)
        self.socket_inode = directory.socket_info().st_ino
        self.listener.listen(MAX_CONNECTIONS); self.listener.setblocking(False)
        self.selector.register(self.listener, selectors.EVENT_READ, 'listener')
        for sig in (signal.SIGINT, signal.SIGTERM): signal.signal(sig, lambda *_: setattr(self, 'stopping', True))
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    def replay_next(self):
        try:
            record = next(self.replay)
        except StopIteration:
            self.replay = self.replay_record = None
            self.worker_ready = True
            self.save('ready', 'catalog_replayed')
            return
        request = validate_request(dict(record['request']))
        body = base64.b64decode(request['name_b64'])
        sequence = request['sequence']
        command = 0x101 if 'entry_id' in request else 0x100
        words = (command, request['entry_kind'], request['parent_id'], request.get('entry_id', 0), sequence >> 32, sequence & 0xffffffff, len(body))
        self.replay_record = record
        self.worker_write = struct.pack('!7I', *words) + body
        self.selector.register(self.worker.stdin, selectors.EVENT_WRITE, 'worker_write')

    def checkpoint_command(self, phase, name, sequence, client=None):
        self.checkpoint_action = {'phase': phase, 'name': name, 'sequence': sequence, 'client': client}
        self.send_checkpoint(0x106)

    def send_checkpoint(self, command):
        action = self.checkpoint_action
        body = os.fsencode(f'/proc/{os.getpid()}/fd/{self.directory.fd}/{action["name"]}') if command in (0x105, 0x106) else b''
        self.internal_checkpoint = True
        self.worker_write = struct.pack('!7I', command, 0, 0, 0, 0, 0, len(body)) + body
        self.selector.register(self.worker.stdin, selectors.EVENT_WRITE, 'worker_write')

    def finish_checkpoint(self, payload):
        action = self.checkpoint_action
        phase = action['phase']
        self.internal_checkpoint = False
        if payload.get('snapshot_id') != self.accepted_identity or payload.get('status') == 'error':
            self.journal_failure = 'catalog_checkpoint_invalid' if phase == 'recover' else 'catalog_journal_write_failed'
            self.checkpoint_action = None
            self.abort_worker('catalog_checkpoint_failed')
            return
        if phase == 'recover':
            if payload.get('status') != 'catalog_restored' or payload.get('sequence') != action['sequence']:
                self.journal_failure = 'catalog_checkpoint_invalid'
                self.abort_worker('catalog_checkpoint_invalid')
                return
            self.checkpoint_action = None
            self.recovered_sequence = action['sequence']
            self.recover_catalog(restored=True)
            return
        if phase == 'compact_start':
            if payload.get('status') != 'catalog_compacting':
                self.abort_worker('worker_protocol_failed'); return
            self.active = None
            action['phase'] = 'compact'
            if action['client'] is not None: self.reply(action['client'], payload)
            action['client'] = None
        elif phase == 'compact':
            if payload.get('status') != 'catalog_status':
                self.abort_worker('worker_protocol_failed'); return
            if not payload.get('building'):
                if payload.get('deferred_reason'):
                    self.journal_failure = 'catalog_journal_write_failed'
                    self.abort_worker('catalog_checkpoint_failed'); return
                try:
                    action['name'] = self.journal.prepare_checkpoint()
                except (JournalError, BoundaryError, OSError):
                    self.journal_failure = 'catalog_journal_write_failed'
                    self.abort_worker('catalog_checkpoint_failed'); return
                action['sequence'] = payload['sequence']
                action['phase'] = 'write_start'
                self.send_checkpoint(0x105)
                return
        elif phase == 'write_start':
            if payload.get('status') != 'catalog_checkpointing' or payload.get('checkpoint_sequence') != action['sequence']:
                self.abort_worker('worker_protocol_failed'); return
            action['phase'] = 'poll'
        elif phase == 'poll':
            if payload.get('checkpoint_sequence') != action['sequence'] or payload.get('status') not in ('catalog_checkpointing', 'catalog_checkpointed'):
                self.abort_worker('worker_protocol_failed'); return
            if payload['status'] == 'catalog_checkpointed':
                try:
                    self.journal = self.journal.rollover(action['name'], action['sequence'])
                    self.recovered_sequence = self.journal.count
                except (JournalError, BoundaryError, OSError, ValueError):
                    # Reopen the selected pair after ambiguous manifest publication;
                    # never retry a rename merely because the acknowledgement failed.
                    self.journal_failure = 'catalog_journal_write_failed'
                    self.abort_worker('catalog_checkpoint_publication_failed'); return
                self.checkpoint_action = None
                if self.pending_replacement is not None:
                    client = self.pending_replacement; self.pending_replacement = None
                    self.start_candidate(client)
                    return
                if self.journal.checkpoint_required():
                    self.checkpoint_action = {'phase': 'compact_start', 'name': None, 'sequence': None, 'client': None}
                    self.send_checkpoint(0x102)
                return
        else:
            self.abort_worker('worker_protocol_failed'); return
        self.checkpoint_poll_after = time.monotonic() + .05

    def recover_catalog(self, restored=False):
        if not restored:
            self.recovered_sequence = 0
            if self.journal_failure != 'catalog_checkpoint_invalid':
                try:
                    selected = CatalogJournal.checkpoint_selection(self.directory, self.accepted_identity)
                    if selected is not None:
                        name, sequence = selected
                        self.checkpoint_command('recover', name, sequence)
                        return
                except (JournalError, BoundaryError, OSError, ValueError):
                    self.journal_failure = 'catalog_checkpoint_invalid'

        self.recovery_gap = 'catalog_recovered_source_gap'
        if self.checkpoint_fallback:
            self.journal_failure = self.recovery_gap = 'catalog_checkpoint_fallback'
            self.worker_ready = True
            self.save('ready', self.recovery_gap)
            return
        if self.journal_failure and self.journal_failure != 'catalog_journal_write_failed':
            self.recovery_gap = self.journal_failure
            self.worker_ready = True
            self.save('ready', self.recovery_gap)
            return
        try:
            self.journal = CatalogJournal(self.directory, self.accepted_identity)
            self.journal_failure = None
            if self.journal.tail_uncommitted: self.recovery_gap = 'catalog_journal_tail_uncommitted'
            # Validate protocol records before exposing any partially replayed view.
            for record in self.journal.records():
                request = validate_request(dict(record['request']))
                if request.get('op') != 'catalog_apply':
                    raise JournalError('journal_invalid')
            self.replay = self.journal.records()
            self.replay_next()
        except (JournalError, BoundaryError, OSError, ValueError):
            if self.journal: self.journal.close()
            self.journal = self.replay = self.replay_record = None
            self.journal_failure = self.recovery_gap = 'catalog_journal_invalid'
            self.worker_ready = True
            self.save('ready', self.recovery_gap)

    def save(self, phase, reason=None):
        if phase=='stopped' and (self.candidate_record or self.retiring_record):self.quarantined=True
        self.directory.save({'phase': 'quarantined' if self.quarantined else phase, 'worker': self.record, 'candidate_worker': self.candidate_record, 'retiring_worker': self.retiring_record, 'supervisor': identity(os.getpid()), 'database': os.path.abspath(self.database), 'accepted_database': os.path.abspath(self.worker_database), 'snapshot_id': self.accepted_identity, 'reason': reason})
    def close_client(self, client):
        if self.pending_replacement is client: self.pending_replacement = None
        sock = client['socket']
        if self.candidate and self.candidate['client'] is client:self.abort_candidate('cancelled', reply=False)
        if client.get('shutdown'): self.stopping = True
        self.clients.pop(sock.fileno(), None)
        try: self.selector.unregister(sock)
        except KeyError: pass
        sock.close()
        try: self.queue.remove(client)
        except ValueError: pass
        if self.active is client:
            self.active = None
            self.abort_worker('cancelled')
    def reply(self, client, payload):
        if client['socket'].fileno() < 0: return
        request = client.get('request') or {}
        payload['request_id'] = request.get('request_id')
        if request.get('op') in (None,'query') and self.incremental_coverage is not None:
            coverage=dict(self.incremental_coverage)
            if coverage['state'] in ('watching','pending') and time.monotonic()>self.coverage_deadline:
                coverage.update(state='deferred',reason='watcher_lease_expired')
            payload['incremental_coverage']=coverage
        if self.catalog_journal_enabled:
            if payload.get('status') == 'catalog_status' and self.checkpoint_action is not None:
                payload['building'] = True
            payload['durable'] = self.journal is not None and self.journal_failure is None and payload.get('status') in ('catalog_applied', 'replaced', 'catalog_checkpointed', 'catalog_status', 'catalog_located', 'catalog_missing', 'ok', 'truncated')
            if request.get('op') in (None, 'query') and self.recovery_gap:
                roots = payload.get('snapshot', {}).get('roots', [])
                if roots:
                    root = roots[0]
                    encoded_root = root.get('path_bytes_base64') or base64.b64encode(os.fsencode(root['path'])).decode()
                    payload['incremental_coverage'] = {'state': 'deferred', 'root_b64': encoded_root,
                        'event_sequence': 0, 'catalog_sequence': self.recovered_sequence,
                        'last_reconciled_unix_ms': None, 'oldest_unapplied_unix_ms': None,
                        'reason': self.recovery_gap}
        body = encoded(payload)
        if len(body) > request.get('max_bytes', MAX_RESPONSE): body = encoded(error('response_size_limit', request.get('request_id')))
        client['output'] = body; client['deadline'] = time.monotonic() + 2
        self.selector.modify(client['socket'], selectors.EVENT_WRITE, client)
    def accept(self):
        connection, _ = self.listener.accept(); connection.setblocking(False)
        credentials = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if credentials[1] != os.geteuid(): connection.close(); return
        if len(self.clients) >= MAX_CONNECTIONS:
            try: connection.send(encoded(error('busy')))
            except OSError: pass
            connection.close(); return
        client = {'socket': connection, 'input': bytearray(), 'output': None, 'request': None, 'deadline': time.monotonic() + 2}
        self.clients[connection.fileno()] = client
        self.selector.register(connection, selectors.EVENT_READ, client)
    def read_client(self, client):
        data = client['socket'].recv(MAX_FRAME + 1)
        if not data: self.close_client(client); return
        if client['request'] is not None: self.reply(client, error('invalid_request')); return
        client['input'].extend(data)
        if len(client['input']) > MAX_FRAME: self.reply(client, error('invalid_request')); return
        if b'\n' not in client['input']: return
        try:
            raw = bytes(client['input']); line, trailing = raw.split(b'\n', 1)
            if trailing: raise BoundaryError('invalid_request')
            request = validate_request(json.loads(line))
        except (ValueError, UnicodeError, RecursionError, BoundaryError): self.reply(client, error('invalid_request')); return
        client['request'] = request
        if request.get('op') == 'stop':
            self.reply(client, {'schema_version': 1, 'status': 'stopping', 'complete': False, 'results': []})
            client['shutdown'] = True; return
        if request.get('op') == 'replace':
            self.start_candidate(client);return
        if request.get('expected_database_b64') and base64.b64decode(request['expected_database_b64']) != os.fsencode(os.path.abspath(self.database)):
            self.reply(client, error('snapshot_conflict')); return
        if self.quarantined: self.reply(client, error('quarantined')); return
        if len(self.queue) >= MAX_QUEUE: self.reply(client, error('busy')); return
        client['deadline'] = time.monotonic() + request['timeout_ms']/1000
        self.queue.append(client)
    def spawn(self):
        executable = str(Path(__file__).resolve().with_name('fsearch-worker'))
        command = [executable, self.worker_database, str(os.getpid())]
        self.worker_checkpoint_sequence = None
        if self.catalog_journal_enabled and self.accepted_identity is not None and not self.checkpoint_baseline:
            try:
                selected = CatalogJournal.checkpoint_selection(self.directory, self.accepted_identity, fallback=self.checkpoint_fallback)
                if selected is not None:
                    name, sequence = selected
                    command = [executable, f'/proc/{os.getpid()}/fd/{self.directory.fd}/{name}', str(os.getpid()), '--checkpoint', self.accepted_identity]
                    self.worker_checkpoint_sequence = sequence
            except (JournalError, BoundaryError, OSError, ValueError):
                self.journal_failure = 'catalog_checkpoint_invalid'
                self.checkpoint_fallback = self.checkpoint_baseline = True
        self.worker = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, close_fds=True, preexec_fn=worker_limits)
        try:
            self.record = identity(self.worker.pid)
            self.save('starting')  # Durable identity before the worker may open the snapshot.
            self.worker.stdin.write(b'G'); self.worker.stdin.flush()
        except Exception:
            self.abort_worker('containment_unavailable'); raise
        os.set_blocking(self.worker.stdout.fileno(), False)
        os.set_blocking(self.worker.stdin.fileno(), False)
        self.selector.register(self.worker.stdout, selectors.EVENT_READ, 'worker')
        self.start_deadline = time.monotonic() + self.startup_timeout
        self.worker_read.clear(); self.worker_ready = False
    def abort_worker(self, code):
        if self.catalog_journal_enabled and not self.worker_ready and code in (
                'worker_failed', 'worker_protocol_failed', 'startup_deadline',
                'catalog_replay_failed', 'containment_unavailable', 'deadline'):
            self.startup_exhausted = code
        if self.incremental_coverage is not None:self.incremental_coverage.update(state='deferred',reason='worker_stopped')
        if self.candidate:self.abort_candidate(code)
        if self.pending_replacement is not None:
            client = self.pending_replacement; self.pending_replacement = None
            self.reply(client, error(code))
        if self.worker is None: return
        worker = self.worker
        for stream in (worker.stdin, worker.stdout):
            try: self.selector.unregister(stream)
            except KeyError: pass
        worker.kill()
        try: worker.wait(timeout=0.1); reaped = True
        except subprocess.TimeoutExpired: reaped = False
        worker.stdin.close(); worker.stdout.close()
        self.checkpoint_action = None
        self.internal_checkpoint = False
        self.worker = None; self.worker_ready = False; self.worker_write = b''; self.worker_read.clear()
        if self.journal: self.journal.close()
        self.journal = self.replay = self.replay_record = None
        self.stranded = None if reaped else worker
        self.quarantined = self.quarantined or not reaped
        if reaped: self.record = None
        self.save('quarantined' if not reaped else 'stopped', 'cleanup_unproved' if not reaped else code)
        affected = ([self.active] if self.active is not None else []) + list(self.queue)
        self.active = None; self.queue.clear()
        for client in affected: self.reply(client, error('cleanup_unproved' if not reaped else code))
        self.next_start = time.monotonic() + 1
    def read_worker(self):
        data = os.read(self.worker.stdout.fileno(), 65536)
        if not data: self.abort_worker('worker_failed'); return
        self.worker_read.extend(data)
        if len(self.worker_read) < 4: return
        size = struct.unpack('!I', self.worker_read[:4])[0]
        if size > MAX_RESPONSE or size < 1 or len(self.worker_read) > size + 4:
            self.abort_worker('worker_protocol_failed'); return
        if len(self.worker_read) < size + 4: return
        try: payload = json.loads(self.worker_read[4:])
        except (ValueError, UnicodeError): self.abort_worker('worker_protocol_failed'); return
        self.worker_read.clear()
        if self.checkpoint_action is not None and (self.internal_checkpoint or self.checkpoint_action['phase'] == 'compact_start'):
            self.finish_checkpoint(payload)
            return
        if self.replay_record is not None:
            record = self.replay_record
            if payload.get('status') != 'catalog_applied' or payload.get('sequence') != record['request']['sequence'] or payload.get('entry_id') != record['entry_id']:
                self.journal_failure = 'catalog_replay_failed'
                self.abort_worker('catalog_replay_failed'); return
            self.recovered_sequence = payload['sequence']
            self.replay_record = None
            self.replay_next()
            return
        if not self.worker_ready:
            if payload.get('status') != 'ready':
                if self.worker_checkpoint_sequence is not None:
                    self.journal_failure = 'catalog_checkpoint_invalid'
                    if not self.checkpoint_fallback:
                        self.checkpoint_fallback = True
                    else:
                        self.checkpoint_baseline = True
                elif self.catalog_journal_enabled and self.checkpoint_fallback:
                    self.startup_exhausted = 'catalog_checkpoint_unavailable'
                self.abort_worker(payload.get('error', {}).get('code', 'worker_failed')); return
            if self.catalog_journal_enabled and self.accepted_identity is not None and payload.get('snapshot_id') != self.accepted_identity:
                self.startup_exhausted = 'snapshot_conflict'
                self.abort_worker('snapshot_conflict'); return
            self.accepted_identity = payload.get('snapshot_id')
            if self.catalog_journal_enabled:
                if self.worker_checkpoint_sequence is not None:
                    if payload.get('checkpoint_sequence') != self.worker_checkpoint_sequence:
                        self.journal_failure = 'catalog_checkpoint_invalid'
                        if not self.checkpoint_fallback:
                            self.checkpoint_fallback = True
                        else:
                            self.checkpoint_baseline = True
                        self.abort_worker('catalog_checkpoint_invalid'); return
                    self.recovered_sequence = self.worker_checkpoint_sequence
                    self.recover_catalog(restored=True)
                else:
                    self.recover_catalog()
            else:
                self.worker_ready = True; self.save('ready')
        elif self.active is not None:
            if time.monotonic() >= self.active['deadline']: self.abort_worker('deadline'); return
            client = self.active
            if self.journal is not None and client['request'].get('op') == 'catalog_apply' and payload.get('status') == 'catalog_applied':
                try:
                    self.journal.append(client['request'], payload['entry_id'])
                    self.recovered_sequence = payload['sequence']
                except (JournalError, OSError):
                    self.journal_failure = 'catalog_journal_write_failed'
                    self.abort_worker('catalog_journal_write_failed'); return
            self.active = None; self.reply(client, payload)
        else: self.abort_worker('worker_protocol_failed')
    def start_candidate(self, client):
        if self.quarantined:self.reply(client,error('quarantined'));return
        if self.candidate or self.retiring_record:self.reply(client,error('replacement_busy'));return
        if not self.worker_ready:self.reply(client,error('service_starting'));return
        if self.catalog_journal_enabled:
            if self.journal is None or self.journal_failure or self.journal.tail_uncommitted:
                self.reply(client, error('catalog_journal_invalid')); return
            if self.pending_replacement is not None:
                self.reply(client, error('replacement_busy')); return
            if self.checkpoint_action is not None or self.journal.checkpoint_name is None:
                self.pending_replacement = client
                client['deadline'] = time.monotonic() + client['request']['timeout_ms']/1000
                if self.checkpoint_action is None:
                    self.checkpoint_action = {'phase': 'compact_wait', 'name': None, 'sequence': None, 'client': None}
                return
        path=os.fsdecode(base64.b64decode(client['request']['candidate_database_b64']))
        executable=str(Path(__file__).resolve().with_name('fsearch-worker'))
        try:
            process=subprocess.Popen([executable,path,str(os.getpid())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,close_fds=True,preexec_fn=worker_limits)
            self.candidate={'process':process,'client':client,'path':path,'input':bytearray(),'ready':False,'deadline':time.monotonic()+self.startup_timeout,'phase':'initial','next_poll':0}
            self.candidate_record=identity(process.pid)
            self.save('ready','candidate_loading')
            process.stdin.write(b'G');process.stdin.flush()
            os.set_blocking(process.stdout.fileno(),False)
            self.selector.register(process.stdout,selectors.EVENT_READ,'candidate')
            client['deadline']=time.monotonic()+client['request']['timeout_ms']/1000
        except (OSError,ValueError,BoundaryError):
            if self.candidate:self.abort_candidate('candidate_unavailable')
            else:self.reply(client,error('candidate_unavailable'))
    def abort_candidate(self, code, reply=True):
        candidate=self.candidate
        if not candidate:return
        process=candidate['process']
        try:self.selector.unregister(process.stdout)
        except KeyError:pass
        process.kill()
        try:process.wait(timeout=.1);reaped=True
        except subprocess.TimeoutExpired:reaped=False
        process.stdin.close();process.stdout.close();self.candidate=None
        if reaped:self.candidate_record=None
        else:self.quarantined=True;self.candidate_stranded=process
        self.save('ready' if self.worker_ready else 'stopped',code if reaped else 'cleanup_unproved')
        if reply:self.reply(candidate['client'],error(code if reaped else 'cleanup_unproved'))
    def candidate_checkpoint_command(self, command, phase):
        candidate = self.candidate
        body = os.fsencode(f'/proc/{os.getpid()}/fd/{self.directory.fd}/{candidate["checkpoint_name"]}') if command == 0x105 else b''
        candidate['process'].stdin.write(struct.pack('!7I', command, 0, 0, 0, 0, 0, len(body)) + body)
        candidate['process'].stdin.flush()
        candidate['phase'] = phase

    def poll_candidate_checkpoint(self):
        if self.candidate and self.candidate['phase'] == 'checkpoint_idle' and time.monotonic() >= self.candidate['next_poll']:
            self.candidate_checkpoint_command(0x107, 'checkpoint_poll')

    def read_candidate(self):
        candidate=self.candidate
        data=os.read(candidate['process'].stdout.fileno(),4096)
        if not data:self.abort_candidate('candidate_failed');return
        candidate['input'].extend(data);buffer=candidate['input']
        if len(buffer)<4:return
        size=struct.unpack('!I',buffer[:4])[0]
        if not 1<=size<=4092 or len(buffer)>size+4:self.abort_candidate('worker_protocol_failed');return
        if len(buffer)<size+4:return
        try:payload=json.loads(buffer[4:])
        except (ValueError,UnicodeError):self.abort_candidate('worker_protocol_failed');return
        buffer.clear()
        if not isinstance(payload,dict):self.abort_candidate('worker_protocol_failed');return
        if payload.get('status')=='error':
            failure=payload.get('error')
            self.abort_candidate(failure.get('code','candidate_failed') if isinstance(failure,dict) else 'candidate_failed');return
        phase=candidate['phase']
        if phase=='initial':
            if payload.get('status')!='ready' or not isinstance(payload.get('snapshot_id'),str) or len(payload['snapshot_id'])>256:
                self.abort_candidate('worker_protocol_failed');return
            candidate['identity']=payload['snapshot_id']
            if self.catalog_journal_enabled:
                if candidate['identity']==self.accepted_identity:
                    self.abort_candidate('snapshot_conflict');return
                try:candidate['checkpoint_name']=self.journal.prepare_checkpoint()
                except (JournalError,BoundaryError,OSError):self.abort_candidate('catalog_checkpoint_failed');return
                self.candidate_checkpoint_command(0x105,'checkpoint_start');return
        else:
            if payload.get('snapshot_id')!=candidate['identity'] or payload.get('checkpoint_sequence')!=0 or payload.get('sequence')!=0:
                self.abort_candidate('worker_protocol_failed');return
            if payload.get('status')=='catalog_checkpointing':
                candidate['phase']='checkpoint_idle';candidate['next_poll']=time.monotonic()+.05;return
            if phase!='checkpoint_poll' or payload.get('status')!='catalog_checkpointed':
                self.abort_candidate('worker_protocol_failed');return
        candidate['ready']=True
        self.selector.unregister(candidate['process'].stdout)
    def promote_candidate(self):
        candidate=self.candidate
        if not candidate or not candidate['ready'] or self.active is not None or self.internal_checkpoint or self.checkpoint_action is not None:return
        old_journal = self.journal
        if self.catalog_journal_enabled:
            try:
                next_journal = self.journal.prepare_replacement(candidate['identity'], candidate['checkpoint_name'])
            except (JournalError, BoundaryError, OSError, ValueError):
                self.abort_candidate('catalog_replacement_publication_failed'); return
            self.journal = next_journal
            self.journal_failure = None
            self.recovered_sequence = 0
            self.recovery_gap = 'snapshot_replaced'
        old=self.worker;old_record=self.record
        for stream in (old.stdin,old.stdout):
            try:self.selector.unregister(stream)
            except KeyError:pass
        self.worker=candidate['process'];self.record=self.candidate_record
        self.worker_database=candidate['path'];self.accepted_identity=candidate['identity']
        if self.incremental_coverage is not None:self.incremental_coverage.update(state='reconciling',reason='snapshot_replaced')
        self.worker_ready=True;self.worker_read.clear();self.worker_write=b''
        self.candidate=None;self.candidate_record=None;self.retiring_record=old_record
        os.set_blocking(self.worker.stdin.fileno(),False)
        self.selector.register(self.worker.stdout,selectors.EVENT_READ,'worker')
        self.retiring_stranded = old
        self.save('ready','retiring_previous')
        if old_journal is not None: old_journal.close()
        old.kill()
        try:old.wait(timeout=.1);reaped=True
        except subprocess.TimeoutExpired:reaped=False
        old.stdin.close();old.stdout.close()
        if reaped:self.retiring_record=None;self.retiring_stranded=None
        else:self.quarantined=True;self.retiring_stranded=old
        self.save('ready' if reaped else 'quarantined','replaced' if reaped else 'cleanup_unproved')
        self.reply(candidate['client'],{'schema_version':1,'status':'replaced','complete':False,'results':[],'snapshot_id':self.accepted_identity} if reaped else error('cleanup_unproved'))
    def schedule(self):
        if self.quarantined or self.active or self.internal_checkpoint: return
        if self.checkpoint_action is not None and self.worker_ready and time.monotonic() >= self.checkpoint_poll_after:
            phase = self.checkpoint_action['phase']
            if phase == 'compact_wait':
                self.checkpoint_action['phase'] = 'compact_start'
                self.send_checkpoint(0x102)
                return
            if phase in ('compact', 'poll'):
                self.send_checkpoint(0x103 if phase == 'compact' else 0x107)
                return
        if not self.queue: return
        if self.worker is None:
            if self.startup_exhausted:
                self.reply(self.queue.popleft(), error(self.startup_exhausted))
            elif time.monotonic() >= self.next_start: self.spawn()
            return
        if not self.worker_ready: return
        if self.checkpoint_action is not None and self.journal is not None and self.queue[0]['request'].get('op') == 'catalog_apply' and self.journal.checkpoint_required():
            return
        self.active = self.queue.popleft(); request = self.active['request']
        if (request.get('op') or '').startswith('catalog_'):
            expected=request.get('expected_snapshot_id')
            if expected is not None and expected!=self.accepted_identity:
                client=self.active;self.active=None;self.reply(client,error('snapshot_conflict'));return
            op=request['op'];body=b''
            if op=='catalog_coverage':
                self.incremental_coverage=dict(request['coverage']);self.coverage_deadline=time.monotonic()+2
                if self.catalog_journal_enabled and self.journal is not None and self.journal_failure is None and not self.journal.tail_uncommitted and request['coverage']['state']=='watching' and request['coverage']['catalog_sequence']==self.journal.count:
                    self.recovery_gap=None
                client=self.active;self.active=None
                self.reply(client,{'schema_version':1,'status':'catalog_coverage','complete':False,'results':[],'snapshot_id':self.accepted_identity})
                return
            if op=='catalog_compact' and self.catalog_journal_enabled:
                if self.candidate is not None or self.pending_replacement is not None:
                    client = self.active; self.active = None; self.reply(client, error('replacement_busy')); return
                if self.checkpoint_action is not None:
                    client = self.active; self.active = None
                    self.reply(client, {'schema_version': 1, 'status': 'catalog_compacting', 'complete': False, 'results': [], 'building': True, 'snapshot_id': self.accepted_identity})
                    return
                if self.journal is None or self.journal_failure or self.journal.tail_uncommitted:
                    client = self.active; self.active = None
                    self.reply(client, error('checkpoint_busy' if self.checkpoint_action else 'catalog_journal_invalid'))
                    return
                self.checkpoint_action = {'phase': 'compact_start', 'name': None, 'sequence': None, 'client': self.active}
                self.worker_write = struct.pack('!7I', 0x102, 0, 0, 0, 0, 0, 0)
                self.selector.register(self.worker.stdin, selectors.EVENT_WRITE, 'worker_write')
                return
            if op=='catalog_apply':
                if self.catalog_journal_enabled:
                    try:
                        if self.journal is None: raise JournalError('catalog_journal_invalid')
                        self.journal.reserve(request)
                    except (JournalError, OSError) as failure:
                        self.recovery_gap = str(failure) if isinstance(failure, JournalError) else 'catalog_journal_write_failed'
                        client = self.active; self.active = None; self.reply(client, error(self.recovery_gap)); return
                body=base64.b64decode(request['name_b64']);sequence=request['sequence']
                command=0x101 if 'entry_id' in request else 0x100
                words=(command,request['entry_kind'],request['parent_id'],request.get('entry_id',0),sequence>>32,sequence&0xffffffff,len(body))
            else:
                command={'catalog_compact':0x102,'catalog_status':0x103,'catalog_lookup':0x104}[op]
                if op=='catalog_lookup':body=base64.b64decode(request['path_b64'])
                words=(command,0,0,0,0,0,len(body))
            self.worker_write=struct.pack('!7I',*words)+body
            self.selector.register(self.worker.stdin,selectors.EVENT_WRITE,'worker_write');return
        query = request['query'].encode(); extension = (request['extension'] or '').encode()
        flags = int(request['path']) | (int(request['match_case']) << 1) | (4 if request['extension'] is not None else 0)
        self.worker_write = struct.pack('!7I', flags, ('all', 'files', 'folders').index(request['kind']), request['limit'], request['max_candidates'], request['max_bytes'], len(query), len(extension)) + query + extension
        self.selector.register(self.worker.stdin, selectors.EVENT_WRITE, 'worker_write')
    def run(self):
        try:
            while not self.stopping:
                for key, mask in self.selector.select(0.01):
                    tag = key.data
                    try:
                        if tag == 'listener': self.accept()
                        elif tag == 'worker':
                            if self.worker and key.fileobj is self.worker.stdout: self.read_worker()
                        elif tag == 'candidate':
                            if self.candidate and key.fileobj is self.candidate['process'].stdout:self.read_candidate()
                        elif tag == 'worker_write':
                            if self.worker and key.fileobj is self.worker.stdin:
                                count = os.write(key.fd, self.worker_write); self.worker_write = self.worker_write[count:]
                                if not self.worker_write: self.selector.unregister(key.fileobj)
                        elif mask & selectors.EVENT_WRITE:
                            count = tag['socket'].send(tag['output']); tag['output'] = tag['output'][count:]
                            if not tag['output']: self.close_client(tag)
                        else: self.read_client(tag)
                    except (BlockingIOError, InterruptedError): pass
                    except (BrokenPipeError, ConnectionResetError):
                        if isinstance(tag, dict): self.close_client(tag)
                        else: self.abort_worker('worker_failed')
                if self.stranded is not None and self.stranded.poll() is not None:
                    self.stranded = None  # Reap when possible; durable quarantine still requires explicit recovery.
                now = time.monotonic()
                for client in list(self.clients.values()):
                    if now >= client['deadline']:
                        if client['output'] is not None: self.close_client(client)
                        elif self.candidate and self.candidate['client'] is client:self.abort_candidate('deadline')
                        elif self.active is client: self.abort_worker('deadline')
                        else:
                            try: self.queue.remove(client)
                            except ValueError: pass
                            self.reply(client, error('deadline'))
                if self.worker and not self.worker_ready and now >= self.start_deadline: self.abort_worker('startup_deadline')
                if self.candidate and now>=self.candidate['deadline'] and not self.candidate['ready']:self.abort_candidate('startup_deadline')
                for stranded in (self.candidate_stranded,self.retiring_stranded):
                    if stranded is not None:stranded.poll()
                self.poll_candidate_checkpoint()
                self.promote_candidate()
                self.schedule()
        finally:
            self.abort_worker('shutdown')
            if self.stranded is not None: self.stranded.poll()
            for client in list(self.clients.values()): self.close_client(client)
            self.selector.close(); self.listener.close()
            current = self.directory.socket_info()
            if current and current.st_ino == self.socket_inode: os.unlink(self.directory.name, dir_fd=self.directory.fd)

def client(args, directory):
    request = {'schema_version': 1, 'request_id': uuid.uuid4().hex, 'op': 'stop'} if args.command == 'stop' else {
        'schema_version': 1, 'request_id': uuid.uuid4().hex, 'query': args.query, 'extension': args.extension,
        'kind': args.kind, 'path': args.path, 'match_case': args.match_case, 'limit': args.limit,
        'max_candidates': args.max_candidates, 'max_bytes': args.max_bytes, 'timeout_ms': args.timeout_ms}
    if args.command == 'replace':
        if not args.candidate_database:raise BoundaryError('invalid_request')
        request={'schema_version':1,'request_id':uuid.uuid4().hex,'op':'replace','candidate_database_b64':base64.b64encode(os.fsencode(os.path.abspath(args.candidate_database))).decode(),'timeout_ms':args.timeout_ms}
    validate_request(request)
    body = encoded(request)
    if len(body) > MAX_FRAME: raise BoundaryError('invalid_request')
    startup_deadline = time.monotonic() + 2
    launcher = None
    while True:
        directory.socket_info()
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); connection.settimeout(0.1)
        try: connection.connect(directory.address); break
        except (FileNotFoundError, ConnectionRefusedError):
            connection.close()
            state = directory.state()
            if state and state.get('phase') == 'quarantined': raise BoundaryError('quarantined')
            if args.command == 'stop' or not args.database: raise BoundaryError('service_unavailable')
            if launcher is None:
                launcher = subprocess.Popen([str(Path(__file__).resolve()), 'serve', '--socket', args.socket, '--database', args.database], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
            if time.monotonic() >= startup_deadline: raise BoundaryError('startup_deadline')
            time.sleep(0.01)
    try:
        credentials = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if credentials[1] != os.geteuid(): raise BoundaryError('unsafe_peer')
        state = directory.state()
        if args.database and state and state.get('database') != os.path.abspath(args.database): raise BoundaryError('snapshot_conflict')
        deadline = time.monotonic() + args.timeout_ms/1000 + 0.3
        connection.settimeout(max(0.001, deadline-time.monotonic()))
        connection.sendall(body); response = bytearray()
        while b'\n' not in response:
            remaining = deadline-time.monotonic()
            if remaining <= 0: raise BoundaryError('deadline')
            connection.settimeout(remaining)
            chunk = connection.recv(65536)
            if not chunk: raise BoundaryError('service_unavailable')
            response.extend(chunk)
            if len(response) > args.max_bytes: raise BoundaryError('response_size_limit')
        payload = json.loads(response)
        if payload.get('request_id') != request['request_id'] and not (payload.get('status') == 'error' and payload.get('request_id') is None): raise BoundaryError('worker_protocol_failed')
        sys.stdout.write(response.decode()); return int(payload.get('status') == 'error')
    except socket.timeout: raise BoundaryError('deadline')
    finally: connection.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('serve', 'query', 'stop', 'recover', 'replace'))
    parser.add_argument('--socket', required=True); parser.add_argument('--database')
    parser.add_argument('--catalog-journal', action='store_true')
    parser.add_argument('--candidate-database'); parser.add_argument('--query'); parser.add_argument('--extension'); parser.add_argument('--kind', default='all')
    parser.add_argument('--path', action='store_true'); parser.add_argument('--match-case', action='store_true')
    parser.add_argument('--limit', type=int, default=100); parser.add_argument('--max-candidates', type=int, default=500000)
    parser.add_argument('--max-bytes', type=int, default=MAX_RESPONSE); parser.add_argument('--timeout-ms', type=int, default=2000)
    args = parser.parse_args()
    directory = None
    try:
        directory = PrivateDirectory(args.socket)
        if args.command in ('query', 'stop', 'replace'): return client(args, directory)
        directory.lock(); reconcile(directory, args.command == 'recover')
        if args.command == 'recover': print(json.dumps({'status': 'recovered'})); return 0
        if not args.database: raise BoundaryError('invalid_request')
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        maximum = 2048*1024*1024 if hard == resource.RLIM_INFINITY else min(hard, 2048*1024*1024)
        current = 64*1024*1024 if soft == resource.RLIM_INFINITY else min(soft, 64*1024*1024)
        resource.setrlimit(resource.RLIMIT_AS, (min(current, maximum), maximum))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        Supervisor(directory, args.database, args.catalog_journal).run(); return 0
    except BoundaryError as exc: sys.stdout.buffer.write(encoded(error(str(exc)))); return 1
    except (OSError, ValueError, UnicodeError): sys.stdout.buffer.write(encoded(error('service_unavailable'))); return 1
    finally:
        if directory: directory.close()
if __name__ == '__main__': raise SystemExit(main())
