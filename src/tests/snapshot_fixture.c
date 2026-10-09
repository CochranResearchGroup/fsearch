/* Owned-root fixture builder for public CLI tests. Not installed. GPL-2.0-or-later. */
#include "fsearch_database_file.h"
#include "fsearch_database_include.h"
#include <string.h>
int main(int argc, char **argv) {
    if (argc < 4 || strcmp(argv[1], "build")) return 2;
    g_autoptr(FsearchDatabaseIncludeManager) includes = fsearch_database_include_manager_new();
    g_autoptr(FsearchDatabaseExcludeManager) excludes = fsearch_database_exclude_manager_new();
    // Persist GUI auto-update flags: query-only loading must ignore them.
    for (int i = 3; i < argc; i++) {
        g_autoptr(FsearchDatabaseInclude) root = fsearch_database_include_new(argv[i], TRUE, TRUE, TRUE, TRUE, 1);
        fsearch_database_include_manager_add(includes, root);
    }
    g_autoptr(FsearchDatabaseIndexStore) store = fsearch_database_index_store_new(
        includes, excludes, DATABASE_INDEX_PROPERTY_FLAG_NAME | DATABASE_INDEX_PROPERTY_FLAG_PATH
                            | DATABASE_INDEX_PROPERTY_FLAG_SIZE | DATABASE_INDEX_PROPERTY_FLAG_MODIFICATION_TIME,
        NULL, NULL);
    g_autoptr(GCancellable) cancel = g_cancellable_new();
    fsearch_database_index_store_start(store, cancel);
    g_autoptr(GMutexLocker) lock = fsearch_database_index_store_get_locker(store);
    return fsearch_database_file_save(store, argv[2]) ? 0 : 1;
}
