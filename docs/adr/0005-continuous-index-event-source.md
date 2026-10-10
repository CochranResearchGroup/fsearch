# ADR0005: event-source retention is part of the memory budget

Status: PROPOSED implementation; operator selected the 600 MiB broker-design direction on 2026-10-09
Date: 2026-10-08
Scope: Plan0006 M3; approved workspace only

## Evidence and problem

The packed catalog is insufficient to qualify an always-warm service: every inotify directory mark can retain kernel metadata. The accepted600MiB steady envelope includes these charges, along with the query process, updater and retained generations.

Owned measurements under the unchanged1280MiB/no-swap cgroup:

| Directories | Watch admission | Charged after bounded reclaim | Kernel | Anonymous |
|---|---|---|---|---|
| 10000 | 0.299s | 28.07MiB | 12.77MiB | 14.98MiB |
| 100000 | 3.855s | 149.19MiB | 125.02MiB | 23.88MiB |
| 300000 | 8.256s | 702.02MiB | 422.39MiB | 45.94MiB |
| 618761 | FAILED60s startup bound | no steady observation | not qualified | not qualified |

The300k total includes233.55MiB file cache left after the bounded512MiB reclaim request. Reclaim returned EAGAIN despite reducing charges; do not call that total an irreducible minimum. Kernel plus anonymous charges nevertheless already consume468.33MiB at less than half the current directory count. The exact-count run reached the1280MiB cap and failed its watch-admission deadline. All owned trees/processes were cleaned, failures retained and no real root scanned.

This is strong evidence against the proposed inotify architecture under the accepted combined budget; it is not an exact current-workspace aggregate measurement or proof of a universal impossibility. Reducing userspace watch-path strings alone does not remove the dominant observed kernel charges. The current production candidate remains unqualified.

## Alternatives and authority

1. Preserve600MiB and investigate an event source without one pinned inode per directory. A narrowly bounded privileged broker is a candidate, not an accepted implementation. Its design must specify the event observation scope, filtering before any export or secondary metadata probe, root and mount identity, capability lifetime, private authenticated transport, overflow detection, process/resource limits and rollback. Linux filesystem-wide fanotify marks require CAP_SYS_ADMIN and observe the filesystem rather than merely the approved subtree. That is a new security/observation boundary; existing workspace-indexing authority does not grant it. Do not grant capabilities, run sudo, install a privileged helper or activate wider observation without explicit operator direction.
2. Keep a wholly unprivileged pinned-watch source and propose a measured higher aggregate budget. This requires an explicit operator rebaseline; do not silently raise the accepted caps or mark the existing targets passed. Current evidence does not establish the replacement budget.
3. Unprivileged evictable fanotify inode marks can release pinned inodes, but eviction also loses their marks. They are unsuitable unless actual loss is reliably exposed and the full freshness contract is retained. An owned pinned/evictable positive-control experiment is recorded separately. Silent loss is a rejection, not an optimization.

Polling, narrowing the workspace, omitting kernel charges and reporting cached results as fresh are not substitutes for the approved destination.

## Next gate

The operator accepted recommendation 1 on 2026-10-09: preserve600MiB and prepare the privileged-broker design for review. The [review packet](../dev/notes/2026-10-09-plan6-broker-design.md) records observation scope, authority, filtering, unresolved confinement/descriptor-transfer questions, resources and rollback. The constraint-choice blocker is resolved for design/source preparation; privileged execution and broader observation remain unauthorized. Next is the unprivileged parser/filter fixture packet. M3 acceptance remains open; do not install the partial updater.

## Primary references

- [Linux fanotify_init restrictions](https://man7.org/linux/man-pages/man2/fanotify_init.2.html): unprivileged groups cannot use mount/filesystem marks.
- [Linux fanotify_mark semantics](https://man7.org/linux/man-pages/man2/fanotify_mark.2.html): FAN_MARK_EVICTABLE permits inode eviction and loses the mark; FAN_EVENT_ON_CHILD is not recursive; filesystem marks require CAP_SYS_ADMIN.
- [Owned raw resource receipts](../dev/notes/plan6-evidence/) and [M3 checkpoint](../dev/notes/2026-10-08-plan6-m3-ingestion.md).

## Operator containment clarification —2026-10-09

Operator clarification2026-10-09: bounded metadata reads through a descriptor opened and validated while in the approved root remain acceptable if the directory moves out during that operation. Validate before and after, discard affected output, stop/report a gap, and do not follow the outside destination or probe/export/log outside names. This exception covers formerly admitted objects only; it does not admit initially outside paths/handles, file-content reads, new roots or broader observation. Kernel development is explicitly out of scope. Resource/freshness/soak gates are unchanged.

BRK-CONF-001 is accepted as a bounded transition under this clarified contract; retain the original strict-criterion failure and diagnostic. It is no longer a contract blocker. Real fanotify delivery, privilege lifetime, filtering, resources and installed acceptance remain unqualified. Capability grants, privileged fixtures, filesystem-wide marks and installation still require a concrete separately authorized activation packet.
