# Incremental filename prototype verdict

Date: 2026-10-08
Status: synthetic state-model experiment complete; native integration unstarted
Tracker: https://github.com/CochranResearchGroup/fsearch/issues/23
Branch: prototype/incremental-filenames (throwaway; do not merge into master)
Baseline: 2f313c825b6591542d0cfbce205c530ce3c683c5

## Answer

**Proceed to a bounded native experiment.** Stable directory-entry identities plus immutable base records and a bounded overlay can represent incremental changes without scanning/rebuilding the base on each mutation. One ancestor rename changes descendant paths through parent links; deleting an ancestor hides its descendants; recreating the same name with a new identity does not resurrect old descendants. Retired identities must not be reused. These are model findings, not production acceptance.

One shared pure JavaScript model lives in [the self-contained demo](../../src/prototypes/incremental-filenames.html); [the Node experiment](../../src/prototypes/incremental-experiment.cjs) extracts and executes that exact script. No production code or service was changed. Node v24.18.0, 512 MiB V8 old-heap ceiling, 45-second run deadlines. RSS is not bounded by the V8 heap ceiling; process RSS was measured separately.

## Reproduce

Open src/prototypes/incremental-filenames.html directly in a browser. It has free-play actions, current cached state and guided directory-rename, delete, lost-event and budget-deferral walkthroughs. Everything is local and self-contained.

Run from the prototype worktree:

```sh
node --max-old-space-size=512 src/prototypes/incremental-experiment.cjs correctness
timeout 45s node --expose-gc --max-old-space-size=512 src/prototypes/incremental-experiment.cjs workload 100000
timeout 45s node --expose-gc --max-old-space-size=512 src/prototypes/incremental-experiment.cjs workload 1000000
```

This is an experiment driver with oracle assertions, not a production test suite. Frozen workload and promotion gate are in [plan 0003](../dev/plans/0003-2026-10-08-incremental-prototype.md). The 100k run met the gate (under 30 seconds and peak RSS below 200 MiB), permitting 1m. No larger experiment was attempted.

## Evidence

[Correctness receipt](incremental-evidence/correctness.json): 70 exhaustive comparisons against an independently maintained full-path map, using 1,000 files. Cases include create/delete/rename, nested ancestor move, ancestor deletion/recreation, literal punctuation and Unicode in case-sensitive strings, rejected cycles/outside parents/invalid basenames/synthetic symlink and mount admission, event loss, restart/offline coverage, explicit reconciliation and atomic budget deferral. Failed batches do not modify accepted changes. Mutation paths did not enumerate base entries. Query paths do enumerate them.

| Synthetic workload | 100,003 base records | 1,000,003 base records |
|---|---:|---:|
| Normal visibility p95 / max, 20 creates | 146.04 / 172.98 ms | 919.73 / 921.69 ms |
| Heavy visibility, one 1,000-create batch | 295.60 ms | 1,059.05 ms |
| Base RSS | 102.08 MiB | 436.05 MiB |
| Peak RSS including compaction | 151.46 MiB | 582.18 MiB |
| Compaction duration | 27.73 ms | 523.05 ms |
| Total run | 3.24 s | 17.93 s |

[100k raw receipt](incremental-evidence/100k.json), [1m raw receipt](incremental-evidence/1m.json). Normal timing includes an intentional 100 ms debounce before each create; heavy timing includes 250 ms before the batch. Both include full query visibility checks. These measure synthetic event-submission-to-model-query visibility, not filesystem-mutation-to-native-query latency. Each run is one process; fixture/model/temporary query allocations are included. There is no native service, kernel watcher, parallel builder, filesystem event queue or realistic concurrent workload in these measurements. No slope from JS memory to native six-million-entry memory is warranted.

The demo rendered successfully in a fresh headless Chrome profile, with the expected initial coverage and nested Unicode path. [Browser receipt](incremental-evidence/browser-render.json). Guided clicks were not browser-automated; transitions are exercised through the shared model experiment. The owned browser process group was cleaned up and profile removed.

## What remains unproved

- Exact native matcher parity, ordering, Unicode/ICU case folding, non-UTF8 names and existing candidate limits. The model intentionally uses case-sensitive JavaScript string matching.
- Native overlay/query merging, signature maintenance and compaction. This JavaScript prototype scans the full base for queries; one-million-file normal samples already approach one second.
- Real filesystem ingestion and permission/mount/symlink confinement. Synthetic rejected events are state-model cases, not kernel security qualification.
- Coverage and kernel memory for approximately 619,000 directory watches. No watcher is installed or modeled as a measured resource.
- The accepted 600 MiB steady and 1.25 GiB aggregate update budgets at 6,734,348 real entries. The prototype entry-count cap demonstrates atomic deferral semantics, not byte-aware admission.
- Persistent replay and downtime recovery. Restart/overflow/offline mark cached coverage incomplete and block new deltas until supplied authoritative reconciliation. Supplying a fixture is not a recovery algorithm.
- Event-source identity and ordering: stable per-directory-entry identities must distinguish hard links and reused inode identities, and rename-overwrite events must retire displaced entries. The model assumes ordered validated events; sibling-name collision detection is not implemented.

Compaction in the measured workload copies records and constructs another map, increasing RSS. The direction therefore removes rebuild work from ordinary mutations but does not eliminate compaction overlap by itself. Avoid claiming that an overlay automatically solves memory pressure.

## Next bounded native packet

Prototype an identity-keyed delta filter/merge at the existing headless snapshot seam, preserving the authoritative native literal matcher. Start at 100k owned synthetic names and compare create/delete/rename results with an exhaustive native oracle, then consider 1m after frozen resource gates pass. Count all serving/update/compaction processes and candidate allocations. Retain truthful incomplete coverage and atomic deferral. Keep collection, directory-watch scale and production rollout as separately qualified concerns. Do not copy this JavaScript model into production or enable whole-workspace rebuilding after each event.

## Runtime and custody

Installed workspace query service remained active with MainPID 94383 and zero automatic restarts. No real roots were scanned, no services restarted, no user routing changed. Research and accepted requirement records are included on this prototype branch for restart-safe provenance, with glossary terms preserved. Prototype source, evidence and verdict are committed on the dedicated branch and linked to #23; no main integration is intended. Durable personal/graph memory is not written; explicit forbidden disposition is recorded separately.
