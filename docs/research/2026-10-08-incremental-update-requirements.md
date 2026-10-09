# Agreed incremental-update requirements

Date: 2026-10-08
Status: requirements accepted; prototype not started
Owner: Codex

The operator answered “yes all” to the two recommendations presented after the memory research. This records shared understanding of those requirements. It does not claim the targets have been achieved.

## Accepted targets

For the current 6,734,348-entry workspace corpus:

- Created, renamed and deleted filenames should be reflected in searchable knowledge within one second under normal activity, allowing up to ten seconds during heavy activity.
- Target steady aggregate resident memory of at most 600 MiB, including the query service and any continuous update/watcher processes.
- Budget at most 1.25 GiB aggregate resident memory during updates, counting serving, watcher, builder, validator and replacement processes together.
- When an update would exceed the budget, defer it and keep the last accepted snapshot searchable. Report deferred/stale/incomplete coverage explicitly; a deferred update is an exception to the freshness target, not a successful timely refresh.

The numeric budgets apply to this corpus. They are not automatically whole-Ubuntu or twenty-million-entry acceptance limits. Existing filesystem admission, no-symlink/no-cross-mount confinement, private cached visibility and exact-match verification remain applicable.

## Next bounded experiment

Prototype incremental create/delete/rename handling against owned synthetic roots, with an immutable base and bounded changes as a candidate design. Compare results with an exhaustive oracle, preserve Unicode and literal semantics, and exercise directory moves, missed events, overflow, restart and deferred updates. Measure aggregate memory and mutation-to-search visibility, including debounce and queue delay. Freeze concrete normal/heavy mutation workloads and measurement conditions before qualification; these workloads are not yet specified. Watch admission cost and compaction peak must be counted rather than omitted.

No production activation, additional root indexing, privileged helper or physical-disk investigation is implied. The accepted service stays available. This requirements record does not select a final storage representation or establish an incremental implementation.

## Provenance

[Memory and update research](2026-10-08-memory-and-incremental-updates.md), [installed workspace acceptance](2026-10-08-workspace-index.md), GLOSSARY.md and ADRs 0001–0003. Targets are reversible product requirements, so no new architectural decision record is warranted yet.
