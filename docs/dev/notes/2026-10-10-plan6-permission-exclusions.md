# Plan0006 native permission exclusion consistency

State: SOURCE_PARTIAL; M3/M4 IN_PROGRESS; M5/M6 PENDING.
Starting checkpoint12f7eff69425324fdf5cc8b2b3ef112767f40636.

Frozen public native control: one owned directory mode000 containing a prepared
filename, and one readable sibling. Refresh must succeed, report exactly one
permission exclusion and return only the sibling. Broker inventory must agree,
export only the root/sibling and finish instead of admitting the excluded
directory or stopping the whole root. Real DAC/Landlock/openat2, no internal
permission override and no privileged operation.

Red: refresh/query pass, but inventory emits the denied directory then exits4
with inventory_failed. Minimal fix probes directory read eligibility before
export, skipping only EACCES/EPERM and retaining identity checks and explicit
gaps for unexpected errors. The native worker's limits, root validation, mount
and symlink constraints, capabilities and confinement are unchanged.

First bounded green: native permission control and source transport pass2/2.
The assembled frontend case was NOT selected because its explicit frontend-root
environment was absent, so it skipped; do not call that a3/3pass. Retain the
first log/receipt and run the selected full source suite.

Actual follow-up frozen before execution: same already-authorized fixed owned
root/helper. Mode000 directory exists before baseline; broker must start, keep
both excluded directory and its descendant absent through ordinary CLI/fresh
MCP and continue readable create/subtree/rename updates. Native reader/test
guard45s, unit65s,1280MiB/no swap/CPU150percent/Tasks128 and unchanged host PSI
thresholds. Prior owned state archived after PID/start/boot absence checks.

This qualifies static permission exclusion consistency only. Configured ignored
paths, live permission/type transitions, mount changes, adversarial/current-scale
and combined helper/kernel resource gates remain open. Cached filename knowledge
is not a current-permission authorization check. No reboot, new root/mount grant
or installed workspace activation.

Actual selected permission fixture passed: exit0,7.563s, cgroup
peak147591168bytes/swap0. Both excluded directory and descendant are absent
through ordinary CLI/fresh MCP, readable creates/subtrees/renames remain visible.
All sampled owned PIDs absent in fresh proc readback. Runtime/source hashes,
reversible archive, process identity absence and raw logs retained separately.

Graphiti prior mixed-churn job reconciled completed_visible; no retry. Focused
discovery returned historical checkpoint facts rather than permission evidence;
current public native red/green is authoritative. This source-backed outcome
will receive one queued singleton closeout after final regression.

Matt review against12f7eff6: Standards no bounded blockers; native descriptors
close on every path and the probe does not introduce file-content access. Spec
no static-exclusion blockers: inventory/refresh agree, child replacement causes
a gap, and denied entries are skipped before any handle is exported. Existing
framing duplication remains nonblocking backlog. Live newly-created excluded
types/permissions are separate open ingestion gates, not implied by this static
bootstrap result. Next: public actual symlink/FIFO/live-permission eligibility
comparison with a rebuilt snapshot. Mount effects still require separate
authority; full M3/M4/aggregate/soak acceptance remains open.

Final65-case serial regression passes after the documented stable-preflight rerun.

First full65-case run interrupted after30passing groups by sustained host memory
pressure (guard reason sustained_host_pressure,108.665s, owned cgroup
peak134172672bytes/swap0). The next crash case received the guard SIGTERM;
this is not a crash-test source failure. All sampled owned PIDs absent, unit
terminal/MainPID0. Retain the failed pressure receipt/raw log. A single bounded
rerun is allowed only after a fresh stable preflight; no pressure threshold or
individual test deadline change.

The first ten-second rerun stability check failed (memory full avg10 rose to
5.99); no experiment was launched from it. A second fresh ten-second check
passed with all frozen thresholds met. The single full rerun uses the original
235s guard; the interrupted65-case attempt used250s, but was pressure-stopped
at108.665s rather than a duration limit. Individual test/acceptance deadlines,
resource caps and pressure thresholds remain unchanged.

Prepared --actual-exclusions selects a separate actual durable test for live
symlink/FIFO/mode000 directory events. A later regular sentinel must be visible
before checking exclusion; each candidate is compared with a rebuilt native
snapshot. This prepared fixture has not yet qualified those semantics. It is
not registered as an automatic privileged test and grants no additional root
or setup authority.

Final rerun:65/65pass, exit0,148.591s, cgroup
peak226525184bytes/swap0. No skipped case; both new permission
controls selected. All sampled owned PIDs absent in fresh proc readback.
Static permission exclusion source qualification is complete; wider M3/M4
and live eligibility gates remain open. No pressure/acceptance target rebaseline.
Graphiti disposition queued with this canonical source artifact as provenance;
queue acceptance is not terminal persistence or retrieval proof.
