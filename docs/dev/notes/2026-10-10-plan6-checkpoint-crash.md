# Plan0006 interrupted checkpoint publication

State: SOURCE_PARTIAL. M3/M4 IN_PROGRESS; M5/M6 PENDING.
Starting source1db59ca7; owned worktree fsearch-incremental-generations.

Public seam: actual supervisor/native worker catalog mutation, query, lookup,
status and recovery CLI. Each run accepts checkpoint sequence1, acknowledges
sequence2, requests compaction and crashes during second checkpoint publication.
Root and original snapshot are removed before recovery. Both mutations, raw path
bytes, snapshot identity and entry IDs survive actual worker restart.

One boundary was exercised at a time:
- Before manifest rename: completed unpublished pair cannot displace accepted
  selection; prior checkpoint plus its committed journal recovers sequence2.
- After manifest rename and directory fsync: newly selected pair recovers sequence2.
- While native checkpoint writer is gated before its first write: query still
  serves the acknowledged mutation, then supervisor SIGKILL interrupts publication.
  Prior accepted pair plus journal recovers despite the incomplete inactive image.

Existing code passes; no speculative production fix or invented red cycle.
Injected hooks are owned-test-only. Gate state identifies the interruption;
correctness assertions use public protocol responses, not artifact contents.
The existing native writer gate is reused, not a second injection framework.

Validation: registered Meson3/3 pass, zero skip/failure. Exact commands,
pressure/cgroup limits and terminal outcomes are in m4-checkpoint-*-pressure.json
and m4-manifest-*-pressure.json. Raw Meson log retained as
plan6-evidence/m4-checkpoint-three-testlog.txt. Identity hashes and fresh absence
of all sampled owned PIDs are in m4-checkpoint-crash-identity.json.
Combined serial regression:53/53 pass, zero skip/failure, 156.313s;
cgroup memory.peak=191217664 bytes, swap.peak=0.
Exact command and host-pressure evidence in m4-crash-full-serial-pressure.json;
raw output in m4-crash-full-serial-testlog.txt. All sampled owned PIDs absent.
The first full run used excessive parallelism and exhausted TasksMax128: retained
overparallel raw logs are unqualified. It was stopped, then serial execution
passed under the same memory/swap/task limits; no limit was relaxed.

Matt review: Standards and Spec checked separately; zero blocking packet findings.
Standards nonblocking_backlog: duplicated socket/start/reap harness between append
and checkpoint tests; defer extraction until the crash matrix settles, preserving
public-seam assertions and independent fault controls.
No production behavior change. Process crash only; local-filesystem power loss,
prior-boot recovery, complete crash matrix and current-scale startup remain open.
M3 watch/mount/ignored-policy adversarial acceptance and current-scale freshness,
M5 resource aggregation/24-hour soak and M6 installed rollback/72-hour soak remain
unaccepted. No reboot, installation, privilege grant or real-root scan occurred.

Next packet: prior-boot/dirty-startup fail-closed recovery at owned state boundary.
Graphiti initial disposition: unavailable, rejected before queue because the prior
append extraction was active. Exact reconciliation found no episode and explicitly
authorized retry; retain both receipts. Append memory is completed_visible.

Graphiti final disposition: queued, job db6addfd-ee48-4be4-a595-37cbb5ced833; queue acceptance only, reconcile before a related retry.
