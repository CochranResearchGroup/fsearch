# Unicode memory leak repair — 2026-10-04

Status: source repair qualified locally; production acceleration goal remains active. Branch `feature/7-warm-local-service`, base `5ec26bab`. Source changes remain uncommitted and installed binaries are unchanged.

## Feedback loop and diagnosis

Stable seam: existing private service socket. A new regression creates 4,097 owned synthetic filenames plus the helper's existing invoice fixture, warms five Unicode queries, then issues 64 more. It checks exact `école` results from the same resident worker and at most 4 MiB RSS growth. This exercises the real matcher reuse pattern, not allocation internals or a prototype replacement.

The initial helper edit failed because added names were not materialized; that setup failure is retained separately and is not the diagnostic red signal. The corrected regression failed in 0.755 seconds with 27,840 KiB growth against a 4,096 KiB bound. Ranked explanations were overwritten owned UTF copies, retained response buffers and one-time ICU caches. Only the UTF copy lifetime changed: free its previous owned copy before storing the next filename. Existing normalization, case handling and public result semantics are preserved.

Exact targeted command:

```sh
python3 src/tests/test_service.py /tmp/fsearch-warm-release-build/src/fsearch-service /tmp/fsearch-warm-release-build/src/fsearch-cli /tmp/fsearch-warm-release-build/src/tests/snapshot_fixture /tmp/fsearch-warm-release-build/src/tests/libheadless_fault_fixture.so WarmService.test_repeated_unicode_queries_keep_resident_worker_memory_bounded
```

[Diagnostic red](production-evidence/unicode-leak-red.txt), [green](production-evidence/unicode-leak-green.txt), [setup failure](production-evidence/fixture-helper-failure.txt).

## Verification

Rebuilt with `/usr/bin/gcc` and the existing Meson release configuration. The targeted socket test passes in 0.605 seconds. All 15 Meson targets pass, including 13 upstream targets, 15 direct CLI cases and now 20 service cases. No production limits were relaxed. [Build](production-evidence/leak-build.txt), [full regressions](production-evidence/leak-regressions.txt).

The original larger scenario was rerun through the real supervisor and compiled resident worker: a 100,000-name virtual snapshot, five warmups and 100 subsequent Unicode requests. All results completed and matched the known literal path, worker identity stayed constant, and worker RSS stayed at 19,376 KiB (zero measured growth). The fixture-generation probe linked the actual rebuilt library; the prototype-only matcher override was explicitly removed. The real worker performed every query. [Original-workload receipt](production-evidence/unicode-original-workload-green.json), [reproducer](production-evidence/recheck-unicode-original.py).

Fresh readback found no remaining fixture worker/supervisor trees and verified all installed hashes remain unchanged. [Closeout](production-evidence/leak-closeout.json). The repair is not yet installed, and formal fixed-point review of the subsequent production acceleration is still pending.

## Remaining full-goal work

The operator was asked to settle aggregate RSS (recommended 128 MiB versus 256 MiB), short/Unicode/path query targets (recommended 30 ms p95 with exact semantics and truthful caps), and the existing CLI/socket seams, review baseline `5ec26bab` and four-ticket breakdown. Those questions remain pending; no approval is inferred from elapsed time.

A concrete [draft spec](../specs/0003-production-filename-acceleration.md), [draft breakdown](../plans/0003-production-acceleration-breakdown.md) and four issue-body drafts are ready for review. Publication and dependent acceleration implementation follow those answers. Native compact acceleration, short/Unicode/path handling, real worker/socket performance/resource qualification, two-axis review and subsequent installation remain incomplete.

Memory disposition: forbidden; personal memory writes require explicit user authorization, which was not given. Repository source and receipts preserve this result.
