---
status: candidate source decision for Plan0006 M4; program and installed acceptance pending
---
# Persist private catalog generations behind descriptor boundaries

ADR0004 retains its immutable-view, identity, replay and memory principles. This
M4 continuation supersedes its durability deferral and pure-engine I/O statement
only at new private checkpoint descriptor APIs. Query/mutation paths never probe
indexed storage. The codec streams owner-private cache descriptors; the worker
owns cache pathname opening and the supervisor owns generation publication.

FSCG0001 persists sequence/generation/highwater and byte names; FSHM0001 persists
bounded cached coverage metadata. Validation reads bytes back against intended
checksums without constructing another resident catalog. Complete recovery
independently validates checksum, tree, binding and metadata sequence before
query readiness. Metadata timestamps retain original observation provenance.

Background capture permits continuing queries/mutations. A two-slot journal
manifest selects a complete private generation plus committed replay prefix;
post-capture accepted records are carried before publication. Replacement stages
both identities before accepted service-state publication, so either state can
select a complete matching pair after an interrupted publication.

Partial replay tails preserve the committed view read-only; corrupt committed
replay serves the accepted private generation deferred. Lost observation remains
an explicit source gap. Local-filesystem fsync assumptions and all power-loss,
capacity/current-scale and corrupt-pair fallback acceptance remain unqualified.
The format is opt-in supporting source, without installed workspace acceptance; no GUI or root admission
change follows. Evidence:2026-10-10-plan6-durable-replay.md and its hash receipt.

## Bounded corrupt-generation fallback

Same-identity rollover publishes manifest version3 with exactly two records:
selected generation first, retained previous generation second, distinct slots
and nondecreasing selected sequence. Legacy single-record manifests and version2
two-identity replacement manifests remain readable. Replacement never permits
fallback to a different accepted snapshot identity. Storage retention remains
two slots; no additional resident catalog or indexed-root probe is introduced.

A selected checkpoint/metadata/sequence failure advances once to the retained
accepted generation, validated by the native worker before query readiness.
Fallback is read-only with catalog_checkpoint_fallback coverage; no observation
lease can clear it and no journal append/replacement is admitted. If private
recovery cannot select a valid view, the original qualified cache is attempted
only against the recorded accepted identity. Exhausted corruption recovery
returns catalog_checkpoint_unavailable without a new worker per query. A changed
baseline returns snapshot_conflict. Invalid manifests do not authorize scanning
or selecting unreferenced cache files.

This narrows corrupt-pair source gaps; full process/power-loss/crash and startup
qualification, durable observation reconciliation and M3/M5/M6 remain open.

## Bounded durable groups —2026-10-10

The public owner-private service accepts at most8contiguous mutations in one
durable group, after reserving all records inside the existing1024record and
16MiB journal bounds. The native worker applies entries in order while the
supervisor keeps the client active; queries, internal checkpoint dispatch and
replacement promotion cannot expose an uncommitted native prefix. Each native
reply must bind the accepted snapshot, sequence and valid entry ID without
a deferred reason. A failed native prefix is reaped/discarded and recovered
from the prior committed view.

Journal frames/checksums/cursor format remain unchanged. Write the bounded
frames and chain, sync the log, atomically publish and sync the committed cursor,
then reply. Crash before cursor publication retains the old committed prefix
read-only when a tail exists; published cursor replays the complete group.
No unsynced acknowledgement, in-place cursor overwrite or larger retention
is introduced. Failure/timeout after publication remains an ambiguous accepted
effect requiring current readback, not blind retry.

The broker groups only independent regular create/rename entries after ordinary
rooted eligibility checks. Shared namespace sides, directory work, replacements,
exclusions and non-durable fixtures retain single application. The service
advertises remaining record capacity so groups stop at the same journal limit.
Source acknowledgement follows durable group completion; a fresh EAGAIN remains
necessary for watching. The [durable batch qualification](../dev/notes/2026-10-10-plan6-durable-batches.md)
retains public red/green, cursor cuts, publication pause, native gap/identity
controls and the fixed actual workload. Power-loss, aggregate/current-scale
and operational soaks remain unqualified.
