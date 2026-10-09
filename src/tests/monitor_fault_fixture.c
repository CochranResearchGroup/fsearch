#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <poll.h>
#include <stdlib.h>
#include <string.h>
#include <sys/inotify.h>
#include <unistd.h>

static int watched_fd = -1, root_watch=-1, nested_watch=-1;
static int injected;
int inotify_init1(int flags) {
    int (*real_init)(int) = dlsym(RTLD_NEXT, "inotify_init1");
    watched_fd = real_init(flags);
    return watched_fd;
}
int inotify_add_watch(int fd, const char *path, unsigned mask) {
    if (getenv("FSEARCH_MONITOR_FIXTURE_WATCH_FAILURE")) { errno = ENOSPC; return -1; }
    int (*real_add)(int, const char *, unsigned) = dlsym(RTLD_NEXT, "inotify_add_watch");
    int watch=real_add(fd, path, mask);
    if(watch>=0){if(root_watch<0)root_watch=watch;else if(nested_watch<0)nested_watch=watch;}
    return watch;
}
ssize_t read(int fd, void *buffer, size_t count) {
    if (fd == watched_fd && getenv("FSEARCH_MONITOR_FIXTURE_OVERFLOW") && count >= sizeof(struct inotify_event)) {
        struct inotify_event event = {.wd = -1, .mask = IN_Q_OVERFLOW};
        memcpy(buffer, &event, sizeof(event));
        return sizeof(event);
    }
    if(fd==watched_fd&&!injected&&getenv("FSEARCH_MONITOR_FIXTURE_MOVE_CHILD")&&root_watch>=0&&nested_watch>=0&&count>=2*(sizeof(struct inotify_event)+32)) {
        injected=1;
        struct inotify_event from={.wd=root_watch,.mask=IN_MOVED_FROM|IN_ISDIR,.cookie=123,.len=32};
        struct inotify_event child={.wd=nested_watch,.mask=IN_CREATE,.len=32};
        memset(buffer,0,2*(sizeof(from)+32));memcpy(buffer,&from,sizeof(from));strcpy((char*)buffer+sizeof(from),"nested");
        size_t offset=sizeof(from)+32;memcpy((char*)buffer+offset,&child,sizeof(child));strcpy((char*)buffer+offset+sizeof(child),"must-not-disappear.txt");
        return 2*(sizeof(from)+32);
    }
    ssize_t (*real_read)(int, void *, size_t) = dlsym(RTLD_NEXT, "read");
    return real_read(fd, buffer, count);
}

int poll(struct pollfd *fds,nfds_t count,int timeout) {
    if(count>=1&&fds[0].fd==watched_fd&&(getenv("FSEARCH_MONITOR_FIXTURE_OVERFLOW")||(!injected&&getenv("FSEARCH_MONITOR_FIXTURE_MOVE_CHILD")))) {
        fds[0].revents=POLLIN;return 1;
    }
    int (*real_poll)(struct pollfd*,nfds_t,int)=dlsym(RTLD_NEXT,"poll");
    return real_poll(fds,count,timeout);
}
