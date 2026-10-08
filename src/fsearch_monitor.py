#!/usr/bin/env python3
"""Optional explicit-root monitoring, separate from the query service."""
import argparse
import contextlib
import io
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import resource
import select
import signal
import time
from types import SimpleNamespace

base = Path(__file__).resolve().parent
refresh_path = base/'fsearch-refresh'
if not refresh_path.exists(): refresh_path = base/'fsearch_refresh.py'
loader = importlib.machinery.SourceFileLoader('_fsearch_monitor_refresh', str(refresh_path))
spec = importlib.util.spec_from_loader(loader.name, loader)
refresh = importlib.util.module_from_spec(spec)
loader.exec_module(refresh)
lifecycle = refresh.lifecycle
BoundaryError = lifecycle.BoundaryError


class GenerationChanged(Exception):
    def __init__(self, status): self.status = status


def emit(status, **fields):
    print(json.dumps({'schema_version': 1, 'status': status, 'reason': status, **fields}), flush=True)


class MonitorRefresh(refresh.Refresh):
    def cleanup(self):
        # A second shutdown signal must not interrupt reap/quarantine recording.
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
        cleaned = False
        try:
            super().cleanup()
            cleaned = True
        finally:
            if cleaned: signal.pthread_sigmask(signal.SIG_SETMASK, previous)


class Watcher(MonitorRefresh):
    def __init__(self, directory, root):
        super().__init__(directory)
        self.root = root
        self.buffer = bytearray()
        self.change = None
        previous = directory.state() or {}
        self.snapshot_id = previous.get('snapshot_id')

    def save(self, phase, reason):
        self.directory.save({'phase': phase, 'reason': reason, 'root': self.root,
                             'worker': self.record, 'snapshot_id': self.snapshot_id,
                             'supervisor': lifecycle.identity(os.getpid())})

    def message(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            if b'\n' in self.buffer:
                line, _, rest = self.buffer.partition(b'\n'); self.buffer = bytearray(rest)
                try: message = json.loads(line)
                except (ValueError, UnicodeError): raise BoundaryError('worker_protocol_failed') from None
                if not isinstance(message, dict): raise BoundaryError('worker_protocol_failed')
                return message
            if not select.select([self.worker.stdout], [], [], max(0, deadline-time.monotonic()))[0]:
                return None
            data = os.read(self.worker.stdout.fileno(), 4097)
            if not data: raise BoundaryError('failed_worker')
            self.buffer.extend(data)
            if len(self.buffer) > 4096: raise BoundaryError('worker_protocol_failed')

    def arm(self, timeout):
        self.spawn([str(base/'fsearch-monitor-worker'), '--root', self.root])
        message = self.message(timeout)
        if message is None: raise BoundaryError('watch_deadline')
        if message.get('status') == 'error':
            failure = message.get('error')
            if not isinstance(failure, dict) or not isinstance(failure.get('code'), str):
                raise BoundaryError('worker_protocol_failed')
            raise BoundaryError(failure['code'])
        if message.get('status') != 'ready' or any(type(message.get(key)) is not int
                or message[key] <= 0 for key in ('watches', 'root_device', 'root_inode')):
            raise BoundaryError('worker_protocol_failed')
        self.save('ready', 'armed')
        emit('armed', root=self.root, snapshot_id=self.snapshot_id, watches=message['watches'])

    def check(self, timeout=0):
        if self.change is None:
            message = self.message(timeout)
            if message is None: return
            self.change = message.get('status')
            if self.change not in ('dirty', 'overflow', 'offline'):
                raise BoundaryError('failed_worker')
        if self.change == 'offline': raise BoundaryError('root_offline')
        raise GenerationChanged(self.change)


class MonitoredRefresh(MonitorRefresh):
    def __init__(self, directory, watcher):
        super().__init__(directory)
        self.watcher = watcher

    def read_frame(self, timeout, framed):
        result = super().read_frame(timeout, framed)
        # Reject a dirty generation before proceeding to candidate publication.
        self.watcher.check()
        return result


def accepted_identity(directory, name):
    fd = directory.open_private(name, os.O_RDONLY)
    try:
        info = os.fstat(fd)
        mtime = divmod(info.st_mtime_ns, 1000000000)
        ctime = divmod(info.st_ctime_ns, 1000000000)
        return ':'.join(map(str, (info.st_dev, info.st_ino, info.st_size, *mtime, *ctime)))
    finally: os.close(fd)


def replace_serving(socket_path, database, expected_identity, root):
    directory = lifecycle.PrivateDirectory(socket_path)
    try:
        args = SimpleNamespace(command='replace', socket=socket_path, database=None,
            candidate_database=database, query=None, extension=None, kind='all', path=False,
            match_case=False, limit=100, max_candidates=500000,
            max_bytes=lifecycle.MAX_RESPONSE, timeout_ms=2000)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = lifecycle.client(args, directory)
        try: response = json.loads(output.getvalue())
        except (ValueError, UnicodeError): raise BoundaryError('worker_protocol_failed') from None
        if not isinstance(response, dict): raise BoundaryError('worker_protocol_failed')
        if code or response.get('status') != 'replaced':
            failure = response.get('error')
            if not isinstance(failure, dict) or not isinstance(failure.get('code'), str):
                raise BoundaryError('worker_protocol_failed')
            raise BoundaryError(failure['code'])
        if response.get('snapshot_id') != expected_identity:
            raise BoundaryError('replacement_identity_mismatch')
        emit('serving_replaced', root=root, snapshot_id=response['snapshot_id'], visibility='cached')
    finally: directory.close()


def watch(directory, root, database, timeout, socket_path=None):
    consecutive_dirty = 0
    while True:
        watcher = Watcher(directory, root)
        try:
            watcher.arm(timeout)
            update_directory = lifecycle.PrivateDirectory(database+'.refresh')
            try:
                update_directory.lock()
                lifecycle.reconcile(update_directory)
                MonitoredRefresh(update_directory, watcher).run(root, database, timeout)
                watcher.check()
                watcher.snapshot_id = accepted_identity(directory, Path(database).name)
                watcher.save('ready', 'published')
                emit('published', root=root, snapshot_id=watcher.snapshot_id,
                     visibility='cached', coverage='watching')
                if socket_path: replace_serving(socket_path, database, watcher.snapshot_id, root)
            finally: update_directory.close()
            consecutive_dirty = 0
            while True: watcher.check(.1)
        except GenerationChanged as changed:
            consecutive_dirty += 1
            emit(changed.status, root=root, snapshot_id=watcher.snapshot_id, coverage='incomplete')
            if consecutive_dirty >= 8: raise BoundaryError('reconciliation_limit')
        finally: watcher.cleanup()
        time.sleep(.05)  # Bounded debounce; the next generation arms before refresh.


def interrupted(signum, frame): raise BoundaryError('interrupted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['watch', 'recover'])
    parser.add_argument('--root')
    parser.add_argument('--socket')
    parser.add_argument('--database', required=True)
    parser.add_argument('--timeout-ms', type=int, default=10000)
    args = parser.parse_args(); directory = None
    try:
        if not 1 <= args.timeout_ms <= 300000 or (args.command == 'watch'
                and (not args.root or not os.path.isabs(args.root))):
            raise BoundaryError('invalid_request')
        if args.root is not None and (len(os.fsencode(args.root)) > 4096 or '\0' in args.root):
            args.root = None
            raise BoundaryError('invalid_request')
        database = os.path.abspath(args.database)
        directory = lifecycle.PrivateDirectory(database+'.monitor'); directory.lock()
        lifecycle.reconcile(directory, args.command == 'recover')
        if args.command == 'recover': emit('recovered'); return 0
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        maximum = min(hard, 2048*1024*1024) if hard != resource.RLIM_INFINITY else 2048*1024*1024
        current = min(soft, 64*1024*1024) if soft != resource.RLIM_INFINITY else 64*1024*1024
        resource.setrlimit(resource.RLIMIT_AS, (min(current, maximum), maximum))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGINT, interrupted)
        watch(directory, os.path.abspath(args.root), database, args.timeout_ms/1000, args.socket)
    except (BoundaryError, OSError, ValueError, UnicodeError) as exc:
        code = str(exc) if isinstance(exc, BoundaryError) else 'monitor_unavailable'
        try: state = directory.state() if directory else {}
        except (BoundaryError, OSError): state = {}
        emit('stopped' if code == 'interrupted' else 'error', root=args.root,
             snapshot_id=(state or {}).get('snapshot_id'), reason=code, error={'code': code})
        return 0 if code == 'interrupted' else 1
    finally:
        if directory: directory.close()


if __name__ == '__main__': raise SystemExit(main())
