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
#include <stdint.h>
#include <unicode/ustring.h>
#if defined(__GLIBC__)
#include <malloc.h>
#endif
struct FsearchHeadlessSnapshot {
    FsearchDatabaseIndexStore *store;
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
    fsearch_database_index_store_unref(snapshot->store);
    g_free(snapshot->identity);
    g_free(snapshot->signatures[0]);
    g_free(snapshot->signatures[1]);
    g_free(snapshot);
}

const char *fsearch_headless_identity(FsearchHeadlessSnapshot *snapshot) { return snapshot->identity; }

FsearchHeadlessSnapshot *fsearch_headless_open(const char *path, const char **error) {
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
    build_signatures(snapshot);
    return snapshot;
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

GString *fsearch_headless_search(const Options *options, FsearchHeadlessSnapshot *snapshot, const char **error) {
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
