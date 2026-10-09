/* Throwaway native matcher seam. Synthetic records only. GPL-2.0-or-later. */
#include "fsearch_headless.h"
#include "fsearch_database_file.h"
#include "fsearch_database_entry.h"
#include "fsearch_database_include.h"
#include "fsearch_query.h"
#include "fsearch_headless_signature.h"
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
/* Immutable sorted identity ranks; only the bounded delta is re-sorted per query. */
static GArray *ranks[2];
static uint64_t *planes[2];
static size_t strides[2];
static int rank_compare(const void *a,const void *b,void *unused) {
 unsigned ai=*(const unsigned*)a,bi=*(const unsigned*)b;
 Record *ar=get(ai),*br=get(bi);
 return db_entry_compare_entries_by_name(&ar->entry,&br->entry);
}
static void build_candidates(void) {
 FsearchUtfBuilder builder={0};
 for(unsigned type=0;type<2;type++) {
  ranks[type]=g_array_new(false,false,sizeof(unsigned));
  for(unsigned id=0;id<base->len;id++) if(((Record*)g_ptr_array_index(base,id))->kind==(type?2:1))g_array_append_val(ranks[type],id);
  g_array_sort_with_data(ranks[type],rank_compare,NULL);
  size_t stride=strides[type]=(ranks[type]->len+63)/64;
  planes[type]=g_malloc0(stride*192*sizeof(uint64_t));
  for(unsigned rank=0;rank<ranks[type]->len;rank++) {
   unsigned id=g_array_index(ranks[type],unsigned,rank);Record*r=get(id);uint64_t sig[3];signature_text(r->name,sig);
   if(!signature_ascii(r->name)) {
    g_autofree char*normalized=normalized_utf8(&builder,r->name);
    if(normalized){uint64_t folded[3];signature_text(normalized,folded);for(unsigned w=0;w<3;w++)sig[w]|=folded[w];}
    else for(unsigned w=0;w<3;w++)sig[w]=UINT64_MAX;
   }
   for(unsigned w=0;w<3;w++)for(uint64_t bits=sig[w];bits;bits&=bits-1) {
    unsigned bit=__builtin_ctzll(bits);planes[type][(w*64+bit)*stride+rank/64]|=UINT64_C(1)<<(rank%64);
   }
  }
 }
 fsearch_utf_builder_clear(&builder);
}
static uint64_t possible_block(unsigned type,unsigned block,const uint64_t required[3]) {
 uint64_t possible=UINT64_MAX;
 for(unsigned w=0;w<3&&possible;w++)for(uint64_t bits=required[w];bits&&possible;bits&=bits-1) {
  unsigned bit=__builtin_ctzll(bits);possible&=planes[type][(w*64+bit)*strides[type]+block];
 }
 return possible;
}
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
static bool exact(unsigned id,Options*o,FsearchQuery*q,FsearchQueryMatchData*m) {
 Record*r=get(id);if(!r||!r->kind||!live(id))return false;
 if(o->extension&&(r->kind!=1||!db_entry_get_extension(r->entry)||g_ascii_strcasecmp(db_entry_get_extension(r->entry),o->extension)))return false;
 FsearchDatabaseEntry*leaf=r->entry,*parent=NULL;
 if(o->path&&id){g_autofree char*pp=fullpath(r->parent);parent=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,pp,NULL,DATABASE_ENTRY_TYPE_FOLDER);leaf=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,r->name,parent,r->kind==2?DATABASE_ENTRY_TYPE_FOLDER:DATABASE_ENTRY_TYPE_FILE);}
 fsearch_query_match_data_set_entry(m,leaf);bool match=fsearch_query_match(q,m);
 if(parent){db_entry_free(leaf);db_entry_free(parent);}return match;
}
static void candidate(Options*o){
 gint64 start=g_get_monotonic_time();g_autoptr(FsearchQuery)q=fsearch_query_new_literal(o->query,(o->path?QUERY_FLAG_SEARCH_IN_PATH:0)|(o->match_case?QUERY_FLAG_MATCH_CASE:0));
 FsearchQueryMatchData*m=fsearch_query_match_data_new(NULL,NULL);
 GArray*hits=g_array_new(false,false,sizeof(unsigned));unsigned examined=0,blocks=0;
 uint64_t required[3]={0};bool filter=query_signature(o,required);
 for(unsigned type=0;type<2;type++) {
  if((type==0&&!strcmp(o->kind,"folders"))||(type==1&&!strcmp(o->kind,"files")))continue;
  GArray *basehits=g_array_new(false,false,sizeof(unsigned)),*deltahits=g_array_new(false,false,sizeof(unsigned));
  for(unsigned block=0;block<strides[type];block++) {
   blocks++;uint64_t possible=filter?possible_block(type,block,required):UINT64_MAX;
   while(possible){unsigned rank=block*64+__builtin_ctzll(possible);possible&=possible-1;if(rank>=ranks[type]->len)continue;
    unsigned id=g_array_index(ranks[type],unsigned,rank);if(g_hash_table_contains(delta,GUINT_TO_POINTER(id+1)))continue;
    examined++;if(exact(id,o,q,m))g_array_append_val(basehits,id);
   }
  }
  GHashTableIter it;gpointer key,value;g_hash_table_iter_init(&it,delta);
  while(g_hash_table_iter_next(&it,&key,&value)){Record*r=value;if(r->kind!=(type?2:1))continue;unsigned id=GPOINTER_TO_UINT(key)-1;examined++;if(exact(id,o,q,m))g_array_append_val(deltahits,id);}
  g_array_sort_with_data(deltahits,rank_compare,NULL);
  unsigned b=0,d=0;
  while(b<basehits->len||d<deltahits->len){unsigned id;
   if(d==deltahits->len||(b<basehits->len&&rank_compare(&g_array_index(basehits,unsigned,b),&g_array_index(deltahits,unsigned,d),NULL)<=0))id=g_array_index(basehits,unsigned,b++);
   else id=g_array_index(deltahits,unsigned,d++);
   g_array_append_val(hits,id);
  }
  g_array_unref(basehits);g_array_unref(deltahits);
 }
 fsearch_query_match_data_free(m);printf("{\"coverage\":\"%s\",\"elapsed_ms\":%.3f,\"examined\":%u,\"candidate_blocks\":%u,\"overlay\":%u,\"paths_b64\":[",deferred?"deferred":"current",(g_get_monotonic_time()-start)/1000.,examined,blocks,g_hash_table_size(delta));
 unsigned returned=MIN(hits->len,(unsigned)o->limit);
 for(unsigned i=0;i<returned;i++){g_autofree char*p=fullpath(g_array_index(hits,unsigned,i));g_autofree char*encoded=g_base64_encode((guchar*)p,strlen(p));printf("%s\"%s\"",i?",":"",encoded);}
 printf("],\"total_matches\":%u,\"order_group_sizes\":[",hits->len);
 unsigned group=0;for(unsigned i=0;i<hits->len;) {unsigned j=i+1,ai=g_array_index(hits,unsigned,i);Record*a=get(ai);
  while(j<hits->len){unsigned bi=g_array_index(hits,unsigned,j);Record*b=get(bi);if(a->kind!=b->kind||rank_compare(&ai,&bi,NULL))break;j++;}
  printf("%s%u",group++?",":"",j-i);i=j;
 }
 puts("]}");g_array_unref(hits);
}
int main(int argc,char**argv){if(argc!=2)return 2;struct rlimit bound={1024UL*1024*1024,1024UL*1024*1024},core={0,0};setrlimit(RLIMIT_AS,&bound);setrlimit(RLIMIT_CORE,&core);umask(0077);fixture(atoi(argv[1]));build_candidates();puts("{\"ready\":true}");fflush(stdout);
 char*line=NULL;size_t size=0;while(getline(&line,&size,stdin)>0){line[strcspn(line,"\r\n")]=0;g_auto(GStrv)v=g_strsplit(line,"\t",-1);
  if(!strcmp(v[0],"U")){gsize n;g_autofree char*name=(char*)g_base64_decode(v[4],&n);name=g_realloc(name,n+1);name[n]=0;bool accepted=update(atoi(v[1]),atoi(v[2]),atoi(v[3]),name);printf("{\"accepted\":%s,\"overlay\":%u}\n",accepted?"true":"false",g_hash_table_size(delta));}
  else if(!strcmp(v[0],"S"))printf("{\"saved\":%s}\n",save_oracle(v[1])?"true":"false");
  else if(!strcmp(v[0],"Q")){gsize n;g_autofree char*text=(char*)g_base64_decode(v[5],&n);text=g_realloc(text,n+1);text[n]=0;Options o={.query=text,.path=atoi(v[1]),.match_case=atoi(v[2]),.kind=v[3],.extension=strcmp(v[4],"-")?v[4]:NULL,.limit=v[6]?atoi(v[6]):1000,.max_candidates=500000,.max_bytes=1048576};candidate(&o);if(snapshot){const char*error=NULL;g_autoptr(GString)reply=fsearch_headless_search(&o,snapshot,&error);if(!reply)return 4;fputs(reply->str,stdout);}}
  else if(!strcmp(v[0],"R")){struct rusage r;getrusage(RUSAGE_SELF,&r);printf("{\"peak_rss_kib\":%ld}\n",r.ru_maxrss);}
  fflush(stdout);
 }return 0;
}
