#!/usr/bin/env python3
"""Bounded synthetic CLI viability experiment. No real-root indexes or installation."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

binary, fixture, sqlite_python, output = map(Path, sys.argv[1:5])
output.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env.pop('LOCATE_PATH', None)
for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'G_MESSAGES_DEBUG'):
    env.pop(key, None)
with tempfile.TemporaryDirectory(prefix='fsearch-benchmark-') as temporary:
    work = Path(temporary)
    root = work / 'owned-root'
    root.mkdir()
    paths = [root / f'entry{i:05d}.txt' for i in range(10000)]
    for path in paths:
        path.touch()
    snapshot = work / 'snapshot.db'
    subprocess.run([str(fixture), 'build', str(snapshot), str(root)], check=True, env=env, timeout=20)
    snapshot.chmod(0o600)
    path_list = work / 'paths.txt'
    path_list.write_text(''.join(str(path) + '\n' for path in paths))
    locate_db = work / 'plocate.db'
    subprocess.run(['/usr/sbin/plocate-build', '-p', '-l', '1', str(path_list), str(locate_db)],
                   check=True, env=env, capture_output=True, timeout=20)
    locate_db.chmod(0o600)
    sqlite_db = work / 'files.sqlite'
    create = '''from pathlib import Path
import sys
from file_searcher.index import connect
root=Path(sys.argv[2])
con=connect(Path(sys.argv[1]))
con.executemany("INSERT INTO entries(path,name,parent,ext,kind,size,mtime,root_id,windows_path) VALUES (?,?,?,?,?,?,?,?,?)", [(str(root/f"entry{i:05d}.txt"),f"entry{i:05d}.txt",str(root),"txt","file",0,0,"fixture",None) for i in range(10000)])
con.commit()
con.close()
'''
    subprocess.run([str(sqlite_python), '-I', '-c', create, str(sqlite_db), str(root)],
                   check=True, env=env, timeout=20)
    query = 'entry0000'
    sqlite_query = 'import json,sys; from pathlib import Path; from file_searcher.index import search; print(json.dumps(search(Path(sys.argv[1]),sys.argv[2],100)))'
    candidates = {
        'fsearch_cli': [str(binary), '--database', str(snapshot), '--query', query, '--kind', 'files'],
        'file_searcher_sqlite_process': [str(sqlite_python), '-I', '-c', sqlite_query, str(sqlite_db), query],
        'plocate_fixture_only': ['/usr/bin/plocate', '-d', str(locate_db), '-i', '--limit', '100', '--', query],
    }
    expected = {f'entry{i:05d}.txt' for i in range(10)}
    measurements = {}
    for name, command in candidates.items():
        samples, rss = [], []
        for i in range(31):
            rss_file = work / 'rss.txt'
            started = time.perf_counter()
            result = subprocess.run(['/usr/bin/time', '-f', '%M', '-o', str(rss_file), *command],
                                    env=env, capture_output=True, text=True, timeout=15)
            if result.returncode:
                raise RuntimeError((name, result.returncode, result.stderr, result.stdout))
            samples.append((time.perf_counter() - started) * 1000)
            rss.append(int(rss_file.read_text()))
            if name == 'plocate_fixture_only':
                found = {Path(line).name for line in result.stdout.splitlines()}
            else:
                payload = json.loads(result.stdout)
                rows = payload['results'] if isinstance(payload, dict) else payload
                found = {Path(row['path']).name for row in rows}
            assert found == expected, (name, found)
        ordered = sorted(samples[1:])
        measurements[name] = {'first_invocation_ms': samples[0],
                              'subsequent_processes': len(ordered),
                              'p50_ms': statistics.median(ordered), 'p95_ms': ordered[28],
                              'max_process_rss_kib': max(rss), 'results_correct': True}
    warmed = '''import json,sys,time,statistics
from pathlib import Path
from file_searcher.index import search
samples=[]
for i in range(31):
 start=time.perf_counter(); rows=search(Path(sys.argv[1]),sys.argv[2],100); samples.append((time.perf_counter()-start)*1000)
 assert len(rows)==10
print(json.dumps({"p50_ms":statistics.median(samples[1:]),"p95_ms":sorted(samples[1:])[28]}))
'''
    result = subprocess.run([str(sqlite_python), '-I', '-c', warmed, str(sqlite_db), query],
                            env=env, check=True, capture_output=True, text=True, timeout=15)
    measurements['file_searcher_sqlite_in_process'] = json.loads(result.stdout)
    fsearch = measurements['fsearch_cli']
    summary = {'fixture_files': 10000, 'query': query, 'measurements': measurements,
               'fsearch_first_slice_gate_pass': fsearch['p95_ms'] <= 250 and fsearch['max_process_rss_kib'] <= 131072,
               'fsearch_binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
               'fsearch_snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
               'sqlite_python': str(sqlite_python),
               'plocate_version': subprocess.check_output(['/usr/bin/plocate', '--version'], text=True).splitlines()[0],
               'source_base': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
               'limits': 'Separate fresh processes, potentially warm OS caches; tiny flat native fixture; no full MCP, real-root or adoption claim.'}
    output.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
