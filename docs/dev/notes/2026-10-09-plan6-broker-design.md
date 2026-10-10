# Plan0006 M3: filesystem event broker review packet

Status: DESIGN_PREPARED; implementation and privileged activation unqualified
Date: 2026-10-09
Owner: primary Plan0006 execution agent
Source authority: ADR0005; Plan0006; operator acceptance of the recommended design direction.

## Decision and bounded outcome

Keep the accepted 600 MiB aggregate steady target and 1.25 GiB update target. Investigate one filesystem notification mark instead of one inode-pinning watch per directory. This packet specifies the candidate and its rejection gates. It grants no capabilities, installs nothing, and changes neither the approved workspace root nor production runtime. M3–M6 remain open. Historical inotify failures remain evidence, not waived gates.

## Architecture and observation boundary

Use a notification-only fanotify group, nonblocking and close-on-exec, with directory/name/target file-handle reporting and FAN_RENAME support where the actual kernel/filesystem supports them. Add one FAN_MARK_FILESYSTEM mark to the filesystem containing the approved root. Feature probing must reject unsupported combinations; there is no silent inode-watch fallback that evades the aggregate budget. Do not request permission events, unlimited queues/marks, PID descriptors, process inspection, or file-content access.

The kernel queue necessarily contains events from elsewhere on that filesystem. Workspace-only export does not make collection workspace-only. A future activation request must explicitly authorize this transient filesystem-wide observation, name the actual filesystem/mount identity, and distinguish it from approved-subtree indexing. No Windows, network, Drive, or additional filesystem marks are implied. Outside names, handles, PIDs and raw queue buffers must never be logged, persisted, exported to the updater, or used for secondary metadata lookups. Parse only enough to decide admission; discard other records immediately. Diagnostic counters contain counts/reasons, not outside identifiers.

Separate a minimal setup launcher from an unprivileged event broker. Proposed launcher privileges are CAP_SYS_ADMIN for group/mark creation, with no CAP_DAC_READ_SEARCH or arbitrary open_by_handle_at support. Launcher validates a fixed operator-owned root configuration, establishes the group/mark, and passes the descriptor over a private authenticated Unix transport. It then exits. Broker runs as the index owner, with no retained capabilities, no network, and filesystem access restricted to the admitted root using existing containment primitives. Descriptor ownership, continued read behavior after privilege drop/transfer, seccomp compatibility and cleanup are qualification questions, not assumed facts. If this split cannot be proved on the actual platform, return to design review rather than leave a privileged reader running.

## Identity, bootstrap and filtering

Pin the admitted root and record root generation, filesystem identity, mount identity, and root directory handle. Build a compact directory-handle to stable catalog-entry map during a contained baseline inventory. Key handles by filesystem ID, handle type, length and opaque bytes; never infer scope from a basename, PID, inode number alone, or a user-supplied handle. The handle map and retained bootstrap events have fixed byte/entry limits and count against the aggregate budget.

Begin event collection before inventory. Buffer bounded records, construct the map, then replay accepted events in sequence and establish a drained-source barrier before publishing fresh coverage. Overflow, unsupported handles, identity change, ambiguous ancestry, or inability to reconcile the baseline keeps coverage deferred/reconciling. A heartbeat alone cannot prove the queue drained. The cut and mutations arriving during inventory require an actual owned race test.

Known parent membership is necessary but insufficient: a parent may have moved outside the root after the event was queued. Before exporting a name or probing metadata, resolve its cached relative ancestry from the pinned root with BENEATH/NO_SYMLINKS/NO_XDEV and compare directory handle identity. A missing or changed parent produces a gap/reconciliation, never an outside handle lookup. Contained pathname resolution is still subject to concurrent ancestor moves; reused open descriptors can refer to moved-out directories. The implementation must prove the containment invariant under adversarial moves using the existing monitor's checks or a stronger mechanism. Failure to prove it is a blocking rejection; cached membership alone is not a security proof.

Unknown parent records are discarded without external handle resolution. Events inside a newly admitted directory can therefore be missed until its inventory completes. Directory creation/move-in must trigger bounded contained inventory and explicit pending coverage; no fresh state until buffered/reconciled changes are accounted for. This must be qualified against child-before-parent queue order and event coalescing.

## Namespace cases

| Event | Required behavior |
|---|---|
| Create under admitted parent | Validate parent identity; preserve raw basename bytes; admit target directory identity before bounded subtree inventory. |
| File delete | Apply by admitted parent and cached entry identity; metadata lookup is unnecessary. |
| Rename within root | Validate old/new ancestry; preserve entry identity and update parent/name atomically; reconcile ambiguity or overwritten target. |
| Move out | Revoke the moved directory and descendant admission before subsequent export; remove namespace entries; never resolve outside destination. |
| Move in | Ignore outside old name; validate admitted destination; inventory subtree with pending coverage until reconciled. |
| Neither parent admitted | Drop record; export no identifier. |
| Hard link or replacement | Maintain directory-entry identity independently of object handle; never conflate aliases. |
| Root moved/replaced, mount changed, unmount | Invalidate root generation and report deferred; require root revalidation rather than following it. |
| Attribute/close-write without usable namespace identity | Reconcile bounded admitted scope; do not guess a path from a handle. |

Rename records can carry both old and new names: admission/filtering is per side. Never serialize an entire raw record merely because one side is admitted. Deleted handles and handle reuse/staleness need explicit tests. The event stream is not a durable filesystem journal.

## Transport, failure and resources

Private owner-only Unix endpoints authenticate credentials and an explicit session/root generation. Startup requests cannot choose arbitrary roots or marks. Use versioned bounded framing, raw-byte names, monotonically increasing sequence, source observation time and bounded message size. Never pass the raw fanotify descriptor to the query service or frontend. Keep source-progress lease, startup drain barrier, gap reporting, catalog sequence checks and cleanup/quarantine semantics from the current M3 candidate.

Bound kernel queue, user queue, directory map, inventory work, event export rate and reconciliation attempts. FAN_Q_OVERFLOW, malformed/truncated records, unsupported information types, queue exhaustion, broker death, lease expiry or receiver backpressure immediately invalidates freshness. Cached queries remain available with honest deferred coverage. Restart only after proving the previous owned tree and descriptors are gone; no automatic privileged restart loop. Unrelated filesystem churn can overwhelm a filesystem-wide queue even when all records are dropped, so this is an explicit rejection/stress case.

Charge launcher, broker, kernel queue/marks, handle map, updater, query catalog, supervisors, retained readers, bootstrap buffers and builders to the same aggregate accounting. No source-specific memory allowance is accepted in advance. Current packed-catalog evidence leaves limited headroom; constant mark count does not prove the 600 MiB target. Use bounded cgroup measurements including kernel/file charges and zero swap. No global cache drops, sysctl increases, artificial host pressure, or outsourcing charges to another cgroup.

## Qualification order and next packet

1. Implement unprivileged parser/filter/state-machine fixtures using synthetic binary fanotify records. Test malformed lengths, unknown types, raw names, dual-sided renames, identity reuse, queue limits, source lease and explicit gaps. This packet can run without creating a fanotify group or granting privilege.
2. Prepare the concrete launcher/broker source, service configuration and rollback diff. Review exact capabilities, descriptor-transfer ownership, root configuration, observation filesystem and confinement limitations. This is preparation, not activation.
3. Obtain explicit authorization for one bounded privileged owned-fixture run with the exact observation scope stated. Include inside/outside siblings, adversarial ancestry moves, overflow/backpressure, kernel feature failures, privilege drop, process reap and queue/map memory. No real workspace activation in this gate.
4. Only after correctness/confinement passes, qualify directory scales and combined memory/freshness under the frozen limits. Preserve failures. Actual filesystem events are required; parser fixtures cannot establish delivery or freshness.
5. Continue M4 durable recovery, M5 current-count aggregate acceptance and 24-hour synthetic soak, then separately approved M6 reversible installation and 72-hour installed soak. No shortened soak substitutes.

Terminal condition of the next source packet: parser/filter fixtures pass or record a specific design rejection, with no privileged effects and no real-root inventory. Expected writes are broker/parser source and owned tests plus this packet's evidence. Work remains on feat/incremental-generations; default-branch integration and installation are separate gates. Original goal controls persist; do not reset the three-hour/two-million-token bounds.

## Rollback and proposed eventual approval surface

Before any activation, provide exact executable hashes, launcher privilege mechanism, service units, root/mount/filesystem identity, queue/map limits, cgroup limits, install paths and stop/disable commands. Rollback closes the sole notification descriptor, proves the mark and owned process tree are gone, removes only the new owned units/capability grants, and returns to the existing snapshot query runtime. Retain accepted snapshots and evidence. Privileged setup failure cannot alter installed query serving.

## Primary API references

- [fanotify_init(2)](https://man7.org/linux/man-pages/man2/fanotify_init.2.html): group classes, handle-reporting combinations and unprivileged restrictions.
- [fanotify_mark(2)](https://man7.org/linux/man-pages/man2/fanotify_mark.2.html): filesystem mark scope and capability requirements.
- [fanotify(7)](https://man7.org/linux/man-pages/man7/fanotify.7.html): record format, rename information, coalescing and overflow behavior.

This is a proposed design. Privilege-transfer, confinement, kernel compatibility and combined resource claims remain unproved.

## Current contract amendment —2026-10-09

Operator clarification2026-10-09: bounded metadata reads through a descriptor opened and validated while in the approved root remain acceptable if the directory moves out during that operation. Validate before and after, discard affected output, stop/report a gap, and do not follow the outside destination or probe/export/log outside names. This exception covers formerly admitted objects only; it does not admit initially outside paths/handles, file-content reads, new roots or broader observation. Kernel development is explicitly out of scope. Resource/freshness/soak gates are unchanged.

The original strict read-time wording above is historical and superseded only for this transition. BRK-CONF-001 is not an activation blocker under the clarified boundary. No custom-kernel work is authorized or needed for this accepted contract. Remaining privileged-observation and installation gates remain in effect.
