/* Isolated native/SQLite candidate experiment. Not installed. GPL-2.0-or-later.
 * The harness injects an unchanged headless search body with candidate iteration.
 * Trusted generated snapshots/input only; not a new public API. */
#include "fsearch_headless.c"
#include "fsearch_database_sort.h"
#include <sqlite3.h>
#include <stdint.h>
#include <sys/time.h>
#include <time.h>

#define POSTING_BUDGET 500000u
static GHashTable *postings[2];
static GArray *unsupported[2];
static sqlite3 *sql;
static unsigned engine;
static uint64_t posting_work;
static bool candidate_limited;
static gint64 query_deadline;
static size_t posting_bytes;
static unsigned posting_keys;
static unsigned entry_counts[2];
static unsigned ascii_lower(unsigned c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }
static bool ascii_text(const char *s) {
    for (const unsigned char *p=(const unsigned char *)s; *p; ++p) if (*p >= 128) return false;
    return true;
}
static uint32_t gram(const unsigned char *p) { return (ascii_lower(p[0])<<16)|(ascii_lower(p[1])<<8)|ascii_lower(p[2]); }
static bool budget(void) {
    if (++posting_work > POSTING_BUDGET || ((posting_work & 255)==0 && g_get_monotonic_time()>query_deadline)) {
        candidate_limited=true; return false;
    }
    return true;
}
static bool contains(const GArray *a, uint32_t value) {
    unsigned lo=0,hi=a->len;
    while(lo<hi) {
        if (!budget()) return false;
        unsigned mid=lo+(hi-lo)/2; uint32_t x=g_array_index(a,uint32_t,mid);
        if(x<value)lo=mid+1;else hi=mid;
    }
    return lo<a->len && g_array_index(a,uint32_t,lo)==value;
}
static void sql_ok(int result) {
    if(result!=SQLITE_OK && result!=SQLITE_DONE && result!=SQLITE_ROW) {
        fprintf(stderr,"SQLite failure %d: %s\n",result,sqlite3_errmsg(sql)); exit(20);
    }
}
static void sql_exec(const char *s) { sql_ok(sqlite3_exec(sql,s,NULL,NULL,NULL)); }
static void build_accelerator(FsearchHeadlessSnapshot *snapshot) {
    if(!engine)return;
    if (engine==2) { sql_ok(sqlite3_open(":memory:",&sql)); sql_exec("CREATE VIRTUAL TABLE tri USING fts5(name, tokenize='trigram'); BEGIN"); }
    sqlite3_stmt *insert=NULL;
    if(engine==2)sql_ok(sqlite3_prepare_v2(sql,"INSERT INTO tri(rowid,name) VALUES(?,?)",-1,&insert,NULL));
    for(unsigned type=0;type<2;++type) {
        postings[type]=g_hash_table_new_full(g_direct_hash,g_direct_equal,NULL,(GDestroyNotify)g_array_unref);
        unsupported[type]=g_array_new(FALSE,FALSE,sizeof(uint32_t));
        g_autoptr(FsearchDatabaseChunkedArray) entries=type ? fsearch_database_index_store_get_folders(snapshot->store,DATABASE_INDEX_PROPERTY_NAME) : fsearch_database_index_store_get_files(snapshot->store,DATABASE_INDEX_PROPERTY_NAME);
        unsigned count=entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;
        entry_counts[type]=count;
        for(uint32_t rank=0;rank<count;++rank) {
            const char *name=db_entry_get_name_raw(fsearch_database_chunked_array_get_entry(entries,rank));
            if(!ascii_text(name)) {g_array_append_val(unsupported[type],rank);continue;}
            if(engine==1) {
                uint32_t block=rank/64;
                size_t len=strlen(name);
                for(size_t j=0;j+2<len;++j) {
                    uint32_t code=gram((const unsigned char *)name+j);
                    GArray *list=g_hash_table_lookup(postings[type],GUINT_TO_POINTER(code+1));
                    if(!list){list=g_array_new(FALSE,FALSE,sizeof(uint32_t));g_hash_table_insert(postings[type],GUINT_TO_POINTER(code+1),list);++posting_keys;}
                    if(!list->len || g_array_index(list,uint32_t,list->len-1)!=block){g_array_append_val(list,block);posting_bytes+=4;}
                }
            } else if(engine==2) {
                sqlite3_bind_int64(insert,1,((sqlite3_int64)type<<32)+rank+1);
                sql_ok(sqlite3_bind_text(insert,2,name,-1,SQLITE_TRANSIENT)); sql_ok(sqlite3_step(insert));sql_ok(sqlite3_reset(insert));
            }
        }
    }
    if(engine==2){sqlite3_finalize(insert);sql_exec("COMMIT");}
}
static gint uint_compare(gconstpointer a,gconstpointer b) {
    uint32_t x=*(const uint32_t *)a,y=*(const uint32_t *)b;return x>y ? 1 : x<y ? -1 : 0;
}
static int sql_progress(void *unused) { (void)unused; return !budget(); }
/* NULL means bounded sequential fallback. Non-NULL is a sound candidate superset.
 * ASCII-only indexing keeps unsupported names in an unconditional candidate bucket. */
static GArray *candidate_ranks(const Options *options,unsigned type) {
    if(!engine || options->path || !ascii_text(options->query) || strlen(options->query)<3)return NULL;
    GArray *result=g_array_new(FALSE,FALSE,sizeof(uint32_t));
    if(engine==1) {
        GArray *lists[4096];unsigned n=0;GArray *pivot=NULL;
        for(const unsigned char *p=(const unsigned char *)options->query;p[2];++p) {
            if(!budget())break;
            GArray *list=g_hash_table_lookup(postings[type],GUINT_TO_POINTER(gram(p)+1));
            if(!list){n=0;pivot=NULL;break;}
            lists[n++]=list;if(!pivot || list->len<pivot->len)pivot=list;
        }
        if(pivot && pivot->len>4096 && !candidate_limited){g_array_unref(result);return NULL;}
        if(pivot && !candidate_limited)for(unsigned j=0;j<pivot->len;++j) {
            if(!budget())break;
            uint32_t rank=g_array_index(pivot,uint32_t,j);bool present=true;
            for(unsigned k=0;k<n;++k)if(lists[k]!=pivot && !contains(lists[k],rank)){present=false;break;}
            if(present)for(uint32_t expanded=rank*64;expanded<entry_counts[type] && expanded<(rank+1)*64;++expanded){if(!budget())break;g_array_append_val(result,expanded);}
            if(candidate_limited)break;
        }
    } else {
        GString *phrase=g_string_new("\"");
        for(const char *p=options->query;*p;++p){g_string_append_c(phrase,*p);if(*p=='\"')g_string_append_c(phrase,'\"');}
        g_string_append_c(phrase,'\"');sqlite3_stmt *select=NULL;
        sql_ok(sqlite3_prepare_v2(sql,"SELECT rowid FROM tri WHERE tri MATCH ? AND rowid BETWEEN ? AND ? ORDER BY rowid",-1,&select,NULL));
        sqlite3_bind_text(select,1,phrase->str,-1,SQLITE_TRANSIENT);
        sqlite3_bind_int64(select,2,((sqlite3_int64)type<<32)+1);
        sqlite3_bind_int64(select,3,((sqlite3_int64)type<<32)+UINT32_MAX);
        sqlite3_progress_handler(sql,1000,sql_progress,NULL);
        int rc;bool broad=false;
        while((rc=sqlite3_step(select))==SQLITE_ROW) {
            if(!budget())break;
            uint32_t rank=(uint32_t)(sqlite3_column_int64(select,0)-1);g_array_append_val(result,rank);
            if(result->len>4096){broad=true;break;}
        }
        if(rc!=SQLITE_INTERRUPT)sql_ok(rc);
        sqlite3_progress_handler(sql,0,NULL,NULL);sqlite3_finalize(select);g_string_free(phrase,TRUE);
        if(broad && !candidate_limited){g_array_unref(result);return NULL;}
    }
    for(unsigned j=0;j<unsupported[type]->len;++j) {
        if(!budget())break;
        uint32_t rank=g_array_index(unsupported[type],uint32_t,j);g_array_append_val(result,rank);
    }
    g_array_sort(result,uint_compare);
    unsigned unique=0;for(unsigned j=0;j<result->len;++j){uint32_t rank=g_array_index(result,uint32_t,j);if(!unique || g_array_index(result,uint32_t,unique-1)!=rank)g_array_index(result,uint32_t,unique++)=rank;}
    g_array_set_size(result,unique);return result;
}

GString *prototype_filtered_search(const Options *options, FsearchHeadlessSnapshot *snapshot, const char **error) {
    FsearchDatabaseIndexStore *store = snapshot->store;
    struct stat st = snapshot->stat;
    g_autoptr(FsearchQuery) query = fsearch_query_new_literal(
        options->query, (options->path ? QUERY_FLAG_SEARCH_IN_PATH : 0)
                            | (options->match_case ? QUERY_FLAG_MATCH_CASE : 0));
    FsearchQueryMatchData *match_data = fsearch_query_match_data_new(NULL, NULL);
    g_autoptr(GString) results = g_string_new(NULL);
    unsigned returned = 0;
    unsigned examined = 0;
    const char *stop = "ok";
    for (unsigned type = 0; type < 2 && !strcmp(stop, "ok"); ++type) {
        if ((type == 0 && !strcmp(options->kind, "folders"))
            || (type == 1 && !strcmp(options->kind, "files"))) {
            continue;
        }
        g_autoptr(FsearchDatabaseChunkedArray) entries = type == 0
            ? fsearch_database_index_store_get_files(store, DATABASE_INDEX_PROPERTY_NAME)
            : fsearch_database_index_store_get_folders(store, DATABASE_INDEX_PROPERTY_NAME);
        g_autoptr(GArray) candidates = candidate_ranks(options,type);
        if(candidate_limited){*error="candidate_work_limit";return NULL;}
        const unsigned count = candidates ? candidates->len : entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;
        for (unsigned i = 0; i < count; ++i) {
            if (examined >= (unsigned)options->max_candidates) {
                stop = "work_limit";
                break;
            }
            FsearchDatabaseEntry *entry = fsearch_database_chunked_array_get_entry(entries, candidates ? g_array_index(candidates,uint32_t,i) : i);
            examined++;
            if (options->extension) {
                const char *ext = db_entry_get_extension(entry);
                if (type == 1 || !ext || g_ascii_strcasecmp(ext, options->extension)) {
                    continue;
                }
            }
            fsearch_query_match_data_set_entry(match_data, entry);
            if (!fsearch_query_match(query, match_data)) {
                continue;
            }
            if (returned >= (unsigned)options->limit) {
                stop = "result_limit";
                break;
            }
            g_autoptr(GString) path = db_entry_get_path_full(entry);
            g_autoptr(GString) row = g_string_new(NULL);
            append_path(row, path->str);
            // Reserve metadata space; the final response is checked again.
            if (results->len + row->len + 1 > (unsigned)options->max_bytes / 2) {
                stop = "byte_limit";
                break;
            }
            if (returned) {
                g_string_append_c(results, ',');
            }
            g_string_append_len(results, row->str, row->len);
            returned++;
        }
    }
    fsearch_query_match_data_free(match_data);
    g_autoptr(GString) out = g_string_new(NULL);
    g_string_append_printf(out, "{\"schema_version\":1,\"status\":\"%s\",\"complete\":%s,"
                                 "\"truncated\":%s,\"visibility\":\"cached\",\"examined\":%u,"
                                 "\"snapshot\":{\"identity\":\"%s\",\"mtime_unix\":%lld,\"age_seconds\":%lld,\"roots\":[",
                           stop, !strcmp(stop, "ok") ? "true" : "false",
                           !strcmp(stop, "ok") ? "false" : "true", examined,
                           snapshot->identity, (long long)st.st_mtime,
                           (long long)MAX(0, g_get_real_time() / G_USEC_PER_SEC - st.st_mtime));
    g_autoptr(FsearchDatabaseIncludeManager) manager = fsearch_database_index_store_get_include_manager(store);
    g_autoptr(GPtrArray) roots = fsearch_database_include_manager_get_includes(manager);
    for (unsigned i = 0; i < roots->len; ++i) {
        if (i) {
            g_string_append_c(out, ',');
        }
        FsearchDatabaseInclude *root = g_ptr_array_index(roots, i);
        append_path(out, fsearch_database_include_get_path(root));
        g_string_truncate(out, out->len - 1);
        const int64_t scan_time = fsearch_database_include_get_last_scan_time(root);
        g_string_append_printf(out, ",\"last_scan_unix\":%lld,\"age_seconds\":",
                               (long long)scan_time);
        if (scan_time > 0) {
            g_string_append_printf(out, "%lld", (long long)MAX(0, g_get_real_time() / G_USEC_PER_SEC - scan_time));
        }
        else {
            g_string_append(out, "null");
        }
        g_string_append_printf(out, ",\"last_error_code\":%u}",
                               fsearch_database_include_get_last_error_code(root));
        if (out->len > (unsigned)options->max_bytes / 2) {
            *error = "coverage_size_limit";
            return NULL;
        }
    }
    g_string_append(out, "]},\"results\":[");
    g_string_append_len(out, results->str, results->len);
    g_string_append(out, "]}\n");
    if (out->len > (unsigned)options->max_bytes) {
        *error = "response_size_limit";
            return NULL;
    }
    return g_steal_pointer(&out);
}



static int compare_name(void *a,void *b,void *unused) {
    (void)unused;return db_entry_compare_entries_by_name(a,b);
}
static int compare_path(void *a,void *b,void *unused) {
    (void)unused;return db_entry_compare_entries_by_path(a,b);
}
static bool make_snapshot(const char *path,unsigned count) {
    g_autoptr(FsearchDatabaseIncludeManager) includes=fsearch_database_include_manager_new();
    g_autoptr(FsearchDatabaseExcludeManager) excludes=fsearch_database_exclude_manager_new();
    g_autoptr(FsearchDatabaseInclude) include=fsearch_database_include_new("/__fsearch_trigram_virtual_owned__",TRUE,TRUE,FALSE,FALSE,0);
    fsearch_database_include_manager_add(includes,include);
    g_autoptr(DynamicArray) folders=darray_new(128),files=darray_new(count);
    FsearchDatabaseEntry *root=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,"/__fsearch_trigram_virtual_owned__",NULL,DATABASE_ENTRY_TYPE_FOLDER);darray_add_item(folders,root);
    FsearchDatabaseEntry *parents[64];
    for(unsigned j=0;j<64;++j){char name[100];snprintf(name,sizeof(name),"department-%02u-invoice-path",j);parents[j]=db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,name,root,DATABASE_ENTRY_TYPE_FOLDER);darray_add_item(folders,parents[j]);}
    const char *special[]={"invoice-unique-zqx.pdf","literal*wild?.txt","100%_quote\"[x].pdf","CAFÉ-ÉCOLE.pdf","cafe\xCC\x81-note.txt","Straße.txt","STRASSE.txt","raw-\xff-bytes.txt","abcxxbcd.txt","aab.txt","abb.txt","abca.txt","İstanbul.pdf","emoji-😀.pdf","noextension","trailing.","line\nbreak.txt","ababa.txt","slashless-invoice.txt","a\"b.csv"};
    unsigned specials=sizeof(special)/sizeof(special[0]);
    const char *categories[]={"report","notes","invoice","archive","photo","code","receipt","build"};
    for(unsigned i=0;i<count;++i) {
        char name[512];
        if(i<specials)snprintf(name,sizeof(name),"%s",special[i]);
        else if(i==count-1)snprintf(name,sizeof(name),"zz-last-rare-qvt.pdf");
        else if(i%991==0)snprintf(name,sizeof(name),"long-%0180u-shared-report-%07u.txt",i,i);
        else snprintf(name,sizeof(name),"%s-%07u-common.%s",categories[i%8],i,i%3==0 ? "pdf" : i%3==1 ? "txt" : "csv");
        darray_add_item(files,db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME,name,parents[i%64],DATABASE_ENTRY_TYPE_FILE));
    }
    g_autoptr(GPtrArray) indices=g_ptr_array_new_with_free_func((GDestroyNotify)fsearch_database_index_unref);
    g_autoptr(DynamicArray) files_path=darray_copy(files),folders_path=darray_copy(folders);
    darray_sort(files_path,compare_path,NULL,NULL);darray_sort(folders_path,compare_path,NULL,NULL);
    FsearchDatabaseIndex *index=fsearch_database_index_new_with_content(include,excludes,folders_path,files_path,DATABASE_INDEX_PROPERTY_FLAG_NAME|DATABASE_INDEX_PROPERTY_FLAG_PATH);g_ptr_array_add(indices,index);
    darray_sort(files,compare_name,NULL,NULL);darray_sort(folders,compare_name,NULL,NULL);
    DynamicArray *fa[NUM_DATABASE_INDEX_PROPERTIES]={0},*da[NUM_DATABASE_INDEX_PROPERTIES]={0};fa[DATABASE_INDEX_PROPERTY_NAME]=files;da[DATABASE_INDEX_PROPERTY_NAME]=folders;fa[DATABASE_INDEX_PROPERTY_PATH]=files_path;da[DATABASE_INDEX_PROPERTY_PATH]=folders_path;
    g_autoptr(FsearchDatabaseIndexStore) store=fsearch_database_index_store_new_snapshot(indices,fa,da,includes,excludes,DATABASE_INDEX_PROPERTY_FLAG_NAME|DATABASE_INDEX_PROPERTY_FLAG_PATH);
    return fsearch_database_file_save(store,path);
}
static void resources(long *rss,unsigned long *vm) {
    struct rusage usage;getrusage(RUSAGE_SELF,&usage);*rss=usage.ru_maxrss;
    FILE *f=fopen("/proc/self/status","r");char line[200];*vm=0;
    if(f){while(fgets(line,sizeof(line),f))if(sscanf(line,"VmPeak: %lu",vm)==1)break;fclose(f);}
}
static void discard_log(const gchar *domain,GLogLevelFlags level,const gchar *message,gpointer data) {
    (void)domain;(void)data;
    if(level & (G_LOG_LEVEL_ERROR|G_LOG_LEVEL_CRITICAL|G_LOG_LEVEL_WARNING))fprintf(stderr,"%s\n",message);
}
int main(int argc,char **argv) {
    g_log_set_default_handler(discard_log,NULL);
    if(argc!=4)return 2;
    struct rlimit limit={256u*1024*1024,256u*1024*1024};if(setrlimit(RLIMIT_AS,&limit))return 3;
    struct rlimit core={0,0};setrlimit(RLIMIT_CORE,&core);
    if(!strcmp(argv[1],"build"))return make_snapshot(argv[2],strtoul(argv[3],NULL,10)) ? 0 : 4;
    engine=!strcmp(argv[1],"native") ? 1 : !strcmp(argv[1],"sqlite") ? 2 : 0;
    gint64 started=g_get_monotonic_time();const char *error=NULL;
    FsearchHeadlessSnapshot *snapshot=fsearch_headless_open(argv[2],&error);
    if(!snapshot){fprintf(stdout,"{\"error\":\"%s\"}\n",error);return 5;}
    gint64 loaded=g_get_monotonic_time();build_accelerator(snapshot);gint64 built=g_get_monotonic_time();
    long rss;unsigned long vm;resources(&rss,&vm);
    int pages=0,page_size=0;
    if(sql){sqlite3_stmt *s;sql_ok(sqlite3_prepare_v2(sql,"PRAGMA page_count",-1,&s,NULL));sql_ok(sqlite3_step(s));pages=sqlite3_column_int(s,0);sqlite3_finalize(s);sql_ok(sqlite3_prepare_v2(sql,"PRAGMA page_size",-1,&s,NULL));sql_ok(sqlite3_step(s));page_size=sqlite3_column_int(s,0);sqlite3_finalize(s);}
    printf("{\"ready\":true,\"load_ms\":%.3f,\"build_ms\":%.3f,\"peak_rss_kib\":%ld,\"peak_vm_kib\":%lu,\"posting_payload_bytes\":%zu,\"posting_keys\":%u,\"sqlite_pages_bytes\":%lld}\n",(loaded-started)/1000.,(built-loaded)/1000.,rss,vm,posting_bytes,posting_keys,(long long)pages*page_size);fflush(stdout);
    char *line=NULL;size_t capacity=0;
    while(getline(&line,&capacity,stdin)>0) {
        /* Fixture protocol: numeric options followed by TAB then literal query.
         * Query bytes may contain TAB, but not LF in this experiment. */
        unsigned flags,kind,max_candidates,max_bytes,result_limit;int consumed=0;
        if(sscanf(line,"%u %u %u %u %u%n",&flags,&kind,&max_candidates,&max_bytes,&result_limit,&consumed)!=5)return 6;
        if(line[consumed]!='\t')return 6;
        char *query=line+consumed+1;size_t len=strlen(query);if(len && query[len-1]=='\n')query[len-1]=0;
        char *extension=strchr(query,'\t');if(extension){*extension++=0;}
        if(strlen(query)>4096 || (max_candidates>MAX_CANDIDATES && (strcmp(argv[1],"oracle") || max_candidates>1000100)) || max_bytes>MAX_RESPONSE_BYTES || result_limit>1000)return 7;
        Options options={.query=query,.extension=extension,.kind=kind==1 ? "files" : kind==2 ? "folders" : "all",.path=flags&1,.match_case=(flags&2)!=0,.limit=result_limit,.max_candidates=max_candidates,.max_bytes=max_bytes,.timeout_ms=2000};
        posting_work=0;candidate_limited=false;gint64 begin=g_get_monotonic_time();query_deadline=begin+2000000;
        clock_t cpu_start=clock();GString *response=engine ? prototype_filtered_search(&options,snapshot,&error) : fsearch_headless_search(&options,snapshot,&error);
        gint64 done=g_get_monotonic_time();resources(&rss,&vm);
        printf("{\"elapsed_ms\":%.3f,\"cpu_ms\":%.3f,\"posting_work\":%llu,\"candidate_limited\":%s,\"peak_rss_kib\":%ld,\"peak_vm_kib\":%lu,\"response\":",(done-begin)/1000.,(clock()-cpu_start)*1000./CLOCKS_PER_SEC,(unsigned long long)posting_work,candidate_limited ? "true" : "false",rss,vm);
        if(response){fwrite(response->str,1,response->len-1,stdout);g_string_free(response,TRUE);}else printf("{\"error\":\"%s\"}",error);
        printf("}\n");fflush(stdout);
    }
    free(line);if(sql)sqlite3_close(sql);
    for(unsigned i=0;i<2;++i){g_clear_pointer(&postings[i],g_hash_table_unref);g_clear_pointer(&unsupported[i],g_array_unref);}
    fsearch_headless_close(snapshot);return 0;
}
