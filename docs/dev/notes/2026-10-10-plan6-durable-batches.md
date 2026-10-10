# Plan0006 bounded durable batch throughput

State SOURCE_PACKET_QUALIFIED; M3/M4 IN_PROGRESS, M5/M6 pending.
Starting checkpoint9f0271d9. Full objective and frozen limits unchanged.

Public red from prior packet: repaired and previous committed actual runtimes
miss10s heavy rename gates. Profile ranks per-entry journal/cursor three-fsync
publication (1579fsync/7.323s) over eligibility (503calls/0.203s).

Frozen hypothesis: bounded8entry group commit preserves ordered native
application and existing FSCJ cursor format while amortizing durable publication.
A batch is admitted only if all records fit the existing1024record/16MiB limits,
with contiguous sequences and exact accepted identity. Queries and replacement
promotion cannot observe partially applied/uncommitted entries. A native failure
reaps/discards that worker and recovers the old committed prefix. Log/cursor
crash controls retain old prefix for unpublished cursor, complete batch for
published cursor, no acknowledgement before publication. No filesystem power-loss
claim. Batch is bounded durable publication, not a new transaction abstraction.

Broker batches only independent regular CREATE/RENAME events without shared
namespace sides; parent/entry containment and eligibility remain mandatory.
Directories, exclusions, dependent events and non-durable fixtures keep single
application. Source applied sequence advances only after durable success; only
subsequent EAGAIN establishes watching. Cooperative50ms turn and pending/byte
bounds remain. No new root/mount/helper/configuration/installation/reboot.

Freeze public protocol/codec and actual supervisor crash controls before native
implementation. Keep raw red/green, three cursor cuts, publication pause/query
barrier, failed-native-prefix and malformed/oversized/sequence/identity controls.
Actual final workload remains27normal +3840heavy, four clients, three production
rollovers,768independent oracle paths,1s/10s visibility. Guard180s/unit200s,
1280MiB/no swap/CPU150percent/Tasks128; unchanged host pressure stops. Whole-service
aggregate/current-scale/soak gates remain open.

Public baseline red returns invalid_request for an8entry batch. First harness
run incorrectly installed a missing append_batch hook even in normal mode;
its startup failure is retained separately. The public red uses no hook.
First repaired protocol run4oldcontrols pass, batch acknowledgement/recovery
reaches sequence9, but normal oracle query also matched the fixture root named
fsearch-batch-crash. Change only its prefix to fsearch-group-crash. The run
also stops on host pressure before remaining batch cuts; raw testlog and
pressure receipt retained. No matcher or crash expectation was weakened.

Corrected first protocol recheck9/9 passes, retaining all three old single-entry
crash controls. Extended controls initially5/8: normal/pause accidentally sent
the same batch twice (second rejected journal_sequence); capacity re-entry
accidentally attempted a duplicate CREATE name (native error). Retain raw
controls-first log. Remove only duplicate send and choose a distinct post-rollover
name. All7publicbatch controls then pass; new source-reader failure test expected
retained pending entries despite existing sticky-gap discard. Preserve7/8log,
change only that expectation to discard while asserting applied sequence stays0.
Source-reader17/17 passes, including batch yield/order and subsequent-drain rule.

Public controls now establish: durable sequence9 and8stable distinct IDs, raw
bytes preserved across recovery with root/original snapshot absent; unpublished
cursor old prefix1 read-only, published cursor complete prefix9; pause before
cursor publication blocks mutation reply and query; native failure after first
apply discards partial native view and recovers prefix1; invalid empty/oversized/
noncontiguous/bool/identity batches rejected before effects; exact production
1024record capacity enforced and explicit rollover permits the next batch.
No format change, resource increase or unsynced acknowledgement.

Initial frozen actual workload passes: normalmax0.071737s, heavymax5.271394s,
1215queries/errors0,768oracle paths, checkpoint3072. Guard42.215s, cgroup
peak163323904bytes/swap0. Full first73/73 passes with no skips; raw log/receipt
retained. These qualify the initial batch implementation, not the later repair.

Review identified that an early deferred native response could be hidden by
a clean last response. Public injected native_deferred control is red: first
response carries a gap yet whole batch returns durable sequence9 with no gap.
Before any batch journal publication, reject/reap a native response with a
deferred reason or wrong snapshot binding, preserving the old accepted prefix.
Add both public deferred and identity controls; requalify final source.

Final gap/identity repair10/10targeted controls passes. A deferred response or
wrong accepted-snapshot binding before group publication now aborts/reaps the
uncommitted native prefix. Fresh recovery returns prior sequence1 with no batch
entries, original indexed root and baseline snapshot absent. Native errors and
all earlier crash/capacity/acknowledgement controls remain green.
Previous live-eligibility Graphiti receipt reconciles completed_visible, episode
a6373a48-d587-4084-9922-a3098e6fcb4a; receipt copied into repo evidence.

Final frozen actual confirmation passes:27normal/3840heavy, normalmax0.169204s,
heavymax4.684217s,1155queries/errors0,768independent oracle paths and checkpoint
3072. Guard40.198s, cgroup peak158289920bytes/swap0. Source/runtime hashes and
retired process identities are preserved separately from initial timing run.
This is bounded owned-root performance, not current-scale/aggregate acceptance.

Standards review against9f0271d9: at most8prepared mutations and8native replies,
unchanged64KiB request/1MiB response/queue/ownership/resource bounds, native
mutations ordered under one active client, parent/entry metadata classification
retained, no root probes in query dispatch, no new persistence format. Existing
public socket/test framing duplication remains nonblocking backlog.
Spec review: durable-before-success/query-publication, exact journal capacity,
cursor crash prefixes, raw-byte name/entry identity recovery, failed/deferred/
wrong-identity native prefix discard and subsequent source-drain requirement
all pass current controls. Directory/dependent/excluded/non-durable events keep
the existing single path. M3/M4 acceptance, helper/kernel aggregate, ignored/
attribute-only/mount/adversarial/exhaustion/current-scale/soak/install gates
remain open. No thresholds, privilege, roots or durability were weakened.

Final qualification:75/75 full groups pass, no skips, guard151.901s,
cgroup peak196374528bytes/swap0. Actual final exclusion control passes in8.924s,
peak139919360bytes/swap0; extended actual control passes in13.151s,
peak139567104bytes/swap0. Extended controls cover listener handoff/startup,
directory inventory/ancestor rename, root replacement, delete/recreate/hardlink
stable distinct IDs, subtree move-out/in, symlink exclusion without traversal,
and clean restart/rebuild. Adversarial confinement still requires separate proof.
Raw final logs/pressure/runtime identities are under plan6-evidence with prefix
m4-durable-batch-. Earlier failed runs remain preserved.

Cleanup: final exclusion five and final extended four exact recorded
PID/start/boot identities are absent; fixture outputs archived without deletion.
Final extended unit and fixed setup helper are inactive, MainPID0, success.
Helper SHA8f049df68f682ac4a2513761e33f4e5fb4068e4c1658304ffb6ec222802de1ea;
root configuration SHA1cb6ce8b272b3153d4a8cd0449cf9ac8b41d9bcbce8e53588e67b8af5e329566.
No installed activation or reboot. These cgroup peaks exclude the separate
setup helper/kernel and do not establish aggregate600MiB acceptance.

Memory disposition: queued in openclaw_ec_main through graphiti-runtime remember.
Job6c58dc9f-ef00-44ce-8f91-b84b279fda67 accepted2026-10-10T19:46:36Z;
receipt m4-durable-batch-memory-receipt.json. Queue acceptance is not persistence
or retrieval proof; reconcile this receipt before any related retry. The supplied
reference time19:48Z was rounded ahead of actual acceptance; recorded_at/queued_at
remain the authoritative receipt timestamps.
