---
status: accepted service contract; replacement remains a separate approved ticket
---
# Keep an accepted snapshot warm for repeated filename queries

On 2026-10-04 the operator asked whether FSearch should be a service, invoked ask-matt, and directed continuation after recommended lifecycle defaults were presented. Proceed with per-user on-demand startup, serial active queries through a bounded queue, the last accepted snapshot after refresh failure, and quarantine with file-searcher SQLite fallback after unproved worker cleanup.

The load-once native experiment measured 100,000-file warm requests at 11.50 ms median versus 48.84 ms for one-shot queries, with 23,308 KiB loaded worker RSS. Its six-second idle trace followed by a query after deleting the indexed root showed zero indexed-root probes. Evidence: ../research/2026-10-04-resident-prototype.md. This resolves ADR 0001's condition for evaluating a persistent API; its private cached-visibility and separate-update policies remain in force.

Holding an accepted snapshot in memory avoids repeated reconstruction, at the cost of idle memory and a longer-lived failure/recovery lifecycle. The CLI remains a client/diagnostic interface, and file-searcher remains the MCP layer. A private Unix socket is the proposed local interface; no network API is needed. A warm query worker must not gain scans, monitors or filesystem permission checks.

The operator approved the concrete service breakdown; issues #7 and #8 record warm serving and replacement separately. No production socket, service installation or user MCP registration has been performed. Do not claim that warm snapshots remove the matching loop's sequential cost. Prototype source and artifacts are preserved uncommitted under the repo's explicit commit-authorization boundary.

The service slice implements the approved serial queue and address-space limits with native warm CLI transport and a standard-library supervisor. Its source acceptance is recorded in ../research/2026-10-04-service-acceptance.md. Source acceptance is not runtime installation or MCP integration.
