# Search private snapshots through a bounded JSON CLI

Published: https://github.com/CochranResearchGroup/fsearch/issues/2

Status: READY; owner: ecochran76; honor blocking dependencies.

## Parent

https://github.com/CochranResearchGroup/fsearch/issues/1

## What to build

An operator can run a no-display JSON CLI against an explicit private snapshot and receive bounded cached filename results, completeness and freshness without reaching indexed roots.

## Acceptance criteria

- [ ] Versioned public CLI contract supports typed literal name/path matching, extension and file/folder filters; GUI query syntax cannot activate metadata-probing features.
- [ ] Explicit query-only lifecycle constructs no indexed-root monitors, scan fallback or root-poll sources; serving cannot refresh or save the snapshot.
- [ ] Per-user snapshot ownership/permissions and snapshot/input limits are enforced. Trusted owner-generated format boundary is documented; arbitrary uploaded snapshots are unsupported.
- [ ] Matching/collection, returned entries/bytes, memory and process duration have explicit limits; truncation, timeout, incomplete search, failure and completed zero matches are distinguished.
- [ ] Freshness and covered-root information comes from the snapshot without current root probes. Cached visibility is explicit.
- [ ] Unicode, quotes, newline and non-UTF-8 path representation is specified and verified through the CLI.
- [ ] Persisted synthetic results remain usable after source-root removal; all-thread syscall tracing, including a run beyond the old polling interval and a sensitive negative control, observes no indexed-root accesses.
- [ ] Upstream tests pass; scoped cold/warm fixture measurements establish whether one-shot startup is viable before more indexing machinery is built.

## Blocked by

None: can start immediately.
