# FSearch memory and incremental-update research

Date: 2026-10-08
State: CLOSED (research complete; implementation unstarted)
Owner: Codex
Source baseline: installed native `e0ec8e758db755dbd3cf8b3a83c9e4a467c50137`; repository `2f313c825b6591542d0cfbce205c530ce3c683c5`.

## Question, scope and stopping rule

Is the 6.73-million-entry filename index reasonably memory efficient, what happens during updates, and which update strategy should be prototyped before broader Ubuntu adoption? Use current process/cgroup readbacks, the installed source, official Everything documentation, Microsoft filesystem documentation and Linux kernel/man-pages documentation. Stop after one read-only runtime baseline, source analysis and these primary-source comparisons. No new root scans, refreshes, privileged helpers, monitoring activation, configuration changes or disk diagnostics. Graphiti discovery skipped: current source, acceptance artifacts and fresh counters supply the required context. Existing GLOSSARY.md terms apply; no competing domain document is needed.

## Finding

Steady memory is defensible for this corpus, and broadly comparable in scale to Everything's published guidance. That does not establish workstation-wide affordability or implementation optimality. Peak memory and repeated full-tree work are the significant scaling constraints. Keep the accepted cached service while investigating incremental updates; do not enable the present whole-tree reconciliation loop over the workspace.

## Measured baseline

Read at 2026-10-08 13:09:24 UTC. Private machine-readable receipt: `~/.local/share/fsearch/operations/workspace-20261008/memory-research-readback.json`. The following counters are reproduced here so the findings do not depend solely on a temporary/private locator.

| Quantity | Value | Interpretation |
|---|---:|---|
| Indexed files / directories | 6,115,587 / 618,761 | 6,734,348 total entries from accepted refresh |
| Saved snapshot | 132,313,886 bytes (126.2 MiB) | Disk bytes, not resident memory |
| Query service memory.current | 515,518,464 bytes (491.64 MiB) | Entire query service cgroup |
| Query service memory.peak | 1,019,846,656 bytes (972.60 MiB) | Recorded cgroup lifetime peak; not a synchronized phase trace |
| Worker RSS / PSS | 499,384 / 492,731 KiB | smaps_rollup; PSS apportions shared pages |
| Supervisor RSS / PSS | 16,532 / 9,361 KiB | smaps_rollup; sampled separately from worker |
| Query service swap | 524,288 bytes (0.5 MiB) | Worker reports zero swap; supervisor accounts for it |
| Service OOM / OOM-kill counters | 0 / 0 | No recorded cgroup OOM event |
| Host MemAvailable | 41,427,192 KiB (~39.5 GiB) | Availability at this readback only |
| Host swap used | ~25.30 GiB | Retained swapped pages do not by themselves prove current thrashing |
| Host memory PSI, some/full avg10 | 0.00 / 0.00 | No measured memory stalls in that recent window |

The accepted build took 84.84 seconds. Twenty prior warm native CLI calls for one filename had median 20.21 ms and p95 23.86 ms. Those are historical acceptance samples, not freshly rerun general workload benchmarks or MCP timings. [Installed acceptance](2026-10-08-workspace-index.md).

The cgroup includes its descendants; memory.current and memory.peak measure a different scope from a single process RSS. Peak records the maximum since cgroup creation or applicable reset, so attributing its precise instant requires phase sampling. [Kernel cgroup documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html).

The earlier statement that “under 1% of host RAM” makes this reasonable was insufficient. Current FSearch swap is negligible and current host memory stalls are low, but this readback neither diagnoses earlier sluggishness nor establishes that future refreshes are harmless. No Windows-host pressure assessment was made.

## Where the memory goes

The query loader already uses arena-backed entries, retains NAME order, skips unneeded sorted arrays, and avoids GUI per-root owning chunks. It trims freed loader scratch where glibc supports that hint. The remaining representation holds names, parent links, ordering pointers and a substring prefilter. [Query loader](https://github.com/CochranResearchGroup/fsearch/blob/e0ec8e758db755dbd3cf8b3a83c9e4a467c50137/src/fsearch_database_file.c), [headless loader and signatures](https://github.com/CochranResearchGroup/fsearch/blob/e0ec8e758db755dbd3cf8b3a83c9e4a467c50137/src/fsearch_headless.c).

The 192-bit signature layout requires 24 bytes per entry plus block rounding: **154.14 MiB for this corpus if both signature allocations succeed**. Its ceiling is 256 MiB; allocation failure falls back to exact bounded scanning. This is a source-derived allocation size, not a measured heap profile or proof that each allocation succeeded. Turning it off would sacrifice candidate filtering; the latency cost is unmeasured. A compact representation or narrower filter is an experiment, not a free memory saving. [Signature allocation and fallback](https://github.com/CochranResearchGroup/fsearch/blob/e0ec8e758db755dbd3cf8b3a83c9e4a467c50137/src/fsearch_headless.c).

The entry arena's 1 GiB limit, 2 GiB worker address-space limit, 512 MiB snapshot limit and 1,536 MiB query-service cgroup limit are ceilings, not preallocated consumption. The installed unit supplies the cgroup limit; source supplies the other bounds. [Source capacity change](https://github.com/CochranResearchGroup/fsearch/pull/22), [installed acceptance](2026-10-08-workspace-index.md).

## Refresh and replacement peak

Refresh builds a complete candidate, reaps the builder, loads the candidate in a validation worker, reaps that worker, then publishes it. The serving query worker can remain alive throughout. Warm replacement separately starts a new query worker while retaining the old one, then promotes and reaps the old generation. The query service therefore temporarily carries two loaded snapshots. [Refresh sequence](https://github.com/CochranResearchGroup/fsearch/blob/e0ec8e758db755dbd3cf8b3a83c9e4a467c50137/src/fsearch_refresh.py), [replacement sequence](https://github.com/CochranResearchGroup/fsearch/blob/e0ec8e758db755dbd3cf8b3a83c9e4a467c50137/src/fsearch_service.py).

The recorded 972.60 MiB cgroup peak is consistent with this overlap; it is not proof of the exact phase responsible. **Total refresh peak remains unmeasured**: explicit refresh runs outside the query-service cgroup. Its worker address-space bound does not impose a combined resident-memory limit over refresh plus serving. This is the first measurement gap to close before expanding or promising an aggregate resource budget.

Single-point linear extrapolation, including fixed overhead, gives the following planning estimates. These are not acceptance results:

| Entries | Steady service estimate | Replacement-overlap estimate |
|---|---:|---:|
| Current 6.73 million | 492 MiB measured | 973 MiB recorded peak |
| 10 million | ~730 MiB | ~1,444 MiB |
| 20 million | ~1,460 MiB | ~2,888 MiB |

At ten million entries, estimated replacement overlap approaches the installed 1,536 MiB limit before accounting for workload variation. Twenty million entries exceed the current ten-million-entry scan cap and would exceed that service limit during comparable replacement. Longer names and changed data structures alter these estimates. The earlier steady-only whole-drive extrapolation understated the update constraint.

## Everything comparison

Everything's FAQ gives approximately 100 MB RAM and 45 MB disk per million files. It also says its default 1.4 configuration stores sizes, dates and extra sorting data. Our service uses about 76.55 resident bytes per indexed file-or-directory entry and 19.65 saved bytes per entry. This is the same broad order of magnitude, not a matched benchmark: entry mix, optional metadata, units, versions, filenames and process scope differ. There is no evidence here that Everything uses dramatically less RAM for equivalent data. [Everything FAQ](https://www.voidtools.com/faq/).

Everything's architectural advantage for NTFS freshness is its use of the USN journal, allowing updates after downtime. Microsoft's change journal records volume changes rather than requiring traversal for each update; journal history can be deleted, so consumers still need recovery logic. We have not qualified an equivalent persistent change feed for this Ubuntu filesystem. [Everything FAQ](https://www.voidtools.com/faq/), [Microsoft change journals](https://learn.microsoft.com/en-us/windows/win32/fileio/change-journals).

## Update architecture

The current monitor arms directory watches, runs a full refresh and watches for a dirty generation. Changes cause it to discard/rearm and rebuild, with only 50 ms debounce and termination after eight consecutive dirty generations. It is bounded, but a busy workspace can repeatedly invalidate expensive scans or terminate monitoring. [Monitor implementation](https://github.com/CochranResearchGroup/fsearch/blob/e0ec8e758db755dbd3cf8b3a83c9e4a467c50137/src/fsearch_monitor.py).

Linux inotify requires separate subdirectory watches, handling newly created/moved-in trees and queue overflow. Its notifications are a change feed while monitoring, not our qualified downtime-replay mechanism. A 619,000-directory tree therefore has substantial watch admission and maintenance work. Kernel watch memory is not included in today's service footprint because that monitor is off. [Linux inotify documentation](https://man7.org/linux/man-pages/man7/inotify.7.html).

Fanotify can monitor a filesystem with fewer marks, but filesystem marks require CAP_SYS_ADMIN; unprivileged groups cannot mark whole mounts/filesystems. Mount marks also cannot supply several file-handle-based create/move events, so “watch the mount” is not a complete filename-update design. It still has queue overflow. A privileged, tightly scoped helper would be a separate architectural and authorization decision, not an automatic optimization. [fanotify_init](https://man7.org/linux/man-pages/man2/fanotify_init.2.html), [fanotify_mark](https://man7.org/linux/man-pages/man2/fanotify_mark.2.html), [fanotify events](https://man7.org/linux/man-pages/man7/fanotify.7.html).

**Recommended prototype (inference):** immutable searchable base plus bounded additions/deletions/renames overlay, fed by batched directory events. Reconcile only affected subtrees; perform occasional compaction with one admitted candidate at a time. Use parent identities so renaming a directory does not require rewriting all descendant full paths. Explicitly mark coverage incomplete after overflow, missing events, restart or offline roots until bounded reconciliation completes. A persisted application event log cannot recover events lost while the watcher was stopped. Preserve no-symlink/no-cross-mount checks during subtree admission; notifications alone do not authorize traversal.

This separates query storage from change ingestion. It may reduce rebuild frequency and overlap, but incremental names, ordering and signature updates need exact-result tests. Directory-watch admission cost remains a separate unresolved concern; the overlay does not solve it by itself. Sharding by approved subtree is an alternative if compaction overlap proves too large, at the cost of federation and skew handling. Neither is implemented by this research.

## Recommended next packet

Use grill-with-docs to agree on freshness and combined memory targets, then prototype against owned synthetic roots. Suggested starting targets, **not accepted gates**: steady service <=600 MiB and aggregate update peak <=1.25 GiB at the present corpus; event-to-query p95 <=1 second for a bounded mutation workload; explicit incomplete coverage after overflow or restart; exact parity for create/delete/rename, Unicode, moved trees and confinement escapes. Representative native query p95 <=50 ms is a proposed target, not established by the one-query baseline.

First obtain one instrumented, explicitly scheduled refresh/replacement trace that counts serving, builder, validator and candidate processes together, with phases, peak RSS/PSS/cgroup accounting, CPU/I/O and query latency. Do not reset historical counters or trigger that costly real-root run as part of this read-only research. Use that trace and synthetic delta tests to decide whether filter compression, structural sharing, sharding or ingestion changes offer the best benefit. No additional deployment or root expansion is implied.

## Validation and remaining uncertainty

Research is source-grounded and the current read-only counters were captured. No code changed, so no implementation tests or stress run were needed. Full build peak, per-allocation heap usage, watch overhead at this corpus, incremental correctness and a matched Everything workload remain unmeasured. Runtime state, installed configuration and indexing scope were unchanged. This file is the research deliverable; branch research/workspace-memory, retained local worktree, uncommitted for review. Memory disposition is recorded separately as forbidden: no separate durable memory write is authorized.
