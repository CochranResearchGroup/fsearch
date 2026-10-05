/* THROWAWAY RESEARCH PROBE: trusted synthetic databases only, not a public API.
 * No GtkApplication, gtk_init, default user config, or automatic update entrypoint.
 * Links the existing GTK-dependent library; does not prove a GTK-free engine.
 */
#include "fsearch_database_file.h"
#include "fsearch_database_include.h"
#include "fsearch_database_entry.h"
#include "fsearch_database_search_info.h"
#include "fsearch_database_search_view.h"
#include "fsearch_filter_manager.h"
#include "fsearch_query.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void json_string(const char *s) {
    putchar('"');
    for (const unsigned char *p = (const unsigned char *)s; *p; ++p) {
        if (*p == '"' || *p == '\\') printf("\\%c", *p);
        else if (*p < 32) printf("\\u%04x", *p);
        else putchar(*p);
    }
    putchar('"');
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "PROTOTYPE: build DB FIXTURE_ROOT | query DB PATTERN [LIMIT] [cancel]\n");
        return 2;
    }
    if (!strcmp(argv[1], "build")) {
        g_autoptr(FsearchDatabaseIncludeManager) includes = fsearch_database_include_manager_new();
        g_autoptr(FsearchDatabaseExcludeManager) excludes = fsearch_database_exclude_manager_new();
        g_autoptr(FsearchDatabaseInclude) root = fsearch_database_include_new(argv[3], TRUE, TRUE, FALSE, FALSE, 0);
        fsearch_database_include_manager_add(includes, root);
        g_autoptr(FsearchDatabaseIndexStore) store = fsearch_database_index_store_new(
            includes, excludes, DATABASE_INDEX_PROPERTY_FLAG_NAME | DATABASE_INDEX_PROPERTY_FLAG_PATH
                                | DATABASE_INDEX_PROPERTY_FLAG_SIZE | DATABASE_INDEX_PROPERTY_FLAG_MODIFICATION_TIME,
            NULL, NULL);
        g_autoptr(GCancellable) cancel = g_cancellable_new();
        fsearch_database_index_store_start(store, cancel);
        g_autoptr(GMutexLocker) lock = fsearch_database_index_store_get_locker(store);
        return fsearch_database_file_save(store, argv[2]) ? 0 : 1;
    }
    if (strcmp(argv[1], "query")) return 2;
    g_autoptr(FsearchDatabaseIndexStore) store = NULL;
    if (!fsearch_database_file_load(argv[2], NULL, &store, NULL, NULL, NULL, NULL)) {
        fprintf(stderr, "PROTOTYPE: database load failed; no scan fallback\n");
        return 1;
    }
    FsearchFilterManager *filters = fsearch_filter_manager_new_with_defaults();
    g_autoptr(FsearchQuery) query = fsearch_query_new(argv[3], NULL, filters, 0, "prototype");
    g_autoptr(GCancellable) cancel = g_cancellable_new();
    if (argc > 5 && !strcmp(argv[5], "cancel")) g_cancellable_cancel(cancel);
    const unsigned limit = argc > 4 ? MIN((unsigned)atoi(argv[4]), 100u) : 10;
    g_autoptr(GMutexLocker) lock = fsearch_database_index_store_get_locker(store);
    const bool complete = fsearch_database_index_store_search(
        store, 1, query, DATABASE_INDEX_PROPERTY_NAME, GTK_SORT_ASCENDING, cancel);
    g_autoptr(FsearchDatabaseSearchInfo) info = fsearch_database_index_store_get_search_info(store, 1);
    if (!info) { fsearch_filter_manager_unref(filters); return 1; }
    const unsigned total = fsearch_database_search_info_get_num_files(info)
                           + fsearch_database_search_info_get_num_folders(info);
    FsearchDatabaseSearchView *view = fsearch_database_index_store_get_search_view(store, 1);
    printf("{\"prototype\":true,\"complete\":%s,\"total\":%u,\"truncated\":%s,\"results\":[",
           complete ? "true" : "false", total, total > limit ? "true" : "false");
    for (unsigned i = 0; i < MIN(total, limit); ++i) {
        FsearchDatabaseEntry *entry = fsearch_database_search_view_get_entry_for_idx(view, i);
        g_autoptr(GString) path = db_entry_get_path_full(entry);
        if (i) putchar(',');
        json_string(path->str);
    }
    puts("]}");
    fsearch_filter_manager_unref(filters);
    return 0;
}
