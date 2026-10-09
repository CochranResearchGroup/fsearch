"""Positive controls for owned-workload timeout and aggregate RSS enforcement."""
import json,subprocess,sys,tempfile
from pathlib import Path
runner=sys.argv[1]
with tempfile.TemporaryDirectory(prefix='fsearch-guard-controls-') as tmp:
    for label,extra,command in [
        ('deadline',['--seconds','0.3'],[sys.executable,'-c','import time;time.sleep(30)']),
        ('memory',['--seconds','5','--rss-mib','16'],[sys.executable,'-c','import time;x=bytearray(64*1024*1024);time.sleep(30)'])]:
        receipt=Path(tmp,label+'.json')
        p=subprocess.run([sys.executable,runner,'--receipt',str(receipt),*extra,'--',*command],timeout=10)
        evidence=json.loads(receipt.read_text());assert p.returncode==1
        assert evidence['reason']==('deadline' if label=='deadline' else 'aggregate_rss_budget'),evidence
        assert evidence['elapsed_seconds']<5
    wrapper=Path(tmp,'no_blocking_pss.py')
    marker=Path(tmp,'pss-read')
    wrapper.write_text("import pathlib,runpy,sys\noriginal=pathlib.Path.read_text\ndef guarded(path,*args,**kwargs):\n if path.name=='smaps_rollup':\n  pathlib.Path("+repr(str(marker))+").write_text('unexpected blocking PSS read')\n  raise AssertionError('PSS must not block the pressure monitor')\n return original(path,*args,**kwargs)\npathlib.Path.read_text=guarded\nsys.argv=sys.argv[1:]\nrunpy.run_path(sys.argv[0],run_name='__main__')\n")
    receipt=Path(tmp,'no_blocking_pss.json')
    p=subprocess.run([sys.executable,str(wrapper),runner,'--receipt',str(receipt),'--seconds','0.3',
        '--',sys.executable,'-c','import time;time.sleep(30)'],timeout=10)
    assert not marker.exists(),'monitor attempted potentially blocking PSS read'
    evidence=json.loads(receipt.read_text());assert p.returncode==1 and evidence['reason']=='deadline',evidence
    assert evidence['peak_sampled_pss_bytes'] is None and evidence['elapsed_seconds']<5,evidence
    slow=Path(tmp,'slow_status.py')
    slow.write_text("import pathlib,runpy,sys,time\noriginal=pathlib.Path.read_text\nseen=False\ndef guarded(path,*args,**kwargs):\n global seen\n if path.name=='status' and not seen:\n  seen=True;time.sleep(1.1)\n return original(path,*args,**kwargs)\npathlib.Path.read_text=guarded\nsys.argv=sys.argv[1:]\nrunpy.run_path(sys.argv[0],run_name='__main__')\n")
    receipt=Path(tmp,'sample_gap.json')
    p=subprocess.run([sys.executable,str(slow),runner,'--receipt',str(receipt),'--seconds','5',
        '--',sys.executable,'-c','import time;time.sleep(30)'],timeout=10)
    evidence=json.loads(receipt.read_text());assert p.returncode==1 and evidence['reason']=='monitor_sample_gap',evidence
    assert evidence['max_sample_gap_seconds']>=1 and evidence['elapsed_seconds']<5,evidence
print('pressure guard positive controls and nonblocking sampling pass')
