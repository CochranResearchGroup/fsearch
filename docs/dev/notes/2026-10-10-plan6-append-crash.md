# Plan0006 append publication process-crash qualification

State: SOURCE_PARTIAL; M3/M4 remain IN_PROGRESS; M5/M6 pending.
Worktree: fsearch-incremental-generations; starting source10220f6b.

Public seam: actual supervisor/native worker catalog_apply, catalog_status,
query, catalog_lookup and explicit recovery CLI, with private owned fixtures.
Fault injection terminates the supervisor at one durability boundary at a time.
No production implementation change was required; existing behavior passed.

- After journal fsync, before cursor publication: recover acknowledged sequence1;
  sequence2 is absent and uncommitted-tail state refuses subsequent mutations.
- After cursor-file fsync, before cursor rename: same sequence1 read-only outcome.
- After cursor rename and directory fsync, before acknowledgement: sequence2 is
  recovered from the published durable cursor despite the lost acknowledgement.

Each cut starts from an accepted private sequence1 checkpoint, removes the root
and original snapshot before recovery, and preserves acknowledged raw path bytes,
entry ID and snapshot identity. The crashed worker is reaped before recovery.
These tests qualify process-crash ordering only, not local-filesystem power loss.
They do not authorize a reboot, installed activation or additional roots.

Validation: registered Meson3/3 pass, zero skips/failures; exact commands and
resource receipts in plan6-evidence/m4-append-*-pressure.json and
m4-cursor-*-pressure.json; retained raw log m4-append-three-testlog.txt.
Fresh /proc readback proves all sampled owned PIDs absent; hashes are retained
in m4-append-crash-identity.json. The prior47-group full regression remains its
own earlier result; this packet adds three tests, not a claim of a full50 rerun.

Matt review: Standards and Spec separately examined at the public seam.
No blocking packet findings. Injected durability hooks are test-only; behavior
assertions use the actual protocol. No fabricated red/fix cycle for behavior
already implemented. Full crash/checkpoint/compaction matrix, startup proof,
M3 current-scale freshness, aggregate resource acceptance and soaks remain open.
Next packet: interrupted checkpoint publication and compaction recovery.

Graphiti: prior corrupt-pair closeout reconciled completed_visible; retained
m4-corrupt-pair-reconciliation-visible.json. Append-crash closeout is separately
qualified for queued memory, linked to this artifact and its exact receipts.
