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
