# Plan0006 bootstrap qualification before publication

State: SOURCE_PARTIAL. M3/M4 IN_PROGRESS; M5/M6 PENDING.
Starting checkpoint9e3fcec925bb5d386f708b9e935975cbb6954d32.

Public red control: an admitted in-root CREATE during bootstrap caused
bootstrap_changed, but the serving snapshot identity had already changed.
The old code scanned into the canonical cache and replaced serving before
qualifying the namespace. This violates preservation of the last accepted
generation on a rejected update. The descriptor fixture is synthetic; physical
owned files and native refresh/query processes are real. It does not qualify
actual kernel dirty-startup delivery. The first red attempt misread the status
schema; retain it as a fixture failure. Corrected red-b is the defect evidence.

Fix: scan into one fixed private candidate, inventory and qualify through one
isolated native reader, then reap/reconcile that reader before publishing the
same candidate. Candidate custody and fsync precede atomic cache rename; the
serving reader accepts the resulting identity. Events after the baseline cut
remain queued until the serving reader accepts that image. Unproved preview
cleanup blocks a later bootstrap before refresh. Failed qualification preserves
both public accepted snapshot identity and canonical cache bytes; coverage is
deferred and a fresh MCP query cannot see the unqualified filename.

Validation: first bounded green2/2; final serial regression63/63, exit0,
155.477s, cgroup memory.peak194703360 bytes, swap.peak0. Actual fixed-root
fanotify regression exit0,16.516s, reader/test cgroup peak147025920 bytes,
swap0. Public CLI/fresh MCP, stable distinct hard-link identities, subtree moves,
symlink boundary, clean restart and root replacement controls pass. Staged
runtime hashes and starting-source identity are in the preflight receipt.
All sampled owned PIDs are absent in a fresh proc readback. Prior fixture files
were archived reversibly after recorded process identity absence checks.
Installed helper/root/config and privileges were unchanged. Helper/kernel
combined aggregate, production scale and actual dirty-bootstrap delivery remain
unqualified; this does not close M3 or establish durable event cursor continuity.

Matt review against the fixed starting checkpoint: Standards zero blockers;
existing socket/test framing duplication remains nonblocking backlog. Spec zero
bounded blockers: qualification precedes accepted cache/serving replacement,
private reader cleanup precedes replacement reader construction, failed admission
retains accepted state and truthful deferred coverage. Full crash/power-loss,
mount/ignored/watch-exhaustion/adversarial/current-scale, aggregate24h and
installed rollback72h gates remain open. No reboot or workspace activation.

Graphiti: previous session-loss receipt reconciled completed_visible, no retry.
This qualified source outcome receives a queued singleton with this note as
provenance. Queue acceptance alone is not terminal persistence proof.
Next: bounded M3 ignored-policy/mount and observation-loss admission controls,
then remaining M4/aggregate gates under the unchanged full objective.
