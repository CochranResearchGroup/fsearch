# M2 production catalog measurement packet

Owner: Codex. Issue: #28. Source: feat/incremental-generations (uncommitted candidate); actual input hashes must accompany acceptance.

Freeze before execution: deterministic in-memory forest with two folders and count-2 filenames `fixed-%07u.txt`, root `/__benchmark_owned__`, ancestor `ancestor`. Counts 100000, 300000, 1000000; advance serially only after preceding query gates pass and host preflight allows launch. This small corpus diagnoses production engine cost; it is not the representative M5 Unicode/path corpus or current-workspace acceptance.

Six classes: exact selective fixed-0000042.txt, zero-hit no-such-qzx-entry, common fixed, short x, ancestor-only path ancestor, slash path ancestor/fixed-0000042.txt. File filter, literal matching, 1000 results, 500000 examined candidates, 1 MiB response, intrinsic 1000 ms deadline. Two warmups then 30 observations; nearest-rank p50 index14, p95 index28, max index29. Selective/zero gate 10 ms; common/short 100 ms; paths 250 ms. Correctness checks expected result count and completion reason before a timing passes. A work-limited selective path fails, even if fast. No baseline changes after a failure.

Every stage: dedicated cgroup MemoryMax1280M, swap0, CPU150%, Nice10, IOWeight10; host pressure guard and 120-second deadline. Accounted catalog bytes exclude fixture seed arrays, query buffers and allocator retention. Whole cgroup peak includes construction input, driver and serving process; report separately. These are native cached queries, not CLI/MCP timings, event visibility or compaction acceptance.

## Observed candidate results

Initial 1m stage failed: slash path returned one match but stopped at 500000 examined entries, so correctness/completeness gate failed. Retained in m2-query-initial-1m.json. Added a cached ASCII path prefilter: either the full literal occurs in the parent path or its final component occurs in the basename. Uncertain overlong parent paths remain candidates; native exact matching remains authoritative. Unicode uncertainty retains bounded fallback. Expanded independent forest oracle to include slash paths, trailing separators and ancestor-only matches; full 26-group regression passes.

The first attempted corrected measurements used the stale non-test benchmark executable. Those m2-query-fixed-* files are invalid for the changed source, retained with m2-query-stale-benchmark.json. Explicitly rebuilt target; source/binary hashes in m2-query-rebuilt-inputs.json.

Corrected stages all pass this diagnostic corpus:

| Entries | Selective p95 ms | Slash-path p95 ms | Whole cgroup peak MiB |
|---|---|---|---|
| 100000 | 0.049 | 8.356 | 21.02 |
| 300000 | 0.262 | 24.309 | 46.56 |
| 1000000 | 0.483 | 64.854 | 136.38 |

All corrected slash queries complete with one examined candidate; candidate selection still traverses name-index blocks, so this is not constant-time path lookup. No swap in the owned cgroups. Common/short p95 below 1 ms; ancestor-only below 1.5 ms. Construction input allocations are included in peaks. These results do not prove current-scale, representative-path, aggregate update or installed acceptance.

ASan/UBSan lifecycle and query-bounds group passes (9 cases); catalog translation unit instrumented, linked native library archive uninstrumented. Raw sanitizer log and pressure receipt retained. Next gates: compaction with the production signature index, larger representative corpus/current scale, actual frontend contracts, and contained event ingestion/durable recovery.
