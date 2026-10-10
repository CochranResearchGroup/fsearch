# Plan0006 assembled broker and confinement checkpoint

Status: M3 IN_PROGRESS; BRK-CONF-001 blocks actual activation. Plan0006 remains OPEN.

Worktree `/tmp/fsearch-incremental-generations`, branch `feat/incremental-generations`, base `51f6af730f8b3f8f459c721ec6b6fffa8f34d49d`. Changes are uncommitted and unpublished. The previous wiring note is historical; this note reconciles subsequent source progress.

## Working source and validation

The assembled standalone broker now uses authenticated descriptor transport, pinned root identity, actual unprivileged contained inventory, a bounded SQLite parent-linked admission map, actual native catalog mutation and truthful coverage. Owned fixtures exercise directory inventory, ancestor rename, move-out revocation, root replacement, startup reconciliation, overflow, restart after proven worker reap, normal CLI and fresh MCP clients. Descriptor records remain synthetic; actual fanotify delivery and mutation-to-search SLA are unqualified.

All32 registered native test groups passed serially in `plan6-evidence/m3-broker-source-validation.txt` with the unchanged pressure guard. Earlier failed/pressure-stopped runs remain preserved. Subsequent product change only adds the actual-source refusal below; focused assembled CLI/MCP regression passes in `m3-broker-confinement-gate.txt`, including refusal before catalog/root/transport access and no created state. Both boundary workers60950/61751 were reaped. Dedicated cgroup peak145330176bytes, owned swap0; no current-scale resource claim follows from small fixtures.

## BRK-CONF-001: inventory descriptor ancestry race

The owned diagnostic pauses immediately after the helper validates an opened directory and before its directory read. It moves the directory to an owned sibling outside the admitted root, adds a new outside filename, then resumes. `m3-broker-ancestry-race-abi.txt` proves one `getdents64` read through the moved-out descriptor. The helper subsequently exits4 with a gap and exports no outside filename. Export containment passes; outside metadata-read confinement FAILS. A successful diagnostic process exit means evidence collection completed, not that confinement passed. The first two fixture attempts did not reach their trigger and are retained as invalid qualification attempts.

The fixture interposes the actual readdir64 ABI; it does not weaken the helper's sandbox. Everything read or renamed is synthetic and owned. No capability, fanotify group or mark was created. The kernel's [Landlock documentation](https://docs.kernel.org/userspace-api/landlock.html#rights-associated-with-file-descriptors) confirms that read permissions are associated with opening, rather than rechecked on subsequent reads. Our fixture provides the concrete directory-read evidence. Before/after userspace validation cannot close this demonstrated interval; adding more such checks is not an accepted repair.

Actual `--source-kind fanotify` now refuses with `broker_confinement_unqualified` before opening the root, contacting the catalog or requesting a descriptor. Fixture mode remains explicit and diagnostic. No override is provided. The compiled setup helper is non-installed and has never been executed.

## Remaining gates and next packet

Outcome01 is not accepted: the confinement invariant needs an enforceable read-time boundary. Also resolve the real transport credentials topology: SO_PEERCRED of a user-created socketpair cannot attest a subsequently privileged setup process; a root-created accepted socket is the proposed source-preparation path, not proof. Conservative bootstrap rejects any namespace event during inventory and is not current-scale startup acceptance. Do not ask for privileged observation based on the passing component tests.

Next is a bounded design packet assessing a kernel-enforced read-time boundary against BRK-CONF-001 and the unchanged600MiB envelope. It must identify exact additional effects/capabilities and a repeatable owned negative control before any activation request. If no candidate can satisfy the invariant, preserve this rejection and request an explicit contract decision rather than weakening the boundary. Source preparation remains authorized; privileged activation remains separately gated.

M4 durable checkpoint/replay, M5 combined resource qualification and24-hour synthetic soak, M6 reversible installation/direct installed CLI/MCP and72-hour operational soak remain open. No abbreviated soak is acceptance.

Fresh installed readback: servicePID94383, native worker3338, NRestarts0; runtime `e0ec8e758db755dbd3cf8b3a83c9e4a467c50137`, original workspace pilot snapshot/socket. No experiment broker/helper remains in the fresh process census. Installed runtime is unchanged.

Memory disposition: forbidden; no personal durable memory write authorized. Machine-readable non-write receipt is recorded at closeout.

## Superseding operator decision and source continuation

Operator accepted bounded metadata reads through formerly admitted descriptors after concurrent moves and rejected kernel work. BRK-CONF-001 is no longer a contract blocker; retain all original diagnostic/strict-criterion failures above as history. ADR0005 is updated. Current source/startup/activation state is in `2026-10-09-plan6-bootstrap-candidate.md`. Actual privilege/observation remains separately gated.
