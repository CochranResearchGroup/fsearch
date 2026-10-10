/* Private snapshot search seam. GPL-2.0-or-later. */
#pragma once
#include <glib.h>
#include <stdbool.h>
#include <stdint.h>
#define MAX_SNAPSHOT_BYTES (512 * 1024 * 1024)
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
typedef struct FsearchCatalog FsearchCatalog;
FsearchHeadlessSnapshot *fsearch_headless_open_catalog(const char *path, const char **error);
FsearchCatalog *fsearch_headless_catalog(FsearchHeadlessSnapshot *snapshot);
bool fsearch_headless_restore_catalog(FsearchHeadlessSnapshot *, int checkpoint_fd, const char **error);
FsearchHeadlessSnapshot *fsearch_headless_open(const char *path, const char **error);
void fsearch_headless_close(FsearchHeadlessSnapshot *snapshot);
const char *fsearch_headless_identity(FsearchHeadlessSnapshot *snapshot);
GString *fsearch_headless_search(const Options *options, FsearchHeadlessSnapshot *snapshot, const char **error);
void fsearch_headless_append_json_string(GString *out, const char *text);
G_DEFINE_AUTOPTR_CLEANUP_FUNC(FsearchHeadlessSnapshot, fsearch_headless_close)

bool fsearch_headless_checkpoint_metadata_write(FsearchHeadlessSnapshot *, int fd, uint64_t sequence, const char **error);
FsearchHeadlessSnapshot *fsearch_headless_open_checkpoint(const char *path, const char *identity, const char **error);
