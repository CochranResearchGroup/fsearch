/* FSearch headless snapshot CLI. GPL-2.0-or-later; see COPYING. */
#include "fsearch_database_file.h"
#include "fsearch_database_include.h"
#include "fsearch_database_entry.h"
#include "fsearch_query.h"
#include "fsearch_utf.h"
#include "fsearch_string_utils.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <poll.h>
#include <signal.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "fsearch_headless.h"
#include "fsearch_catalog_query.h"
#include <stdint.h>
#include <unicode/ustring.h>
#if defined(__GLIBC__)
#include <malloc.h>
#endif
struct FsearchHeadlessSnapshot {
    FsearchDatabaseIndexStore *store;
    FsearchCatalog *catalog;
    FsearchDatabaseIncludeManager *root_metadata;
    struct stat stat;
    char *identity;
    /* Fixed 192-bit trigram signatures: a sound filter, never a matcher. */
    uint64_t *signatures[2];
    size_t signature_stride[2];
};

#include "fsearch_headless_signature.h"
static uint64_t signature_block(FsearchHeadlessSnapshot *snapshot, unsigned type, unsigned block,
                                const uint64_t required[SIGNATURE_WORDS]) {
    uint64_t possible = UINT64_MAX;
    for (unsigned word = 0; word < SIGNATURE_WORDS && possible; ++word) {
        uint64_t bits = required[word];
        while (bits && possible) {
            unsigned bit = __builtin_ctzll(bits);
            possible &= snapshot->signatures[type][(word * 64u + bit) * snapshot->signature_stride[type] + block];
            bits &= bits - 1;
        }
    }
    return possible;
}
static uint64_t signature_flags(FsearchHeadlessSnapshot *snapshot, unsigned type, unsigned rank) {
    size_t stride = snapshot->signature_stride[type];
    uint64_t mask = UINT64_C(1) << (rank % 64);
    uint64_t flags = 0;
    if (snapshot->signatures[type][191u * stride + rank / 64] & mask) flags |= SIGNATURE_NONASCII;
    if (snapshot->signatures[type][190u * stride + rank / 64] & mask) flags |= SIGNATURE_UPPERCASE;
    return flags;
}
static void build_signatures(FsearchHeadlessSnapshot *snapshot) {
    size_t allocated = 0;
    FsearchUtfBuilder builder = {0};
    for (unsigned type = 0; type < 2; ++type) {
        g_autoptr(FsearchDatabaseChunkedArray) entries = type
            ? fsearch_database_index_store_get_folders(snapshot->store, DATABASE_INDEX_PROPERTY_NAME)
            : fsearch_database_index_store_get_files(snapshot->store, DATABASE_INDEX_PROPERTY_NAME);
        unsigned count = entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;
        size_t stride = ((size_t)count + 63) / 64;
        if (stride > (SIGNATURE_MAX_BYTES - allocated) / (192u * sizeof(uint64_t))) continue;
        size_t bytes = stride * 192u * sizeof(uint64_t);
        uint64_t *signatures = g_try_malloc0(bytes);
        if (!signatures) continue; /* Exact bounded scanning remains available. */
        snapshot->signatures[type] = signatures; allocated += bytes;
        snapshot->signature_stride[type] = stride;
        g_autoptr(DynamicArray) chunks = entries ? fsearch_database_chunked_array_get_chunks(entries) : NULL;
        unsigned rank = 0;
        for (unsigned c = 0; chunks && c < darray_get_num_items(chunks); ++c) {
            DynamicArray *chunk = darray_get_item(chunks, c);
            for (unsigned i = 0; i < darray_get_num_items(chunk); ++i) {
                const char *name = db_entry_get_name_raw(darray_get_item(chunk, i));
                uint64_t signature[SIGNATURE_WORDS];
                signature_text(name, signature);
                if (!signature_ascii(name)) {
                    g_autofree char *normalized = normalized_utf8(&builder, name);
                    if (normalized) {
                        uint64_t folded[SIGNATURE_WORDS];
                        signature_text(normalized, folded);
                        for (unsigned word = 0; word < SIGNATURE_WORDS; ++word)
                            signature[word] |= folded[word];
                    }
                    else for (unsigned word = 0; word < SIGNATURE_WORDS; ++word)
                        signature[word] = UINT64_MAX; /* Preserve raw-byte/error fallback. */
                }
                for (unsigned word = 0; word < SIGNATURE_WORDS; ++word) {
                    uint64_t bits = signature[word];
                    while (bits) {
                        unsigned bit = __builtin_ctzll(bits);
                        signatures[(word * 64u + bit) * stride + rank / 64] |= UINT64_C(1) << (rank % 64);
                        bits &= bits - 1;
                    }
                }
                rank++;
            }
        }
    }
    fsearch_utf_builder_clear(&builder);
}

void fsearch_headless_close(FsearchHeadlessSnapshot *snapshot) {
    if (!snapshot) return;
    if(snapshot->store)fsearch_database_index_store_unref(snapshot->store);
    if(snapshot->catalog)fsearch_catalog_free(snapshot->catalog);
    if(snapshot->root_metadata)g_object_unref(snapshot->root_metadata);
    g_free(snapshot->identity);
    g_free(snapshot->signatures[0]);
    g_free(snapshot->signatures[1]);
    g_free(snapshot);
}

const char *fsearch_headless_identity(FsearchHeadlessSnapshot *snapshot) { return snapshot->identity; }

static FsearchHeadlessSnapshot *open_snapshot(const char *path, bool indexed, const char **error) {
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0) { *error = "snapshot_unavailable"; return NULL; }
    struct stat st;
    if (fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) || st.st_uid != geteuid() || (st.st_mode & 0077)) {
        close(fd); *error = "snapshot_not_private"; return NULL;
    }
    if (st.st_size <= 0 || st.st_size > MAX_SNAPSHOT_BYTES) {
        close(fd); *error = "snapshot_size_limit"; return NULL;
    }
    FsearchDatabaseIndexStore *store = NULL;
    bool loaded = fsearch_database_file_load_query_snapshot_fd(fd, &store);
    close(fd);
    if (!loaded) { *error = "snapshot_load_failed"; return NULL; }
    FsearchHeadlessSnapshot *snapshot = g_new0(FsearchHeadlessSnapshot, 1);
    snapshot->store = store; snapshot->stat = st;
    snapshot->identity = g_strdup_printf("%llu:%llu:%lld:%lld:%ld:%lld:%ld",
        (unsigned long long)st.st_dev, (unsigned long long)st.st_ino, (long long)st.st_size,
        (long long)st.st_mtim.tv_sec, st.st_mtim.tv_nsec,
        (long long)st.st_ctim.tv_sec, st.st_ctim.tv_nsec);
#if defined(__GLIBC__)
    // Return freed loader scratch space before reserving the candidate index.
    // Correctness does not depend on the allocator supporting this hint.
    malloc_trim(0);
#endif
    if(indexed)build_signatures(snapshot);
    return snapshot;
}

FsearchHeadlessSnapshot *fsearch_headless_open(const char *path,const char **error) {return open_snapshot(path,true,error);}
FsearchCatalog *fsearch_headless_catalog(FsearchHeadlessSnapshot*s) {return s->catalog;}
bool fsearch_headless_restore_catalog(FsearchHeadlessSnapshot *s,int fd,const char **error) {
    FsearchCatalogLimits limits={1200UL*1024*1024,4096,4096,16};
    FsearchCatalog *next=fsearch_catalog_checkpoint_read(fd,s->identity,&limits,error);
    if(!next)return false;
    FsearchCatalog *old=s->catalog;s->catalog=next;fsearch_catalog_free(old);
#if defined(__GLIBC__)
    malloc_trim(0);
#endif
    return true;
}
FsearchHeadlessSnapshot *fsearch_headless_open_catalog(const char*path,const char**error) {
    FsearchHeadlessSnapshot*s=open_snapshot(path,false,error);if(!s)return NULL;
    g_autoptr(FsearchDatabaseChunkedArray)folders=fsearch_database_index_store_get_folders(s->store,DATABASE_INDEX_PROPERTY_NAME);
    g_autoptr(FsearchDatabaseChunkedArray)files=fsearch_database_index_store_get_files(s->store,DATABASE_INDEX_PROPERTY_NAME);
    unsigned nf=folders?fsearch_database_chunked_array_get_num_entries(folders):0,nn=files?fsearch_database_chunked_array_get_num_entries(files):0;
    if(nf>10000000u||nn>10000000u-nf){*error="entry_limit";fsearch_headless_close(s);return NULL;}
    if(!nf&&!nn){build_signatures(s);return s;} /* Preserve valid empty legacy snapshots. */
    FsearchCatalogEntry*seed=g_try_new0(FsearchCatalogEntry,nf+nn);
    if(!seed){*error="memory_budget";fsearch_headless_close(s);return NULL;}
    g_autoptr(GHashTable)ids=g_hash_table_new(g_direct_hash,g_direct_equal);unsigned next=0;
    /* Allocate configured roots first so ID zero is always an immutable root. */
    for(unsigned roots=0;roots<2;roots++)for(unsigned i=0;i<nf;i++) {
        FsearchDatabaseEntry*e=fsearch_database_chunked_array_get_entry(folders,i);bool root=db_entry_get_parent(e)==NULL;
        if(root!=(roots==0))continue;g_hash_table_insert(ids,e,GUINT_TO_POINTER(++next));
    }
    for(unsigned type=0;type<2;type++) {
        FsearchDatabaseChunkedArray*array=type?files:folders;
        g_autoptr(DynamicArray)chunks=array?fsearch_database_chunked_array_get_chunks(array):NULL;
        for(unsigned chunk=0;chunks&&chunk<darray_get_num_items(chunks);chunk++) {
            DynamicArray*entries=darray_get_item(chunks,chunk);
            for(unsigned i=0;i<darray_get_num_items(entries);i++) {
                FsearchDatabaseEntry*e=darray_get_item(entries,i),*parent=db_entry_get_parent(e);
                unsigned id=type?next++:GPOINTER_TO_UINT(g_hash_table_lookup(ids,e))-1;
                gpointer parent_id=parent?g_hash_table_lookup(ids,parent):GUINT_TO_POINTER(id+1);
                if(!parent_id){g_free(seed);*error="invalid_parent";fsearch_headless_close(s);return NULL;}
                seed[id]=(FsearchCatalogEntry){id,GPOINTER_TO_UINT(parent_id)-1,type?FSEARCH_CATALOG_FILE:FSEARCH_CATALOG_FOLDER,db_entry_get_name_raw(e)};
            }
        }
    }
    /* Leave process/service headroom outside the catalog's own allocation ledger. */
    FsearchCatalogLimits limits={1200UL*1024*1024,4096,4096,16};
    s->catalog=fsearch_catalog_new(seed,nf+nn,&limits,error);g_free(seed);
    if(!s->catalog){fsearch_headless_close(s);return NULL;}
    s->root_metadata=fsearch_database_index_store_get_include_manager(s->store);
    fsearch_database_index_store_unref(s->store);s->store=NULL;
#if defined(__GLIBC__)
    malloc_trim(0);
#endif
    return s;
}

/* Cached coverage metadata accompanies a private catalog generation. It never
 * reconstructs roots by probing the filesystem or makes an observation claim. */
#define CHECKPOINT_METADATA_MAX (64u * 1024u)
static void metadata_u32(GByteArray *data,uint32_t value){value=GUINT32_TO_LE(value);g_byte_array_append(data,(guint8*)&value,4);}
static void metadata_u64(GByteArray *data,uint64_t value){value=GUINT64_TO_LE(value);g_byte_array_append(data,(guint8*)&value,8);}
static uint32_t metadata_read32(const guint8 *data){uint32_t value;memcpy(&value,data,4);return GUINT32_FROM_LE(value);}
static uint64_t metadata_read64(const guint8 *data){uint64_t value;memcpy(&value,data,8);return GUINT64_FROM_LE(value);}
static void metadata_digest(const void *data,size_t length,guint8 digest[32]) {
    GChecksum *sum=g_checksum_new(G_CHECKSUM_SHA256);g_checksum_update(sum,data,length);
    gsize n=32;g_checksum_get_digest(sum,digest,&n);g_checksum_free(sum);
}
static bool metadata_io(int fd,void *data,size_t size,bool writing) {
    size_t offset=0;while(offset<size){ssize_t n=writing?pwrite(fd,(char*)data+offset,size-offset,offset):pread(fd,(char*)data+offset,size-offset,offset);
        if(n<0&&errno==EINTR)continue;
        if(n<=0)return false;
        offset+=n;
    }
    return true;
}
bool fsearch_headless_checkpoint_metadata_write(FsearchHeadlessSnapshot *s,int fd,uint64_t sequence,const char **error) {
    struct stat info;if(fstat(fd,&info)||!S_ISREG(info.st_mode)||info.st_size){*error="checkpoint_metadata_output";return false;}
    g_autoptr(GPtrArray) roots=fsearch_database_include_manager_get_includes(s->root_metadata);
    if(roots->len>1024){*error="checkpoint_metadata_budget";return false;}
    g_autoptr(GByteArray) data=g_byte_array_new();g_byte_array_append(data,(guint8*)"FSHM0001",8);
    guint8 digest[32];metadata_digest(s->identity,strlen(s->identity),digest);g_byte_array_append(data,digest,32);
    metadata_u64(data,sequence);metadata_u64(data,s->stat.st_mtime);metadata_u32(data,roots->len);
    for(unsigned i=0;i<roots->len;i++){
        FsearchDatabaseInclude *root=g_ptr_array_index(roots,i);const char *path=fsearch_database_include_get_path(root);size_t n=strnlen(path,4097);
        if(!n||n>4096||path[0]!='/'||data->len+16+n+32>CHECKPOINT_METADATA_MAX){*error="checkpoint_metadata_budget";return false;}
        metadata_u32(data,n);metadata_u64(data,fsearch_database_include_get_last_scan_time(root));
        metadata_u32(data,fsearch_database_include_get_last_error_code(root));g_byte_array_append(data,(guint8*)path,n);
    }
    metadata_digest(data->data,data->len,digest);g_byte_array_append(data,digest,32);
    if(!metadata_io(fd,data->data,data->len,true)||fsync(fd)){*error="checkpoint_metadata_write_failed";return false;}
    g_autofree guint8 *readback=g_malloc(data->len);struct stat written;
    if(fstat(fd,&written)||written.st_size!=data->len||!metadata_io(fd,readback,data->len,false)||memcmp(data->data,readback,data->len)){
        *error="checkpoint_metadata_readback_failed";return false;
    }
    return true;
}
static int checkpoint_private_open(const char *path) {
    int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);struct stat info;
    if(fd<0)return -1;
    if(fstat(fd,&info)||!S_ISREG(info.st_mode)||info.st_uid!=geteuid()||(info.st_mode&077)||info.st_nlink!=1){close(fd);return -1;}
    return fd;
}
FsearchHeadlessSnapshot *fsearch_headless_open_checkpoint(const char *path,const char *identity,const char **error) {
    if(!identity||!*identity||strlen(identity)>256||strspn(identity,"0123456789:-")!=strlen(identity)){*error="checkpoint_binding";return NULL;}
    g_autofree char *metadata_path=g_strconcat(path,".metadata",NULL);
    int meta=checkpoint_private_open(metadata_path);struct stat info;
    if(meta<0){*error="checkpoint_metadata_missing";return NULL;}
    if(fstat(meta,&info)||info.st_size<92||info.st_size>CHECKPOINT_METADATA_MAX){close(meta);*error="checkpoint_metadata_invalid";return NULL;}
    g_autofree guint8 *data=g_malloc(info.st_size);bool loaded=metadata_io(meta,data,info.st_size,false);close(meta);
    if(!loaded){*error="checkpoint_metadata_invalid";return NULL;}
    guint8 digest[32],binding[32];metadata_digest(data,info.st_size-32,digest);metadata_digest(identity,strlen(identity),binding);
    if(!loaded||memcmp(data,"FSHM0001",8)||memcmp(data+8,binding,32)||memcmp(data+info.st_size-32,digest,32)){*error="checkpoint_metadata_invalid";return NULL;}
    unsigned count=metadata_read32(data+56);size_t offset=60,end=info.st_size-32;
    FsearchHeadlessSnapshot *s=g_new0(FsearchHeadlessSnapshot,1);s->identity=g_strdup(identity);s->stat.st_mtime=metadata_read64(data+48);
    s->root_metadata=fsearch_database_include_manager_new();bool valid=count<=1024;
    for(unsigned i=0;i<count&&valid;i++){
        if(end-offset<16){valid=false;break;}
        unsigned n=metadata_read32(data+offset);int64_t scan=metadata_read64(data+offset+4);uint32_t code=metadata_read32(data+offset+12);offset+=16;
        if(!n||n>4096||n>end-offset||data[offset]!='/'||memchr(data+offset,0,n)){valid=false;break;}
        g_autofree char *root_path=g_strndup((char*)data+offset,n);offset+=n;
        g_autoptr(FsearchDatabaseInclude) root=fsearch_database_include_new(root_path,false,true,false,false,-1);
        fsearch_database_include_set_last_scan_time(root,scan);fsearch_database_include_set_last_error_code(root,code);
        fsearch_database_include_manager_add(s->root_metadata,root);
    }
    if(!valid||offset!=end){fsearch_headless_close(s);*error="checkpoint_metadata_invalid";return NULL;}
    int fd=checkpoint_private_open(path);
    if(fd<0){fsearch_headless_close(s);*error="checkpoint_open_failed";return NULL;}
    FsearchCatalogLimits limits={1200UL*1024*1024,4096,4096,16};s->catalog=fsearch_catalog_checkpoint_read(fd,identity,&limits,error);close(fd);
    FsearchCatalogStatus state={0};if(s->catalog)fsearch_catalog_status(s->catalog,&state);
    if(!s->catalog||state.sequence!=metadata_read64(data+40)){if(s->catalog)*error="checkpoint_metadata_sequence";fsearch_headless_close(s);return NULL;}
    return s;
}

void
fsearch_headless_append_json_string(GString *out, const char *text) {
    g_string_append_c(out, '"');
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        if (*p == '"' || *p == '\\') {
            g_string_append_c(out, '\\');
            g_string_append_c(out, *p);
        }
        else if (*p < 32) {
            g_string_append_printf(out, "\\u%04x", *p);
        }
        else {
            g_string_append_c(out, *p);
        }
    }
    g_string_append_c(out, '"');
}

static void
append_path(GString *out, const char *path) {
    g_string_append(out, "{\"path\":");
    if (g_utf8_validate(path, -1, NULL)) {
        fsearch_headless_append_json_string(out, path);
        g_string_append(out, ",\"path_bytes_base64\":null}");
    }
    else {
        g_autofree char *encoded = g_base64_encode((const guchar *)path, strlen(path));
        g_string_append(out, "null,\"path_bytes_base64\":");
        fsearch_headless_append_json_string(out, encoded);
        g_string_append_c(out, '}');
    }
}

static GString *catalog_search(const Options*o,FsearchHeadlessSnapshot*s,const char**error) {
    g_autoptr(FsearchCatalogView)v=fsearch_catalog_acquire(s->catalog);FsearchCatalogQueryResult r;
    if(!fsearch_catalog_query(v,o,&r,error))return NULL;
    FsearchCatalogStatus state;fsearch_catalog_status(s->catalog,&state);
    GString*out=g_string_new(NULL);
    g_string_append_printf(out,"{\"schema_version\":1,\"status\":\"%s\",\"complete\":%s,\"truncated\":%s,\"visibility\":\"cached\",\"examined\":%u,\"catalog\":{\"sequence\":%llu,\"generation\":%llu,\"deferred_reason\":",r.stop,!strcmp(r.stop,"ok")?"true":"false",!strcmp(r.stop,"ok")?"false":"true",r.examined,(unsigned long long)fsearch_catalog_view_sequence(v),(unsigned long long)fsearch_catalog_view_generation(v));
    if(state.deferred_reason)fsearch_headless_append_json_string(out,state.deferred_reason);else g_string_append(out,"null");
    g_string_append_printf(out,"},\"snapshot\":{\"identity\":\"%s\",\"mtime_unix\":%lld,\"age_seconds\":%lld,\"roots\":[",s->identity,(long long)s->stat.st_mtime,(long long)MAX(0,g_get_real_time()/G_USEC_PER_SEC-s->stat.st_mtime));
    g_autoptr(GPtrArray)roots=fsearch_database_include_manager_get_includes(s->root_metadata);
    for(unsigned i=0;i<roots->len;i++) {
        FsearchDatabaseInclude*root=g_ptr_array_index(roots,i);if(i)g_string_append_c(out,',');append_path(out,fsearch_database_include_get_path(root));g_string_truncate(out,out->len-1);
        int64_t scan=fsearch_database_include_get_last_scan_time(root);g_string_append_printf(out,",\"last_scan_unix\":%lld,\"age_seconds\":",(long long)scan);
        if(scan>0)g_string_append_printf(out,"%lld",(long long)MAX(0,g_get_real_time()/G_USEC_PER_SEC-scan));else g_string_append(out,"null");
        g_string_append_printf(out,",\"last_error_code\":%u}",fsearch_database_include_get_last_error_code(root));
        if(out->len>(unsigned)o->max_bytes/2){fsearch_catalog_query_clear(&r);g_string_free(out,true);*error="coverage_size_limit";return NULL;}
    }
    g_string_append(out,"]},\"results\":[");g_string_append_len(out,r.rows->str,r.rows->len);g_string_append(out,"]}\n");fsearch_catalog_query_clear(&r);
    if(out->len>(unsigned)o->max_bytes){g_string_free(out,true);*error="response_size_limit";return NULL;}return out;
}
GString *fsearch_headless_search(const Options *options, FsearchHeadlessSnapshot *snapshot, const char **error) {
    if(snapshot->catalog)return catalog_search(options,snapshot,error);
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
    uint64_t required[SIGNATURE_WORDS] = {0};
    bool filter = query_signature(options, required);
    bool path_parts = options->path && options->query[0] && !strchr(options->query, '/')
                      && signature_ascii(options->query)
                      && (options->match_case || fsearch_string_is_ascii_icase(options->query));
    g_autoptr(GHashTable) parent_matches = path_parts ? g_hash_table_new(g_direct_hash, g_direct_equal) : NULL;
    Options basename_options = *options; basename_options.path = false;
    bool path_signature = path_parts && query_signature(&basename_options, required);
    bool short_ascii = !options->path && signature_ascii(options->query)
                       && strlen(options->query) > 0 && strlen(options->query) < 3;
    unsigned candidate_blocks = 0;
    bool ascii_query = !options->path && signature_ascii(options->query);
    // Use the literal matcher's raw-byte selection even for Unicode names.
    // Other ASCII literals can require ICU (for example locale-sensitive case).
    bool raw_ascii_query = ascii_query && (options->match_case || fsearch_string_is_ascii_icase(options->query));
    g_autofree char *lower_query = ascii_query ? g_ascii_strdown(options->query, -1) : NULL;
    for (unsigned type = 0; type < 2 && !strcmp(stop, "ok"); ++type) {
        if ((type == 0 && !strcmp(options->kind, "folders"))
            || (type == 1 && !strcmp(options->kind, "files"))) {
            continue;
        }
        g_autoptr(FsearchDatabaseChunkedArray) entries = type == 0
            ? fsearch_database_index_store_get_files(store, DATABASE_INDEX_PROPERTY_NAME)
            : fsearch_database_index_store_get_folders(store, DATABASE_INDEX_PROPERTY_NAME);
        const unsigned count = entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;
        g_autoptr(DynamicArray) chunks = entries ? fsearch_database_chunked_array_get_chunks(entries) : NULL;
        unsigned chunk_index = 0, chunk_base = 0;
        DynamicArray *chunk = count ? darray_get_item(chunks, 0) : NULL;
        unsigned chunk_end = chunk ? darray_get_num_items(chunk) : 0;
        uint64_t possible_block = 0;
        for (unsigned i = 0; i < count; ++i) {
            while (i >= chunk_end) {
                chunk_base = chunk_end;
                chunk = darray_get_item(chunks, ++chunk_index);
                chunk_end += darray_get_num_items(chunk);
            }
            if (filter || short_ascii || path_parts) {
                if (i % 64 == 0 && ++candidate_blocks > CANDIDATE_BLOCK_BUDGET) {
                    stop = "work_limit"; break;
                }
                if (filter && snapshot->signatures[type]) {
                    if (i % 64 == 0) {
                        possible_block = signature_block(snapshot, type, i / 64, required);
#if defined(__GNUC__)
                        // Prefetch only future candidates, using the same column intersection.
                        if (i + 256 < chunk_end) {
                            if (++candidate_blocks > CANDIDATE_BLOCK_BUDGET) { stop = "work_limit"; break; }
                            uint64_t future = signature_block(snapshot, type, i / 64 + 4, required);
                            while (future) {
                                unsigned ahead = i + 256 + __builtin_ctzll(future);
                                if (ahead >= chunk_end) break;
                                void *entry = darray_get_item(chunk, ahead - chunk_base);
                                __builtin_prefetch(entry, 0, 3);
                                __builtin_prefetch((void *)((uintptr_t)entry + 64), 0, 3);
                                future &= future - 1;
                            }
                        }
#endif
                    }
                    if (!(possible_block & (UINT64_C(1) << (i % 64)))) continue;
                }
            }
            FsearchDatabaseEntry *entry = darray_get_item(chunk, i - chunk_base);
            if (path_parts) {
                FsearchDatabaseEntry *parent = db_entry_get_parent(entry);
                gpointer cached = g_hash_table_lookup(parent_matches, parent);
                if (!cached && g_hash_table_size(parent_matches) < 4096) {
                    g_autoptr(GString) path = db_entry_get_path(entry);
                    bool matches = options->match_case ? strstr(path->str, options->query) != NULL
                                                       : strcasestr(path->str, options->query) != NULL;
                    cached = GINT_TO_POINTER(matches ? 2 : 1);
                    g_hash_table_insert(parent_matches, parent, cached);
                }
                if (cached == GINT_TO_POINTER(1)) {
                    if (path_signature && snapshot->signatures[type]
                        && !(signature_block(snapshot, type, i / 64, required) & (UINT64_C(1) << (i % 64)))) continue;
                    const char *name = db_entry_get_name_raw(entry);
                    if (!(options->match_case ? strstr(name, options->query) : strcasestr(name, options->query))) continue;
                }
                // An uncached parent falls back to authoritative full-path matching.
                // A slash-free literal cannot cross a parent/name separator.
            }
            if (ascii_query) {
                const char *name = db_entry_get_name_raw(entry);
                bool indexed = snapshot->signatures[type] != NULL;
                uint64_t flags = indexed ? signature_flags(snapshot, type, i) : 0;
                bool ascii = indexed ? !(flags & SIGNATURE_NONASCII) : signature_ascii(name);
                if ((ascii || raw_ascii_query) && !(options->match_case ? strstr(name, options->query)
                               : indexed && !(flags & SIGNATURE_UPPERCASE) ? strstr(name, lower_query)
                               : short_ascii ? short_ascii_contains(name, options->query, false)
                               : strcasestr(name, options->query))) continue;
            }
            if (examined >= (unsigned)options->max_candidates) {
                stop = "work_limit";
                break;
            }
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
