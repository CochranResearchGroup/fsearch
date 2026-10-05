#!/usr/bin/env python3
"""Isolated 64-entry block postings; exact matcher verifies the candidate superset."""
import hashlib, json, shlex, subprocess, tempfile
from pathlib import Path
from benchmark_trigram import REPO, CASES, BENCH, normalize, readline, request, percentiles

def source_variant(entropy=False):
    source=(REPO/'src/prototypes/trigram_probe.c').read_text()
    source=source.replace('static unsigned posting_keys;', 'static unsigned posting_keys;\nstatic unsigned entry_counts[2];')
    source=source.replace('for(uint32_t rank=0;rank<count;++rank)', 'entry_counts[type]=count;\n        for(uint32_t rank=0;rank<count;++rank)')
    source=source.replace('size_t len=strlen(name);', 'uint32_t block=rank/64;\n                size_t len=strlen(name);')
    source=source.replace('list->len-1)!=rank){g_array_append_val(list,rank);', 'list->len-1)!=block){g_array_append_val(list,block);')
    source=source.replace('if(present)g_array_append_val(result,rank);', 'if(present)for(uint32_t expanded=rank*64;expanded<entry_counts[type] && expanded<(rank+1)*64;++expanded){if(!budget())break;g_array_append_val(result,expanded);}')
    source=source.replace('g_array_sort(result,uint_compare);return result;', 'g_array_sort(result,uint_compare);\n    unsigned unique=0;for(unsigned j=0;j<result->len;++j){uint32_t rank=g_array_index(result,uint32_t,j);if(!unique || g_array_index(result,uint32_t,unique-1)!=rank)g_array_index(result,uint32_t,unique++)=rank;}\n    g_array_set_size(result,unique);return result;')
    if entropy:
        needle='else snprintf(name,sizeof(name),"%s-%07u-common.%s",categories[i%8],i,i%3==0 ? "pdf" : i%3==1 ? "txt" : "csv");'
        assert source.count(needle)==1
        source=source.replace(needle, 'else {uint32_t state=i+1;for(unsigned k=0;k<40;++k){state^=state<<13;state^=state>>17;state^=state<<5;name[k]="abcdefghijklmnopqrstuvwxyz0123456789"[state%36];}snprintf(name+40,sizeof(name)-40,"-%07u.txt",i);}')
    core=(REPO/'src/fsearch_headless.c').read_text();body=core[core.index('GString *fsearch_headless_search('):]
    body=body.replace('fsearch_headless_search(', 'prototype_filtered_search(',1)
    needle='        const unsigned count = entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;'
    assert body.count(needle)==1
    body=body.replace(needle, '        g_autoptr(GArray) candidates = candidate_ranks(options,type);\n        if(candidate_limited){*error="candidate_work_limit";return NULL;}\n        const unsigned count = candidates ? candidates->len : entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;')
    body=body.replace('fsearch_database_chunked_array_get_entry(entries, i)', 'fsearch_database_chunked_array_get_entry(entries, candidates ? g_array_index(candidates,uint32_t,i) : i)')
    return source.replace('/* GENERATED_FILTERED_SEARCH */',body)

def compile_variant(build,evidence,entropy):
    stem='entropy' if entropy else 'repetitive'
    generated=evidence/(stem+'.generated.c');generated.write_text(source_variant(entropy))
    binary=evidence/stem
    pkg=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-3.0','gio-unix-2.0','libpcre2-8','icu-uc','sqlite3'],text=True))
    command=['/usr/bin/gcc','-O3','-g','-Wall','-Wextra','-std=gnu11','-D_GNU_SOURCE','-D_FILE_OFFSET_BITS=64','-DHAVE_CONFIG_H','-I'+str(REPO/'src'),'-I'+str(build),'-I'+str(build/'src'),str(generated),str(build/'src/libfsearch.a'),*pkg,'-lm','-pthread','-o',str(binary)]
    result=subprocess.run(command,capture_output=True,text=True);(evidence/(stem+'-compile.txt')).write_text(shlex.join(command)+'\n'+result.stdout+result.stderr);result.check_returncode()
    return binary

def current_rss(process):
    status=Path(f'/proc/{process.pid}/status').read_text()
    return int(next(line.split()[1] for line in status.splitlines() if line.startswith('VmRSS:')))

def main():
    build=Path('/tmp/fsearch-warm-release-build');evidence=REPO/'docs/research/compact-evidence';evidence.mkdir(exist_ok=True)
    result={'prototype_only':True,'block_entries':64,'actual_repaired_library':True,'scope':'stdio prototype, not real socket or aggregate supervisor memory acceptance','fixtures':[]}
    def save(): (evidence/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='fsearch-compact-owned-') as temporary:
        for entropy in (False,True):
            stem='entropy' if entropy else 'repetitive';print(stem,flush=True)
            binary=compile_variant(build,evidence,entropy);snapshot=Path(temporary)/(stem+'.db')
            subprocess.run([str(binary),'build',str(snapshot),'1000000'],check=True,timeout=90,capture_output=True);snapshot.chmod(0o600)
            row={'fixture':stem,'files':1000000,'snapshot_bytes':snapshot.stat().st_size,'snapshot_sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'modes':[]};result['fixtures'].append(row);save()
            oracle={}
            for mode in ('oracle','native'):
                print(stem,mode,flush=True)
                with (evidence/(stem+'-'+mode+'.stderr.txt')).open('wb') as err:
                    process=subprocess.Popen([str(binary),mode,str(snapshot),'unused'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err)
                    try:
                        ready=readline(process,35);assert ready.get('ready'),ready
                        entry={'mode':mode,'ready':ready,'steady_rss_kib':current_rss(process),'cases':[]};row['modes'].append(entry);save()
                        for label,query,options in CASES:
                            first=request(process,query,dict(options,max_candidates=1000065) if mode=='oracle' else options)
                            if mode=='oracle':oracle[label]=first['response']
                            elif first['response'].get('status')!='work_limit' and not first['candidate_limited']:
                                assert normalize(first['response'])==normalize(oracle[label]),(stem,label,first,oracle[label])
                            case={'label':label,'first':first,'complete_oracle_parity':mode=='native' and normalize(first['response'])==normalize(oracle[label])}
                            if mode=='native' and label in BENCH:
                                samples=[request(process,query,options)['elapsed_ms'] for _ in range(100 if label in ('rare','late','absent','present_grams_absent') else 5)]
                                case['latency']=percentiles(samples);case['raw_ms']=samples
                            entry['cases'].append(case);save()
                        entry['final_rss_kib']=current_rss(process)
                    finally:
                        process.stdin.close()
                        try:process.wait(timeout=3)
                        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
                        process.stdout.close()
                    entry['returncode']=process.returncode;save()
            binary.unlink()
    result['complete']=True;save()
    print(evidence/'comparison.json',flush=True)
if __name__=='__main__':main()
