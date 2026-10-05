# Compact block postings experiment — 2026-10-04

Status: isolated prototype evidence; production design answers remain pending. No production candidate index was added or installed.

## Question and implementation

Can a 64-entry filename block replace each individual rank in the native trigram posting lists and satisfy the proposed memory target? The prototype intersects sorted block IDs, expands a surviving block to at most 64 filename ranks, merges the unconditional unsupported-name bucket, sorts and deduplicates ranks, and runs the existing exact matcher. This remains a candidate superset: all matching ASCII filenames occur in a block listed for every query trigram, and unsupported names remain unconditional candidates. False positives require exact verification. Existing short, Unicode and path fallback behavior is retained.

The [driver](../../src/prototypes/benchmark_compact.py) derives the isolated implementation from the original probe and links the actual repaired library without a prototype UTF override. The [receipt](compact-evidence/comparison.json) records source/library/generated-binary hashes, generated source and compiler commands, actual resource readbacks and raw latency samples. Generated virtual snapshots contain one million files and 65 folders; no production roots or installed binaries are changed. This measures a stdio prototype, not the public socket or supervisor aggregate.

## Results

On repetitive filenames, posting payload falls from the historical 91,006,988 bytes to **10,736,664 bytes** (about 88 percent reduction). Final run load plus construction is **1,277.777 ms**. Native process peak RSS is **123,312 KiB**, steady READY RSS **115,528 KiB**, and final RSS **116,488 KiB**. Loader peak contributes substantially; posting payload alone is not process memory. Supervisor memory and resource variability remain unqualified, so this does not establish the proposed 128 MiB aggregate gate.

Four selective cases have 100 samples each: rare p95 **0.113 ms**, late **0.164 ms**, absent **0.060 ms**, and present-trigrams-but-absent-literal **0.065 ms**. All 25 completed/result-limited cases match the exhaustive oracle's ordered results and coverage metadata. Five cases remain truthfully work-limited: two-character, Unicode, case-fold, normalization, and the deliberate tiny work cap. Two-character and Unicode samples remain roughly 242 and 261 ms p95 respectively, based on only five exploratory samples, and do not meet the proposed 30 ms gate. Path samples are also exploratory, not acceptance evidence.

The varied-filename fixture retains special cases and long names but replaces ordinary names with deterministic 40-character xorshift-generated strings plus unique numeric suffixes. Its linear exhaustive oracle loads and completes all 30 cases. Its native compact index fails during construction under the unchanged **256 MiB address-space ceiling**: GLib reports an allocation failure and the process exits on signal 5 before READY. [Raw stderr](compact-evidence/entropy-native.stderr.txt). The final harness records the failure explicitly; successful experiment completion is not production qualification. The initial run exposed the same failure and its driver is retained separately.

## Consequence for production

Fixed-size block postings are insufficient by themselves. Nearby sorted names can share trigrams, but varied names make blocks contain many distinct trigrams. The production index builder needs an explicit allocation budget, a representation chosen from corpus evidence, and safe fallback before allocation failure. The draft spec and compact-basename ticket now state this requirement. The varied-filename fixture must remain part of qualification; do not select the repetitive fixture alone or relax existing limits to hide this failure.

The leak repair remains separate and qualified locally. Compact production acceleration, short/Unicode/path acceleration, real worker/socket acceptance, review and installation remain incomplete.

Memory disposition: forbidden; no explicit authorization for a personal memory write.
