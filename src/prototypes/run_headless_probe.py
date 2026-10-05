#!/usr/bin/env python3
"""Research experiment, not production tests or a service. Use a prebuilt probe."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

binary = Path(sys.argv[1]).resolve()
evidence = Path(sys.argv[2]).resolve()
evidence.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'G_MESSAGES_DEBUG'):
    env.pop(name, None)
with tempfile.TemporaryDirectory(prefix='fsearch-prototype-') as tmp:
    work = Path(tmp)
    root = work / 'PROTOTYPE-wipe-me-root'
    root.mkdir()
    names = ['invoice-one.pdf', 'invoice-two.pdf', 'notes.txt', 'quote"file.pdf', 'line\nbreak.pdf']
    for name in names:
        (root / name).write_text('synthetic fixture\n')
    database = work / 'PROTOTYPE-wipe-me.db'
    subprocess.run([str(binary), 'build', str(database), str(root)], env=env, check=True, timeout=15)
    shutil.rmtree(root)
    receipts = []
    for label, query, limit, cancelled, expected in [
        ('names', 'invoice', '10', False, 2),
        ('limited', 'invoice', '1', False, 2),
        ('extension', 'ext:pdf', '10', False, 4),
        ('empty', 'missing-needle', '10', False, 0),
        ('cancelled', 'invoice', '10', True, 0),
    ]:
        trace = work / f'{label}.trace'
        args = [str(binary), 'query', str(database), query, limit]
        if cancelled:
            args.append('cancel')
        result = subprocess.run(['strace', '-f', '-e', 'trace=%file', '-o', str(trace), *args],
                                env=env, capture_output=True, text=True, check=True, timeout=15)
        response = json.loads(result.stdout)
        assert response['total'] == expected, (label, response)
        assert response['complete'] == (not cancelled), (label, response)
        assert len(response['results']) == min(expected, int(limit)), (label, response)
        probes = [line for line in trace.read_text().splitlines() if str(root) in line]
        assert not probes, (label, probes)
        receipts.append({'case': label, 'response': response, 'indexed_root_file_syscalls': len(probes)})
        (evidence / f'{label}.trace').write_text(trace.read_text().replace(tmp, '<fixture>'))
    # Negative control: existing contenttype syntax really probes indexed paths.
    trace = work / 'contenttype.trace'
    control = subprocess.run(['strace', '-f', '-e', 'trace=%file', '-o', str(trace),
                              str(binary), 'query', str(database), 'contenttype:pdf', '10'],
                             env=env, capture_output=True, text=True, check=True, timeout=15)
    control_probes = [line for line in trace.read_text().splitlines() if str(root) in line]
    assert control_probes, 'Tracing must detect known live metadata probes'
    (evidence / 'contenttype.trace').write_text(trace.read_text().replace(tmp, '<fixture>'))
    missing = subprocess.run([str(binary), 'query', str(work / 'missing.db'), 'invoice'],
                             env=env, capture_output=True, text=True, timeout=15)
    assert missing.returncode == 1 and not missing.stdout
    summary = {'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'display_variables_removed': True, 'fixture_root_deleted_before_queries': True,
               'cases': receipts, 'load_failure_no_fallback': True,
               'gtk_dependency_removed': False,
               'contenttype_negative_control_indexed_root_syscalls': len(control_probes),
               'limits': 'Output bounded, engine still collects all matches; short synthetic runs only.'}
    text = json.dumps(summary, indent=2).replace(tmp, '<fixture>') + '\n'
    (evidence / 'summary.json').write_text(text)
    print(text)
