# Installed local-workspace filename snapshot — 2026-10-08

Operator explicitly authorized `/home/ecochran76/workspace.local` and deferred disk diagnostics. This supersedes the earlier expansion hold; it does not establish physical disk health.

Installed native source: `e0ec8e758db755dbd3cf8b3a83c9e4a467c50137`. Direct `/usr/bin/cc` Meson build and all 20 test groups passed. Tests cover permission exclusions, bounded startup override, root-move confinement, malformed lifecycle state, deadlines and cleanup. Failed candidate attempts are retained in the private operation receipts: prototype refresh failure, 60-second timeout, and complete-scan loader arena failure. None changed live routing.

The accepted candidate published in **84.84 seconds**: **6,115,587 files and 618,761 directories**; **34,223 symlinks and 45 permission-denied subtrees excluded**, zero descendant mounts crossed. Snapshot size **132,313,886 bytes** (126.2 MiB). Hidden files, generated trees and dependencies are included where readable. No content indexing or permission changes were performed. Counts reflect a changing filesystem, not an atomic filesystem snapshot.

Normal `fsr` and a freshly initialized MCP client using the stored user registration returned the expected native source file through the warm socket and reported the workspace root. Direct native folder queries found fsearch, file-searcher, SysRAG, agent-browser and LitScout; agent-browser reached the requested 1,000-result limit, explicitly reported. Twenty warm native CLI name queries: median 20.21 ms, p95 23.86 ms, maximum 29.11 ms. This is a single-query sample, not a general benchmark or MCP latency measurement. Full slash-containing path queries can still reach the retained 500,000-examination budget and report `work_limit`.

The enabled `fsearch-workspace-query.service` uses a 1,536 MiB cgroup memory limit, no automatic restart, a 30-second worker startup bound and low CPU/I/O priority. Observed steady worker RSS 498,824 KiB, supervisor RSS 16,960 KiB; zero automatic restarts. Actual same-snapshot warm replacement returned `replaced`. The four previous pilot units are disabled/stopped, with units, runtimes and snapshots retained for rollback. Existing six roots, 22 aliases, SQLite, Everything and unrelated configuration remain identical. The MCP registration and frontend runtime are unchanged. SysRAG remains inactive with MainPID zero.

## Freshness boundary

This is a **cached filename snapshot**, not an active whole-workspace monitor. Whole-tree rebuilding after each event is not qualified for six million files; no 618,000-watch continuous monitor is installed or claimed. Explicit `fsearch-workspace-refresh` builds a candidate at low priority with a five-minute scan deadline, validates it, then requests warm replacement. The refresh build and replacement stages were individually exercised; the wrapper is the composition of those commands. Continuous large-root freshness is follow-up work.

Private rollback and receipts: `~/.local/share/fsearch/operations/workspace-20261008/`. `rollback.py` checks the current configuration hash, restores two-root configuration and reenables the prior units. Rollback is prepared, not executed. Private runtime manifests retain artifact hashes and source identity. References: issue #21, source/acceptance PR #22.
