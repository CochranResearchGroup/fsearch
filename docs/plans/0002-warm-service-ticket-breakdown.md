# Warm-service tracer-bullet proposal

Status: APPROVED by the operator on 2026-10-04; published ticket IDs in warm-service-tickets.json. Spec: ../specs/0002-warm-filename-service.md. Preserve existing parents and completed local CLI work.

1. **Serve private snapshot queries through a warm local service**
   - Blocked by: FSearch #2 (integrated bounded CLI/snapshot seam).
   - Delivers: owner-private Unix socket, on-demand bounded startup, CLI client, resident query worker, serial requests, eight-request queue, queue-inclusive deadlines, bounded memory/input/output, cancellation/disconnect handling and durable quarantine with explicit recovery.
   - Verify: client requests use cached names without indexed-root probes; queue saturation/expiry and startup/worker faults are structured; no replacement after unproved cleanup across supervisor restart; direct CLI and upstream regressions pass. Freeze socket performance/resource gates before measuring. Fixed snapshot only; no replacement yet.

2. **Replace a warm service's accepted snapshot without losing qualified results**
   - Blocked by: slice 1 and FSearch #3 (accepted snapshot refresh).
   - Delivers: explicit candidate acceptance, coherent response identity, old snapshot while candidate loads, bounded two-worker overlap, failure preservation, retiring-worker cleanup and quarantine.
   - Verify: failed/budget-exceeding candidates preserve old results; one response uses one identity; overlapping replacement rejected; worker count/address space bounded; uncertain retirement cannot admit another worker.

3. **Extend existing file-searcher #20 to use the warm service**
   - Blocked by: slice 1; replaces direct-CLI-only route with service-aware access while retaining the direct diagnostic path.
   - Delivers: existing MCP tools route filename requests through warm queries with preserved intent/results, busy/unavailable/quarantined diagnostics, SQLite fallback and isolated packaged acceptance. Do not create a duplicate MCP ticket.

4. **Update existing FSearch #5 adoption dependency**
   - Blocked by: existing refresh #3, monitoring #4, file-searcher #20, and slice 2.
   - Delivers: installed service/client/MCP identity, aggregate/idle resource measurements, rollback and explicit real-root storage admission. It remains the existing adoption ticket, not a new packaging-only delivery.

Proposed contract defaults are in the source spec: queue eight, 2-second deadline, supervisor 64 MiB address space, workers 256 MiB each, at most two during replacement. These are reviewable qualification defaults, not measured real-system budgets. The two new tickets and existing MCP/adoption dependency extensions have been published. The warm spec may be published as a planning parent; publishing a spec does not approve its tickets or runtime installation.

## Source continuation

Issue #7 is implemented and qualified locally on `feature/7-warm-local-service`; see ../research/2026-10-04-service-acceptance.md. Changes remain uncommitted/uninstalled and the issue remains open pending integration. The remaining slices have not been implemented.
