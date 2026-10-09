/* Bounded, single-generation explicit-root watcher. GPL-2.0-or-later. */
#define _GNU_SOURCE
#include <dirent.h>
#include <glib.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/landlock.h>
#include <linux/openat2.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <sys/inotify.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#define ENTRY_LIMIT 10000000u
#define WATCH_LIMIT 800000u
static unsigned entries, watches;
static int notifications, root_watch;
static bool events_mode;
typedef struct { dev_t device; ino_t inode; char relative[]; } WatchInfo;
static GHashTable *watch_paths;
static uint64_t event_sequence;


static int failure(const char *code) {
    printf("{\"schema_version\":1,\"status\":\"error\",\"error\":{\"code\":\"%s\"}}\n", code);
    return 3;
}
static int beneath(int parent, const char *name, int flags) {
    struct open_how how = {.flags = flags | O_CLOEXEC,
        .resolve = RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_XDEV};
    return syscall(SYS_openat2, parent, name, &how, sizeof(how));
}
static bool confine(int root) {
    struct landlock_ruleset_attr rules = {.handled_access_fs = (1ULL << 15) - 1};
    int fd = syscall(SYS_landlock_create_ruleset, &rules, sizeof(rules), 0);
    if (fd < 0) return false;
    struct landlock_path_beneath_attr read = {.parent_fd = root,
        .allowed_access = LANDLOCK_ACCESS_FS_READ_DIR};
    bool ok = !syscall(SYS_landlock_add_rule, fd, LANDLOCK_RULE_PATH_BENEATH, &read, 0)
           && !prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
           && !syscall(SYS_landlock_restrict_self, fd, 0);
    close(fd);
    return ok;
}
static bool watch_tree(int fd, unsigned depth, int root, const char *relative) {
    if (depth > 64 || watches >= WATCH_LIMIT) { close(fd); return false; }
    /* Resolve the pinned descriptor, never a mutable child pathname. */
    char path[64];
    snprintf(path, sizeof(path), "/proc/self/fd/%d", fd);
    int watch = inotify_add_watch(notifications, path,
        IN_ONLYDIR | IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO
        | IN_DELETE_SELF | IN_MOVE_SELF | IN_ATTRIB | IN_UNMOUNT);
    if (watch < 0) { close(fd); return false; }
    watches++;
    if(events_mode) {
        struct stat pinned;
        if(fstat(fd,&pinned)){close(fd);return false;}
        WatchInfo *info=g_try_malloc(sizeof(*info)+strlen(relative)+1);
        if(!info){close(fd);return false;}
        info->device=pinned.st_dev;info->inode=pinned.st_ino;strcpy(info->relative,relative);
        g_hash_table_insert(watch_paths,GINT_TO_POINTER(watch),info);
    }
    if (!depth) root_watch = watch;
    DIR *directory = fdopendir(fd);
    if (!directory) { close(fd); return false; }
    bool ok = true;
    for (;;) {
        errno = 0;
        struct dirent *item = readdir(directory);
        if (!item) { if (errno) ok = false; break; }
        if (!strcmp(item->d_name, ".") || !strcmp(item->d_name, "..")) continue;
        if (++entries > ENTRY_LIMIT) { ok = false; break; }
        char child_path[4096];
        int length = snprintf(child_path, sizeof(child_path), "%s%s%s", relative,
                              relative[0] ? "/" : "", item->d_name);
        if (length < 0 || (size_t)length >= sizeof(child_path)) { ok = false; break; }
        // A pinned parent can be moved outside the root. Re-resolve every child
        // from the approved root, rather than treating that parent as authority.
        int child = beneath(root, child_path, O_PATH);
        if (child < 0) {
            if (errno == ELOOP || errno == EXDEV || errno == EACCES || errno == EPERM) continue;
            ok = false; break;
        }
        struct stat info;
        if (fstat(child, &info)) { close(child); ok = false; break; }
        int contents = S_ISDIR(info.st_mode) ? beneath(root, child_path, O_RDONLY | O_DIRECTORY) : -1;
        bool directory_entry = S_ISDIR(info.st_mode);
        close(child);
        if (directory_entry) {
            if (contents < 0 && (errno == EACCES || errno == EPERM)) continue;
            struct stat pinned;
            if (contents < 0 || fstat(contents, &pinned)
                || pinned.st_dev != info.st_dev || pinned.st_ino != info.st_ino) {
                if (contents >= 0) close(contents);
                ok = false; break;
            }
            if (!watch_tree(contents, depth + 1, root, child_path)) { ok = false; break; }
        }
    }
    closedir(directory);
    return ok;
}
static int event_gap(const char *reason) {
    printf("{\"schema_version\":1,\"status\":\"gap\",\"reason\":\"%s\",\"sequence\":%llu}\n",reason,(unsigned long long)event_sequence);
    return 4;
}
static int continuous_events(int root) {
    union { struct inotify_event alignment; char bytes[65536]; } buffer;
    for(;;) {
        ssize_t count;
        do {count=read(notifications,buffer.bytes,sizeof(buffer.bytes));}while(count<0&&errno==EINTR);
        if(count<=0)return event_gap("watch_failed");
        for(size_t offset=0;offset<(size_t)count;) {
            if((size_t)count-offset<sizeof(struct inotify_event))return event_gap("event_frame");
            struct inotify_event *event=(struct inotify_event*)(buffer.bytes+offset);
            if(event->len>(size_t)count-offset-sizeof(*event))return event_gap("event_frame");
            offset+=sizeof(*event)+event->len;
            if(event->mask&IN_Q_OVERFLOW)return event_gap("overflow");
            if(event->wd==root_watch&&(event->mask&(IN_MOVE_SELF|IN_DELETE_SELF|IN_UNMOUNT|IN_IGNORED)))return event_gap("root_offline");
            /* Directory topology changes require a contained reconciliation.
             * Stop and release all watches before any possibly moved child is
             * probed. The updater must not claim freshness across this gap. */
            if(event->mask&(IN_ISDIR|IN_MOVE_SELF|IN_DELETE_SELF|IN_UNMOUNT|IN_IGNORED))return event_gap("directory_topology");
            if(!(event->mask&(IN_CREATE|IN_DELETE|IN_MOVED_FROM|IN_MOVED_TO)))continue;
            WatchInfo *parent=g_hash_table_lookup(watch_paths,GINT_TO_POINTER(event->wd));
            if(!parent||!event->len||!memchr(event->name,0,event->len)||strchr(event->name,'/'))return event_gap("event_identity");
            /* Re-resolve parent from the admitted root, never from its possibly
             * relocated watch descriptor, and verify the watched identity. */
            int parent_fd=beneath(root,*parent->relative?parent->relative:".",O_PATH|O_DIRECTORY);
            struct stat info;
            bool valid=parent_fd>=0&&!fstat(parent_fd,&info)&&info.st_dev==parent->device&&info.st_ino==parent->inode;
            if(parent_fd>=0)close(parent_fd);
            if(!valid)return event_gap("parent_relocated");
            if(event->mask&(IN_CREATE|IN_MOVED_TO)) {
                char relative[4096];int n=snprintf(relative,sizeof(relative),"%s%s%s",parent->relative,*parent->relative?"/":"",event->name);
                if(n<0||(size_t)n>=sizeof(relative))return event_gap("path_limit");
                int child=beneath(root,relative,O_PATH);
                if(child<0) {
                    if(errno==ELOOP||errno==EXDEV)continue;
                    return event_gap("mutation_race");
                }
                bool eligible=!fstat(child,&info)&&S_ISREG(info.st_mode);close(child);
                if(!eligible)continue;
            }
            g_autofree char *parent_b64=g_base64_encode((const guchar*)parent->relative,strlen(parent->relative));
            g_autofree char *name_b64=g_base64_encode((const guchar*)event->name,strlen(event->name));
            if(event_sequence==UINT64_MAX)return event_gap("sequence_limit");
            printf("{\"schema_version\":1,\"status\":\"event\",\"sequence\":%llu,\"mask\":%u,\"cookie\":%u,\"parent_b64\":\"%s\",\"name_b64\":\"%s\",\"kind\":1,\"observed_monotonic_us\":%lld}\n",(unsigned long long)++event_sequence,event->mask,event->cookie,parent_b64,name_b64,(long long)g_get_monotonic_time());
        }
    }
}
int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    events_mode=argc==4&&!strcmp(argv[3],"--events");
    if ((argc != 3&&!events_mode) || strcmp(argv[1], "--root") || argv[2][0] != '/') return failure("invalid_request");
    if(events_mode)watch_paths=g_hash_table_new_full(g_direct_hash,g_direct_equal,NULL,g_free);
    pid_t parent = getppid();
    if (prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != parent) return failure("parent_changed");
    char gate;
    if (read(STDIN_FILENO, &gate, 1) != 1 || gate != 'G') return failure("admission_denied");
    struct rlimit memory = {256u * 1024u * 1024u, 256u * 1024u * 1024u}, core = {0, 0};
    if (setrlimit(RLIMIT_AS, &memory) || setrlimit(RLIMIT_CORE, &core)) return failure("resource_limit");
    if (syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION) < 3)
        return failure("confinement_unavailable");
    struct open_how how = {.flags = O_PATH | O_DIRECTORY | O_CLOEXEC, .resolve = RESOLVE_NO_SYMLINKS};
    int root = syscall(SYS_openat2, AT_FDCWD, argv[2], &how, sizeof(how));
    if (root < 0) return failure("root_unavailable");
    struct stat info;
    if (fstat(root, &info) || !confine(root)) { close(root); return failure("confinement_failed"); }
    notifications = inotify_init1(IN_CLOEXEC);
    int contents = beneath(root, ".", O_RDONLY | O_DIRECTORY);
    if (notifications < 0 || contents < 0) {
        close(root);
        if (contents >= 0) close(contents);
        if (notifications >= 0) close(notifications);
        return failure("watch_unavailable");
    }
    bool complete = watch_tree(contents, 0, root, "");
    if(!events_mode)close(root);
    if (!complete) { close(notifications); return failure("coverage_incomplete"); }
    printf("{\"schema_version\":1,\"status\":\"ready\",\"watches\":%u,\"root_device\":%llu,\"root_inode\":%llu}\n",
        watches, (unsigned long long)info.st_dev, (unsigned long long)info.st_ino);
    if(events_mode) {
        printf("{\"schema_version\":1,\"status\":\"coverage\",\"reconciliation_required\":true,\"reason\":\"startup_gap\"}\n");
        int result=continuous_events(root);close(notifications);close(root);g_hash_table_unref(watch_paths);return result;
    }
    union { struct inotify_event alignment; char bytes[65536]; } buffer;
    ssize_t count;
    do { count = read(notifications, buffer.bytes, sizeof(buffer.bytes)); } while (count < 0 && errno == EINTR);
    if (count <= 0) { close(notifications); return failure("watch_failed"); }
    const char *status = "dirty";
    for (size_t offset = 0; offset + sizeof(struct inotify_event) <= (size_t)count;) {
        struct inotify_event *event = (struct inotify_event *)(buffer.bytes + offset);
        if (event->len > (size_t)count - offset - sizeof(*event)) {
            close(notifications); return failure("worker_protocol_failed");
        }
        if (event->mask & IN_Q_OVERFLOW) status = "overflow";
        else if (!strcmp(status, "dirty") && event->wd == root_watch
                 && (event->mask & (IN_MOVE_SELF | IN_DELETE_SELF | IN_UNMOUNT | IN_IGNORED))) status = "offline";
        offset += sizeof(*event) + event->len;
    }
    close(notifications); /* Release every watch, including moved directories. */
    printf("{\"schema_version\":1,\"status\":\"%s\"}\n", status);
    return 0;
}
