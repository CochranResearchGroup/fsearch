# Everything-like filename search speed on WSL

Research date: 2026-10-04. Source anchor: local FSearch commit `5ec26bab` on `feature/7-warm-local-service`; installed executable source commit `7e3a7f1b`. Documentation-only research; no new benchmark, runtime modification, real-root scan, or implementation occurred.

## Question, scope and stopping rule

What architecture changes are most likely to produce consistently low filename-search latency at 100,000 to one million entries while retaining literal matching, private cached visibility, bounded work and isolation from unsafe mounts?

Allowed sources: official Everything documentation; Microsoft filesystem documentation; Linux kernel/manual documentation; official SQLite documentation; official plocate source/manual; current local FSearch code and qualification receipts. A background research agent examined the bounded plocate/SQLite comparison; root examined Everything, Linux monitoring and local code. Stop when the sources explain the existing bottleneck, establish feasible accelerator choices and monitoring constraints, and support a concrete comparison experiment. Stop before implementation, privileged filesystem experiments or expanding approved roots. Output: this single research Markdown note.

## Findings and evidence

### 1. Everything's documented advantages are residency and filesystem-assisted updates

Everything keeps its running database in memory and indexes names and paths. Additional metadata and fast-sort indexes trade memory for avoiding later filesystem reads. Its documented update mechanism uses the NTFS USN journal. Official documentation does not establish its internal substring-search algorithm; claiming it uses trigrams would be unsupported. [Everything indexes](https://www.voidtools.com/en-us/support/everything/indexes/), [Everything options](https://www.voidtools.com/en-us/support/everything/options/)

Microsoft describes the per-volume USN journal as a log of file/directory changes that avoids repeated whole-volume enumeration. This is filesystem-provided evidence, rather than an application's own live notification queue. [Microsoft change journals](https://learn.microsoft.com/en-us/windows/win32/fileio/change-journals)

Everything's folder indexing is explicitly slower than native NTFS indexing. **Inference:** preserve Everything's Windows coverage; traversing Windows mounts from WSL would give up that advantage. This does not prove a numerical performance difference on this host. [Everything folder indexing](https://www.voidtools.com/en-us/support/everything/folder_indexing/)

### 2. Our current resident engine still searches sequentially

`fsearch_headless_search()` iterates name-sorted files, then folders; it tests the extension before invoking the literal matcher. Result and work limits stop traversal. Full paths are already constructed only for matches in basename mode, so that proposed optimization is partly implemented already. Match-data buffers are invalidated between entries; Unicode normalization can be repeated when needed. These are structural observations, not a CPU profile. [Headless matcher](../../src/fsearch_headless.c), [match-data buffers](../../src/fsearch_query_match_data.c), [literal dispatch](../../src/fsearch_query_node.c)

The upstream GUI search already distributes ranges over a thread pool, joins chunked arrays and collects matching results. Our query-only snapshot constructor deliberately omits that worker-bearing lifecycle. Reusing the GUI search wholesale would not automatically preserve our bounded output and lifecycle contract. A parallel scan is a plausible benchmark baseline, not evidence that more threads are the best accelerator. [GUI search and worker pool](../../src/fsearch_database_index_store.c), [query-only service contract](../warm-service.md)

Existing source benchmarks used synthetic flat fixtures and 30 warm subsequent requests:

| Entries | Ten-hit socket p95 | Zero-hit socket p95 | Fresh native CLI p95 | Supervisor + worker observed RSS |
|---:|---:|---:|---:|---:|
| 10,000 | 1.07 ms | 1.82 ms | 10.54 ms | 27,592 KiB |
| 100,000 | 14.73 ms | 19.52 ms | 22.64 ms | 41,712 KiB |

The source acceptance establishes these measurements, not million-file, production-tree, MCP or installed performance. Separate installed tests prove functional acceptance. No new performance measurements were run for this note. [Source benchmark and caveats](2026-10-04-service-acceptance.md), [installed acceptance](2026-10-04-install-acceptance.md)

The current 500,000 examined-entry ceiling prevents calling an exhaustive million-entry linear search complete. The 64 MiB snapshot cap, two-second startup bound and 256 MiB worker address-space limit also constrain scale; RSS is different from address space. An accelerator must account for loading/building memory and startup before performance claims, without silently relaxing the existing caps. [Headless bounds](../../src/fsearch_headless.h), [worker/supervisor bounds](../warm-service.md)

### 3. Trigram filtering is supported by a working primary-source design

Plocate uses three-byte trigrams and inverted posting lists. Its 1.1.25 source stores compressed filename-block IDs in postings, not a posting per individual file. It deduplicates IDs and delta-encodes them. Search orders groups by estimated posting count, intersects smaller lists first, and verifies filenames afterward; exceptionally large lists may be skipped because exact verification remains authoritative. Source anchors: `database-builder.cpp` (`EncodingCorpus::flush_block`, `PostingListBuilder::add_docid`) and `plocate.cpp` search/intersection logic. [Official project](https://plocate.sesse.net/), [official 1.1.25 source archive](https://plocate.sesse.net/download/plocate-1.1.25.tar.gz)

The plocate manual documents scan fallbacks for insufficient usable trigrams and differing wildcard/locale semantics. Its case handling and non-UTF-8 limitations make copying its public query semantics unsuitable for our literal API. **Inference:** reuse the candidate-filter idea; preserve our matcher as the final authority. Neither source supplies a transferable speed or RAM guarantee. [Official plocate manual](https://plocate.sesse.net/plocate.1.html)

For `invoice`, candidate generation can use `inv`, `nvo`, `voi`, `oic`, `ice`, starting with a small posting list. A name containing every trigram may still lack the contiguous literal; exact verification is mandatory. Query cost depends on posting lengths and candidate count, not simply query length. Common trigrams and short inputs remain potentially expensive. This algorithmic explanation is a proposed design inference from the cited plocate implementation.

### 4. SQLite is a useful comparison, with semantic constraints

SQLite FTS5 supports Unicode-character trigrams. MATCH does not match substrings shorter than three characters; LIKE/GLOB can scan when no usable three-character run exists. Case-sensitive trigram mode supports indexed GLOB, not LIKE. Diacritic removal changes semantics and disables indexed LIKE/GLOB. LIKE with ESCAPE cannot use this optimization. MATCH has an expression grammar, so parameter binding alone does not make a query literal. Reduced-detail indexes restrict long MATCH tokens. External-content tables require synchronization. These differences require explicit literal, Unicode and short-query parity testing. SQLite's documentation promises no latency or RAM result for our corpus. **Recommendation:** include FTS5 as a simpler comparison implementation, not assume it preserves our matcher or outperforms native postings. [SQLite FTS5 trigram documentation](https://www.sqlite.org/fts5.html#the_trigram_tokenizer)

### 5. Linux freshness requires recovery, not just a watcher

Upstream FSearch 0.3 already provides folder monitoring with fanotify and an inotify fallback. Its documentation notes startup rescans, per-directory watch/mark consumption and filesystem limitations. This is machinery to evaluate inside the contained index worker; it is intentionally disabled in our query-only lifecycle. [Upstream FSearch database update](https://github.com/cboxdoerfer/fsearch/wiki/Database-update), [local index lifecycle](../../src/fsearch_database_index.c)

Inotify is nonrecursive; new subdirectories need watches and gap detection. Its queue can overflow, renames are racy, and remote changes on network filesystems are not reported. **Inference:** persist an explicit dirty/freshness state and reconcile an approved subtree after overflow, downtime or ambiguous events, while continuing to serve the last accepted snapshot. A private application log can persist events already received but cannot recover events that arrived while no monitor was running. [Linux inotify manual](https://man7.org/linux/man-pages/man7/inotify.7.html)

Fanotify offers broader observation, but requires kernel/filesystem/permission qualification and also has a queue. It is not automatically a persistent USN-equivalent log. The ext4 journal documentation describes crash-consistent block/metadata transactions. **Inference:** parsing the mounted ext4 journal is not a supported substitute established by this research for an application filename-change API; do not make raw-volume parsing the first approach. [Linux fanotify manual](https://man7.org/linux/man-pages/man7/fanotify.7.html), [ext4 journal documentation](https://docs.kernel.org/filesystems/ext4/journal.html)

The scanner's storage boundary remains independent of lookup acceleration. Descriptor-relative `openat2` resolution can forbid escape, symlinks and mount crossings, including bind mounts. This is a candidate confinement primitive to qualify for issue #3, not proof that every scanner/monitor syscall is contained or that an admitted disk cannot stall. [Linux openat2 manual](https://man7.org/linux/man-pages/man2/openat2.2.html), [approved refresh scope](../plans/headless-ticket-drafts/02-contained-refresh.md)

## Decision recorded after research

The operator accepted the native prototype direction on 2026-10-04. [ADR 0003](../adr/0003-native-trigram-candidate-acceleration.md) is the authoritative decision; the evidence and unmeasured caveats below remain intact.

## Recommended comparison experiment

This is a recommendation, not an approved implementation contract or an achieved speed guarantee.

Compare the existing sequential matcher, a compact native trigram candidate filter, and SQLite FTS5 trigram on identical owned synthetic filename records. Consider a bounded parallel scan only as an additional baseline after profiling. Begin at 100,000 entries; attempt one million only when fixture loading and accelerator construction fit the current resource envelope, otherwise record the cap failure and propose a separate reviewed envelope change. Never raise installed limits merely to make a chart pass.

The native filter should initially use stable per-snapshot entry ranks and sorted/delta-coded postings or measured bitmap alternatives. Compare per-entry postings with block postings if memory is excessive. Preserve file-before-folder ordering and current name order; intersect extension/kind candidates only when equivalence is proved. Existing parent-linked entry data should be reused before designing a new compact database. Do not store every expanded full path without measuring duplication.

Preserve literal matching: `%`, `_`, `*`, quotes and brackets are characters, not user query syntax. Candidate selection must be a superset of exact matches. Use the existing matcher's normalization/case semantics where proved compatible; scan unsupported Unicode, non-UTF-8 and path-mode cases until sound candidate handling is demonstrated. In particular, a basename-only index cannot exclude files whose parent path matches. One- and two-character queries need a bounded scan or separately measured short-gram index; prefix search alone cannot preserve arbitrary substring semantics.

Candidate filtering, posting traversal/intersection, normalization and output must all remain deadline- and memory-bounded. Revisit the meaning of `examined` explicitly if it changes from scanning entries to verifying candidates; do not hide unbounded posting work behind a low candidate count. Reuse prior candidate sets only for compatible queries on the same snapshot when those sets are complete; truncated returned rows cannot be reused as an exhaustive candidate set.

Use nested directories, repeated common names, mixed extensions, long names, Unicode normalization/case cases, non-UTF-8 names, basename/path queries and literal punctuation. Include absent trigrams, zero-hit queries whose trigrams all occur, rare hits near the end, high-frequency matches, one/two-character inputs, and output caps. Compare exact results, order and completeness with an exhaustive test oracle, rather than accepting a faster incomplete answer.

Measure p50/p95/p99 separately for native matcher, warm public socket, fresh CLI and eventual MCP. Also record CPU per request, posting work, candidates verified, cold loading/index construction, snapshot size, peak RSS/address space and aggregate supervisor/worker/replacement memory. Use separate processes and fixed fixtures; report cold/warm-cache conditions. Proposed exploration targets: selective warm socket queries below 5 ms p95 at 100,000 entries and below 10 ms at one million. These are targets for evaluation, not frozen acceptance gates; broad/short cases require separate truthful bounds. Preserve zero indexed-root syscalls during queries.

## Implementation order and open questions

1. Prototype candidate acceleration with exact semantic parity and memory measurements; do not change installed code for this research.
2. Complete contained initial refresh (#3) so production snapshots can be admitted safely.
3. Qualify safe resident snapshot replacement (#8) and monitoring (#4), including overflow/downtime recovery and overlapping memory.
4. Integrate file-searcher MCP (#20) using a persistent client process. The current socket allows one request per connection: avoid per-request process launch first, and measure before changing the socket protocol to support persistent connections.

No source inspected proves Everything-like latency for our host or corpus. Remaining decisions are native versus SQLite, entry versus block postings, Unicode/path indexing, short-query behavior, serialization/build timing, update strategy and a million-entry resource envelope. This research stops at a supported experiment recommendation rather than guessing those answers.

Memory disposition: forbidden. This is durable source-anchored research, but developer instructions require explicit authorization for personal memory writes; none was given. A separate machine-readable non-write receipt records that boundary.
