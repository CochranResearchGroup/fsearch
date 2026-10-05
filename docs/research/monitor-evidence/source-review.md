# Contained monitoring source review

Frozen source: 10170cfe7848754bd5c68a49685d62ff17f2308e. Baseline: 35061a31 (committed monitor contract, before implementation).
Diff: `git diff 35061a31...10170cfe -- src`.
Review performed serially against AGENTS.md, CONTRIBUTING.md, codex-stack.md, runtime-proof.md, issue #4 (issue-4-review.json), Plan 0004 and spec 0003.

## Standards

- nonblocking_backlog: watch and refresh workers duplicate confinement/traversal contracts. This repair changes both together and tests both; a shared native admission helper would reduce future drift.
- nonblocking_backlog: Watcher inherits unused candidate-building operations from Refresh, and replacement adapts a command namespace to the existing client. A smaller shared process-lifecycle boundary would make those dependencies clearer. Current reuse preserves the established identity/gate/cleanup and private-client contract.
- nonblocking_backlog: duplicate _GNU_SOURCE definitions in native workers produce compiler warnings, consistent with an existing refresh-worker warning. No documented hard violation was found.

## Spec

- blocking, resolved: moving an admitted parent directory outside the root allowed new descendant opens through its pinned descriptor. Both workers reproduced the gap in owned all-process traces. Every descendant now resolves a complete relative path from the approved root FD; directory re-opens compare inode/device identity. Repaired traces and public monitor/refresh races prove refusal and accepted-byte preservation. Landlock alone is not claimed to mediate metadata.
- blocking, resolved: a second shutdown signal could interrupt reap/quarantine recording. Both monitor-owned lifecycle classes now mask shutdown signals during cleanup; the uncertain-cleanup fixture sends a second signal after the owned child is killed and still observes cleanup_unproved plus durable quarantine.
- resolved: monitor messages now include reasons and known root/snapshot context, and oversized roots fail before admission.
- Source evidence: 19 targets pass, including 20 supervisor tests, 10 native worker tests and the registered move-race target. Watch setup, mutation during refresh, nested changes, overflow, offline state, failed worker, serialization, quarantine/recovery, shutdown, resource ceilings and warm acknowledgement identity are covered. Independent query/client traces during monitoring and after root removal contain no indexed-root probes, with a detected negative control.
- needs_evidence: versioned installed monitor acceptance, installed query isolation/move race and fresh process/resource readback precede adoption acceptance. No production root or default activation is authorized by these fixtures.

Summary: Standards has three nonblocking backlog findings; Spec has two resolved blockers and one installed-evidence gate. The wider MCP/publication program remains open.
