/* Exercise the actual setup accept path using unprivileged owned sockets.
 * Never execute the setup main, create a fanotify group or grant capabilities. */
#define main fsearch_setup_main
#include "../fsearch_broker_setup.c"
#undef main
#undef NDEBUG
#include <assert.h>
#include <dirent.h>
#include <sys/wait.h>

static unsigned descriptors(void) {
    DIR *directory = opendir("/proc/self/fd");
    assert(directory);
    unsigned count = 0;
    while (readdir(directory)) count++;
    closedir(directory);
    return count;
}

int main(void) {
    assert(geteuid() != 0);
    char temporary[] = "/tmp/fsearch-listener-XXXXXX";
    assert(mkdtemp(temporary));
    char path[108];
    assert(snprintf(path, sizeof(path), "%s/socket", temporary) < (int)sizeof(path));
    int listener = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
    assert(listener >= 0);
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    strcpy(address.sun_path, path);
    assert(!bind(listener, (struct sockaddr *)&address, offsetof(struct sockaddr_un, sun_path) + strlen(path) + 1));
    assert(!listen(listener, 4));
    int client = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
    assert(client >= 0);
    assert(!connect(client, (struct sockaddr *)&address, offsetof(struct sockaddr_un, sun_path) + strlen(path) + 1));
    unsigned before = descriptors();
    /* A user-created listener cannot impersonate an administrator listener. */
    assert(accept_client(listener, 0, getuid(), path) < 0);
    assert(accept_client(listener, getuid(), getuid(), "/wrong-owned-endpoint") < 0);
    assert(descriptors() == before);
    pid_t creator = getpid(), child = fork();
    assert(child >= 0);
    if (!child) {
        int accepted = accept_client(listener, getuid(), getuid(), path);
        assert(accepted >= 0);
        assert(fcntl(accepted, F_GETFD) & FD_CLOEXEC);
        assert(send(accepted, &creator, sizeof(creator), MSG_NOSIGNAL) == sizeof(creator));
        close(accepted);
        _exit(0);
    }
    pid_t attested;
    assert(recv(client, &attested, sizeof(attested), 0) == sizeof(attested));
    assert(attested == creator);
    struct ucred peer;
    socklen_t peer_length = sizeof(peer);
    assert(!getsockopt(client, SOL_SOCKET, SO_PEERCRED, &peer, &peer_length));
    assert(peer.pid == creator && peer.pid != child && peer.uid == getuid());
    int status;
    assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && !WEXITSTATUS(status));
    close(client);
    client = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
    assert(client >= 0);
    assert(!connect(client, (struct sockaddr *)&address, offsetof(struct sockaddr_un, sun_path) + strlen(path) + 1));
    before = descriptors();
    assert(accept_client(listener, getuid(), getuid() + 1, path) < 0);
    assert(descriptors() == before);
    int pair[2];
    assert(!socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, pair));
    assert(accept_client(pair[0], getuid(), getuid(), path) < 0);
    int stream = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    assert(stream >= 0);
    assert(accept_client(stream, getuid(), getuid(), path) < 0);
    close(stream); close(pair[0]); close(pair[1]); close(client); close(listener);
    assert(!unlink(path) && !rmdir(temporary));
    puts("broker_listener_pass: creator credentials survive inherited accept; wrong creator/client/path and socketpair refused; no descriptor leak; child reaped");
    return 0;
}
