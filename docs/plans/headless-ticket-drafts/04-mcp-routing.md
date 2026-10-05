# Route Linux filename requests through file-searcher MCP

Published: https://github.com/CochranResearchGroup/file-searcher/issues/20

Status: READY; owner: ecochran76; honor blocking dependencies.

## Parent

https://github.com/CochranResearchGroup/fsearch/issues/1

## What to build

An agent uses the existing file-searcher tools with an optional FSearch backend and retains existing intent interpretation, schemas, SQLite fallback and Everything routing.

## Acceptance criteria

- [ ] Create a linked integration issue in CochranResearchGroup/file-searcher after this breakdown is approved.
- [ ] Use the versioned packaged CLI contract; preserve filename paths and truthful cached visibility, truncation, completeness and freshness.
- [ ] Isolated public MCP fixtures cover success, load failure, timeout and degraded partial results without real-root indexing.
- [ ] No default routing or installed registration change before adoption qualification.

## Blocked by

https://github.com/CochranResearchGroup/fsearch/issues/2; no dependency on refresh or monitoring for synthetic integration.
