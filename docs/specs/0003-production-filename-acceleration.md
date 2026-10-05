# Production filename acceleration

Status: APPROVED on 2026-10-04 by the operator’s “ok go” following the concrete decision summary. Public seams: existing CLI/private socket. Review baseline: 5ec26bab. Four-ticket breakdown approved. Production gates below are frozen before implementation measurements.

## Problem Statement

A warm filename service avoids disk probes and repeated loading but still performs costly sequential matching. A selective million-entry query can hit the examined-entry cap before finding a cached match. The prototype demonstrates selective acceleration but consumes excessive posting memory and leaves slow short, Unicode and path searches. Repeated Unicode normalization also leaks memory in the existing matcher.

## Solution

Preserve a private accepted snapshot and return exact literal filename results through the existing CLI and Unix socket. Use a compact native candidate filter, followed by authoritative exact verification, to avoid scanning unrelated entries. Keep resource bounds and truthful coverage even when a query cannot finish. Fix the Unicode lifetime defect independently before accelerator integration.

## User Stories

1. As the operator, I want repeated Unicode searches to retain bounded worker memory so the resident service remains usable.
2. As a filename-search user, I want selective literal queries to examine a small candidate set so large snapshots respond promptly.
3. As a user, I want common queries to return bounded results quickly without collecting every possible match.
4. As a user, I want one- and two-character inputs to retain arbitrary substring semantics.
5. As a user, I want Unicode case and normalization behavior to remain compatible with the current matcher.
6. As a user, I want case-sensitive queries to preserve exact case behavior.
7. As a user, I want path searches to include matching parent directories.
8. As a user, I want duplicate basenames from different directories returned in the existing order.
9. As a user, I want punctuation such as percent, underscore, star and quotes treated literally.
10. As a user, I want raw-byte filenames returned losslessly when they cannot be represented as UTF-8.
11. As a user, I want extension and file/folder filters preserved.
12. As a user, I want output byte and result limits to produce truthful truncation.
13. As an agent client, I want incomplete searches distinguished from completed empty results.
14. As an operator, I want memory, startup and work bounds measured before deployment.
15. As an operator, I want cancellation and failed-worker cleanup to retain existing quarantine behavior.
16. As an operator, I want the loaded snapshot to retain its identity if its pathname changes.
17. As an operator, I want queries to remain independent of indexed-root filesystem activity.
18. As a developer, I want direct CLI and socket behavior to share the matcher and candidate-selection implementation.
19. As a developer, I want upstream GUI behavior and tests preserved.
20. As an operator, I want runtime acceptance to distinguish source qualification from installed qualification.

## Implementation Decisions

- The existing CLI and private socket are the public acceptance seams. The native snapshot/matcher is the shared implementation; the supervisor retains lifecycle authority.
- Repair owned Unicode string lifetime without changing normalization semantics or disabling Unicode matching.
- Candidate filtering must be a sound superset of exact matches. Every returned result still passes the existing literal matcher and typed filters. No false negatives are allowed to make a benchmark faster.
- Measure compact per-entry/delta and filename-block postings against the uncompressed prototype; select a representation from memory and correctness evidence. Preserve stable ordering without materializing all matches.
- Short, Unicode and path candidate handling must be proven sound independently; an unsupported case must remain an explicit bounded scan, never a silent empty result. This is a correctness fallback, not acceptance of failing latency targets.
- Count candidate preparation/posting work as bounded work, separately from exact verification. The initial bounded signature design reserves at most 32 MiB for both types together; a query visits at most 500,000 blocks of 64 signature records, preserving the existing exact-verification cap separately. Prefetch blocks count against the same preparation budget. No eager candidate result array is built. Allocation failure or the fixed reservation cap retains bounded exact scanning. Diagnostics currently remain the existing examined/status/complete fields; preparation-cap exhaustion returns work_limit with complete=false, never an empty completed result. Snapshot/query construction must not hide unbounded activity behind a small examined count. Specify any public diagnostic changes before implementation.
- The query-only FD view retains NAME order, parent links and coverage without GUI index structures. Immutable entries use a snapshot-owned arena capped at 96 MiB; entry copies retain individual ownership. Valid Unicode names contribute both raw and ICU-normalized folded grams; conversion failure keeps unconditional exact fallback. Slash-free ASCII path queries may prune basename candidates only after a bounded parent-path cache proves the parent does not match.
- Retain the current 64 MiB snapshot cap, worker 256 MiB address-space ceiling, supervisor 64 MiB soft ceiling, two-second startup bound, request queue/deadline policy, private socket ownership checks and durable cleanup/quarantine semantics.
- Approved aggregate RSS ceiling: 128 MiB for one worker plus supervisor at one million names, including construction peak. Approved p95 targets: under 10 ms for selective warm socket queries and under 30 ms for designated short, Unicode and path queries at one million names. Preserve exact semantics and truthful incomplete responses when a bound stops work; incompleteness does not satisfy the performance qualification gate.
- Enforce a candidate-index construction budget before allocation growth; compact blocks alone are insufficient, as the isolated varied-filename experiment exhausted the existing 256 MiB address-space ceiling. Representation choice and safe fallback must preserve exact verification and truthful incompleteness.
- Qualify corpus diversity and peak construction/query memory; repetitive flat ASCII fixtures alone cannot establish the target behavior.
- No snapshot-update or monitoring lifecycle enters the query worker. Existing safe refresh, monitoring, replacement and file-searcher MCP work remain separate linked scopes.

## Testing Decisions

- Test observable results and lifecycle through CLI/socket rather than posting representation or private helper calls.
- Retain the new real-socket repeated-Unicode memory regression: stable results, same resident worker and bounded growth after warmup.
- Compare result order, typed filters, completeness/truncation, identity and coverage with a test-only exhaustive oracle; exclude only changing clock ages and intentionally different examined counts.
- Verify short/Unicode/path, duplicate names, high-entropy names, non-UTF-8 paths, common/selective/zero-hit queries and literal punctuation.
- Retain upstream unit targets plus direct CLI and real-service tests. Use existing fault fixtures for crash, deadline, cancellation, startup and unproved reap behavior.
- Use the approved frozen performance/resource gates before measurement. Report socket, native matcher and fresh CLI costs separately, with at least 100 warm samples per designated query and p50/p95/p99.
- Complete-search probes are reported separately from broad result-limited response timings. Complete short probe: literal `??`; complete path probe: `zz-last-rare-qvt` with path=true. The retained broad `ab` and parent-directory workloads exercise truthful result caps but do not count as complete-search performance acceptance. These probes were added with retained failing measurements before final source freeze; numerical gates are unchanged.
- Trace all query processes separately from latency and require zero indexed-root file syscalls.
- Read back installed source/artifact identity only after source and real worker/socket qualification; no fixture scan becomes a production updater.

## Out of Scope

New real-root admission/scans; whole-drive or Windows-mount indexing; production refresh/monitoring implementation; safe live snapshot replacement; file-searcher MCP implementation; public network APIs; raw-volume parsing; relaxed limits without explicit review.

## Further Notes

The current research favors native candidates over SQLite at one million names. The existing installed source is unchanged. Production installation is downstream of qualification, not proof that the unfinished indexing/adoption program is complete.
