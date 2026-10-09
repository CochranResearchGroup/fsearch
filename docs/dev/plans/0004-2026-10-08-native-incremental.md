# Native incremental matcher experiment

State: CLOSED
Owner: Codex
Issue: https://github.com/CochranResearchGroup/fsearch/issues/24

## Current State
JS model accepted as an exploration direction only. Native service stays unchanged.

## Frozen scope
128-file owned synthetic correctness corpus, independent full-path mutation oracle rebuilt to a real private snapshot, native authoritative literal matching for candidate and snapshot. Case modes, basename/path, files/folders/all, extensions, Unicode and raw-byte filenames. Compare complete result sets; report ordering as unqualified unless directly checked. Budget deferral must preserve prior view. No actual watcher or filesystem confinement claim.

Performance: 100k synthetic files, 20 normal creates (100 ms debounce), one 1,000-create batch (250 ms debounce), native query visibility and process RSS/peak. Permit 1m only if 100k peak <200 MiB and elapsed <30 seconds. 60-second run timeout and 1 GiB address-space limit; capture all failures. One process contains base/overlay and oracle fixture; no production memory extrapolation. Correctness and resource verdicts stay separate. No native signatures/ordering integration or real-root indexing is implied by this seam experiment.

## Completion
Publish experiment source/receipts/verdict on prototype/native-incremental and link tracker; keep out of master. Identify one bounded source integration successor or a precise blocker.

Outcome: 3,528 comparisons pass; 100k and gated 1m runs complete. See docs/research/2026-10-08-native-incremental-prototype.md. Native ordering, actual watcher, compaction and aggregate production qualification remain open.
