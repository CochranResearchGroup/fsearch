/* Owned-fixture interposition only: pause immediately before directory read. */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <dirent.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

struct dirent *readdir(DIR *stream) {
    static struct dirent *(*original)(DIR *);
    static int paused;
    if (!original) original = dlsym(RTLD_NEXT, "readdir64");
    const char *victim = getenv("FSEARCH_BROKER_FIXTURE_INODE");
    const char *progress = getenv("FSEARCH_BROKER_FIXTURE_PROGRESS_FD");
    const char *resume = getenv("FSEARCH_BROKER_FIXTURE_RESUME_FD");
    if (!paused && victim && progress && resume) {
        struct stat identity;
        if (!fstat(dirfd(stream), &identity)) {
            if ((unsigned long long)identity.st_ino == strtoull(victim, NULL, 10)) {
                paused = 1;
                char token = 'P';
                if (write(atoi(progress), &token, 1) != 1 || read(atoi(resume), &token, 1) != 1)
                    _exit(91);
            }
        }
    }
    return original(stream);
}
