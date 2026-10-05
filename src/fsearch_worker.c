/* Resident query worker. Private supervised binary protocol. GPL-2.0-or-later. */
#include "fsearch_headless.h"
#include <arpa/inet.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <unistd.h>

static bool read_all(void *buffer, size_t size) {
    char *p = buffer;
    while (size) { ssize_t n = read(STDIN_FILENO, p, size); if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return false;
        p += n; size -= n; }
    return true;
}
static bool write_all(const void *buffer, size_t size) {
    const char *p = buffer;
    while (size) { ssize_t n = write(STDOUT_FILENO, p, size); if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return false;
        p += n; size -= n; }
    return true;
}
static bool send_frame(const char *body, size_t size) {
    uint32_t length = htonl(size);
    return write_all(&length, sizeof(length)) && write_all(body, size);
}
static void discard_log(const gchar *domain, GLogLevelFlags level, const gchar *message, gpointer data) {
    (void)domain; (void)level; (void)message; (void)data;
}
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    if (prctl(PR_SET_PDEATHSIG, SIGKILL) < 0 || getppid() != (pid_t)atoi(argv[2])) return 2;
    g_log_set_default_handler(discard_log, NULL);
    char gate;
    if (!read_all(&gate, 1) || gate != 'G') return 2;
    const char *error = NULL;
    g_autoptr(FsearchHeadlessSnapshot) snapshot = fsearch_headless_open(argv[1], &error);
    if (!snapshot) {
        g_autofree char *body = g_strdup_printf("{\"status\":\"error\",\"error\":{\"code\":\"%s\"}}", error);
        send_frame(body, strlen(body)); return 1;
    }
    g_autofree char *ready = g_strdup_printf("{\"status\":\"ready\",\"snapshot_id\":\"%s\"}", fsearch_headless_identity(snapshot));
    if (!send_frame(ready, strlen(ready))) return 1;
    for (;;) {
        uint32_t wire[7];
        if (!read_all(wire, sizeof(wire))) return 0;
        for (unsigned i = 0; i < 7; i++) wire[i] = ntohl(wire[i]);
        if (wire[0] > 7 || wire[1] > 2 || wire[2] < 1 || wire[2] > 1000 || wire[3] < 1 || wire[3] > MAX_CANDIDATES
            || wire[4] < 512 || wire[4] > MAX_RESPONSE_BYTES || wire[5] > 4096 || wire[6] > 512) return 2;
        char query[4097] = {0}, extension[513] = {0};
        if (!read_all(query, wire[5]) || !read_all(extension, wire[6])) return 2;
        if (strlen(query) != wire[5] || strlen(extension) != wire[6] || !g_utf8_validate(query, -1, NULL)
            || !g_utf8_validate(extension, -1, NULL)) return 2;
        const char *kinds[] = {"all", "files", "folders"};
        Options options = {.query = query, .extension = (wire[0] & 4) ? extension : NULL, .kind = (char *)kinds[wire[1]],
            .path = wire[0] & 1, .match_case = wire[0] & 2, .limit = wire[2], .max_candidates = wire[3], .max_bytes = wire[4]};
        g_autoptr(GString) response = fsearch_headless_search(&options, snapshot, &error);
        if (!response) response = g_string_new(NULL), g_string_printf(response,
            "{\"schema_version\":1,\"status\":\"error\",\"complete\":false,\"error\":{\"code\":\"%s\"},\"results\":[]}", error);
        if (!send_frame(response->str, response->len)) return 1;
    }
}
