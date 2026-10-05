# Contained approved-root monitoring

Implementation packet for CochranResearchGroup/fsearch #4, following installed refresh/replacement qualification. This packet admits only owned fixtures. Existing GUI monitoring remains independent.

## Lifecycle

Expose an optional `fsearch-monitor watch --root ABS --database ABS` supervisor. Root is explicit and immutable for the process lifetime; no GUI root import, ancestor watching, root reappearance polling, or watch requests supplied by events. Emit bounded JSON lines with schema_version, status, reason, approved root, and last accepted snapshot identity where known. Missing or relative roots fail before state creation. Use an owner-private lifecycle lock beside the snapshot and persist supervisor/worker identities before worker admission. A second supervisor is rejected. Restart reconciles old identities; uncertain cleanup is durable quarantine requiring explicit recovery, never an elapsed-time reset.

A separately bounded native watch worker installs inotify watches by the same trusted FD-relative, NO_SYMLINKS/NO_XDEV traversal as refresh. Kernel confinement is established before recursive traversal; unsupported confinement fails closed before root access. No file content reads. Cap depth at 64, entries at one million, and watches at 65536; a watch-admission failure reports incomplete coverage rather than claiming ready. Resource ceiling: supervisor 64 MiB soft address space, 256 MiB hard; native worker 256 MiB. The watcher does not construct query snapshots or change GUI flags.

One watch generation stops and closes all watches after the first relevant batch. Event names are never interpreted as paths. Report only dirty, overflow, or offline signals; do not retain watches on directories moved outside the approved tree. Moved/deleted watched roots invalidate coverage. Reconciliation re-enumerates only the original approved root. Unexpected worker exit is explicit failed-worker state with no silent retry. Blocking traversal/startup and refresh each have bounded supervisor deadlines; cleanup uncertainty quarantines further updates.

Establish recursive watches before the initial contained refresh. Keep the watch worker alive while refresh builds so events during construction mark the generation dirty; do not label that generation current. Coalesce changes within a bounded debounce window, with at most one admitted refresh. Re-arm then refresh after a dirty generation; never infer that an event-free unarmed gap is coverage. If continuous churn prevents a clean generation within the bounded reconciliation budget, report dirty/incomplete while retaining the accepted snapshot. Overflow requires full approved-root reconciliation, never an incremental replay claim.

Every refresh uses the existing fsearch-refresh admission, validation, atomic publication, deadline and quarantine protocol. Monitoring cannot recover refresh quarantine automatically. Accepted bytes survive offline roots, overflow, refresh failure and monitor restart. Query processes remain independent and never perform root metadata calls. Optional explicit service replacement uses the existing private acceptance contract only after publication; its failure does not relabel the old serving identity as current. Snapshot publication and warm replacement are distinct acknowledgements.

## Public acceptance matrix

- Missing/relative roots: structured invalid_request, no root access or lifecycle state creation.
- Create/rename/delete, including newly created nested directories: query a new accepted snapshot and preserve cached visibility/freshness fields.
- Watch installation race and mutation during refresh: dirty generation is not reported current; bounded reconciliation includes the mutation.
- Symlink, mount rejection and directory moved outside: all-process trace proves no target metadata/content traversal; no expanded approved root.
- Overflow and watch-budget exhaustion: explicit coverage failure, last accepted snapshot stays queryable.
- Offline root and failed worker: explicit terminal state, no root polling or unbounded restart.
- Existing refresh quarantine and simultaneous monitor/refresh admission: no bypass, serialized updates, preserved bytes.
- Supervisor termination and explicit restart/recovery: worker absence proved through current OS identities; uncertain cleanup remains quarantined.
- Removed indexed root while querying an accepted snapshot: all query-process file traces contain no root probes.
- Full upstream regressions, Standards/Spec review, installed CLI readback and process/resource census precede adoption.

No production root admission, default service activation, user MCP registration, or remote publication follows merely from source acceptance. Watching via inotify supplies Linux change notifications; it does not establish storage health or Everything-style journal indexing.
