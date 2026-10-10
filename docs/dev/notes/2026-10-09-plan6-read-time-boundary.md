# Plan0006: read-time containment adjudication and listener source repair

Status: M3 IN_PROGRESS; BRK-CONF-001 remains blocking for actual activation.
Owner: Codex; operator: ecochran76. Parent: Plan0006 / issue26; M3 issue29.
Source custody: `/home/ecochran76/worktrees/fsearch-incremental-generations`,
`feat/incremental-generations`, base `51f6af730f8b3f8f459c721ec6b6fffa8f34d49d`.
Source changes remain uncommitted and unpublished. No installation or privilege effect.

## Execution control and packet

Continuation began2026-10-10T02:33:29Z (local2026-10-09). Checkpoint by
2026-10-10T05:28:29Z, strictly before the three-hour deadline05:33:29Z and
before two million tokens. This independent clock supersedes neither the
historical exceeded window nor its receipts. Prior turn was progress: exact
worktree contents and dirty state moved from volatile storage to durable custody.

Bounded outcome: adjudicate an enforceable read-time design against the actual
race; repair the independent credential topology without enabling fanotify.
Existing32-group evidence is historical source evidence, not rerun here.
Only changed transport/setup surfaces receive focused verification. No root
scan, privileged fixture, kernel loading, capability grant, mark or service
replacement is authorized by this packet.

## Current authoritative finding

The prior identity manifest still matches every recorded source/helper except
the intentionally edited broker CLI, setup helper, broker process test and
Meson test list. The matching compiled inventory helper remains unchanged.
Its owned adversarial diagnostic is retained: one outside `getdents64`, no
outside export, gap/exit4. This packet does not rerun an unchanged reproducer
or reinterpret diagnostic exit0 as acceptance.

Current host kernel: `6.6.87.2-microsoft-standard-WSL2`. The approved workspace
is on `/dev/sdd`, ext4, mounted at `/`. Exact matching Microsoft kernel tag
sources were fetched read-only and hashed; see the identity receipt. They are
stored at `/home/ecochran76/worktrees/fsearch-kernel-containment-research-2026-10-09`.
This is source evidence, not proof of the running kernel's complete build config.

- [Matching WSL readdir source](https://github.com/microsoft/WSL2-Linux-Kernel/blob/linux-msft-wsl-6.6.87.2/fs/readdir.c):
  `iterate_dir` checks `security_file_permission` before acquiring the directory
  `i_rwsem`, then calls the filesystem iterator while holding that shared lock.
  An LSM admission decision at that hook is not atomic with namespace ancestry
  and enumeration. Holding the target inode alone also leaves ancestor moves.
- [Matching AppArmor source](https://github.com/microsoft/WSL2-Linux-Kernel/blob/linux-msft-wsl-6.6.87.2/security/apparmor/file.c):
  `aa_file_perm` may return on cached allowed permissions with compatible labels.
  AppArmor's ordinary descriptor path is not a demonstrated per-read repair.
- [Landlock descriptor rights](https://docs.kernel.org/userspace-api/landlock.html#rights-associated-with-file-descriptors):
  opening grants descriptor access; the existing actual-helper diagnostic
  demonstrates the directory consequence. No additional equivalent check repairs it.
- [Directory locking](https://docs.kernel.org/filesystems/directory-locking.html)
  and [matching rename source](https://github.com/microsoft/WSL2-Linux-Kernel/blob/linux-msft-wsl-6.6.87.2/fs/namei.c):
  cross-directory rename takes the filesystem rename mutex before directory
  locks. Ordinary same-parent rename does not take that filesystem mutex.
  The rename mutex alone therefore does not stabilize the configured root
  pathname against replacement or same-parent renaming of a prefix.
- [Matching namespace source](https://github.com/microsoft/WSL2-Linux-Kernel/blob/linux-msft-wsl-6.6.87.2/fs/namespace.c):
  mount-topology exclusion uses a private `namespace_sem`; a simple external
  module cannot assume an exported supported API for this lock.

These reject the current userspace boundary and ordinary LSM-hook replacement.
They do not establish that all possible architectures are impossible.

## Concrete strict-boundary candidate

A kernel-assisted, bounded **scoped metadata operation** could perform ancestry
validation and the metadata read inside one namespace-stable kernel operation.
This is a candidate architecture requiring implementation and proof, not an
available ioctl or a passing primitive. No kernel source modification, build,
module load or VM boot occurred in this packet.

Proposed request: owner-authenticated root session/generation, a bounded relative
path, pagination cookie and output limit. It accepts no arbitrary outside handle
or caller-selected root. Copy/validate input and preallocate a maximum64KiB
kernel output buffer before locking; copy results to userspace only after
unlocking. Root identity, configured locator, mount identity and containment
must remain valid across the entire read, including stat/handle extraction,
not merely enumeration. Repeat the guarantee for every page. Unknown state
returns a gap without reading the rejected object.

Required mechanism: namespace-topology exclusion, filesystem rename exclusion,
and appropriate ancestor/parent inode locks in a proved lock order. Preserve
the configured root locator against same-parent root/prefix rename, reject
symlinks and cross-mount resolution, and perform lookup/identity/read inside
that exclusion. A target inode lock or a pre-read LSM check alone is insufficient.
No lock may be held while waiting for a userspace acknowledgement or copying
to a potentially faulting userspace buffer. Cancellation, partial output,
filesystem stalls and all failure exits require a lock/reference cleanup proof.

Additional effects/cost: kernel development with internal VFS/namespace APIs;
an isolated guest kernel or modified host kernel for actual verification;
temporary interference with cross-directory renames on the filesystem and
possibly mount operations while reads execute. On this host that filesystem
contains more than the workspace. No such interference or host-kernel change
is authorized. No matching kernel build tree or `qemu-system-x86_64` executable
was found at startup. Host-kernel replacement/reboot is not the proposed next test.

Frozen resource adjudication: at most one active read, bounded64KiB output and
bounded root/session/ancestor state avoid a new per-directory persistent
kernel watch structure. This does not prove600MiB combined steady or1.25GiB
update memory, zero swap, latency or bounded lock duration. All remain measured
rejection gates. Disk stalls while holding broad locks are a material unsolved
operational issue; a timeout in userspace is not proof that kernel locks released.

Owned verification required before activation review: root/ancestor/target
moves before and during reads; same-parent root rename/replacement; mount
detach/replacement; hard links/symlinks; pagination; cancellation and injected
read stalls. Instrument actual filesystem iterator/metadata entry, not just
returned output. A moved-out directory must reach no iterator after rejection;
a concurrent move during a read must either remain blocked until the bounded
read finishes or cause rejection before reading. Prove both positive admission
and the existing negative control's sensitivity, lock release, process reap,
combined resource limits and unrelated rename latency. Use only an owned
guest disk/tree; no filesystem-wide host marks are needed for this primitive.

Decision required: whether to extend the broker architecture to kernel-assisted
containment and prepare an isolated guest proof, while keeping the exact
criterion and resource targets. If the operator declines that additional
architecture, the current broker cannot activate under its existing contract;
an explicit alternative design/contract decision is needed. Descriptor-scoped
read access with strict export containment would be a criterion change, not a
repair, and has not been adopted. Do not weaken the criterion implicitly.

## Independent transport source repair

`fsearch_broker_setup.c` now takes `--listener-fd FD`, validates a root-created
AF_UNIX/SOCK_SEQPACKET listener at the fixed `/run/fsearch/broker.sock`, then
accepts one configured owner client within a bounded wait. It refuses a
user-created listener, wrong endpoint/client, non-listener or wrong socket type
before creating any group/mark. The accepted endpoint is CLOEXEC and closed on
all exits. Fixed administrator root configuration and session/root attestation
remain mandatory. Inherited connected socketpairs are no longer setup input.

`fsearch_broker.py` adds `--handoff-socket` as an alternative to inherited fixture
transport. Kernel peer credentials are checked before sending session bytes.
The fanotify refusal still executes before root, catalog or transport access
for both input forms. Source preparation adds no override or activation path.

The actual C accept function is tested using owned unprivileged sockets. A child
accepts on its parent's listener; the client attests the creator PID, not the
accepting child. Wrong creator/client/path, socketpair and wrong type are
negative controls; descriptor counts and child reap are checked. Production
root credentials and actual fanotify transfer remain unqualified.

The assembled owned CLI/fresh MCP fixture starts through a named listener,
then restarts through inherited fixture transport. Create, populated directory,
ancestor rename, overflow/deferred coverage, restart-after-reap and root
replacement remain externally tested. This is an actual source repair with
integration evidence, not M3 or whole-program acceptance.

Evidence: `plan6-evidence/m3-listener-20261010T0240-*` retains the initial passing
run; `m3-listener-20261010T0244-*` records the expanded final negative controls.
Both run in dedicated transient user cgroups under unchanged host pressure
gates, MemoryMax1280M/MemorySwapMax0/CPUQuota150%/IOWeight10 and40-second
deadlines. Strict-warning C compilation, the actual listener fixture,13 source
transport cases and assembled CLI/MCP checks are the focused scope.

## Program state

M1/M2 remain source accepted. M3/outcome01 remains incomplete because the
read-time confinement gate lacks an implemented, qualified mechanism. M4
durability, M5 combined current-scale qualification/24-hour soak and M6
publication/reversible installation/direct acceptance/72-hour soak remain open.
No tracker mutation, commit, installed runtime change or new root admission.
The current snapshot service remains useful but is not continuously updating.

Memory discovery skipped: current source and retained diagnostic identify the
exact accepted finding; prior memory would not strengthen its kernel proof.
Memory disposition: forbidden; this source packet does not authorize personal
durable memory writing. Preserve the runtime non-write receipt at closeout.

Final focused run: exit0,7.993seconds; cgroup memory.peak153,153,536bytes, swap peak0; sampled descendant RSS peak209,317,888bytes, maximum sampling gap0.236seconds. The systemd terminal summary reports256KiB after process exit; use the in-run cgroup receipt, not that inconsistent terminal summary, for this bounded fixture measurement. Neither establishes current-scale acceptance. Boundary workers80400/81407 were reaped by the fixture and absent in the subsequent OS census. Final source/build/kernel hashes are in `m3-listener-20261010T0244-identity.json`.

## Three-turn blocked audit —2026-10-10T02:44:33Z

The same BRK-CONF-001/architecture decision remained unresolved across the source-repair goal turn and two automatic continuations. The source-repair turn was progress; the first continuation was no progress, and this continuation revalidated the same condition with zero identity-manifest drift. The actual fanotify refusal remains present. No operator answer or additional effect authority has arrived. All independent authorized work identified in this packet is checkpointed; kernel-assisted architecture preparation is the pending operator decision, with privileged proof separately withheld. No milestone or program completion is claimed. Set the goal control toBLOCKED under the three-turn rule; keep Plan0006OPEN and preserve the full objective, source custody and original gates. This is not a time-budget stop: independent elapsed time is11minutes4seconds, before the05:33:29Zdeadline.

## Superseding operator decision and source continuation

Operator accepted bounded metadata reads through formerly admitted descriptors after concurrent moves and rejected kernel work. BRK-CONF-001 is no longer a contract blocker; retain all original diagnostic/strict-criterion failures above as history. ADR0005 is updated. Current source/startup/activation state is in `2026-10-09-plan6-bootstrap-candidate.md`. Actual privilege/observation remains separately gated.
