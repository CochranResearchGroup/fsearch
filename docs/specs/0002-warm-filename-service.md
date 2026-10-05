# Warm private filename query service

Status: published planning parent https://github.com/CochranResearchGroup/fsearch/issues/6; operator-approved service contract; accepted direction in ADR 0002. Existing filename-search parent remains open. Date: 2026-10-04.

## Problem Statement

Repeated agent filename requests reconstruct an entire snapshot and start processes on every query. At 100,000 synthetic filenames this costs tens of milliseconds beyond matching. A long-lived query worker can avoid repeated loading, but must preserve private cached visibility and contain failures without accumulating replacement workers.

## Solution

A per-user service starts on demand and keeps an accepted snapshot ready for filename requests. The CLI remains a client and diagnostic interface; file-searcher remains the MCP layer. Results retain explicit completeness and saved freshness. A stalled or uncertain worker cannot cause unchecked restart cycles; file-searcher falls back to SQLite.

## User Stories

1. As an agent, I want repeated requests to reuse an accepted snapshot, so I avoid repeated loading.
2. As an operator, I want on-demand startup, so an unused service does not consume memory by default.
3. As an agent, I want the existing CLI query/result contract, so warm access does not change filename semantics.
4. As an operator, I want local owner-private access, so another user cannot retrieve cached names.
5. As an agent, I want explicit cold-start versus ready state, so startup is distinguishable from query latency.
6. As an agent, I want bounded queue admission, so overload does not create unlimited waiting requests.
7. As an agent, I want a deadline covering queue wait and matching, so queued requests cannot wait indefinitely.
8. As an agent, I want explicit cancelled and timed-out responses, so failed searches are not reported as empty.
9. As an operator, I want worker cleanup evidence, so a timeout does not silently leave runaway replacements.
10. As an operator, I want quarantine retained across service restart, so restarting cannot bypass uncertain cleanup.
11. As an agent, I want SQLite fallback during unavailable or quarantined service states, so discovery remains useful.
12. As an operator, I want query workers to avoid scans, monitors and access checks on indexed roots, so warming does not reintroduce storage stalls.
13. As an agent, I want saved coverage, scan age and snapshot identity, so I know which observations generated a response.
14. As an operator, I want failed refresh to preserve accepted results, so a bad update does not erase working discovery.
15. As an agent, I want coherent snapshot replacement, so one response does not mix old and new observations.
16. As an operator, I want replacement memory bounded, so warming two snapshots cannot exceed the service budget.
17. As an operator, I want explicit shutdown and restart behavior, so abandoned client connections do not retain uncontrolled work.
18. As an operator, I want isolated socket and MCP acceptance, so prototype pipe measurements are not confused with production service readiness.
19. As an operator, I want existing GUI and direct one-shot CLI behavior retained, so the service stays optional.
20. As an operator, I want installation qualified separately, so source readiness cannot silently change my runtime.

## Implementation Decisions

- Accepted direction: per-user on-demand service; one active query through a bounded queue; preserved last accepted snapshot after refresh failure; SQLite fallback and quarantine after unproved reap. No network listener.
- Use a filesystem Unix socket in a validated owner-private directory, owner-only socket permissions and peer effective-user identity checks. Reject unsafe directories, symlinks and unexpected existing sockets rather than blindly unlinking them. Only one supervisor may own a service instance.
- Keep query processing in a resident worker separate from the supervisor. No GUI lifecycle, monitor, root polling, scan fallback or permission revalidation. Query input remains typed literal text, extension and file/folder filters.
- Proposed initial serving contract: one active request, at most eight queued requests, queue-full explicit `busy`; capped frame size and response bytes; request identifiers and versioned framing. Do not let idle clients retain unbounded input buffers or connections. The existing direct snapshot CLI remains available.
- Proposed deadline defaults: existing 2-second request deadline, maximum 10 seconds. Count queue wait after admission. Startup has its own bounded deadline. Disconnection removes queued work; active cancellation may terminate the worker to enforce the bound. Other affected requests receive explicit failure, never fabricated empty results. Do not automatically replay the cancelled request.
- After proved cleanup, a later new request may initiate a bounded restart. No immediate automatic query retry; bound restart frequency under repeated failures. After unproved cleanup, persist quarantine without time-based expiry. Startup must reconcile worker identity and cleanup state; PID alone is not sufficient identity. An explicit recovery must prove old workers absent before accepting replacement.
- Proposed resource envelope for qualification: supervisor address space at most 64 MiB; each resident or replacement worker at most 256 MiB; at most two workers during a qualified replacement. Maximum aggregate declared address-space envelope is 576 MiB, not a measured RSS claim and not an operator adoption budget. Client/MCP memory is outside this envelope and measured separately. Reject loads that exceed bounds.
- Initially serve a fixed accepted snapshot. Explicit replacement is a separate slice: validate candidate privately in a bounded worker, keep old accepted queries available, publish candidate identity only after readiness, pin each admitted response to one snapshot, and retire the old worker with proved cleanup. Refuse overlapping replacement attempts. Candidate failure leaves old snapshot accepted. Unproved worker cleanup prevents another replacement and quarantines serving rather than admitting more workers.
- Accept only explicit private owner-generated snapshots through validated descriptors. Keep the inherited trusted-input format boundary; no arbitrary upload API. Record snapshot identity beyond its timestamp. No real-root scanning inside replacement.
- File-searcher owns MCP routing, fallback semantics and process invocation. A busy/unavailable/quarantined FSearch result does not become evidence of zero matches; preserve backend diagnostics and other backend results.
- Keep service configuration and installed runtime adoption separate. Systemd activation, login startup and automatic monitoring integration are not part of the first service slice.

## Testing Decisions

- Highest public seam: CLI requests through an isolated owner-private Unix socket, consuming the same versioned JSON result semantics as direct snapshot queries. Keep the existing direct CLI tests as regression coverage. MCP integration uses the existing public file-searcher tools in an isolated configuration.
- Test literal inputs, byte-preserving filenames, completeness, freshness, private snapshot rejection and no-scan failures through subprocess clients.
- Use synthetic faults to qualify startup timeout, active cancellation, queue saturation/expiry, disconnected clients, worker crash and cleanup uncertainty. Assert no replacement after unproved reap, including supervisor restart and recovery reconciliation.
- Trace all service threads/processes during idle and query runs beyond the original polling interval against removed fixture roots. Preserve the known probing negative control as instrumentation sensitivity evidence.
- Replacement tests cover coherent responses, failure before publication, bounded two-worker overlap, rejection of simultaneous replacement, budget failure and retiring-worker quarantine.
- Freeze socket round-trip, aggregate memory, idle resources and cleanup gates before production qualification. Native pipe prototype thresholds establish research viability only; do not substitute them for service acceptance.

## Out of Scope

Real-root admission, filesystem traversal confinement, indexing implementation, automatic monitor-triggered replacement, network APIs, shared multi-user indexes, changing file-searcher defaults, automatic installation, changing GUI behavior and unbounded parallel query execution.

## Further Notes

The resident prototype supports the architectural direction: 100,000-file ten-hit p50 11.50 ms versus one-shot 48.84 ms, loaded worker RSS 23,308 KiB. It does not implement the socket, authentication, queue, hard limits, cancellation, replacement or quarantine. Sequential matching remains a distinct optimization opportunity. Existing refresh, monitoring and installation tickets remain open; only the service and MCP dependency changes are proposed here.
