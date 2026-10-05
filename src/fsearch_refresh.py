#!/usr/bin/env python3
"""Explicit-root refresh; candidate construction never replaces serving workers."""
import argparse,importlib.machinery,importlib.util,json,os,resource,selectors,shutil,struct,subprocess,time,uuid
from pathlib import Path
base=Path(__file__).resolve().parent
service_path=base/'fsearch-service'
if not service_path.exists():service_path=base/'fsearch_service.py'
loader=importlib.machinery.SourceFileLoader('_fsearch_lifecycle',str(service_path))
spec=importlib.util.spec_from_loader(loader.name,loader);lifecycle=importlib.util.module_from_spec(spec);loader.exec_module(lifecycle)
BoundaryError=lifecycle.BoundaryError

def decode_reply(data):
    try:reply=json.loads(data)
    except (ValueError,UnicodeError):raise BoundaryError('worker_protocol_failed') from None
    if not isinstance(reply,dict):raise BoundaryError('worker_protocol_failed')
    if reply.get('status')=='ready':
        if not isinstance(reply.get('snapshot_id'),str) or not 1<=len(reply['snapshot_id'])<=256:
            raise BoundaryError('worker_protocol_failed')
    if reply.get('status')=='error':
        failure=reply.get('error')
        if not isinstance(failure,dict) or not isinstance(failure.get('code'),str):
            raise BoundaryError('worker_protocol_failed')
    return reply

class Refresh:
    def __init__(self,directory):
        self.directory=directory;self.worker=None;self.record=None;self.quarantined=False
    def save(self,phase,reason):
        self.directory.save({'phase':phase,'reason':reason,'worker':self.record,'supervisor':lifecycle.identity(os.getpid())})
    def spawn(self,command):
        self.worker=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,close_fds=True,preexec_fn=lifecycle.worker_limits)
        self.record=lifecycle.identity(self.worker.pid)
        self.save('starting','refresh_worker')
        self.worker.stdin.write(b'G');self.worker.stdin.flush()
        return self.worker
    def cleanup(self):
        if self.worker is None:return
        worker=self.worker
        worker.kill()
        try:worker.wait(timeout=.1);reaped=True
        except subprocess.TimeoutExpired:reaped=False
        worker.stdin.close();worker.stdout.close();self.worker=None
        if reaped:self.record=None;self.save('stopped','worker_reaped')
        else:self.quarantined=True;self.save('quarantined','cleanup_unproved')
        if not reaped:raise BoundaryError('cleanup_unproved')
    def read_frame(self,timeout,framed):
        worker=self.worker;data=bytearray();deadline=time.monotonic()+timeout
        os.set_blocking(worker.stdout.fileno(),False)
        with selectors.DefaultSelector() as selector:
            selector.register(worker.stdout,selectors.EVENT_READ)
            while time.monotonic()<deadline:
                if not selector.select(min(.01,max(0,deadline-time.monotonic()))):continue
                chunk=os.read(worker.stdout.fileno(),4097)
                if not chunk:break
                data.extend(chunk)
                if len(data)>4096:raise BoundaryError('worker_protocol_failed')
                if framed and len(data)>=4:
                    length=struct.unpack('!I',data[:4])[0]
                    if not 1<=length<=4092:raise BoundaryError('worker_protocol_failed')
                    if len(data)==length+4:return decode_reply(data[4:])
            else:raise BoundaryError('deadline')
        if framed:raise BoundaryError('refresh_failed')
        try:
            code=worker.wait(timeout=max(0,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            raise BoundaryError('deadline') from None
        if code!=0:raise BoundaryError('refresh_failed')
        return decode_reply(data)
    def run(self,root,database,timeout):
        name=Path(database).name
        stage_name='.refresh-'+uuid.uuid4().hex
        os.mkdir(stage_name,mode=0o700,dir_fd=self.directory.fd)
        stage_fd=os.open(stage_name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.directory.fd)
        candidate_name='candidate.db';candidate=f'/proc/{os.getpid()}/fd/{stage_fd}/./{candidate_name}'
        try:
            self.spawn([str(base/'fsearch-refresh-worker'),'--root',root,'--output',candidate])
            built=self.read_frame(timeout,False)
            if built.get('status')!='candidate':raise BoundaryError('refresh_failed')
            self.cleanup()
            self.spawn([str(base/'fsearch-worker'),candidate,str(os.getpid())])
            accepted=self.read_frame(2,True)
            if accepted.get('status')!='ready':raise BoundaryError(accepted.get('error',{}).get('code','candidate_rejected'))
            self.cleanup()
            fd=os.open(candidate_name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=stage_fd)
            try:
                info=os.fstat(fd)
                mtime=divmod(info.st_mtime_ns,1000000000);ctime=divmod(info.st_ctime_ns,1000000000)
                current=':'.join(map(str,(info.st_dev,info.st_ino,info.st_size,*mtime,*ctime)))
                if current!=accepted['snapshot_id']:raise BoundaryError('candidate_changed')
                os.fsync(fd)
            finally:os.close(fd)
            # Validate an existing destination without following aliases.
            try:previous=self.directory.open_private(name,os.O_RDONLY)
            except FileNotFoundError:previous=None
            if previous is not None:os.close(previous)
            os.replace(candidate_name,name,src_dir_fd=stage_fd,dst_dir_fd=self.directory.fd)
            os.fsync(self.directory.fd)
            self.save('stopped','published')
            return {'schema_version':1,'status':'published','database':os.path.abspath(database),'scan':built}
        finally:
            try:self.cleanup()
            finally:
                os.close(stage_fd)
                if not self.quarantined:
                    # Delete only the generated stage under the pinned directory.
                    shutil.rmtree(f'/proc/self/fd/{self.directory.fd}/{stage_name}')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['refresh','recover'])
    parser.add_argument('--root');parser.add_argument('--database',required=True);parser.add_argument('--timeout-ms',type=int,default=10000)
    args=parser.parse_args();directory=None
    try:
        if not 1<=args.timeout_ms<=60000 or (args.command=='refresh' and (not args.root or not os.path.isabs(args.root))):raise BoundaryError('invalid_request')
        directory=lifecycle.PrivateDirectory(args.database+'.refresh');directory.lock()
        lifecycle.reconcile(directory,args.command=='recover')
        if args.command=='recover':payload={'schema_version':1,'status':'recovered'}
        else:
            soft,hard=resource.getrlimit(resource.RLIMIT_AS)
            maximum=256*1024*1024 if hard==resource.RLIM_INFINITY else min(hard,256*1024*1024)
            current=64*1024*1024 if soft==resource.RLIM_INFINITY else min(soft,64*1024*1024)
            resource.setrlimit(resource.RLIMIT_AS,(min(current,maximum),maximum))
            resource.setrlimit(resource.RLIMIT_CORE,(0,0))
            payload=Refresh(directory).run(os.path.abspath(args.root),args.database,args.timeout_ms/1000)
        print(json.dumps(payload));return 0
    except (BoundaryError,OSError,ValueError,UnicodeError) as exc:
        print(json.dumps({'schema_version':1,'status':'error','error':{'code':str(exc) if isinstance(exc,BoundaryError) else 'refresh_unavailable'}}));return 1
    finally:
        if directory:directory.close()
if __name__=='__main__':raise SystemExit(main())
