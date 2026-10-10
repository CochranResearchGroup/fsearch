"""Assembled broker command with ordinary descriptors and actual owned roots.

The event producer injects records after mutations. Actual fanotify delivery and
adversarial confinement remain explicitly separate qualification requirements.
"""
import base64
import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fsearch_broker_source as transport
from fsearch_fanotify_events import CREATE, DELETE, RENAME, ONDIR, OVERFLOW
from test_fanotify_events import event, info

ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('runtime', type=Path)
    parser.add_argument('frontend', type=Path)
    parser.add_argument('boundary', type=Path)
    parser.add_argument('--actual-fixture-dir', type=Path)
    parser.add_argument('--extended-actual', action='store_true')
    parser.add_argument('--actual-overflow', action='store_true')
    parser.add_argument('--actual-edges', action='store_true')
    parser.add_argument('--actual-loss', action='store_true')
    parser.add_argument('--actual-churn', action='store_true')
    parser.add_argument('--actual-exclusions', action='store_true')
    parser.add_argument('--profile-broker', action='store_true')
    parser.add_argument('--profile-service', action='store_true')
    parser.add_argument('--startup-churn', action='store_true')
    parser.add_argument('--permission-exclusions', action='store_true')
    parser.add_argument('--durable-catalog', action='store_true')
    args = parser.parse_args()
    actual = args.actual_fixture_dir is not None
    assert not args.startup_churn or not actual, 'startup churn uses the explicit descriptor fixture'
    assert not args.durable_catalog or actual, 'durability requires explicit actual fixture'
    assert not args.extended_actual or actual, 'extended controls require explicit actual fixture'
    assert not args.actual_overflow or actual and not args.extended_actual, 'overflow requires separate actual fixture run'
    assert not args.actual_edges or actual and not args.extended_actual and not args.actual_overflow, 'edge controls require separate actual run'
    assert not args.actual_loss or actual and not any((args.extended_actual, args.actual_overflow, args.actual_edges)), 'session loss requires a separate actual run'
    assert not args.actual_churn or actual and args.durable_catalog and not any((args.extended_actual, args.actual_overflow, args.actual_edges, args.actual_loss)), 'churn requires a separate actual durable run'
    assert not args.permission_exclusions or not any((args.extended_actual, args.actual_overflow, args.actual_edges, args.actual_loss, args.actual_churn, args.startup_churn)), 'permission exclusions require a separate run'
    assert not args.actual_exclusions or actual and args.durable_catalog and not any((args.extended_actual, args.actual_overflow, args.actual_edges, args.actual_loss, args.actual_churn, args.startup_churn, args.permission_exclusions)), 'live exclusions require a separate actual durable run'
    if args.actual_overflow:
        assert 0 < int(Path('/proc/sys/fs/fanotify/max_queued_events').read_text()) <= 16384, 'queue bound outside reviewed burst'
    if actual:
        # Prepared owned fixture only; the separately reviewed setup service
        # must already have fixed this same root in administrator configuration.
        manifest = json.loads((args.actual_fixture_dir / 'owned-fixture.json').read_text())
        assert manifest == {'schema_version': 1, 'owner_uid': os.geteuid(), 'root': str(args.actual_fixture_dir / 'owned')}
        assert args.actual_fixture_dir.is_absolute() and not args.actual_fixture_dir.is_symlink()
        assert args.actual_fixture_dir.stat().st_uid == os.geteuid()
        assert (args.actual_fixture_dir / 'owned').is_dir() and not (args.actual_fixture_dir / 'owned').is_symlink()
        assert not list((args.actual_fixture_dir / 'owned').iterdir())
    if str(args.frontend) == '-':
        configured = os.environ.get('FSEARCH_FRONTEND_ACCEPTANCE_ROOT')
        if not configured:
            print('Explicit frontend acceptance root not selected; broker CLI/MCP qualification not run.')
            return 77
        runtime, frontend, boundary = args.runtime, Path(configured), args.boundary
    else:
        runtime, frontend, boundary = args.runtime, args.frontend, args.boundary
    broker_executable = runtime / 'fsearch_broker.py' if actual else Path(__file__).resolve().parents[1] / 'fsearch_broker.py'
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='fsearch-broker-process-') as temporary:
        # Production requires a root-authenticated named endpoint before any
        # root/catalog state. The accepted transition exception is not authority
        # for a user-created socketpair or listener to supply a real source.
        for handoff, reason in ((['--transport-fd', '987654'], 'handoff_authority'), (['--handoff-socket', temporary + '/absent-handoff'], 'broker_unavailable')):
            rejected = subprocess.run([sys.executable, str(broker_executable),
                '--root', temporary + '/absent', '--database', temporary + '/absent-db',
                '--socket', temporary + '/absent-socket', *handoff,
                '--boundary', temporary + '/absent-helper'],
                capture_output=True, text=True, timeout=3)
            assert rejected.returncode == 1, rejected
            assert json.loads(rejected.stdout)['reason'] == reason
            assert not list(Path(temporary).iterdir()), 'rejected activation left state'
        impostor = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        impostor_path = temporary + '/impostor.sock'
        impostor.bind(impostor_path); impostor.listen(1)
        try:
            rejected = subprocess.run([sys.executable, str(broker_executable),
                '--root', temporary + '/absent', '--database', temporary + '/absent-db',
                '--socket', temporary + '/absent-socket', '--handoff-socket', impostor_path,
                '--boundary', temporary + '/absent-helper'], capture_output=True, text=True, timeout=3)
            assert rejected.returncode == 1 and json.loads(rejected.stdout)['reason'] == 'handoff_peer', rejected
            assert list(Path(temporary).iterdir()) == [Path(impostor_path)], 'untrusted peer created state'
        finally:
            impostor.close(); os.unlink(impostor_path)
        work = args.actual_fixture_dir if actual else Path(temporary)
        root = work / 'owned'; root.mkdir(exist_ok=actual)
        (root / 'initial.txt').touch()
        denied = None
        if args.permission_exclusions:
            denied = root / 'permissions-excluded'; denied.mkdir()
            (denied / 'permissions-hidden.txt').touch()
            denied.chmod(0)
        database = work / 'snapshot'; endpoint = work / 'q.sock'
        refreshed = subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], check=True, capture_output=True, timeout=10)
        if args.permission_exclusions:
            assert json.loads(refreshed.stdout)['scan']['excluded_permissions'] == 1, refreshed.stdout
        # Obtain only this owned root's handle from the actual unprivileged
        # helper. This does not create any fanotify group/mark.
        identity_worker = subprocess.Popen([str(boundary), '--root', str(root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        identity_out, identity_err = identity_worker.communicate(b'GI -\n', timeout=5)
        assert identity_worker.returncode == 0, identity_out + identity_err
        root_handle = next(json.loads(line) for line in identity_out.splitlines() if json.loads(line).get('status') == 'item' and json.loads(line)['path_b64'] == '')
        def side(role, name):
            return info(role, bytes.fromhex(root_handle['handle']), name,
                        bytes.fromhex(root_handle['fsid']), root_handle['handle_kind'])

        config = work / 'config.json'
        config.write_text(json.dumps({'roots': [], 'aliases': [], 'db_path': str(work / 'sqlite'),
            'fsearch_command': str(runtime / 'fsearch-cli'), 'fsearch_database': str(database), 'fsearch_socket': str(endpoint)}))
        env = {**os.environ, 'FILE_SEARCHER_CONFIG': str(config), 'FILE_SEARCHER_DB': str(work / 'sqlite'),
               'FILE_SEARCHER_STATE_DIR': str(work / 'state'), 'PYTHONDONTWRITEBYTECODE': '1'}
        interpreter = [sys.executable] + (['-m', 'cProfile', '-o', str(work / 'service.profile')] if args.profile_service else [])
        server = subprocess.Popen([*interpreter, str(runtime / 'fsearch-service'), 'serve', '--database', str(database), '--socket', str(endpoint)] + (['--catalog-journal'] if args.durable_catalog else []), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
        broker = None; channels = []; worker_pids = []; timings = []
        def record_timing(sample):
            timings.append(sample)
            if actual: (work / 'visibility-timings.json').write_text(json.dumps(timings, indent=2) + '\n')
        def result_paths(rows):
            return sorted(base64.b64decode(row['path_bytes_base64'], validate=True) if row.get('path_bytes_base64') else os.fsencode(row['path']) for row in rows)
        def public(query, expected, state=None, mcp=False, mutate=None):
            python = frontend / '.venv/bin/python'
            if mcp:
                script = '''import asyncio,json,os,sys,time
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
 async with stdio_client(StdioServerParameters(command=sys.executable,args=['-m','file_searcher.mcp_server'],env=dict(os.environ))) as (reader,writer):
  async with ClientSession(reader,writer) as session:
   await session.initialize()
   origin=None
   if len(sys.argv)>2:
    origin=time.monotonic();Path(sys.argv[2]).touch()
   result=await session.call_tool('file_searcher_find',{'query':sys.argv[1],'use_everything':False,'use_locate':False})
   while origin is not None and not result.isError and not result.structuredContent.get('results') and time.monotonic()-origin<1:
    await asyncio.sleep(.01)
    result=await session.call_tool('file_searcher_find',{'query':sys.argv[1],'use_everything':False,'use_locate':False})
   assert not result.isError
   if origin is None: print(json.dumps(result.structuredContent))
   else: print(json.dumps({'payload':result.structuredContent,'mutation_visibility_seconds':time.monotonic()-origin}))
asyncio.run(main())
'''
                command = [str(python), '-c', script, query] + ([str(mutate)] if mutate is not None else [])
            else:
                command = [str(python), '-m', 'file_searcher.cli', 'find', '--no-everything', '--no-locate', query]
            reply = subprocess.run(command, cwd=frontend, env=env, capture_output=True, text=True, timeout=10)
            assert reply.returncode == 0, reply.stderr
            payload = json.loads(reply.stdout)
            if mutate is not None:
                measured = payload['mutation_visibility_seconds']
                payload = payload['payload']
                sample = {'control': 'normal_create', 'seconds': measured, 'gate_seconds': 1, 'surface': 'initialized_fresh_mcp', 'entries': 1}
                record_timing(sample)
                assert measured <= 1, sample
            assert result_paths(payload['results']) == sorted(map(os.fsencode, expected)), payload
            coverage = payload['backends']['fsearch']['incremental_coverage']
            assert coverage['state'] in (state,) if state else coverage['state'] in ('watching', 'pending'), payload
            assert payload['backends']['fsearch']['complete'], payload
            return payload

        def visible(query, expected, origin=None, seconds=1, label=None):
            origin = time.monotonic() if origin is None else origin
            deadline = origin + seconds
            while True:
                reply = subprocess.run([str(runtime / 'fsearch-cli'), '--socket', str(endpoint), '--query', query, '--limit', '1000'], capture_output=True, text=True, timeout=3)
                assert reply.returncode == 0, reply.stderr
                result = json.loads(reply.stdout)
                if args.durable_catalog: assert result['durable'] is True, result
                if result_paths(result['results']) == sorted(map(os.fsencode, expected)):
                    assert result['complete'] and not result['truncated'], result
                    elapsed = time.monotonic() - origin
                    assert elapsed <= seconds, {'visibility_seconds': elapsed, 'gate_seconds': seconds}
                    if label: record_timing({'control': label, 'seconds': elapsed, 'gate_seconds': seconds, 'surface': 'native_cli', 'entries': len(expected)})
                    return
                if time.monotonic() >= deadline:
                    failure = {'control': label, 'seconds': time.monotonic() - origin,
                               'expected_entries': len(expected), 'observed_entries': len(result['results']),
                               'gate_seconds': seconds, 'payload': result}
                    if actual: (work / 'visibility-failure.json').write_text(json.dumps(failure, indent=2) + '\n')
                    raise AssertionError({key: value for key, value in failure.items() if key != 'payload'})
                time.sleep(.01)

        def start(name, named=False):
            nonlocal broker
            writer = source = None
            if actual:
                transport_args = ['--handoff-socket', '/run/fsearch/broker.sock']
                inherited = ()
            elif named:
                listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                handoff_path = str(work / 'handoff.sock')
                listener.bind(handoff_path); listener.listen(1); listener.settimeout(5)
                channels.append(listener)
                transport_args = ['--handoff-socket', handoff_path]
                inherited = ()
            else:
                client, server_transport = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                channels.extend((client, server_transport))
                transport_args = ['--transport-fd', str(server_transport.fileno())]
                inherited = (server_transport.fileno(),)
            if not actual:
                source, writer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                source.setblocking(False)
                channels.extend((source, writer))
            log = work / (name + '.log')
            with log.open('wb') as output:
                interpreter = [sys.executable] + (['-m', 'cProfile', '-o', str(work / (name + '.profile'))] if args.profile_broker else [])
                broker = subprocess.Popen([*interpreter, str(broker_executable), '--root', str(root), '--database', str(database), '--socket', str(endpoint),
                    '--runtime', str(runtime), '--boundary', str(boundary), *transport_args, '--source-kind', 'fanotify' if actual else 'fixture'],
                    pass_fds=inherited, stdout=output, stderr=subprocess.PIPE, env=env, start_new_session=True)
            if actual:
                # Real outside-owned changes while the baseline is built.
                outside = work / 'outside-fixture'; outside.mkdir(exist_ok=True)
                (outside / 'outside-bootstrap-secret').touch()
            elif named:
                client, _ = listener.accept(); channels.append(client); listener.close()
            else:
                server_transport.close()
            if not actual:
                client.settimeout(3)
                request = client.recv(transport.HANDOFF.size + 1)
                magic, generation, token, device, inode = transport.HANDOFF.unpack(request)
                assert magic == transport.MAGIC and (device, inode) == (root.stat().st_dev, root.stat().st_ino)
                writer.send(event(CREATE, [info(2, b'outside-bootstrap', b'outside-bootstrap-secret'), info(1)]))
                if args.startup_churn:
                    (root / 'unqualified-bootstrap.txt').touch()
                    writer.send(event(CREATE, [side(2, b'unqualified-bootstrap.txt'), info(1)]))
                transport.send_source(client, source.fileno(), peer_uid=os.geteuid(), generation=generation,
                                      token=token, root_identity=(device, inode))
                source.close(); client.close()
            deadline = time.monotonic() + 10
            while True:
                rows = [json.loads(line) for line in log.read_text().splitlines()]
                watching = next((row for row in rows if row['status'] == 'watching'), None)
                if args.startup_churn and any(row['status'] == 'error' for row in rows):
                    return writer, log
                if watching:
                    worker_pids.append(watching['boundary_worker']['pid'])
                    if actual:
                        for pid in (broker.pid, watching['boundary_worker']['pid']):
                            status = dict(line.split(':', 1) for line in Path('/proc', str(pid), 'status').read_text().splitlines() if ':' in line)
                            assert set(map(int, status['Uid'].split())) == {os.geteuid()}, 'reader identity changed'
                            assert all(int(status[key].strip(), 16) == 0 for key in ('CapEff', 'CapPrm', 'CapAmb')), 'reader retained privilege'
                            assert status['NoNewPrivs'].strip() == '1', 'reader permits privilege acquisition'
                    return writer, log
                assert broker.poll() is None, log.read_text() + broker.stderr.read().decode()
                assert time.monotonic() < deadline, log.read_text()
                time.sleep(.01)

        def terminal(reason, code=1):
            output, error = broker.communicate(timeout=5)
            assert broker.returncode == code, error
            assert all(not Path('/proc', str(pid)).exists() for pid in worker_pids), worker_pids

        def catalog_call(op, **fields):
            request = {'schema_version': 1, 'request_id': 'catalog-control', 'op': op, **fields}
            with socket.socket(socket.AF_UNIX) as channel:
                channel.settimeout(3); channel.connect(str(endpoint))
                channel.sendall((json.dumps(request) + '\n').encode())
                body = b''
                while b'\n' not in body:
                    block = channel.recv(65536); assert block
                    body += block
            result = json.loads(body)
            assert result['status'] != 'error', result
            return result

        def lookup_id(path):
            return catalog_call('catalog_lookup', path_b64=base64.b64encode(os.fsencode(path)).decode())['entry_id']

        def inject(writer, data):
            if not actual:
                writer.send(data)

        try:
            deadline = time.monotonic() + 5
            while not endpoint.exists():
                assert server.poll() is None and time.monotonic() < deadline; time.sleep(.01)
            if args.startup_churn:
                before = subprocess.run([str(runtime / 'fsearch-cli'), '--socket', str(endpoint), '--query', 'initial'], capture_output=True, text=True, timeout=3)
                assert before.returncode == 0, before.stderr
                original_snapshot = catalog_call('catalog_status')['snapshot_id']
                original_cache = database.read_bytes()
            writer, log = start('first', named=True)
            if args.startup_churn:
                terminal('bootstrap_changed')
                after = subprocess.run([str(runtime / 'fsearch-cli'), '--socket', str(endpoint), '--query', 'initial'], capture_output=True, text=True, timeout=3)
                assert after.returncode == 0, after.stderr
                snapshot = catalog_call('catalog_status')['snapshot_id']
                assert snapshot == original_snapshot, ('failed bootstrap replaced accepted snapshot', original_snapshot, snapshot)
                assert database.read_bytes() == original_cache, 'failed bootstrap replaced restart cache'
                public('unqualified-bootstrap', [], 'deferred', mcp=True)
                print(json.dumps({'result': 'dirty_bootstrap_preserves_accepted_snapshot', 'snapshot_id': snapshot}))
                return 0
            public('outside-bootstrap-secret', [], mcp=True)
            initial = root / 'process-created.pdf'; initial.touch()
            inject(writer, event(CREATE, [side(2, os.fsencode(initial.name)), info(1)]))
            visible('process-created', [initial]); public('process-created', [initial]); public('process-created', [initial], mcp=True)
            directory = root / 'process-directory'; (directory / 'deep').mkdir(parents=True)
            child = directory / 'deep' / 'process-child.txt'; child.touch()
            inject(writer, event(CREATE | ONDIR, [side(2, os.fsencode(directory.name)), info(1)]))
            visible('process-child', [child]); public('process-child', [child], mcp=True)
            renamed = root / 'process-renamed'; os.rename(directory, renamed)
            inject(writer, event(RENAME | ONDIR, [side(10, os.fsencode(directory.name)), side(12, os.fsencode(renamed.name)), info(1)]))
            visible('process-child', [renamed / 'deep' / child.name])
            if args.permission_exclusions:
                public('permissions-excluded', [], mcp=True)
                public('permissions-hidden', [])
                print(json.dumps({'result': 'broker_permission_exclusions_preserve_readable_updates',
                    'durable_catalog': args.durable_catalog, 'actual_delivery': 'PASS' if actual else 'NOT_QUALIFIED',
                    'owned_boundary_pids': worker_pids}))
                return 0
            if not actual:
                writer.send(event(OVERFLOW, [])); terminal('queue_overflow')
                assert 'queue_overflow' in log.read_text(), log.read_text()
                public('process-created', [initial], 'deferred'); public('process-created', [initial], 'deferred', mcp=True)
                writer.close()
                writer, log = start('restart-after-proved-cleanup')
                public('process-child', [renamed / 'deep' / child.name], mcp=True)
            if args.actual_edges:
                slot = root / 'edge-slot.txt'
                origin = time.monotonic(); slot.touch()
                visible('edge-slot', [slot], origin, label='normal_create')
                origin = time.monotonic(); slot.unlink()
                visible('edge-slot', [], origin, label='normal_delete')
                slot.mkdir(); descendant = slot / 'edge-descendant.txt'; descendant.touch()
                visible('edge-descendant', [descendant])
                descendant.unlink(); visible('edge-descendant', [])
                slot.rmdir(); visible('edge-slot', [])
                slot.touch(); visible('edge-slot', [slot]); visible('edge-descendant', [])
                raw = os.fsencode(root) + b'/edge-raw-\xff.txt'
                fd = os.open(raw, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600); os.close(fd)
                raw_path = Path(os.fsdecode(raw))
                visible('edge-raw-', [raw_path]); public('edge-raw-', [raw_path], mcp=True)
                renamed_raw = os.fsencode(root) + b'/edge-raw-renamed-\xfe.txt'
                origin = time.monotonic(); os.rename(raw, renamed_raw)
                renamed_path = Path(os.fsdecode(renamed_raw))
                visible('edge-raw-', [renamed_path], origin, label='normal_raw_rename')
                public('edge-raw-', [renamed_path])
                for mcp in (False, True):
                    measured = root / ('edge-measured-mcp.txt' if mcp else 'edge-measured-cli.txt')
                    if mcp:
                        public(measured.stem, [measured], mcp=True, mutate=measured)
                    else:
                        origin = time.monotonic(); measured.touch()
                        public(measured.stem, [measured])
                        elapsed = time.monotonic() - origin
                        record_timing({'control': 'normal_create', 'seconds': elapsed, 'gate_seconds': 1,
                                       'surface': 'frontend_cli', 'entries': 1})
                        assert elapsed <= 1, timings[-1]
                heavy = [root / f'edge-heavy-{index:04}.txt' for index in range(128)]
                origin = time.monotonic()
                for path in heavy: path.touch()
                visible('edge-heavy-', heavy, origin, seconds=10, label='heavy_128_create_burst')
                public('edge-heavy-0127', [heavy[-1]], mcp=True)
                (work / 'visibility-timings.json').write_text(json.dumps(timings, indent=2) + '\n')
            extended_controls = []
            if args.actual_exclusions:
                excluded = [root / 'excluded-live-symlink', root / 'excluded-live-fifo', root / 'excluded-live-denied']
                controls = []
                try:
                    for index, path in enumerate(excluded):
                        if index == 0: path.symlink_to(work / 'outside-fixture', target_is_directory=True)
                        elif index == 1: os.mkfifo(path, 0o600)
                        else: path.mkdir(mode=0)
                        # A later same-parent regular event must become visible
                        # before checking absence, avoiding an early empty read.
                        sentinel = root / f'eligible-after-exclusion-{index}.txt'; sentinel.touch()
                        visible(sentinel.stem, [sentinel])
                        oracle = work / 'exclusion-oracle'
                        subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(oracle)], check=True, capture_output=True, timeout=10)
                        reference = subprocess.run([str(runtime / 'fsearch-cli'), '--database', str(oracle), '--query', path.name], check=True, capture_output=True, text=True, timeout=3)
                        assert json.loads(reference.stdout)['results'] == [], reference.stdout
                        public(path.name, [], mcp=True)
                        controls.append(path.name)
                    oracle = work / 'exclusion-oracle'
                    refreshed = subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(oracle)], check=True, capture_output=True, timeout=10)
                    scan = json.loads(refreshed.stdout)['scan']
                    assert scan['excluded_symlinks'] == 1 and scan['excluded_permissions'] == 1, scan
                    expected = subprocess.run([str(runtime / 'fsearch-cli'), '--database', str(oracle), '--query', 'excluded-live-'], check=True, capture_output=True, text=True, timeout=3)
                    assert json.loads(expected.stdout)['results'] == [], expected.stdout
                    public('excluded-live-', [], mcp=True)
                    print(json.dumps({'result': 'actual_live_exclusions_match_rebuilt_oracle', 'controls': controls, 'scan': scan}))
                    return 0
                finally:
                    if excluded[-1].exists(): excluded[-1].chmod(0o700)
            if args.actual_churn:
                # Frozen workload: 27 normal mutations, three mixed bursts of
                # 512 creates/512 renames/256 deletes, four querying clients.
                # Each burst is timed from its first mutation, a stronger bound
                # than timing only the last mutation's visibility.
                stop_clients = threading.Event()
                query_samples, query_errors = [], []
                def querying_client():
                    while not stop_clients.is_set():
                        began = time.monotonic()
                        try:
                            reply = subprocess.run([str(runtime / 'fsearch-cli'), '--socket', str(endpoint), '--query', 'initial', '--limit', '1000'], capture_output=True, text=True, timeout=3)
                            result = json.loads(reply.stdout)
                            assert reply.returncode == 0 and result_paths(result['results']) == [os.fsencode(root / 'initial.txt')], reply.stderr or result
                            assert result['durable'] is True, result
                            assert result['incremental_coverage']['state'] in ('watching', 'pending'), result['incremental_coverage']
                            query_samples.append(time.monotonic() - began)
                        except BaseException as error:
                            query_errors.append(repr(error)); stop_clients.set()
                        stop_clients.wait(.1)
                clients = [threading.Thread(target=querying_client) for _ in range(4)]
                for thread in clients: thread.start()
                phases = []
                try:
                    for index in range(9):
                        normal = root / f'normal-churn-{index}.txt'
                        changed = root / f'normal-churn-renamed-{index}.txt'
                        origin = time.monotonic(); normal.touch()
                        visible('normal-churn-', [normal], origin, label='normal_churn_create')
                        origin = time.monotonic(); normal.rename(changed)
                        visible('normal-churn-', [changed], origin, label='normal_churn_rename')
                        origin = time.monotonic(); changed.unlink()
                        visible('normal-churn-', [], origin, label='normal_churn_delete')
                    for cycle in range(3):
                        prefix = f'heavy-churn-{cycle}-'
                        paths = [root / f'{prefix}{index:04d}.txt' for index in range(512)]
                        origin = time.monotonic()
                        for path in paths: path.touch()
                        visible(prefix, paths, origin, seconds=10, label='heavy_churn_create_512')
                        changed = [path.with_name(path.stem + '-renamed.txt') for path in paths]
                        origin = time.monotonic()
                        for old, new in zip(paths, changed): old.rename(new)
                        visible(prefix, changed, origin, seconds=10, label='heavy_churn_rename_512')
                        origin = time.monotonic()
                        for path in changed[:256]: path.unlink()
                        visible(prefix, changed[256:], origin, seconds=10, label='heavy_churn_delete_256')
                        phases.append(catalog_call('catalog_status'))
                        public(changed[-1].stem, [changed[-1]], mcp=True)
                finally:
                    stop_clients.set()
                    for thread in clients: thread.join(timeout=4)
                    (work / 'churn-query-samples.json').write_text(json.dumps({'seconds': query_samples, 'errors': query_errors,
                        'live_clients': sum(thread.is_alive() for thread in clients)}, indent=2) + '\n')
                assert not any(thread.is_alive() for thread in clients), 'query clients did not stop'
                assert not query_errors and len(query_samples) >= 4, query_errors
                # Independently traverse/rebuild, then query native snapshot
                # matching; do not derive the oracle from broker event replies.
                oracle = work / 'churn-oracle'
                subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(oracle)], check=True, capture_output=True, timeout=10)
                expected_reply = subprocess.run([str(runtime / 'fsearch-cli'), '--database', str(oracle), '--query', 'heavy-churn-', '--limit', '1000'], check=True, capture_output=True, text=True, timeout=3)
                expected = json.loads(expected_reply.stdout)
                actual_reply = subprocess.run([str(runtime / 'fsearch-cli'), '--socket', str(endpoint), '--query', 'heavy-churn-', '--limit', '1000'], check=True, capture_output=True, text=True, timeout=3)
                current = json.loads(actual_reply.stdout)
                assert len(expected['results']) == 768 and result_paths(current['results']) == result_paths(expected['results']), (current, expected)
                generation = json.loads(Path(str(endpoint) + '.catalog-generation').read_text())
                checkpoint = generation['generations'][0] if generation['schema_version'] == 3 else generation
                assert checkpoint['sequence'] >= 3072, generation
                (work / 'churn-result.json').write_text(json.dumps({'controls': 'actual_mixed_churn_four_clients_three_production_rollovers', 'timings': timings, 'phases': phases, 'checkpoint_sequence': checkpoint['sequence'], 'query_sample_seconds': query_samples, 'query_errors': query_errors, 'oracle_results': len(expected['results'])}, indent=2) + '\n')
                extended_controls.append('mixed_churn_four_clients_three_production_rollovers_rebuilt_oracle')
            if args.extended_actual:
                moved_child = renamed / 'deep' / child.name
                retired_child_id = lookup_id(moved_child)
                moved_child.unlink(); visible('process-child', [])
                moved_child.touch(); visible('process-child', [moved_child])
                recreated_child_id = lookup_id(moved_child)
                assert recreated_child_id != retired_child_id, 'deleted entry identity resurrected'
                linked = root / 'process-child-hardlink.txt'
                os.link(moved_child, linked)
                visible('process-child', [moved_child, linked])
                linked_id = lookup_id(linked)
                assert linked.stat().st_ino == moved_child.stat().st_ino
                assert linked_id != recreated_child_id, 'hard links share directory-entry identity'
                renamed_link = root / 'process-child-hardlink-renamed.txt'
                os.rename(linked, renamed_link)
                visible('process-child', [moved_child, renamed_link])
                assert lookup_id(renamed_link) == linked_id, 'hard-link rename changed entry identity'
                renamed_link.unlink(); visible('process-child', [moved_child])
                assert lookup_id(moved_child) == recreated_child_id, 'alias deletion retired surviving entry'
                public('process-child', [moved_child], mcp=True)
                extended_controls.append('delete_recreate_hardlink_stable_distinct_ids')
                outside_tree = work / 'outside-tree'
                os.rename(renamed, outside_tree)
                visible('process-child', [])
                public('process-child', [], mcp=True)
                (outside_tree / 'outside-subtree-secret.txt').touch()
                public('outside-subtree-secret', [], mcp=True)
                returned = root / 'process-returned'
                os.rename(outside_tree, returned)
                visible('process-child', [returned / 'deep' / child.name])
                visible('outside-subtree-secret', [returned / 'outside-subtree-secret.txt'])
                extended_controls.append('subtree_move_out_in')
                link = root / 'process-symlink'
                os.symlink(work / 'outside-fixture', link)
                barrier = root / 'extended-exclusion-barrier.txt'; barrier.touch()
                visible('extended-exclusion-barrier', [barrier])
                visible('process-symlink', [])
                public('process-symlink', [], mcp=True)
                public('outside-bootstrap-secret', [], mcp=True)
                link.unlink(); visible('process-symlink', [])
                extended_controls.append('symlink_exclusion_no_target_traversal')
                os.killpg(broker.pid, signal.SIGTERM)
                terminal('interrupted', code=0)
                public('process-created', [initial], 'deferred', mcp=True)
                offline = root / 'process-offline.txt'; offline.touch()
                writer, log = start('actual-restart-after-proved-cleanup', named=True)
                visible('process-offline', [offline])
                public('process-offline', [offline], mcp=True)
                extended_controls.append('actual_restart_clean_rebuild')
            if args.actual_loss:
                assert broker.poll() is None
                os.killpg(broker.pid, signal.SIGKILL)
                broker.communicate(timeout=5); assert broker.returncode == -signal.SIGKILL
                deadline = time.monotonic() + 3
                for pid in worker_pids:
                    while Path('/proc', str(pid)).exists():
                        try:
                            if os.waitpid(pid, os.WNOHANG)[0]: break
                        except ChildProcessError: pass
                        assert time.monotonic() < deadline, ('lost broker worker not reaped', pid)
                        time.sleep(.01)
                missed = root / 'session-loss-missed.txt'; missed.touch()
                origin = time.monotonic()
                while True:
                    result = subprocess.run([str(runtime / 'fsearch-cli'), '--socket', str(endpoint), '--query', 'process-created'], capture_output=True, text=True, timeout=3)
                    assert result.returncode == 0, result.stderr
                    payload = json.loads(result.stdout)
                    if payload['incremental_coverage']['state'] == 'deferred': break
                    assert time.monotonic() - origin < 3, payload
                    time.sleep(.05)
                assert payload['incremental_coverage']['reason'] == 'watcher_lease_expired', payload
                public('process-created', [initial], 'deferred', mcp=True)
                public('session-loss-missed', [], 'deferred')
                recovery = subprocess.run([sys.executable, str(runtime / 'fsearch-service'), 'recover', '--socket', str(database) + '.broker'], capture_output=True, text=True, timeout=3)
                assert recovery.returncode == 0 and json.loads(recovery.stdout)['status'] == 'recovered', recovery
                writer, log = start('actual-session-loss-restart', named=True)
                visible('session-loss-missed', [missed])
                public('session-loss-missed', [missed], mcp=True)
                extended_controls.append('abrupt_session_loss_lease_expiry_clean_reconciliation')
            if args.actual_overflow:
                burst = work / 'outside-overflow'; burst.mkdir()
                os.killpg(broker.pid, signal.SIGSTOP)
                try:
                    for index in range(17000):
                        (burst / str(index)).touch()
                finally:
                    os.killpg(broker.pid, signal.SIGCONT)
                terminal('queue_overflow')
                assert 'queue_overflow' in log.read_text(), log.read_text()
                public('process-created', [initial], 'deferred', mcp=True)
                public('outside-overflow', [], 'deferred')
                print(json.dumps({'status': 'actual_kernel_overflow_pass',
                                  'burst_entries': 17000, 'actual_delivery': 'PASS',
                                  'coverage': 'deferred_queue_overflow',
                                  'boundary_pids_reaped': worker_pids}))
                return 0
            # Root relocation is detected from actual helper health checks even
            # with a quiet ordinary source. Never traverse the replacement.
            outside = work / 'moved-owned'; os.rename(root, outside); root.mkdir()
            (root / 'replacement-secret.txt').touch()
            terminal('parent_identity_changed')
            assert any(reason in log.read_text() for reason in ('parent_identity_changed', 'root_identity_changed', 'admission_failed')), log.read_text()
            public('process-created', [initial], 'deferred', mcp=True)
            public('replacement-secret', [], 'deferred')
            print(json.dumps({'status': 'actual_broker_owned_pass' if actual else 'assembled_broker_fixture_pass',
                              'durable_catalog': args.durable_catalog,
                              'controls': ['named_listener_handoff', 'outside_bootstrap_churn', 'startup', 'create', 'directory_inventory', 'ancestor_rename', 'root_replacement'] + extended_controls + (['file_directory_replacement', 'raw_byte_create_rename', 'normal_heavy_visibility'] if args.actual_edges else []) + ([] if actual else ['inherited_fixture_handoff', 'overflow', 'restart_after_reap']),
                              'actual_delivery': 'PASS' if actual else 'NOT_QUALIFIED', 'adversarial_confinement': 'SEPARATE_RECEIPT_REQUIRED', 'boundary_pids_reaped': worker_pids}))
        finally:
            for process in (broker, server):
                if process:
                    if process.poll() is None: os.killpg(process.pid, signal.SIGTERM)
                    try: process.communicate(timeout=5)
                    except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL); process.communicate(timeout=5)
            for channel in channels: channel.close()
            # Adopt and reap any owned child that raced its supervisor's exit.
            while True:
                try:
                    if os.waitpid(-1, os.WNOHANG)[0] == 0: break
                except ChildProcessError: break
            if denied is not None:
                denied.chmod(0o700)


if __name__ == '__main__': raise SystemExit(main())
