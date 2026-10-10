"""Real owned inode-mark regression; never creates a filesystem mark."""
import ctypes
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fsearch_fanotify_events as f

lib = ctypes.CDLL(None, use_errno=True)
with tempfile.TemporaryDirectory(prefix='fsearch-owned-coalesce-') as directory:
    source = lib.fanotify_init(0x1e00 | 1 | 2, os.O_RDONLY | os.O_CLOEXEC)
    if source < 0:
        if ctypes.get_errno() in (1, 22, 38):
            print('coalescing_skip: unprivileged FID fanotify unavailable')
            raise SystemExit(77)
        raise OSError(ctypes.get_errno(), 'fanotify_init')
    root = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        assert lib.fanotify_mark(source, 1, ctypes.c_uint64(f.CREATE | f.DELETE), root, None) == 0
        transient = Path(directory) / 'transient'
        transient.touch(); transient.unlink()
        data = os.read(source, 65536)
        decoded = f.decode(data)
        assert len(decoded) == 1 and decoded[0].mask == f.CREATE | f.DELETE
        parent = decoded[0].sides[0].parent
        outside = f.ExportFilter(1)
        assert outside.consume(data, 1, lambda *args: None) == () and outside.sequence == 0
        inside = f.ExportFilter(1)
        try:
            inside.consume(data, 1, lambda handle, generation: 0 if handle == parent else None)
        except f.Gap as error:
            assert str(error) == 'ambiguous_operation' and inside.sequence == 0
        else:
            raise AssertionError('ambiguous admitted operation was exported')
        print('coalescing_pass: real CREATE|DELETE discarded outside, sticky gap inside; no names exported')
    finally:
        os.close(root); os.close(source)
