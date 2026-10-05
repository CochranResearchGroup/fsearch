# Warm service investigation, 2026-10-04

## Bound and sources

Question: what costs does the current one-shot CLI pay per request, and what evidence supports a resident query worker? Allowed evidence: current repository source, compiler commands, and owned synthetic fixtures. Stop after separating load/matching/response costs at 10,000 and 100,000 entries, qualifying an optimized CLI build, and recording the unresolved lifecycle decisions. No real-root admission, runtime installation, service implementation or commits.

Primary sources: [CLI implementation](../../src/fsearch_cli.c), [copied-source instrumentation harness](../../src/prototypes/profile_cli.py), [fixture benchmark](../../src/prototypes/benchmark_cli.py), [accepted snapshot decision](../adr/0001-private-snapshots-for-headless-search.md). Raw results and build flags: [debug profile](warm-service-evidence/debug-profile.json), [release profile](warm-service-evidence/release-profile.json), [release benchmark](warm-service-evidence/release-benchmark.json), and [release CLI tests](warm-service-evidence/release-tests.txt).

## Findings

The earlier 16.77 ms p95 comparison used the Meson debug build with `-O0`, not an optimized executable. This qualification was missing from the initial explanation. Preserve that receipt as historical evidence; it does not represent optimized FSearch performance.

The CLI opens and loads the entire private snapshot inside its worker on every request. Its matching loop walks eligible cached entries sequentially. A successful complete low-hit query examines every eligible entry; a result limit does not avoid that scan when fewer than the limit match. Process supervision, library startup, worker cleanup and output transfer add costs outside the measured worker stages. Those individual overheads have not yet been separated.

Copied-source instrumentation preserves production code and emits microsecond stage timings only in the experimental copy. Ten subsequent requests after one first request give these medians:

| Build / workload | Snapshot load | Matching | Response assembly | Whole request |
|---|---:|---:|---:|---:|
| Debug / 10,000 files, ten hits | 3.66 ms | 1.10 ms | 0.008 ms | 11.81 ms |
| Release / 10,000 files, ten hits | 2.60 ms | 0.66 ms | 0.006 ms | 10.55 ms |
| Debug / 100,000 files, ten hits | 36.68 ms | 22.04 ms | 0.027 ms | 72.95 ms |
| Release / 100,000 files, ten hits | 25.36 ms | 11.50 ms | 0.022 ms | 48.48 ms |

Zero-hit workloads also exhaust the index and show similar costs (see raw receipts). The release profile overlapped a small fixture benchmark; treat these numbers as exploratory, not adoption thresholds or a controlled debug/release speedup estimate. The final release benchmark was rerun without those competing experiments: FSearch CLI p95 15.55 ms, maximum process RSS 8320 KiB on 10,000 entries. Filename libraries and OS caches may be warm; these are not cold-cache runs. No million-file extrapolation has been established.

Inference: keeping an accepted snapshot in memory should remove its repeated reconstruction cost and much of process startup. This is supported by measured load cost, not yet a measured resident-service speedup. Sequential matching remains work proportional to examined entries. A service alone does not establish an efficient search index or acceptable memory at operator scale.

## Proposed design and unresolved interview frontier

Preserve cached visibility and the query/update separation from ADR 0001. Use an owner-private local interface, with file-searcher retaining MCP routing and fallback. Keep the CLI as a client and diagnostic seam. No production listener is implemented by this investigation.

Q1: service lifetime and concurrency. Recommendation: per-user, started on demand; hold the last accepted snapshot in a query worker; one active request and a bounded queue; failed refresh leaves the last accepted snapshot serving. Alternative: always running at login, or design concurrent queries first.

Q2: failed worker cleanup. Recommendation: an unproved reap quarantines the service and file-searcher uses SQLite until explicit recovery. Alternative: return an explicit error without fallback. Do not launch replacement workers while cleanup remains unproved.

These are pending operator answers; elapsed time does not approve them. Once settled, ask only the dependent frontier: deadline/recovery policy for requests, queue admission, and the resource budget during snapshot replacement. Do not silently assume that a service may temporarily hold two large snapshots or duplicate workers.

## Next experimental packet, after shared understanding

Freeze workload/resource gates before building a throwaway resident worker. Compare load-once warm queries with the one-shot release CLI at 10,000 and 100,000 entries, then a larger fixture only within an agreed resource budget. Measure client round trip, worker matching, aggregate process memory, idle resources, and maximum bounded output. Exercise cancellation, queue saturation, disconnects, replacement failure and restart/quarantine through synthetic faults. Preserve zero indexed-root probes beyond the existing polling interval. Do not infer a safe updater from query-only isolation.

Use those findings to propose a service ADR and revisions to the existing spec/ticket graph. Keep parent issue #1 and CLI issue #2 open pending integration; do not replace approved tickets until the revised breakdown is reviewed. Implementation then proceeds with public-seam TDD and source review. No install or personal-memory write was authorized.

Memory disposition: forbidden; the durable source findings remain in this repo, while personal memory writes require explicit authorization.

## Subsequent continuation

The operator directed continuation with recommended defaults. ADR 0002 records that accepted direction. The resident experiment passed its research gates; see `2026-10-04-resident-prototype.md`. Source spec and concrete ticket changes are prepared under spec 0002 and plan 0002. Their detailed implementation contracts remain proposals until the ticket review.
