"""Owned-only unprivileged fanotify retention and eviction correctness probe."""
import ctypes,errno,json,os,select,shutil,struct,sys,time
from pathlib import Path
root=Path(sys.argv[1]);assert root.is_dir() and not list(root.iterdir())
libc=ctypes.CDLL(None,use_errno=True)
libc.fanotify_init.argtypes=[ctypes.c_uint,ctypes.c_uint];libc.fanotify_init.restype=ctypes.c_int
libc.fanotify_mark.argtypes=[ctypes.c_int,ctypes.c_uint,ctypes.c_uint64,ctypes.c_int,ctypes.c_char_p];libc.fanotify_mark.restype=ctypes.c_int
relative=next(x.split(':',2)[2].strip() for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
cgroup=Path('/sys/fs/cgroup')/relative.lstrip('/')
def metrics():
    stat={k:int(v) for k,v in (x.split() for x in (cgroup/'memory.stat').read_text().splitlines())}
    return {'total':int((cgroup/'memory.current').read_text()),'anon':stat['anon'],'kernel':stat['kernel'],'file':stat['file']}
def mark_count(fd):
    with open(f'/proc/self/fdinfo/{fd}') as info:return sum(line.startswith('fanotify ino:') for line in info)
results=[]
try:
    for mode in ('pinned','evictable'):
        tree=root/mode;tree.mkdir()
        for number in range(10000):(tree/f'dir-{number:05}').mkdir()
        # FAN_REPORT_FID | FAN_REPORT_DFID_NAME; no mount/filesystem marks.
        fd=libc.fanotify_init(0x1|0x2|0x200|0xc00,os.O_RDONLY|os.O_LARGEFILE)
        if fd<0:raise OSError(ctypes.get_errno(),'fanotify_init')
        try:
            for number in range(10000):
                flags=0x1|0x8|(0x200 if mode=='evictable' else 0)
                if libc.fanotify_mark(fd,flags,0x100|0x08000000,-100,os.fsencode(tree/f'dir-{number:05}')):
                    raise OSError(ctypes.get_errno(),'fanotify_mark inode')
            before=metrics();before_marks=mark_count(fd);reclaim=[]
            for _ in range(3):
                try:(cgroup/'memory.reclaim').write_text(str(512*1024*1024));reclaim.append({'result':'fulfilled'})
                except OSError as exc:reclaim.append({'result':'returned_error','errno':exc.errno})
            pressure=bytearray(224*1024*1024)
            after=metrics();after_marks=mark_count(fd);del pressure
            for number in (0,2499,4999,7499,9999):(tree/f'dir-{number:05}'/'probe.txt').touch()
            masks=[];deadline=time.monotonic()+.5
            while select.select([fd],[],[],max(0,deadline-time.monotonic()))[0]:
                data=os.read(fd,65536);offset=0
                while offset<len(data):
                    length,version,_,metadata_length,mask,event_fd,pid=struct.unpack_from('=IBBHQii',data,offset)
                    assert version==3 and 24<=metadata_length<=length and offset+length<=len(data)
                    masks.append(mask)
                    if event_fd>=0:os.close(event_fd)
                    offset+=length
                if time.monotonic()>=deadline:break
            results.append({'mode':mode,'marks_before':before_marks,'marks_after_reclaim':after_marks,
                'memory_before':before,'memory_after_reclaim':after,'reclaim':reclaim,
                'probes':5,'create_events':sum(bool(mask&0x100) for mask in masks),'overflow':any(mask&0x4000 for mask in masks)})
        finally:os.close(fd)
        shutil.rmtree(tree)
    assert results[0]['create_events']==5 and not results[0]['overflow'],results
    print(json.dumps({'result':'measured' if results[1]['marks_after_reclaim']<results[1]['marks_before'] else 'inconclusive_eviction_not_observed','scope':'owned directory inode marks only; no capabilities or mount/filesystem marks',
        'observations':results,'eviction_exercised':results[1]['marks_after_reclaim']<results[1]['marks_before'],'observed_create_events_complete':results[1]['create_events']==5 and not results[1]['overflow']},indent=2),flush=True)
finally:shutil.rmtree(root)
