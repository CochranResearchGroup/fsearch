# Previous-boot startup recovery

Owner: ecochran76. State: CLOSED. Issue: #18. Parent: #5.

## Scope

Restore reliable approved query/monitor login startup after an unclosed prior Linux boot. Source surfaces: shared lifecycle reconciliation, service/monitor synthetic tests, installed qualification. No disk repair, elevated permissions, new roots, forced state deletion, same-boot recovery relaxation, or automatic retries.

## Acceptance

Prior-boot automatic recovery requires canonical valid identities for every recorded worker, candidate, retiring worker and supervisor, all from a verified different boot. Mixed/current/unknown/malformed records remain quarantined. Keep snapshot identity and metadata. Prove query and monitor startup through synthetic public seams; run existing containment tests. Publish tested source, qualify package identity, preserve rollback and verify installed CLI/MCP plus normal startup behavior without rebooting the host.

## Current State

Baseline origin/master c7b82eadcc8914362c75c5032cb3a2ae17296f42. Worktree /tmp/fsearch-boot-recovery-20261007, branch fix/18-previous-boot. Actual WSL restart caused both query units to reject prior-boot ready state; scoped built-in recovery restored all four units and cached README queries. Prior state evidence is preserved privately. Synthetic red reproducer confirms reconcile rejects a valid previous-boot ready generation with quarantined. Shared lifecycle implementation and three focused regression tests now pass (phase matrix plus current/mixed/malformed/unknown refusal). Public query/monitor startup, existing containment suite, publication and installed qualification remain.

## Execution

One serialized lifecycle change: add validated previous-boot recovery; add positive/negative regression coverage; run contained fixture suite; publish and qualify installed artifacts before changing production identity. Existing storage-health administrator gate remains independent under #5.

## Qualification findings

Direct-compiler two-job build succeeded; compiler-cache build stalled before compilation and was stopped with owned process cleanup. Initial comprehensive lane: 19/20 groups passed; overflow fixture failed. Unchanged baseline lifecycle also failed overflow snapshot preservation, proving pre-existing fixture timing sensitivity. Deterministic scanner delay and terminal deadline repair retain eight-overflow, failure-exit and byte-identical snapshot assertions. Corrected baseline overflow test passes. Public previous-boot query/monitor startup tests pass; corrected comprehensive lane passes all 20/20 Meson groups (serial, no exclusions). Original failure receipts retained privately under /tmp/fsearch-boot-*.txt.

## Installed acceptance

Source PR #19 and both CI checkpoints passed; versioned installed package and public/production-shaped prior-boot startup accepted. See [installed acceptance](../../research/2026-10-07-installed-boot-recovery.md). Documentation publication completes custody; physical storage remains #5.
