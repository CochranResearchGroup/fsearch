#!/usr/bin/env python3
"""Stage/install/remove the fixed FSearch setup helper. Never activates a mark."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

SOCKET = 'fsearch-broker-setup.socket'
SERVICE = 'fsearch-broker-setup.service'
BASE = Path('/usr/local/libexec/fsearch-broker')
CONFIG = Path('/etc/fsearch/broker-root.conf')
UNITS = Path('/etc/systemd/system')
RECEIPT = BASE / 'installation.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stage(binary, uid, gid, root, bundle):
    if uid <= 0 or gid <= 0 or not root.is_absolute() or '\n' in str(root):
        raise ValueError('requires non-root account and one absolute root')
    data = binary.read_bytes()
    if not data.startswith(b'\x7fELF'):
        raise ValueError('setup must be a built ELF executable')
    version = digest(data)
    executable = BASE / version / 'fsearch-broker-setup'
    files = {str(executable): data,
             str(CONFIG): f'{uid}\n{root}\n'.encode(),
             str(UNITS / SOCKET): f'''[Unit]
Description=FSearch privileged event-source setup endpoint
[Socket]
ListenSequentialPacket=/run/fsearch/broker.sock
SocketUser={uid}
SocketGroup={gid}
SocketMode=0600
DirectoryMode=0755
Service={SERVICE}
RemoveOnStop=yes
[Install]
WantedBy=sockets.target
'''.encode(),
             str(UNITS / SERVICE): f'''[Unit]
Description=FSearch bounded privileged event-source setup
StartLimitIntervalSec=60
StartLimitBurst=3
[Service]
Type=oneshot
User={uid}
Group={gid}
ExecStart={executable} --listener-fd 3
CapabilityBoundingSet=CAP_SYS_ADMIN
AmbientCapabilities=CAP_SYS_ADMIN
NoNewPrivileges=yes
Restart=no
TimeoutStartSec=5
TimeoutStopSec=5
LimitCORE=0
MemoryMax=64M
MemorySwapMax=0
TasksMax=8
StandardOutput=null
StandardError=journal
'''.encode()}
    bundle.mkdir()
    metadata = {'schema_version': 1, 'version': version, 'uid': uid, 'gid': gid,
                'root': str(root), 'activation': 'disabled', 'files': {}}
    for index, (target, content) in enumerate(files.items()):
        name = f'payload-{index}'
        (bundle / name).write_bytes(content)
        metadata['files'][target] = {'payload': name, 'sha256': digest(content),
                                    'mode': 0o555 if target == str(executable) else 0o644}
    (bundle / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


def load(bundle):
    m = json.loads((bundle / 'manifest.json').read_text())
    version = m['version']
    if len(version) != 64 or any(c not in '0123456789abcdef' for c in version):
        raise ValueError('invalid version')
    expected = {str(BASE / version / 'fsearch-broker-setup'), str(CONFIG),
                str(UNITS / SOCKET), str(UNITS / SERVICE)}
    if set(m['files']) != expected or m['schema_version'] != 1:
        raise ValueError('unexpected installation surface')
    contents = {}
    for target, info in m['files'].items():
        name = info['payload']
        if Path(name).name != name or (bundle / name).is_symlink():
            raise ValueError('invalid payload')
        data = (bundle / name).read_bytes()
        if digest(data) != info['sha256'] or info['mode'] not in (0o555, 0o644):
            raise ValueError('payload drift')
        contents[target] = data
    if digest(contents[str(BASE / version / 'fsearch-broker-setup')]) != version:
        raise ValueError('binary/version mismatch')
    return m, contents


def destination(prefix, absolute):
    return prefix / str(absolute).lstrip('/')


def safe_parent(path, prefix, created):
    missing = []
    cursor = path.parent
    while cursor != prefix:
        if cursor.is_symlink():
            raise ValueError(f'symlink parent: {cursor}')
        if cursor.exists():
            st = cursor.stat()
            if st.st_uid != os.geteuid() or st.st_mode & 0o022:
                raise ValueError(f'untrusted parent: {cursor}')
        else:
            missing.append(cursor)
        cursor = cursor.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        created.append(directory)
        directory.chmod(0o755)


def install(bundle, prefix, listen=False):
    m, contents = load(bundle)
    paths = [destination(prefix, p) for p in m['files']]
    receipt = destination(prefix, RECEIPT)
    if any(p.exists() or p.is_symlink() for p in paths + [receipt]):
        raise ValueError('existing installation/configuration; refusing overwrite')
    if prefix == Path('/'):
        for unit in (SOCKET, SERVICE):
            result = subprocess.run(['systemctl', 'show', unit, '-p', 'LoadState', '--value'],
                                    check=True, capture_output=True, text=True, timeout=10)
            if result.stdout.strip() != 'not-found':
                raise ValueError('existing system unit')
    created = []
    written = []
    try:
        for target, data in contents.items():
            path = destination(prefix, target)
            safe_parent(path, prefix, created)
            with path.open('xb') as stream:
                written.append(path)
                stream.write(data)
            path.chmod(m['files'][target]['mode'])
        m['socket_activation'] = {'requested': listen, 'result': 'not_attempted'}
        if prefix == Path('/'):
            subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=10)
            if listen:
                subprocess.run(['systemctl', 'enable', '--now', SOCKET], check=True, timeout=15)
                m['socket_activation']['result'] = 'enable_and_start_succeeded'
        # This records command results, not a claim that an event mark exists.
        m.pop('activation', None)
        safe_parent(receipt, prefix, created)
        m['created_directories'] = [str(p.relative_to(prefix)) for p in created]
        with receipt.open('x') as stream:
            written.append(receipt)
            json.dump(m, stream, indent=2)
            stream.write('\n')
        receipt.chmod(0o644)
    except BaseException as failure:
        cleanup_errors = []
        def cleanup(action):
            try:
                action()
            except Exception as error:
                cleanup_errors.append(str(error))
        if prefix == Path('/') and listen:
            cleanup(lambda: subprocess.run(['systemctl', 'disable', '--now', SOCKET], check=True, timeout=15))
            cleanup(lambda: subprocess.run(['systemctl', 'stop', SERVICE], check=True, timeout=10))
        for path in reversed(written):
            cleanup(path.unlink)
        for directory in reversed(created):
            cleanup(directory.rmdir)
        if prefix == Path('/'):
            cleanup(lambda: subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=10))
        if cleanup_errors:
            failure.add_note('Rollback incomplete: ' + '; '.join(cleanup_errors))
        raise
    return m


def remove(prefix):
    receipt = destination(prefix, RECEIPT)
    m = json.loads(receipt.read_text())
    # Validate all custody before stopping anything or deleting any file.
    version = m['version']
    allowed = {str(BASE / version / 'fsearch-broker-setup'), str(CONFIG),
               str(UNITS / SOCKET), str(UNITS / SERVICE)}
    if len(version) != 64 or any(c not in '0123456789abcdef' for c in version) or set(m['files']) != allowed:
        raise ValueError('invalid installed receipt')
    for target, info in m['files'].items():
        path = destination(prefix, target)
        if path.is_symlink() or digest(path.read_bytes()) != info['sha256']:
            raise ValueError('installed drift; preserve and reconcile')
    directories = []
    for name in m['created_directories']:
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('invalid receipt directory')
        directories.append(prefix / relative)
    if prefix == Path('/'):
        subprocess.run(['systemctl', 'disable', '--now', SOCKET], check=True, timeout=15)
        subprocess.run(['systemctl', 'stop', SERVICE], check=True, timeout=10)
    for target in reversed(list(m['files'])):
        destination(prefix, target).unlink()
    receipt.unlink()
    for directory in reversed(directories):
        try:
            directory.rmdir()
        except OSError:
            pass  # Preserve directories used by other software.
    if prefix == Path('/'):
        subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=10)
    return {'removed_version': version, 'reader_note': 'stop reader first to close its event descriptor'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    p = commands.add_parser('stage')
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--uid', type=int, required=True)
    p.add_argument('--gid', type=int, required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--bundle', type=Path, required=True)
    for action in ('install', 'remove'):
        p = commands.add_parser(action)
        p.add_argument('--destdir', type=Path, default=Path('/'))
        if action == 'install':
            p.add_argument('--bundle', type=Path, required=True)
            p.add_argument('--listen', action='store_true', help='enable/start socket; no mark until reader connects')
    args = parser.parse_args()
    if args.action == 'stage':
        result = stage(args.binary, args.uid, args.gid, args.root, args.bundle)
    else:
        prefix = args.destdir.absolute()
        if prefix == Path('/') and os.geteuid() != 0:
            raise SystemExit('Administrator install/remove required; no effects performed.')
        if prefix != Path('/') and (not prefix.is_dir() or prefix.is_symlink()):
            raise ValueError('destdir must be an existing owned directory')
        result = install(args.bundle, prefix, args.listen) if args.action == 'install' else remove(prefix)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
