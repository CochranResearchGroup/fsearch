/* Contained explicit-root candidate builder. GPL-2.0-or-later. */
#define _GNU_SOURCE
#include "fsearch_database_file.h"
#include "fsearch_database_entry.h"
#include "fsearch_database_include.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/landlock.h>
#include <linux/openat2.h>
#include <stdio.h>
#include <signal.h>
#include <string.h>
#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#define ENTRY_LIMIT 1000000u
static unsigned excluded_symlinks, excluded_mounts;
static int confined_open(int parent, const char *name, int flags) {
    struct open_how how = {.flags = flags | O_CLOEXEC,
        .resolve = RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_XDEV};
    return syscall(SYS_openat2, parent, name, &how, sizeof(how));
}
static bool restrict_filesystem(int root, int output) {
    int abi = syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION);
    if (abi < 3) return false;
    struct landlock_ruleset_attr rules = {.handled_access_fs = (1ULL << 15) - 1};
    int fd = syscall(SYS_landlock_create_ruleset, &rules, sizeof(rules), 0);
    if (fd < 0) return false;
    struct landlock_path_beneath_attr read = {.parent_fd = root,
        .allowed_access = LANDLOCK_ACCESS_FS_READ_DIR};
    struct landlock_path_beneath_attr write = {.parent_fd = output,
        .allowed_access = LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_TRUNCATE
                        | LANDLOCK_ACCESS_FS_MAKE_REG | LANDLOCK_ACCESS_FS_REMOVE_FILE | LANDLOCK_ACCESS_FS_REFER};
    bool ok = !syscall(SYS_landlock_add_rule, fd, LANDLOCK_RULE_PATH_BENEATH, &read, 0)
           && !syscall(SYS_landlock_add_rule, fd, LANDLOCK_RULE_PATH_BENEATH, &write, 0)
           && !prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
           && !syscall(SYS_landlock_restrict_self, fd, 0);
    close(fd); return ok;
}
static bool walk(int fd, FsearchDatabaseEntry *parent, DynamicArray *folders, DynamicArray *files, unsigned depth,
                 int root, const char *relative) {
    if (depth > 64) return false;
    DIR *directory = fdopendir(fd);
    if (!directory) { close(fd); return false; }
    bool ok = true;
    for (;;) {
        errno = 0;
        struct dirent *item = readdir(directory);
        if (!item) { if (errno) ok = false; break; }
        if (!strcmp(item->d_name, ".") || !strcmp(item->d_name, "..")) continue;
        // O_PATH without O_NOFOLLOW makes NO_SYMLINKS reject even the last link.
        char child_path[4096];
        int length = snprintf(child_path, sizeof(child_path), "%s%s%s", relative,
                              relative[0] ? "/" : "", item->d_name);
        if (length < 0 || (size_t)length >= sizeof(child_path)) { ok = false; break; }
        // Re-resolve from the approved root: an admitted parent may have moved.
        int child = confined_open(root, child_path, O_PATH);
        if (child < 0) {
            if (errno == ELOOP) { excluded_symlinks++; continue; }
            if (errno == EXDEV) { excluded_mounts++; continue; }
            ok = false; break;
        }
        struct stat info;
        if (fstat(child, &info) || darray_get_num_items(files) + darray_get_num_items(folders) >= ENTRY_LIMIT) {
            close(child); ok = false; break;
        }
        if (S_ISDIR(info.st_mode)) {
            int contents = confined_open(root, child_path, O_RDONLY | O_DIRECTORY);
            close(child);
            struct stat pinned;
            if (contents < 0 || fstat(contents, &pinned)
                || pinned.st_dev != info.st_dev || pinned.st_ino != info.st_ino) {
                if (contents >= 0) close(contents);
                ok = false; break;
            }
            FsearchDatabaseEntry *entry = db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME, item->d_name, parent, DATABASE_ENTRY_TYPE_FOLDER);
            darray_add_item(folders, entry);
            if (!walk(contents, entry, folders, files, depth + 1, root, child_path)) { ok = false; break; }
        }
        else {
            close(child);
            if (S_ISREG(info.st_mode)) darray_add_item(files, db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME, item->d_name, parent, DATABASE_ENTRY_TYPE_FILE));
        }
    }
    closedir(directory); return ok;
}
static int compare_name(void *a, void *b, void *unused) { (void)unused; return db_entry_compare_entries_by_name(a, b); }
static int compare_path(void *a, void *b, void *unused) { (void)unused; return db_entry_compare_entries_by_path(a, b); }
static bool save_candidate(const char *root_path, const char *output_path, DynamicArray *folders, DynamicArray *files) {
    g_autoptr(FsearchDatabaseIncludeManager) includes = fsearch_database_include_manager_new();
    g_autoptr(FsearchDatabaseExcludeManager) excludes = fsearch_database_exclude_manager_new();
    g_autoptr(FsearchDatabaseInclude) include = fsearch_database_include_new(root_path, TRUE, TRUE, FALSE, FALSE, 0);
    fsearch_database_include_set_last_scan_time(include, g_get_real_time() / G_USEC_PER_SEC);
    fsearch_database_include_set_last_scanned_file_count(include, darray_get_num_items(files));
    fsearch_database_include_set_last_scanned_folder_count(include, darray_get_num_items(folders));
    fsearch_database_include_manager_add(includes, include);
    g_autoptr(GPtrArray) indices = g_ptr_array_new_with_free_func((GDestroyNotify)fsearch_database_index_unref);
    g_autoptr(DynamicArray) file_paths = darray_copy(files), folder_paths = darray_copy(folders);
    darray_sort(file_paths, compare_path, NULL, NULL); darray_sort(folder_paths, compare_path, NULL, NULL);
    g_ptr_array_add(indices, fsearch_database_index_new_with_content(include, excludes, folder_paths, file_paths,
        DATABASE_INDEX_PROPERTY_FLAG_NAME | DATABASE_INDEX_PROPERTY_FLAG_PATH));
    darray_sort(files, compare_name, NULL, NULL); darray_sort(folders, compare_name, NULL, NULL);
    DynamicArray *fa[NUM_DATABASE_INDEX_PROPERTIES] = {0}, *da[NUM_DATABASE_INDEX_PROPERTIES] = {0};
    fa[DATABASE_INDEX_PROPERTY_NAME] = files; da[DATABASE_INDEX_PROPERTY_NAME] = folders;
    fa[DATABASE_INDEX_PROPERTY_PATH] = file_paths; da[DATABASE_INDEX_PROPERTY_PATH] = folder_paths;
    g_autoptr(FsearchDatabaseIndexStore) store = fsearch_database_index_store_new_snapshot(indices, fa, da, includes, excludes,
        DATABASE_INDEX_PROPERTY_FLAG_NAME | DATABASE_INDEX_PROPERTY_FLAG_PATH);
    g_autoptr(GMutexLocker) locker = fsearch_database_index_store_get_locker(store);
    return fsearch_database_file_save(store, output_path);
}
int main(int argc, char **argv) {
    if (argc != 5 || strcmp(argv[1], "--root") || strcmp(argv[3], "--output") || argv[2][0] != '/') return 2;
    pid_t parent_pid = getppid();
    if (prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != parent_pid) return 3;
    char gate;
    if (read(STDIN_FILENO, &gate, 1) != 1 || gate != 'G') return 2;
    struct rlimit memory = {256u * 1024u * 1024u, 256u * 1024u * 1024u};
    struct rlimit size = {64u * 1024u * 1024u, 64u * 1024u * 1024u};
    struct rlimit core = {0, 0};
    if (setrlimit(RLIMIT_CORE, &core) || setrlimit(RLIMIT_AS, &memory) || setrlimit(RLIMIT_FSIZE, &size)) return 3;
    if (syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION) < 3) return 3;
    struct open_how how = {.flags = O_PATH | O_DIRECTORY | O_CLOEXEC, .resolve = RESOLVE_NO_SYMLINKS};
    int root = syscall(SYS_openat2, AT_FDCWD, argv[2], &how, sizeof(how));
    if (root < 0) return 3;
    g_autofree char *output_directory = g_path_get_dirname(argv[4]);
    int output = open(output_directory, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    struct stat output_info;
    if (output < 0 || fstat(output, &output_info) || output_info.st_uid != geteuid() || (output_info.st_mode & 0077)) {
        close(root); if (output >= 0) close(output); return 3;
    }
    umask(0077);
    g_autofree char *output_name = g_path_get_basename(argv[4]);
    if (fchdir(output) || !restrict_filesystem(root, output)) { close(root); close(output); return 3; }
    g_autoptr(DynamicArray) folders = darray_new(128), files = darray_new(128);
    FsearchDatabaseEntry *entry = db_entry_new(DATABASE_INDEX_PROPERTY_FLAG_NAME, argv[2], NULL, DATABASE_ENTRY_TYPE_FOLDER);
    darray_add_item(folders, entry);
    int contents = confined_open(root, ".", O_RDONLY | O_DIRECTORY);
    close(output);
    bool complete = contents >= 0 && walk(contents, entry, folders, files, 0, root, "");
    close(root);
    if (!complete || !save_candidate(argv[2], output_name, folders, files)) return 4;
    printf("{\"status\":\"candidate\",\"excluded_symlinks\":%u,\"excluded_mounts\":%u}\n", excluded_symlinks, excluded_mounts);
    return 0;
}
