---
status: accepted
---
# Serve headless filename search from private snapshots

The operator requested Linux filename search alongside Everything's Windows coverage, while avoiding plocate's query-time filesystem stalls. On 2026-10-04, the operator directed continuation after the recommended JSON CLI and private cached visibility choices were presented; we proceed with those defaults. Headless filename queries consume per-user snapshots and report freshness and completeness rather than revalidating access to every result. Index updates and monitoring are separate from query serving.

This deliberately accepts stale names and changed-permission names in a private owner-scoped index; it does not authorize exposing another user's index. Content-type probing, automatic scan fallback and root reappearance polling cannot run inside a query-only lifecycle. Storage admission and update-worker containment remain separate qualification work. Everything retains Windows coverage, and file-searcher retains MCP routing. A persistent API is deferred until measurements show a CLI is insufficient.
