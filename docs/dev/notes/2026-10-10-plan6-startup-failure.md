# Plan0006 durable startup transport failure

State: SOURCE_PARTIAL; M3/M4 IN_PROGRESS, M5/M6 PENDING.
Starting sourceaf117ca5; fsearch-incremental-generations worktree.

Public seam: actual supervisor JSON socket protocol and owned out-of-process
worker fault executable. Fixture setup and final recovery use the actual native
worker. No internal collaborator mocks; faults are injected at its executable
transport boundary. Root and original snapshot are absent during failing startup
and final durable recovery.

Red: EOF before ready caused the second query to launch a second worker.
Exact original command is retained in m4-startup-eof-red-pressure.json (exit1).
Cause: abort_worker reaped the failed worker and scheduled another launch despite
incomplete durable startup. The corruption-selection exhaustion guard applied only
to checkpoint content errors, leaving transport/replay errors eligible to retry.

Minimal fix: record terminal startup_exhausted for durable startup/replay transport,
protocol, startup-deadline, replay-ack, containment and active-request deadline
failure while worker_ready is false. Existing proven corrupt-generation selection
fallback remains bounded; no new selection, root probe or background retry.
The error applies to that supervisor lifetime. A deliberate stop/start with the
real worker recovers the original durable pair and replay.

Green: EOF, invalid startup frame, startup timeout and EOF after a valid ready
handshake while replaying sequence2 each admit one launch across six queries,
leave no owned children and report the exact failure code. Restart with the real
native worker recovers sequence2, snapshot identity, both entry IDs and explicit
catalog_recovered_source_gap. Focused corruption fallback and replay regression
also pass. Receipts bind exact commands and unchanged cgroup/resource limits.

The emitted replay handshake is an adversarial transport fixture, not native
checkpoint-validation evidence. Native checkpoint/replay correctness is covered
by the separate actual-worker regression and final actual-worker recovery.

First full regression:61/62 pass; monitor_supervisor failed its existing
overflow-reconciliation five-second deadline. Raw full log and pressure receipt
retained. Isolated unchanged overflow case passes under the same bounds. One
bounded full control passes62/62, zero skip/failure, 151.123s.
No timeout or resource limit was raised. Dedicated cgroup memory.peak
187478016 bytes, swap.peak=0.
Retain m4-startup-full-control-testlog.txt and pressure receipt. All sampled
owned PIDs from red/green/full/monitor controls are absent in fresh /proc readback;
source/runtime hashes in m4-startup-failure-identity.json.
## Standards review

Fixed pointaf117ca5; zero blocking findings. Repeated public socket/start harness
is nonblocking_backlog; do not widen this repair into a test-framework refactor.

## Spec review

Zero startup-packet blockers: red before minimal fix, terminal failure within the
supervisor lifetime, explicit restart retains durable identity and replay, and
corruption fallback remains bounded. Full monitor deadline variability remains
needs_evidence; retain the failed run even if the bounded control passes. Full process/power-loss/crash/current-scale qualification and M3/M5/M6
remain open. No reboot, installed activation, root grant or real-root scan.

Graphiti prior-boot closeout is completed_visible with retained receipt.
Current source-backed startup-failure closeout will receive its own disposition.

Graphiti disposition: queued, job219f5b87-92ec-47f8-86a2-76d4995c8b73; queue acceptance only, reconcile before related retry. Next: M3 broker event semantics and durable observation-cursor reconciliation under existing owned-fixture authority.
