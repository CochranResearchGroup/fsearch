/* Owned inode-mark syscall regression. No capabilities or filesystem mark. */
#define main fsearch_setup_main
#include "../fsearch_broker_setup.c"
#undef main
#undef NDEBUG
#include <assert.h>

int main(void) {
    assert(geteuid() != 0);
    char path[] = "/tmp/fsearch-mark-fd-XXXXXX";
    assert(mkdtemp(path));
    int source = fanotify_init(FAN_CLASS_NOTIF | FAN_CLOEXEC | FAN_NONBLOCK | FAN_REPORT_DFID_NAME_TARGET,
                              O_RDONLY | O_CLOEXEC);
    if (source < 0 && (errno == EPERM || errno == ENOSYS || errno == EINVAL)) {
        assert(!rmdir(path));
        puts("broker_mark_descriptor_skip: unprivileged FID fanotify unavailable");
        return 77;
    }
    assert(source >= 0);
    int path_only = safe_open(AT_FDCWD, path, O_PATH | O_DIRECTORY);
    assert(path_only >= 0);
    errno = 0;
    assert(fanotify_mark(source, FAN_MARK_ADD, FAN_CREATE | FAN_ONDIR, path_only, NULL) == -1 && errno == EBADF);
    close(path_only);
    int root = open_root(path);
    assert(root >= 0);
    int result = fanotify_mark(source, FAN_MARK_ADD, FAN_CREATE | FAN_ONDIR, root, NULL);
    int error = errno;
    close(root); close(source);
    assert(!rmdir(path));
    if (result) fprintf(stderr, "mark_descriptor_failed errno=%d\n", error);
    assert(result == 0);
    puts("broker_mark_descriptor_pass: owned inode mark accepts setup root descriptor");
    return 0;
}
