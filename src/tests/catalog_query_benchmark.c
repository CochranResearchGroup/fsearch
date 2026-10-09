/* Owned synthetic query/resource measurement; never installed. GPL-2.0-or-later. */
#include "fsearch_catalog_query.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/resource.h>
static int compare(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    unsigned count=atoi(argv[1]);if(count<100||count>10000000)return 2;
    gint64 start=g_get_monotonic_time();
    FsearchCatalogEntry *rows=g_new0(FsearchCatalogEntry,count);char **names=g_new0(char*,count);
    for(unsigned i=0;i<count;i++) {
        names[i]=i==0?g_strdup("/__benchmark_owned__"):i==1?g_strdup("ancestor"):g_strdup_printf("fixed-%07u.txt",i);
        rows[i]=(FsearchCatalogEntry){i,i<2?0:1,i<2?FSEARCH_CATALOG_FOLDER:FSEARCH_CATALOG_FILE,names[i]};
    }
    FsearchCatalogLimits limits={1200UL*1024*1024,4096,4096,16};const char *error=NULL;
    g_autoptr(FsearchCatalog)c=fsearch_catalog_new(rows,count,&limits,&error);g_assert_nonnull(c);
    for(unsigned i=0;i<count;i++)g_free(names[i]);
    g_free(names);g_free(rows);
    double load_ms=(g_get_monotonic_time()-start)/1000.;
    g_autoptr(FsearchCatalogView)v=fsearch_catalog_acquire(c);
    struct {const char *name,*query,*stop;bool path;unsigned returned;double gate;} cases[]={
        {"selective","fixed-0000042.txt","ok",false,1,10},
        {"zero","no-such-qzx-entry","ok",false,0,10},
        {"common","fixed","result_limit",false,1000,100},
        {"short","x","result_limit",false,1000,100},
        {"ancestor","ancestor","result_limit",true,1000,250},
        {"slash_path","ancestor/fixed-0000042.txt","ok",true,1,250},
    };
    bool passed=true;printf("{\"entries\":%u,\"load_ms\":%.3f,\"queries\":[",count,load_ms);
    for(unsigned k=0;k<G_N_ELEMENTS(cases);k++) {
        double times[30];FsearchCatalogQueryResult r;
        Options o={.query=(char*)cases[k].query,.kind="files",.path=cases[k].path,.limit=1000,.max_candidates=500000,.max_bytes=1048576,.timeout_ms=1000};
        for(unsigned j=0;j<32;j++) {
            gint64 begin=g_get_monotonic_time();g_assert_true(fsearch_catalog_query(v,&o,&r,&error));
            double ms=(g_get_monotonic_time()-begin)/1000.;if(j>=2)times[j-2]=ms;
            if(j<31)fsearch_catalog_query_clear(&r);
        }
        qsort(times,30,sizeof(double),compare);
        unsigned expected=cases[k].returned;if(!strcmp(cases[k].name,"common")||!strcmp(cases[k].name,"short")||!strcmp(cases[k].name,"ancestor"))expected=MIN(1000,count-2);
        const char *stop=expected<1000?"ok":cases[k].stop;
        bool valid=!strcmp(r.stop,stop)&&r.returned==expected,gate=valid&&times[28]<=cases[k].gate;passed &= gate;
        printf("%s{\"class\":\"%s\",\"p50_ms\":%.3f,\"p95_ms\":%.3f,\"max_ms\":%.3f,\"stop\":\"%s\",\"returned\":%u,\"examined\":%u,\"candidate_blocks\":%u,\"correct\":%s,\"gate_pass\":%s}",k?",":"",cases[k].name,times[14],times[28],times[29],r.stop,r.returned,r.examined,r.candidate_blocks,valid?"true":"false",gate?"true":"false");
        fsearch_catalog_query_clear(&r);
    }
    FsearchCatalogStatus state;fsearch_catalog_status(c,&state);struct rusage usage;getrusage(RUSAGE_SELF,&usage);
    printf("],\"accounted_bytes\":%zu,\"process_peak_rss_kib\":%ld,\"result\":\"%s\"}\n",state.accounted_bytes,usage.ru_maxrss,passed?"pass":"fail");
    return passed?0:1;
}
