---
status: accepted for Plan 0006 source integration; installed adoption remains unqualified
---
# Publish immutable filename generations with bounded compaction replay

Plan 0006 and its operator execution direction require continuous indexing without losing the accepted query view during update failure. Native catalog source uses a packed immutable base, a bounded copy-on-write overlay and monotonically allocated directory-entry identities. An identity represents one entry, not an inode; deletion and recreation allocate a new identity, preventing resurrection of descendants or hard-link conflation.

A reader acquires a reference to a complete view under the catalog owner lock. Its base and overlay remain immutable until release. Mutations validate their expected sequence, namespace, parent tree and identity, then publish a new view. The existing serial active-query contract is preserved; concurrent clients remain bounded by the service queue. Reader references may span updater work, and old views are reclaimed only when their final reference is released.

Compaction captures an immutable view at sequence S and reserves replacement memory before construction. One builder runs outside the owner lock while accepted subsequent mutations enter a bounded replay log. After joining the builder, independent validation compares the candidate with the captured view. Publication under the owner lock combines the candidate with the final replayed mutation for each identity and advances the generation atomically at the current accepted sequence. An event arriving after publication belongs to the new view. A replay gap/overflow, failed allocation, invalid candidate, lagging-reader budget or shutdown prevents publication and exposes deferral; accepted updates and the prior serving generation remain intact. No automatic retries or cleanup assumptions are introduced.

The native allocation ledger includes retained bases, overlays, reader views, tickets and replay capacity, with conservative allocator overhead. Reserved bytes are commitment, not resident memory. Whole-service RSS/PSS/cgroup memory and swap measurements remain the acceptance authority; fixture-only objects and other processes are not hidden by this ledger. The catalog itself performs no filesystem operations. Durable checkpoints and real watcher reconciliation remain later Plan 0006 milestones.

Source acceptance does not imply installation, workspace monitoring, current permission checks or whole-workspace memory acceptance. Test-only adapters qualify catalog semantics against rebuilt native snapshots; production query collection and acceleration integrate separately in M2. Prototype branches remain excluded from master.
