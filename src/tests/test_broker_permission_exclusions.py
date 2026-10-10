"""Real owned DAC exclusions must agree across native refresh and inventory."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

runtime, boundary = map(Path, sys.argv[1:])
os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='fsearch-permission-inventory-') as temporary:
    work = Path(temporary)
    root = work / 'owned'; root.mkdir()
    visible = root / 'permissions-visible.txt'; visible.touch()
    denied = root / 'permissions-denied'; denied.mkdir()
    (denied / 'permissions-hidden.txt').touch()
    denied.chmod(0)
    try:
        database = work / 'snapshot'
        refresh = subprocess.run([sys.executable, str(runtime / 'fsearch-refresh'), 'refresh',
            '--root', str(root), '--database', str(database)], capture_output=True, text=True, timeout=8)
        assert refresh.returncode == 0, refresh.stdout + refresh.stderr
        assert json.loads(refresh.stdout)['scan']['excluded_permissions'] == 1, refresh.stdout
        query = subprocess.run([str(runtime / 'fsearch-cli'), '--database', str(database),
            '--query', 'permissions-'], capture_output=True, text=True, timeout=3)
        assert query.returncode == 0, query.stderr
        result = json.loads(query.stdout)
        assert result['complete'] and not result['truncated'], result
        assert [item['path'] for item in result['results']] == [str(visible)], result
        inventory = subprocess.run([str(boundary), '--root', str(root)], input=b'GI -\n',
            capture_output=True, timeout=3)
        rows = [json.loads(line) for line in inventory.stdout.splitlines()]
        assert inventory.returncode == 0, {'exit_code': inventory.returncode, 'rows': rows}
        assert rows[-1]['status'] == 'inventory_done', rows
        paths = {base64.b64decode(row['path_b64'], validate=True) for row in rows if row['status'] == 'item'}
        assert paths == {b'', os.fsencode(visible.name)}, paths
        print(json.dumps({'result': 'native_refresh_inventory_permission_exclusions_agree',
            'excluded_permissions': 1, 'readable_siblings': 1, 'inventory_items': len(paths)}))
    finally:
        denied.chmod(0o700)
