# Plan0006 restart checkpoint

State: OPEN / IN_PROGRESS. This is a checkpoint, not program acceptance.
Goal: execute the full Plan0006; no implementation theater; monitor host pressure; stop/checkpoint before2million tokens or3hours.
Execution began2026-10-09T01:34:28Z; reserved final checkpoint04:19:28Z. Budget usage at03:41:27Z:806573tokens,7917seconds. Controls persist across turns/plan revisions. Read clock/goal before new work; do not restart the budget.

## Authority and source custody

Canonical plan: docs/dev/plans/0006-2026-10-08-incremental-service.md. Native issue26 OPEN; M3issue29 OPEN. M1/M2 source accepted; M3–M6 unaccepted.
Native source: /tmp/fsearch-incremental-generations, feat/incremental-generations, prior implementation checkpoint7bc0e05ec20161d703e2a060af0acd72c8388915. Subsequent age/health source is the current branch HEAD, bound by m3-health-source-runtime-identity.json; verify current remote rather than reverting to this older checkpoint. Preserve the original fsearch checkout and other prototype/plan worktrees; do not merge prototypes wholesale.
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


Age/health continuation: full28native groups pass with source observation timestamps, idle native heartbeat,2second watcher-progress timeout and startup drain barrier. A real paused owned watcher reports deferred while cached queries stay complete and is killed/reaped. Normal fixture max105.37ms,1100burst1.6164s, source-stall deferred/reaped1.5103s. Fresh CLI/MCP evidence and source/runtime identities: m3-health-cli-mcp*, m3-health-source-runtime-identity.json. Retained restart diagnostic proves quarantine after abrupt parent death; test ordering changed to restart only after cleanup proof. No resource/privilege/root decision changed. Read this continuation alongside the original checkpoint; current branch HEAD is authoritative.


## Blocked execution audit | 2026-10-09T04:06Z

The same event-source/resource authority condition persisted through the directory-memory continuation, the independent observation-age/watcher-health continuation, and this third goal turn. Original operator constraint question has no recorded answer. Source7a53377aa167ba7333bfaecf7abd50e9a30a4f16 is published/clean;28native groups and8paired CLI/MCP tests pass. M3 resource/current-scale acceptance is unproved and exact-directory startup failed; ADR0005 remains PROPOSED. The600MiBtarget and approved workspace-only observation scope remain fixed.

Independent known correctness/front-end packets are complete and checkpointed. M4 depends on M3, M5 on M1–M4, and M6 on M5. Advancing the selected event-source architecture now requires choosing whether to preserve the memory target and prepare a bounded privileged-source design, or preserve fully unprivileged operation and propose a measured budget rebaseline. No answer is inferred from elapsed time or automatic continuations. Do not activate privileges, broaden observation, increase budgets or install the unqualified candidate. Speculative alternative implementation and repetition of failed pressure/scale packets are not substitutes for this decision.

Fresh audit: only installed fsearch-worker3338 under active supervisor94383, NRestarts0; native runtime identity remains e0ec8e758db755dbd3cf8b3a83c9e4a467c50137. No owned experiment is live. Worktree clean before this documentation change. Host PSI memoryfull avg10 0.96, IO full0.24, below guard stop thresholds; no additional stress runs. Goal usage at audit926196tokens/9512seconds, below operator stop limits; existing final checkpoint reservation04:19:28Z was not reset. Goal disposition BLOCKED pending operator input, not COMPLETE or an inferred pause. Full M1–M6 objective and24h/72hsoaks remain required on resume.

Memory disposition forbidden; preserve a non-write receipt. Resume by reading the operator choice, current plan/ADR, Git remote and installed identity; then derive one bounded source/qualification packet. A broker-design choice alone does not authorize privileged activation or filesystem-wide observation.


## Operator decision | 2026-10-09

The operator accepted the recommendation to preserve600MiB and prepare a privileged event-broker design for review. The earlier unanswered-choice statements above describe the historical checkpoint. ADR0005 and the Plan0006 current packet are reconciled; the review packet is 2026-10-09-plan6-broker-design.md. Privileged execution, filesystem-wide observation and installation remain separately gated. Next source packet is unprivileged binary-parser/filter fixtures, not actual fanotify activation. Original goal budget/time controls and all M3–M6 acceptance criteria persist. No source executable, installed runtime, root registration or service unit changed in this design packet.

Broker parser continuation: see 2026-10-09-plan6-broker-parser.md and plan6-evidence/m3-broker-parser-pressure.json. Nine synthetic ABI/filter fixtures pass; source is not installed or connected to observation. Original controls and privilege gates persist.

Next-checkpoint goal completed at the broker bootstrap source checkpoint:2026-10-09-plan6-broker-bootstrap.md.15synthetic cases pass; no actual source adapter or privileged activation. Parent Plan0006 remains OPEN.
