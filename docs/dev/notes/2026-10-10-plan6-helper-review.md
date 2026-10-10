# Privileged-helper package review

Scope: `packaging/broker/{manage.py,test_manage.py,README.md}`. Fixed point
HEAD51f6af730f8b3f8f459c721ec6b6fffa8f34d49d; package is entirely untracked.
No commits exist between the base and HEAD; three-dot committed diff is empty.
Accordingly this review explicitly examines the added working-tree package,
not a claimed committed diff. Review-baseline clarification was offered; absent
an alternative, use the narrow helper scope selected in the preceding routing.
No delegated reviewers; Standards and Spec evaluated separately by primary.

Sources: AGENTS.md, CONTRIBUTING.md, docs/agents/codex-stack.md,
docs/agents/domain.md, ADR0005, continuous-service specification0004 and operator
request for a maintained privileged helper without repeated sudo authentication.
Current sources suffice; advisory memory discovery skipped. Memory disposition
forbidden: no personal durable-memory write authorized.

## Standards

No accepted documented-standard violations in this bounded package. Fowler smell
heuristics do not justify a blocking abstraction/refactor in this small installer.
Existing five owned controls pass. This does not imply specification acceptance.

## Spec

### HLP-001 — blocking, P1: partial writes escape rollback tracking

Criterion: spec0004 requires bounded cleanup; package promises rollback and
refusal to overwrite existing custody. In manage.py142–145, append to `written`
occurs only after writing and closing. An OSError during write leaves the newly
created partial executable untracked. Directory removal then raises ENOTEMPTY,
masking the original failure and leaving an unreceipted file. Subsequent install
refuses overwrite and ordinary remove has no receipt to recover from.

Reproducer: owned destdir, valid staged fixture ELF; intercept Path.open('xb')
for setup to write two bytes, flush, then raise injected disk-full. Observed
surviving helper bytes7f45 and raised ENOTEMPTY on its version directory. No
systemd/root effects. Confidence high. Remedy: register created files immediately
following successful exclusive open, before any write; preserve original failure
and aggregate cleanup errors. Apply same fix to receipt creation. Add failed-write
regression; systemctl rollback failures must likewise not bypass cleanup/reporting.

### HLP-002 — blocking, P2: inherited umask prevents setup access

Criterion: helper runs as configured UID1000 and must execute the sealed binary
and read fixed administrator config. manage.py120 uses mkdir(mode0755) without
normalizing permissions; process umask077 turns new directories into0700.
Root-owned version directory/config parent then deny UID1000 traversal.

Reproducer: stage valid owned fixture bundle; os.umask(077), install to owned
destdir, restore mask. Every newly created directory is0700. Confidence high.
Remedy: explicitly chmod newly created directories0755 independent of umask;
do not alter existing directories. Add restrictive-umask lifecycle control.
Fresh installed directory readback is0755/root, so existing installation is
unaffected by this case; this is installer portability/reliability failure.

### HLP-003 — nonblocking_backlog, P3: receipt activation state is stale

Operator's successful --listen install prints/stores activation=disabled even
though system socket is active. Hashes/custody remain valid, and authoritative
systemctl readback disambiguates it, but the installer receipt misstates requested
state. Remedy: record socket activation request/result separately from live state;
never imply a filesystem mark was activated merely by starting a socket.

## Disposition

Standards: zero accepted violations. Spec: two accepted blocking defects (highest
P1) and one nonblocking receipt defect. Review is complete; fixes have not been
applied by this review. Installed helper binary/config/units were not modified.
Actual fanotify delivery remains unqualified: last attempt stopped at host-pressure
preflight, before a test/helper process or mark existed. Preserve these findings
for one bounded remediation pass, then verify only their regression controls and
critical effects; do not restart broad discovery.

## Closed-world remediation

Operator authorized fixes after review. HLP-001: installer tracks a newly opened
payload/receipt before writing; cleanup attempts every step, records failures as
exception notes and preserves the initiating error. Systemd rollback also
attempts stopping setup, and a disable timeout no longer bypasses file cleanup.
HLP-002: only newly created directories are explicitly chmod0755 independent of
umask. Existing directories are not changed. HLP-003: new receipts remove the
ambiguous activation field and record socket activation request plus command
result, explicitly distinct from live socket state or a filesystem mark.

Eleven focused lifecycle controls pass, including restrictive umask, partial
binary and receipt writes, retry after failed write, cleanup failure with original
error preservation, activation metadata and mocked systemd enable/disable timeout.
The systemd failure control maps all root paths into owned destdir and mocks every
systemctl call; no actual privilege effects. Original pre-fix reproducers remain
above. Both blocking findings and the nonblocking receipt finding are resolved in
source. No broad rediscovery was performed; the systemd unit payloads and helper
binary were unchanged. Fresh installed payload hashes still match the original
root receipt; socket active, setup inactive/MainPID0; snapshot service
active/MainPID94383/NRestarts0. Existing installation receipt retains its historical
stale field; it was not silently rewritten. No reinstall/authentication is needed
for these source installer fixes. Actual event delivery remains unqualified.
Memory disposition: forbidden; no durable personal-memory write authorized.

## Authorized checkpoint reconciliation

2026-10-10: operator authorized committing qualified source. Eleven owned
installer controls were rerun by the primary agent and pass. This checkpoint
preserves resolved HLP-001/HLP-002/HLP-003 findings; no installation, systemctl
activation or root-scope change was performed. Earlier untracked/base descriptions
remain historical.
