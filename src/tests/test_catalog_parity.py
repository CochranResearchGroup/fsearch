"""Independent real owned-tree/native snapshot oracle across catalog generations."""
import base64,itertools,json,os,shutil,struct,subprocess,sys,tempfile
from pathlib import Path
fixture,snapshot_builder,worker=sys.argv[1:];os.umask(0o077)
def b64(s):return base64.b64encode(s).decode()
def receive(p):
    size=p.stdout.read(4)
    assert len(size)==4,('worker EOF',p.stderr.read().decode(errors='replace')[-1000:])
    return json.loads(p.stdout.read(struct.unpack('!I',size)[0]))
checks=prefixes=0;phases=[];sequence=0
with tempfile.TemporaryDirectory(prefix='fsearch-catalog-parity-') as tmp:
    root=os.fsencode(tmp+'/owned');os.mkdir(root)
    rows=[(0,0,2,root),(1,0,2,b'alpha'),(2,1,2,b'nested')]
    paths={0:root,1:root+b'/alpha',2:root+b'/alpha/nested'}
    os.mkdir(paths[1]);os.mkdir(paths[2])
    names=['CAFÉ-ÉCOLE.pdf','Straße.txt','STRASSE.txt','İstanbul.pdf','cafe\u0301.txt','literal*wild?.txt','emoji-😀.txt','line\nbreak.txt']
    raw=[x.encode() for x in names]+[b'raw-\xff.txt']
    for i in range(3,128):
        name=raw[i-3] if i-3<len(raw) else f'file-{i:04}.txt'.encode();rows.append((i,2,1,name));paths[i]=paths[2]+b'/'+name;Path(os.fsdecode(paths[i])).touch()
    p=subprocess.Popen([fixture],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    p.stdin.write(str(len(rows))+'\n')
    for i,parent,kind,name in rows:p.stdin.write(f'{i}\t{parent}\t{kind}\t{b64(name)}\n')
    p.stdin.flush();assert json.loads(p.stdout.readline())['ready']
    def send(s):p.stdin.write(s+'\n');p.stdin.flush();line=p.stdout.readline();assert line,('catalog EOF',p.stderr.read()[-1000:]);return json.loads(line)
    def mutation(i,parent,kind,name):
        global sequence
        sequence+=1;assert send(f'U\t{sequence}\t{i}\t{parent}\t{kind}\t{b64(name)}')['accepted']
        old=paths[i]
        if kind:
            dest=paths[parent]+b'/'+name;os.rename(old,dest)
            for j,path in list(paths.items()):
                if path==old or path.startswith(old+b'/'):paths[j]=dest+path[len(old):]
        else:
            shutil.rmtree(old) if os.path.isdir(old) else os.unlink(old)
            for j,path in list(paths.items()):
                if path==old or path.startswith(old+b'/'):del paths[j]
    def create(parent,kind,name):
        global sequence
        sequence+=1;answer=send(f'C\t{sequence}\t{parent}\t{kind}\t{b64(name)}');assert answer['accepted'];i=answer['id'];paths[i]=paths[parent]+b'/'+name
        os.mkdir(paths[i]) if kind==2 else Path(os.fsdecode(paths[i])).touch();return i
    def parity(label):
        global checks,prefixes
        db=tmp+'/oracle.db';subprocess.run([snapshot_builder,'build',db,os.fsdecode(root)],check=True,stdout=subprocess.DEVNULL)
        os.chmod(db,0o600)
        gold=subprocess.Popen([worker,db,str(os.getpid())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        gold.stdin.write(b'G');gold.stdin.flush();assert receive(gold)['status']=='ready'
        try:
            for text,path,case,kind,extension in itertools.product(['','file','café','STRASSE','İ','*','?','raw','alpha','moved','fresh','😀','alpha/nested','nested/file','moved-2/fresh','/alpha/','nested/CAFÉ'],[0,1],[0,1],['all','files','folders'],['-','txt','pdf']):
                def query(limit):
                    answer=send(f'Q\t{path}\t{case}\t{kind}\t{extension}\t{b64(text.encode())}\t{limit}')
                    ext=b'' if extension=='-' else extension.encode();flags=path|case*2|(4 if ext else 0);encoded=text.encode()
                    gold.stdin.write(struct.pack('!7I',flags,['all','files','folders'].index(kind),limit,500000,1048576,len(encoded),len(ext))+encoded+ext);gold.stdin.flush();expected=receive(gold)
                    actual=[base64.b64decode(x['path_bytes_base64']) if x.get('path_bytes_base64') else os.fsencode(x['path']) for x in answer['results']]
                    reference=[base64.b64decode(x['path_bytes_base64']) if x.get('path_bytes_base64') else os.fsencode(x['path']) for x in expected['results']]
                    return answer,expected,actual,reference
                answer,expected,actual,reference=query(1000);assert expected['status']=='ok' and answer['status']=='ok'
                assert sorted(actual)==sorted(reference),(label,text,path,case,kind,extension)
                offset=0
                for n in answer['groups']:
                    assert sorted(actual[offset:offset+n])==sorted(reference[offset:offset+n]),('order',label,text,offset,n)
                    offset+=n
                assert offset==len(actual);checks+=1
                if not text and not path and not case and kind=='all' and extension=='-':
                    for limit in (1,7,31):
                        short,native,a,b=query(limit);assert a==actual[:limit] and b==reference[:limit];prefixes+=1
            phases.append(label)
        finally:gold.stdin.close();gold.wait(timeout=5);assert gold.returncode==0
    try:
        parity('initial')
        for cycle in range(3):
            assert send('B')['accepted']
            mutation(1,0,2,f'moved-{cycle}'.encode());mutation(3,2,1,f'café-{cycle}.pdf'.encode())
            create(0,1,f'new-{cycle}.txt'.encode())
            if cycle==0:create(0,1,'Straße.txt'.encode())
            parity(f'build-{cycle}-with-replay')
            assert send('P')['accepted'];parity(f'published-{cycle}')
        mutation(1,0,0,b'');parity('ancestor-delete')
        fresh=create(0,2,b'moved-2');create(fresh,1,b'fresh.txt');parity('recreate-new-identity')
        assert send('B')['accepted'] and send('P')['accepted'];parity('post-delete-compaction')
    finally:p.stdin.close();p.wait(timeout=5);assert p.returncode==0
print(json.dumps({'result':'pass','comparisons':checks,'limited_prefix_checks':prefixes,'phases':phases,'oracle':'independent owned filesystem rebuilt through native snapshot builder and resident worker','scope':'production bounded catalog query loop against independent legacy native snapshot worker'},indent=2))
