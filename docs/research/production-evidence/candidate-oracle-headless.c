/* FSearch headless snapshot CLI. GPL-2.0-or-later; see COPYING. */
#include "fsearch_database_file.h"
#include "fsearch_database_include.h"
#include "fsearch_database_entry.h"
#include "fsearch_query.h"
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
struct FsearchHeadlessSnapshot {
    FsearchDatabaseIndexStore *store;
    struct stat stat;
    char *identity;
};

void fsearch_headless_close(FsearchHeadlessSnapshot *snapshot) {
    if (!snapshot) return;
    fsearch_database_index_store_unref(snapshot->store);
    g_free(snapshot->identity);
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
    bool loaded = fsearch_database_file_load_snapshot_fd(fd, &store);
    close(fd);
    if (!loaded) { *error = "snapshot_load_failed"; return NULL; }
    FsearchHeadlessSnapshot *snapshot = g_new0(FsearchHeadlessSnapshot, 1);
    snapshot->store = store; snapshot->stat = st;
    snapshot->identity = g_strdup_printf("%llu:%llu:%lld:%lld:%ld:%lld:%ld",
        (unsigned long long)st.st_dev, (unsigned long long)st.st_ino, (long long)st.st_size,
        (long long)st.st_mtim.tv_sec, st.st_mtim.tv_nsec,
        (long long)st.st_ctim.tv_sec, st.st_ctim.tv_nsec);
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
    for (unsigned type = 0; type < 2 && !strcmp(stop, "ok"); ++type) {
        if ((type == 0 && !strcmp(options->kind, "folders"))
            || (type == 1 && !strcmp(options->kind, "files"))) {
            continue;
        }
        g_autoptr(FsearchDatabaseChunkedArray) entries = type == 0
            ? fsearch_database_index_store_get_files(store, DATABASE_INDEX_PROPERTY_NAME)
            : fsearch_database_index_store_get_folders(store, DATABASE_INDEX_PROPERTY_NAME);
        const unsigned count = entries ? fsearch_database_chunked_array_get_num_entries(entries) : 0;
        for (unsigned i = 0; i < count; ++i) {
            if (examined >= (unsigned)options->max_candidates) {
                stop = "work_limit";
                break;
            }
            FsearchDatabaseEntry *entry = fsearch_database_chunked_array_get_entry(entries, i);
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

