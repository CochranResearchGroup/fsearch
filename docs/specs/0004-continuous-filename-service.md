# Continuously indexed filename service: remaining delivery specification

Status: DRAFT for seam/breakdown review; Plan0006 remains canonical for milestones and frozen gates.
Owner: ecochran76; implementation owner: Codex
Date: 2026-10-09
Parent: https://github.com/CochranResearchGroup/fsearch/issues/26

## Problem Statement

The approved workspace has fast cached filename search, but continuous indexing is not installed. The current inode-per-directory event source has failed its startup/resource qualification. Small parser and state fixtures have improved source correctness without delivering an assembled replacement. The operator needs reliable continuous search without workstation sluggishness, concealed event loss or unsafe filesystem observation.

## Solution

Complete an assembled, reviewable broker candidate; qualify its real event source and confinement; make recovery durable; prove combined freshness, query and memory targets; then adopt it reversibly through the normal CLI/MCP with the full operational soak. Preserve the accepted snapshot and useful cached queries throughout failures. Work stops at outcome checkpoints, while supporting edits and tests proceed inside each outcome.

## User Stories

1. As an operator, I want the entire approved workspace continuously indexed, so searches include recent filename changes.
2. As an agent, I want normal CLI and MCP tools to access the same accepted generation, so backend internals do not change my workflow.
3. As an operator, I want normal changes visible within one second, so discovery feels immediate.
4. As an operator, I want heavy changes visible within ten seconds, so sustained work remains searchable.
5. As an operator, I want all persistent service and kernel memory within600MiB, so indexing does not make the workstation sluggish.
6. As an operator, I want update peaks within1.25GiB with no acceptance through swap, so compaction remains bounded.
7. As an agent, I want exact literal/filter results and truthful truncation, so a fast incomplete response cannot imply no matches.
8. As an agent, I want raw filename bytes preserved, so non-UTF-8 names remain discoverable.
9. As an operator, I want ancestor moves and directory replacements handled, so entire subtrees do not become incorrect.
10. As an operator, I want hard links treated as distinct directory entries, so aliases remain searchable independently.
11. As an operator, I want indexing confined to approved roots, with the bounded formerly-admitted-descriptor transition exception in ADR0005; unrelated names must never be exported or logged and outside destinations must never be followed.
12. As an operator, I want any wider kernel observation described before activation, so approval refers to the actual effect.
13. As an operator, I want privilege removed after setup, so a long-running privileged reader is not silently introduced.
14. As an agent, I want explicit pending/deferred coverage after a source gap, so cached visibility is not mistaken for current coverage.
15. As an operator, I want bounded reconciliation and cleanup, so failures cannot accumulate watcher or builder processes.
16. As an operator, I want the last accepted generation available during update failure, so discovery stays useful.
17. As an operator, I want durable checkpoint/replay and truthful restart, so crashes do not lose accepted updates silently.
18. As an operator, I want aggregate resource measurements at current scale during actual churn, so isolated component results cannot mask pressure.
19. As an operator, I want a24-hour synthetic soak before adoption, so delayed growth and event-loss bugs are exposed.
20. As an operator, I want reversible installation and direct fresh-client acceptance, so source readiness cannot masquerade as runtime success.
21. As an operator, I want a72-hour installed soak, so operational reliability is proved over sustained use.
22. As an operator, I want optional Everything and SQLite fallback preserved, so this Linux work does not remove existing discovery routes.
23. As an operator, I want meaningful end-to-end checkpoints, so work sessions advance an operational outcome rather than stop after component tests.
24. As an operator, I want failed evidence retained and caps unchanged, so acceptance cannot be manufactured by changing the requirements.

## Implementation Decisions

- Plan0006 is the program authority. This specification elaborates its remaining M3–M6 delivery; it replaces none of its targets, dependencies, soak durations or admission rules. Glossary and ADRs retain domain/architecture authority.
- Immutable catalog generation, native matching and bounded worker transport already have source acceptance. Preserve them; integrate broker events through the existing updater and private catalog mutation seam. Query workers remain isolated from root metadata operations.
- The candidate source uses a single filesystem notification mark with subtree-only export. Kernel collection is filesystem-wide and requires separate explicit observation/capability approval. Neither the specification nor ready labels authorize activation.
- Prefer a minimal setup launcher that passes a descriptor to an unprivileged broker and exits. Capability lifetime and continued descriptor behavior are proof obligations. No permission events, network listener, content indexing or arbitrary outside handle resolution.
- Root generation, mount/filesystem identity, raw basenames and opaque directory handles govern admission. Cached membership is insufficient: validate rooted identity before and after metadata operations, discard/report a gap on an ancestry change, and qualify adversarial moves under ADR0005's operator-approved bounded transition exception. No initially outside object is admitted.
- Bootstrap requires a clean accepted baseline and source-drain cut. Current conservative dirty-baseline rejection is supporting source, not evidence of a viable current-scale startup strategy. Candidate acceptance must show bounded startup under the frozen workload; design revisions are allowed without changing the final contract.
- Event loss, unknown identity, backpressure, expired source lease and failed reconciliation expose deferred coverage while accepted queries remain usable. No blind retries after unproved cleanup.
- Directory creation/move-in requires bounded inventory; move-out revokes admission before export. Parent/name mutations preserve directory-entry identity and cannot resurrect retired descendants.
- Durable recovery serves an accepted generation promptly, then catches up separately. Filesystem durability assumptions and fsync/publication boundaries are explicit; a full rescan on every restart is insufficient.
- Resource qualification includes setup, broker, kernel queue/marks, updater, catalog, retained readers, builder and supervisor together. Record fixture allocations separately without moving service charges outside the envelope.
- Freeze query corpus, seeds, mutation rates, concurrency, deadlines and measurement method before qualification. Keep workload source identity and raw failure receipts. Actual event-to-query timestamps begin at mutation.
- Four outcome tickets form the delivery spine: assembled source candidate; actual privileged source qualification; durable/reliable current-scale service; reversible installed adoption. Supporting work can proceed within each ticket, but cannot close it independently. One owner controls the critical integration lane.

## Testing Decisions

- Main acceptance boundary: owned mutations followed by normal CLI and fresh MCP search/coverage responses through the actual assembled service. Assert externally visible results, sequence/generation consistency, truthful coverage and bounded process/resource behavior.
- Existing actual CLI/MCP contracts, rebuilt-snapshot parity oracles, updater faults and source-progress controls are prior art. Reuse these seams rather than inventing a separate demo API.
- Binary/parser tests remain supporting tests. A synthetic ordinary-descriptor event adapter can prove wiring and failure behavior, but cannot prove fanotify delivery, privilege drop or containment.
- Actual owned-root tests qualify create/delete/rename, ancestor moves, replacement, hard links, raw names, ignored paths, symlinks, mount/identity changes and adversarial move races before workspace exercise.
- Failure controls cover startup cuts, event overflow, unrelated-filesystem churn, source stalls, receiver backpressure, dirty bootstrap, inventory gaps, broker death, unproved reap, checkpoint crashes and corrupt replay. A known probing control validates no-query-root-probe instrumentation.
- Source candidate review has Standards and Spec axes. Accepted blocking findings require bounded remediation; nonblocking findings do not reset acceptance or start endless review.
- Scale stages are100k,~300k,1m,~3m,exact current count,10m;20m requires a separate envelope. All Plan0006 frozen query/freshness/resource gates apply.24hsynthetic and72hinstalled soaks must run for their full durations.
- Document correctness, confinement, delivery, resource, durability and integration verdicts separately. A controlled deferred result is a successful failure control, not performance acceptance.

## Out of Scope

New roots, whole-Ubuntu/Windows/Drive scans, replacing Everything, content indexing, network exposure, private-data export, SysRAG unpark, disk repair/reboot, unrelated process cleanup, silent runtime activation, weakening caps, shortened soaks and wholesale prototype merges.

## Further Notes

Source custody: feat/incremental-generations, bootstrap checkpoint a23d5ef32abd730cf4645e76026e0216cb71ee5b. Fifteen synthetic parser/state tests pass. Installed service was unchanged by these source packets; this is not a current installed identity claim. Native M3 issue29 remains open; parent26 remains open. Historical blocked audits remain historical, not current goal-control state. The most recent next-checkpoint goal completed; no new goal is inferred from this planning task.

Review boundary: source design/implementation may proceed within standing authority; actual filesystem-wide observation and privileged activation need explicit approval against the assembled packet. Duration does not replace an evidence gate. Checkpoint at the assembled candidate outcome or a verified hard stop, with substantive progress updates throughout.
