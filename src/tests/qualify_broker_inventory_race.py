"""Frozen owned ancestry-race diagnostic; never touches personal roots.

Reports export and metadata confinement independently. A deferred outcome does
not erase a demonstrated outside read. This is not a privileged fanotify run.
"""
import json
import argparse
import base64
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('boundary', type=Path)
    parser.add_argument('fixture', type=Path)
    parser.add_argument('--pre-moved', action='store_true')
    args = parser.parse_args()
    boundary, fixture = args.boundary, args.fixture
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='fsearch-broker-race-') as temporary:
        work = Path(temporary); root = work / 'owned'; victim = root / 'victim'
        victim.mkdir(parents=True); (victim / 'inside.txt').touch()
        moved = work / 'outside-owned-fixture'; trace = work / 'trace'
        if args.pre_moved:
            os.rename(victim, moved)
            (moved / 'outside-secret.fixture').touch()
        progress_read, progress_write = os.pipe()
        resume_read, resume_write = os.pipe()
        env = {**os.environ, 'LD_PRELOAD': str(fixture),
               'FSEARCH_BROKER_FIXTURE_INODE': str((moved if args.pre_moved else victim).stat().st_ino),
               'FSEARCH_BROKER_FIXTURE_PROGRESS_FD': str(progress_write),
               'FSEARCH_BROKER_FIXTURE_RESUME_FD': str(resume_read)}
        child = subprocess.Popen(['strace', '--kill-on-exit', '-f', '-yy', '-s', '4096',
            '-e', 'trace=getdents64,openat,openat2,newfstatat,statx', '-o', str(trace),
            str(boundary), '--root', str(root)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            pass_fds=(progress_write, resume_read), start_new_session=True)
        os.close(progress_write); os.close(resume_read)
        try:
            child.stdin.write(b'GI dmljdGlt\n' if args.pre_moved else b'GI -\n'); child.stdin.flush()
            if not args.pre_moved:
                assert select.select([progress_read], [], [], 3)[0], 'fixture did not reach read boundary'
                assert os.read(progress_read, 1) == b'P'
                os.rename(victim, moved)
                (moved / 'outside-secret.fixture').touch()
                os.write(resume_write, b'R')
            output, error = child.communicate(timeout=5)
            assert child.returncode == 4, (child.returncode, output, error)
            rows = [json.loads(line) for line in output.splitlines()]
            assert rows[-1]['status'] == 'gap', rows
            outside_export = any(b'outside-secret.fixture' in base64.b64decode(row['path_b64'], validate=True)
                                 for row in rows if row.get('status') == 'item')
            assert not outside_export and b'outside-secret.fixture' not in error, (output, error)
            lines = trace.read_text().splitlines()
            outside_reads = [line for line in lines if 'getdents64(' in line and str(moved) in line]
            secondary = [line for line in lines if 'outside-secret.fixture' in line
                         and any(call in line for call in ('openat(', 'openat2(', 'newfstatat(', 'statx('))]
            assert not secondary, secondary
            assert len(outside_reads) == (0 if args.pre_moved else 1), outside_reads
            print(json.dumps({'status': 'diagnostic_complete', 'fixture_reached': not args.pre_moved,
                'case': 'outside_before_admission' if args.pre_moved else 'move_after_admission',
                'source_exit': child.returncode, 'deferred_control': 'PASS',
                'outside_export': 'FAIL' if outside_export else 'PASS',
                'outside_metadata_read': 'FAIL' if outside_reads else 'PASS',
                'outside_secondary_probe': 'PASS',
                'current_contract': 'PASS',
                'contract_disposition': 'rejected_before_read' if args.pre_moved else 'accepted_bounded_transition',
                'outside_read_count': len(outside_reads),
                'trace_evidence': [line.replace(str(work), '<owned-fixture>') for line in outside_reads]}))
        finally:
            if child.poll() is None: os.killpg(child.pid, signal.SIGKILL)
            child.communicate(timeout=5)
            for fd in (progress_read, resume_write): os.close(fd)


if __name__ == '__main__': main()
