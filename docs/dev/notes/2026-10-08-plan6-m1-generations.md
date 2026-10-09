# Plan 0006 M1: native immutable catalog and bounded compaction

State: SOURCE_ACCEPTED. Parent #26; child #27. Installed acceptance: NOT RUN.
Source baseline: 2f313c825b6591542d0cfbce205c530ce3c683c5.
Branch: feat/incremental-generations. Tested input/binary hashes: plan6-evidence/m1-tested-inputs.json.

## Delivered behavior

Production library source now contains a packed immutable filename catalog, bounded copy-on-write overlays, stable never-reused entry identities, pinned reader lifetimes, namespace/cycle/type-transition checks and sequence validation. One background compaction reserves replacement memory, captures a consistent view, constructs and validates a new base, then replays accepted changes under the owner lock before atomic publication. Old readers retain their own valid generation; reclamation follows the last reference.

Replay overflow, failed allocation/construction/validation/publication, retained-reader limits and shutdown prevent publication and preserve accepted state with an explicit deferred reason. Mutation allocation and overlay-budget failures do not advance sequence. The source performs no filesystem operations. The catalog is a reusable library component; it is not yet the production serving engine. ADR 0004 records its ownership/publication contract.

## Evidence and precise limits

- All 24 native Meson test groups pass. New tests cover immutable views, four compactions with 400 mutations, four concurrent readers, ancestor deletion/recreation, namespace collisions, cycle/type rejection, replay overflow, retained-reader budgets, memory allocation failures and shutdown boundaries.
- A separate fault executable compiles the exact production implementation with test-local allocation interception. Allocation failures at initialization, mutation, ticket creation, candidate construction and publication preserve state and release reservations. Corrupting a replacement parent fails validation and revokes an earlier validation success. No testing backdoor is installed.
- 4,320 catalog/native-matcher result and comparator-group comparisons plus 30 limited prefixes pass against an independently mutated owned filesystem, rebuilt through the real native snapshot builder and resident query worker. Ten phases span three background builds/publications, concurrent accepted replay changes, ancestor deletion, recreation with fresh IDs and post-delete compaction. The test adapter uses the real catalog APIs and native literal matcher; it is not the production accelerated query loop. Equal-basename tie order remains unspecified.
- Targeted ASan/UBSan lifecycle and allocation/corruption suites pass, including reader views retained after catalog destruction. Catalog/test source is instrumented; the existing native matcher static archive is not fully instrumented by these targeted binaries.
- Pressure guard positive controls actually stop an owned timeout and an over-budget memory allocation. The full suite and scale runs use isolated transient user cgroups with MemoryMax 1.25 GiB, swap disabled, CPUQuota 150%, Nice 10 and IOWeight 10. Each scale stage has a 60-second deadline and advances only after the prior stage passes.

| Synthetic entries | Four-compaction workload | Maximum compaction + oracle check | Exact cgroup memory peak |
|---|---|---|---|
| 100,000 | 1.078 s | 301.7 ms | 24.03 MiB |
| 300,000 | 3.076 s | 779.7 ms | 52.42 MiB |
| 1,000,000 | 11.560 s | 2,776.2 ms | 122.93 MiB |

Every scale run accepted 400 mutations and verified all live entry names/parents against an independent deterministic oracle, with sampled descendant path checks. Four reader threads exercised pinned paths and authoritative literal matching concurrently. Cgroup peaks include the fixture generator, reader threads, builder, allocator retention and guard process; swap peak was zero. These catalog-only runs do not include the final native signature/sort index, real watcher, checkpoint or existing production snapshot representation. They do not establish the 6.73m production memory/freshness/query targets.

Initial regression launches failed before tests due to missing uvx in the transient service PATH and an incorrectly guessed absolute path. Both are retained separately; verified /home/linuxbrew/.linuxbrew/bin/uvx was used for the successful run. No implementation failures were hidden or converted to passes.

## Reproduction

```
CC=/usr/bin/cc uvx --with ninja --from meson meson setup /tmp/fsearch-generations-build .
uvx --with ninja --from meson meson compile -C /tmp/fsearch-generations-build -j 2
uvx --with ninja --from meson meson test -C /tmp/fsearch-generations-build --print-errorlogs
# For resource qualification, run test_catalog --scale N through run_pressure_guard.py
# inside a dedicated user cgroup with the exact limits above. Receipts retain commands.
```

Receipts under plan6-evidence/ contain actual commands, host PSI, sampled descendant RSS/PSS and exact cgroup memory/swap peaks. Internal catalog accounting distinguishes reserved commitment from resident memory. The cgroup measurement, not the internal ledger, supplies the physical peak evidence.

## M2 integration design and remaining program

Extend the packed base with native basename sort ranks and shared native signature bitplanes. Stream a bounded merge of base and delta candidates through authoritative matching with work/result/byte/deadline checks during collection. Import the existing private snapshot without retaining a second full serving representation, preserve root metadata and raw bytes, and expose sequence/generation/deferred coverage through the existing worker/service interface. Port reviewed primitives individually from the experiments; do not merge prototype branches. Validate the actual serving loop against the unchanged native snapshot oracle before connecting real events.

M2 must additionally qualify multiple approved roots, collision/type replacement and durable event-delivery interfaces. M3–M6 retain watcher/reconciliation, crash recovery, current-scale aggregate qualification, installation/rollback and both soaks. Plan 0006 stays open. The installed service was not replaced or reconfigured; no personal workspace scan or mutation occurred in M1. All filesystem mutations were inside owned temporary fixtures.
