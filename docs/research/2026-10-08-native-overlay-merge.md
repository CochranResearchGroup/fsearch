# Native accelerated overlay and ordering experiment

Issue: https://github.com/CochranResearchGroup/fsearch/issues/25
Source baseline: 9002f969ff6d67bca2b3ce110584c9cc1e86b0d5.
Capture branch: prototype/native-overlay-merge. This branch includes throwaway predecessor experiments and must stay outside master.

## Result

Native signature candidate filtering now feeds an immutable sorted base plus a separately exact-matched, bounded overlay. Matching hits merge in the native headless order: files first, folders second, basename comparator within each kind. Renamed/deleted base identities are suppressed; ancestor moves affect current path verification without rewriting descendant base signatures. Every candidate still passes the authoritative literal matcher and filters.

The existing headless signature helpers moved byte-for-byte into an internal header shared by the production search implementation and prototype. A hash/extraction check is captured alongside 20 passing existing native test groups. The production search loop and installed runtime were not changed.

4,536 full result-set and native comparator-group comparisons passed against independently mutated paths rebuilt into actual private native snapshots. 81 bounded prefix checks passed. Cases include Unicode normalization/case modes, raw-byte filenames, empty/short literals, literal wildcard characters, filters, ancestor rename/delete, retired identities, moves across sort positions, duplicate basenames in different parents and budget deferral. Exact returned sequences also matched in this fixture, but the native basename comparator has no tie-break for equal names: only comparator-group equivalence is an API-independent ordering conclusion. At a tied prefix cutoff, any member of that tie group is admissible.

The first expanded correctness run failed because the new fixture accidentally placed two identities at the identical full path. The fixture was corrected to put the duplicate basename under a different parent. The failure receipt is retained. Trusted synthetic input still does not enforce namespace collision rejection; a real event ingestion layer must qualify that separately.

## Synthetic workload

| Files | Normal visibility p95 / max | 1,000 serial creates | Name query p95 | Path query max | Worker peak RSS | Startup |
|---|---|---|---|---|---|---|
| 100,000 | 100.59 / 100.59 ms | 325.76 ms | 0.137 ms | 32.61 ms | 32.30 MiB | 0.128 s |
| 1,000,000 | 102.52 / 103.68 ms | 327.09 ms | 0.242 ms | 329.05 ms | 248.53 MiB | 1.311 s |

Twenty normal creates include simulated 100 ms debounce; the serial 1,000-create burst includes 250 ms. Query p95 uses 20 selective basename samples after the burst. Path maximum uses five samples. The selective basename query exact-examined at most 1,021 identities at either scale: 1,020 overlay entries plus one base signature candidate. This is a selective-query result, not an across-query speed guarantee. Path queries intentionally fall back to scanning, with 1,001,023 examined at 1m.

For comparison, the predecessor's recorded 1m selective basename p95 was 79.954 ms, versus 0.242 ms here, approximately 330 times faster in these separate synthetic runs. Worker peak increased from 222.03 to 248.53 MiB. Full-path maximum remained approximately 329 ms. The improvement is consistent with filtering base records through bitplanes while scanning only the bounded delta, but these runs are not a controlled production benchmark.

100k passed the frozen promotion gate (<200 MiB worker peak, <30 seconds) before the 1m run. Workload time excluding startup: 2.50 and 3.94 seconds. Driver peaks separately were 14.69 and 14.53 MiB. Worker plus driver peaks are not simultaneous aggregate measurements. The worker also holds an independent full-path synthetic fixture oracle; it is not the production snapshot representation.

## Reproduction and evidence

```
CC=/usr/bin/cc uvx --with ninja --from meson meson setup /tmp/fsearch-native-overlay-build .
uvx --with ninja --from meson meson compile -C /tmp/fsearch-native-overlay-build -j 2
uvx --with ninja --from meson meson test -C /tmp/fsearch-native-overlay-build --print-errorlogs
timeout 60s python3 src/prototypes/native_incremental_experiment.py /tmp/fsearch-native-overlay-build/src/native-incremental-prototype correctness
timeout 60s python3 src/prototypes/native_incremental_experiment.py /tmp/fsearch-native-overlay-build/src/native-incremental-prototype workload 100000
# Promote only after checking the 100k resource gate.
timeout 60s python3 src/prototypes/native_incremental_experiment.py /tmp/fsearch-native-overlay-build/src/native-incremental-prototype workload 1000000
```

Raw receipts: native-overlay-evidence/. Earlier native-incremental-evidence/ belongs to predecessor issue 24. Worker address-space limit is 1 GiB; each experiment has a 60-second timeout. Only owned temporary snapshots are serialized; no roots are scanned. The prototype target remains install:false. No-display execution is not GTK independence.

## Remaining gates

This is algorithm integration inside the prototype, not a production overlay API. Candidate/output work and byte-limit enforcement, namespace collision/type-transition validation, concurrent readers, immutable generation publication, real watcher loss/recovery and permission revalidation remain unqualified. Candidate hits are collected before response limiting; production memory and work caps require a different streaming/limited interface. This experiment shares signature primitives but does not replace the production headless search loop or snapshot loader.

The overlay cap remains 2,048 identities, with truthful deferred coverage and the accepted view searchable. There is no compaction yet. Neither the 600 MiB steady target nor the 1.25 GiB aggregate update target is proven for the 6.73m installed index. No extrapolation or real-root expansion is authorized by this evidence.

Next bounded packet: test off-thread compaction into a replacement immutable generation, atomic reader publication and update deferral against a measured aggregate memory budget, still with synthetic events. Include sustained churn, concurrent queries, generation failure and replay; defer real watcher integration until that passes.

Post-test OS readback: installed fsearch-workspace-query.service active, MainPID 94383, NRestarts 0. One serving fsearch-worker remained (PID 3338); no native-incremental prototype process remained. Installed binaries, service configuration, indexes and watcher settings unchanged. SysRAG remains outside this task.

Memory disposition: forbidden; this packet does not authorize durable memory writes. Non-write receipt retained with evidence.
