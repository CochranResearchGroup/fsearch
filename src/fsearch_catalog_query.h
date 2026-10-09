/* Bounded cached literal matching over an immutable catalog view. GPL-2.0-or-later. */
#pragma once
#include "fsearch_catalog.h"
#include "fsearch_headless.h"
typedef struct {
    GString *rows;
    const char *stop;
    unsigned returned, examined, candidate_blocks;
} FsearchCatalogQueryResult;
bool fsearch_catalog_query(FsearchCatalogView *, const Options *, FsearchCatalogQueryResult *, const char **error);
void fsearch_catalog_query_clear(FsearchCatalogQueryResult *);
