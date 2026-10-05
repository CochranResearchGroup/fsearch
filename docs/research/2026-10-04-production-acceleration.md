# Production query acceleration qualification — 2026-10-04

The approved source packet implements issues #10–#13 against spec #9. The numerical gates remain 128 MiB aggregate RSS, 256 MiB worker AS, 64 MiB snapshot, two-second startup, selective socket p95 below 10 ms and designated complete short/Unicode/path p95 below 30 ms. This is synthetic query-serving acceptance, not real filesystem indexing or full Everything-like adoption. Installation remains downstream of formal review.

The worker uses a query-only immutable NAME view and a capped entry arena. Fixed 192-bit raw/normalized trigram signatures reserve at most 32 MiB; every result still passes the original literal matcher. Short ASCII searches use an optimized literal scan; slash-free ASCII path searches cache at most 4,096 parent decisions. Other path cases retain bounded exact fallback. No roots are probed.

| Million-name corpus | Combined HWM KiB | Selective worst p95 ms | Complete short p95 ms | Unicode p95 ms | Complete path p95 ms |
|---|---:|---:|---:|---:|---:|
| full | 103132 | 4.42 | 13.34 | 4.40 | 11.44 |
| entropy | 128020 | 9.00 | 15.74 | 4.81 | 15.00 |
| unicode-heavy | 123316 | 7.63 | 21.53 | 4.30 | 10.89 |

Each query has 100 warm socket and 100 native samples with p50/p95/p99 and raw observations. Fresh CLI cost is separately recorded from three cold launches per query; it includes snapshot construction and is not claimed as warm latency. The varied corpus has long independent names; the Unicode-heavy corpus replaces 200,000 ordinary names with Cyrillic names. Complete probes are literal `??`, Unicode `école`, and `zz-last-rare-qvt` with path=true. Broad `ab` and parent-path queries intentionally reach result_limit and do not qualify complete-search latency. This distinction corrects an earlier progress readout that treated capped timings as a passed complete-search gate.

All 15 Meson targets pass. Thirty-eight actual CLI/socket cases agree with the fixed-point exhaustive oracle, excluding examined counts and changing ages/request IDs. Deliberate verification-cap cases are explicitly distinguished. Every direct CLI case and all socket cases were traced across child processes; indexed-root file syscalls are zero. Duplicate ordering, literal punctuation, case, normalization, raw-byte paths, extension/kind, response caps and coverage are included. Existing crash/deadline/cancellation/reap tests remain green.

Unicode leak red/green, failed posting-memory designs, high-water memory failures, short-query failures and the concurrent-build test failure remain in evidence. Current measurements never ran alongside compilation. Peak RSS uses both frequent aggregate sampling and the conservative sum of individual VmHWM counters, including construction.

The machine-readable qualification is [production-qualification.json](production-evidence/production-qualification.json). Final source, parity and corpus receipts are in [production-evidence](production-evidence/). One measured header differs only by a removed trailing blank line, recorded explicitly in qualification provenance. Source, installed runtime, full adoption and external publication remain separate boundaries.

## Installed readback

Review and installation are now complete; see [installed acceptance](2026-10-04-production-install-acceptance.md). The source packet and installed artifact identity are separate from the later evidence-only commit.
