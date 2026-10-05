# Resident query experiment — frozen before execution

Question: does loading once improve repeated cached query latency enough to justify a service prototype? Use only owned native temporary roots at 10,000 and 100,000 flat files. Use the existing release library and copied current CLI matching/JSON logic, one worker, serial newline-delimited literal requests over pipes. This is NOT the production socket protocol or containment model.

Measure ready/startup (includes initial load), worker-reported load time, 31 requests per hit/miss workload (first separately, next 30 p50/p95), direct warmed worker RSS, and matching-only timing. Compare optimized one-shot processes at the same sizes. Assert ten exact hit names and complete zero misses. Instrumented resident and uninstrumented CLI are different paths; record this caveat. Warm OS caches are allowed, not cold-cache claims.

Provisional prototype viability gates: resident request p95 <= 5 ms at 10k and <= 30 ms at 100k, resident loaded RSS <= 128 MiB at 100k, and resident median < corresponding one-shot median for each workload. These are research gates, not adoption thresholds. Stop on gate failure; do not silently change gates or broaden roots.

After measurements, remove the owned root and trace all worker file syscalls through a six-second idle period and cached request. Require zero accesses to removed indexed-root paths and clean EOF shutdown/reaping. The previously recorded content-type negative control supplies trace sensitivity evidence. Production queue, Unix socket credentials, cancellation, replacement, quarantine and restart remain unqualified.
