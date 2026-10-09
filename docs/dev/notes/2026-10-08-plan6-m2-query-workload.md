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

## Larger-stage packet, frozen before execution

Advance the same diagnostic corpus to 3000000 entries, then exact historical workspace count6734348 only if3m passes. Same query limits, percentiles and performance gates; 120-second stage deadline and1280MiB/no-swap cgroup retained. Real filesystem scope unchanged: all entries generated in memory. Source dc88a160; explicit benchmark relink required after deadline-status source change. No target changes authorized.

## Exact-count diagnostic and ancestor candidate repair

Original3m stage passed; exact6734348 stage failed slash-path latency: p95 416.061ms >250ms despite complete/correct results. Retained m2-query-current-count.json with pressure receipt. Fixed candidate selection by probing folder-name candidates for the final path component. If no visible folder path can contain the full literal, basename tail signatures safely filter all candidates. Matching ancestors, probe cap4096, empty tails, overlong paths or Unicode uncertainty retain bounded fallback. Overlay folders and ancestor renames are evaluated in the current view. Expanded rebuilt-snapshot oracle covers slash/ancestor paths across compaction, rename and deletion; all26native groups pass.

Corrected3m: selective p95 .922ms, slash1.326ms. Exact6734348: selective2.055ms, zero .903ms, slash2.013ms, common/short below .53ms. Whole construction cgroup peaks391.89/869.43MiB respectively, swap0; exact-count accounted catalog444468618bytes. Construction peaks include generated input; accounted bytes do not prove steady RSS. This shallow two-folder diagnostic is not the representative directory shape/current-workspace acceptance. Raw receipts and source/binary hashes m2-ancestor-bench-*.

## Directory-heavy/deeper packet, frozen before execution

Stages100000/9187folders,300000/27561,1000000/91873,3000000/275619,6734348/618761; advance serially after preceding correctness/query/pressure gates pass. Deterministic10-way directory tree, file parents distributed across folders by identity. Every1000th file contributes one Unicode CAFÉ pdf, one raw-byte txt, and one literal*? txt; other files fixed-ID txt. Selective target folders+42 stays ordinary. Ten classes: prior six plus Unicode+pdf filter, raw-byte hits, literal punctuation, folder-kind filter. Expected full match counts calculated from generated shape before queries; response caps/completeness must match those counts. Unicode/raw/punctuation and folders use100ms common-query gate; selective/zero10ms, paths250ms retained. Two warmups/30observations, same query bounds, cgroup/pressure controls and120sdeadline. Larger basename storage/ancestor depths are now included; this remains synthetic source qualification, not actual workspace acceptance or installed CLI latency.

Directory-heavy first corpus passes through exact count, including Unicode basenames. Before new measurements add two required path classes: exact Unicode filename under its immediate parent, and zero-hit missing/ÉCOLE. Gates250ms, same bounds. Generalize ancestor probe to native literal matching for Unicode paths; enable tail signatures only when the full query's normalization is index-supported. Raw ASCII prefilter remains restricted to its prior safe conditions. Freeze same stage sequence and resources before collecting these added classes. Existing prior corpus results remain valid for its source, not evidence for the new Unicode path classes.

## Indexed compaction resource stages

Freeze existing production lifecycle workload (four compactions,400accepted mutations, four concurrently pinned readers, independent formula oracle) at3m then exact6734348 synthetic entries. Tree shape is the original shallow churn fixture; directory-heavy query qualification remains separate.3m deadline120s; exact-count complete four-cycle deadline240s, fixed before execution because the1m four-cycle run took19.36s under CPU150%. Each owns the same1280MiB/no-swap cgroup and pressure guard. The catalog's1GiB allocation admission remains unchanged. Advance only if3m passes. Report full build+validation+oracle cycle times separately from event freshness. Any budget or pressure failure retains accepted state/evidence and fails the stage.

All12directory-heavy query classes now pass through6734348entries/618761folders. Exact-count Unicode path selective p95 15.418ms, zero13.408ms; full native regression26groups passes. M2 current-count compaction is now running under frozen240s deadline after3m passed four cycles/400events (maxcycle14590.590ms, elapsed60060.454ms). Tool session45335 and guarded unit fsearch-plan6-m2-compaction-current-count are the exact running handles; do not restart on observation yield. Aggregate construction/update acceptance remains pending this receipt.

## Current-count compaction outcome

Exact6734348 four-cycle fixture passes:400 accepted mutations,32738958 concurrent reader checks,141577.664ms total,34284.751ms maximum build/validation/oracle cycle. Cgroup memory.peak1168338944bytes (1114.21MiB), swap.peak0, below1280MiB. Accounted live catalog444469589bytes and peak allocation commitment997750030bytes are separate metrics. This synthetic process measurement includes the native query catalog, driver/readers and builder; it does not include a production watcher/supervisor nor prove installed aggregate steady memory.

Latest targeted ASan/UBSan lifecycle group passes; instrumented catalog adapter versus independent rebuilt native snapshots passes6120comparisons/30prefixes across10phases. Linked native archive remains uninstrumented. Source and compiled inputs retained in m2-unicode-tree-inputs.json; no source changes followed these checks.
