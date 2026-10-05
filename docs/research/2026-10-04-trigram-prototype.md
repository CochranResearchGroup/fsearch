# Native trigram prototype outcome — 2026-10-04

## Outcome

The native candidate filter is a strong selective-query acceleration candidate. The isolated comparison completed at 100,000 and one million virtual filenames, with 180 matrix cases, 21 supplemental duplicate-basename cases and 100 warm samples for each designated workload. It is **not production-ready**: memory, fallback costs, the existing Unicode lifetime defect and production protocol/resource qualification remain gates.

Source anchor: `5ec26bab`, branch `feature/7-warm-local-service`. The prototype and decision/research artifacts remain local and uncommitted. Installed source `7e3a7f1b` and all installed executable hashes are unchanged. No production implementation, root scan, service registration or MCP change occurred. [Accepted direction](../adr/0003-native-trigram-candidate-acceleration.md), [frozen plan and amendment](trigram-qualification-plan.md), [raw benchmark](trigram-evidence/benchmark.json), [closeout readback](trigram-evidence/closeout.json)

## What was built

An isolated native C probe loads ordinary owner-private snapshots under the existing 64 MiB file cap and 256 MiB address-space ceiling. A fixture-only builder constructs entries and NAME/PATH arrays directly; indexed roots never exist. The candidate filter stores deduplicated ASCII byte-trigram postings as per-snapshot name ranks in GArray vectors. Small posting lists are intersected; pivots larger than 4096 trigger sequential fallback. Non-ASCII names are unconditional candidates, while non-ASCII queries, short queries and path mode use sequential matching. Both accelerators use FSearch's actual literal matcher and the original headless search response body with only candidate iteration substituted. No separate substring oracle replaces FSearch semantics.

SQLite uses an in-memory FTS5 trigram table with bound, quoted literal MATCH phrases and the same unsupported-name bucket. Candidate sets larger than 4096 fall back to sequential matching. The native filter has a 500,000 posting-operation budget; SQLite uses progress callbacks plus row accounting and a deadline. Their work counters have different units and must not be compared as equivalent VM operations. Query verification retains the public 500,000-entry cap. A separate test-only exhaustive oracle can examine the complete generated corpus once per case; installed/public limits were never raised.

The current experiment does not add compression, persistent accelerator serialization, monitoring, live replacement, socket handling or MCP integration. [Probe source](../../src/prototypes/trigram_probe.c), [reproducible driver](../../src/prototypes/benchmark_trigram.py), [duplicate fixture check](../../src/prototypes/verify_trigram_duplicates.py)

## Warm matcher results

Nearest-rank p95 of 100 samples after three warmups; time includes candidate generation, matching and response construction, excluding process startup and socket/MCP transport. All engines use the identical prototype-only Unicode lifetime repair described below.

| Files | Query | Sequential p95 | Native p95 | SQLite p95 |
|---:|---|---:|---:|---:|
| 100,000 | Selective `invoice-unique-zqx` | 11.867 ms | 0.059 ms | 0.389 ms |
| 100,000 | Absent literal | 12.205 ms | 0.057 ms | 0.105 ms |
| 100,000 | Common match, bounded output | 0.086 ms | 0.110 ms | 0.958 ms |
| 100,000 | Two-character fallback | 10.707 ms | 10.998 ms | 10.629 ms |
| 100,000 | Unicode fallback | 21.943 ms | 23.638 ms | 20.968 ms |
| 1,000,000 | Selective `invoice-unique-zqx` | Incomplete at work cap | 0.079 ms | 1.308 ms |
| 1,000,000 | Absent literal | Incomplete at work cap | 0.075 ms | See raw receipt |
| 1,000,000 | Common match, bounded output | See raw receipt | 0.107 ms | See raw receipt |
| 1,000,000 | Two-character fallback | Incomplete at work cap | 231.024 ms, incomplete | See raw receipt |
| 1,000,000 | Unicode fallback | Incomplete at work cap | 300.954 ms, incomplete | See raw receipt |
| 1,000,000 | Path query | See raw receipt | 30.288 ms | See raw receipt |

The selective 100,000-entry native improvement is approximately 201 times against a semantically equivalent complete sequential response. Do not calculate a million-entry speedup against an incomplete sequential response. Native selective million-entry results match the separate exhaustive oracle. The fixtures favor highly repetitive ASCII names; their postings dictionary is only about 1,600 distinct trigrams. These figures do not establish performance on arbitrary multilingual or high-entropy corpora, installed sockets, CLI launch, MCP or interactive UI.

## Construction and resources

| Files / engine | Snapshot load | Accelerator build | Maximum observed peak RSS | Readiness within two-second bound |
|---|---:|---:|---:|---|
| 100,000 / native | 29.115 ms | 46.739 ms | 29,184 KiB | Yes in this run |
| 1,000,000 / native | 378.037 ms | 1,275.423 ms | 192,868 KiB | Yes in this run |
| 1,000,000 / SQLite | 372.062 ms | 4,721.102 ms | 220,184 KiB | No |

Snapshots were 2,893,012 and 28,908,910 bytes. Native postings payload was 9,101,412 and 91,006,988 bytes, before vector capacity/hash overhead. Million-entry native peak virtual address space was 241,276 KiB; SQLite reached 259,760 KiB, near the unchanged 262,144 KiB ceiling. These are single-process prototype peaks, excluding supervisor and replacement overlap. Native's roughly 188 MiB peak RSS exceeds the earlier 128 MiB aggregate service qualification envelope; fitting the worker AS cap alone is not adoption proof. Single observed readiness times also do not establish a startup tail-latency guarantee.

## Correctness, isolation and retained failures

Of 180 matrix cases, 152 had exact response parity after excluding only changing wall-clock ages and deliberately different examined counts. The other 28 were comparisons where the sequential work cap prevented equivalence; complete accelerated responses were additionally checked against the exhaustive test oracle. Deliberate small-work-cap cases remain bounded and truthful. Ordered results, status, completeness/truncation, identity and root coverage were checked. False positives with all query trigrams present but no contiguous literal were rejected by the actual matcher. The supplemental 21 cases prove duplicate-name order, extension/kind filters and output limits. [Duplicate receipt](trigram-evidence/duplicate-parity.json)

Separate file-syscall traces recorded zero indexed-root probes at both corpus sizes. Additional traces exercise literal, path, Unicode and raw-byte-name queries for all three engines. [Isolation receipt](trigram-evidence/all-semantics-isolation.json), [100k trace](trigram-evidence/query-100000.trace), [million trace](trigram-evidence/query-1000000.trace)

The initial fixture omitted PATH fast-sort arrays, causing a loader assertion. The fixture was corrected without changing the loader. An initial repeated-response equality assertion also compared wall-clock ages; only those dynamic ages were removed from equality. Both failures are retained. The first fully structured comparison then exposed an existing Unicode memory leak: `fsearch_utf_builder_normalize_and_fold_case()` assigns `builder->string = g_strdup(string)` without freeing its previous owned string. A standalone repeated-query reproduction terminated under the unchanged AS cap with GLib's allocation failure. [Fixture failure](trigram-evidence/initial-readiness-failure.md), [age assertion](trigram-evidence/age-clock-failure.txt), [failed pre-repair comparison](trigram-evidence/unicode-leak-incomplete-benchmark.json), [leak reproduction](trigram-evidence/unicode-leak-reproduction.json), [production source](../../src/fsearch_utf.c)

The completed comparison links a prototype-only copy of fsearch_utf.c freeing the prior string before replacement. The same memory-lifetime repair applies to all engines; their matching semantics are unchanged. Production and installed copies remain unrepaired. Generated native and repaired matcher source, the exact measured driver, compiler command and source/executable hashes are retained. The original eager intersection also rejected common queries at its posting budget; the completed experiment uses sound sequential fallback instead. None of the failed runs is presented as passing acceptance.

## Recommended next packet

Retain native acceleration as the preferred production-design direction. Before integration: repair and regression-test the actual Unicode lifetime defect; reduce posting memory using measured delta/block alternatives; resolve short-query and Unicode/path fallback latency/completeness; freeze production work-accounting semantics and startup/aggregate/replacement gates; then qualify the real worker/socket path. Preserve the current installed version until that integration qualifies. Safe initial refresh, monitoring, snapshot replacement and MCP remain separate existing scopes.

Reproduce with the existing release build:

```sh
python3 src/prototypes/benchmark_trigram.py /tmp/fsearch-warm-release-build /tmp/fsearch-trigram-evidence --samples 100
python3 src/prototypes/verify_trigram_duplicates.py /tmp/fsearch-warm-release-build /tmp/fsearch-trigram-evidence
```

Memory disposition: forbidden. This durable result is recorded in the repo, but personal memory writes require explicit operator authorization, which was not given.
