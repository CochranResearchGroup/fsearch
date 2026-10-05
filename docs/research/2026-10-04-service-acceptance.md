# Warm service source acceptance, 2026-10-04

## Scope and identity

Implements approved FSearch issue #7 locally. Service and replacement tickets #7/#8 are published under planning parent #6; existing file-searcher #20 and FSearch #5 have native blocking links to the new slices. Parent #1/#6 and all integration-dependent tickets remain open. This is the first fixed-snapshot service slice, not replacement or deployment.

Branch: `feature/7-warm-local-service`. Base: `d531eb3b50560fb7d9ba731787100d827f4e1e8a`. All changes remain uncommitted. Current source/configuration and executable hashes: `service-evidence/source-identity.json`. No installed service, user MCP registration, real-root scan or default-backend change occurred. Existing file-searcher worktree remains clean.

## Delivered behavior

- Shared C private-snapshot loader/matcher/JSON seam preserves direct CLI behavior. The resident C worker loads once, accepts bounded private framing and omits GUI monitors/scans/polling.
- A Python 3 standard-library supervisor provides an owner-private Unix socket with peer UID checks, one active query, eight queued requests, sixteen connections, 64 KiB request frames and bounded responses. CLI queries use native C warm transport; Python control code runs only for cold startup/reconciliation and explicit administration.
- Queue-inclusive deadlines, bounded startup, cancellation/disconnection, worker crash and clean stop produce explicit outcomes. A later new request may restart after a one-second cooldown; failed requests are not replayed.
- Worker identity is durably saved before opening its snapshot. Parent-death SIGKILL, bounded reap and identity reconciliation remain separate proof boundaries. Unproved reaping persists quarantine across restart; eventual reaping does not clear quarantine. Explicit recovery refuses incomplete identities or possibly-live workers.
- Supervisor effective soft address-space ceiling is 64 MiB, with a hard ceiling at most 256 MiB to allow worker children to set their approved 256 MiB ceiling. Stricter inherited hard limits are honored. Only one worker is admitted in this slice.
- Fixed-snapshot identities and cached visibility are reported. Explicit database mismatch fails; removing/replacing its pathname cannot silently retarget the loaded snapshot. Empty literal extensions retain direct CLI semantics.

Public contract and commands: `../warm-service.md`. Safe runtime-storage admission is separate from owner-private directory validation.

## Verification

`service-evidence/qualified-tests.txt`: all 15 Meson targets passed: 13 upstream targets, 15 direct-CLI cases and 19 service cases. The direct isolation test now asserts at least 5.9 seconds elapsed; the fault library resumes interrupted sleeps so a signal cannot shorten the intended six-second dwell.

The service tests exercise cold on-demand client access, address-space limits, uncertain reap/quarantine across restart and explicit recovery, malformed frames, queue saturation and queued expiry, shutdown acknowledgement/reaping, invalid identity rejection, active disconnect and new-request restart, startup deadline, worker crash, six-second traced idle/query isolation, supervisor death/reconciliation, snapshot mismatch, maximum escaped query size, directory/socket/symlink guards, retained snapshot after pathname removal, missing-snapshot no-scan failure, escaped request-ID byte caps and empty-extension parity.

Red/green logs are retained under `service-evidence/`. Inherited root fixture flags enable GUI monitoring/startup scans/rescan; query-only loading ignores them. The native service traces follow all processes and observe zero indexed-root file syscalls after deleting the owned roots. Earlier content-type negative control receipts establish instrumentation sensitivity. No real kernel/disk stall was induced.

One cancellation/restart availability assertion failed under the full run while giving a fresh request the default two-second budget, which also includes the deliberate one-second restart cooldown and injected half-second query delay. The targeted diagnostic passed. Its availability assertion now requests a bounded five-second budget; default and queued/active deadline behavior remain independently tested. Failure logs were retained, not rewritten as success.

## Frozen service benchmark

Frozen gates: `service-evidence/qualification-plan.md`. Raw records/traces: `service-evidence/benchmark.json`, `service-10000.trace`, `service-100000.trace`. Both workloads passed all socket/resource gates.

| Owned fixture | Warm ten-hit socket p50 / p95 | Warm zero-hit socket p95 | Fresh native CLI p50 / p95 | Supervisor + worker RSS |
|---|---:|---:|---:|---:|
| 10,000 names | 0.85 / 1.07 ms | 1.82 ms | 7.19 / 10.54 ms | 27,592 KiB |
| 100,000 names | 13.72 / 14.73 ms | 19.52 ms | 19.55 / 22.64 ms | 41,712 KiB |

Thirty subsequent requests after the first; exact ten hits and completed zero hits verified. First socket hit requests took 31.47 ms and 60.83 ms respectively with the supervisor already listening; these are not end-to-end cold service launch measurements. Summed observed RSS is not peak memory. Six-second idle CPU was 0.02 / 0.03 seconds, worker identity stayed constant, and traced queries after removing roots had zero indexed-root file syscalls.

The initial Python-client benchmark is preserved as `benchmark-python-client.json`: fresh CLI p95 was 64.82 ms / 101.45 ms. That evidence justified native warm CLI transport; the current receipt reflects the final native transport. Potentially warm OS caches, flat fixtures and source binaries do not establish full MCP, real-root, million-file or installed performance. Sequential matching remains proportional to examined cached entries.

## Source review

Standards: preserve upstream GUI entry points, original worker-bearing constructors and existing load behavior; use the shared snapshot seam without duplicating matching logic. Fixed C compiler indentation warnings. Raised declared Meson minimum to 0.50 for the actual script configure/install features. Restricted the new headless library source to Linux so Linux-specific stat/socket assumptions do not alter non-Linux GUI builds. `review-build.txt` confirms the final build-graph correction leaves qualified executable hashes unchanged. `git diff --check` passes. No blocking documented-standard finding remains.

Spec: reviewed owner-private pathname/peer boundary, request/frame/output caps, deadlines including queued work, worker startup gating, cleanup evidence, durable quarantine/recovery, fixed snapshot identity, cold-only Python startup and shared direct/warm input semantics. Accepted initial transport overhead and empty-extension parity findings were fixed and qualified. Replacement, refresh admission, monitoring, MCP fallback execution and installed qualification remain explicitly outside issue #7. No blocking first-slice finding remains. This is source review against the approved contract, not a committed PR review or deployment review.

## Remaining gates and closeout

No commit or push is authorized by the current repo contract; `docs/agents/codex-stack.md` requires explicit authorization. Issue #7 stays open pending source integration. Issue #8 is blocked by this service and refresh #3. Monitoring #4, file-searcher MCP #20 and adoption #5 remain open. Preserve current installed file-searcher until separate installed acceptance.

`service-evidence/process-census.json` records zero remaining owned source-service fixture supervisors, workers or trace wrappers after qualification. CodeGraph was synced and healthy. Source health, synthetic qualification, integration and installed acceptance remain distinct.

Memory disposition: forbidden; durable personal-memory writes require explicit authorization, which was not given. A machine-readable non-write receipt is preserved in `service-evidence/memory-disposition.json`.
