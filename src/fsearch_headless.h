/* Private snapshot search seam. GPL-2.0-or-later. */
#pragma once
#include <glib.h>
#include <stdbool.h>
#define MAX_SNAPSHOT_BYTES (64 * 1024 * 1024)
#define MAX_RESPONSE_BYTES (1024 * 1024)
#define MAX_CANDIDATES 500000
typedef struct {
    gchar *database;
    gchar *socket;
    gchar *query;
    gchar *extension;
    gchar *kind;
    gboolean path;
    gboolean match_case;
    gint limit;
    gint max_candidates;
    gint max_bytes;
    gint timeout_ms;
} Options;

typedef struct FsearchHeadlessSnapshot FsearchHeadlessSnapshot;
FsearchHeadlessSnapshot *fsearch_headless_open(const char *path, const char **error);
void fsearch_headless_close(FsearchHeadlessSnapshot *snapshot);
const char *fsearch_headless_identity(FsearchHeadlessSnapshot *snapshot);
GString *fsearch_headless_search(const Options *options, FsearchHeadlessSnapshot *snapshot, const char **error);
void fsearch_headless_append_json_string(GString *out, const char *text);
G_DEFINE_AUTOPTR_CLEANUP_FUNC(FsearchHeadlessSnapshot, fsearch_headless_close)
