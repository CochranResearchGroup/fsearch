# Repository production pilot and staged growth

Owner: ecochran76. Issue: #5. User approved assessment and indexing of `/home/ecochran76/workspace.local/file-searcher` only on 2026-10-05.

## Admission and execution

The approved root maps to ext4 `/dev/sdd` (device 8:48) in WSL2. Sysfs identifies a Microsoft virtual disk; the physical backing drive and its health remain unknown from this Linux view. This assessment does not establish that the suspected bad physical disk is unrelated. No Windows mount or broader workspace root was scanned. The installed contained refresh completed in 0.321 seconds, published a private snapshot, excluded four symlinks and encountered no descendant mounts.

Private operational evidence and snapshot: `~/.local/share/fsearch/operations/repository-pilot-20261005/`. Native installed source: `eda902627bc96e626887b06f69f66bc3c43499e3`. Installed optional frontend: `0f0f48445da14892cee8e393505ba0239ed9f6b2/python-3.12`. Neither user MCP registration nor default routing changed.

## Query qualification

One cold CLI request took 26.227 ms. The following stages vary sequential request count, not indexed corpus size or concurrency. Each request checked the expected repository README hit. These are local end-to-end CLI measurements, including process startup; they are not engine-only timings.

| Requests | Median ms | p95 ms |
|---:|---:|---:|
| 1 | 26.227 | 26.227 |
| 3 | 6.209 | 6.209 |
| 10 | 5.426 | 5.723 |
| 32 | 5.912 | 6.496 |
| 100 | 5.012 | 5.653 |

The resident supervisor used 18,240 KiB RSS and worker 8,800 KiB (27,040 KiB combined). Actual installed stdio MCP `find` and `lookup` both returned the expected hit with a successful FSearch backend. Test services exited cleanly; the MCP worker was absent afterward. The accepted snapshot is retained; no background pilot service remains active.

## Incremental complexity

Interpretation pending user clarification: a half-decade is a factor of sqrt(10), approximately 3.16. The first request-count ladder was 1, 3, 10, 32, 100. Progress by changing one dimension at a time:

1. Baseline: this root, literal cached filename queries, direct CLI and actual MCP (executed).
2. Query diversity: path, extension, folders, Unicode and completed-zero queries against this same admitted snapshot.
3. Concurrency: owned clients at 1, 3, 10, 32; preserve bounded queue/busy semantics rather than demanding all requests succeed simultaneously.
4. Freshness: explicit refresh, accepted snapshot replacement, then contained monitoring of this root; prove cleanup and cached-query isolation at each stage.
5. Larger corpora: synthetic 1k, 3.2k, 10k, 32k, 100k, 320k, 1m names with frozen latency/RSS/resource gates. Real-root expansion requires separate root selection and admission; numerical growth does not authorize scanning siblings.
6. Persistent pilot and routing activation: qualify rollback and operator-visible behavior before changing default user registration.

Keep cold/warm timing separate. Retain failures, stop expansion on quarantine/unproved cleanup, and preserve the last accepted snapshot. Physical storage admission remains independent of performance evidence. This pilot does not close broader #5 adoption or parent #1.

Memory disposition: forbidden; no personal memory write authorized.

## Query diversity and concurrency executed

The same accepted snapshot passed literal filename, selective full-path, folder, Unicode-zero and literal-punctuation-zero queries. Broad Python-extension filtering returned exactly the 1,000-entry cap with `result_limit` and `complete=false`; this is truthful bounded behavior. The first harness incorrectly required every diversity request to complete, failed on broad-query truncation, and its private receipt is retained as `complexity-first.json`. The corrected harness validates truncation explicitly rather than changing production bounds.

Concurrent client stages 1, 3, 10 and 32 all returned correct completed README hits. Observed maximum end-to-end request latency was 6.43, 6.75, 9.89 and 28.31 ms respectively. Client starts were scheduled through a thread pool; this does not establish that all requests occupied the queue simultaneously or qualify queue saturation. Existing fault/queue tests remain the relevant saturation evidence. Service exited zero and its recorded worker was absent afterward. Private details: `complexity.json`.

Next complexity step is explicit refresh and serving-snapshot replacement on this same approved root, followed by bounded monitoring. No root expansion follows from these request-count stages.

## Refresh, replacement and monitoring executed

A second explicit contained refresh of the same approved repository completed in 0.175 seconds, again excluding four symlinks and no descendant mounts. The warm service acknowledged explicit candidate replacement with its accepted snapshot identity, and subsequent cached README lookup succeeded.

The installed monitor then armed 627 directory watches and acknowledged both publication and serving replacement. Three uniquely owned empty sentinel create/delete cycles within the approved repository became visible through the warm query service: creates in 0.238, 0.398 and 0.400 seconds; deletes in 0.230, 0.230 and 0.289 seconds. The sentinel was removed. Dirty-generation reconciliation occurred; its event history is retained rather than hidden. This small pilot establishes exercised freshness, not a guaranteed latency SLA or larger-root watch-resource bound.

Observed supervisor RSS was 18,240 KiB for query and 17,120 KiB for monitor; these are supervisor-only figures, not aggregate indexing memory. Both exited zero, and all 26 recorded worker identities were absent after shutdown. Private evidence: `freshness.json`, `monitor-events.jsonl`, `freshness.py`. The accepted pilot snapshots remain private; no background service, default routing change or broader-root indexing was enabled.
