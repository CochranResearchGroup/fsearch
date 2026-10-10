"""Descriptor-source -> production catalog -> normal CLI/fresh MCP.

Synthetic source batches accompany owned mutations. No claim of actual kernel
delivery or production containment follows from the fixture admission map.
"""
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import runpy
import signal
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fsearch_fanotify_events import BootstrapSession, Gap, CREATE, DELETE, RENAME, ONDIR, Handle
from fsearch_broker_source import CatalogBroker, SourceReader, send_source, receive_source
from fsearch_broker_admission import DirectoryMap, ContainedAdmission
from test_fanotify_events import event, info


def main():
    runtime, frontend = map(Path, sys.argv[1:3])
    boundary_executable = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    incremental = runpy.run_path(str(runtime / 'fsearch-incremental'))
    python = frontend / '.venv/bin/python'
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='fsearch-broker-catalog-') as tmp:
        work = Path(tmp); root = work / 'owned'; root.mkdir()
        (root / 'initial.txt').touch()
        database = work / 'snapshot'; endpoint = work / 'q.sock'
        subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], check=True, capture_output=True, timeout=10)
        config = work / 'config.json'
        config.write_text(json.dumps({'roots': [], 'aliases': [], 'db_path': str(work / 'sqlite'),
            'fsearch_command': str(runtime / 'fsearch-cli'), 'fsearch_database': str(database), 'fsearch_socket': str(endpoint)}))
        env = {**os.environ, 'FILE_SEARCHER_CONFIG': str(config), 'FILE_SEARCHER_DB': str(work / 'sqlite'),
               'FILE_SEARCHER_STATE_DIR': str(work / 'state'), 'PYTHONDONTWRITEBYTECODE': '1'}
        server = subprocess.Popen([sys.executable, str(runtime / 'fsearch-service'), 'serve', '--database', str(database), '--socket', str(endpoint)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
        client = reader = admission = directory_map = boundary_directory = None
        source, writer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        source.setblocking(False)
        transport_a, transport_b = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            deadline = time.monotonic() + 5
            while not endpoint.exists():
                assert server.poll() is None and time.monotonic() < deadline
                time.sleep(.01)
            token = os.urandom(32)
            send_source(transport_a, source.fileno(), peer_uid=os.geteuid(), generation=1, token=token)
            received = receive_source(transport_b, peer_uid=os.geteuid(), generation=1, token=token)
            source.close(); transport_a.close(); transport_b.close()
            session = BootstrapSession(1)
            reader = SourceReader(received, session)
            client = incremental['CatalogClient'](str(endpoint)); client.reset()
            root_id = client.lookup(os.fsencode(root))['entry_id']
            parent_paths = {root_id: b''}
            validate = lambda handle, generation: root_id if handle.opaque == b'inside' else None
            inventory = None
            if boundary_executable:
                lifecycle = incremental['lifecycle']
                boundary_directory = lifecycle.PrivateDirectory(str(work / 'boundary'))
                boundary_directory.lock(); lifecycle.reconcile(boundary_directory)
                owner = incremental['ContinuousWatcher'](boundary_directory, str(root))
                directory_map = DirectoryMap()
                admission = ContainedAdmission(owner, boundary_executable, client, os.fsencode(root), 1, directory_map)
                admission.arm(); admission.inventory(root_id, os.fsencode(root), baseline=True)
                validate, parent_paths, inventory = admission.validate, directory_map, admission.inventory
            session.finish_baseline(1)
            broker = CatalogBroker(reader, client, os.fsencode(root), validate, parent_paths, inventory)
            assert broker.pump() and session.state == 'watching'

            def parent_info(role, name, parent=root_id):
                if directory_map:
                    row = directory_map.database.execute('SELECT identity FROM directories WHERE id=?', (parent,)).fetchone()[0]
                    import struct
                    identity = Handle(row[:8], struct.unpack('!i', row[8:12])[0], row[12:])
                    return info(role, opaque=identity.opaque, name=name, fsid=identity.fsid, kind=identity.kind)
                return info(role, name=name)

            def cli(query, expected, coverage='watching'):
                result = subprocess.run([str(python), '-m', 'file_searcher.cli', 'find', '--no-everything', '--no-locate', query], cwd=frontend, env=env, capture_output=True, text=True, timeout=5)
                assert result.returncode == 0, result.stderr
                payload = json.loads(result.stdout)
                assert sorted(row['path'] for row in payload['results']) == sorted(map(str, expected)), payload
                backend = payload['backends']['fsearch']
                assert backend['complete'] and backend['incremental_coverage']['state'] == coverage, payload
                return payload

            async def fresh_mcp(query, expected, coverage='watching'):
                # Use frontend's actual installed MCP dependency environment.
                script = '''import asyncio,json,os,sys
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
 async with stdio_client(StdioServerParameters(command=sys.executable,args=['-m','file_searcher.mcp_server'],env=dict(os.environ))) as (reader,writer):
  async with ClientSession(reader,writer) as session:
   await session.initialize()
   result=await session.call_tool('file_searcher_find',{'query':sys.argv[1],'use_everything':False,'use_locate':False})
   assert not result.isError
   print(json.dumps(result.structuredContent))
asyncio.run(main())
'''
                result = subprocess.run([str(python), '-c', script, query], cwd=frontend, env=env, capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, result.stderr
                payload = json.loads(result.stdout)
                assert sorted(row['path'] for row in payload['results']) == sorted(map(str, expected)), payload
                assert payload['backends']['fsearch']['incremental_coverage']['state'] == coverage, payload
                assert payload['backends']['fsearch']['complete'], payload

            created = root / 'broker-visible.pdf'; started = time.monotonic(); created.touch()
            writer.send(event(CREATE, [parent_info(2, os.fsencode(created.name)), info(1)])); assert broker.pump()
            cli('broker-visible', [created]); asyncio.run(fresh_mcp('broker-visible', [created]))
            synthetic_create_seconds = time.monotonic() - started
            renamed = root / 'broker-renamed.pdf'; os.rename(created, renamed)
            writer.send(event(RENAME, [parent_info(10, os.fsencode(created.name)), parent_info(12, os.fsencode(renamed.name)), info(1)])); assert broker.pump()
            cli('broker-visible', []); cli('broker-renamed', [renamed])
            linked = root / 'broker-linked.pdf'; os.link(renamed, linked)
            writer.send(event(CREATE, [parent_info(2, os.fsencode(linked.name)), info(1)])); assert broker.pump()
            cli('pdf', [renamed, linked])
            renamed.unlink(); writer.send(event(DELETE, [parent_info(2, os.fsencode(renamed.name)), info(1)])); assert broker.pump()
            cli('pdf', [linked]); asyncio.run(fresh_mcp('pdf', [linked]))
            writer.send(event(CREATE, [info(2, b'outside', b'outside-secret'), info(1)])); assert broker.pump()
            cli('outside-secret', [])
            if admission:
                nested = root / 'broker-directory'; (nested / 'deep').mkdir(parents=True)
                child = nested / 'deep' / 'broker-child.txt'; child.touch()
                writer.send(event(CREATE | ONDIR, [parent_info(2, os.fsencode(nested.name)), info(1)])); assert broker.pump()
                cli('broker-child', [child]); asyncio.run(fresh_mcp('broker-child', [child]))
                nested_id = client.lookup(os.fsencode(nested))['entry_id']
                deep_id = client.lookup(os.fsencode(nested / 'deep'))['entry_id']
                old_deep_identity = directory_map.database.execute('SELECT identity FROM directories WHERE id=?', (deep_id,)).fetchone()[0]
                moved = root / 'broker-moved'; os.rename(nested, moved)
                writer.send(event(RENAME | ONDIR, [parent_info(10, os.fsencode(nested.name)), parent_info(12, os.fsencode(moved.name)), info(1)])); assert broker.pump()
                cli('broker-child', [moved / 'deep' / child.name])
                new_child = moved / 'deep' / 'broker-after-move.txt'; new_child.touch()
                writer.send(event(CREATE, [parent_info(2, os.fsencode(new_child.name), deep_id), info(1)])); assert broker.pump()
                cli('broker-after-move', [new_child])
                outside = work / 'outside-moved'; os.rename(moved, outside)
                writer.send(event(RENAME | ONDIR, [parent_info(10, os.fsencode(moved.name)), info(12, b'outside', b'outside-secret'), info(1)])); assert broker.pump()
                assert directory_map.get(deep_id) is None and directory_map.get(nested_id) is None
                cli('broker-child', []); cli('broker-after-move', [])
                assert directory_map.database.execute('SELECT id FROM directories WHERE identity=?', (old_deep_identity,)).fetchone() is None
            writer.send(event()[:12])
            try: broker.pump()
            except Gap: pass
            else: raise AssertionError('malformed source accepted')
            cli('broker-linked', [linked], 'deferred'); asyncio.run(fresh_mcp('broker-linked', [linked], 'deferred'))
            print(json.dumps({'status': 'synthetic_wiring_pass', 'native_inventory': bool(admission), 'synthetic_create_cli_plus_mcp_seconds': synthetic_create_seconds,
                              'actual_delivery': 'NOT_QUALIFIED', 'containment': 'NOT_QUALIFIED'}))
        finally:
            if reader: reader.close()
            if admission: admission.close()
            if directory_map: directory_map.close()
            if boundary_directory: boundary_directory.close()
            if client: client.close()
            for channel in (source, writer, transport_a, transport_b): channel.close()
            if server.poll() is None: os.killpg(server.pid, signal.SIGTERM)
            try: server.communicate(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(server.pid, signal.SIGKILL); server.communicate(timeout=5)
            assert server.poll() is not None


if __name__ == '__main__':
    main()
