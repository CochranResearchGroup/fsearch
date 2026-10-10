"""Public native entry classification agrees with a rebuilt owned snapshot."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

runtime, boundary = map(Path, sys.argv[1:])
os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='fsearch-classification-') as temporary:
    work = Path(temporary); root = work / 'owned'; root.mkdir()
    regular = root / 'entry-regular'; regular.touch()
    unreadable = root / 'entry-unreadable-file'; unreadable.touch(); unreadable.chmod(0)
    readable = root / 'entry-readable-directory'; readable.mkdir()
    denied = root / 'entry-denied-directory'; denied.mkdir(mode=0)
    outside = work / 'outside-owned'; outside.mkdir(); (outside / 'secret.fixture').touch()
    link = root / 'entry-symlink'; link.symlink_to(outside, target_is_directory=True)
    fifo = root / 'entry-fifo'; os.mkfifo(fifo, 0o600)
    cases = [(regular, 1), (unreadable, 1), (readable, 2), (denied, 0),
             (link, 0), (fifo, 0), (root / 'entry-missing', 0)]
    try:
        inventory = subprocess.run([str(boundary), '--root', str(root)], input=b'GI -\n', capture_output=True, timeout=3)
        assert inventory.returncode == 0, inventory.stdout + inventory.stderr
        rows = [json.loads(line) for line in inventory.stdout.splitlines()]
        parent = next(row for row in rows if row.get('path_b64') == '')
        commands = [f'S - {parent["fsid"]} {parent["handle_kind"]} {parent["handle"]} {base64.b64encode(os.fsencode(path.name)).decode()}\n' for path, kind in cases]
        probe = subprocess.run([str(boundary), '--root', str(root)], input=('G' + ''.join(commands)).encode(), capture_output=True, timeout=3)
        assert probe.returncode == 0, probe.stdout + probe.stderr
        result = [json.loads(line) for line in probe.stdout.splitlines()]
        assert result[0]['status'] == 'ready', result
        assert result[1:] == [{'status': 'entry_kind', 'kind': kind} for path, kind in cases], result
        # A supplied name cannot bypass the current admitted parent handle.
        wrong_handle = ('0' if parent['handle'][0] != '0' else '1') + parent['handle'][1:]
        rejected = subprocess.run([str(boundary), '--root', str(root)],
            input=f'GS - {parent["fsid"]} {parent["handle_kind"]} {wrong_handle} {base64.b64encode(b"entry-regular").decode()}\n'.encode(),
            capture_output=True, timeout=3)
        assert rejected.returncode == 4, rejected.stdout + rejected.stderr
        rejection = [json.loads(line) for line in rejected.stdout.splitlines()]
        assert rejection[-1] == {'status': 'gap', 'reason': 'parent_identity_changed'}, rejection
        assert not any(row.get('status') == 'entry_kind' for row in rejection), rejection
        database = work / 'snapshot'
        refresh = subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh', '--root', str(root), '--database', str(database)], capture_output=True, timeout=8)
        assert refresh.returncode == 0, refresh.stdout + refresh.stderr
        query = subprocess.run([str(runtime / 'fsearch-cli'), '--database', str(database), '--query', 'entry-'], capture_output=True, text=True, timeout=3)
        assert query.returncode == 0, query.stderr
        expected = json.loads(query.stdout)
        assert expected['complete'] and not expected['truncated'], expected
        assert sorted(item['path'] for item in expected['results']) == sorted(str(path) for path, kind in cases if kind), expected
        print(json.dumps({'result': 'native_entry_eligibility_matches_snapshot', 'cases': len(cases), 'unreadable_regular_filename_retained': True}))
    finally:
        denied.chmod(0o700); unreadable.chmod(0o600)
