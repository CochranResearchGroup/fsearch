"""Bounded private directory identity map and contained-worker adapter.

This connects real rooted inventory/validation to broker admission. It does not
qualify adversarial ancestry races or actual fanotify delivery by itself.
"""
import base64
import os
import sqlite3
import struct
import time

from fsearch_fanotify_events import Gap, Handle


class DirectoryMap:
    """Temporary SQLite parent-linked map; no full-path dictionary or watches.

    Temporary map storage is not an accepted recovery checkpoint. Its kernel
    cache and bounded pager remain part of the service resource accounting.
    """
    def __init__(self, *, max_directories=800000):
        if type(max_directories) is not int or not 1 <= max_directories <= 800000:
            raise ValueError('map_configuration')
        self.database = sqlite3.connect('')
        self.database.execute('PRAGMA cache_size=-4096')
        self.database.execute('PRAGMA mmap_size=0')
        self.database.execute('PRAGMA temp_store=FILE')
        self.database.execute('CREATE TABLE directories(id INTEGER PRIMARY KEY, parent INTEGER, name BLOB NOT NULL, identity BLOB UNIQUE NOT NULL)')
        self.database.execute('CREATE INDEX directory_parent ON directories(parent)')
        self.max_directories = max_directories
        self.count = 0

    def close(self):
        self.database.close()

    @staticmethod
    def key(handle):
        if not isinstance(handle, Handle) or len(handle.fsid) != 8 or not 1 <= len(handle.opaque) <= 128 or type(handle.kind) is not int or not -2**31 <= handle.kind < 2**31:
            raise Gap('map_handle_invalid')
        return handle.fsid + struct.pack('!i', handle.kind) + handle.opaque

    def admitted(self, handle):
        row = self.database.execute('SELECT id FROM directories WHERE identity=?', (self.key(handle),)).fetchone()
        return row[0] if row else None

    def identity(self, entry):
        row = self.database.execute('SELECT identity FROM directories WHERE id=?', (entry,)).fetchone()
        if row is None:
            raise Gap('map_entry_missing')
        data = row[0]
        return Handle(data[:8], struct.unpack('!i', data[8:12])[0], data[12:])

    def identities(self):
        for (data,) in self.database.execute('SELECT identity FROM directories'):
            yield Handle(data[:8], struct.unpack('!i', data[8:12])[0], data[12:])

    def add(self, handle, entry, parent, name):
        if type(entry) is not int or entry < 0 or parent is not None and (type(parent) is not int or parent < 0) or not isinstance(name, bytes) or b'/' in name or b'\0' in name or len(name) > 255 or name in (b'.', b'..') or parent is None and name != b'' or parent is not None and not name:
            raise Gap('map_entry_invalid')
        if parent == entry or parent is not None and self.database.execute('SELECT 1 FROM directories WHERE id=?', (parent,)).fetchone() is None:
            raise Gap('map_parent_missing')
        key = self.key(handle)
        existing = self.database.execute('SELECT parent,name,identity FROM directories WHERE id=?', (entry,)).fetchone()
        if existing:
            if existing != (parent, name, key):
                raise Gap('map_identity_changed')
            return
        if self.count >= self.max_directories:
            raise Gap('map_limit')
        try:
            self.database.execute('INSERT INTO directories VALUES(?,?,?,?)', (entry, parent, name, key))
            self.database.commit()
            self.count += 1
        except sqlite3.IntegrityError:
            self.database.rollback()
            raise Gap('map_identity_collision') from None

    def get(self, entry, default=None):
        parts, seen = [], set()
        for _ in range(65):
            if entry in seen:
                raise Gap('map_cycle')
            seen.add(entry)
            row = self.database.execute('SELECT parent,name FROM directories WHERE id=?', (entry,)).fetchone()
            if row is None:
                return default
            parent, name = row
            if parent is None:
                path = b'/'.join(reversed(parts))
                if len(path) >= 4096:
                    raise Gap('map_path_limit')
                return path
            parts.append(name); entry = parent
        raise Gap('map_depth_limit')

    def reparent(self, entry, parent, name):
        ancestor, seen = parent, set()
        for _ in range(65):
            if ancestor == entry or ancestor in seen:
                raise Gap('map_cycle')
            seen.add(ancestor)
            row = self.database.execute('SELECT parent FROM directories WHERE id=?', (ancestor,)).fetchone()
            if row is None:
                raise Gap('map_parent_missing')
            if row[0] is None:
                break
            ancestor = row[0]
        else:
            raise Gap('map_depth_limit')
        if not isinstance(name, bytes) or not name or len(name) > 255 or b'/' in name or b'\0' in name or name in (b'.', b'..'):
            raise Gap('map_name_invalid')
        cursor = self.database.execute('UPDATE directories SET parent=?,name=? WHERE id=? AND parent IS NOT NULL', (parent, name, entry))
        if cursor.rowcount != 1:
            self.database.rollback()
            raise Gap('map_entry_missing')
        self.database.commit()

    def retire(self, entry):
        deadline = time.monotonic() + 1
        self.database.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        try:
            before = self.database.total_changes
            self.database.execute('WITH RECURSIVE retired(id) AS (SELECT id FROM directories WHERE id=? UNION ALL SELECT d.id FROM directories d JOIN retired r ON d.parent=r.id) DELETE FROM directories WHERE id IN (SELECT id FROM retired)', (entry,))
            removed = self.database.total_changes - before
            self.database.commit(); self.count -= removed
        except sqlite3.OperationalError:
            self.database.rollback()
            raise Gap('map_retirement_budget') from None
        finally:
            self.database.set_progress_handler(None, 0)


class ContainedAdmission:
    """Reuse journaled/reap-checked monitor ownership for the native helper.

    `watcher` is the existing ContinuousWatcher ownership/framing object, not
    an inotify source. Its spawn/cleanup retain quarantine on unproved reap.
    """
    def __init__(self, watcher, executable, client, root, generation, directory_map):
        self.watcher, self.executable, self.client = watcher, executable, client
        self.root, self.generation, self.map = root, generation, directory_map
        self.root_identity = None

    def arm(self, timeout=2):
        self.watcher.spawn([str(self.executable), '--root', os.fsdecode(self.root)])
        reply = self.watcher.message(timeout)
        if not reply or reply.get('status') != 'ready' or any(type(reply.get(key)) is not int or reply[key] <= 0 for key in ('root_device', 'root_inode')):
            raise Gap('boundary_startup_failed')
        self.root_identity = (reply['root_device'], reply['root_inode'])
        self.watcher.save('ready', 'boundary_ready')

    def close(self):
        self.watcher.cleanup()

    def validate(self, handle, generation):
        if generation != self.generation:
            raise Gap('root_generation_changed')
        entry = self.map.admitted(handle)
        if entry is None:
            return None  # Never resolve unknown/outside handles.
        path = self.map.get(entry)
        encoded = base64.b64encode(path).decode() if path else '-'
        request = f'V {encoded} {handle.fsid.hex()} {handle.kind} {handle.opaque.hex()}\n'.encode()
        self.watcher.worker.stdin.write(request); self.watcher.worker.stdin.flush()
        reply = self.watcher.message(1)
        if not reply or reply.get('status') != 'admitted':
            raise Gap('parent_identity_changed')
        return entry

    def inventory(self, entry, absolute_path, *, baseline=False, seconds=10, source_check=None):
        if absolute_path == self.root:
            relative = b''
        elif absolute_path.startswith(self.root + b'/'):
            relative = absolute_path[len(self.root) + 1:]
        else:
            raise Gap('inventory_scope')
        encoded = base64.b64encode(relative).decode() if relative else '-'
        self.watcher.worker.stdin.write(f'I {encoded}\n'.encode()); self.watcher.worker.stdin.flush()
        deadline = time.monotonic() + seconds
        while True:
            if time.monotonic() >= deadline:
                raise Gap('inventory_deadline')
            if source_check:
                source_check()
            reply = self.watcher.message(max(0, deadline - time.monotonic()))
            if not reply:
                raise Gap('inventory_deadline')
            if reply.get('status') == 'inventory_done':
                return
            if reply.get('status') != 'item' or type(reply.get('kind')) is not int or reply['kind'] not in (1, 2):
                raise Gap('inventory_failed')
            try:
                path = base64.b64decode(reply['path_b64'], validate=True)
            except (KeyError, ValueError, TypeError):
                raise Gap('inventory_protocol') from None
            if len(path) >= 4096 or b'\0' in path or path.startswith(b'/') or any(piece in (b'.', b'..') or path and not piece for piece in path.split(b'/')) or relative and path != relative and not path.startswith(relative + b'/'):
                raise Gap('inventory_scope')
            absolute = self.root + (b'/' + path if path else b'')
            located = self.client.lookup(absolute)
            if located and located['entry_kind'] != reply['kind']:
                raise Gap('inventory_kind_changed')
            if not located:
                if baseline:
                    raise Gap('baseline_changed')
                parent_path, _, name = absolute.rpartition(b'/')
                parent = self.client.lookup(parent_path)
                if not parent or parent['entry_kind'] != 2:
                    raise Gap('inventory_parent_missing')
                new_entry = self.client.apply(parent['entry_id'], name, kind=reply['kind'])
                located = {'entry_id': new_entry, 'parent_id': parent['entry_id'], 'entry_kind': reply['kind']}
            if absolute == absolute_path and located['entry_id'] != entry:
                raise Gap('inventory_root_changed')
            if reply['kind'] == 2:
                try:
                    identity = Handle(bytes.fromhex(reply['fsid']), reply['handle_kind'], bytes.fromhex(reply['handle']))
                except (KeyError, ValueError, TypeError):
                    raise Gap('inventory_protocol') from None
                name = path.rsplit(b'/', 1)[-1] if path else b''
                self.map.add(identity, located['entry_id'], located['parent_id'] if path else None, name)
