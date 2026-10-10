"""Actual native checkpoint wire, retired IDs and cached recovery without roots."""
import base64,hashlib,json,os,struct,subprocess,sys,tempfile,time
from pathlib import Path
runtime=Path(sys.argv[1]);fault=Path(sys.argv[2]) if len(sys.argv)>2 else None;os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='fsearch-native-checkpoint-') as temporary:
    work=Path(temporary);gate=work/'writer-gate';root=work/'owned';root.mkdir();(root/'initial').touch();database=work/'snapshot';checkpoint=work/'checkpoint'
    subprocess.run([sys.executable,str(runtime/'fsearch-refresh'),'refresh','--root',str(root),'--database',str(database)],check=True,capture_output=True,timeout=10)
    def read(worker):
        prefix=worker.stdout.read(4);assert len(prefix)==4,'worker rejected checkpoint wire'
        size=struct.unpack('!I',prefix)[0];assert size<=1048576
        return json.loads(worker.stdout.read(size))
    def start():
        worker=subprocess.Popen([str(runtime/'fsearch-worker'),str(database),str(os.getpid())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env={**os.environ,**({'LD_PRELOAD':str(fault),'FSEARCH_CHECKPOINT_TEST_GATE':str(gate)} if fault else {})})
        worker.stdin.write(b'G');worker.stdin.flush();ready=read(worker);assert ready['status']=='ready';
        global baseline_identity
        baseline_identity=ready['snapshot_id'];return worker
    def call(worker,op,kind=0,parent=0,id=0,seq=0,body=b''):
        worker.stdin.write(struct.pack('!7I',op,kind,parent,id,seq>>32,seq&0xffffffff,len(body))+body);worker.stdin.flush();return read(worker)
    worker=start()
    try:
        retired=call(worker,0x100,1,0,seq=1,body=b'retired')['entry_id']
        assert call(worker,0x101,0,0,retired,2)['status']=='catalog_applied'
        raw=call(worker,0x100,1,0,seq=3,body=b'raw-\xff')['entry_id']
        if fault:gate.touch()
        result=call(worker,0x105,body=os.fsencode(checkpoint));assert result['status']=='catalog_checkpointing',result
        assert result['checkpoint_sequence']==3,result
        assert call(worker,0x100,1,0,seq=4,body=b'after-capture')['status']=='catalog_applied'
        if fault:
            assert gate.exists() and checkpoint.stat().st_size==0
            assert call(worker,0x104,body=os.fsencode(root)+b'/raw-\xff')['entry_id']==raw
            gate.unlink()
        deadline=time.monotonic()+3
        while True:
            result=call(worker,0x107)
            if result['status']=='catalog_checkpointed':break
            assert result['status']=='catalog_checkpointing' and time.monotonic()<deadline,result
            time.sleep(.01)
        assert result['checkpoint_sequence']==3 and result['sequence']==4,result
    finally:
        gate.unlink(missing_ok=True)
        worker.stdin.close();worker.wait(timeout=5)
    (root/'initial').unlink();root.rmdir()
    worker=start()
    try:
        result=call(worker,0x106,body=os.fsencode(checkpoint));assert result['status']=='catalog_restored' and result['sequence']==3,result
        result=call(worker,0x104,body=os.fsencode(root)+b'/raw-\xff');assert result['entry_id']==raw,result
        new=call(worker,0x100,1,0,seq=4,body=b'new')['entry_id'];assert new>raw>retired
        print(json.dumps({'result':'native_checkpoint_wire_pass','sequence':3,'raw_bytes':True,'retired_id_reuse':False,'indexed_root_absent':True,'queries_and_mutations_during_held_write':bool(fault)}))
    finally:
        gate.unlink(missing_ok=True)
        worker.stdin.close();worker.wait(timeout=5)

    database.unlink()
    def private_start():
        process=subprocess.Popen([str(runtime/'fsearch-worker'),str(checkpoint),str(os.getpid()),'--checkpoint',baseline_identity],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        process.stdin.write(b'G');process.stdin.flush();return process,read(process)
    worker,ready=private_start()
    try:
        assert ready['status']=='ready' and ready['checkpoint_sequence']==3,ready
        query=b'raw-';worker.stdin.write(struct.pack('!7I',0,0,100,500000,1048576,len(query),0)+query);worker.stdin.flush()
        result=read(worker);assert result['snapshot']['identity']==baseline_identity and result['snapshot']['roots'][0]['path']==str(root),result
        assert result['snapshot']['roots'][0]['last_scan_unix']>0,result
    finally:
        worker.stdin.close();worker.wait(timeout=5)
    metadata=Path(str(checkpoint)+'.metadata');original=metadata.read_bytes()
    for corrupted,code in ((original[:-1]+bytes([original[-1]^1]),'checkpoint_metadata_invalid'),
                           (original[:40]+struct.pack('<Q',4)+original[48:-32],'checkpoint_metadata_sequence')):
        if code.endswith('_sequence'):corrupted+=hashlib.sha256(corrupted).digest()
        metadata.write_bytes(corrupted)
        worker,result=private_start()
        try:assert result['status']=='error' and result['error']['code']==code,result
        finally:worker.stdin.close();worker.wait(timeout=5)
    metadata.write_bytes(original)
    print(json.dumps({'result':'private_checkpoint_metadata_pass','original_snapshot_absent':True,'indexed_root_absent':True,'cached_coverage_preserved':True,'metadata_checksum_and_sequence_refused':True}))
