# Native incremental filename experiment

Issue: https://github.com/CochranResearchGroup/fsearch/issues/24
Source baseline: 2f313c825b6591542d0cfbce205c530ce3c683c5.
Prototype branch: prototype/native-incremental. Keep this throwaway implementation out of master.
Predecessor: prototype/incremental-filenames at ab10fd9240dda282ebfb3b83122dae5f38ff4e21 (issue 23); accepted requirements are captured there.

## Verdict

The parent-linked overlay can preserve native literal matching result sets across incremental mutations in an owned synthetic corpus. This supports a bounded integration experiment, not production acceptance or installation.

Correctness: 3,528 complete result-set comparisons against independently mutated full paths rebuilt into real serialized FSearch snapshots, then searched through the existing headless loader. Cases include basename/path, case modes, files/folders/all, extensions, Unicode, raw bytes, literal wildcard characters, ancestor rename/delete and recreation with new identities. Invalid cycles, missing parents and retired identity reuse are rejected. At the 2,048-identity overlay cap, further updates defer while accepted results remain available with deferred coverage. Native result ordering is unqualified.

| Synthetic files | Normal visibility p95 / max | 1,000 serial creates | Worker peak RSS | Name query p95 | Path query max |
|---|---|---|---|---|---|
| 100,000 | 111.2 / 112.0 ms | 358.4 ms | 29.84 MiB | 13.39 ms | 45.43 ms |
| 1,000,000 | 202.7 / 218.9 ms | 399.1 ms | 222.03 MiB | 79.95 ms | 330.87 ms |

Normal measurements include a simulated 100 ms debounce; heavy measurements include 250 ms. Each workload contains 20 normal creates and one serial 1,000-create burst. Total measured workload times: 2.96 and 7.33 seconds. The 100k run satisfied the frozen promotion gate (<200 MiB worker peak and <30 seconds). Driver peak RSS was separately 14.53 and 14.38 MiB; adding separate peaks is a conservative bound, not a measured simultaneous aggregate peak. Both workload processes include synthetic base/overlay records and a full-path oracle fixture, but do not load the correctness snapshot.

Initial correctness run failed because newline trimming also removed an empty trailing protocol field. The parser now preserves tabs, and correctness was rerun successfully. The retained initial-failure receipt describes the failure separately from the successful run.

## Reproduction

```
CC=/usr/bin/cc uvx --with ninja --from meson meson setup /tmp/fsearch-native-incremental-build .
uvx --with ninja --from meson meson compile -C /tmp/fsearch-native-incremental-build -j 2
timeout 60s python3 src/prototypes/native_incremental_experiment.py /tmp/fsearch-native-incremental-build/src/native-incremental-prototype correctness
timeout 60s python3 src/prototypes/native_incremental_experiment.py /tmp/fsearch-native-incremental-build/src/native-incremental-prototype workload 100000
timeout 60s python3 src/prototypes/native_incremental_experiment.py /tmp/fsearch-native-incremental-build/src/native-incremental-prototype workload 1000000
```

Worker address space is capped at 1 GiB; core dumps disabled. Correctness snapshots live only in an owned temporary directory. Raw receipts are under native-incremental-evidence/. Meson target is install:false. No real roots were scanned. Only prototype comparisons and build were run; this is not a full production regression acceptance.

## Limits and next packet

Candidate queries use the authoritative native literal matcher but scan effective records; they do not integrate native signature acceleration or sorted result merging. Path queries allocate temporary parent views. The prototype has no real watcher, event-loss recovery, compaction, permission revalidation or concurrency protocol. Its serial burst is not atomic batch publication. Do not extrapolate to the 6.73-million-entry runtime or claim the 600 MiB steady / 1.25 GiB aggregate update targets are met. A no-display run does not prove GTK independence.

Next bounded packet: integrate an identity-based overlay with native candidate selection and sorted result merging in a separate source branch, still driven by synthetic events. Qualify ordering and literal/filter parity against rebuilt snapshots before introducing watcher or compaction effects.

Installed service readback after experiments: active, MainPID 94383, NRestarts 0. No installed binaries, service configuration, indexes or watcher settings changed. SysRAG remains outside this task.

Memory disposition: forbidden; durable memory writes were not authorized for this packet. A non-write receipt is retained with the evidence.
