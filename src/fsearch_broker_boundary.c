/* Rooted handle inventory/validation preparation. GPL-2.0-or-later.
 * No fanotify groups, marks, open_by_handle_at or indexed file-content reads.
 * Actual adversarial ancestry confinement is a separate qualification gate.
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <glib.h>
#include <linux/landlock.h>
#include <linux/capability.h>
#include <linux/openat2.h>
#include <signal.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <unistd.h>

#define MAX_ENTRIES 10000000u
#define MAX_DIRECTORIES 800000u
static int root;
static const char *root_path;
static struct stat root_identity;
static unsigned long long root_mount;
static unsigned entries, directories;

static bool mount_identity(int fd, unsigned long long *mount) {
    struct statx result;
    if (statx(fd, "", AT_EMPTY_PATH, STATX_MNT_ID, &result) || !(result.stx_mask & STATX_MNT_ID)) return false;
    *mount = result.stx_mnt_id;
    return true;
}

static bool root_current(void) {
    /* This metadata-only revalidation addresses the configured root itself,
     * never a caller-selected path or an outside event handle. No replacement
     * root is admitted/traversed after an identity or mount mismatch. */
    struct open_how how = {.flags = O_PATH | O_DIRECTORY | O_CLOEXEC, .resolve = RESOLVE_NO_SYMLINKS};
    int current = syscall(SYS_openat2, AT_FDCWD, root_path, &how, sizeof(how));
    struct stat identity; unsigned long long mount;
    bool ok = current >= 0 && !fstat(current, &identity) && mount_identity(current, &mount)
        && identity.st_dev == root_identity.st_dev && identity.st_ino == root_identity.st_ino && mount == root_mount;
    if (current >= 0) close(current);
    return ok;
}

static int beneath(const char *path, int flags) {
    if (!root_current()) { errno = ESTALE; return -1; }
    struct open_how how = {.flags = flags | O_CLOEXEC,
        .resolve = RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_XDEV};
    return syscall(SYS_openat2, root, *path ? path : ".", &how, sizeof(how));
}

static bool confine(void) {
    if (syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION) < 3) return false;
    struct landlock_ruleset_attr rules = {.handled_access_fs = (1ULL << 15) - 1};
    int ruleset = syscall(SYS_landlock_create_ruleset, &rules, sizeof(rules), 0);
    if (ruleset < 0) return false;
    struct landlock_path_beneath_attr access = {.parent_fd = root,
                                               .allowed_access = LANDLOCK_ACCESS_FS_READ_DIR};
    bool ok = !syscall(SYS_landlock_add_rule, ruleset, LANDLOCK_RULE_PATH_BENEATH, &access, 0)
        && !prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        && !syscall(SYS_landlock_restrict_self, ruleset, 0);
    close(ruleset);
    return ok;
}

static char *hex(const unsigned char *data, size_t length) {
    char *result = g_try_malloc(length * 2 + 1);
    if (!result) return NULL;
    for (size_t i = 0; i < length; i++) snprintf(result + i * 2, 3, "%02x", data[i]);
    return result;
}

static bool handle(int fd, char **fsid, int *kind, char **opaque) {
    struct statfs filesystem;
    union { max_align_t alignment; unsigned char bytes[sizeof(struct file_handle) + 128]; } storage = {0};
    struct file_handle *identity = (struct file_handle *)storage.bytes;
    identity->handle_bytes = 128;
    int mount;
    if (fstatfs(fd, &filesystem) || name_to_handle_at(fd, "", identity, &mount, AT_EMPTY_PATH)
        || !identity->handle_bytes || identity->handle_bytes > 128) return false;
    *fsid = hex((const unsigned char *)&filesystem.f_fsid, sizeof(filesystem.f_fsid));
    *opaque = hex(identity->f_handle, identity->handle_bytes);
    *kind = identity->handle_type;
    return *fsid && *opaque;
}

static bool same_path(int fd, const char *relative) {
    struct stat pinned, current;
    int again = beneath(relative, O_PATH | O_DIRECTORY);
    bool ok = again >= 0 && !fstat(fd, &pinned) && !fstat(again, &current)
        && pinned.st_dev == current.st_dev && pinned.st_ino == current.st_ino;
    if (again >= 0) close(again);
    return ok;
}

static bool emit_item(const char *relative, unsigned kind) {
    if (++entries > MAX_ENTRIES || strlen(relative) >= 4096) return false;
    g_autofree char *path = g_base64_encode((const guchar *)relative, strlen(relative));
    if (kind == 1) {
        printf("{\"status\":\"item\",\"kind\":1,\"path_b64\":\"%s\"}\n", path);
        return true;
    }
    if (++directories > MAX_DIRECTORIES) return false;
    int fd = beneath(relative, O_PATH | O_DIRECTORY);
    if (fd < 0) return false;
    g_autofree char *fsid = NULL, *opaque = NULL;
    int handle_kind;
    bool ok = handle(fd, &fsid, &handle_kind, &opaque) && same_path(fd, relative);
    close(fd);
    if (ok) printf("{\"status\":\"item\",\"kind\":2,\"path_b64\":\"%s\",\"fsid\":\"%s\",\"handle_kind\":%d,\"handle\":\"%s\"}\n", path, fsid, handle_kind, opaque);
    return ok;
}

static bool inventory(const char *relative, unsigned depth) {
    if (depth > 64) return false;
    int fd = beneath(relative, O_RDONLY | O_DIRECTORY);
    if (fd < 0) return false;
    DIR *stream = fdopendir(fd);
    if (!stream) { close(fd); return false; }
    bool ok = true;
    for (;;) {
        if (!same_path(dirfd(stream), relative)) { ok = false; break; }
        errno = 0;
        struct dirent *entry = readdir(stream);
        if (!entry) { if (errno) ok = false; break; }
        if (!same_path(dirfd(stream), relative)) { ok = false; break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        char child[4096];
        int length = snprintf(child, sizeof(child), "%s%s%s", relative, *relative ? "/" : "", entry->d_name);
        if (length < 0 || (size_t)length >= sizeof(child)) { ok = false; break; }
        /* Always resolve from root; directory descriptors may have moved. */
        int item = beneath(child, O_PATH);
        if (item < 0) {
            if (errno == ELOOP || errno == EXDEV || errno == EACCES || errno == EPERM) continue;
            ok = false; break;
        }
        struct stat metadata;
        bool stat_ok = fstat(item, &metadata) == 0;
        close(item);
        if (!stat_ok) { ok = false; break; }
        unsigned kind = S_ISDIR(metadata.st_mode) ? 2 : S_ISREG(metadata.st_mode) ? 1 : 0;
        if (kind && !emit_item(child, kind)) { ok = false; break; }
        if (kind == 2 && !inventory(child, depth + 1)) { ok = false; break; }
    }
    closedir(stream);
    return ok;
}

static char *relative_path(const char *encoded) {
    if (!strcmp(encoded, "-")) return g_strdup("");
    gsize length;
    g_autofree guchar *bytes = g_base64_decode(encoded, &length);
    if (length >= 4096 || memchr(bytes, 0, length) || (length && bytes[0] == '/')) return NULL;
    g_autofree char *canonical = g_base64_encode(bytes, length);
    if (strcmp(canonical, encoded)) return NULL;
    char *path = g_strndup((char *)bytes, length);
    g_auto(GStrv) parts = g_strsplit(path, "/", -1);
    for (unsigned i = 0; parts[i]; i++) {
        if (!strcmp(parts[i], ".") || !strcmp(parts[i], "..")) { g_free(path); return NULL; }
    }
    return path;
}

int main(int argc, char **argv) {
    if (argc != 3 || strcmp(argv[1], "--root") || *argv[2] != '/') return 2;
    struct rlimit memory = {128u * 1024u * 1024u, 128u * 1024u * 1024u}, core = {0, 0};
    pid_t parent = getppid();
    if (setrlimit(RLIMIT_AS, &memory) || setrlimit(RLIMIT_CORE, &core)
        || prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != parent) return 3;
    struct __user_cap_header_struct cap_header = {.version = _LINUX_CAPABILITY_VERSION_3};
    struct __user_cap_data_struct caps[2] = {{0}};
    if (geteuid() == 0 || syscall(SYS_capget, &cap_header, caps) || caps[0].effective || caps[1].effective) return 3;
    char gate;
    if (read(STDIN_FILENO, &gate, 1) != 1 || gate != 'G') return 3;
    struct open_how initial = {.flags = O_PATH | O_DIRECTORY | O_CLOEXEC, .resolve = RESOLVE_NO_SYMLINKS};
    root = syscall(SYS_openat2, AT_FDCWD, argv[2], &initial, sizeof(initial));
    root_path = argv[2];
    if (root < 0 || fstat(root, &root_identity) || !mount_identity(root, &root_mount) || !confine()) return 3;
    setvbuf(stdout, NULL, _IOLBF, 0);
    struct stat root_info;
    if (fstat(root, &root_info)) return 3;
    printf("{\"status\":\"ready\",\"root_device\":%llu,\"root_inode\":%llu,\"root_mount\":%llu}\n", (unsigned long long)root_info.st_dev, (unsigned long long)root_info.st_ino, root_mount);
    char request[8192];
    while (fgets(request, sizeof(request), stdin)) {
        char *newline = strchr(request, '\n');
        if (!newline) return 4;
        *newline = 0;
        g_auto(GStrv) fields = g_strsplit(request, " ", -1);
        unsigned count = g_strv_length(fields);
        if (count < 2) return 4;
        g_autofree char *relative = relative_path(fields[1]);
        if (!relative) return 4;
        if (!strcmp(fields[0], "I") && count == 2) {
            entries = directories = 0;
            if (!emit_item(relative, 2) || !inventory(relative, 0)) {
                puts("{\"status\":\"gap\",\"reason\":\"inventory_failed\"}"); return 4;
            }
            puts("{\"status\":\"inventory_done\"}");
        }
        else if (!strcmp(fields[0], "V") && count == 5) {
            int fd = beneath(relative, O_PATH | O_DIRECTORY);
            g_autofree char *fsid = NULL, *opaque = NULL;
            char *end; errno = 0;
            long expected_kind = strtol(fields[3], &end, 10);
            int actual_kind;
            bool ok = !errno && !*end && fd >= 0 && handle(fd, &fsid, &actual_kind, &opaque)
                && actual_kind == expected_kind && !strcmp(fsid, fields[2]) && !strcmp(opaque, fields[4]) && same_path(fd, relative);
            if (fd >= 0) close(fd);
            puts(ok ? "{\"status\":\"admitted\"}" : "{\"status\":\"gap\",\"reason\":\"parent_identity_changed\"}");
            if (!ok) return 4;
        }
        else return 4;
    }
    close(root);
    return ferror(stdin) ? 4 : 0;
}
