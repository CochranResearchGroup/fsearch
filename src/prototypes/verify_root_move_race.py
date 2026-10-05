"""Pause descendant admission, move an owned subtree, and trace both workers."""
import argparse
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, default=Path('/tmp/fsearch-warm-release-build/src'))
    parser.add_argument('--fault', type=Path, default=Path('/tmp/fsearch-warm-release-build/src/tests/librefresh_fault_fixture.so'))
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args(); runtime = args.runtime.resolve(); evidence = args.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True); receipts = []
    for kind in ('monitor', 'refresh'):
        with tempfile.TemporaryDirectory(prefix='fsearch-move-race-owned-') as temporary:
            work = Path(temporary); root = work/'approved'; root.mkdir()
            nested = root/'nested'; nested.mkdir(); (nested/'race-probe.pdf').touch()
            stage = work/'stage'; stage.mkdir(mode=0o700)
            notify_read, notify_write = os.pipe(); resume_read, resume_write = os.pipe()
            env = dict(os.environ, LD_PRELOAD=str(args.fault.resolve()),
                       FSEARCH_FIXTURE_RACE_NOTIFY_FD=str(notify_write),
                       FSEARCH_FIXTURE_RACE_RESUME_FD=str(resume_read))
            command = [str(runtime/('fsearch-monitor-worker' if kind == 'monitor' else 'fsearch-refresh-worker')),
                       '--root', str(root)]
            if kind == 'refresh': command += ['--output', str(stage/'candidate.db')]
            trace = evidence/(kind+'.trace')
            process = subprocess.Popen(['strace', '-f', '-yy', '-e', 'trace=%file,getdents64', '-o', str(trace), *command],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       env=env, pass_fds=(notify_write, resume_read))
            os.close(notify_write); os.close(resume_read)
            try:
                process.stdin.write(b'G'); process.stdin.flush()
                assert select.select([notify_read], [], [], 3)[0], 'race gate not reached'
                assert os.read(notify_read, 1) == b'B'
                outside = work/'outside'; nested.rename(outside); os.write(resume_write, b'G')
                stdout, stderr = process.communicate(timeout=5)
                (evidence/(kind+'.stdout.txt')).write_bytes(stdout)
                (evidence/(kind+'.stderr.txt')).write_bytes(stderr)
                raw = trace.read_text(); probed = str(outside/'race-probe.pdf') in raw
                receipt = {'worker': kind, 'exit': process.returncode, 'outside_child_descriptor_observed': probed,
                           'owned_fixtures_only': True, 'candidate_exists': (stage/'candidate.db').exists(), 'trace': str(trace)}
                receipts.append(receipt)
                assert not probed, receipt
                assert process.returncode != 0 and not receipt['candidate_exists'], receipt
                if kind == 'monitor': assert json.loads(stdout)['error']['code'] == 'coverage_incomplete'
            finally:
                if process.poll() is None: process.kill(); process.communicate(timeout=3)
                os.close(notify_read); os.close(resume_write)
    (evidence/'verification.json').write_text(json.dumps(receipts, indent=2)+'\n')
    print('Both workers reject the moved subtree without outside descendant access')


if __name__ == '__main__': main()
