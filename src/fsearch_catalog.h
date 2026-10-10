/* Owner-scoped immutable filename generations. GPL-2.0-or-later. */
#pragma once
#include <glib.h>
#include <stdbool.h>
#include <stdint.h>

typedef struct FsearchCatalog FsearchCatalog;
typedef struct FsearchCatalogView FsearchCatalogView;
typedef struct FsearchCatalogBuild FsearchCatalogBuild;
typedef enum { FSEARCH_CATALOG_DELETED, FSEARCH_CATALOG_FILE, FSEARCH_CATALOG_FOLDER } FsearchCatalogKind;
typedef struct {
    uint32_t id, parent;
    FsearchCatalogKind kind;
    const char *name; /* raw filesystem bytes; roots have parent == id and contain their absolute paths */
} FsearchCatalogEntry;
typedef struct {
    size_t memory_limit;
    unsigned overlay_limit, replay_limit, view_limit;
} FsearchCatalogLimits;
typedef struct {
    uint64_t sequence, generation;
    size_t accounted_bytes, reserved_bytes, peak_bytes;
    unsigned live_views, overlay_entries;
    const char *deferred_reason; /* static string; NULL means no deferral */
    bool building, closed;
} FsearchCatalogStatus;
typedef bool (*FsearchCatalogVisitor)(const FsearchCatalogEntry *, void *);

FsearchCatalog *fsearch_catalog_new(const FsearchCatalogEntry *entries, unsigned count,
                                   const FsearchCatalogLimits *limits, const char **error);
/* Close cancels publication, but pinned views and an outstanding build remain owned by callers. */
void fsearch_catalog_close(FsearchCatalog *catalog);
void fsearch_catalog_free(FsearchCatalog *catalog);
FsearchCatalogView *fsearch_catalog_acquire(FsearchCatalog *catalog);
FsearchCatalogView *fsearch_catalog_view_ref(FsearchCatalogView *view);
void fsearch_catalog_view_unref(FsearchCatalogView *view);
bool fsearch_catalog_view_get(FsearchCatalogView *view, uint32_t id, FsearchCatalogEntry *entry);
bool fsearch_catalog_view_lookup(FsearchCatalogView *, const char *absolute_path, FsearchCatalogEntry *);
char *fsearch_catalog_view_path(FsearchCatalogView *view, uint32_t id);
bool fsearch_catalog_view_visit(FsearchCatalogView *view, FsearchCatalogVisitor visitor, void *data);
uint64_t fsearch_catalog_view_sequence(FsearchCatalogView *view);
uint64_t fsearch_catalog_view_generation(FsearchCatalogView *view);
/* Expected sequence makes duplicate/reordered/gapped delivery explicit. Create allocates a fresh ID. */
bool fsearch_catalog_create(FsearchCatalog *, uint64_t sequence, uint32_t parent,
                            FsearchCatalogKind kind, const char *name, uint32_t *id, const char **error);
bool fsearch_catalog_change(FsearchCatalog *, uint64_t sequence, uint32_t id, uint32_t parent,
                            FsearchCatalogKind kind, const char *name, const char **error);
void fsearch_catalog_status(FsearchCatalog *, FsearchCatalogStatus *status);
/* Begin reserves the complete replacement allocation. Run on a background thread; publish on owner. */
FsearchCatalogBuild *fsearch_catalog_compact_begin(FsearchCatalog *, const char **error);
bool fsearch_catalog_compact_run(FsearchCatalogBuild *, const char **error);
bool fsearch_catalog_compact_validate(FsearchCatalogBuild *, const char **error);
void fsearch_catalog_compact_abort(FsearchCatalog *, FsearchCatalogBuild *, const char *reason);
bool fsearch_catalog_compact_publish(FsearchCatalog *, FsearchCatalogBuild *, const char **error);
/* Must join the build thread before freeing the build. No implicit retry. */
void fsearch_catalog_compact_free(FsearchCatalog *, FsearchCatalogBuild *);
G_DEFINE_AUTOPTR_CLEANUP_FUNC(FsearchCatalogView, fsearch_catalog_view_unref)
G_DEFINE_AUTOPTR_CLEANUP_FUNC(FsearchCatalog, fsearch_catalog_free)

/* Owner-private cache descriptors only. Writer requires an empty file; caller owns
 * atomic publication and directory fsync. Reader validates snapshot binding,
 * checksum and tree before exposing a catalog. Indexed roots are never probed. */
bool fsearch_catalog_checkpoint_write(FsearchCatalog *, int fd, const char *snapshot_id, const char **error);
FsearchCatalog *fsearch_catalog_checkpoint_read(int fd, const char *snapshot_id,
                                               const FsearchCatalogLimits *, const char **error);

typedef struct FsearchCatalogCheckpoint FsearchCatalogCheckpoint;
FsearchCatalogCheckpoint *fsearch_catalog_checkpoint_capture(FsearchCatalog *, const char **error);
bool fsearch_catalog_checkpoint_write_capture(FsearchCatalogCheckpoint *, int fd, const char *snapshot_id, const char **error);
void fsearch_catalog_checkpoint_free(FsearchCatalogCheckpoint *);
uint64_t fsearch_catalog_checkpoint_sequence(FsearchCatalogCheckpoint *);

bool fsearch_catalog_checkpoint_verify_capture(FsearchCatalogCheckpoint *, int fd, const char **error);
