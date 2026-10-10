/* Preparation only: never installed or invoked by ordinary tests.
 * Fixed root-owned configuration; one filesystem mark; no event reads.
 * The activation packet must separately authorize filesystem-wide observation.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/capability.h>
#include <linux/openat2.h>
#include <poll.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/fanotify.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <sys/un.h>
#include <unistd.h>

#define CONFIG_DIRECTORY "/etc/fsearch"
#define CONFIG_NAME "broker-root.conf"
#define SETUP_SOCKET "/run/fsearch/broker.sock"

/* SO_PEERCRED records credentials at listen/connect/socketpair, not the
 * credentials of a process that later inherits a socketpair. Require the
 * administrator-created listener, then accept and authenticate the client.
 * This function is also exercised without privileges using owned sockets. */
static int accept_client(int listener, uid_t creator, uid_t client, const char *path) {
    struct ucred peer;
    socklen_t peer_length = sizeof(peer);
    int type, listening;
    socklen_t type_length = sizeof(type), listening_length = sizeof(listening);
    struct sockaddr_un address = {0};
    socklen_t address_length = sizeof(address);
    size_t path_length = strlen(path);
    if (path_length >= sizeof(address.sun_path)
        || getsockopt(listener, SOL_SOCKET, SO_TYPE, &type, &type_length) || type != SOCK_SEQPACKET
        || getsockopt(listener, SOL_SOCKET, SO_ACCEPTCONN, &listening, &listening_length) || !listening
        || getsockopt(listener, SOL_SOCKET, SO_PEERCRED, &peer, &peer_length) || peer.uid != creator
        || getsockname(listener, (struct sockaddr *)&address, &address_length)
        || address.sun_family != AF_UNIX
        || address_length != offsetof(struct sockaddr_un, sun_path) + path_length + 1
        || memcmp(address.sun_path, path, path_length + 1)) return -1;
    int flags = fcntl(listener, F_GETFL);
    if (flags < 0 || fcntl(listener, F_SETFL, flags | O_NONBLOCK)) return -1;
    struct pollfd ready = {.fd = listener, .events = POLLIN};
    if (poll(&ready, 1, 2000) != 1 || !(ready.revents & POLLIN)) return -1;
    int channel = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
    if (channel < 0) return -1;
    peer_length = sizeof(peer);
    if (getsockopt(channel, SOL_SOCKET, SO_PEERCRED, &peer, &peer_length) || peer.uid != client) {
        close(channel);
        return -1;
    }
    return channel;
}

static int rejected(unsigned stage, int error) {
    /* No names, handles, PIDs, configuration bytes or paths in diagnostics. */
    fprintf(stderr, "broker_setup_rejected stage=%u errno=%d\n", stage, error);
    return 1;
}

static int safe_open(int base, const char *path, int flags) {
    struct open_how how = {.flags = flags | O_CLOEXEC,
                          .resolve = RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS};
    if (base != AT_FDCWD) how.resolve |= RESOLVE_BENEATH;
    return syscall(SYS_openat2, base, path, &how, sizeof(how));
}

static int open_root(const char *path) {
    /* fanotify_mark(NULL pathname) uses fdget, which rejects O_PATH.
     * Pin a readable directory descriptor; never enumerate or read it. */
    return safe_open(AT_FDCWD, path, O_RDONLY | O_DIRECTORY);
}

static int controlled(int fd, int directory) {
    struct stat st;
    return fstat(fd, &st) == 0 && st.st_uid == 0 && !(st.st_mode & 0022)
        && (directory ? S_ISDIR(st.st_mode) : S_ISREG(st.st_mode) && st.st_nlink == 1 && st.st_size < 4096);
}

int main(int argc, char **argv) {
    int config_dir = -1, config = -1, root = -1, source = -1, channel = -1, result = 1;
    unsigned stage = 1;
    int saved_errno = 0;
    char settings[4096], *end;
    unsigned char payload[64];
    if (argc != 3 || strcmp(argv[1], "--listener-fd")) return rejected(stage, errno);
    /* Inherited root-created private SOCK_SEQPACKET listener. Session bytes arrive on
     * that authenticated channel, never in process arguments or environment.
     * A privileged launcher accepts no caller-selected root/configuration. */
    errno = 0;
    long listener = strtol(argv[2], &end, 10);
    if (errno || *end || listener < 3 || listener > 1048576) return rejected(stage, errno);
    /* Reject broader capability sets, including DAC/search privileges. */
    struct __user_cap_header_struct header = {.version = _LINUX_CAPABILITY_VERSION_3};
    struct __user_cap_data_struct caps[2] = {{0}};
    if (syscall(SYS_capget, &header, caps) || caps[0].effective != (1U << CAP_SYS_ADMIN) || caps[1].effective)
        return rejected(stage, errno);
    stage = 2;
    config_dir = safe_open(AT_FDCWD, CONFIG_DIRECTORY, O_RDONLY | O_DIRECTORY);
    if (config_dir < 0 || !controlled(config_dir, 1)) goto done;
    stage = 3;
    config = safe_open(config_dir, CONFIG_NAME, O_RDONLY | O_NOFOLLOW);
    if (config < 0 || !controlled(config, 0)) goto done;
    stage = 4;
    ssize_t length = read(config, settings, sizeof(settings) - 1);
    if (length <= 0 || length >= (ssize_t)sizeof(settings) - 1) goto done;
    settings[length] = 0;
    if (memchr(settings, 0, length)) goto done;
    /* Exactly UID newline absolute-root newline. No whitespace expansion. */
    char *path = strchr(settings, '\n');
    if (!path) goto done;
    *path++ = 0;
    errno = 0;
    unsigned long uid = strtoul(settings, &end, 10);
    if (errno || *end || !*settings || settings[0] == '-' || uid > UINT32_MAX || !uid || *path != '/') goto done;
    char *last = strchr(path, '\n');
    if (!last || last[1]) goto done;
    *last = 0;
    stage = 5;
    channel = accept_client((int)listener, 0, (uid_t)uid, SETUP_SOCKET);
    if (channel < 0) goto done;
    stage = 6;
    struct timeval wait = {.tv_sec = 2};
    if (setsockopt(channel, SOL_SOCKET, SO_RCVTIMEO, &wait, sizeof(wait))) goto done;
    /* No incoming ancillary descriptor is accepted. MSG_CTRUNC rejects it;
     * undispatched SCM_RIGHTS descriptors are closed by the kernel. */
    struct iovec request_data = {.iov_base = payload, .iov_len = sizeof(payload)};
    struct msghdr request = {.msg_iov = &request_data, .msg_iovlen = 1};
    if (recvmsg(channel, &request, 0) != sizeof(payload) || request.msg_flags & (MSG_TRUNC | MSG_CTRUNC)
        || memcmp(payload, "FSBRK002", 8)) goto done;
    unsigned generation_nonzero = 0;
    for (unsigned i = 8; i < 16; i++) generation_nonzero |= payload[i];
    if (!generation_nonzero) goto done;
    stage = 7;
    root = open_root(path);
    if (root < 0) goto done;
    /* Attest the exact pinned root chosen by the fixed administrator config;
     * the caller cannot choose a different root through its request. */
    uint64_t expected_device = 0, expected_inode = 0;
    for (unsigned i = 0; i < 8; i++) {
        expected_device = (expected_device << 8) | payload[48+i];
        expected_inode = (expected_inode << 8) | payload[56+i];
    }
    stage = 8;
    struct stat pinned;
    if (!expected_device || !expected_inode || fstat(root, &pinned)
        || expected_device != (uint64_t)pinned.st_dev || expected_inode != (uint64_t)pinned.st_ino) goto done;
    stage = 9;
    source = fanotify_init(FAN_CLASS_NOTIF | FAN_CLOEXEC | FAN_NONBLOCK | FAN_REPORT_DFID_NAME_TARGET, O_RDONLY | O_CLOEXEC);
    if (source < 0) goto done;
    stage = 10;
    if (fanotify_mark(source, FAN_MARK_ADD | FAN_MARK_FILESYSTEM,
                      FAN_CREATE | FAN_DELETE | FAN_RENAME | FAN_ONDIR | FAN_EVENT_ON_CHILD, root, NULL)) goto done;
    /* The setup process never reads the queue. Transfer, close and exit. */
    union { struct cmsghdr align; char bytes[CMSG_SPACE(sizeof(int))]; } ancillary = {0};
    struct iovec data = {.iov_base = payload, .iov_len = sizeof(payload)};
    struct msghdr message = {.msg_iov = &data, .msg_iovlen = 1,
                             .msg_control = ancillary.bytes, .msg_controllen = sizeof(ancillary.bytes)};
    struct cmsghdr *control = CMSG_FIRSTHDR(&message);
    control->cmsg_level = SOL_SOCKET; control->cmsg_type = SCM_RIGHTS; control->cmsg_len = CMSG_LEN(sizeof(int));
    memcpy(CMSG_DATA(control), &source, sizeof(source));
    stage = 11;
    if (sendmsg(channel, &message, MSG_NOSIGNAL | MSG_DONTWAIT) != sizeof(payload)) goto done;
    result = 0;
done:
    saved_errno = errno;
    if (channel >= 0) close(channel);
    if (source >= 0) close(source);
    if (root >= 0) close(root);
    if (config >= 0) close(config);
    if (config_dir >= 0) close(config_dir);
    return result ? rejected(stage, saved_errno) : 0;
}
