# Plan0006 durable catalog prior-boot state boundary

State: SOURCE_PARTIAL; M3/M4 IN_PROGRESS, M5/M6 PENDING.
Starting source6c02c37b, worktree fsearch-incremental-generations.

Actual supervisor/native worker public mutation/status/query/lookup and CLI
startup/recovery are exercised on an owned fixture. After accepted checkpoint1
and acknowledged journal mutation2, stop the actual service and prove its worker
absent. Replace only the owned state artifact with canonical synthetic prior-boot
identities referencing the still-live test PID, then remove root/original snapshot.
This isolates boot-proof behavior from PID absence without rebooting the host.

Ready, starting and quarantined states with coherent prior-boot proof recover
sequence2, same snapshot identity, raw bytes and both stable IDs. Query coverage
is explicitly deferred with catalog_recovered_source_gap.
Current-boot live identities and mixed prior/current-boot live candidate state
refuse serve/recover/serve with quarantined, preserve state bytes and leave no
owned child processes. After correcting only the synthetic state, recovery passes.
No production source behavior change was required.

Retained initial failure: the mixed fixture originally used two different old
boots, with every identity individually absent. Startup correctly refused
automatic recovery, but explicit recovery correctly allowed proved cleanup.
That expectation was wrong, not a production defect. The corrected fixture uses
an actual live current-boot candidate and proves the intended fail-closed gate.
Original receipts and initial raw testlog remain unqualified for that case.

Validation: five registered tests pass, zero skip/failure. Exact commands,
resource limits and observed results in m4-prior-boot-*-pressure.json and
m4-*-boot-refusal-pressure.json; raw corrected log m4-prior-boot-corrected-testlog.txt.
Hash/PID absence receipt m4-prior-boot-identity.json. Earlier53 full regression
remains independently valid; no claim of a combined58 full run.

Matt review at fixed source6c02c37b: Spec zero blocking findings for this bounded
state proof; Standards zero blockers, nonblocking_backlog for duplicated public
socket/start harness across crash tests. No speculative production refactor.
Synthetic boot metadata with actual runtime is not real reboot or filesystem
power-loss qualification. No reboot, installed activation, root admission or
real-root scan occurred. Full M3/M4 and M5/M6 gates remain open.
Next packet: bounded startup/replay worker transport failure, preventing a fresh
worker on every query when durable startup cannot become ready.

Graphiti checkpoint-crash closeout is completed_visible with retained receipt.
This distinct prior-boot source qualification is queued separately with provenance.
