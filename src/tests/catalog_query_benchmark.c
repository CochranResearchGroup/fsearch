/* Owned synthetic query/resource measurement; never installed. GPL-2.0-or-later. */
#include "fsearch_catalog_query.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/resource.h>
static int compare(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
int main(int argc,char **argv) {
    if(argc!=2&&argc!=3)return 2;
    unsigned count=atoi(argv[1]);if(count<100||count>10000000)return 2;
    unsigned folders=argc==3?atoi(argv[2]):2;
    if(folders<2||folders>=count)return 2;
    unsigned unicode=0,raw=0,punctuation=0,ancestor_hits=0;
    unsigned target=folders==2?42:folders+42;
    if(target>=count)return 2;
    gint64 start=g_get_monotonic_time();
    FsearchCatalogEntry *rows=g_new0(FsearchCatalogEntry,count);char **names=g_new0(char*,count);
    for(unsigned i=0;i<count;i++) {
        if(!i)names[i]=g_strdup("/__benchmark_owned__");
        else if(i<folders)names[i]=folders==2?g_strdup("ancestor"):g_strdup_printf("folder-%07u",i);
        else if(folders>2&&i!=target&&i%1000==0){names[i]=g_strdup_printf("CAFÉ-%07u.pdf",i);unicode++;}
        else if(folders>2&&i!=target&&i%1000==1){names[i]=g_strdup_printf("raw-\xff-%07u.txt",i);raw++;}
        else if(folders>2&&i!=target&&i%1000==2){names[i]=g_strdup_printf("literal*?-%07u.txt",i);punctuation++;}
        else names[i]=g_strdup_printf("fixed-%07u.txt",i);
        unsigned parent=i<folders?(i? (i-1)/10:0):1+i%(folders-1);
        rows[i]=(FsearchCatalogEntry){i,parent,i<folders?FSEARCH_CATALOG_FOLDER:FSEARCH_CATALOG_FILE,names[i]};
        if(i>=folders){unsigned ancestor=parent;while(ancestor>1)ancestor=(ancestor-1)/10;if(ancestor==1)ancestor_hits++;}
    }
    unsigned unicode_target=((folders+999)/1000)*1000;
    if(unicode_target==target)unicode_target+=1000;
    g_autofree char *unicode_path=unicode_target<count&&folders>2?g_strdup_printf("%s/%s",names[rows[unicode_target].parent],names[unicode_target]):g_strdup("missing/é");
    g_autofree char *selective=g_strdup(names[target]);
    g_autofree char *slash=g_strdup_printf("%s/%s",names[rows[target].parent],names[target]);
    FsearchCatalogLimits limits={1200UL*1024*1024,4096,4096,16};const char *error=NULL;
    g_autoptr(FsearchCatalog)c=fsearch_catalog_new(rows,count,&limits,&error);g_assert_nonnull(c);
    for(unsigned i=0;i<count;i++)g_free(names[i]);
    g_free(names);g_free(rows);
    double load_ms=(g_get_monotonic_time()-start)/1000.;
    g_autoptr(FsearchCatalogView)v=fsearch_catalog_acquire(c);
    unsigned normal=count-folders-unicode-raw-punctuation;
    struct {const char *name,*query;bool path;unsigned hits;double gate;const char *kind,*extension;} cases[]={
        {"selective",selective,false,1,10,"files",NULL},
        {"zero","no-such-qzx-entry",false,0,10,"files",NULL},
        {"common","fixed",false,normal,100,"files",NULL},
        {"short","x",false,normal,100,"files",NULL},
        {"ancestor",folders==2?"ancestor":"folder-0000001",true,ancestor_hits,250,"files",NULL},
        {"slash_path",slash,true,1,250,"files",NULL},
        {"unicode","café",false,unicode,100,"files","pdf"},
        {"raw_bytes","raw-",false,raw,100,"files",NULL},
        {"punctuation","literal*?",false,punctuation,100,"files",NULL},
        {"unicode_path",unicode_path,true,folders>2&&unicode_target<count?1:0,250,"files",NULL},
        {"unicode_path_zero","missing/ÉCOLE",true,0,250,"files",NULL},
        {"folder_filter",folders==2?"ancestor":"folder-",false,folders-1,100,"folders",NULL},
    };
    bool passed=true;printf("{\"entries\":%u,\"folders\":%u,\"load_ms\":%.3f,\"queries\":[",count,folders,load_ms);
    for(unsigned k=0;k<G_N_ELEMENTS(cases);k++) {
        double times[30];FsearchCatalogQueryResult r;
        Options o={.query=(char*)cases[k].query,.kind=(char*)cases[k].kind,.extension=(char*)cases[k].extension,.path=cases[k].path,.limit=1000,.max_candidates=500000,.max_bytes=1048576,.timeout_ms=1000};
        for(unsigned j=0;j<32;j++) {
            gint64 begin=g_get_monotonic_time();g_assert_true(fsearch_catalog_query(v,&o,&r,&error));
            double ms=(g_get_monotonic_time()-begin)/1000.;if(j>=2)times[j-2]=ms;
            if(j<31)fsearch_catalog_query_clear(&r);
        }
        qsort(times,30,sizeof(double),compare);
        unsigned expected=MIN(1000,cases[k].hits);
        const char *stop=cases[k].hits>1000?"result_limit":"ok";
        bool valid=!strcmp(r.stop,stop)&&r.returned==expected,gate=valid&&times[28]<=cases[k].gate;passed &= gate;
        printf("%s{\"class\":\"%s\",\"p50_ms\":%.3f,\"p95_ms\":%.3f,\"max_ms\":%.3f,\"stop\":\"%s\",\"returned\":%u,\"examined\":%u,\"candidate_blocks\":%u,\"correct\":%s,\"gate_pass\":%s}",k?",":"",cases[k].name,times[14],times[28],times[29],r.stop,r.returned,r.examined,r.candidate_blocks,valid?"true":"false",gate?"true":"false");
        fsearch_catalog_query_clear(&r);
    }
    FsearchCatalogStatus state;fsearch_catalog_status(c,&state);struct rusage usage;getrusage(RUSAGE_SELF,&usage);
    printf("],\"accounted_bytes\":%zu,\"process_peak_rss_kib\":%ld,\"result\":\"%s\"}\n",state.accounted_bytes,usage.ru_maxrss,passed?"pass":"fail");
    return passed?0:1;
}
