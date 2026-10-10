# Plan0006 broker candidate: accepted transition and bounded startup

State: SOURCE_PREPARED_FOR_ACTUAL_QUALIFICATION; M3–M6 remain open.
Owner: Codex; operator: ecochran76; tracker: fsearch issue26/M3 issue29.
Worktree: `/home/ecochran76/worktrees/fsearch-incremental-generations`.
Branch: `feat/incremental-generations`; base51f6af730f8b3f8f459c721ec6b6fffa8f34d49d.
Publication: uncommitted/unpublished. No privileged setup or installed change.

## Operator decision and unchanged destination

The operator rejected Linux kernel development and accepted the reproduced
move-after-admission case as a bounded transition: its descriptor/object was
inside the approved root initially. ADR0005 and the delivery specification now
record that decision. Preserve the original strict-criterion failure; do not
claim the read never occurred. The exception permits no initially outside
admission, outside destination following, outside-name export/logging or file
content read. Validate around each operation, discard affected output and stop
with a truthful gap. No custom kernel/VM work will proceed.

The600MiB steady/1.25GiB update targets, no swap, exact root scope, query and
freshness gates, durability,24-hour synthetic and72-hour installed soaks remain.
The execution window still starts2026-10-10T02:33:29Z; checkpoint by05:28:29Z
and stop before05:33:29Z or two million tokens. Resume did not reset it.

## Implemented and verified

The obsolete `broker_confinement_unqualified` refusal was removed. Production
requires a root-authenticated named setup endpoint before any catalog/root
state; inherited socketpairs are fixture-only. Negative production tests prove
no state creation for inherited input, missing endpoint or a user-created
listener. A valid root source still requires the fixed administrator config,
matching root identity/session and an actual nonblocking fanotify descriptor.
Changing this source gate did not run setup or create any group/mark.

The actual unchanged inventory helper was tested in two owned cases:

- Move after validated admission: exactly one bounded32KiB-capacity directory
  read; post-check gap/exit4; no outside-name export or secondary child probe.
  This passes the new contract and still fails the preserved original criterion.
- Move before requested admission: gap/exit4; zero outside directory reads or
  secondary probes. This is not covered by the accepted exception.

The prior bootstrap rejected every namespace batch, including the candidate's
own private-state writes and unrelated filesystem churn. It now keeps a fixed
1MiB keyed bitmap of changed parent/directory-target identities until inventory
exists. No outside names, handle list, replay records or bitmap persist. After
inventory, check every admitted identity; newly arriving records are also
checked against the completed map while validation runs. In-root changes
reject the baseline; outside changes can be discarded. Hash collisions cause
explicit rejection, not false freshness. At most1,000,000 observations are
admitted, and the existing startup deadline remains enforced. The bitmap is
released at the first qualified drain or failure. This remains a clean-root
bootstrap, not a qualified catch-up/replay strategy under in-root startup churn.

Focused cases prove delayed identity admission, a change arriving after its
parent was scanned, root movement with outside parents, unqualified completion,
bitmap saturation, observation exhaustion and outside-churn startup. The
assembled normal CLI/fresh MCP fixture queues outside events during bootstrap
and asserts no corresponding search result. Existing creates, populated subtree,
ancestor rename, overflow/deferred coverage, restart-after-reap and root
replacement still pass. The actual setup accept function and credential
negative controls pass. Setup flags now use `FAN_REPORT_DFID_NAME_TARGET`, which
includes the required `FAN_REPORT_FID`; the earlier incomplete flag combination
was corrected before any privileged execution.

Final focused evidence: `plan6-evidence/m3-candidate-20261010T0310-output.txt`
and matching pressure receipt. Strict-warning C builds, listener fixture,
21parser/bootstrap cases,13source transport cases,5map cases, both ancestry
controls and assembled CLI/fresh MCP pass. Exit0,8.671seconds; in-run cgroup
peak179,286,016bytes, swap peak0; sampled descendant RSS215,289,856bytes.
These are small owned-fixture measurements, not current-scale acceptance.
Boundary workers74497/75543 were absent in fresh OS readback. Later source edits
only add capability assertions in the gated actual-mode test; that branch is
unexecuted and remains part of the privileged qualification obligation.

Candidate runtime is durable at `/home/ecochran76/worktrees/fsearch-broker-candidate/bin`.
Source, binary, test and unit hashes are in `plan6-activation/candidate-identity.json`.
Prepared actual fixture: `/home/ecochran76/worktrees/fsr-q-20261010/owned`,
initially empty, owned byUID1000, with an explicit owned-fixture manifest.
Production dataset/root and installed runtime were not scanned or replaced.

## Concrete next effect gate

The reviewed coordinator is `plan6-activation/activate_owned.py`. It requires
root and refuses unprivileged invocation without effects. It checks exact staged
hashes and refuses existing config/runtime/units/endpoint. It copies immutable
candidate artifacts to `/run/fsearch-plan6-qualification`, creates only temporary
system units and the fixed `/etc/fsearch/broker-root.conf`, then removes them
on rollback. There is no enablement, file capability or installed runtime replacement.
Stage-only unit verification passed using the owned runtime prefix; original
warning/missing-future-runtime failure is separately retained. Root unit loading
and actual-mode test execution have not occurred.

Request exactly one actual owned-fixture job, up to3minutes including provisioning
and rollback. A root-created SOCK_SEQPACKET listener is at `/run/fsearch/broker.sock`;
only its setup service runs asUID1000 withCAP_SYS_ADMIN, no DAC/search capabilities,
for at most5seconds. It makes one notification-only filesystem mark, transfers
the descriptor and exits. The reader/test run asUID1000 with no capabilities and
NoNewPrivileges; actual-mode tests verify reader/worker credentials. No privileged
automatic retry: one setup launch, StartLimitBurst1, Restart=no.

**Observation is filesystem-wide on `/dev/sdd`, ext4 mounted at `/`, including
outside the workspace.** This is not merely an owned-tree mark. Only the owned
fixture is admitted/indexed. Outside queue data is parsed transiently and dropped;
no outside paths are resolved, exported, logged or persisted. No Windows, Drive,
network or other filesystem mark. No permission events, unlimited queue, file
contents, arbitrary open-by-handle or kernel change.

The check has a45-second pressure-guard deadline, a50-second service timeout and
5-second stop budget. Both services share a root-managed slice capped at1280MiB,
zero swap, CPU150% and IOWeight10. The unprivileged runner preserves unchanged
host-pressure gates; the coordinator reads the common slice's memory/swap peak
to include setup/queue charges. Existing system-manager administrative overhead
is outside that slice; this fixture is not M5 resource acceptance.

Actual-mode controls: real create/search visibility through native CLI, normal
frontend CLI and fresh MCP; populated directory admission; ancestor rename;
owned outside churn/no results; root replacement/degraded coverage; privilege
absence and owned process reap. No synthetic event is sent in actual mode.
Kernel overflow and actual source restart are not claimed by this first job;
synthetic controls remain distinct. Failed delivery/feature/containment/resource
gates stop the run and retain receipts; no cap increase or automatic rerun.

Rollback stops the test/socket/setup/slice, closes the last source descriptor
and mark, removes only newly created config/unit/runtime files and records
unit/PID states. Preserve owned fixture and raw failure evidence. Fresh OS and
installed-service readback are still required after execution; unproved cleanup
blocks any subsequent launch. The earlier workspace snapshot service is never
stopped, reconfigured or replaced by this packet.

Approval is required by ADR0005's explicit withholding of capabilities,
filesystem-wide observation, sudo and privileged fixtures. The metadata
transition decision does not authorize those effects. No automatic approval
review rejection has occurred. Prepare the packet first, then ask once for this
exact job; do not seek installation or real-workspace activation in that request.

## Remaining program and custody

M1/M2 remain source accepted. M3 actual delivery, broader event/race qualification,
startup under the frozen workload and combined resource/freshness proof remain.
M4 checkpoint/replay, M5 current-scale acceptance/24-hour synthetic soak and M6
publication/reversible installed acceptance/72-hour soak remain open. No issue
closure, commit, push or acceptance is inferred from this candidate.

Fresh installed readback: servicePID94383, NRestarts0, runtime
e0ec8e758db755dbd3cf8b3a83c9e4a467c50137. No privileged broker is installed.
Memory disposition: forbidden; the source/activation preparation scope does not
authorize personal durable memory writes. Preserve the non-write receipt.

## Repository-owned helper preparation, 2026-10-10

Operator approved the bounded actual test, but `sudo -n` refused because a
password is required; no privileged effects occurred. Operator then requested a
repo-owned helper before authenticating sudo. `packaging/broker/manage.py` now
stages/installs/removes the existing setup binary with root-owned SHA256-versioned
custody, fixed UID/root config, socket-activated CAP_SYS_ADMIN-only setup and
bounded restart attempts. `packaging/broker/README.md` contains the new install
and rollback commands. The old temporary coordinator is not compatible with an
installed fixed config/socket and must not be run after this installation.

Prepared bundle: `/home/ecochran76/worktrees/fsearch-broker-helper-bundle`,
helper version51cf1cae5f2d3208f6591b410b0bd0ebcdddca0cf2d0a5bde5bc07c67bbdad72,
UID/GID1000, existing owned fixture only. One administrator installation can start
the socket; later unprivileged readers receive new event descriptors without
sudo prompts. No actual install/enable/mark occurred during preparation.
Five owned lifecycle/negative controls pass; shadow unit verification passes.
Actual source qualification remains open, as do M3–M6. The bundle and new package
sources are uncommitted/unpublished. Memory disposition remains forbidden.

### Installed helper and first bounded launch, 2026-10-10

Operator authenticated and installed the repository-owned helper with `--listen`.
Fresh readback: four installed payload hashes match the bundle, ownerUID0 and no
group/world write; system socket active, setup service inactive/MainPID0. Version
51cf1cae5f2d3208f6591b410b0bd0ebcdddca0cf2d0a5bde5bc07c67bbdad72, config still
UID1000/owned fixture only. Receipt's `activation: disabled` describes staged
metadata and is stale after `--listen`; authoritative socket readback is active.

Attempted one unprivileged actual-mode test using the installed socket in user
unit `fsearch-actual-owned-20261010`, NoNewPrivileges, MemoryMax1280MiB/Swap0,
CPU150%, IOWeight10 and45-second pressure guard. Receipt
`plan6-evidence/m3-installed-helper-actual-pressure.json` reports
`host_pressure_preflight`: memory full avg10=2.15 exceeded2; MemAvailable
41,836,167,168bytes. The guard did not launch a test process (exit_code null,
zero samples). Consequently no helper setup, fanotify mark or reader started;
actual event delivery remains unqualified. No automatic retry or cap relaxation.
Fresh OS readback found no broker reader/boundary/test/setup processes; installed
snapshot service remains active/MainPID94383/NRestarts0. Persistent helper socket
is deliberately retained as requested; temporary-activation rollback is no
longer the installation lifecycle. Memory disposition: forbidden, unchanged.

### Helper review remediation

The narrow two-axis review and closed-world fix are recorded in
`2026-10-10-plan6-helper-review.md`. Installer partial-write rollback and inherited
umask defects are fixed; new receipts distinguish socket activation requests from
command results. Eleven focused owned/mocked lifecycle controls pass. Installed
helper binary/config/units are unchanged and still hash-match; no privileged
operation or reauthentication was required. Actual-source qualification remains
pending after the preserved pressure-preflight stop; M3–M6 remain open.

### New execution window and actual handoff failure

New operator goal window starts2026-10-10T14:26:26Z; checkpoint by16:21:26Z,
hard stop16:26:26Z or one million tokens, whichever earlier. Earlier three-hour
windows are historical and not carried into this explicitly replaced goal.

Host pressure qualified on fresh readback. Actual-mode run in guarded unit
`fsearch-actual-owned-20261010b` failed0.785seconds after launch with handoff_invalid.
Setup journal reports broker_setup_rejected; root service failed/exit1/MainPID0.
Pressure receipt `m3-installed-helper-actual-pressure-b.json` and diagnostic receipt
`m3-installed-helper-handoff-failure.json` retain failure. Fresh OS readback finds
no broker reader/boundary/setup processes. Owned generated fixture data is retained;
do not reset it blindly or rerun the original empty-fixture command.

Ask Matt route: diagnosing-bugs. Generic installed-helper rejection prevents a
trustworthy distinction between listener, config/root and kernel-source failure.
Source diagnostic adds numeric stage/errno only; no filenames, opaque handles,
tokens, outside metadata or capability expansion. Strict C build and actual
listener negative/credential controls pass. Diagnostic bundle prepared at
`/home/ecochran76/worktrees/fsearch-broker-helper-diagnostic-bundle`, version
4d394a997e36a5e809beb36b93327d28cce092b1cce6b184b75f56cde1946f6c. Not installed.
Stages:1invocation/capability,2config-directory,3config-file,4config-parser,
5listener,6request,7root-open,8root-attestation,9fanotify-init,10mark,11handoff-send.
This is diagnostic preparation, not a claimed root cause or fix. Installed
helper stays old version; administrator maintenance is needed to replace its
root-owned executable. The original candidate identity manifest refers to the
pre-diagnostic source; preserve it as historical rather than claim source matches.
Memory disposition forbidden; no personal durable-memory write authorized.

### Minimal diagnostic handoff probe

Diagnostic helper installation remains pending: fresh root receipt still reports
version51cf1cae..., setup failed/MainPID0. New
`src/tests/probe_broker_handoff.py` reduces the next experiment to the fixed
owned-root descriptor handoff, with no inventory, snapshot, frontend, mutations
or event reads. It validates installed hashes/admission, requires an explicit
expected version, sets NoNewPrivileges and refuses capabilities. Default inspect
mode never connects. --execute refuses before connection if diagnostic version
is not installed; both inspection and that refusal were exercised. No new source
or mark was created. Once authenticated helper maintenance completes, run this
probe under the unchanged pressure guard/cgroup before retrying assembled tests.
It will close a successfully transferred descriptor immediately. Rejection plus
numbered helper journal stage supplies the missing evidence; probe success alone
would establish handoff, not actual delivery/freshness or M3 acceptance.

### Confirmed mark descriptor defect and source fix

Operator installed diagnostic version4d394a99.... Guarded minimal probe reproduces
handoff_invalid; helper journal stage10/errno9 identifies fanotify_mark EBADF.
Receipt `m3-diagnostic-handoff-pressure.json` preserves the attempt. Setup exited;
fresh MainPID0 and snapshot MainPID94383/NRestarts0. Linux6.6 primary source
https://raw.githubusercontent.com/torvalds/linux/v6.6/fs/notify/fanotify/fanotify_user.c
fanotify_find_path uses fdget for NULL pathname, rejecting O_PATH descriptors.

`test_broker_mark_descriptor.c` reproduces EBADF with the actual helper root-open
function and an unprivileged owned-directory inode mark. Red before fix, green
after read-only directory pin replaces O_PATH; negative O_PATH control still
returns EBADF. No filesystem mark or capability grant in regression. Registered
in Meson; unavailable unprivileged FID fanotify is explicit skip77, not acceptance.
Root identity attestation, no symlinks, fixed config/capability/scope retained;
setup neither enumerates the read-only directory nor reads file contents.
Strict C builds, descriptor regression and listener controls pass.

Fixed helper bundle `/home/ecochran76/worktrees/fsearch-broker-helper-fixed-bundle`,
version8f049df68f682ac4a2513761e33f4e5fb4068e4c1658304ffb6ec222802de1ea,
prepared but NOT installed. Installed actual-source retest remains necessary;
owned inode mark does not prove filesystem delivery or M3. Administrator helper
maintenance required; ordinary reader restarts still require no sudo. Preserve
old diagnostic receipt and earlier failed actual receipts. Memory forbidden.

### Actual owned delivery passes after kernel coalescing repair

Operator installed fixed helper8f049df.... Minimal guarded handoff succeeds and
closes transferred source without event reads; `m3-fixed-handoff-pressure.json`.
First full owned attempt then truthfully stopped with ambiguous_operation:
`m3-fixed-actual-pressure.json`, generated state preserved under
`failed-coalescing-archive`. Real owned inode-mark experiment produced merged
CREATE|DELETE mask0x300 and reproduced the parser failure. New synthetic controls
failed before fix. Decoder now preserves merged-mask structure; outside admission
is discarded, admitted ambiguity remains sticky gap, and bootstrap dirty sketch
continues to reject changed admitted parents. No ambiguous operations are applied
as though their order were known. Overflow and malformed ABI still invalidate.

Real-kernel owned coalescing regression,24parser/bootstrap,13transport and5map
controls pass. `test_fanotify_coalescing.py` registered in Meson; unsupported
unprivileged FID fanotify is explicit skip77. Reader module staged without sudo.
Full actual test then PASS: root-authenticated named handoff, outside bootstrap
churn, startup, create visibility via native CLI/normal frontend CLI/fresh MCP,
populated-directory inventory, ancestor rename, root replacement/degraded
coverage/no replacement-name results and boundary worker46677 reap. No injected
synthetic records in actual mode. Pressure receipt `m3-coalescing-actual-pressure.json`:
exit0,6.0615seconds, in-run reader/test cgroup memory.peak148,406,272bytes, swap0,
sampled descendants202,625,024bytes. Root setup sibling cap64MiB is separate;
these measurements are NOT combined M5 resource acceptance. Post-exit systemd
summary512KiB is not the in-run peak. Exact source/runtime/helper/frontend hashes
in `m3-coalescing-actual-identity.json`; original candidate identity remains
historical. Fresh setup inactive/MainPID0/success; fresh OS no reader/boundary/test
processes, worker46677 absent. Snapshot service unchanged/MainPID94383/NRestarts0.

M3 remains open: actual restart/overflow, full namespace/race matrix, real-root
startup/freshness/resource proof remain. M4–M6 and both soaks remain open. No
commit/push/integration inferred. Next bounded packet: broaden owned actual
namespace and restart controls, retaining this passing sample independently.
Memory disposition forbidden. Goal tool still returns historical blocked status;
operator authentication removed that blocker and work proceeded under direction.

### Extended actual namespace/restart and kernel overflow qualification

Under existing fixed owned-root helper8f049df..., gated --extended-actual passes:
delete/recreate, same-inode hardlink entries, subtree move-out revocation, outside
child churn/no outside results, populated move-in inventory, symlink entry/no
target traversal and graceful reader restart after proven cleanup. Offline
created file becomes visible through native CLI/fresh MCP after clean rebuild.
This is not M4 checkpoint/replay. Root replacement/deferred coverage still passes.
Receipt `m3-extended-actual-pressure.json`:14.893seconds, reader/test cgroup
peak145,457,152bytes/swap0, sampled descendants202,129,408bytes. Identity receipt
`m3-extended-actual-identity.json`, workers80234/81301 absent. Prior basic-pass
fixture/logs preserved under passed-basic-archive; extended state preserved under
passed-extended-archive. Configured root path unchanged; no files destroyed.

Separate gated --actual-overflow pauses the reader group, creates17,000 owned
outside-root entries against verified kernel queue limit16,384, resumes, and
asserts real queue_overflow + reader exit + fresh MCP deferred coverage retaining
accepted results. Outside-burst names are never returned. PASS; receipt
`m3-overflow-actual-pressure-b.json`:8.6456seconds, reader/test cgroup
peak162,594,816bytes/swap0, sampled descendants178,745,344bytes. Identity receipt
`m3-overflow-actual-identity.json`; worker95700 absent. The initial overflow launch
ran preparation from the wrong cwd and argparse refused unknown flag before any
connection/mutation; its failure receipt is retained as
`m3-overflow-actual-pressure.json`, not concealed by the actual pass.

Fresh all sampled owned PIDs from both passing jobs absent; privileged setup
inactive/MainPID0/success; existing snapshot service MainPID94383/NRestarts0/active.
Only reader/test user cgroup measured here; root setup/queue sibling and full
runtime aggregate are not accepted against M5 from these small fixtures.
No install, unit/capability change or additional sudo needed for these tests.
Test-only extensions preserve default synthetic and first actual mode; no source
behavior changed in this packet. Diff check passes. No commit/publication.

M3 still needs remaining adversarial namespace/raw-name/replacement cases,
ignored/mount boundaries/watch exhaustion and normal/heavy visibility measurements
before approved workspace qualification. M4 durable replay, M5 scale/24-hour soak,
M6 publication/install/72-hour soak remain. Next packet: remaining bounded owned
namespace and visibility controls, then address the first source failure rather
than expanding review. Memory disposition forbidden, no personal write.

### Owned replacement/raw-byte/visibility packet

Gated --actual-edges passes file→directory→file replacement without retired
child resurrection, non-UTF8 create/rename with base64 byte identity verified
through native CLI, normal frontend CLI and fresh MCP, and bounded visibility
controls. Changed test result comparisons use authoritative path_bytes_base64
where present. Native visibility assertions now include response arrival within
deadline instead of accepting a late successful response.

Timings preserved in `m3-edges-visibility-timings.json`: native normal
create50.90ms/delete63.35ms/raw-rename7.03ms; normal frontend CLI create202.71ms;
fresh initialized MCP create146.45ms; all128heavy burst entries271.68ms from
before first mutation. Normal1second/heavy10second checks pass for this tiny
frozen workload, not at current6.73m-entry scale. MCP starts fresh and initializes
before its owned mutation, then queries/polls through the same session. Startup
cost is not silently folded into ingestion freshness.

Initial attempt failed a cold-MCP end-to-end assertion at1.352689seconds. Retain
`m3-edges-actual-pressure.json` and `m3-edges-cold-mcp-failure.json`; adjudication:
invalid as event-ingestion failure because it timed session startup after the
mutation. The observed cold end-to-end latency remains real/unpassed evidence;
no warm CLI/MCP percentile acceptance is claimed. Failed fixture preserved under
failed-cold-mcp-archive. Corrected actual receipt
`m3-edges-actual-pressure-b.json`:exit0,11.541seconds, memory.peak146,153,472bytes,
swap0. Identity/source hashes in m3-edges-identity.json.

Default assembled synthetic fixture rerun because shared test helper changed:
PASS, `m3-edge-fixture-regression-pressure.json`,11.363seconds,
memory.peak145,338,368bytes/swap0. No additional source behavior change in this
packet. Fresh all24actual and25synthetic sampled owned PIDs absent; workers38518,
43393/44603 reaped; privileged setup inactive/MainPID0; installed snapshot
MainPID94383/NRestarts0/active. Diff check passes, no commit or publication.

M3 ignored/mount boundary/watch-exhaustion and adversarial-race qualification,
startup under frozen workload and current-scale freshness/resource gates remain.
M4 accepted-generation persistence/replay is still missing; clean-rebuild restart
is not durable recovery. Next substantive source packet should address that
missing recovery path rather than add duplicate easy fixtures. M5/M6 and both
soaks unchanged. Memory disposition forbidden; no personal memory write.

### Durable replay source checkpoint

Opt-in supervisor/native-worker accepted-mutation replay implemented and qualified
on owned fixtures with indexed root absent. Separate fsynced committed cursor
protects earlier acknowledged view from a partial uncommitted tail; source gap
remains explicit. Details, limits, failures, Standards/Spec disposition and next
checkpoint/rollover packet: `2026-10-10-plan6-durable-replay.md`. M4 IN_PROGRESS,
not accepted; installed snapshot runtime unchanged. All9sampled replay job PIDs
absent. Original candidate/runtime hashes are historical; latest source replay
receipt m4-durable-cursor-identity.json is authoritative for this packet.
