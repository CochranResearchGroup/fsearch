#!/usr/bin/env python3
"""THROWAWAY load-once experiment, NOT a production daemon. Owned fixtures only."""
import hashlib, json, os, shlex, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
build=Path(sys.argv[1]).resolve(); output=Path(sys.argv[2]).resolve()
original=(repo/'src/fsearch_cli.c').read_text()
source=original[:original.index('static volatile sig_atomic_t interrupted;')]
start=source.index('search_snapshot(const Options *options) {')
end=source.index('    g_autoptr(FsearchQuery) query =',start)
source=source[:start]+'search_snapshot(const Options *options, FsearchDatabaseIndexStore *store, struct stat st) {\n    gint64 matching_started=g_get_monotonic_time();\n'+source[end:]
source=source.replace('    fsearch_query_match_data_free(match_data);','    fprintf(stderr,"MATCH %lld\\n",(long long)(g_get_monotonic_time()-matching_started));\n    fsearch_query_match_data_free(match_data);',1)
source+=r'''
/* Fixture-only protocol: one literal UTF-8 line per request; no public listener. */
int main(int argc, char **argv) {
    if(argc!=2) return 2;
    gint64 started=g_get_monotonic_time();
    int fd=open(argv[1], O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
    struct stat st;
    if(fd<0 || fstat(fd,&st)<0) return 3;
    g_autoptr(FsearchDatabaseIndexStore) store=NULL;
    if(!fsearch_database_file_load_snapshot_fd(fd,&store)) return 4;
    close(fd);
    fprintf(stderr,"READY %lld\n",(long long)(g_get_monotonic_time()-started));
    fflush(stderr);
    char *line=NULL; size_t capacity=0; ssize_t length;
    while((length=getline(&line,&capacity,stdin))>=0) {
        if(length>4097) return 5;
        if(length && line[length-1]=='\n') line[length-1]=0;
        Options options={.query=line,.kind="files",.limit=100,.max_candidates=MAX_CANDIDATES,.max_bytes=MAX_RESPONSE_BYTES};
        int result=search_snapshot(&options,store,st);
        fflush(stdout); fflush(stderr);
        if(result) return result;
    }
    free(line);
    return 0;
}
'''
# Raw C string needs single C escapes, not Python-escaped literal backslashes.
source=source.replace("line[length-1]=='\\\\n'", "line[length-1]=='\\n'")
source=source.replace('READY %lld\\\\n','READY %lld\\n')
output.parent.mkdir(parents=True,exist_ok=True)
output.with_suffix('.prototype.c').write_text(source)
env=dict(os.environ)
for key in ('DISPLAY','WAYLAND_DISPLAY','LD_PRELOAD','G_MESSAGES_DEBUG'): env.pop(key,None)
def percentiles(samples):
    ordered=sorted(samples[1:])
    return {'first_ms':samples[0],'p50_ms':statistics.median(ordered),'p95_ms':ordered[28]}
with tempfile.TemporaryDirectory(prefix='fsearch-resident-experiment-') as temporary:
    work=Path(temporary); copied=work/'resident.c'; copied.write_text(source)
    obj=work/'resident.o'; binary=work/'resident-prototype'
    compile_row=next(r for r in json.loads((build/'compile_commands.json').read_text()) if r['file'].endswith('/fsearch_cli.c'))
    args=shlex.split(compile_row['command']); args.remove('-MD')
    for flag in ('-MQ','-MF'):
        pos=args.index(flag); del args[pos:pos+2]
    args[args.index('-o')+1]=str(obj); args[args.index('-c')+1]=str(copied)
    subprocess.run(args,cwd=build,check=True,capture_output=True)
    link=subprocess.check_output(['uvx','--with','ninja','ninja','-C',str(build),'-t','commands','src/fsearch-cli'],text=True).splitlines()[-1]
    args=shlex.split(link); args[args.index('-o')+1]=str(binary)
    args=[str(obj) if a=='src/fsearch-cli.p/fsearch_cli.c.o' else a for a in args]
    subprocess.run(args,cwd=build,check=True,capture_output=True)
    summary={'production_source_sha256':hashlib.sha256(original.encode()).hexdigest(),'prototype_sha256':hashlib.sha256(source.encode()).hexdigest(),'compiler':compile_row['command'],'workloads':[],'limits':'Pipe protocol, serial requests, no service supervision/reload/socket/queue; native fixtures and potentially warm OS caches.'}
    for count in (10000,100000):
        root=work/f'owned-{count}'; root.mkdir()
        for i in range(count): (root/f'entry{i:06d}.txt').touch()
        snapshot=work/f'snapshot-{count}.db'
        subprocess.run([str(build/'src/tests/snapshot_fixture'),'build',str(snapshot),str(root)],env=env,check=True,capture_output=True,timeout=60)
        snapshot.chmod(0o600)
        ready_start=time.perf_counter()
        process=subprocess.Popen([str(binary),str(snapshot)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        try:
            ready=process.stderr.readline().split(); assert ready[0]=='READY',ready
            ready_ms=(time.perf_counter()-ready_start)*1000; load_ms=int(ready[1])/1000
            status=Path(f'/proc/{process.pid}/status').read_text()
            rss=int(next(line.split()[1] for line in status.splitlines() if line.startswith('VmRSS:')))
            for query in ('entry00000','absent-literal'):
                rounds=[]; matches=[]; oneshot=[]
                for _ in range(31):
                    started=time.perf_counter(); process.stdin.write(query+'\n'); process.stdin.flush()
                    payload=json.loads(process.stdout.readline()); rounds.append((time.perf_counter()-started)*1000)
                    stage=process.stderr.readline().split(); assert stage[0]=='MATCH'
                    matches.append(int(stage[1])/1000)
                    expected={f'entry{i:06d}.txt' for i in range(10)} if query=='entry00000' else set()
                    assert payload['complete'] and {Path(row['path']).name for row in payload['results']}==expected
                    started=time.perf_counter()
                    result=subprocess.run([str(build/'src/fsearch-cli'),'--database',str(snapshot),'--query',query,'--kind','files'],env=env,check=True,capture_output=True,text=True,timeout=15)
                    oneshot.append((time.perf_counter()-started)*1000)
                    assert json.loads(result.stdout)['complete']
                round_stats=percentiles(rounds); one_stats=percentiles(oneshot)
                passed=round_stats['p95_ms']<=(5 if count==10000 else 30) and rss<=131072 and round_stats['p50_ms']<one_stats['p50_ms']
                summary['workloads'].append({'files':count,'query':query,'ready_ms':ready_ms,'load_ms':load_ms,'resident_rss_kib':rss,'resident_roundtrip':round_stats,'matching':percentiles(matches),'oneshot_roundtrip':one_stats,'gate_pass':passed,'resident_raw_ms':rounds,'oneshot_raw_ms':oneshot})
        finally:
            process.stdin.close()
            try: code=process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5); raise
            assert code==0,code
        if count==10000:
            assert shutil.which('strace'), 'strace required for isolation observation'
            shutil.rmtree(root); trace=work/'resident.trace'
            traced=subprocess.Popen(['strace','-f','-e','trace=%file','-o',str(trace),str(binary),str(snapshot)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
            try:
                assert traced.stderr.readline().startswith('READY ')
                time.sleep(6)
                traced.stdin.write('entry00000\n'); traced.stdin.flush()
                payload=json.loads(traced.stdout.readline()); assert len(payload['results'])==10 and payload['complete']
            finally:
                traced.stdin.close()
                try: code=traced.wait(timeout=5)
                except subprocess.TimeoutExpired: traced.kill(); traced.wait(timeout=5); raise
                assert code==0
            trace_text=trace.read_text(); assert str(root) not in trace_text
            output.parent.mkdir(parents=True,exist_ok=True)
            output.with_suffix('.trace').write_text(trace_text)
            summary['isolation']={'idle_seconds':6,'indexed_root_syscalls':0,'root_removed':True,'eof_exit':code,'strace_follow_children':True}
    summary['all_gates_pass']=all(row['gate_pass'] for row in summary['workloads'])
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({**summary,'workloads':[{k:v for k,v in row.items() if not k.endswith('_raw_ms')} for row in summary['workloads']]},indent=2))
