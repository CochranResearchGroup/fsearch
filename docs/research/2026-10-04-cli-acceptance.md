# JSON CLI local acceptance, 2026-10-04

Scope: FSearch issue #2, approved CLI-first slice. Branch `feature/2-headless-json-cli`; base `d531eb3b50560fb7d9ba731787100d827f4e1e8a`. Changes are uncommitted and not installed. Published ticket/dependency IDs: `../plans/headless-tickets.json`. Parent #1 remains open.

## Evidence

`cli-evidence/full-tests.txt`: 14 Meson targets passed, including all 13 upstream targets and 15 public CLI test cases. Red/green receipts remain alongside it, including the initial Unicode failure and corrected locale-independent argument handling. `test_headless.py` tests owned temporary snapshots after deleting their source root; failure injection is supplied by a noninstalled test library, never by production CLI options.

Deadline and SIGTERM tests prove structured failure and worker reaping. A 600 MiB injected allocation is denied under the 512 MiB address-space limit. Atomic path replacement after opening retains the validated inode. Private, symlink, FIFO, corrupt and oversized inputs fail explicitly. Literal metacharacters, Unicode, control characters and non-UTF-8 filename bytes round-trip. Result/work/response bounds distinguish incomplete results from completed empty searches.

The lifecycle test traces all processes through a six-second post-load dwell with saved GUI monitor, startup-scan and one-second rescan flags enabled. It observes one worker thread and zero indexed-root file syscalls. The earlier technical probe negative control records six content-type probes, establishing instrumentation sensitivity (`headless-evidence/summary.json`). These synthetic observations do not prove real disk health or approved traversal confinement.

## Frozen benchmark

Plan: `cli-benchmark-plan.md`; results: `cli-evidence/benchmark.json`. 10,000 flat native fixture files, ten exact expected results, first invocation plus 30 subsequent fresh processes per candidate. FSearch p95 16.77 ms, max process RSS 8320 KiB; SQLite fresh process p95 46.47 ms, RSS 18240 KiB; private fixture plocate p95 4.97 ms, RSS 5120 KiB. Warm in-process SQLite p95 0.314 ms. FSearch passes the predeclared 250 ms / 128 MiB first-slice viability gate.

This is potentially warm OS cache, not a cold-cache benchmark or full MCP comparison. RSS is the largest observed process, not aggregate supervisor-plus-worker memory. The plocate index contains only owned fixture paths with visibility checking enabled; LOCATE_PATH is removed and an explicit private database supplied. Setting LOCATE_PATH to an empty string initially caused an extra nonexistent database lookup despite returning correct hits; the benchmark harness was corrected to remove the variable. No system locate index or real-root scan was used.

## Local review

Standards review: preserved upstream GUI entry points and constructor behavior; shared loader/constructor refactors keep their original path, while snapshot entry points omit workers/timers. No unrelated tracked changes or release/version bump. Public subprocess tests exercise behavior rather than mirroring implementation. No blocking documented-standard finding.

Spec review: the issue #2 slice supplies literal typed query-only JSON, explicit private inode loading, bounded collection/output/process lifetime, truthful cached visibility and saved freshness. Reviewed the worker supervision, failure paths and descriptor ownership. Limits and cleanup uncertainty are documented. No blocking slice finding; the remaining parent-spec requirements belong to published refresh, monitoring, MCP and installed acceptance tickets. Inherited snapshot parsing remains trusted-owner input with worker containment, not a hardened arbitrary-upload parser.

## Remaining gates

No source commit, remote branch, PR, installation, user MCP registration or real-root admission was performed. Commit authorization is still required by `docs/agents/codex-stack.md`. Issue #2 remains open pending integration. Issue #3 handles approved-root refresh; #4 monitoring; file-searcher #20 MCP; #5 installed qualification. Preserve current file-searcher fallback until adoption is independently accepted.

Memory disposition: forbidden; durable personal memory writes require explicit authorization, which was not given. A non-write receipt is recorded in `cli-evidence/memory-disposition.json`.
