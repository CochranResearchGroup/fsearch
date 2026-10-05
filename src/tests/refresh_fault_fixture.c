/* Provider-free refresh fault adapter. Never installed. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <dlfcn.h>
#include <errno.h>
#include <stdarg.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

long syscall(long number, ...) {
    long (*real_call)(long, ...) = dlsym(RTLD_NEXT, "syscall");
    va_list args; va_start(args, number); long result;
    if (number == SYS_openat2) {
        int fd = va_arg(args, int); const char *path = va_arg(args, const char *);
        void *how = va_arg(args, void *); size_t size = va_arg(args, size_t);
        if (path[0] == '/' && getenv("FSEARCH_REFRESH_FIXTURE_INVALID_REPLY")) {
            const char *variant = getenv("FSEARCH_REFRESH_FIXTURE_INVALID_REPLY");
            const char *reply = !strcmp(variant, "ready") ? "{\"status\":\"ready\"}\n"
                              : !strcmp(variant, "error") ? "{\"status\":\"error\",\"error\":[]}\n" : "[]\n";
            write(STDOUT_FILENO, reply, strlen(reply)); _exit(0);
        }
        const char *delay = getenv("FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS");
        if (delay && path[0] == '/') {
            if (getenv("FSEARCH_REFRESH_FIXTURE_CLOSE_STDOUT")) close(STDOUT_FILENO);
            long ms = strtol(delay, NULL, 10);
            struct timespec interval = {ms / 1000, (ms % 1000) * 1000000};
            while (nanosleep(&interval, &interval) && errno == EINTR) {}
        }
        const char *notify = getenv("FSEARCH_FIXTURE_RACE_NOTIFY_FD");
        const char *resume = getenv("FSEARCH_FIXTURE_RACE_RESUME_FD");
        const char *basename = strrchr(path, '/');
        basename = basename ? basename + 1 : path;
        if (getenv("FSEARCH_FIXTURE_RACE_PAUSE") && !strcmp(basename, "race-probe.pdf")) raise(SIGSTOP);
        if (notify && resume && !strcmp(basename, "race-probe.pdf")) {
            char gate = 'B';
            write(atoi(notify), &gate, 1);
            if (read(atoi(resume), &gate, 1) != 1 || gate != 'G') _exit(91);
        }
        if (getenv("FSEARCH_REFRESH_FIXTURE_MOUNT") && !strcmp(basename, "excluded-mount")) {
            write(STDERR_FILENO, "injected_EXDEV\n", 15); errno = EXDEV; result = -1;
        }
        else result = real_call(number, fd, path, how, size);
    }
    else if (number == SYS_landlock_create_ruleset) {
        void *attr = va_arg(args, void *); size_t size = va_arg(args, size_t); unsigned flags = va_arg(args, unsigned);
        if (getenv("FSEARCH_REFRESH_FIXTURE_NO_LANDLOCK") && flags == 1) { errno = EOPNOTSUPP; result = -1; }
        else result = real_call(number, attr, size, flags);
    }
    else if (number == SYS_landlock_add_rule) {
        int fd = va_arg(args, int); int type = va_arg(args, int); void *attr = va_arg(args, void *); unsigned flags = va_arg(args, unsigned);
        result = real_call(number, fd, type, attr, flags);
    }
    else if (number == SYS_landlock_restrict_self) {
        int fd = va_arg(args, int); unsigned flags = va_arg(args, unsigned); result = real_call(number, fd, flags);
    }
    else { errno = ENOSYS; result = -1; }
    va_end(args); return result;
}
int fstatat(int fd, const char *path, struct stat *info, int flags) {
    int (*real_call)(int, const char *, struct stat *, int) = dlsym(RTLD_NEXT, "fstatat");
    if (getenv("FSEARCH_REFRESH_FIXTURE_MOUNT") && !strcmp(path, "excluded-mount"))
        write(STDERR_FILENO, "FORBIDDEN_METADATA\n", 19);
    return real_call(fd, path, info, flags);
}
