#!/usr/bin/env python3
"""Install only the explicitly reviewed, measured local query runtime."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
EVIDENCE=REPO/'docs/research/production-evidence'
BUILD=Path('/tmp/fsearch-warm-release-build/src')
NAMES=('fsearch-cli','fsearch-worker','fsearch-service')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('source_commit');args=parser.parse_args()
    source=subprocess.check_output(['git','rev-parse',args.source_commit],cwd=REPO,text=True).strip()
    review=json.loads((EVIDENCE/'production-review.json').read_text())
    assert review['source_commit']==source and review['standards_blocking']==0 and review['spec_blocking']==0
    qualification=json.loads((EVIDENCE/'production-qualification.json').read_text())
    assert qualification['source_qualified'] is True
    for name in NAMES:assert digest(BUILD/name)==qualification['artifacts'][name]
    for path,expected in qualification['sources'].items():
        assert digest(REPO/path)==expected
        assert hashlib.sha256(subprocess.check_output(['git','show',source+':'+path],cwd=REPO)).hexdigest()==expected
    destination=Path.home()/'.local/share/fsearch/runtimes'/source
    links=Path.home()/'.local/bin';links.mkdir(parents=True,exist_ok=True)
    previous={name:os.readlink(links/name) if (links/name).is_symlink() else None for name in NAMES}
    assert all(previous.values()),'Expected the known previous runtime symlinks; refuse an unrelated command replacement.'
    assert not destination.exists(),'Existing runtime needs separate reconciliation.'
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.fsearch-install-',dir=destination.parent) as directory:
        stage=Path(directory)/'runtime';(stage/'bin').mkdir(parents=True)
        files={}
        for name in NAMES:
            shutil.copy2(BUILD/name,stage/'bin'/name)
            assert digest(stage/'bin'/name)==qualification['artifacts'][name]
            files[name]={'path':str(destination/'bin'/name),'sha256':digest(stage/'bin'/name)}
        manifest={'source_commit':source,'branch':subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),'files':files,'previous_links':previous,'review_sha256':digest(EVIDENCE/'production-review.json'),'qualification_sha256':digest(EVIDENCE/'production-qualification.json')}
        (stage/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        os.rename(stage,destination)
    changed=[]
    try:
        for name in NAMES:
            temporary=links/('.'+name+'.install-'+str(os.getpid()))
            temporary.symlink_to(destination/'bin'/name);os.replace(temporary,links/name);changed.append(name)
        for name in NAMES:
            assert (links/name).resolve()==destination/'bin'/name
            assert digest(links/name)==qualification['artifacts'][name]
    except BaseException:
        for name in changed:
            temporary=links/('.'+name+'.rollback-'+str(os.getpid()))
            temporary.symlink_to(previous[name]);os.replace(temporary,links/name)
        raise
    (EVIDENCE/'installed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(destination)
if __name__=='__main__':main()
