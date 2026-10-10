# Plan0006 broker wiring and pressure checkpoint

State: PARTIAL_SOURCE_WIRING_PASS / QUALIFICATION_HELD_HOST_PRESSURE
Owner: Codex; operator ecochran76
Parent: Plan0006, M3 / issue29; delivery outcome01 remains OPEN
Baseline: feat/incremental-generations at51f6af730f8b3f8f459c721ec6b6fffa8f34d49d
Checkpoint time:2026-10-09T21:46Z

## Verified progress

`fsearch_broker_source.py` implements authenticated owner-checked Unix
SOCK_SEQPACKET descriptor transfer, generation/session binding, close-on-exec
adoption, rejection/reaping of malformed and excess SCM_RIGHTS descriptors,
and nonblocking-source validation. The reader has per-turn batch/byte/time
bounds, consumes dropped outside batches within those bounds, and derives a
source drain cut only from EAGAIN. Exhaustion remains pending; EOF, malformed
batches and application failures become sticky deferred coverage.

Admitted create/delete/rename sides now reach the production CatalogClient,
native mutation API and normal query service. CatalogSink handles file
replacement, independent hardlink entries, directory ancestor-path updates and
retired-map removal. Directory creation requires an inventory callback; missing
inventory fails deferred instead of claiming freshness. CatalogBroker publishes
pending/watching/deferred coverage through the actual native API and preserves
the first known pending timestamp across bounded turns.

The parser incorrectly rejected native root entry ID0. Actual service wiring
reproduced admission_invalid; zero-based admitted IDs are now supported while
booleans and negative IDs remain invalid. The root-ID regression is added to
the existing parser fixtures.

Owned ordinary descriptors plus actual filesystem mutations pass create,
rename, hardlink, delete, PDF-filter, outside-side drop and malformed-source
controls through normal CLI and fresh MCP clients. A malformed batch leaves
accepted cached hits usable with deferred coverage. This test's admitted handle
map is a fixture; it is not production containment. Source injection accompanies
the mutation; it is not actual fanotify delivery. Its measured1.302second
create-through-CLI-plus-fresh-MCP duration is diagnostic, not a1second freshness
SLA pass or warm latency acceptance.

Eleven transport/reader unit cases passed before subsequent catalog integration.
The new test is registered in Meson. Launcher source passes
`cc -Wall -Wextra -Werror -fsyntax-only`. Registered Meson/full native suites and
post-correction parser/transport reruns remain unexecuted at this checkpoint;
host pressure prevents qualification. No source-accepted or integration-ready
claim is made.

## Retained evidence and independent verdicts

- `plan6-evidence/m3-broker-catalog-first-pressure.json`: preflight refused,
  memory-full PSI2.92%; no child launched.
- `m3-broker-catalog.txt` and its pressure receipt: actual root-ID failure.
- `m3-broker-catalog-retest.txt` and receipt: fixture incorrectly used a
  compound natural-language phrase with the literal find API. Corrected to
  literal names and a separate PDF-filter query; public routing unchanged.
- `m3-broker-catalog-final.txt` and receipt: synthetic wiring PASS,4.985seconds,
  cgroup peak139784192bytes, owned swap0, maximum sample gap0.233seconds.
  Sampled RSS183934976bytes is reported separately from the cgroup peak.
- Delivery: NOT_QUALIFIED. Confinement: NOT_QUALIFIED. Current-scale resource
  and freshness: NOT_QUALIFIED. Durability: NOT_IMPLEMENTED.
- Spec: outcome01 incomplete. Standards: bounded transport/failure semantics
  reviewed by primary; required comprehensive validation is pending. No
  independent reviewer or delegated acceptance is claimed.

## Concrete setup source and remaining activation boundary

`fsearch_broker_setup.c` is built as a non-installed preparation target. It
accepts only an inherited private seqpacket descriptor, reads fixed root-owned
non-writable `/etc/fsearch/broker-root.conf`, authenticates the configured index
UID, and receives session/generation bytes over the channel rather than process
arguments. Its effective capability set must be exactly CAP_SYS_ADMIN. It creates
one notification-only, nonblocking/CLOEXEC filesystem mark, transfers the sole
event descriptor, closes it and exits without reading events. Unsupported
features, extra privileges, malformed requests and backpressure reject with an
identifier-free diagnostic. No unlimited marks/queues, permission events,
outside handle lookup, installation or capability grant is introduced.

This source has not been executed. No config, privileged service, capability,
mark or filesystem-wide observation was activated. The setup handoff does not
yet prove actual filesystem/root identity attestation, post-transfer behavior,
privilege separation or ancestry confinement. Those are rejection gates before
activation, not assumptions supplied by the ordinary-descriptor tests.

## Hard stop and restart

Host pressure rose after the completed short owned test. Fresh readback:
memory-full avg10=6.76%, IO-full avg10=16.03%, above frozen2%/15% thresholds.
Additional native/frontend experiments are stopped. All owned experiment handles
are terminal. Source, transport, descriptors and temporary fixture tree were
closed/removed by the completed test. OS census contains only the pre-existing
production FSearch supervisor94383 and worker3338; NRestarts0. Installed native
runtime remains e0ec8e758db755dbd3cf8b3a83c9e4a467c50137. No production change.

Next: recheck host pressure; run corrected parser/transport and registered native
tests under the unchanged1280MiB/no-swap envelope. Then finish actual contained
admission/map construction, directory inventory, source-supervisor cleanup and
bootstrap integration for outcome01. Extend the real CLI/fresh MCP test with
directory/race/stall controls, publish exact runtime identities, and review the
assembled launcher/observation/rollback packet before requesting its separate
privileged effect approval. Do not activate this partial candidate.

Plan0006 M3–M6 and native Plan0007 remain open. The24hour synthetic and72hour
installed soaks retain their full durations. No elapsed-time shortcut or changed
resource/root envelope is accepted. This is source progress followed by a
verified resource hard stop, not program completion or a new scope definition.

Memory disposition: forbidden; no durable personal memory write authorized.
