---
status: accepted prototype direction
---
# Accelerate literal filename search with native trigram candidates

On 2026-10-04, the operator said “ok lock that in” after reviewing the recommendation in [Everything-like speed research](../research/2026-10-04-everything-speed.md). Native trigram candidate acceleration is the chosen next performance experiment. This decision approves the prototype direction; it does not assert a measured speedup or select an unmeasured production index format.

## Decision

Build a compact native trigram candidate filter in front of the existing literal matcher. The matcher remains the final correctness authority. Candidate generation must be a superset of exact matches; uncertain or unsupported semantics fall back to bounded scanning with truthful completeness. Preserve literal punctuation, case/Unicode behavior, non-UTF-8 handling, basename/path distinction, extension/kind filters, result order, snapshot identity and existing output/resource bounds.

Compare the native prototype with the current sequential matcher and SQLite FTS5 trigram on identical owned synthetic records. Begin at 100,000 entries; test one million only if loading and construction fit the current envelope. Record cap failures rather than silently raising installed limits. Measure exact parity, p50/p95/p99, candidate/posting work, CPU, index size, construction/startup and peak memory. Include rare/common/zero-hit queries, one/two-character inputs, nested paths, Unicode and literal punctuation. Performance targets suggested by the research remain hypotheses until a concrete qualification plan freezes them before measurement.

Keep the query worker resident and free of indexed-root probes. Keep scanning, monitoring and accepted-snapshot publication separate. Preserve Everything for Windows coverage; file-searcher remains the MCP layer. Avoid per-request process launch in eventual MCP integration before considering a socket protocol change.

## Boundaries and follow-up

The next authorized direction is an isolated native prototype and comparison, not installation of a new accelerator. Production integration follows measured correctness, resource and performance acceptance. Existing safe-refresh (#3), monitoring (#4), snapshot-replacement (#8) and file-searcher MCP (#20) scopes remain separate. This decision does not authorize new real-root scans, broader filesystem admission, user MCP changes or personal memory writes.

Posting representation (entry versus block IDs, delta lists versus bitmaps), serialization/build timing, short-query acceleration, full Unicode/path coverage and the million-entry resource envelope remain experiment outputs. Do not claim Everything uses trigrams; the inspected official sources establish residency and journal-assisted updates, not its substring-search internals.

## Prototype evidence

The isolated comparison is complete; see [prototype outcome](../research/2026-10-04-trigram-prototype.md). Selective native queries met the exploration targets, with exact-match verification and an exhaustive test oracle. Million-entry posting memory, unsupported-query fallbacks and a reproduced existing Unicode lifetime leak block production adoption. The leak repair exists only in the prototype comparison. No accelerator or repair was installed. The accepted prototype direction remains unchanged; production format and integration require a subsequent concrete qualification plan.

## Approved production packet

The subsequent approved spec and tickets #9–#13 authorize source implementation and qualification. The Unicode lifetime repair is now in real source. See [production qualification](../research/2026-10-04-production-acceleration.md) for the selected bounded signature representation, complete-query gates, preserved failures and exact installation boundary. The historical prototype section above describes its earlier state; it is not the current implementation status.
