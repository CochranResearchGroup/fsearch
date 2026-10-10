# Plan0006 actual sustained mixed churn qualification

Frozen before execution at sourcec29f8ae0. Existing authorized fixed owned
fanotify root/helper and staged runtime; no new mount/root/privilege/activation.
One guarded actual durable fixture:27normal mutations (9create/rename/delete
cycles), then3heavy cycles each512create,512rename,256delete. Four concurrent
native CLI clients query an unchanged sibling through the public bounded queue.
Every normal mutation must reach query visibility within1s; every complete
heavy phase within10s from BEFORE its first mutation. Fresh MCP verifies each
cycle's final surviving name. Independently refreshed native snapshot must
match the full final768path result set. Production journal checkpoint must
reach sequence3072 or later without lowering its1024record limit.

Frozen limits:180s pressure deadline,200s unit bound,1280MiB cgroup/no swap,
CPU150percent,Tasks128,unchanged host PSI/8GiB preflight. Refresh oracle10s,
public native request3s,client cleanup4s. Preserve failed receipts and workload;
no threshold rebaseline or hidden retry. These are owned small-root gates,
not whole-workspace/current-scale/aggregate/soak acceptance.

## Diagnosis and retained outcomes

Initial public actual run missed the first512create burst gate (409visible
paths at the last10s query); coverage expired during bulk work. Broker's later
catalog_apply_failed occurs during fixture cleanup and is not independently
adjudicated as the root cause. Native broker profile retained:18.8s in catalog
requests and5.5s in fixed sleeps over25.4s. Avoiding50ms sleeps after undrained
turns alone allowed the first cycle but failed the second create burst (499/512
at10.018s). Preserve all failures, profiles, pressure receipts and archived
fixture states; do not report the partial cycle as workload acceptance.

A separate public ordinary-descriptor red showed one slow-consumer call applied
all3queued events despite its turn time budget. Fix yields between pending
applications, retaining only the existing bounded admitted export queue. Real
application progress renews liveness while state remains pending. Only EAGAIN
after pending work is complete can restore watching. This is a cooperative
bound: individual admission/application callbacks retain their own deadlines.
The default source-reader tests14/14 pass, including exact sequential delivery
across yields, sticky errors and absence of false drain. No raw batch retention,
pending/byte cap expansion, deadline change or weaker durability was introduced.

With both fixes the profiled service run passed all3cycles:27normal +3840heavy
mutations,768rebuilt-oracle matches, checkpoint3072 and2544queries with no
errors. Heavy maximum9.905s. Service profile identifies11698fsync calls consuming
50.27s of79.57s; durable append dominates. Do not infer whole-workspace or robust
long-soak headroom from this marginal small-root result.

Unprofiled confirmation also requires complete/untruncated native responses and
watching/pending coverage on every concurrent query. It passed: normal maximum
0.078939s, heavy maximum9.339470s,2344query samples/errors0, all768oracle paths
equal, checkpoint3072. Reader/test cgroup peak149327872bytes/swap0; all sampled
owned PIDs absent in fresh proc readback. Helper/kernel combined aggregate
remains unqualified. Runtime hashes are in m3-bounded-turn-identity.json; final
source differs from that staged broker-source file only in a clarifying docstring.
The confirmation fixture source and hashes are retained separately. Installed
helper configuration and root admission unchanged. No reboot or installation.

Matt review against c29f8ae0: Standards no bounded blockers; existing public
socket framing/test harness duplication remains nonblocking backlog. Spec no
bounded blockers: sequential bounded carryover, no sleep while backlog remains,
truthful pending coverage and unchanged1024record durable rollover. Aggregate,
current-scale, ignored/mount/watch-exhaustion/adversarial and full M4 crash/cursor
gates remain open; M5/M6 soak/install acceptance remains pending.

Full serial source regression and final-source actual regression pass; see final validation below.
Graphiti bootstrap-publication receipt reconciled completed_visible/no retry.
This durable diagnosis and source fix receive a qualified queued singleton
closeout with this note as provenance; queue acceptance alone is not persistence.

## Qualified baseline cut correction

Review found that finish_baseline left a qualified session reconciling until
the first drain. A public descriptor arriving after that cut incorrectly raised
bootstrap_dirty. Retained qualified red establishes this rejection; it does NOT
establish silent loss. Fix marks a qualified baseline pending immediately,
so later events are admitted replay. Legacy unqualified startup still rejects
dirty inventory, and watching still requires a later drain. The initial broader
receive-condition edit violated the legacy dirty-inventory control; its failure
is retained and that edit was replaced with this qualified-state transition.
One prior test's reconciling expectation changed to pending after qualification,
retaining its pre-cut reconciling and post-drain watching assertions.

Public source-reader15/15 and event-filter24/24 controls pass. The first full
regression before this additional repair passed63/63; it cannot qualify the
subsequent change. Final full regression and current staged actual regression
pass; see final validation below. Actual mixed timing runs above qualified the bounded-turn changes;
they do not independently establish a real-kernel event exactly inside this cut.

## Final validation

Final63/63 serial source regression passed, exit0,154.532s, cgroup
peak201457664bytes/swap0. Final current-source staged actual extended regression
passed, exit0,14.476s, cgroup peak139476992bytes,
swap0. Public CLI/fresh MCP, distinct stable hard-link IDs,
subtree/symlink boundaries, clean restart and root replacement pass. All sampled
owned PIDs absent. Helper SHA8f049df68f682ac4a2513761e33f4e5fb4068e4c1658304ffb6ec222802de1ea
and configuration SHA1cb6ce8b272b3153d4a8cd0449cf9ac8b41d9bcbce8e53588e67b8af5e329566
are unchanged; setup service is inactive/MainPID0 after invocation.

Final Standards/Spec review includes the qualified-cut repair. No bounded
blockers remain; preserve the nonblocking framing backlog and all wider open
gates. Next: ignored/permission exclusion consistency through actual owned
fixtures; mount effects still need separate authority. Full M1–M6 objective and
600MiB/1.25GiB resource targets remain unchanged.
