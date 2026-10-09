/* Bounded, single-generation explicit-root watcher. GPL-2.0-or-later. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <dirent.h>
#include <glib.h>
#include <poll.h>
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
static GHashTable *watch_paths, *expected_ignored, *pending_directories;
typedef struct { int watch; dev_t device; ino_t inode; gint64 deadline; } PendingDirectory;
static bool inventory_mode;
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
static bool emit_event(const char *parent,const char *name,unsigned kind,unsigned mask,unsigned cookie) {
    if(event_sequence==UINT64_MAX)return false;
    g_autofree char *parent_b64=g_base64_encode((const guchar*)parent,strlen(parent));
    g_autofree char *name_b64=g_base64_encode((const guchar*)name,strlen(name));
    printf("{\"schema_version\":1,\"status\":\"event\",\"sequence\":%llu,\"mask\":%u,\"cookie\":%u,\"parent_b64\":\"%s\",\"name_b64\":\"%s\",\"kind\":%u,\"observed_monotonic_us\":%lld}\n",(unsigned long long)++event_sequence,mask,cookie,parent_b64,name_b64,kind,(long long)g_get_monotonic_time());
    return true;
}
static void emit_inventory(const char *phase) {
    printf("{\"schema_version\":1,\"status\":\"inventory\",\"phase\":\"%s\",\"sequence\":%llu,\"observed_monotonic_us\":%lld}\n",phase,(unsigned long long)event_sequence,(long long)g_get_monotonic_time());
}
static void emit_progress(const char *status) {
    printf("{\"schema_version\":1,\"status\":\"%s\",\"sequence\":%llu,\"observed_monotonic_us\":%lld}\n",status,(unsigned long long)event_sequence,(long long)g_get_monotonic_time());
}
static bool prefix_contains(const char *prefix,const char *path) {
    size_t n=strlen(prefix);return !strncmp(prefix,path,n)&&(!path[n]||path[n]=='/');
}
static void remove_subtree(const char *prefix) {
    GHashTableIter iter;gpointer key,value;g_hash_table_iter_init(&iter,watch_paths);
    while(g_hash_table_iter_next(&iter,&key,&value)) {
        WatchInfo *info=value;
        if(prefix_contains(prefix,info->relative)) {
            g_hash_table_add(expected_ignored,key);inotify_rm_watch(notifications,GPOINTER_TO_INT(key));
            g_hash_table_iter_remove(&iter);watches--;
        }
    }
}
static int find_watch(const char *relative) {
    GHashTableIter iter;gpointer key,value;g_hash_table_iter_init(&iter,watch_paths);
    while(g_hash_table_iter_next(&iter,&key,&value))if(!strcmp(((WatchInfo*)value)->relative,relative))return GPOINTER_TO_INT(key);
    return -1;
}
static bool rename_watches(const char *old,const char *replacement) {
    size_t old_length=strlen(old);GHashTableIter iter;gpointer key,value;g_hash_table_iter_init(&iter,watch_paths);
    while(g_hash_table_iter_next(&iter,&key,&value)) {
        WatchInfo *info=value;if(!prefix_contains(old,info->relative))continue;
        size_t length=strlen(replacement)+strlen(info->relative+old_length);
        if(length>=4096)return false;
        WatchInfo *next=g_try_malloc(sizeof(*next)+length+1);if(!next)return false;
        next->device=info->device;next->inode=info->inode;
        strcpy(next->relative,replacement);strcat(next->relative,info->relative+old_length);
        g_hash_table_iter_replace(&iter,next);
    }
    return true;
}
static bool pending_subtree(const char *relative) {
    GHashTableIter iter;gpointer value;g_hash_table_iter_init(&iter,pending_directories);
    while(g_hash_table_iter_next(&iter,NULL,&value)) {
        PendingDirectory *pending=value;WatchInfo *info=g_hash_table_lookup(watch_paths,GINT_TO_POINTER(pending->watch));
        if(info&&prefix_contains(info->relative,relative))return true;
    }
    return false;
}
static void expire_directory_moves(void) {
    GHashTableIter iter;gpointer value;g_hash_table_iter_init(&iter,pending_directories);gint64 now=g_get_monotonic_time();
    while(g_hash_table_iter_next(&iter,NULL,&value)) {
        PendingDirectory *pending=value;if(now<pending->deadline)continue;
        WatchInfo *info=g_hash_table_lookup(watch_paths,GINT_TO_POINTER(pending->watch));
        if(info){g_autofree char *relative=g_strdup(info->relative);remove_subtree(relative);}
        g_hash_table_iter_remove(&iter);
    }
}
static bool watch_tree(int fd, unsigned depth, int root, const char *relative) {
    if (depth > 64 || watches >= WATCH_LIMIT || (events_mode&&watches+g_hash_table_size(expected_ignored)>=WATCH_LIMIT)) { close(fd); return false; }
    /* Resolve the pinned descriptor, never a mutable child pathname. */
    char path[64];
    snprintf(path, sizeof(path), "/proc/self/fd/%d", fd);
    int watch = inotify_add_watch(notifications, path,
        IN_ONLYDIR | IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO
        | IN_DELETE_SELF | IN_MOVE_SELF | IN_ATTRIB | IN_UNMOUNT);
    if (watch < 0) { close(fd); return false; }
    bool existing=events_mode&&g_hash_table_contains(watch_paths,GINT_TO_POINTER(watch));
    if(existing&&!inventory_mode){close(fd);return true;}
    if(!existing)watches++;
    if(events_mode&&!existing) {
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
        if(inventory_mode&&(directory_entry||S_ISREG(info.st_mode))) {
            if(!emit_event(relative,item->d_name,directory_entry?2:1,IN_CREATE,0)) {ok=false;break;}
        }
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
    gint64 next_heartbeat=g_get_monotonic_time()+500000;bool barrier_pending=false;
    for(;;) {
        struct pollfd waiting[2]={{.fd=notifications,.events=POLLIN},{.fd=STDIN_FILENO,.events=POLLIN}};
        int timeout=barrier_pending?0:(g_hash_table_size(pending_directories)?20:500);
        int ready;do{ready=poll(waiting,2,timeout);}while(ready<0&&errno==EINTR);
        if(ready<0)return event_gap("watch_failed");
        if(waiting[1].revents) {
            char command;if(read(STDIN_FILENO,&command,1)!=1||command!='B')return event_gap("control_failed");
            barrier_pending=true;
        }
        if(!waiting[0].revents) {
            if(barrier_pending) {
                /* The control byte may arrive after poll examined inotify.
                 * Recheck after reading it before choosing the drain cut. */
                struct pollfd verify={.fd=notifications,.events=POLLIN};
                int queued;do{queued=poll(&verify,1,0);}while(queued<0&&errno==EINTR);
                if(queued<0)return event_gap("watch_failed");
                if(queued)continue;
            }
            expire_directory_moves();gint64 now=g_get_monotonic_time();
            /* Acknowledge only after all already queued inotify records have
             * been processed. New mutations after this cut remain sequenced. */
            if(barrier_pending){emit_progress("barrier");barrier_pending=false;}
            if(now>=next_heartbeat){emit_progress("heartbeat");next_heartbeat=now+500000;}
            continue;
        }
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
            if(g_hash_table_contains(expected_ignored,GINT_TO_POINTER(event->wd))) {
                if(event->mask&IN_IGNORED)g_hash_table_remove(expected_ignored,GINT_TO_POINTER(event->wd));
                continue;
            }
            WatchInfo *watched=g_hash_table_lookup(watch_paths,GINT_TO_POINTER(event->wd));
            if(watched&&pending_subtree(watched->relative)) {
                /* Until a move cookie resolves, this watch may be outside the
                 * admitted root. Never probe/export its names or silently lose
                 * a mutation that could belong to an internal rename. */
                if(event->mask&(IN_CREATE|IN_DELETE|IN_MOVED_FROM|IN_MOVED_TO|IN_ATTRIB|IN_UNMOUNT|IN_IGNORED))return event_gap("directory_move_concurrent");
                continue;
            }
            if(event->mask&IN_MOVE_SELF) {
                if(!watched)return event_gap("event_identity");
                int current=beneath(root,*watched->relative?watched->relative:".",O_PATH|O_DIRECTORY);struct stat identity;
                bool valid=current>=0&&!fstat(current,&identity)&&identity.st_dev==watched->device&&identity.st_ino==watched->inode;
                if(current>=0)close(current);
                if(!valid)return event_gap("parent_relocated");
                continue;
            }
            if(event->mask&(IN_UNMOUNT|IN_IGNORED))return event_gap("directory_topology");
            if(event->mask&IN_DELETE_SELF) {
                WatchInfo *removed=g_hash_table_lookup(watch_paths,GINT_TO_POINTER(event->wd));
                if(!removed)return event_gap("event_identity");
                g_autofree char *relative=g_strdup(removed->relative),*parent=g_strdup(relative);
                char *slash=strrchr(parent,'/');const char *name=slash?slash+1:relative;if(slash)*slash=0;else *parent=0;
                if(!emit_event(parent,name,2,IN_DELETE,0))return event_gap("sequence_limit");
                remove_subtree(relative);continue;
            }
            if((event->mask&IN_ISDIR)&&(event->mask&IN_ATTRIB))return event_gap("directory_topology");
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
            char relative[4096];int n=snprintf(relative,sizeof(relative),"%s%s%s",parent->relative,*parent->relative?"/":"",event->name);
            if(n<0||(size_t)n>=sizeof(relative))return event_gap("path_limit");
            unsigned kind=(event->mask&IN_ISDIR)?2:1;
            bool paired_directory=false;
            if(kind==2&&(event->mask&IN_MOVED_FROM)) {
                int moved=find_watch(relative);WatchInfo *info=g_hash_table_lookup(watch_paths,GINT_TO_POINTER(moved));
                if(!info||!event->cookie||g_hash_table_size(pending_directories)>=128||g_hash_table_contains(pending_directories,GUINT_TO_POINTER(event->cookie)))return event_gap("directory_move_budget");
                PendingDirectory *pending=g_try_malloc(sizeof(*pending));if(!pending)return event_gap("memory_budget");
                *pending=(PendingDirectory){moved,info->device,info->inode,g_get_monotonic_time()+100000};
                g_hash_table_insert(pending_directories,GUINT_TO_POINTER(event->cookie),pending);
            }
            if(event->mask&(IN_CREATE|IN_MOVED_TO)) {
                n=snprintf(relative,sizeof(relative),"%s%s%s",parent->relative,*parent->relative?"/":"",event->name);
                if(n<0||(size_t)n>=sizeof(relative))return event_gap("path_limit");
                int child=beneath(root,relative,O_PATH);
                if(child<0) {
                    if(errno==ELOOP||errno==EXDEV)continue;
                    return event_gap("mutation_race");
                }
                bool eligible=!fstat(child,&info)&&(S_ISREG(info.st_mode)||S_ISDIR(info.st_mode));close(child);
                if(eligible)kind=S_ISDIR(info.st_mode)?2:1;
                if(!eligible)continue;
                if(kind!=((event->mask&IN_ISDIR)?2u:1u))return event_gap("mutation_type_race");
                if(kind==2&&(event->mask&IN_MOVED_TO)) {
                    PendingDirectory *pending=g_hash_table_lookup(pending_directories,GUINT_TO_POINTER(event->cookie));
                    if(pending) {
                        WatchInfo *old=g_hash_table_lookup(watch_paths,GINT_TO_POINTER(pending->watch));
                        if(!old||info.st_dev!=pending->device||info.st_ino!=pending->inode)return event_gap("directory_move_identity");
                        g_autofree char *previous=g_strdup(old->relative);
                        int victim=find_watch(relative);
                        if(victim>=0&&victim!=pending->watch)remove_subtree(relative);
                        if(!rename_watches(previous,relative))return event_gap("directory_move_budget");
                        g_hash_table_remove(pending_directories,GUINT_TO_POINTER(event->cookie));paired_directory=true;
                    }
                }
            }
            if(!emit_event(parent->relative,event->name,kind,event->mask,event->cookie))return event_gap("sequence_limit");
            if(kind==2&&(event->mask&IN_DELETE))remove_subtree(relative);
            if(kind==2&&!paired_directory&&(event->mask&(IN_CREATE|IN_MOVED_TO))) {
                int contents=beneath(root,relative,O_RDONLY|O_DIRECTORY);
                if(contents<0)return event_gap("directory_unavailable");
                unsigned depth=1;for(const char*p=relative;*p;p++)if(*p=='/')depth++;
                emit_inventory("begin");
                inventory_mode=true;entries=0;bool complete=watch_tree(contents,depth,root,relative);inventory_mode=false;
                if(!complete)return event_gap("subtree_incomplete");
                emit_inventory("end");
            }
        }
        expire_directory_moves();
    }
}
int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    events_mode=argc==4&&!strcmp(argv[3],"--events");
    if ((argc != 3&&!events_mode) || strcmp(argv[1], "--root") || argv[2][0] != '/') return failure("invalid_request");
    if(events_mode){watch_paths=g_hash_table_new_full(g_direct_hash,g_direct_equal,NULL,g_free);expected_ignored=g_hash_table_new(g_direct_hash,g_direct_equal);pending_directories=g_hash_table_new_full(g_direct_hash,g_direct_equal,NULL,g_free);}
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
        int result=continuous_events(root);close(notifications);close(root);g_hash_table_unref(watch_paths);g_hash_table_unref(expected_ignored);g_hash_table_unref(pending_directories);return result;
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
