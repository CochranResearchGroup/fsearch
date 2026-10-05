# CLI viability measurement plan (frozen before execution)

Scope: 10,000 generated flat filenames in a new owned native temporary root; no system index, user configuration, mounted-share scan or cache eviction. One independently specified query `entry0000` must return exactly entry00000.txt through entry00009.txt.

Candidates: this FSearch JSON CLI; the installed file-searcher SQLite backend in a fresh interpreter; plocate using ONLY a freshly built private fixture database, with visibility checks enabled and LOCATE_PATH cleared. Report SQLite's warmed in-process function separately because that resembles its existing MCP use. CLI formatting/features differ; this is a startup/load viability comparison, not a complete replacement benchmark.

Measurements: first process after fixture creation, then 30 separate subsequent processes per candidate; wall-clock p50/p95, maximum RSS from /usr/bin/time (largest process/descendant, not summed aggregate), result correctness. No claim of cold OS cache; file/library caches may already be warm. Record executable identities and snapshot hashes.

Provisional first-slice viability gate: FSearch subsequent-process p95 <= 250 ms and maximum-process RSS <= 128 MiB at this workload. This leaves headroom within file-searcher's existing multi-backend request budget; it is not an adoption gate or a claim about larger datasets. Failure should prompt investigation before update/monitoring work. Final adoption workloads and gates remain ticket #5's responsibility.
