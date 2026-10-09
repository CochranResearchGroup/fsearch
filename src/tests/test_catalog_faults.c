/* Compile the production implementation directly to inject allocation/corruption
 * faults without shipping a testing backdoor in the library. GPL-2.0-or-later. */
#include <glib.h>
#include <stdlib.h>
static gint allocation_failure=-1;
static void *fault_calloc(size_t n,size_t bytes) {
    if(allocation_failure==0)return NULL;
    if(allocation_failure>0)allocation_failure--;
    return calloc(n,bytes);
}
#define calloc fault_calloc
#include "../fsearch_catalog.c"
#undef calloc

static const FsearchCatalogEntry seed[]={
    {0,0,FSEARCH_CATALOG_FOLDER,"/__fault_owned__"},
    {1,0,FSEARCH_CATALOG_FOLDER,"alpha"},
    {2,1,FSEARCH_CATALOG_FILE,"before.txt"}
};
static const FsearchCatalogLimits limits={1024*1024,64,64,8};
static void unchanged(FsearchCatalog*c) {
    FsearchCatalogStatus s;fsearch_catalog_status(c,&s);g_assert_cmpuint(s.sequence,==,0);g_assert_cmpuint(s.generation,==,0);
    g_autoptr(FsearchCatalogView)v=fsearch_catalog_acquire(c);g_autofree char*p=fsearch_catalog_view_path(v,2);
    g_assert_cmpstr(p,==,"/__fault_owned__/alpha/before.txt");
}
static void test_allocations(void) {
    const char*error=NULL;
    for(int i=0;i<4;i++) {
        allocation_failure=i;FsearchCatalog*c=fsearch_catalog_new(seed,3,&limits,&error);allocation_failure=-1;
        g_assert_null(c);
    }
    for(unsigned stage=0;stage<4;stage++) {
        FsearchCatalog*c=fsearch_catalog_new(seed,3,&limits,&error);g_assert_nonnull(c);FsearchCatalogBuild*t=NULL;
        if(stage>1){t=fsearch_catalog_compact_begin(c,&error);g_assert_nonnull(t);}
        if(stage==3){g_assert_true(fsearch_catalog_compact_run(t,&error));g_assert_true(fsearch_catalog_compact_validate(t,&error));}
        allocation_failure=0;
        if(stage==0)g_assert_false(fsearch_catalog_change(c,1,2,1,FSEARCH_CATALOG_FILE,"after.txt",&error));
        if(stage==1)g_assert_null(fsearch_catalog_compact_begin(c,&error));
        if(stage==2)g_assert_false(fsearch_catalog_compact_run(t,&error));
        if(stage==3)g_assert_false(fsearch_catalog_compact_publish(c,t,&error));
        allocation_failure=-1;unchanged(c);
        if(t)fsearch_catalog_compact_free(c,t);
        FsearchCatalogStatus s;fsearch_catalog_status(c,&s);g_assert_cmpuint(s.reserved_bytes,==,0);
        fsearch_catalog_free(c);
    }
}
static void test_corruption(void) {
    const char*error=NULL;FsearchCatalog*c=fsearch_catalog_new(seed,3,&limits,&error);g_assert_nonnull(c);
    FsearchCatalogBuild*t=fsearch_catalog_compact_begin(c,&error);g_assert_nonnull(t);g_assert_true(fsearch_catalog_compact_run(t,&error));
    g_assert_true(fsearch_catalog_compact_validate(t,&error));
    /* Revalidation failure must revoke a previous validation success. */
    /* A candidate with a broken parent must fail validation and cannot publish. */
    t->replacement->entries[2].parent=2;
    g_assert_false(fsearch_catalog_compact_validate(t,&error));g_assert_cmpstr(error,==,"validation_failed");
    g_assert_false(fsearch_catalog_compact_publish(c,t,&error));unchanged(c);
    fsearch_catalog_compact_free(c,t);fsearch_catalog_free(c);
}
int main(int argc,char**argv) {
    g_test_init(&argc,&argv,NULL);g_test_add_func("/catalog-faults/allocation",test_allocations);
    g_test_add_func("/catalog-faults/candidate-corruption",test_corruption);return g_test_run();
}
