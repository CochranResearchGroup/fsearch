/* Test-only adapter for native catalog/rebuilt snapshot parity. Not installed. */
#include "fsearch_catalog.h"
#include "fsearch_headless.h"
#include "fsearch_database_entry.h"
#include "fsearch_query.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

typedef struct {FsearchDatabaseEntry *entry,*parent;char*path;unsigned kind;} Hit;
static void hit_free(void*data){Hit*h=data;db_entry_free(h->entry);if(h->parent)db_entry_free(h->parent);g_free(h->path);g_free(h);}
static int compare(const void*a,const void*b){Hit*x=*(Hit**)a,*y=*(Hit**)b;if(x->kind!=y->kind)return(x->kind>y->kind)-(x->kind<y->kind);return db_entry_compare_entries_by_name(&x->entry,&y->entry);}
typedef struct {FsearchCatalogView*view;Options*options;FsearchQuery*query;FsearchQueryMatchData*match;GPtrArray*hits;} Search;
static bool visit(const FsearchCatalogEntry*e,void*data) {
    Search*s=data;Options*o=s->options;
    if((!strcmp(o->kind,"files")&&e->kind!=FSEARCH_CATALOG_FILE)||(!strcmp(o->kind,"folders")&&e->kind!=FSEARCH_CATALOG_FOLDER))return true;
    Hit*h=g_new0(Hit,1);h->kind=e->kind;h->path=fsearch_catalog_view_path(s->view,e->id);
    if(e->id){g_autofree char*p=fsearch_catalog_view_path(s->view,e->parent);h->parent=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,p,NULL,DATABASE_ENTRY_TYPE_FOLDER);}
    h->entry=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,e->name,h->parent,e->kind==FSEARCH_CATALOG_FILE?DATABASE_ENTRY_TYPE_FILE:DATABASE_ENTRY_TYPE_FOLDER);
    const char*ext=db_entry_get_extension(h->entry);
    if(o->extension&&(e->kind!=FSEARCH_CATALOG_FILE||!ext||g_ascii_strcasecmp(ext,o->extension))){hit_free(h);return true;}
    fsearch_query_match_data_set_entry(s->match,h->entry);
    if(fsearch_query_match(s->query,s->match))g_ptr_array_add(s->hits,h);else hit_free(h);
    return true;
}
static void query(FsearchCatalog*c,Options*o) {
    g_autoptr(FsearchCatalogView)v=fsearch_catalog_acquire(c);g_autoptr(FsearchQuery)q=fsearch_query_new_literal(o->query,(o->path?QUERY_FLAG_SEARCH_IN_PATH:0)|(o->match_case?QUERY_FLAG_MATCH_CASE:0));
    FsearchQueryMatchData*m=fsearch_query_match_data_new(NULL,NULL);GPtrArray*hits=g_ptr_array_new_with_free_func(hit_free);
    Search search={v,o,q,m,hits};fsearch_catalog_view_visit(v,visit,&search);g_ptr_array_sort(hits,compare);
    GString*out=g_string_new(NULL);g_string_append_printf(out,"{\"sequence\":%llu,\"generation\":%llu,\"paths_b64\":[",(unsigned long long)fsearch_catalog_view_sequence(v),(unsigned long long)fsearch_catalog_view_generation(v));
    for(unsigned i=0;i<MIN(hits->len,(unsigned)o->limit);i++){Hit*h=g_ptr_array_index(hits,i);g_autofree char*b64=g_base64_encode((guchar*)h->path,strlen(h->path));g_string_append_printf(out,"%s\"%s\"",i?",":"",b64);}
    g_string_append(out,"],\"groups\":[");unsigned groups=0;
    for(unsigned i=0;i<hits->len;){unsigned j=i+1;while(j<hits->len&&!compare(&hits->pdata[i],&hits->pdata[j]))j++;g_string_append_printf(out,"%s%u",groups++?",":"",j-i);i=j;}
    g_string_append(out,"]}");puts(out->str);g_string_free(out,true);g_ptr_array_unref(hits);fsearch_query_match_data_free(m);
}
static char*decode(const char*s){gsize n;char*p=(char*)g_base64_decode(s,&n);p=g_realloc(p,n+1);p[n]=0;return p;}
static gpointer build(void*t){const char*e=NULL;return GINT_TO_POINTER(fsearch_catalog_compact_run(t,&e));}
int main(void) {
    umask(0077);char*line=NULL;size_t size=0;
    if(getline(&line,&size,stdin)<=0)return 2;unsigned count=atoi(line);if(count>1000||!count)return 2;
    FsearchCatalogEntry*rows=g_new0(FsearchCatalogEntry,count);
    for(unsigned i=0;i<count;i++){if(getline(&line,&size,stdin)<=0)return 2;line[strcspn(line,"\r\n")]=0;g_auto(GStrv)v=g_strsplit(line,"\t",-1);rows[i]=(FsearchCatalogEntry){atoi(v[0]),atoi(v[1]),atoi(v[2]),decode(v[3])};}
    FsearchCatalogLimits limits={16*1024*1024,256,256,16};const char*error=NULL;FsearchCatalog*c=fsearch_catalog_new(rows,count,&limits,&error);if(!c)return 3;
    for(unsigned i=0;i<count;i++)g_free((char*)rows[i].name);g_free(rows);puts("{\"ready\":true}");fflush(stdout);
    FsearchCatalogBuild*t=NULL;GThread*thread=NULL;
    while(getline(&line,&size,stdin)>0) {
        line[strcspn(line,"\r\n")]=0;g_auto(GStrv)v=g_strsplit(line,"\t",-1);bool ok=false;error=NULL;
        if(!strcmp(v[0],"U")){g_autofree char*name=decode(v[5]);ok=fsearch_catalog_change(c,g_ascii_strtoull(v[1],NULL,10),atoi(v[2]),atoi(v[3]),atoi(v[4]),name,&error);}
        else if(!strcmp(v[0],"C")){g_autofree char*name=decode(v[4]);uint32_t id=0;ok=fsearch_catalog_create(c,g_ascii_strtoull(v[1],NULL,10),atoi(v[2]),atoi(v[3]),name,&id,&error);printf("{\"accepted\":%s,\"id\":%u}\n",ok?"true":"false",id);fflush(stdout);continue;}
        else if(!strcmp(v[0],"B")){t=fsearch_catalog_compact_begin(c,&error);ok=t!=NULL;if(ok)thread=g_thread_new("parity-build",build,t);}
        else if(!strcmp(v[0],"P")){ok=thread&&GPOINTER_TO_INT(g_thread_join(thread));thread=NULL;if(ok)ok=fsearch_catalog_compact_validate(t,&error)&&fsearch_catalog_compact_publish(c,t,&error);if(t)fsearch_catalog_compact_free(c,t);t=NULL;}
        else if(!strcmp(v[0],"Q")){g_autofree char*text=decode(v[5]);Options o={.query=text,.path=atoi(v[1]),.match_case=atoi(v[2]),.kind=v[3],.extension=strcmp(v[4],"-")?v[4]:NULL,.limit=atoi(v[6])};query(c,&o);fflush(stdout);continue;}
        else return 2;
        printf("{\"accepted\":%s,\"error\":",ok?"true":"false");GString*code=g_string_new(NULL);if(error)fsearch_headless_append_json_string(code,error);else g_string_append(code,"null");printf("%s}\n",code->str);g_string_free(code,true);fflush(stdout);
    }
    if(thread)g_thread_join(thread);if(t)fsearch_catalog_compact_free(c,t);fsearch_catalog_free(c);free(line);return 0;
}
