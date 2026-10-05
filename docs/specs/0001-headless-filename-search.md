# Headless filename search from private snapshots

Status: published as https://github.com/CochranResearchGroup/fsearch/issues/1; ticket breakdown approved and published. Date: 2026-10-04.

## Problem Statement

The operator needs fast Linux filename discovery through file-searcher without launching filesystem permission checks on Windows mounts during each query. The conservative plocate workaround currently removes Linux locate coverage throughout WSL. Everything already handles Windows storage, and FSearch offers an existing filename engine worth evaluating for Linux storage.

## Solution

Provide a bounded JSON CLI that searches a private snapshot, with explicit freshness, scope, truncation and completeness. Keep filesystem indexing and change monitoring in separately contained workers against approved roots. Connect the CLI to file-searcher's existing MCP interface after the query contract is qualified. Preserve upstream FSearch's GUI behavior.

## User Stories

1. As an operator, I want to search Linux filenames without a display session, so agents can use the engine.
2. As an operator, I want Windows filename discovery to remain with Everything, so Linux indexing does not duplicate Windows traversal.
3. As an agent, I want structured results, so I can consume paths without parsing GUI output.
4. As an agent, I want bounded result counts and response bytes, so broad searches do not overwhelm callers.
5. As an operator, I want query work and memory bounded, so an output limit is not merely cosmetic.
6. As an agent, I want literal name and path matching, so input cannot enable filesystem-probing query functions.
7. As an agent, I want file/folder and extension filters, so common filename requests remain useful.
8. As an agent, I want quoted, Unicode and newline names represented unambiguously, so paths round-trip.
9. As an operator, I want a private owner-scoped snapshot, so cached names are not exposed across users.
10. As an agent, I want the snapshot's age and included-root coverage, so I know what the results establish.
11. As an agent, I want current permission checks distinguished from cached visibility, so a result is not mistaken for proof of access.
12. As an agent, I want incomplete searches distinguished from completed empty searches, so cancellation is not misleading.
13. As an operator, I want missing or invalid snapshots to fail explicitly, so a query never falls back to a real-root scan.
14. As an operator, I want query processes to avoid monitors, scans and root polling, so serving a request cannot reach indexed storage autonomously.
15. As an operator, I want updates limited to approved roots, so excluded mounts are never probed before exclusion.
16. As an operator, I want a stalled update worker contained without automatic replacement, so retries cannot accumulate blocked workers.
17. As an agent, I want the last accepted snapshot available during failed updates, so other work can continue.
18. As an operator, I want change monitoring only on approved roots, so freshness does not silently broaden storage access.
19. As an operator, I want existing GUI behavior and tests preserved, so the fork remains usable and upstreamable.
20. As an operator, I want comparative latency and resource evidence before adoption, so a replacement earns its operational cost.
21. As an operator, I want reversible installation and direct MCP readback, so source readiness is not confused with deployed behavior.

## Implementation Decisions

- Begin with a JSON CLI and a query-only snapshot lifecycle; defer network listeners and a persistent daemon.
- Reuse the existing engine and persisted snapshot format where suitable. Make headless behavior optional and keep GUI defaults intact.
- Initial query inputs are typed literal name/path terms, extension and file/folder filters. Do not expose arbitrary GUI query syntax, custom macros, content-type queries, previews, file actions or metadata discovery. Advanced syntax may be added only after qualification.
- Queries operate on cached metadata and explicitly declare cached visibility. Snapshot metadata reports age and included roots without checking those roots at query time.
- Query-only stores do not construct filesystem monitors, schedule root polling, rescan, save databases or use missing-load fallback. Owning a cancellable is not evidence that blocked filesystem operations can be interrupted.
- Require an explicit private snapshot; no default system-wide database or user GUI configuration import. Database ownership, permissions, size and format are checked at the snapshot boundary. The snapshot is trusted owner-generated input, not a supported arbitrary upload format.
- Bound query input size, returned entries/bytes, matching work, allocation and process duration. A match limit applies during collection. Distinguish cancelled, timed-out, truncated, failed and completed searches in the versioned response contract.
- Preserve filesystem path bytes without ambiguity. Decide the response representation for non-UTF-8 paths before claiming arbitrary Linux filename support.
- Keep index updates separate from serving. Admission comes from explicit configuration and mount/storage evidence, not a live probe that may itself block. Initial validation uses only owned synthetic fixtures.
- A safe traversal must exclude disallowed mounted storage before its first metadata operation; the existing one-filesystem flag and exclusion rules do not meet that condition alone. The exact confinement mechanism is a decision inside the update slice.
- Failed updates preserve the last accepted snapshot. Unproved cleanup quarantines update activity; no expiry-driven replacement.
- Monitoring cannot implicitly add roots or start inside the query CLI. Monitoring qualification follows contained refresh, including event overflow and offline-root behavior.
- Existing file-searcher remains the MCP and intent-routing layer. FSearch supplies filename discovery, without duplicating the MCP stack in C.
- Benchmark before choosing default adoption. Retain SQLite fallback and existing plocate containment until a replacement is independently qualified.

## Testing Decisions

- The primary external seam is the JSON CLI invoked as a subprocess against synthetic snapshots. Assert response semantics, exit behavior, byte/path correctness, failure behavior and deadline behavior rather than private implementation shapes.
- Build fixtures through the existing database APIs; test persisted search after removing the fixture root.
- Trace all query threads and processes to prove the exercised CLI never reaches the indexed root. Include a known probing negative control so instrumentation is shown sensitive. Also run beyond the existing polling interval to exercise lifecycle isolation.
- Retain upstream Meson tests as GUI/engine regression coverage. Existing database round-trip and incomplete-search tests supply prior art.
- Use injected provider-free traversal/worker failures for containment; do not reproduce kernel stalls on real disks or mounts.
- Test MCP integration at the existing public tools using the packaged candidate in an isolated configuration.
- Separate fixture correctness, resource benchmarks, real-root admission, installed identity and direct live MCP acceptance. None implies the next.

## Out of Scope

A network API, content indexing, replacing Everything, importing system plocate databases, scanning whole Windows drives, disk repair, permission revalidation on every hit, silent automatic adoption, unsolicited upstream issue publication, user-runtime changes in this planning phase and a mandatory full GUI rewrite.

## Further Notes

The initial probe established short-lived cached name/extension queries after deleting the source root, plus an observed content-type probe hazard. It did not establish long-lived safety, bounded engine allocations or production containment. First delivery should settle those limits at the CLI seam before extending indexing.
