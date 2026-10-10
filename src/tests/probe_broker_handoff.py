#!/usr/bin/env python3
"""Minimal owned-root handoff probe. Default inspection never connects.

--execute creates one event source through the installed fixed helper, transfers
and closes it without reading any event bytes or modifying the fixture.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fsearch_broker_source import HANDOFF, MAGIC, receive_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owned-fixture', type=Path, required=True)
    parser.add_argument('--expect-version', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    fixture = args.owned_fixture
    manifest = json.loads((fixture / 'owned-fixture.json').read_text())
    root = fixture / 'owned'
    if not fixture.is_absolute() or fixture.is_symlink() or root.is_symlink() or not root.is_dir():
        raise ValueError('invalid owned fixture')
    if fixture.stat().st_uid != os.geteuid() or manifest != {'schema_version': 1, 'owner_uid': os.geteuid(), 'root': str(root)}:
        raise ValueError('fixture admission mismatch')
    receipt_path = Path('/usr/local/libexec/fsearch-broker/installation.json')
    installed = json.loads(receipt_path.read_text())
    version_matches = installed['version'] == args.expect_version
    if installed['uid'] != os.geteuid() or installed['root'] != str(root):
        raise ValueError('installed admission mismatch')
    for name, entry in installed['files'].items():
        path = Path(name)
        status = path.stat()
        if path.is_symlink() or status.st_uid != 0 or status.st_mode & 0o022 or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('installed custody mismatch')
    result = {'mode': 'execute' if args.execute else 'inspect', 'version_matches': version_matches,
              'source_transferred': False, 'event_bytes_read': 0, 'fixture_mutations': 0}
    if not args.execute:
        print(json.dumps(result))
        return 0
    if not version_matches:
        raise ValueError('diagnostic helper not installed; no connection attempted')
    if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0):
        raise OSError('cannot set NoNewPrivileges')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    if any(int(status[key].strip(), 16) for key in ('CapEff', 'CapPrm', 'CapAmb')):
        raise ValueError('probe must have no capabilities')
    pinned = root.stat()
    generation = 1
    token = secrets.token_bytes(32)
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC) as channel:
        channel.settimeout(5)
        channel.connect('/run/fsearch/broker.sock')
        _, uid, _ = struct.unpack('3i', channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != 0:
            raise ValueError('administrator listener required')
        request = HANDOFF.pack(MAGIC, generation, token, pinned.st_dev, pinned.st_ino)
        if channel.send(request) != len(request):
            raise ValueError('short request')
        fd = receive_source(channel, peer_uid=0, generation=generation, token=token,
                            root_identity=(pinned.st_dev, pinned.st_ino), source_kind='fanotify')
        try:
            result['source_transferred'] = True
        finally:
            os.close(fd)
    result['source_closed'] = True
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
