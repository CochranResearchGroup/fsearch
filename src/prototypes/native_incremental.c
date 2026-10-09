/* Throwaway native matcher seam. Synthetic records only. GPL-2.0-or-later. */
#include "fsearch_headless.h"
#include "fsearch_database_file.h"
#include "fsearch_database_entry.h"
#include "fsearch_database_include.h"
#include "fsearch_query.h"
#include <sys/resource.h>
#include <sys/stat.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { char *name; unsigned parent; int kind; FsearchDatabaseEntry *entry; } Record;
typedef struct { char *path; int kind; } Oracle;
static GPtrArray *base,*oracle;
static GHashTable *delta;
static FsearchHeadlessSnapshot *snapshot;
static const unsigned cap=2048;
static bool deferred;
static Record *record_new(const char *name,unsigned parent,int kind) {
 Record *r=g_new0(Record,1);r->name=g_strdup(name);r->parent=parent;r->kind=kind;
 if(kind)r->entry=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,name,NULL,kind==2?DATABASE_ENTRY_TYPE_FOLDER:DATABASE_ENTRY_TYPE_FILE);
 return r;
}
static void record_free(void *p){Record*r=p;if(r->entry)db_entry_free(r->entry);g_free(r->name);g_free(r);}
static Record *get(unsigned id){Record*r=g_hash_table_lookup(delta,GUINT_TO_POINTER(id+1));return r?r:id<base->len?g_ptr_array_index(base,id):NULL;}
static bool live(unsigned id){for(unsigned depth=0;depth<64;depth++){Record*r=get(id);if(!r||!r->kind)return false;if(id==0)return true;id=r->parent;}return false;}
static char *fullpath(unsigned id){if(!live(id))return NULL;const char *parts[64];unsigned n=0;for(;;){Record*r=get(id);parts[n++]=r->name;if(!id)break;id=r->parent;}GString*s=g_string_new("");while(n){if(s->len)g_string_append_c(s,'/');g_string_append(s,parts[--n]);}return g_string_free(s,false);}
static void fixture(unsigned count){
 base=g_ptr_array_new_with_free_func(record_free);oracle=g_ptr_array_new();delta=g_hash_table_new_full(g_direct_hash,g_direct_equal,NULL,record_free);
 for(unsigned id=0;id<count+3;id++){
  char buffer[128];const char *name;unsigned parent=id<3?id? id-1:0:2;int kind=id<3?2:1;
  const char *special[]={"CAFÉ-ÉCOLE.pdf","Straße.txt","STRASSE.txt","İstanbul.pdf","cafe\xcc\x81.txt","literal*wild?.txt","raw-\xff.txt","emoji-😀.txt","100%_[x].csv","line\nbreak.txt"};
  if(!id)name="/__owned_native__";else if(id==1)name="alpha";else if(id==2)name="nested";else if(id<13)name=special[id-3];else{snprintf(buffer,sizeof(buffer),"file-%07u.txt",id);name=buffer;}
  g_ptr_array_add(base,record_new(name,parent,kind));Oracle*o=g_new0(Oracle,1);o->kind=kind;
  if(!id)o->path=g_strdup(name);else {Oracle*p=g_ptr_array_index(oracle,parent);o->path=g_strconcat(p->path,"/",name,NULL);}g_ptr_array_add(oracle,o);
 }
}
static bool update(unsigned id,unsigned parent,int kind,const char *name){
 if(deferred||!id)return false;
 if(!g_hash_table_contains(delta,GUINT_TO_POINTER(id+1))&&g_hash_table_size(delta)>=cap){deferred=true;return false;}
 Record*old=get(id);
 if(kind){if(!*name||strchr(name,'/')||!strcmp(name,".")||!strcmp(name,"..")||!live(parent)||get(parent)->kind!=2)return false;
  unsigned walk=parent;for(unsigned depth=0;depth<64;depth++){if(walk==id)return false;if(!walk)break;walk=get(walk)->parent;}
  if(old&&(!old->kind||!live(id)))return false; /* retired identity must not be reused */
 }else if(!old||!live(id))return false;
 /* Oracle mutates full paths independently; candidate updates only one identity. */
 while(oracle->len<=id)g_ptr_array_add(oracle,g_new0(Oracle,1));
 Oracle*o=g_ptr_array_index(oracle,id);char*previous=g_strdup(o->path);int oldkind=o->kind;
 char*dest=kind?g_strconcat(((Oracle*)g_ptr_array_index(oracle,parent))->path,"/",name,NULL):NULL;
 if(oldkind==2)for(unsigned j=0;j<oracle->len;j++){Oracle*c=g_ptr_array_index(oracle,j);if(c->path&&previous&&g_str_has_prefix(c->path,previous)&&(c->path[strlen(previous)]=='/'||!c->path[strlen(previous)])){char*next=kind?g_strconcat(dest,c->path+strlen(previous),NULL):NULL;g_free(c->path);c->path=next;if(!kind)c->kind=0;}}
 else{g_free(o->path);o->path=g_strdup(dest);o->kind=kind;}
 g_free(previous);g_free(dest);g_hash_table_replace(delta,GUINT_TO_POINTER(id+1),record_new(name,parent,kind));return true;
}
static int by_name(void*a,void*b,void*x){return db_entry_compare_entries_by_name(a,b);}
static int by_path(void*a,void*b,void*x){return db_entry_compare_entries_by_path(a,b);}
static FsearchDatabaseEntry *oracle_entry(const char *path,GHashTable *entries,GHashTable *kinds,DynamicArray *folders,DynamicArray *files){
 FsearchDatabaseEntry*e=g_hash_table_lookup(entries,path);if(e)return e;int kind=GPOINTER_TO_INT(g_hash_table_lookup(kinds,path));g_assert(kind);
 g_autofree char*parentpath=g_path_get_dirname(path),*name=g_path_get_basename(path);FsearchDatabaseEntry*parent=NULL;
 if(strcmp(path,"/__owned_native__"))parent=oracle_entry(parentpath,entries,kinds,folders,files);
 e=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,parent?name:path,parent,kind==2?DATABASE_ENTRY_TYPE_FOLDER:DATABASE_ENTRY_TYPE_FILE);
 g_hash_table_insert(entries,g_strdup(path),e);darray_add_item(kind==2?folders:files,e);return e;
}
static bool save_oracle(const char *path){
 g_autoptr(GHashTable)entries=g_hash_table_new_full(g_str_hash,g_str_equal,g_free,NULL),kinds=g_hash_table_new(g_str_hash,g_str_equal);
 g_autoptr(DynamicArray)folders=darray_new(16),files=darray_new(128);
 for(unsigned i=0;i<oracle->len;i++){Oracle*o=g_ptr_array_index(oracle,i);if(o->kind&&o->path)g_hash_table_insert(kinds,o->path,GINT_TO_POINTER(o->kind));}
 for(unsigned i=0;i<oracle->len;i++){Oracle*o=g_ptr_array_index(oracle,i);if(o->kind&&o->path)oracle_entry(o->path,entries,kinds,folders,files);}
 g_autoptr(FsearchDatabaseIncludeManager)includes=fsearch_database_include_manager_new();g_autoptr(FsearchDatabaseExcludeManager)excludes=fsearch_database_exclude_manager_new();
 g_autoptr(FsearchDatabaseInclude)include=fsearch_database_include_new("/__owned_native__",TRUE,TRUE,FALSE,FALSE,0);fsearch_database_include_manager_add(includes,include);
 g_autoptr(DynamicArray)fp=darray_copy(files),dp=darray_copy(folders);darray_sort(fp,by_path,NULL,NULL);darray_sort(dp,by_path,NULL,NULL);darray_sort(files,by_name,NULL,NULL);darray_sort(folders,by_name,NULL,NULL);
 g_autoptr(GPtrArray)indices=g_ptr_array_new_with_free_func((GDestroyNotify)fsearch_database_index_unref);g_ptr_array_add(indices,fsearch_database_index_new_with_content(include,excludes,dp,fp,DATABASE_INDEX_PROPERTY_FLAG_NAME|DATABASE_INDEX_PROPERTY_FLAG_PATH));
 DynamicArray*fa[NUM_DATABASE_INDEX_PROPERTIES]={0},*da[NUM_DATABASE_INDEX_PROPERTIES]={0};fa[DATABASE_INDEX_PROPERTY_NAME]=files;da[DATABASE_INDEX_PROPERTY_NAME]=folders;fa[DATABASE_INDEX_PROPERTY_PATH]=fp;da[DATABASE_INDEX_PROPERTY_PATH]=dp;
 g_autoptr(FsearchDatabaseIndexStore)store=fsearch_database_index_store_new_snapshot(indices,fa,da,includes,excludes,DATABASE_INDEX_PROPERTY_FLAG_NAME|DATABASE_INDEX_PROPERTY_FLAG_PATH);
 g_autoptr(GMutexLocker)lock=fsearch_database_index_store_get_locker(store);bool ok=fsearch_database_file_save(store,path);
 if(snapshot)fsearch_headless_close(snapshot);const char*error=NULL;snapshot=ok?fsearch_headless_open(path,&error):NULL;
 return snapshot!=NULL;
}
static void candidate(Options*o){
 gint64 start=g_get_monotonic_time();g_autoptr(FsearchQuery)q=fsearch_query_new_literal(o->query,(o->path?QUERY_FLAG_SEARCH_IN_PATH:0)|(o->match_case?QUERY_FLAG_MATCH_CASE:0));
 FsearchQueryMatchData*m=fsearch_query_match_data_new(NULL,NULL);GPtrArray*hits=g_ptr_array_new_with_free_func(g_free);unsigned total=MAX(base->len,oracle->len);
 for(unsigned id=0;id<total;id++){Record*r=get(id);if(!r||!r->kind||!live(id))continue;if(!strcmp(o->kind,"files")&&r->kind!=1)continue;if(!strcmp(o->kind,"folders")&&r->kind!=2)continue;
  if(o->extension&&(r->kind!=1||!db_entry_get_extension(r->entry)||g_ascii_strcasecmp(db_entry_get_extension(r->entry),o->extension)))continue;
  FsearchDatabaseEntry*leaf=r->entry,*parent=NULL;
  if(o->path&&id){g_autofree char*pp=fullpath(r->parent);parent=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,pp,NULL,DATABASE_ENTRY_TYPE_FOLDER);leaf=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,r->name,parent,r->kind==2?DATABASE_ENTRY_TYPE_FOLDER:DATABASE_ENTRY_TYPE_FILE);}
  fsearch_query_match_data_set_entry(m,leaf);if(fsearch_query_match(q,m))g_ptr_array_add(hits,fullpath(id));
  if(parent){db_entry_free(leaf);db_entry_free(parent);}
 }
 fsearch_query_match_data_free(m);printf("{\"coverage\":\"%s\",\"elapsed_ms\":%.3f,\"overlay\":%u,\"paths_b64\":[",deferred?"deferred":"current",(g_get_monotonic_time()-start)/1000.,g_hash_table_size(delta));
 for(unsigned i=0;i<hits->len;i++){char*p=g_ptr_array_index(hits,i);g_autofree char*encoded=g_base64_encode((guchar*)p,strlen(p));printf("%s\"%s\"",i?",":"",encoded);}puts("]}");g_ptr_array_unref(hits);
}
int main(int argc,char**argv){if(argc!=2)return 2;struct rlimit bound={1024UL*1024*1024,1024UL*1024*1024},core={0,0};setrlimit(RLIMIT_AS,&bound);setrlimit(RLIMIT_CORE,&core);umask(0077);fixture(atoi(argv[1]));puts("{\"ready\":true}");fflush(stdout);
 char*line=NULL;size_t size=0;while(getline(&line,&size,stdin)>0){line[strcspn(line,"\r\n")]=0;g_auto(GStrv)v=g_strsplit(line,"\t",-1);
  if(!strcmp(v[0],"U")){gsize n;g_autofree char*name=(char*)g_base64_decode(v[4],&n);name=g_realloc(name,n+1);name[n]=0;bool accepted=update(atoi(v[1]),atoi(v[2]),atoi(v[3]),name);printf("{\"accepted\":%s,\"overlay\":%u}\n",accepted?"true":"false",g_hash_table_size(delta));}
  else if(!strcmp(v[0],"S"))printf("{\"saved\":%s}\n",save_oracle(v[1])?"true":"false");
  else if(!strcmp(v[0],"Q")){gsize n;g_autofree char*text=(char*)g_base64_decode(v[5],&n);text=g_realloc(text,n+1);text[n]=0;Options o={.query=text,.path=atoi(v[1]),.match_case=atoi(v[2]),.kind=v[3],.extension=strcmp(v[4],"-")?v[4]:NULL,.limit=1000,.max_candidates=500000,.max_bytes=1048576};candidate(&o);if(snapshot){const char*error=NULL;g_autoptr(GString)reply=fsearch_headless_search(&o,snapshot,&error);if(!reply)return 4;fputs(reply->str,stdout);}}
  else if(!strcmp(v[0],"R")){struct rusage r;getrusage(RUSAGE_SELF,&r);printf("{\"peak_rss_kib\":%ld}\n",r.ru_maxrss);}
  fflush(stdout);
 }return 0;
}
