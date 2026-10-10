"""Reviewed finite activation/rollback coordinator. Do not run before approval.

One filesystem mark, one setup launch, one owned test. No persistent enablement.
Only the setup service receives CAP_SYS_ADMIN; test/service readers have none.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

REPO = Path('/home/ecochran76/worktrees/fsearch-incremental-generations')
PACKET = REPO / 'docs/dev/notes/plan6-activation'
EVIDENCE = REPO / 'docs/dev/notes/plan6-evidence'
STAGED = Path('/home/ecochran76/worktrees/fsearch-broker-candidate/bin')
RUNTIME = Path('/run/fsearch-plan6-qualification')
CONFIG = Path('/etc/fsearch/broker-root.conf')
UNIT_DIRECTORY = Path('/run/systemd/system')
UNITS = ('fsearch-plan6-qualification.slice',
         'fsearch-plan6-qualification-setup.socket',
         'fsearch-plan6-qualification-setup.service',
         'fsearch-plan6-qualification-check.service')


def command(*args, timeout=10, check=True):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=check)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Requires the separately authorized root activation; no effects performed.')
    os.umask(0o022)
    identity = json.loads((PACKET / 'candidate-identity.json').read_text())
    content = {}
    for name, digest in identity['sha256'].items():
        path = Path(name)
        assert path.is_relative_to(STAGED) and not path.is_symlink()
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, 'candidate drift'
        content[path.relative_to(STAGED)] = data
    units = {name: (PACKET / name).read_bytes() for name in UNITS}
    config = (PACKET / 'broker-root.conf').read_bytes()
    for name, data in {**units, 'broker-root.conf': config}.items():
        assert hashlib.sha256(data).hexdigest() == identity['unit_sha256'][str(PACKET / name)], 'packet drift'
    assert not CONFIG.exists() and not CONFIG.is_symlink(), 'preserve existing administrator configuration'
    assert not RUNTIME.exists() and not RUNTIME.is_symlink(), 'preserve existing runtime'
    assert not Path('/run/fsearch/broker.sock').exists(), 'preserve existing endpoint'
    for name in UNITS:
        assert not (UNIT_DIRECTORY / name).exists()
        loaded = command('systemctl', 'show', name, '-p', 'LoadState', '--value').stdout.strip()
        assert loaded == 'not-found', 'preserve existing unit'
    fixture = Path(identity['fixture'])
    assert json.loads((fixture / 'owned-fixture.json').read_text()) == {
        'schema_version': 1, 'owner_uid': 1000, 'root': str(fixture / 'owned')}
    assert not list((fixture / 'owned').iterdir()), 'fixture must remain untouched before the run'
    assert config == ('1000\n' + str(fixture / 'owned') + '\n').encode()
    result = {'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'identity': str(PACKET / 'candidate-identity.json'), 'test_exit': None,
              'scope': '/dev/sdd ext4 filesystem; indexed owned fixture only',
              'root_helper_launch_limit': 1, 'cgroup': None, 'rollback_errors': []}
    installed = []
    made_config_directory = made_socket_directory = False
    old_signals = {}
    def interrupted(signum, frame):
        raise RuntimeError('activation_deadline_or_interrupt')
    try:
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM):
            old_signals[signum] = signal.signal(signum, interrupted)
        signal.alarm(110)
        made_config_directory = not CONFIG.parent.exists()
        made_socket_directory = not Path('/run/fsearch').exists()
        CONFIG.parent.mkdir(mode=0o755, exist_ok=True)
        info = CONFIG.parent.stat()
        assert info.st_uid == 0 and not info.st_mode & 0o022
        RUNTIME.mkdir(mode=0o755)
        for relative, data in content.items():
            path = RUNTIME / 'bin' / relative
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
            path.chmod(0o555 if relative.name.startswith('fsearch-') else 0o444)
        with CONFIG.open('xb') as stream:
            stream.write(config)
        CONFIG.chmod(0o644)
        installed.append(CONFIG)
        for name, data in units.items():
            path = UNIT_DIRECTORY / name
            with path.open('xb') as stream:
                stream.write(data)
            installed.append(path)
        command('systemctl', 'daemon-reload')
        completed = command('systemctl', 'start', UNITS[-1], timeout=60, check=False)
        result['test_exit'] = completed.returncode
        result['unit_result'] = completed.stderr
        group = command('systemctl', 'show', UNITS[0], '-p', 'ControlGroup', '--value').stdout.strip()
        assert group.startswith('/fsearch.slice/'), 'unexpected qualification cgroup'
        cgroup = Path('/sys/fs/cgroup') / group.lstrip('/')
        result['cgroup'] = {'path': group, **{name: (cgroup / name).read_text().strip()
            for name in ('memory.current', 'memory.peak', 'memory.max', 'memory.swap.current', 'memory.swap.peak', 'memory.swap.max')}}
    except Exception as error:
        result['error'] = str(error)
    finally:
        signal.alarm(0)
        for signum in old_signals:
            signal.signal(signum, signal.SIG_IGN)
        for name in reversed(UNITS):
            try:
                stopped = command('systemctl', 'stop', name, check=False)
                if stopped.returncode:
                    result['rollback_errors'].append({'unit': name, 'error': stopped.stderr})
            except Exception as error:
                result['rollback_errors'].append({'unit': name, 'error': str(error)})
        log = command('journalctl', '--no-pager', '-o', 'cat', '-u', UNITS[-1], '-u', UNITS[-2], check=False)
        (EVIDENCE / 'm3-actual-owned-output.txt').write_text(log.stdout)
        for path in reversed(installed):
            try:
                path.unlink()
            except Exception as error:
                result['rollback_errors'].append({'path': str(path), 'error': str(error)})
        if RUNTIME.exists():
            shutil.rmtree(RUNTIME)
        if made_config_directory:
            try: CONFIG.parent.rmdir()
            except OSError: pass
        if made_socket_directory:
            try: Path('/run/fsearch').rmdir()
            except OSError: pass
        command('systemctl', 'daemon-reload', check=False)
        result['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        result['units_after_rollback'] = {name: command('systemctl', 'show', name, '-p', 'ActiveState', '-p', 'MainPID', check=False).stdout for name in UNITS}
        result['runtime_removed'] = not RUNTIME.exists()
        result['configuration_removed'] = not CONFIG.exists()
        (EVIDENCE / 'm3-actual-owned-activation.json').write_text(json.dumps(result, indent=2) + '\n')
        for name in ('m3-actual-owned-output.txt', 'm3-actual-owned-activation.json'):
            os.chown(EVIDENCE / name, 1000, 1000)
        for signum, handler in old_signals.items():
            signal.signal(signum, handler)
    return 0 if result['test_exit'] == 0 and not result['rollback_errors'] and 'error' not in result else 1


if __name__ == '__main__':
    raise SystemExit(main())
