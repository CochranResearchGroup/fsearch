/* Linux-only fault fixture; injected into the snapshot worker, never production. */
#undef _FILE_OFFSET_BITS
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static bool triggered;
static bool is_snapshot(const char *path) {
    size_t len = strlen(path);
    return (len >= 12 && !strcmp(path + len - 12, "/snapshot.db")) ||
           (len >= 13 && !strcmp(path + len - 13, "/candidate.db"));
}
static void pause_fixture(const char *delay_key) {
    const char *delay = getenv(delay_key);
    if (!delay || triggered) return;
    triggered = true;
    const char *marker = getenv("FSEARCH_FIXTURE_MARKER");
    if (marker) {
        FILE *fp = fopen(marker, "w");
        if (fp) { fprintf(fp, "%d", getpid()); fclose(fp); }
    }
    long ms = strtol(delay, NULL, 10);
    struct timespec interval = {.tv_sec = ms / 1000, .tv_nsec = (ms % 1000) * 1000000};
    while (nanosleep(&interval, &interval) < 0 && errno == EINTR) {}
}
static int fixture_open(const char *symbol, const char *path, int flags, mode_t mode) {
    int (*real_open)(const char *, int, ...) = dlsym(RTLD_NEXT, symbol);
    if (is_snapshot(path)) {
        pause_fixture("FSEARCH_FIXTURE_OPEN_DELAY_MS");
        const char *memory_marker = getenv("FSEARCH_FIXTURE_MEMORY_MARKER");
        if (memory_marker) {
            void *allocation = malloc(600ul * 1024 * 1024);
            FILE *fp = fopen(memory_marker, "w");
            if (fp) { fputs(allocation ? "allowed" : "denied", fp); fclose(fp); }
            free(allocation);
        }
    }
    int fd = real_open(path, flags, mode);
    const char *replacement = getenv("FSEARCH_FIXTURE_REPLACE_WITH");
    if (fd >= 0 && is_snapshot(path) && replacement) rename(replacement, path);
    return fd;
}
int open(const char *path, int flags, ...) {
    mode_t mode = 0;
    if (flags & O_CREAT) { va_list args; va_start(args, flags); mode = va_arg(args, int); va_end(args); }
    return fixture_open("open", path, flags, mode);
}
int open64(const char *path, int flags, ...) {
    mode_t mode = 0;
    if (flags & O_CREAT) { va_list args; va_start(args, flags); mode = va_arg(args, int); va_end(args); }
    return fixture_open("open64", path, flags, mode);
}
int close(int fd) {
    int (*real_close)(int) = dlsym(RTLD_NEXT, "close");
    char link[64], path[4096];
    snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
    ssize_t size = readlink(link, path, sizeof(path) - 1);
    if (size >= 0) {
        path[size] = 0;
        if (is_snapshot(path)) pause_fixture("FSEARCH_FIXTURE_AFTER_LOAD_DELAY_MS");
    }
    return real_close(fd);
}

/* Supervisor fault: make nonblocking reap evidence unavailable, not a real kernel stall. */
#include <sys/wait.h>
pid_t waitpid(pid_t pid, int *status, int options) {
    pid_t (*real_waitpid)(pid_t, int *, int) = dlsym(RTLD_NEXT, "waitpid");
    const char *blocked = getenv("FSEARCH_FIXTURE_WAITPID_BLOCK_FILE");
    if (blocked && (options & WNOHANG) && access(blocked, F_OK) == 0) return 0;
    return real_waitpid(pid, status, options);
}
ssize_t read(int fd, void *buffer, size_t size) {
    ssize_t (*real_read)(int, void *, size_t) = dlsym(RTLD_NEXT, "read");
    ssize_t result = real_read(fd, buffer, size);
    if (fd == STDIN_FILENO && size == 28 && result > 0) pause_fixture("FSEARCH_FIXTURE_QUERY_DELAY_MS");
    return result;
}
