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
print('pressure guard positive controls pass')
