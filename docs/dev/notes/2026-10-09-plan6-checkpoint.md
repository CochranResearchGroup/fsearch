# Plan0006 restart checkpoint

State: OPEN / IN_PROGRESS. This is a checkpoint, not program acceptance.
Goal: execute the full Plan0006; no implementation theater; monitor host pressure; stop/checkpoint before2million tokens or3hours.
Execution began2026-10-09T01:34:28Z; reserved final checkpoint04:19:28Z. Budget usage at03:41:27Z:806573tokens,7917seconds. Controls persist across turns/plan revisions. Read clock/goal before new work; do not restart the budget.

## Authority and source custody

Canonical plan: docs/dev/plans/0006-2026-10-08-incremental-service.md. Native issue26 OPEN; M3issue29 OPEN. M1/M2 source accepted; M3–M6 unaccepted.
Native source: /tmp/fsearch-incremental-generations, feat/incremental-generations, implementation checkpoint7bc0e05ec20161d703e2a060af0acd72c8388915. Exact remote head verified. Preserve the original fsearch checkout and other prototype/plan worktrees; do not merge prototypes wholesale.
Frontend source: cf8b110762eb289034fc16b2d76718255a176d5a, PR31 merged at7b388cdeec29d5c3ca5e90f085537062e41bbbaa; CI SUCCESS. Closeout PR32 merged at714c012475d0cbec47fae04429fb1578c9011ada. Issue30 CLOSED, bounded frontend plan0007 CLOSED. /tmp/file-searcher-incremental-coverage is clean on docs/30-coverage-closeout; original file-searcher checkout remains untouched.
Tracker readback: https://github.com/CochranResearchGroup/fsearch/issues/29#issuecomment-6073808886.

## Verified source progress

Real directory create/inventory, ancestor move, replacement and move-out work without normal snapshot replacement on owned fixtures. Inventory begin/end preserves pending coverage during idle traversal. Concurrent unresolved move mutations now produce explicit gaps before uncertain-path probes/exports; the regression failed before the fix and passes afterward.
All28native groups pass. Latest recorded normal mutation maximum104.61ms,1100-create burst2.1505s (owned fixtures only). Frontend457comprehensive tests/required isolated smoke checks pass; native candidate8contracts pass after final restaging, including actual CLI creation and fresh MCP current/deferred readback. Source/executable hashes and raw receipts live in plan6-evidence/m3-*.
Pressure guard no longer reads smaps_rollup synchronously, emits null PSS and fails closed on sample gaps>1second. Deadline/RSS/forbidden-PSS/delayed-sample controls pass. Final suite max sample gap0.251s, final native CLI/MCP0.236s; zero owned swap.

## Unresolved critical gate

ADR0005 is PROPOSED. Real100k directory watches retained149.19MiB after bounded reclaim;300k retained422.39MiB kernel+45.94MiB anonymous and233.55MiB remaining file cache. Exact618761directory admission failed60s startup under1280MiB/no-swap. No current-workspace combined memory/freshness acceptance exists.
Operator constraint question is pending: preserve600MiB and prepare a narrowly scoped privileged event-source design for review, or keep unprivileged operation and propose a measured higher budget. No answer or elapsed time grants privilege activation, broader event observation or budget changes. Preserve600MiB and existing scope while awaiting direction. Do not install the partial updater.
Evictable fanotify initial probe retained every mark; eviction unexercised/inconclusive. Artificial-high successor coincided with elevated host memory PSI and was explicitly stopped. Its68s monitor gap is retained; the repaired guard controls are subsequent evidence, not a successful pressure rerun. Do not repeat artificial memory.high stress with monitor/workload sharing the throttle, or infer eviction reliability from5/5events without actual mark loss.

## Runtime and cleanup

No installed files, service units, root configuration or MCP registration changed. Fresh readback: fsearch-workspace-query.service active, MainPID94383, NRestarts0; sole fsearch worker3338 resolves to runtime e0ec8e758db755dbd3cf8b3a83c9e4a467c50137/bin/fsearch-worker. Approved root remains /home/ecochran76/workspace.local. Frontend installed identity must be refreshed before any future installation claim.
All owned experiments are terminal. Every m3-*-root.json manifest was reconciled: roots absent. No owned watcher/query/builder process remains. Final host memory PSI avg10full0; IO avg10full0.04. Re-read pressure before new tests.
Temporary candidate /tmp/fsearch-plan6-m3-runtime is staged source evidence, not an installation. Its hashes are in m3-final-native-runtime-identity.json. Build /tmp/fsearch-generations-build. Do not confuse these with the running runtime.

## Next bounded work and stop rules

Resolve the event-source constraint before any dependent privilege/budget effect. A broker design must explicitly bound observation, filtering, authority, private transport, failure/quarantine and rollback; source preparation is not activation authority. Retain original failure receipts. M4 durable checkpoint/replay, M5 aggregate/current-scale qualification and24hsynthetic soak, M6 installed CLI/MCP rollback and72hsoak remain required. Do not count readiness or shortened soaks as completion.
No whole-Ubuntu/Windows/Google Drive admission, SysRAG unpark, disk repair, reboot or unrelated process cleanup is authorized. Stop/checkpoint by the existing reserved time even if these gates remain open. Keep the full objective active rather than redefining completion.
Memory disposition forbidden; receipt /tmp/fsearch-plan6-m3-directory-memory-disposition.json records zero Graphiti writes. No personal memory update was authorized.
