# Warm private snapshot service

The optional Linux service keeps one private accepted snapshot in a resident C worker. A Python 3 standard-library supervisor owns the private Unix socket, connection/queue limits, deadlines and durable cleanup state. The direct one-shot CLI remains available. Builds do not install or register anything automatically. The local installed qualification is recorded in [installation acceptance](research/2026-10-04-install-acceptance.md).

Use an existing owner-private directory (mode 0700) on admitted native storage and an owner-private snapshot (mode 0600). The service does not create a runtime directory or scan roots. Directory permissions establish privacy, not storage-health admission; runtime storage is qualified separately during installation.

```sh
build/src/fsearch-cli --socket /private/runtime/search.sock --database /private/index/snapshot.db --query invoice --extension pdf
build/src/fsearch-cli --socket /private/runtime/search.sock --query invoice
build/src/fsearch-service stop --socket /private/runtime/search.sock
```

The first command starts the service on demand if necessary. Warm CLI requests use native C socket transport; Python is used for cold startup/reconciliation and explicit control commands. Supplying a different database to an existing service fails with `snapshot_conflict`. The first slice serves a fixed snapshot: deleting or replacing its pathname does not retarget the loaded worker. Explicit safe replacement is issue #8.

For foreground operation, use `fsearch-service serve --socket PATH --database PATH`. `fsearch-service query` is an alternative Python client; its interpreter startup is slower than the native warm CLI. A failed connection without an explicit database never scans or starts a default database.

## Socket contract

One UTF-8 JSON object followed by a newline per connection; one versioned JSON response followed by a newline, then close. Required query fields: `schema_version: 1`, `request_id` (UTF-8 string at most 64 bytes), and `query` (literal UTF-8 substring at most 4096 bytes). Optional fields: `extension` (null/absent means no filter; empty string is a literal empty extension), `kind`, `path`, `match_case`, `limit`, `max_candidates`, `max_bytes`, `timeout_ms`. Defaults and query limits match the direct CLI contract. Unknown fields/operations and malformed frames are rejected. Frames are capped at 64 KiB to accommodate JSON escaping within the raw query allowance.

The optional `expected_database_b64` is the base64 of the expected absolute lexical filesystem path bytes. It guards an explicit client database selection without probing its current pathname. The snapshot response contains a descriptor-derived identity (device, inode, size, modification/change timestamps), saved scan/error observations and cached visibility. A response does not establish current filesystem access. The private worker framing is internal and not a public API.

Errors before request admission may have a null request ID; the connection still identifies their single request. Busy, unavailable, failed, cancelled and timed-out results never establish a completed empty search. File-searcher MCP integration and SQLite fallback routing remain issue #20; this source service returns diagnostics but does not itself execute SQLite.

## Bounds and recovery

One active request, at most eight queued requests, at most sixteen live connections. Queue-inclusive deadlines default to two seconds, with a ten-second maximum. Partial-input and stalled-output clients have two-second bounds; snapshot startup has a separate two-second bound. A client deadline can expire while startup continues within that startup bound. Active disconnect/cancellation or deadline kills the worker and explicitly fails other affected requests; the service does not replay them. A later new request can start a new worker after a one-second restart cooldown.

Supervisor effective address-space limit is 64 MiB; its inherited hard ceiling remains at most 256 MiB so a forked worker can raise its soft ceiling to the approved 256 MiB worker limit. Limits honor stricter inherited hard caps. These are address-space ceilings, not RSS measurements. This slice permits only one worker; replacement's two-worker envelope is not implemented.

Before a worker may open the snapshot, the supervisor durably records its PID, kernel start time and boot identity, then releases its startup gate. The worker requests a parent-death SIGKILL. Neither signal delivery nor a kill attempt proves cleanup: a failed bounded reap leaves durable quarantine. When reap evidence becomes available, the supervisor reaps without clearing quarantine. There is no expiration-driven replacement.

After an unexpected supervisor exit or unproved cleanup, stop any still-running supervisor and reconcile explicitly:

```sh
build/src/fsearch-service recover --socket /private/runtime/search.sock
```

Recovery holds the instance lock, validates the saved identity and refuses while the recorded worker could still be alive. A missing or malformed identity is not absence proof. Recovery does not kill an arbitrary saved PID. Start a new request only after successful recovery. Corrupt state requires operator investigation, not automatic deletion.

## Qualification

See [source acceptance](research/2026-10-04-service-acceptance.md) and its frozen gates. Socket queries avoid per-request Python startup; fresh CLI clients still pay native executable startup. GTK development dependencies remain required to build the existing library. The installed CLI and service have separate acceptance evidence. Safe refresh, monitoring, snapshot replacement and MCP routing remain outstanding.
