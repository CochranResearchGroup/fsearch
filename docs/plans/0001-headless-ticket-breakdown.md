# Headless filename search ticket breakdown

Status: APPROVED by the operator on 2026-10-04; five tickets published. Parent: https://github.com/CochranResearchGroup/fsearch/issues/1. Source spec: ../specs/0001-headless-filename-search.md.

1. **Search private snapshots through a bounded JSON CLI**
   - Blocked by: none.
   - Delivers: no-display, query-only cached filename search using explicit private snapshots, structured errors, completeness/freshness, literal input and bounded matching/output. Includes comparative first-invocation/subsequent-process fixture measurements to establish whether CLI startup is viable.
   - Acceptance: zero indexed-root probes, including beyond the old polling interval; rejected probing syntax; missing-load no-scan behavior; cancellation/deadline and resource limits; filename round-trip; upstream tests pass. If engine bounds or format safety require extraction work, include it here rather than land an unsafe interim CLI.

2. **Refresh an approved root while preserving the last accepted snapshot**
   - Blocked by: 1.
   - Delivers: explicit, separate snapshot refresh with pre-probe storage confinement, atomic acceptance and durable update-worker quarantine.
   - Acceptance: synthetic nested-mount/redirection fixtures or injected adapters prove exclusion before metadata access; failed/interrupted updates leave last accepted snapshot searchable; no replacement after unproved cleanup. Decide the confinement mechanism using primary-source evidence before real-root use.

3. **Keep approved-root snapshots fresh through contained monitoring**
   - Blocked by: 2.
   - Delivers: create/rename/delete changes reach snapshots without full rescans on every request, with truthful freshness and offline/overflow state.
   - Acceptance: synthetic events, overflow, offline root, shutdown and restart cases; no implicit root expansion; query CLI remains filesystem-independent.

4. **Route Linux filename requests through file-searcher MCP**
   - Blocked by: 1 (not 2 or 3; synthetic snapshots suffice for integration).
   - Delivers: optional FSearch backend under existing tools, preserving intent, result schema and partial-result behavior alongside SQLite and Everything.
   - Acceptance: packaged candidate and isolated MCP smoke; missing/busy/degraded backend leaves other results usable; defaults do not change until adoption. Requires an issue in file-searcher with a cross-repository dependency on ticket 1.

5. **Qualify and install the replacement reversibly**
   - Blocked by: 2, 3, 4.
   - Delivers: measured candidate, approved real-root index, packaging, reversible registration and direct installed CLI/MCP acceptance.
   - Acceptance: freeze performance/resource gates before benchmark; compare scoped synthetic candidates fairly; prove backing-storage admission separately; verify installed code/config identity, shutdown resource census and rollback receipt. Real-root indexing and installation require operator-directed execution at this phase.

These are vertical deliveries, not separate lexer/build/MCP refactor tickets. Tickets 2 and 4 can proceed independently after 1. Monitoring waits for refresh containment; adoption waits for all serving, update and integration qualifications. Published issues and native dependency IDs are recorded in headless-tickets.json. The CLI slice (#2) is implemented locally pending integration; refresh, monitoring, MCP integration and installation remain open.
