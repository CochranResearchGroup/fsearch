#!/usr/bin/env python3
"""Instrument copied CLI source; never modify production source or scan real roots."""
import json, os, shlex, statistics, subprocess, sys, tempfile, time
from pathlib import Path
repo = Path(__file__).resolve().parents[2]
build = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
source = (repo / 'src/fsearch_cli.c').read_text()
source = source.replace('    int fd = open(options->database,', '    gint64 started = g_get_monotonic_time();\n    int fd = open(options->database,', 1)
source = source.replace('    g_autoptr(FsearchQuery) query =', '    gint64 loaded_at = g_get_monotonic_time();\n    g_autoptr(FsearchQuery) query =', 1)
source = source.replace('    fsearch_query_match_data_free(match_data);', '    gint64 matched_at = g_get_monotonic_time();\n    fsearch_query_match_data_free(match_data);', 1)
source = source.replace('    fputs(out->str, stdout);', '    fprintf(stderr, "PROFILE %lld %lld %lld\\n", (long long)(loaded_at-started), (long long)(matched_at-loaded_at), (long long)(g_get_monotonic_time()-matched_at));\n    fputs(out->str, stdout);', 1)
source = source.replace('        close(STDERR_FILENO);', '        /* profiling only: keep stderr for stage timings */', 1)
env = dict(os.environ)
for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'G_MESSAGES_DEBUG', 'LD_PRELOAD'):
    env.pop(key, None)
with tempfile.TemporaryDirectory(prefix='fsearch-stage-profile-') as tmp:
    work = Path(tmp)
    copied = work / 'profile.c'; copied.write_text(source)
    obj = work / 'profile.o'; binary = work / 'profile-cli'
    compile_row = next(r for r in json.loads((build/'compile_commands.json').read_text()) if r['file'].endswith('/fsearch_cli.c'))
    args = shlex.split(compile_row['command'])
    for flag in ('-MD',):
        args.remove(flag)
    for flag in ('-MQ', '-MF'):
        pos=args.index(flag); del args[pos:pos+2]
    args[args.index('-o')+1]=str(obj); args[args.index('-c')+1]=str(copied)
    subprocess.run(args, cwd=build, check=True, capture_output=True)
    lines=subprocess.check_output(['uvx','--with','ninja','ninja','-C',str(build),'-t','commands','src/fsearch-cli'],text=True).splitlines()
    args=shlex.split(lines[-1]); args[args.index('-o')+1]=str(binary)
    args=[str(obj) if a=='src/fsearch-cli.p/fsearch_cli.c.o' else a for a in args]
    subprocess.run(args,cwd=build,check=True,capture_output=True)
    summary={'build':str(build),'compiler_command':compile_row['command'],'instrumentation':'copied CLI source; load/match/response microsecond markers; worker stderr enabled only in copy','workloads':[]}
    for count in (10000,100000):
        root=work/f'owned-{count}'; root.mkdir()
        for i in range(count): (root/f'entry{i:06d}.txt').touch()
        snapshot=work/f'snapshot-{count}.db'
        subprocess.run([str(build/'src/tests/snapshot_fixture'),'build',str(snapshot),str(root)],env=env,check=True,capture_output=True,timeout=60)
        snapshot.chmod(0o600)
        for query in ('entry00000','absent-literal'):
            samples=[]
            for _ in range(11):
                started=time.perf_counter()
                r=subprocess.run([str(binary),'--database',str(snapshot),'--query',query,'--kind','files'],env=env,capture_output=True,text=True,timeout=15,check=True)
                total=(time.perf_counter()-started)*1000
                line=next(line for line in r.stderr.splitlines() if line.startswith('PROFILE '))
                load,match,response=[int(v)/1000 for v in line.split()[1:]]
                payload=json.loads(r.stdout)
                assert payload['complete'] and len(payload['results'])==(10 if query=='entry00000' else 0)
                samples.append({'load_ms':load,'match_ms':match,'response_ms':response,'total_ms':total,'examined':payload['examined']})
            summary['workloads'].append({'files':count,'query':query,'first':samples[0],'subsequent_p50':{k:statistics.median(row[k] for row in samples[1:]) for k in ('load_ms','match_ms','response_ms','total_ms')},'raw':samples})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k!='raw'} for r in summary['workloads']],indent=2))
