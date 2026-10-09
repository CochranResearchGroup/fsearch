# Plan 0006: continuously indexed, production-qualified filename service

State: OPEN / IN_PROGRESS
Owner: ecochran76
Implementation owner: Codex
Tracker: https://github.com/CochranResearchGroup/fsearch/issues/26
Parent: https://github.com/CochranResearchGroup/fsearch/issues/1
Related adoption/storage work: https://github.com/CochranResearchGroup/fsearch/issues/5
Planning source baseline: 2f313c825b6591542d0cfbce205c530ce3c683c5
First packet: M1 native immutable generations and compaction, in progress under operator execution direction on 2026-10-08.

## Destination and completion rule

Deliver an always-warm Linux filename service behind file-searcher's normal CLI and MCP tools, continuously tracking the entire approved local workspace. Searches remain useful during sustained changes, failed updates, restart and resource pressure. Windows filename coverage stays with optional Everything integration; SQLite fallback remains useful without FSearch.

Close this plan only when M1–M6 pass, production source and frontend integration are published with exact identities, the installed service passes direct CLI/MCP acceptance, and the operational soak passes. Passing an experiment, completing source work or installing a package alone does not complete the program. Record failed gates and remaining work explicitly; do not turn deferred updates or incomplete searches into apparent acceptance.

Operator directed execution of Plan 0006 on 2026-10-08, with pressure monitoring and a checkpoint before three hours or two million tokens. Implementation uses bounded milestone packets. Real-root qualification and installed activation must follow the operator's execution direction and existing root admission; this plan introduces no additional root admission, disk-health conclusion or installation effect.

## Authoritative starting evidence

- The published workspace implementation is on master at the planning baseline. Installed native identity last recorded as e0ec8e758db755dbd3cf8b3a83c9e4a467c50137; the installed frontend identity was 13de343bbed79f4214d844532b7136b0c3e8c10e. Re-read both before implementation or installation claims.
- The accepted workspace snapshot last recorded 6,115,587 files and 618,761 directories (6,734,348 entries), 132,313,886 bytes on disk. Root: `/home/ecochran76/workspace.local`. The workspace-wide service serves a cached snapshot; continuous workspace monitoring is not installed. These are historical locators, not current runtime proof.
- [Accepted requirements and memory research](https://github.com/CochranResearchGroup/fsearch/blob/ab10fd9240dda282ebfb3b83122dae5f38ff4e21/docs/research/2026-10-08-incremental-update-requirements.md) distinguish targets from proven performance.
- [Native overlay experiment, issue 24](https://github.com/CochranResearchGroup/fsearch/blob/9002f969ff6d67bca2b3ce110584c9cc1e86b0d5/docs/research/2026-10-08-native-incremental-prototype.md): parent-linked mutations preserve native literal result sets in synthetic fixtures.
- [Accelerated merge experiment, issue 25](https://github.com/CochranResearchGroup/fsearch/blob/2c4ce4d7e164acd38cd8beeafe2c843f055a19e1/docs/research/2026-10-08-native-overlay-merge.md): 4,536 comparisons, 81 bounded prefixes and 20 native test groups pass; at 1m synthetic files selective basename p95 was 0.242 ms, worker peak 248.53 MiB. Path fallback remained a scan. Compaction, durable event ingestion and production bounds were not qualified.

The prototype branches contain throwaway experiments. Do not merge them wholesale. Port only reviewed implementation slices to branches based on current master, with source tests and production contracts. Domain authority remains GLOSSARY.md and docs/adr/; this document is the program plan, not a competing glossary or architecture decision record.

## Product contract and measurement gates

### Accepted resource and freshness targets

At the current approximately 6.73m-entry workspace:

| Property | Acceptance gate |
|---|---|
| Normal create/rename/delete visibility | Every event in the frozen normal workload searchable within 1 second of the filesystem mutation |
| Heavy change visibility | Every event in the frozen heavy workload searchable within 10 seconds; no silent event loss |
| Aggregate steady memory | At most 600 MiB after warmup, including serving, watcher/updater, supervisors and other program-owned persistent processes |
| Aggregate update memory | At most 1.25 GiB during compaction, validation and replacement, including old/new readers, builder, validator, replay buffers and watcher |
| Budget exhaustion or failed update | Preserve the last accepted generation, defer atomically, and expose truthful stale/incomplete/deferred coverage; no unbounded retries or accumulating workers |
| Correctness | No missing eligible matches or false returned matches versus exhaustive native/rebuilt-snapshot oracles in qualification; every returned match passes authoritative literal matching and filters |

Measure simultaneous aggregate memory across all relevant processes/cgroups, not only the serving unit or a sum of independently observed peaks. Report RSS/PSS, cgroup current/peak and swap separately; do not use swapping to claim the working-set target is met. Attribute fixture-driver memory separately and explain fixture-only allocations. Account for allocator retention, file-backed memory and overlapping generations; preserve the measurement method and raw receipts.

Freshness begins at the actual filesystem mutation in installed tests. Synthetic tests must identify injected timestamps and simulated debounce separately. A watcher acknowledging an event is not search visibility. Cached visibility is not current permission verification. Coverage includes generation identity, last reconciled point, oldest unapplied event, event-loss state, deferred reason and exact approved roots, without probing roots during queries.

### Proposed query and endurance gates to freeze before benchmarking

These are planning targets, not previously accepted measurements. M1/M2 must freeze the dataset seeds, query corpus, event rates, concurrency, percentile calculation, deadlines and response limits before collecting acceptance timings. If implementation evidence makes a target infeasible, retain the failure and request an explicit rebaseline rather than quietly weakening the target.

- Warm end-to-end native basename query p95 <=10 ms for selective and zero-hit queries; p95 <=100 ms for common/short literals with a 1,000-result cap. Include extension/kind filters, Unicode, punctuation and non-UTF-8 cases. Report completion/truncation and examined work for each class; a fast timeout does not pass a query gate.
- Warm path-query p95 <=250 ms for a representative frozen corpus at current scale. Slash-containing, ancestor-only and Unicode paths must be represented; unsupported acceleration falls back truthfully within the declared work budget.
- Measure normal CLI and MCP p50/p95/p99 separately from native matcher time. Proposed warm CLI/MCP p95 <=150 ms for the selective basename corpus, with no per-query scan, snapshot reload or process-tree accumulation.
- Freeze normal and heavy event workloads, including sustained churn across multiple compactions, bursts, ancestor moves, deletes/recreates and duplicate basenames. Use at least four concurrent clients through the bounded queue; preserve the existing serial active-query contract unless a separate ADR justifies changing it.
- No query-time indexed-root metadata probes, monitors or root polling in the instrumented query-only lifecycle. Use a known probing negative control to prove instrumentation sensitivity.
- A 24-hour current-scale synthetic soak precedes a 72-hour installed operational soak. Include periodic failures, restart tests and repeated generation changes; no progressive memory growth, unexplained process accumulation, stale-state concealment or unreconciled event loss.
- Larger synthetic datasets advance in roughly half-decade steps: 100k, approximately 300k, 1m, approximately 3m, 10m. Test the exact current entry count as an additional release gate. A 20m stretch run requires a separately frozen synthetic resource envelope after 10m succeeds; it does not change current-scale memory acceptance or authorize whole-Ubuntu indexing.

Cold startup/load, full construction, compaction, catch-up and restart times are recorded separately. Freeze explicit deadlines for each in the relevant packet before executing it. Do not reset deadlines, raise installed caps or discard outliers to obtain a pass.

## Milestones and dependencies

### M1 — bounded compaction and atomic generation publication

Status: SOURCE_ACCEPTED. Child issue: https://github.com/CochranResearchGroup/fsearch/issues/27. Evidence: [M1 acceptance](../notes/2026-10-08-plan6-m1-generations.md). Synthetic fixtures only.

Build an immutable replacement generation from base plus accepted overlay while readers retain a consistent generation. Bound the builder, replay log and number of retained generations. Establish a publication protocol that cannot lose events arriving during construction; choose sequence/checkpoint and crash semantics explicitly rather than assuming pointer replacement solves replay.

Acceptance:

- Queries overlapping compaction observe one complete generation; no mixed parent/name state, use-after-free, identity reuse or lost accepted mutation.
- Sustained synthetic churn crosses at least three compaction boundaries; exhaustive oracle and ordered-group/prefix comparisons pass throughout. Equal-basename ties retain the native comparator contract unless a separately reviewed decision adds a tie-break.
- Inject builder failure, validation failure, publication failure, lagging reader, replay overflow, allocation pressure and shutdown at phase boundaries. Failures preserve the accepted generation and expose deferral; unproved cleanup quarantines update activity.
- Measure simultaneous builder/reader/updater aggregate peak. Enforce the frozen budget before admitting overlapping work, including reserve for event replay and bounded output. Reclaim old generations only after their readers release them.
- Record source/build identities, initial failures and successful reruns. State the precise memory/lifetime model and remaining production integration gaps.

Exit artifact: source slice or experiment, correctness/resource receipts and a concrete M2 integration design. M1 passing does not authorize installing a prototype.

### M2 — production bounded native query/overlay engine

Depends on M1. Status: PENDING.

Port the qualified design into real native source using shared candidate primitives, parent-linked stable entry identities, native exact matching and sorted base/overlay merging. Define collision, type-transition, rename and retired-identity handling. Treat directory entries distinctly from inode identity so hard links remain correct.

Acceptance:

- Candidate selection is a superset of native matches. Unicode/raw-byte uncertainty, short literals and paths have explicit bounded fallback. Exact result-set and ordering-group parity pass against independent rebuilt snapshots and exhaustive matching.
- Work, queue, input, result count, response bytes, time and allocation limits apply during candidate collection/merge, not after collecting every hit. Broad or adversarial queries return truthful completeness/truncation without unbounded hit buffers.
- Test ties at limited-prefix cutoffs, path mutations, filters, event duplicates/reordering, namespace collisions and file/directory replacement. No retired identity or descendant resurrects after deletion/recreation.
- Current native regression suite and file-searcher contract tests pass. Preserve upstream GUI behavior, optional backend behavior, SQLite fallback and versioned JSON/path-byte representation.
- Freeze and measure the proposed query gates; record limitations by query class. A native-only speedup does not establish CLI/MCP acceptance.

Exit artifact: reviewed production implementation and API contract, with M1 lifecycle integrated and source-bound validation.

### M3 — contained continuous indexing and reconciliation

Depends on M2. Status: PENDING.

Connect a separate contained watcher/updater to approved roots. Coalesce redundant events, retain bounded sequence/replay state, detect queue overflow and handle excluded mounts before metadata access. Reuse existing confinement and quarantine rules; query workers remain isolated from indexed-root operations.

Acceptance:

- Real event semantics first pass on owned fixture roots: creates, renames, ancestor moves, deletes/recreates, hard links, symlinks, ignored paths and mount-boundary changes.
- Overflow, watch exhaustion, startup gaps, missing/offline roots and lost/duplicate/out-of-order events produce explicit degraded coverage and bounded reconciliation. Do not claim complete freshness while an event gap is unresolved.
- Reconciliation cannot broaden root scope or retry a possibly blocked worker without proven cleanup. One stalled root does not prevent queries against the last accepted view.
- Measure event-to-query visibility with actual mutations; prove normal/heavy gates on owned fixtures before the already-approved workspace is exercised.

Exit artifact: contained ingestion/reconciliation source and failure-injection evidence. No real-root expansion follows from fixture success.

### M4 — durable restart and recovery

Depends on M3. Status: PENDING.

Specify checkpoint, replay and accepted-generation persistence. Start serving the last qualified private generation promptly, then catch up through a separately contained updater. Startup readiness must mean query acceptance, not just process existence.

Acceptance:

- Crash tests cover each checkpoint/append/fsync/publication boundary, interrupted compaction, corrupt/truncated replay and invalid snapshots. Recovery either reconstructs a correct view or serves the last accepted view with truthful gap/deferred state.
- Prior-boot snapshots, process stop/start, duplicate replay and event gaps cannot silently publish an incomplete current generation. Filesystem durability assumptions are explicit and qualified.
- No automatic rescan inside query startup; no restart storm, orphan workers or accumulating watch/builder trees. Owner-only snapshot/socket permissions and path bytes remain intact.
- Recovery tests bind source identity, artifacts, observed generation and resource/process readback.

Exit artifact: restart/recovery contract and passing crash/startup matrix.

### M5 — scale and whole-service resource qualification

Depends on M1–M4. Status: PENDING.

Run staged synthetic scale tests, then qualify the exact current approved workspace under a frozen workload and execution envelope. Use owned temporary trees for destructive/fault cases; do not inject disk faults or destructive churn into personal workspace data.

Acceptance:

- At the exact current dataset scale, all accepted freshness/resource gates and frozen query gates pass together during sustained churn and compaction, not in independent best-case runs.
- Report names/paths/filter classes, zero/common/rare hits, p50/p95/p99/max, CPU, construction/compaction times, stored size, candidate work, memory/swap, queue age and reader/replay pressure.
- A 24-hour synthetic soak passes. Prove bounded degradation and recovery under pressure; a resource-deferred run is a correctly handled failure, not target acceptance.
- Stage advancement requires the previous stage's frozen gates and a host-pressure preflight. Halt the owned experiment on sustained host pressure or budget breach, retain evidence and preserve the serving generation. Larger synthetic success does not substitute for current-workspace acceptance or admit new roots.

Exit artifact: acceptance matrix with exact source, workload and scope, complete aggregate receipts, retained failures and an installation/rollback candidate.

### M6 — reversible installed CLI/MCP acceptance and operational soak

Depends on M5 and operator-directed installation. Status: PENDING.

Publish coherent production changes in fsearch and file-searcher through their respective workflows. Install versioned artifacts, preserve the prior runtime/configuration for rollback and activate only the approved workspace. Refresh installed identities before comparing acceptance evidence.

Acceptance:

- Exact source/build/package identities and passing CI are recorded for both repositories. Frontend launchers, stored MCP registration, socket, service units and snapshot/generation identify the intended installation.
- Normal CLI and a fresh MCP client pass representative search, filter, path-byte, freshness, truncation, fallback and degraded-state cases. Cached results never masquerade as current access checks.
- Startup/readiness, stop/start, bounded update failure and rollback are exercised. Use fresh OS process/cgroup readback to prove absence of orphan workers and unexplained resource growth; service status alone is insufficient.
- The 72-hour installed soak passes while querying and continuously updating the approved workspace. Freeze the workload, low-impact owned fixture mutations and resource sampling before starting. Retain operational failures and require a full relevant rerun after a repair.
- Final acceptance publishes current counters, root scope, source/runtime identities, limits, evidence, rollback instructions and any explicitly accepted limitations. Issue 26 and this plan close only then; storage assessment in issue 5 retains its own independent disposition.

## Program controls and restart-safe continuation

Each implementation packet names its milestone, source branch/worktree, issue, frozen workload, resource/deadline limits, pass/fail criteria and evidence artifact before execution. Create child issues when a concrete slice begins; do not create a speculative implementation queue that obscures dependencies. Keep issue 26's checklist and this plan reconciled at milestone boundaries.

At resume: read this plan and issue 26; verify current master, dirty worktrees and installed service identity; inspect the latest milestone receipt; distinguish completed source from installed authority. Do not restart completed experiments just to recover context. Pick the first unpassed dependency and one bounded packet; retain the accepted generation and unrelated work.

A failed gate keeps the milestone/program open. Record the original failure and subsequent correction separately. Stop dependent effects when a correctness/resource/confinement gate fails; continue useful analysis and repairs within the authorized packet. Changes to root scope, accepted resource/freshness limits or completion criteria require an explicit operator rebaseline, not a report-only exception.

Out of scope: content indexing, whole-Ubuntu/Windows/Google Drive scans, replacing Everything, network exposure, private-data export, disk repair/reboot, unparked SysRAG work and silent runtime activation. No-display qualification does not imply GTK independence.

## Milestone ledger

| Milestone | State | Evidence / remaining gate |
|---|---|---|
| M1 | SOURCE_ACCEPTED | [Lifecycle, native oracle, sanitizer and resource receipts](../notes/2026-10-08-plan6-m1-generations.md); installed acceptance remains M6 |
| M2 | PENDING | Production integration and bounded query interface |
| M3 | PENDING | Contained watcher, loss detection and reconciliation |
| M4 | PENDING | Durable checkpoint/replay and crash/startup matrix |
| M5 | PENDING | Current-scale aggregate acceptance and 24-hour synthetic soak |
| M6 | PENDING | Installed CLI/MCP acceptance, rollback and 72-hour operational soak |

Planning closeout: document/tracker publication only; no implementation or runtime effect. Memory disposition: forbidden; durable memory writes are not authorized by this planning packet. Preserve a non-write receipt with the planning evidence.
