#!/usr/bin/env python3
"""Assembled descriptor broker candidate. No mark creation or activation.

Production observation requires a separately authorized setup process. Fixture
mode is explicit and cannot establish actual kernel delivery or confinement.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from fsearch_fanotify_events import BootstrapSession, BootstrapChanges, Gap
from fsearch_broker_source import SourceReader, CatalogBroker, receive_source, _identity
from fsearch_broker_admission import DirectoryMap, ContainedAdmission


def emit(status, **fields):
    print(json.dumps({'schema_version': 1, 'status': status, 'durable': False, **fields}), flush=True)


def load_runtime(runtime):
    path = runtime / 'fsearch-incremental'
    loader = importlib.machinery.SourceFileLoader('_fsearch_broker_incremental', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec); loader.exec_module(module)
    return module


class StartupSource:
    def __init__(self, reader, root):
        self.reader, self.root = reader, root

    def check(self, timeout=0):
        # Keep only bounded dirty-set bits until admission exists. No outside
        # names/handles are retained for replay; admitted changes reject startup.
        self.reader.pump(lambda *args: None, lambda *args: None)


class PreviewCatalog:
    """One isolated candidate reader, reaped before serving publication."""
    def __init__(self, module, runtime, database, socket_path, remaining):
        self.module, self.runtime, self.database = module, runtime, database
        self.socket_path, self.remaining = socket_path, remaining
        self.process = self.client = None

    @staticmethod
    def preflight(module, socket_path):
        directory = module.lifecycle.PrivateDirectory(socket_path)
        try:
            directory.lock(); module.lifecycle.reconcile(directory)
        finally:
            directory.close()

    def __enter__(self):
        self.preflight(self.module, self.socket_path)
        self.client = self.module.CatalogClient(self.socket_path)
        try:
            self.process = subprocess.Popen([sys.executable, str(self.runtime / 'fsearch-service'),
                'serve', '--socket', self.socket_path, '--database', self.database],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            while True:
                self.remaining()
                if self.process.poll() is not None: raise Gap('candidate_reader_failed')
                try:
                    self.client.reset()
                    return self.client
                except (FileNotFoundError, ConnectionRefusedError):
                    time.sleep(.01)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.client:
            self.client.close(); self.client = None
        if self.process:
            if self.process.poll() is None: self.process.terminate()
            try: self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                try: self.process.wait(timeout=.1)
                except subprocess.TimeoutExpired: raise Gap('cleanup_unproved')
            self.process = None
            directory = self.module.lifecycle.PrivateDirectory(self.socket_path)
            try:
                directory.lock(); self.module.lifecycle.reconcile(directory)
            except self.module.lifecycle.BoundaryError as error:
                raise Gap('cleanup_unproved') from error
            finally:
                directory.close()

    def __exit__(self, *args):
        self.close()


def interrupted(signum, frame):
    raise Gap('interrupted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--socket', required=True)
    handoff = parser.add_mutually_exclusive_group(required=True)
    handoff.add_argument('--transport-fd', type=int)
    handoff.add_argument('--handoff-socket')
    parser.add_argument('--source-kind', choices=('fanotify', 'fixture'), default='fanotify')
    parser.add_argument('--generation', type=int, default=1)
    parser.add_argument('--runtime', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--boundary', type=Path, required=True)
    parser.add_argument('--startup-seconds', type=float, default=10)
    args = parser.parse_args()
    reader = client = admission = directory_map = directory = transport = None
    exit_code, reason = 1, 'broker_unavailable'
    try:
        if not os.path.isabs(args.root) or '\0' in args.root or len(os.fsencode(args.root)) >= 4096 or args.transport_fd is not None and args.transport_fd < 3 or args.handoff_socket is not None and (not os.path.isabs(args.handoff_socket) or '\0' in args.handoff_socket or len(os.fsencode(args.handoff_socket)) >= 108) or not 1 <= args.generation < 2**64 or not 0 < args.startup_seconds <= 300:
            raise Gap('broker_configuration')
        startup_deadline = time.monotonic() + args.startup_seconds
        def remaining():
            seconds = startup_deadline - time.monotonic()
            if seconds <= 0:
                raise Gap('bootstrap_deadline')
            return seconds
        # Authenticate the setup endpoint before accessing root/catalog state.
        # Production still requires an administrator-created named endpoint;
        # inherited socketpairs are confined to owned fixture mode.
        if args.source_kind == 'fanotify' and args.transport_fd is not None:
            raise Gap('handoff_authority')
        transport = socket.socket(fileno=args.transport_fd) if args.transport_fd is not None else socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        transport.settimeout(min(2, remaining()))
        if args.handoff_socket is not None:
            transport.connect(args.handoff_socket)
        from fsearch_broker_source import _peer
        peer_uid = 0 if args.source_kind == 'fanotify' else os.geteuid()
        _peer(transport, peer_uid)
        module = load_runtime(args.runtime)
        root = os.fsencode(os.path.abspath(args.root)); database = os.path.abspath(args.database)
        directory = module.lifecycle.PrivateDirectory(database + '.broker')
        directory.lock(); module.lifecycle.reconcile(directory)
        PreviewCatalog.preflight(module, database + '.broker-preview')
        client = module.CatalogClient(args.socket); client.reset()
        client.coverage('reconciling', root, reason='broker_startup')
        directory_map = DirectoryMap()
        owner = module.ContinuousWatcher(directory, os.fsdecode(root))
        admission = ContainedAdmission(owner, args.boundary, client, root, args.generation, directory_map)
        admission.arm(min(2, remaining()))
        token = os.urandom(32)
        # Authenticate peer before sending the request, then require the same
        # root/session attestation with the descriptor response.
        transport.sendall(_identity(args.generation, token, admission.root_identity))
        descriptor = receive_source(transport, peer_uid=peer_uid, generation=args.generation,
                                    token=token, root_identity=admission.root_identity, source_kind=args.source_kind)
        transport.close(); transport = None
        session = BootstrapSession(args.generation, bootstrap_changes=BootstrapChanges())
        reader = SourceReader(descriptor, session)
        startup = StartupSource(reader, os.fsdecode(root))
        signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGINT, interrupted)
        # Scan a private candidate. A failed namespace qualification must not
        # replace either the serving generation or its restart cache.
        candidate = database + '.broker-candidate'
        update = module.lifecycle.PrivateDirectory(database + '.refresh')
        try:
            update.lock(); module.lifecycle.reconcile(update)
            module.monitor.MonitoredRefresh(update, startup).run(os.fsdecode(root), candidate, remaining())
            startup.check()
        finally:
            update.close()
        with PreviewCatalog(module, args.runtime, candidate, database + '.broker-preview', remaining) as preview:
            admission.client = preview
            located_root = preview.lookup(root)
            if not located_root or located_root['entry_kind'] != 2:
                raise Gap('catalog_root_missing')
            admission.inventory(located_root['entry_id'], root, baseline=True,
                                seconds=remaining(), source_check=startup.check)
            session.filter.root_handle = directory_map.identity(located_root['entry_id'])
            def bootstrap_check():
                remaining()
                startup.check()
            session.qualify_baseline(directory_map.identities(), directory_map.admitted, bootstrap_check)
            startup.check(); session.finish_baseline(args.generation)
        # The isolated reader is gone. Events after the qualified baseline cut
        # stay queued until the serving catalog accepts this same image.
        remaining()
        candidate_name, database_name = Path(candidate).name, Path(database).name
        fd = directory.open_private(candidate_name, os.O_RDONLY)
        try:
            if os.fstat(fd).st_nlink != 1: raise Gap('candidate_custody')
            os.fsync(fd)
            previous = directory.open_private(database_name, os.O_RDONLY)
            os.close(previous)
            os.replace(candidate_name, database_name, src_dir_fd=directory.fd, dst_dir_fd=directory.fd)
            os.fsync(directory.fd)
        finally:
            os.close(fd)
        identity = module.monitor.accepted_identity(directory, database_name)
        module.monitor.replace_serving(args.socket, database, identity, os.fsdecode(root))
        client.reset(); admission.client = client
        published_root = client.lookup(root)
        if not published_root or published_root['entry_id'] != located_root['entry_id']:
            raise Gap('catalog_root_changed')
        broker = CatalogBroker(reader, client, root, admission.validate, directory_map, admission.inventory, admission.entry_kind)
        deadline = min(startup_deadline, time.monotonic() + 2)
        while not broker.pump():
            if time.monotonic() >= deadline:
                raise Gap('bootstrap_drain_deadline')
        emit('watching', snapshot_id=client.identity, source_kind=args.source_kind,
             boundary_worker=admission.watcher.record, generation=args.generation)
        next_root_check = 0
        while True:
            if time.monotonic() >= next_root_check:
                admission.validate(session.filter.root_handle, args.generation)
                next_root_check = time.monotonic() + .5
            if broker.pump():
                time.sleep(.05)
    except Gap as error:
        reason = str(error)
        exit_code = 0 if reason == 'interrupted' else 1
    except Exception:
        reason = 'broker_unavailable'
    finally:
        if client:
            try: client.coverage('deferred', os.fsencode(os.path.abspath(args.root)), reason='broker_stopped' if reason == 'interrupted' else reason)
            except Exception: pass
        if reader: reader.close()
        if transport: transport.close()
        if admission:
            try: admission.close()
            except Exception: reason, exit_code = 'cleanup_unproved', 1
        if directory_map: directory_map.close()
        if client: client.close()
        if directory: directory.close()
        emit('stopped' if exit_code == 0 else 'error', reason=reason)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
