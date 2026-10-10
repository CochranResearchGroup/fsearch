# Plan0006 live event eligibility versus rebuilt snapshot

State SOURCE_PARTIAL; M3/M4 IN_PROGRESS; M5/M6 PENDING.
Starting source07df1d5c, existing fixed owned root/helper only.

Frozen actual durable control: create a symlink to the owned outside-fixture,
a FIFO and a mode000 directory, separately after watching. A later same-parent
regular sentinel must become visible before testing absence, preventing early
empty-cache success. Compare each candidate with an independently refreshed
native snapshot, then require fresh MCP agree. Readable updates must continue
and coverage stay watching/pending. No file-content read or target traversal is
authorized by the symlink; no new root or mount grant.

Guard45s/unit65s,1280MiB/no swap/CPU150percent/Tasks128 and unchanged host PSI
thresholds. Native refresh10s/request3s and existing1s sentinel visibility
bound. Preserve failures; do not weaken the oracle, workload or limits.

This tests the explicit native refresh eligibility contract (regular files and
readable rooted directories, excluding links, foreign mounts, denied directory
contents and special files). Configured ignore patterns, live attribute-only
permission changes, mount effects/adversarial/current-scale/aggregate/soaks
remain separate gates. No reboot or installed workspace activation.

## Public red and repair

Actual source07df1d5c returns excluded-live-symlink through fresh MCP with
WATCHING/complete while an independently refreshed snapshot excludes it. The
regular sentinel is already visible. FIFO and denied controls were not reached
in that failed run. Preserve m3-live-exclusions-red-pressure.json, journal and
first log. Native event masks describe namespace events, not entry eligibility.

Production now requires ContainedAdmission.entry_kind before new catalog entries.
Unknown parent/generation is rejected before native access. Native S validates
the admitted parent handle before and after a no-follow/no-cross-mount rooted
metadata probe, pins/revalidates device and inode, and probes directory readability
without reading file contents. Excluded or vanished entries retire cached old
sides; inconsistent types and identities defer via a sticky gap. Queries still
use cached data without filesystem probes. Generic descriptor-only fixtures
retain optional classification and prove no production containment.

First targeted run4/5: native classification passes, but oracle prefix entry-
matched the fixture root named fsearch-entry-eligibility. Preserve the first
testlog. Change only fixture root prefix to fsearch-classification; focused
native/directory-map rerun2/2. Seven cases: regular/readable directory/unreadable
regular filename retained; symlink/FIFO/denied directory/missing entry excluded.

Actual fixed-root green with a separately hashed runtime passes all three live
controls and independent rebuilt oracle/fresh MCP agreement after sentinels.
Guarded elapsed13.978s; cgroup peak140611584 bytes, swap0. Runtime/preflight and
exact retired process identities are in m3-live-eligibility-green-preflight.json.
No installed workspace activation or new privilege/configuration. Combined
helper/kernel memory remains unqualified. Full regression and frozen churn
performance recheck remain pending.

## Regression first result

First full serial run65/66, no skips;160.104s, no pressure stop. All broker,
persistence and frontend cases pass. Monitor.test_overflow_reconciliation_is_
bounded_and_preserves_snapshot misses its unchanged5s terminal bound, the same
control previously retained in mixed-turn work. Full first testlog/receipt are
preserved. Exact case in isolation passes unchanged source/bound: one test
4.998s including setup/cleanup, guarded elapsed5.245s. This does not establish
the cause or erase the full failure. One full rerun is permitted as verification
of this unresolved intermittent result; no deadline or implementation change.

## Frozen churn recheck is red

The repaired runtime misses second-cycle512rename gate at10.017s:447renamed,
65old names; coverage pending, no fake watching. The previous committed runtime
with unchanged workload also misses first-cycle512rename at10.025s:370renamed,
142old names. This comparison does not attribute the failure to classification.
Both raw visibility payloads, query samples, timings, pressure receipts and
archived fixed-root states are retained. Combined durability-throughput gate
remains unqualified; the earlier marginal passing workload does not erase
these failures. A bounded current-source broker/service profile follows before
any performance proposal.

Standards review: production classification mandatory; optional callback only
for descriptor fixtures, no outside-handle resolution, no file content reads,
root/parent/child identity checks and strict typed reply preserved. Native
negative control also rejects a corrupt claimed parent handle with a sticky
gap and no classification export. Spec review: native refresh eligibility and
actual CLI/fresh MCP exclusion agreement pass; current churn gate is red,
attribute-only permission transitions/ignore patterns/mount/adversarial and
whole-service resource/current-scale/soak gates remain open.

Profile control also misses first512create gate:480visible at10.022s. Retain
raw pstats and readable summary. Service514append calls consume7.500s;1579
fsync calls consume7.323s of16.713s. Broker503entry classifications consume
0.203s cumulative; catalog apply waits8.113s and lookups1.474s. Idle sleep
includes startup/normal/drained intervals and does not by itself locate a bulk
backlog defect. Profile overhead makes this diagnostic, not acceptance timing.
Durable append/cursor publication is the ranked throughput bottleneck, consistent
with the prior retained fsync profile. Preserve durable-before-reply and serial
publication; no unsynced acknowledgement or larger journal/resource limit is
authorized by a performance miss.

Full recheck stopped by sustained host memory pressure after29passing groups,
96.336s; cgroup peak130387968bytes/swap0. SIGTERM in the capacity case is a
guard stop, not an adjudicated source defect. Preserve full recheck receipt
and raw testlog. First10s stability preflight fails (initial memory-full2.11);
no experiment started on that failed window. All thresholds remain fixed.

Second10s stability preflight passes. Extended actual regression correctly
excludes the symlink, revealing a stale test expectation that required its
filename to be visible. Preserve extended-first visibility failure and pressure
receipt. Update that one expectation to exclusion with a later regular marker
visibility barrier plus fresh MCP absence; retain outside-target absence and
all hard-link/subtree/restart/root-replacement assertions. This reconciles the
extended control with the independently refreshed native eligibility oracle.

Corrected extended actual regression passes17.256s, cgroup peak140951552bytes/
swap0. All original hard-link identity, subtree move-out/in, no-target traversal,
restart and root replacement controls pass with stricter symlink exclusion.
Fresh exact PID/start/boot checks show all4recordedowned identities absent;
final fixture hashes are retained. Helper/config hashes unchanged.

Next bounded packet: diagnose and repair durable throughput against the frozen
27normal/3840heavy/four-client workload. Rank per-mutation three-fsync durable
append/cursor publication first, catalog lookup/application round trips second,
classification metadata third. Any batching experiment must preserve per-entry
ordering, durable-before-success/query-publication, bounded1024record journals,
crash/replay/corrupt-pair controls and unchanged1s/10s gates. Do not silently
weaken durability, remove confinement or interpret a single marginal pass as
robust production qualification. Attribute-only eligibility, configured ignore,
mount/adversarial/exhaustion, helper/kernel aggregate, scale and soaks remain
open. M3/M4 IN_PROGRESS and M5/M6 pending.

Latest full attempt also stops on sustained host memory/I/O pressure95.753s;
cgroup peak122138624bytes/swap0. Before guard termination, capacity control
hits its unchanged3s socket receive timeout after at least640acceptedmutations.
This is retained separately from the later startup-timeout SIGTERM interruption:
34passing, one capacity failure, one interrupted case, remaining cases not run.
No clean final full-suite result is claimed. Current code matches the earlier
65/66run except later test-only corrupt-parent and extended-symlink controls;
final changed-test qualification remains required. Host pressure does not
authorize wider caps, longer request deadlines or reboot.

## Partial checkpoint validation

Fresh continuous10s healthy window immediately hands off to the unchanged
guarded runner (35s bounded observation, no experiment on an unhealthy window).
Final changed-test qualification6/6, no skips, guarded elapsed19.226s,
cgroup peak192262144bytes/swap0. Includes corrupt parent-handle
rejection, native seven-case snapshot agreement, directory admission, baseline
permissions, assembled CLI/fresh MCP, dirty-startup accepted-cache preservation
and permission-startup CLI/MCP. Final actual extended and live-exclusion controls
pass. Full suite remains unqualified due to retained monitor/capacity/pressure
results; frozen heavy churn remains red. SOURCE_PARTIAL is intentional and does
not accept M3/M4 or the full plan.

Graphiti disposition queued: durable source-backed live eligibility repair and
retained throughput diagnosis, group openclaw_ec_main. Queue receipt is preserved;
queue acceptance alone does not prove persistence or retrieval. Previous static
permission closeout reconciliation is completed_visible and copied into evidence.

Memory queue job0701f247-0d8f-4cfe-ae2e-e4d52118ca73 accepted19:16:24Z;
receipt m3-live-eligibility-memory-receipt.json. No retry or persistence claim.
Final validation sampled PIDs all absent. Historical sampled PIDs that are
present were compared with unit exit monotonic timestamps: remaining identities
started after those units exited (PID reuse); another disappeared during the
readback. No unrelated process was signalled. Fixed helper service is inactive,
MainPID0, Resultsuccess after actual controls.
