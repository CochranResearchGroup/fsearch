# Plan0006 source checkpoint and resume reconciliation

Operator authorized source commit/reconciliation and bounded continuation.
Repository CochranResearchGroup/fsearch, branch feat/incremental-generations,
prior base51f6af730f8b3f8f459c721ec6b6fffa8f34d49d. Fresh origin fetch shows no
divergence before checkpoint. Worktree is the durable incremental-generations
worktree. Helper packaging is separately checkpointed at7e753d5c.

## Qualified source and open gates

Broker confinement/transport/owned delivery and private durable catalog recovery
are supporting source; M3 and M4 remain IN_PROGRESS, M5/M6 PENDING. M1/M2 source
acceptance is retained. Shared service/build boundaries make a clean independent
M3/M4 source split unsafe; preserve the coupled implementation as one source
checkpoint. Historical successful and failed receipts are retained unchanged.
The finite activation packet is historical preparation, not current activation
authority; never run it against an already-installed helper. No installed service,
root config, helper or registration is changed by this task.

Primary-agent fresh verification: owned helper lifecycle11/11 pass; guarded
candidate rebuild passes. Initial suite37 pass,2 fail,1 explicitly skipped.
The two failures were import-path defects in source/run_path test fixtures after
service gained a sibling journal module. Add the exact source/runtime sibling
path to those fixture imports; production lookup/custody is unchanged. Follow-up
boot_recovery, incremental_visibility and broker_process_cli_mcp all pass; broker
fixture is explicitly selected through FSEARCH_FRONTEND_ACCEPTANCE_ROOT. This
resolves the prior skip. Original suite/log and failed launch/configuration
attempts remain in checkpoint-review evidence. No claim of a single all-green
full-suite rerun or current-scale acceptance.

Current plan header/latest checkpoint/next sequence now reflect the later owned
helper and M4 source evidence. Historical blocked-goal statements are preserved
and explicitly superseded: goal tool returned no goal before this task. Current
objective is checkpoint/publish, reconcile and diagnose capacity; the full program
is still open. Original600MiB steady/1.25GiB update targets and root/privilege
boundaries remain unchanged.

## Next bounded packet

Run the existing2052-mutation/two1024-record-boundary control with owned roots,
unchanged memory/swap/pressure gates,120-second execution budget matching its
registered Meson timeout. The earlier40-second deadline is retained; this is a
sequential fsync diagnostic budget, not a production latency rebaseline. Emit
64-record elapsed/batch/max-mutation timing so an early stop still supplies a
minimum diagnostic. No implementation fix is inferred from host pressure.
Terminal outcome: qualified capacity result or retained bounded failure with
observed progress/cause and exact next gate. Full M4 crash/corrupt-pair/startup
qualification and M3 dependency are separate follow-on work.

Memory disposition forbidden: no personal durable-memory writes authorized;
current source/receipts suffice and advisory discovery is unnecessary.
