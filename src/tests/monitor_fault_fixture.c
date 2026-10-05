#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/inotify.h>
#include <unistd.h>

static int watched_fd = -1;
int inotify_init1(int flags) {
    int (*real_init)(int) = dlsym(RTLD_NEXT, "inotify_init1");
    watched_fd = real_init(flags);
    return watched_fd;
}
int inotify_add_watch(int fd, const char *path, unsigned mask) {
    if (getenv("FSEARCH_MONITOR_FIXTURE_WATCH_FAILURE")) { errno = ENOSPC; return -1; }
    int (*real_add)(int, const char *, unsigned) = dlsym(RTLD_NEXT, "inotify_add_watch");
    return real_add(fd, path, mask);
}
ssize_t read(int fd, void *buffer, size_t count) {
    if (fd == watched_fd && getenv("FSEARCH_MONITOR_FIXTURE_OVERFLOW") && count >= sizeof(struct inotify_event)) {
        struct inotify_event event = {.wd = -1, .mask = IN_Q_OVERFLOW};
        memcpy(buffer, &event, sizeof(event));
        return sizeof(event);
    }
    ssize_t (*real_read)(int, void *, size_t) = dlsym(RTLD_NEXT, "read");
    return real_read(fd, buffer, count);
}
