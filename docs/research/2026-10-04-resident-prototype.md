# Resident filename query prototype, 2026-10-04

Question: is load-once query serving measurably useful before adding a production service? Frozen gates and workload: warm-service-evidence/prototype-plan.md. Source: ../../src/prototypes/benchmark_resident.py. The runner derives a throwaway native worker from the current CLI, links the release library, loads an owned private snapshot once, and runs serial literal requests over pipes. No production source changes, arbitrary listener or user-root scans.

## Results

| Files / query | Warm p50 | Warm p95 | One-shot p50 | One-shot p95 | Loaded worker RSS |
|---|---:|---:|---:|---:|---:|
| 10,000 / ten hits | 0.65 ms | 0.78 ms | 10.05 ms | 13.42 ms | 9,048 KiB |
| 10,000 / zero hits | 0.65 ms | 0.74 ms | 9.94 ms | 11.94 ms | 9,048 KiB |
| 100,000 / ten hits | 11.50 ms | 12.53 ms | 48.84 ms | 55.57 ms | 23,308 KiB |
| 100,000 / zero hits | 11.68 ms | 15.27 ms | 51.81 ms | 66.58 ms | 23,308 KiB |

All four cases pass the predeclared research gates. Ten exact expected hit names and completed zero misses were asserted on every resident request. One first request and thirty subsequent requests per case; p50/p95 exclude the first. One-shot and resident requests alternate against the same snapshot. Both have potentially warm OS caches. Experimental worker emits matching markers and uses pipes; production CLI includes supervision. These are not full socket/MCP or adoption measurements. Raw observations, hashes and compiler flags: warm-service-evidence/resident-benchmark.json.

After removing the 10,000-file owned indexed root, a fresh resident worker was traced across all descendants for a six-second idle period and a cached query. Zero indexed-root file syscalls were observed and EOF shutdown exited cleanly. Trace: warm-service-evidence/resident-benchmark.trace. The earlier content-type negative control in headless-evidence supplies known probe sensitivity. No kernel stall was induced.

## Answer and limits

A resident cached worker substantially improves repeated-query latency on these fixtures. It still performs sequential matching; no scale or adoption claim beyond 100,000 flat entries is established. Loaded worker RSS is not aggregate service memory or peak replacement memory.

This is not a production daemon: no Unix socket, client authentication, bounded queue, request cancellation, hard resident-process limits, replacement or durable quarantine is implemented by the experiment. The outer runner owns the fixture workers and waits for EOF shutdown; no installed service exists. A separate interactive lifecycle model accompanies the experiment to make proposed failure states reviewable, without claiming OS containment proof.

Run: `python src/prototypes/benchmark_resident.py /tmp/fsearch-warm-release-build docs/research/warm-service-evidence/resident-benchmark.json`. Preserve original receipts; choose a new output path for another run. Prototype capture remains uncommitted because docs/agents/codex-stack.md requires explicit commit authorization.

Memory disposition: forbidden; no personal-memory write authorization.
