/* FSearch headless snapshot CLI. GPL-2.0-or-later; see COPYING. */
#include "fsearch_database_file.h"
#include "fsearch_database_include.h"
#include "fsearch_database_entry.h"
#include "fsearch_query.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <poll.h>
#include <signal.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include "fsearch_headless.h"
static int
failure(const char *code) {
    printf("{\"schema_version\":1,\"status\":\"error\",\"complete\":false,\"error\":{\"code\":\"%s\"},\"results\":[]}\n", code);
    return 1;
}

static int
search_snapshot(const Options *options) {
    const char *error = NULL;
    g_autoptr(FsearchHeadlessSnapshot) snapshot = fsearch_headless_open(options->database, &error);
    if (!snapshot) return failure(error);
    g_autoptr(GString) response = fsearch_headless_search(options, snapshot, &error);
    if (!response) return failure(error);
    fputs(response->str, stdout);
    return 0;
}

static volatile sig_atomic_t interrupted;

static void
on_interrupt(int signum) {
    interrupted = signum;
}

static void
discard_worker_log(const gchar *domain, GLogLevelFlags level, const gchar *message, gpointer data) {
    (void)domain;
    (void)level;
    (void)message;
    (void)data;
}

static bool
set_worker_limit(int resource, rlim_t value) {
    struct rlimit current;
    if (getrlimit(resource, &current) < 0) {
        return false;
    }
    struct rlimit limit = {.rlim_cur = MIN(current.rlim_cur, value), .rlim_max = MIN(current.rlim_max, value)};
    return setrlimit(resource, &limit) == 0;
}

static int
supervise_search(const Options *options) {
    int channel[2];
    if (pipe2(channel, O_CLOEXEC) < 0) {
        return failure("containment_unavailable");
    }
    struct sigaction action = {.sa_handler = on_interrupt};
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) < 0 || sigaction(SIGTERM, &action, NULL) < 0) {
        close(channel[0]);
        close(channel[1]);
        return failure("containment_unavailable");
    }
    const gint64 deadline = g_get_monotonic_time() + (gint64)options->timeout_ms * 1000;
    pid_t pid = fork();
    if (pid < 0) {
        close(channel[0]);
        close(channel[1]);
        return failure("containment_unavailable");
    }
    if (pid == 0) {
        close(channel[0]);
        if (dup2(channel[1], STDOUT_FILENO) < 0) {
            _exit(1);
        }
        close(channel[1]);
        close(STDERR_FILENO);
        g_log_set_default_handler(discard_worker_log, NULL);
        if (!set_worker_limit(RLIMIT_AS, 2048UL * 1024 * 1024)
            || !set_worker_limit(RLIMIT_CPU, options->timeout_ms / 1000 + 1)
            || !set_worker_limit(RLIMIT_CORE, 0)) {
            failure("containment_unavailable");
            fflush(stdout);
            _exit(1);
        }
        int result = search_snapshot(options);
        fflush(stdout);
        _exit(result);
    }
    close(channel[1]);
    const int flags = fcntl(channel[0], F_GETFL);
    const char *reason = NULL;
    if (flags < 0 || fcntl(channel[0], F_SETFL, flags | O_NONBLOCK) < 0) {
        reason = "containment_unavailable";
    }
    g_autoptr(GString) response = g_string_sized_new(4096);
    bool reaped = false;
    bool eof = false;
    int status = 0;
    while (!reason && !(reaped && eof)) {
        if (interrupted) {
            reason = "cancelled";
            break;
        }
        if (g_get_monotonic_time() >= deadline) {
            reason = "deadline";
            break;
        }
        struct pollfd ready = {.fd = channel[0], .events = POLLIN};
        const int wait_ms = MAX(1, MIN(10, (deadline - g_get_monotonic_time()) / 1000));
        int polled = poll(&ready, 1, wait_ms);
        if (polled < 0 && errno != EINTR) {
            reason = "worker_io_failed";
            break;
        }
        if (polled > 0) {
            char buffer[4096];
            ssize_t count;
            while ((count = read(channel[0], buffer, sizeof(buffer))) > 0) {
                if (response->len + count > (unsigned)options->max_bytes) {
                    reason = "response_size_limit";
                    break;
                }
                g_string_append_len(response, buffer, count);
            }
            if (count == 0) {
                eof = true;
            }
            else if (count < 0 && errno != EAGAIN && errno != EINTR) {
                reason = "worker_io_failed";
            }
        }
        if (!reaped) {
            pid_t result = waitpid(pid, &status, WNOHANG);
            reaped = result == pid;
            if (result < 0 && errno != EINTR) {
                reason = "cleanup_unproved";
            }
        }
    }
    if (!reaped) {
        kill(pid, SIGKILL);
        const gint64 cleanup_deadline = g_get_monotonic_time() + 100000;
        while (!reaped && g_get_monotonic_time() < cleanup_deadline) {
            reaped = waitpid(pid, &status, WNOHANG) == pid;
            if (!reaped) {
                g_usleep(1000);
            }
        }
    }
    close(channel[0]);
    if (!reaped) {
        reason = "cleanup_unproved";
    }
    if (reason) {
        printf("{\"schema_version\":1,\"status\":\"error\",\"complete\":false,"
               "\"error\":{\"code\":\"%s\"},\"worker\":{\"pid\":%d,\"reaped\":%s},\"results\":[]}\n",
               reason, pid, reaped ? "true" : "false");
        return 1;
    }
    if (!WIFEXITED(status) || !response->len) {
        return failure("worker_failed");
    }
    fwrite(response->str, 1, response->len, stdout);
    return WEXITSTATUS(status);
}

/* Return -1 only when cold startup/reconciliation needs the Python control client. */
static int
native_service_client(const Options *options) {
    g_autofree char *directory = g_path_get_dirname(options->socket);
    g_autofree char *name = g_path_get_basename(options->socket);
    int dirfd = open(directory, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    struct stat info;
    if (dirfd < 0) return failure("unsafe_directory");
    if (fstat(dirfd, &info) < 0 || info.st_uid != geteuid() || (info.st_mode & 0077)) {
        close(dirfd); return failure("unsafe_directory");
    }
    if (fstatat(dirfd, name, &info, AT_SYMLINK_NOFOLLOW) < 0) {
        int saved = errno; close(dirfd);
        return saved == ENOENT ? -1 : failure("service_unavailable");
    }
    if (!S_ISSOCK(info.st_mode) || info.st_uid != geteuid() || (info.st_mode & 0077)) {
        close(dirfd); return failure("unsafe_socket");
    }
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    int length = snprintf(address.sun_path, sizeof(address.sun_path), "/proc/self/fd/%d/%s", dirfd, name);
    if (length < 0 || (unsigned)length >= sizeof(address.sun_path)) { close(dirfd); return failure("unsafe_socket"); }
    int connection = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
    if (connection < 0) { close(dirfd); return failure("service_unavailable"); }
    if (connect(connection, (struct sockaddr *)&address, sizeof(address)) < 0) {
        int saved = errno; close(connection); close(dirfd);
        return saved == ENOENT || saved == ECONNREFUSED ? -1 : failure("service_unavailable");
    }
    close(dirfd);
    struct ucred peer;
    socklen_t peer_size = sizeof(peer);
    if (getsockopt(connection, SOL_SOCKET, SO_PEERCRED, &peer, &peer_size) < 0 || peer.uid != geteuid()) {
        close(connection); return failure("unsafe_peer");
    }
    g_autofree char *id = g_strdup_printf("%ld-%lld-%u", (long)getpid(), (long long)g_get_monotonic_time(), g_random_int());
    g_autoptr(GString) request = g_string_new("{\"schema_version\":1,\"request_id\":");
    fsearch_headless_append_json_string(request, id);
    g_string_append(request, ",\"query\":"); fsearch_headless_append_json_string(request, options->query);
    g_string_append(request, ",\"kind\":"); fsearch_headless_append_json_string(request, options->kind);
    if (options->extension) {
        g_string_append(request, ",\"extension\":"); fsearch_headless_append_json_string(request, options->extension);
    }
    if (options->database) {
        g_autofree char *absolute = g_canonicalize_filename(options->database, NULL);
        if (strlen(absolute) > 4096) { close(connection); return failure("invalid_request"); }
        g_autofree char *encoded = g_base64_encode((const guchar *)absolute, strlen(absolute));
        g_string_append(request, ",\"expected_database_b64\":"); fsearch_headless_append_json_string(request, encoded);
    }
    g_string_append_printf(request, ",\"path\":%s,\"match_case\":%s,\"limit\":%d,\"max_candidates\":%d,\"max_bytes\":%d,\"timeout_ms\":%d}\n",
        options->path ? "true" : "false", options->match_case ? "true" : "false",
        options->limit, options->max_candidates, options->max_bytes, options->timeout_ms);
    if (request->len > 65536) { close(connection); return failure("invalid_request"); }
    struct sigaction action = {.sa_handler = on_interrupt};
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) < 0 || sigaction(SIGTERM, &action, NULL) < 0) {
        close(connection); return failure("containment_unavailable");
    }
    const gint64 deadline = g_get_monotonic_time() + (gint64)options->timeout_ms * 1000 + 300000;
    size_t sent = 0;
    g_autoptr(GString) response = g_string_new(NULL);
    const char *error = NULL;
    while (!error) {
        if (interrupted) { error = "cancelled"; break; }
        if (g_get_monotonic_time() >= deadline) { error = "deadline"; break; }
        struct pollfd ready = {.fd = connection, .events = sent < request->len ? POLLOUT : POLLIN};
        int wait_ms = MAX(1, MIN(10, (deadline - g_get_monotonic_time()) / 1000));
        int result = poll(&ready, 1, wait_ms);
        if (result < 0 && errno == EINTR) continue;
        if (result < 0) { error = "service_unavailable"; break; }
        if (!result) continue;
        if (sent < request->len) {
            ssize_t count = send(connection, request->str + sent, request->len - sent, MSG_NOSIGNAL);
            if (count < 0 && (errno == EAGAIN || errno == EINTR)) continue;
            if (count <= 0) { error = "service_unavailable"; break; }
            sent += count;
        }
        else {
            char buffer[4096];
            ssize_t count = read(connection, buffer, sizeof(buffer));
            if (count < 0 && (errno == EAGAIN || errno == EINTR)) continue;
            if (count <= 0) { error = "service_unavailable"; break; }
            if (response->len + count > (unsigned)options->max_bytes) { error = "response_size_limit"; break; }
            g_string_append_len(response, buffer, count);
            if (memchr(buffer, '\n', count)) break;
        }
    }
    close(connection);
    if (error) return failure(error);
    g_autofree char *correlation = g_strdup_printf("\"request_id\":\"%s\"", id);
    bool failed = g_str_has_prefix(response->str, "{\"schema_version\":1,\"status\":\"error\",");
    // This is the canonical schema produced by the owner-private service, not an arbitrary JSON endpoint.
    if (!g_str_has_prefix(response->str, "{\"schema_version\":1,") || response->str[response->len - 1] != '\n'
        || strlen(response->str) != response->len
        || memchr(response->str, '\n', response->len) != response->str + response->len - 1
        || (!strstr(response->str, correlation) && !(failed && strstr(response->str, "\"request_id\":null")))) {
        return failure("worker_protocol_failed");
    }
    fwrite(response->str, 1, response->len, stdout);
    return failed ? 1 : 0;
}

static int
service_client(const Options *options) {
    int warm = native_service_client(options);
    if (warm != -1) return warm;
    g_autofree char *executable = g_file_read_link("/proc/self/exe", NULL);
    if (!executable) return failure("service_unavailable");
    g_autofree char *directory = g_path_get_dirname(executable);
    g_autofree char *service = g_build_filename(directory, "fsearch-service", NULL);
    g_autoptr(GPtrArray) args = g_ptr_array_new_with_free_func(g_free);
    g_ptr_array_add(args, g_strdup(service));
    g_ptr_array_add(args, g_strdup("query"));
    g_ptr_array_add(args, g_strdup("--socket")); g_ptr_array_add(args, g_strdup(options->socket));
    if (options->database) { g_ptr_array_add(args, g_strdup("--database")); g_ptr_array_add(args, g_strdup(options->database)); }
    g_ptr_array_add(args, g_strdup("--query")); g_ptr_array_add(args, g_strdup(options->query));
    g_ptr_array_add(args, g_strdup("--kind")); g_ptr_array_add(args, g_strdup(options->kind));
    if (options->extension) { g_ptr_array_add(args, g_strdup("--extension")); g_ptr_array_add(args, g_strdup(options->extension)); }
    if (options->path) g_ptr_array_add(args, g_strdup("--path"));
    if (options->match_case) g_ptr_array_add(args, g_strdup("--match-case"));
    const char *keys[] = {"--limit", "--max-candidates", "--max-bytes", "--timeout-ms"};
    int values[] = {options->limit, options->max_candidates, options->max_bytes, options->timeout_ms};
    for (unsigned i = 0; i < 4; i++) {
        g_ptr_array_add(args, g_strdup(keys[i])); g_ptr_array_add(args, g_strdup_printf("%d", values[i]));
    }
    g_ptr_array_add(args, NULL);
    execv(service, (char *const *)args->pdata);
    return failure("service_unavailable");
}

int
main(int argc, char **argv) {
    Options options = {.kind = "all", .limit = 100, .max_candidates = MAX_CANDIDATES,
                       .max_bytes = MAX_RESPONSE_BYTES, .timeout_ms = 2000};
    // Preserve argv bytes for UTF-8 query inputs independently of the locale.
    GOptionEntry entries[] = {
        {"socket", 0, 0, G_OPTION_ARG_FILENAME, &options.socket, "Private warm-service socket", "PATH"},
        {"database", 0, 0, G_OPTION_ARG_FILENAME, &options.database, "Explicit private snapshot", "PATH"},
        {"query", 0, 0, G_OPTION_ARG_FILENAME, &options.query, "Literal substring, not GUI query syntax", "TEXT"},
        {"extension", 0, 0, G_OPTION_ARG_FILENAME, &options.extension, "Literal extension without dot", "EXT"},
        {"kind", 0, 0, G_OPTION_ARG_STRING, &options.kind, "files, folders or all", "KIND"},
        {"path", 0, 0, G_OPTION_ARG_NONE, &options.path, "Match full cached path", NULL},
        {"match-case", 0, 0, G_OPTION_ARG_NONE, &options.match_case, "Match case", NULL},
        {"limit", 0, 0, G_OPTION_ARG_INT, &options.limit, "Maximum returned entries (1..1000)", "N"},
        {"max-candidates", 0, 0, G_OPTION_ARG_INT, &options.max_candidates, "Maximum examined entries (1..500000)", "N"},
        {"max-bytes", 0, 0, G_OPTION_ARG_INT, &options.max_bytes, "Maximum response bytes (512..1048576)", "N"},
        {"timeout-ms", 0, 0, G_OPTION_ARG_INT, &options.timeout_ms, "Process deadline (1..10000)", "MS"},
        {NULL}
    };
    g_autoptr(GOptionContext) context = g_option_context_new("- search a trusted private FSearch snapshot");
    g_option_context_add_main_entries(context, entries, NULL);
    g_autoptr(GError) error = NULL;
    if (!g_option_context_parse(context, &argc, &argv, &error) || argc != 1
        || (!options.database && !options.socket) || !options.query || !g_utf8_validate(options.query, -1, NULL)
        || strlen(options.query) > 4096
        || (options.extension && (!g_utf8_validate(options.extension, -1, NULL) || strlen(options.extension) > 512))
        || options.limit < 1 || options.limit > 1000 || options.max_candidates < 1
        || options.max_candidates > MAX_CANDIDATES || options.max_bytes < 512
        || options.max_bytes > MAX_RESPONSE_BYTES || options.timeout_ms < 1 || options.timeout_ms > 10000
        || (strcmp(options.kind, "files") && strcmp(options.kind, "folders") && strcmp(options.kind, "all"))) {
        return failure("invalid_request");
    }
    return options.socket ? service_client(&options) : supervise_search(&options);
}
