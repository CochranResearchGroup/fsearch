#!/usr/bin/env python3
"""Contained filename event ingestion; durable recovery is a separate milestone."""
import argparse,base64,importlib.machinery,importlib.util,json,os,resource,select,signal,socket,struct,time,uuid
from pathlib import Path
base=Path(__file__).resolve().parent
path=base/'fsearch-monitor'
if not path.exists():path=base/'fsearch_monitor.py'
loader=importlib.machinery.SourceFileLoader('_fsearch_incremental_monitor',str(path))
spec=importlib.util.spec_from_loader(loader.name,loader);monitor=importlib.util.module_from_spec(spec);loader.exec_module(monitor)
lifecycle=monitor.lifecycle;BoundaryError=lifecycle.BoundaryError

def emit(status,**fields):
    print(json.dumps({'schema_version':1,'status':status,'durable':False,**fields}),flush=True)

class ContinuousWatcher(monitor.Watcher):
    def message(self,timeout):
        deadline=time.monotonic()+timeout
        while True:
            if b'\n' in self.buffer:
                line,_,rest=self.buffer.partition(b'\n');self.buffer=bytearray(rest)
                if len(line)>8192:raise BoundaryError('worker_protocol_failed')
                result=json.loads(line)
                if not isinstance(result,dict):raise BoundaryError('worker_protocol_failed')
                return result
            if not select.select([self.worker.stdout],[],[],max(0,deadline-time.monotonic()))[0]:return None
            data=os.read(self.worker.stdout.fileno(),8192)
            if not data:raise BoundaryError('failed_worker')
            self.buffer.extend(data)
            if len(self.buffer)>16384:raise BoundaryError('worker_protocol_failed')
    def arm(self,timeout):
        self.spawn([str(base/'fsearch-monitor-worker'),'--root',self.root,'--events'])
        ready=self.message(timeout)
        if not ready or ready.get('status')!='ready':raise BoundaryError('watch_unavailable')
        coverage=self.message(timeout)
        if not coverage or coverage.get('reason')!='startup_gap':raise BoundaryError('worker_protocol_failed')
        self.save('ready','startup_gap')
    def check(self,timeout=0):
        deadline=time.monotonic()+timeout
        while True:
            message=self.message(max(0,deadline-time.monotonic()))
            if message is None:return
            if message.get('status')=='heartbeat':
                if type(message.get('sequence')) is not int or message['sequence']!=0:raise BoundaryError('event_sequence_gap')
                observation_time(message);continue
            raise monitor.GenerationChanged(message.get('reason',message.get('status','unknown')))

    def barrier(self,timeout):
        self.worker.stdin.write(b'B');self.worker.stdin.flush();deadline=time.monotonic()+timeout
        while True:
            message=self.message(max(0,deadline-time.monotonic()))
            if message is None:raise BoundaryError('watcher_barrier_timeout')
            if message.get('status') not in ('heartbeat','barrier'):raise monitor.GenerationChanged(message.get('reason',message.get('status','unknown')))
            if type(message.get('sequence')) is not int or message['sequence']!=0:raise BoundaryError('event_sequence_gap')
            observation_time(message)
            if message['status']=='barrier':return

class CatalogClient:
    def __init__(self,path):
        self.directory=lifecycle.PrivateDirectory(path);self.identity=None;self.sequence=0;self.changes=0;self.last_reconciled=None;self.coverage_state=None;self.batch_remaining=0
    def close(self):self.directory.close()
    def call(self,op,**fields):
        request={'schema_version':1,'request_id':uuid.uuid4().hex,'op':op,'timeout_ms':2000,**fields}
        if self.identity:request['expected_snapshot_id']=self.identity
        lifecycle.validate_request(request);self.directory.socket_info()
        with socket.socket(socket.AF_UNIX) as stream:
            stream.settimeout(2.3);stream.connect(self.directory.address)
            if struct.unpack('3i',stream.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]!=os.geteuid():raise BoundaryError('unsafe_peer')
            stream.sendall(lifecycle.encoded(request));data=bytearray()
            while b'\n' not in data:
                chunk=stream.recv(65536)
                if not chunk:raise BoundaryError('service_unavailable')
                data.extend(chunk)
                if len(data)>lifecycle.MAX_RESPONSE:raise BoundaryError('response_size_limit')
        response=json.loads(data)
        if not isinstance(response,dict) or response.get('request_id')!=request['request_id']:raise BoundaryError('worker_protocol_failed')
        if response.get('status')=='error':raise BoundaryError(response.get('error',{}).get('code','catalog_failed'))
        return response
    def reset(self):
        self.identity=None;state=self.call('catalog_status')
        if state.get('status')!='catalog_status' or type(state.get('sequence')) is not int:raise BoundaryError('worker_protocol_failed')
        self.identity=state['snapshot_id'];self.sequence=state['sequence'];self.changes=0
        self.batch_remaining=self.remaining(state)

    @staticmethod
    def remaining(reply):
        value=reply.get('journal_remaining',0) if reply.get('durable') is True else 0
        if type(value) is not int or not 0<=value<=1024:raise BoundaryError('worker_protocol_failed')
        return value
    def coverage(self,state,root,observed=0,oldest=None,reason=''):
        self.call('catalog_coverage',coverage={'state':state,'root_b64':base64.b64encode(root).decode(),'event_sequence':observed,'catalog_sequence':self.sequence,'last_reconciled_unix_ms':self.last_reconciled,'oldest_unapplied_unix_ms':oldest,'reason':reason})
        self.coverage_state=state
    def lookup(self,path):
        response=self.call('catalog_lookup',path_b64=base64.b64encode(path).decode())
        if response.get('status') not in ('catalog_located','catalog_missing'):raise BoundaryError('worker_protocol_failed')
        return response if response['status']=='catalog_located' else None
    def apply(self,parent,name,entry=None,kind=1):
        fields={'sequence':self.sequence+1,'parent_id':parent,'entry_kind':kind,'name_b64':base64.b64encode(name).decode()}
        if entry is not None:fields['entry_id']=entry
        reply=self.call('catalog_apply',**fields)
        if reply.get('status')!='catalog_applied' or reply.get('sequence')!=self.sequence+1:raise BoundaryError('worker_protocol_failed')
        self.sequence+=1;self.changes+=1
        self.batch_remaining=self.remaining(reply)
        if reply.get('deferred_reason'):raise BoundaryError(reply['deferred_reason'])
        if self.changes>=1024 and not reply.get('building'):
            self.call('catalog_compact');self.changes=0
        return reply['entry_id']

    def apply_batch(self, mutations):
        if not 1<=len(mutations)<=min(lifecycle.MAX_BATCH_RECORDS,self.batch_remaining):raise BoundaryError('catalog_batch_limit')
        requests=[]
        for offset,(parent,name,entry,kind) in enumerate(mutations,1):
            request={'sequence':self.sequence+offset,'parent_id':parent,'entry_kind':kind,'name_b64':base64.b64encode(name).decode()}
            if entry is not None:request['entry_id']=entry
            requests.append(request)
        reply=self.call('catalog_apply_batch',mutations=requests)
        entries=reply.get('entry_ids')
        if reply.get('status')!='catalog_batch_applied' or reply.get('durable') is not True or reply.get('sequence')!=self.sequence+len(mutations) or not isinstance(entries,list) or len(entries)!=len(mutations) or any(type(entry) is not int or not 0<=entry<2**32 for entry in entries):raise BoundaryError('worker_protocol_failed')
        self.sequence+=len(mutations);self.changes+=len(mutations)
        self.batch_remaining=self.remaining(reply)
        if reply.get('deferred_reason'):raise BoundaryError(reply['deferred_reason'])
        if self.changes>=1024 and not reply.get('building'):
            self.call('catalog_compact');self.changes=0
        return entries

def decode(value,relative=False):
    if not isinstance(value,str):raise BoundaryError('worker_protocol_failed')
    raw=base64.b64decode(value,validate=True)
    if b'\0' in raw or len(raw)>4096:raise BoundaryError('worker_protocol_failed')
    if relative:
        if raw.startswith(b'/') or any(x in (b'.',b'..') for x in raw.split(b'/')):raise BoundaryError('worker_protocol_failed')
    elif not raw or b'/' in raw:raise BoundaryError('worker_protocol_failed')
    return raw

def observation_time(message):
    """Map watcher monotonic observation to wall time without resetting backlog age."""
    observed=message.get('observed_monotonic_us');now=time.monotonic_ns()//1000
    if type(observed) is not int or not 0<=observed<=now:raise BoundaryError('event_observation_time')
    return max(0,int(time.time()*1000)-(now-observed)//1000)

def ingest(watcher,client,root):
    observed=0;pending={};next_heartbeat=0;oldest=None;inventory_since=None;last_source_progress=time.monotonic()
    def remove(entry):
        if entry:client.apply(entry['parent_id'],b'',entry['entry_id'],0)
    while True:
        message=watcher.message(.02)
        now=time.monotonic()
        if message is None:
            if now-last_source_progress>2:
                outstanding=[x[2] for x in pending.values()]+([inventory_since] if inventory_since is not None else [])
                client.coverage('deferred',root,observed,min(outstanding) if outstanding else None,reason='watcher_progress_timeout')
                raise BoundaryError('watcher_progress_timeout')
            for cookie,(entry,expiry,received) in list(pending.items()):
                if now>=expiry:remove(entry);del pending[cookie]
            if now>=next_heartbeat:
                outstanding=[x[2] for x in pending.values()]+([inventory_since] if inventory_since is not None else [])
                client.coverage('pending' if outstanding else 'watching',root,observed,min(outstanding) if outstanding else None,reason='subtree_inventory' if inventory_since is not None else '')
                next_heartbeat=now+.5
            continue
        if message.get('status')=='gap':raise monitor.GenerationChanged(message.get('reason','event_gap'))
        if message.get('status')=='heartbeat':
            if type(message.get('sequence')) is not int or message['sequence']!=observed:raise BoundaryError('event_sequence_gap')
            observation_time(message);last_source_progress=time.monotonic();continue
        if message.get('status')=='inventory':
            if type(message.get('sequence')) is not int or message['sequence']!=observed:raise BoundaryError('event_sequence_gap')
            observed_unix_ms=observation_time(message);last_source_progress=time.monotonic()
            if message.get('phase')=='begin' and inventory_since is None:inventory_since=observed_unix_ms
            elif message.get('phase')=='end' and inventory_since is not None:inventory_since=None
            else:raise BoundaryError('worker_protocol_failed')
            outstanding=[x[2] for x in pending.values()]+([inventory_since] if inventory_since is not None else [])
            client.coverage('pending',root,observed,min(outstanding) if outstanding else None,reason='subtree_inventory' if inventory_since is not None else 'inventory_drained')
            continue
        if message.get('status')!='event' or type(message.get('sequence')) is not int or message['sequence']!=observed+1:raise BoundaryError('event_sequence_gap')
        received=observation_time(message);last_source_progress=time.monotonic();observed+=1;oldest=min([received]+[x[2] for x in pending.values()]+([inventory_since] if inventory_since is not None else []))
        client.coverage('pending',root,observed,oldest,reason='event_pending')
        mask=message.get('mask');cookie=message.get('cookie')
        if type(mask) is not int or type(cookie) is not int or message.get('kind') not in (1,2):raise BoundaryError('worker_protocol_failed')
        parent_relative=decode(message.get('parent_b64'),True);name=decode(message.get('name_b64'))
        parent_path=root+(b'/'+parent_relative if parent_relative else b'');path=parent_path+b'/'+name
        parent=client.lookup(parent_path)
        if not parent or parent['entry_kind']!=2:raise monitor.GenerationChanged('parent_missing')
        existing=client.lookup(path)
        if mask&0x40:
            if len(pending)>=128:raise monitor.GenerationChanged('rename_budget')
            if not cookie or cookie in pending:raise monitor.GenerationChanged('rename_cookie')
            pending[cookie]=(existing,time.monotonic()+.1,received)
        elif mask&0x80:
            previous=pending.pop(cookie,(None,0,None))[0]
            if previous:
                if existing and existing['entry_id']!=previous['entry_id']:remove(existing)
                client.apply(parent['entry_id'],name,previous['entry_id'],message['kind'])
            else:
                remove(existing);client.apply(parent['entry_id'],name,kind=message['kind'])
        elif mask&0x200:remove(existing)
        elif mask&0x100:
            if not existing:client.apply(parent['entry_id'],name,kind=message['kind'])
        else:raise BoundaryError('worker_protocol_failed')
        outstanding=[x[2] for x in pending.values()]+([inventory_since] if inventory_since is not None else [])
        emit('applied',event_sequence=observed,catalog_sequence=client.sequence,oldest_unapplied_unix_ms=min(outstanding) if outstanding else None)


def watch(directory,root,database,socket_path,timeout):
    root_bytes=os.fsencode(root);attempts=0;client=CatalogClient(socket_path)
    try:
        while True:
            watcher=ContinuousWatcher(directory,root)
            try:
                client.reset();client.coverage('reconciling',root_bytes,reason='startup_gap')
                watcher.arm(timeout);emit('reconciling',reason='startup_gap',coverage='incomplete')
                update=lifecycle.PrivateDirectory(database+'.refresh')
                try:
                    update.lock();lifecycle.reconcile(update)
                    monitor.MonitoredRefresh(update,watcher).run(root,database,timeout)
                    watcher.check();watcher.barrier(min(2,timeout));identity=monitor.accepted_identity(directory,Path(database).name)
                    monitor.replace_serving(socket_path,database,identity,root)
                finally:update.close()
                client.reset();client.last_reconciled=int(time.time()*1000);client.coverage('watching',root_bytes,reason='reconciled');watcher.snapshot_id=client.identity;watcher.save('ready','reconciled')
                emit('watching',snapshot_id=client.identity,catalog_sequence=client.sequence,coverage='watching');attempts=0
                ingest(watcher,client,root_bytes)
            except monitor.GenerationChanged as changed:
                client.coverage('offline' if changed.status=='root_offline' else 'reconciling',root_bytes,reason=changed.status)
                attempts+=1;emit('gap',reason=changed.status,coverage='incomplete')
                if changed.status=='root_offline' or attempts>=8:raise BoundaryError(changed.status)
            finally:watcher.cleanup()
    finally:
        try:
            if client.identity and client.coverage_state not in ('offline','deferred'):client.coverage('deferred',root_bytes,reason='updater_stopped')
        except (BoundaryError,OSError,ValueError):pass
        client.close()


def interrupted(signum,frame):raise BoundaryError('interrupted')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--database',required=True);parser.add_argument('--socket',required=True);parser.add_argument('--timeout-ms',type=int,default=10000)
    args=parser.parse_args();directory=None
    try:
        if not os.path.isabs(args.root) or len(os.fsencode(args.root))>4096 or '\0' in args.root or not 1<=args.timeout_ms<=300000:raise BoundaryError('invalid_request')
        database=os.path.abspath(args.database);directory=lifecycle.PrivateDirectory(database+'.incremental');directory.lock();lifecycle.reconcile(directory)
        soft,hard=resource.getrlimit(resource.RLIMIT_AS);limit=min(hard,128*1024*1024) if hard!=resource.RLIM_INFINITY else 128*1024*1024;resource.setrlimit(resource.RLIMIT_AS,(limit,hard));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
        watch(directory,os.path.abspath(args.root),database,args.socket,args.timeout_ms/1000)
    except (BoundaryError,OSError,ValueError,UnicodeError) as exc:
        reason=str(exc) if isinstance(exc,BoundaryError) else 'incremental_unavailable'
        emit('stopped' if reason=='interrupted' else 'error',reason=reason,coverage='incomplete');return 0 if reason=='interrupted' else 1
    finally:
        if directory:directory.close()
if __name__=='__main__':raise SystemExit(main())
