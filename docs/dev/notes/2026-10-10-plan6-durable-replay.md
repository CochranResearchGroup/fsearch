# Plan0006 bounded durable catalog replay

State: SOURCE_PARTIAL; M4 remains open, M3 dependency not accepted.
Worktree: /home/ecochran76/worktrees/fsearch-incremental-generations.
Branch feat/incremental-generations, base51f6af730f8b3f8f459c721ec6b6fffa8f34d49d.
Uncommitted/unpublished; installed snapshot runtime unchanged.

## Implemented seam

Supervisor --catalog-journal is opt-in. Successful native catalog mutations are
serialized into an owner-private bounded log, log-fsynced, then published through
an atomic fsynced commit cursor before acknowledgement. Existing query startup
loads the qualified base snapshot; the supervisor validates the entire committed
log and request protocol, then streams records to the actual native worker before
query readiness. Assigned entry IDs/sequence must match replay results. No indexed
root metadata, observation or full-root rescan occurs in this recovery path.

Format FSCJ0001: snapshot-bound header, length-framed accepted requests/entry IDs,
SHA256 chaining, separate cursor containing snapshot/sequence/byte boundary/chain.
Cursor publication: exclusive temporary owner-only file, write/fsync, rename,
parent-directory fsync. Log limits16MiB,8KiB/frame,1,024records. Resource exhaustion
refuses before native mutation; it does not grow the log or raise caps. Invalid
snapshot binding, cursor, frame, sequence or chain never certifies currentness.

A partial uncommitted tail is preserved; replay restores the committed overlay,
query coverage remains deferred, and further mutations refuse. Committed-data
corruption serves the original qualified snapshot with explicit deferred coverage
and refuses mutation. Neither fallback nor recovered replay claims watching:
fanotify observation was lost across the restart and needs separate reconciliation.
Graceful/explicit recovery retains existing exact process-identity quarantine;
crash recovery in tests proves/reaps the old worker before explicit recover.

## Evidence

Actual supervisor/native worker regression failed before feature, then passes:
two acknowledged mutations including raw bytes survive supervisor SIGKILL, exact
worker reap and explicit recovery with the indexed root removed. A partial tail
retains acknowledged names read-only; truncation of committed data instead serves
the old qualified baseline with truthful gap and refuses further mutation.
Nine owned journal controls cover fsync error, partial writes, checksum/header,
snapshot binding, sequence and budgets. The partial-tail control was red before
adding the committed cursor, then green. Original intermediate failures retained
in execution; none is reclassified as full M4 acceptance.

Guarded receipt m4-durable-cursor-pressure.json: exit0,8.991seconds,
reader/test cgroup memory.peak28,925,952bytes/swap0; all9sampled owned PIDs absent.
Source hashes in m4-durable-cursor-identity.json. Existing35-test service suite
passes with journaling disabled (28.055seconds), m4-service-regression-pressure.json.
Later cursor-specific changes are limited to opt-in journal path and verified by
journal/native restart controls. Default installed runtime was never replaced.

## Standards / Spec review disposition

Standards: module keeps framing/filesystem durability behind one bounded journal
interface; native matching and upstream GUI unchanged. Relevant tests registered
in Meson and runtime module copied/installed beside service script. No accepted
blocking standards finding in this source packet.

Spec: actual replay and truthful source-gap recovery now exist. Full accepted
checkpoint/rollover and replacement integration are missing. New opt-in mode
explicitly refuses replacement/checkpoint exhaustion rather than imply completion.
This is an accepted remaining M4 requirement, not scope reduction. Full fsync/
publication crash matrix, compaction recovery, repeated replay/idempotence at
scale, local-filesystem power-loss qualification and aggregate acceptance remain.
No durable coverage/event-stream cursor or current-scale startup catch-up claimed.

## Next packet

Implement atomic accepted-generation checkpoint/rollover preserving immutable IDs,
sequence/highwater and byte paths, then enable replacement against the matching
cursor. The bounded journal is an interim stop point, not the intended steady
state. Integrate recovery into the actual broker service and qualify crash matrix;
retain M3 remaining root/mount/race gates and M5/M6 scope/soaks. No commit authority
inferred. Memory disposition forbidden; no personal durable-memory write.

## Checkpoint continuation 2026-10-10T16:19Z

Earlier missing-checkpoint/replacement statements above are historical. Supporting
source now implements FSCG0001 streamed private generations with sequence,
generation, retired-ID highwater and raw names. FSHM0001 bounded cached coverage
metadata accompanies each generation. Both are fsynced and read back; catalog
validation compares the persisted bytes against the captured intended digest
using64KiB scratch, avoiding a third resident catalog. Query/mutation paths still
perform no indexed-root probes. Recovery loads the private generation directly;
the original snapshot and indexed root can both be absent.

Compaction and checkpoint writes run in background. Queries and durable accepted
mutations continue during a deliberately held write. Rollover copies post-capture
records into a fsynced bounded new log/cursor before selecting one of two fixed
slots. Replacement first preserves the old private generation, validates a new
private generation, then stages a two-identity manifest before accepted service
state publication. Actual supervisor crashes immediately before/after that state
publication select the old/new complete pair respectively. Original cache removal,
raw names, retired identities, partial tails and corrupt committed replay are
exercised through actual native workers. No notification-stream durability claim.

Latest six affected Meson groups pass; receipt m4-bounded-readback-regression-pressure.json,
14.256seconds, cgroup peak78,012,416bytes/swap0. Earlier selected regression had
10/11 groups pass, including35 default-service controls; journal fixture metadata
was accidentally group-readable under systemd umask. Fixed fixture ownership
without loosening production custody,15 journal tests pass, included in latest6.
Real installed helper plus durable catalog extended owned test passes: receipt
m4-installed-helper-durable-actual-pressure-b.json,15.338seconds, reader/test
cgroup peak146,722,816bytes/swap0, normal CLI/fresh MCP and clean broker restart.
Initial actual attempt omitted NoNewPrivileges in its test unit and stopped at
containment assertion; retained unqualified receipt, corrected unit usesNNPyes.

Two full1024-record boundary capacity attempts remain unqualified: m4-two-journal-rollovers-pressure.json: deadline; m4-two-journal-rollovers-pressure-b.json: sustained_host_pressure.
No production memory/swap/visibility gate was relaxed. Execution-budget changes
for sequential fsync controls do not constitute a performance acceptance. Do not
claim two production-limit rollovers pass; inspect receipts and resume this gate.

Standards review: owning interfaces preserve GUI/default serving; private cache
I/O adds a narrow descriptor persistence seam to the catalog, documented inADR0006.
Spec review: blocking synchronous checkpoint I/O and third-catalog validation
allocation corrected and covered by held-write/recovery controls. Whole M4 is
still IN_PROGRESS supporting source, with M3 unaccepted. Full append/fsync/crash/
power-loss matrix, corrupt-pair fallback, prior-boot and dirty-startup/current-scale
visibility, durable event-cursor reconciliation and aggregate resource acceptance
remain. M5/M6 24h/72h soaks unchanged. No installed workspace runtime change.

Exact source/candidate hashes and fresh sampled-PID absence are recorded in
m4-checkpoint-closeout-identity.json. Source remains uncommitted/unpublished at
base51f6af730f8b3f8f459c721ec6b6fffa8f34d49d; worktree/build/tooling are durable
under/home/ecochran76/worktrees. No commit or broader helper-root grant inferred.
Memory disposition forbidden: personal memory writes are not authorized.

Next bounded packet: diagnose production-limit capacity control, then finish
M4 crash/corrupt-pair and startup evidence while retaining M3 mount/ignored/watch-
exhaustion/adversarial gates. Installed helper remains fixed to the owned fixture;
no full-root activation or new sudo authentication was performed in this packet.

## Published source and bounded capacity result

Authorized checkpoint2026-10-10: helper packaging7e753d5c; coupled supporting
broker/durable-catalog source8b134d7f48a374ea6675137dce5dac4c0a3eb0b1 published
on origin/feat/incremental-generations with matching remote SHA. Earlier
uncommitted/unpublished statements above are historical. Fresh verification and
fixture import repairs are described in2026-10-10-plan6-checkpoint-reconciliation.md.

The production-limit capacity control now passes: accepted sequence2052,
checkpoint sequence2048, recovered generation2, retired ID not reused, original
snapshot and indexed root removed before recovery. Receipt
checkpoint-capacity-diagnostic-pressure.json: exit0/reason null,31.062seconds (31.110-second systemd unit runtime).
The120-second diagnostic execution budget matched the registered Meson timeout;
no pressure/memory/swap/visibility gate changed. Progress timings show sequence1024
at14.022seconds and2048 at30.113seconds. Both earlier stopped attempts remain
unqualified historical evidence. They did not reproduce on this bounded run;
this result does not isolate their environmental cause or accept performance
at current workspace scale. Fresh sampled-PID absence and source/test/worker
identity are in checkpoint-capacity-closeout-identity.json.

M4 remains supporting source IN_PROGRESS with M3 unaccepted. Next bounded packet:
complete the remaining checkpoint/append/fsync/publication crash and corrupt-pair
fallback controls, then prior-boot/dirty-startup evidence; retain event-cursor
reconciliation, power-loss/current-scale and aggregate gates. M5/M6 soaks unchanged.
No installed workspace runtime or helper-root change. Memory disposition forbidden.
