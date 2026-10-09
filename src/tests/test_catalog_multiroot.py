"""Compare real forest imports to the independent legacy snapshot worker."""
import base64,itertools,json,os,struct,subprocess,sys,tempfile
from pathlib import Path
builder,worker,oracle=sys.argv[1:]
os.umask(0o077)
def receive(proc):
    header=proc.stdout.read(4)
    assert len(header)==4,proc.stderr.read().decode(errors="replace")
    length=struct.unpack("!I",header)[0]
    payload=bytearray()
    while len(payload)<length:
        chunk=proc.stdout.read(length-len(payload));assert chunk;payload.extend(chunk)
    return json.loads(payload)
def paths(reply):
    return sorted(base64.b64decode(row["path_bytes_base64"]) if row.get("path_bytes_base64") else os.fsencode(row["path"]) for row in reply["results"])
with tempfile.TemporaryDirectory(prefix="fsearch-forest-") as tmp:
    roots=[Path(tmp)/"left",Path(tmp)/"right"]
    for root in roots:
        (root/"nested").mkdir(parents=True)
        for name in ("same.txt","CAFÉ.pdf","literal*?.txt"):
            (root/"nested"/name).touch()
        fd=os.open(os.fsencode(root)+b"/raw-\xff.txt",os.O_CREAT|os.O_WRONLY,0o600);os.close(fd)
    database=Path(tmp)/"snapshot.db"
    subprocess.run([builder,"build",str(database),*map(str,roots)],check=True,stdout=subprocess.DEVNULL)
    processes=[];checks=0
    try:
        for binary in (worker,oracle):
            proc=subprocess.Popen([binary,str(database),str(os.getpid())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            processes.append(proc);proc.stdin.write(b"G");proc.stdin.flush();assert receive(proc)["status"]=="ready"
        for text,path,case,kind,ext in itertools.product(("","same","café","*","raw","left","nested","right/nested","nested/same","left/nested/","/__benchmark_missing__/","nested/CAFÉ","/nested"),(0,1),(0,1),(0,1,2),(b"",b"txt",b"pdf")):
            replies=[];encoded=text.encode()
            for proc in processes:
                flags=path|case*2|(4 if ext else 0)
                proc.stdin.write(struct.pack("!7I",flags,kind,1000,500000,1048576,len(encoded),len(ext))+encoded+ext);proc.stdin.flush();replies.append(receive(proc))
            assert all(r["status"]=="ok" and r["complete"] for r in replies),(text,path,case,kind,ext,replies)
            assert paths(replies[0])==paths(replies[1]),(text,path,case,kind,ext)
            checks+=1
        print(json.dumps({"result":"pass","roots":2,"comparisons":checks,"oracle":"legacy resident snapshot worker","scope":"owned filesystem forest import, native literal matching and filters"}))
    finally:
        for proc in processes:
            proc.stdin.close();proc.wait(timeout=5);assert proc.returncode==0
