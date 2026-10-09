/* Production generation lifecycle tests. Owned in-memory filenames only. GPL-2.0-or-later. */
#include "fsearch_catalog.h"
#include "fsearch_query.h"
#include "fsearch_database_entry.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>

static FsearchCatalogLimits limits={16*1024*1024,256,256,16};
static const FsearchCatalogEntry seed[]={
    {0,0,FSEARCH_CATALOG_FOLDER,"/__catalog_owned__"},
    {1,0,FSEARCH_CATALOG_FOLDER,"alpha"},
    {2,1,FSEARCH_CATALOG_FOLDER,"nested"},
    {3,2,FSEARCH_CATALOG_FILE,"CAFÉ-ÉCOLE.pdf"},
    {4,2,FSEARCH_CATALOG_FILE,"raw-\xff.txt"},
    {5,2,FSEARCH_CATALOG_FILE,"literal*wild?.txt"},
    {6,2,FSEARCH_CATALOG_FILE,"Straße.txt"},
    {7,0,FSEARCH_CATALOG_FILE,"Straße.txt"},
};
static FsearchCatalog *make(FsearchCatalogLimits l) {
    const char*error=NULL;FsearchCatalog*c=fsearch_catalog_new(seed,G_N_ELEMENTS(seed),&l,&error);g_assert_nonnull(c);return c;
}
static FsearchCatalogStatus status(FsearchCatalog*c){FsearchCatalogStatus s;fsearch_catalog_status(c,&s);return s;}
static void path_is(FsearchCatalogView*v,unsigned id,const char*expected) {
    g_autofree char*p=fsearch_catalog_view_path(v,id);g_assert_cmpstr(p,==,expected);
}
static void compact(FsearchCatalog*c) {
    const char*e=NULL;FsearchCatalogBuild*t=fsearch_catalog_compact_begin(c,&e);g_assert_nonnull(t);
    g_assert_true(fsearch_catalog_compact_run(t,&e));g_assert_true(fsearch_catalog_compact_validate(t,&e));
    g_assert_true(fsearch_catalog_compact_publish(c,t,&e));fsearch_catalog_compact_free(c,t);
}
static void test_immutable(void) {
    g_autoptr(FsearchCatalog)c=make(limits);const char*e=NULL;
    FsearchCatalogView*old=fsearch_catalog_acquire(c);
    g_assert_true(fsearch_catalog_change(c,1,1,0,FSEARCH_CATALOG_FOLDER,"moved",&e));
    g_autoptr(FsearchCatalogView)next=fsearch_catalog_acquire(c);
    path_is(old,3,"/__catalog_owned__/alpha/nested/CAFÉ-ÉCOLE.pdf");
    path_is(next,3,"/__catalog_owned__/moved/nested/CAFÉ-ÉCOLE.pdf");
    g_assert_false(fsearch_catalog_change(c,2,1,2,FSEARCH_CATALOG_FOLDER,"cycle",&e));g_assert_cmpstr(e,==,"cycle");
    g_assert_false(fsearch_catalog_change(c,3,3,2,FSEARCH_CATALOG_FILE,"gap",&e));g_assert_cmpstr(e,==,"sequence_gap");
    uint32_t id=0;
    g_assert_false(fsearch_catalog_create(c,2,2,FSEARCH_CATALOG_FILE,"Straße.txt",&id,&e));g_assert_cmpstr(e,==,"namespace_collision");
    g_assert_false(fsearch_catalog_change(c,2,2,1,FSEARCH_CATALOG_FILE,"replacement",&e));g_assert_cmpstr(e,==,"type_transition_requires_new_identity");
    g_assert_true(fsearch_catalog_change(c,2,1,0,FSEARCH_CATALOG_DELETED,NULL,&e));
    compact(c);
    g_assert_false(fsearch_catalog_change(c,3,3,0,FSEARCH_CATALOG_FILE,"resurrected",&e));
    g_assert_true(fsearch_catalog_create(c,3,0,FSEARCH_CATALOG_FOLDER,"moved",&id,&e));g_assert_cmpuint(id,>,7);
    g_autoptr(FsearchCatalogView)latest=fsearch_catalog_acquire(c);FsearchCatalogEntry entry;
    g_assert_false(fsearch_catalog_view_get(latest,3,&entry));
    path_is(next,4,"/__catalog_owned__/moved/nested/raw-\xff.txt");
    fsearch_catalog_view_unref(old);
    g_assert_cmpuint(status(c).generation,==,1);
}
static void test_replay(void) {
    g_autoptr(FsearchCatalog)c=make(limits);const char*e=NULL;
    for(unsigned cycle=0;cycle<4;cycle++) {
        FsearchCatalogBuild*t=fsearch_catalog_compact_begin(c,&e);g_assert_nonnull(t);
        g_assert_true(fsearch_catalog_compact_run(t,&e));g_assert_true(fsearch_catalog_compact_validate(t,&e));
        g_autofree char*name=g_strdup_printf("round-%u",cycle);uint64_t seq=status(c).sequence;
        g_assert_true(fsearch_catalog_change(c,seq+1,1,0,FSEARCH_CATALOG_FOLDER,name,&e));
        g_assert_true(fsearch_catalog_change(c,seq+2,3,2,FSEARCH_CATALOG_FILE,"same*literal?.pdf",&e));
        g_autoptr(FsearchCatalogView)before=fsearch_catalog_acquire(c);g_autofree char*expected=fsearch_catalog_view_path(before,3);
        g_assert_true(fsearch_catalog_compact_publish(c,t,&e));
        g_autoptr(FsearchCatalogView)after=fsearch_catalog_acquire(c);path_is(after,3,expected);
        g_assert_cmpuint(fsearch_catalog_view_sequence(after),==,seq+2);
        g_assert_cmpuint(fsearch_catalog_view_generation(after),==,cycle+1);
        g_assert_false(fsearch_catalog_compact_publish(c,t,&e));g_assert_cmpstr(e,==,"builder_already_published");
        fsearch_catalog_compact_free(c,t);
    }
}
static void test_overflow(void) {
    FsearchCatalogLimits l=limits;l.replay_limit=2;g_autoptr(FsearchCatalog)c=make(l);const char*e=NULL;
    FsearchCatalogBuild*t=fsearch_catalog_compact_begin(c,&e);g_assert_nonnull(t);
    g_assert_true(fsearch_catalog_compact_run(t,&e));g_assert_true(fsearch_catalog_compact_validate(t,&e));
    for(unsigned i=1;i<=3;i++){g_autofree char*n=g_strdup_printf("accepted-%u",i);g_assert_true(fsearch_catalog_change(c,i,3,2,FSEARCH_CATALOG_FILE,n,&e));}
    g_assert_false(fsearch_catalog_compact_publish(c,t,&e));g_assert_cmpstr(e,==,"replay_overflow");
    g_assert_cmpuint(status(c).sequence,==,3);g_assert_cmpuint(status(c).generation,==,0);
    g_assert_cmpstr(status(c).deferred_reason,==,"replay_overflow");
    fsearch_catalog_compact_free(c,t);compact(c);
    g_assert_null(status(c).deferred_reason);g_assert_cmpuint(status(c).reserved_bytes,==,0);
}
static void test_failures(void) {
    const char*reasons[]={"builder_failure","validation_failure","publication_failure"};
    for(unsigned i=0;i<G_N_ELEMENTS(reasons);i++) {
        g_autoptr(FsearchCatalog)c=make(limits);const char*e=NULL;FsearchCatalogBuild*t=fsearch_catalog_compact_begin(c,&e);
        g_assert_nonnull(t);
        if(i){g_assert_true(fsearch_catalog_compact_run(t,&e));if(i==2)g_assert_true(fsearch_catalog_compact_validate(t,&e));}
        fsearch_catalog_compact_abort(c,t,reasons[i]);
        g_assert_false(fsearch_catalog_compact_publish(c,t,&e));g_assert_cmpstr(e,==,reasons[i]);
        g_assert_cmpuint(status(c).generation,==,0);g_assert_cmpuint(status(c).sequence,==,0);
        fsearch_catalog_compact_free(c,t);g_assert_cmpuint(status(c).reserved_bytes,==,0);
    }
    g_autoptr(FsearchCatalog)c=make(limits);const char*e=NULL;FsearchCatalogBuild*t=fsearch_catalog_compact_begin(c,&e);
    g_assert_true(fsearch_catalog_compact_run(t,&e));
    g_assert_false(fsearch_catalog_compact_publish(c,t,&e));g_assert_cmpstr(e,==,"builder_not_validated");
    g_assert_true(fsearch_catalog_compact_validate(t,&e));g_assert_true(fsearch_catalog_compact_publish(c,t,&e));
    fsearch_catalog_compact_free(c,t);
}
static void test_readers(void) {
    FsearchCatalogLimits l=limits;l.view_limit=3;g_autoptr(FsearchCatalog)c=make(l);const char*e=NULL;
    FsearchCatalogView*a=fsearch_catalog_acquire(c);
    g_assert_true(fsearch_catalog_change(c,1,3,2,FSEARCH_CATALOG_FILE,"first",&e));
    g_autoptr(FsearchCatalogView)b=fsearch_catalog_acquire(c);
    g_assert_true(fsearch_catalog_change(c,2,3,2,FSEARCH_CATALOG_FILE,"second",&e));
    g_assert_false(fsearch_catalog_change(c,3,3,2,FSEARCH_CATALOG_FILE,"third",&e));g_assert_cmpstr(e,==,"reader_budget");
    g_assert_cmpuint(status(c).sequence,==,2);
    fsearch_catalog_view_unref(a);
    g_assert_true(fsearch_catalog_change(c,3,3,2,FSEARCH_CATALOG_FILE,"third",&e));
    path_is(b,3,"/__catalog_owned__/alpha/nested/first");
}
static void test_budget(void) {
    FsearchCatalogLimits l=limits;l.overlay_limit=1;g_autoptr(FsearchCatalog)c=make(l);const char*e=NULL;
    g_assert_true(fsearch_catalog_change(c,1,3,2,FSEARCH_CATALOG_FILE,"first",&e));
    g_assert_false(fsearch_catalog_change(c,2,4,2,FSEARCH_CATALOG_FILE,"second",&e));g_assert_cmpstr(e,==,"overlay_budget");
    compact(c);g_assert_true(fsearch_catalog_change(c,2,4,2,FSEARCH_CATALOG_FILE,"second",&e));
    FsearchCatalogLimits small=limits;small.memory_limit=2048;small.replay_limit=16;
    FsearchCatalog*x=fsearch_catalog_new(seed,G_N_ELEMENTS(seed),&small,&e);
    g_assert_nonnull(x);FsearchCatalogBuild*t=fsearch_catalog_compact_begin(x,&e);g_assert_null(t);
    g_assert_cmpstr(e,==,"memory_budget");g_assert_cmpuint(status(x).generation,==,0);fsearch_catalog_free(x);
    small=limits;x=make(limits);small.memory_limit=status(x).accounted_bytes+64;fsearch_catalog_free(x);
    x=fsearch_catalog_new(seed,G_N_ELEMENTS(seed),&small,&e);g_assert_nonnull(x);
    g_assert_false(fsearch_catalog_change(x,1,3,2,FSEARCH_CATALOG_FILE,"pressure",&e));
    g_assert_cmpstr(e,==,"memory_budget");g_assert_cmpuint(status(x).sequence,==,0);
    fsearch_catalog_free(x);
}
static void test_shutdown(void) {
    const char*e=NULL;
    for(unsigned phase=0;phase<3;phase++) {
        FsearchCatalog*c=make(limits);FsearchCatalogView*v=fsearch_catalog_acquire(c);FsearchCatalogBuild*t=fsearch_catalog_compact_begin(c,&e);
        if(phase){g_assert_true(fsearch_catalog_compact_run(t,&e));if(phase==2)g_assert_true(fsearch_catalog_compact_validate(t,&e));}
        fsearch_catalog_close(c);g_assert_null(fsearch_catalog_acquire(c));
        g_assert_false(fsearch_catalog_compact_publish(c,t,&e));g_assert_cmpstr(e,==,"closed");
        fsearch_catalog_compact_free(c,t);fsearch_catalog_free(c);
        path_is(v,3,"/__catalog_owned__/alpha/nested/CAFÉ-ÉCOLE.pdf");fsearch_catalog_view_unref(v);
    }
}
typedef struct {FsearchCatalog*c;gint stop;gint reads;} Reader;
static gpointer reader(void*data) {
    Reader*r=data;
    while(!g_atomic_int_get(&r->stop)) {
        FsearchCatalogView*v=fsearch_catalog_acquire(r->c);g_assert_nonnull(v);
        uint64_t seq=fsearch_catalog_view_sequence(v);
        g_autofree char*expected=g_strdup_printf("/__catalog_owned__/folder-%llu/file-%llu",(unsigned long long)((seq+1)/2),(unsigned long long)(seq/2));
        path_is(v,2,expected);
        /* Exercise the actual literal matcher on the pinned generation's path. */
        g_autofree char*path=fsearch_catalog_view_path(v,2);
        FsearchDatabaseEntry*entry=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,path,NULL,DATABASE_ENTRY_TYPE_FILE);
        FsearchQuery*q=fsearch_query_new_literal(expected,QUERY_FLAG_MATCH_CASE);
        FsearchQueryMatchData*m=fsearch_query_match_data_new(NULL,NULL);fsearch_query_match_data_set_entry(m,entry);
        g_assert_true(fsearch_query_match(q,m));fsearch_query_match_data_free(m);fsearch_query_unref(q);db_entry_free(entry);
        fsearch_catalog_view_unref(v);g_atomic_int_inc(&r->reads);
    }
    return NULL;
}
static gpointer builder(void*data){const char*e=NULL;g_assert_true(fsearch_catalog_compact_run(data,&e));g_assert_true(fsearch_catalog_compact_validate(data,&e));return NULL;}
typedef struct { unsigned count; uint64_t sequence; FsearchCatalogView *view; } Oracle;
static bool oracle_entry(const FsearchCatalogEntry*e,void*data) {
    Oracle*x=data;x->count++;
    g_autofree char*name=e->id==0?g_strdup("/__catalog_owned__"):e->id==1?g_strdup_printf("folder-%llu",(unsigned long long)((x->sequence+1)/2)):e->id==2?g_strdup_printf("file-%llu",(unsigned long long)(x->sequence/2)):g_strdup_printf("fixed-%07u.txt",e->id);
    g_assert_cmpstr(e->name,==,name);g_assert_cmpuint(e->parent,==,e->id<2?0:1);
    if(e->id<3||e->id%1000==0) {
        g_autofree char*expected=e->id==0?g_strdup(name):e->id==1?g_strconcat("/__catalog_owned__/",name,NULL):g_strdup_printf("/__catalog_owned__/folder-%llu/%s",(unsigned long long)((x->sequence+1)/2),name);
        path_is(x->view,e->id,expected);
    }
    return true;
}
static void oracle_check(FsearchCatalog*c,unsigned count) {
    g_autoptr(FsearchCatalogView)v=fsearch_catalog_acquire(c);Oracle x={.sequence=fsearch_catalog_view_sequence(v),.view=v};
    g_assert_true(fsearch_catalog_view_visit(v,oracle_entry,&x));g_assert_cmpuint(x.count,==,count);
}
static void churn(unsigned count,bool report) {
    gint64 started=g_get_monotonic_time();
    FsearchCatalogEntry*rows=g_new0(FsearchCatalogEntry,count);char**names=g_new0(char*,count);
    for(unsigned i=0;i<count;i++) {
        names[i]=i==0?g_strdup("/__catalog_owned__"):i==1?g_strdup("folder-0"):i==2?g_strdup("file-0"):g_strdup_printf("fixed-%07u.txt",i);
        rows[i]=(FsearchCatalogEntry){i,i<2?0:1,i<2?FSEARCH_CATALOG_FOLDER:FSEARCH_CATALOG_FILE,names[i]};
    }
    FsearchCatalogLimits l={1024UL*1024*1024,256,256,16};const char*e=NULL;
    FsearchCatalog*c=fsearch_catalog_new(rows,count,&l,&e);g_assert_nonnull(c);
    for(unsigned i=0;i<count;i++)g_free(names[i]);
    g_free(names);g_free(rows);
    oracle_check(c,count);
    double startup=(g_get_monotonic_time()-started)/1000.;
    Reader r={.c=c};GThread*readers[4];for(unsigned i=0;i<4;i++)readers[i]=g_thread_new("catalog-reader",reader,&r);
    double compact_max=0;unsigned compactions=0;
    for(unsigned round=0;round<4;round++) {
        gint64 t0=g_get_monotonic_time();FsearchCatalogBuild*t=fsearch_catalog_compact_begin(c,&e);g_assert_nonnull(t);
        GThread*thread=g_thread_new("catalog-builder",builder,t);
        for(unsigned j=0;j<50;j++) {
            uint64_t seq=status(c).sequence+1;g_autofree char*name=g_strdup_printf("folder-%llu",(unsigned long long)((seq+1)/2));
            g_assert_true(fsearch_catalog_change(c,seq,1,0,FSEARCH_CATALOG_FOLDER,name,&e));
            g_autofree char*leaf=g_strdup_printf("file-%llu",(unsigned long long)((seq+1)/2));
            g_assert_true(fsearch_catalog_change(c,seq+1,2,1,FSEARCH_CATALOG_FILE,leaf,&e));
        }
        g_thread_join(thread);g_assert_true(fsearch_catalog_compact_publish(c,t,&e));fsearch_catalog_compact_free(c,t);
        oracle_check(c,count);
        compact_max=MAX(compact_max,(g_get_monotonic_time()-t0)/1000.);compactions++;
    }
    g_atomic_int_set(&r.stop,1);for(unsigned i=0;i<4;i++)g_thread_join(readers[i]);
    g_assert_cmpint(r.reads,>,0);FsearchCatalogStatus s=status(c);g_assert_cmpuint(s.generation,==,4);g_assert_cmpuint(s.sequence,==,400);
    if(report){struct rusage usage;getrusage(RUSAGE_SELF,&usage);printf("{\"entries\":%u,\"compactions\":%u,\"accepted_events\":400,\"reader_checks\":%d,\"startup_ms\":%.3f,\"compaction_max_ms\":%.3f,\"accounted_bytes\":%zu,\"peak_committed_bytes\":%zu,\"worker_peak_rss_kib\":%ld,\"elapsed_ms\":%.3f}\n",count,compactions,r.reads,startup,compact_max,s.accounted_bytes,s.peak_bytes,usage.ru_maxrss,(g_get_monotonic_time()-started)/1000.);}
    fsearch_catalog_free(c);
}
static void test_churn(void){churn(128,false);}
int main(int argc,char**argv) {
    if(argc==3&&!strcmp(argv[1],"--scale")){churn(atoi(argv[2]),true);return 0;}
    g_test_init(&argc,&argv,NULL);
    g_test_add_func("/catalog/immutable",test_immutable);g_test_add_func("/catalog/replay",test_replay);
    g_test_add_func("/catalog/replay-overflow",test_overflow);g_test_add_func("/catalog/failures",test_failures);
    g_test_add_func("/catalog/lagging-reader",test_readers);g_test_add_func("/catalog/budgets",test_budget);
    g_test_add_func("/catalog/shutdown",test_shutdown);g_test_add_func("/catalog/concurrent-churn",test_churn);
    return g_test_run();
}
