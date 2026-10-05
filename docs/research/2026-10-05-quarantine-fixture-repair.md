# Resident-query quarantine fixture repair

Owner: ecochran76. Existing issue #7 reopened for master CI run 37330650927.
Baseline: 83ece70022347d58c6b1628bbd87cbdbf9553aa7.

The uncertain-cleanup fixture sent its first request with a 50ms deadline after
only proving socket existence. The worker is lazy: on slower startup that request
can expire while queued, before active-query cleanup, correctly returning deadline.
A 250ms injected snapshot-load delay reproduces that red result against the exact
installed service. This is a test precondition failure, not evidence that quarantine
was bypassed by the service.

The fixture now proves a completed warm query and resident worker identity before
arming a separate delayed-query fault. It then asserts cleanup_unproved, durable
quarantine for that same worker, refused requests/restart, proved eventual reap
and explicit recovery. The fault adapter separates its one-shot load/query markers
and accepts an owned query-arm file; it is never installed. Worker absence is
observed within a bounded deadline after releasing the injected reap block, rather
than assumed after a fixed 150ms sleep. No production deadline or quarantine gate
is changed, and no runtime installation is needed for these test-only edits.

Evidence: quarantine-lazy-load-red.txt reproduces queue expiry; the first warmup
attempt consumed the adapter's shared one-shot marker (quarantine-warmup-first.txt),
so distinct fault-stage markers were added. quarantine-lazy-load-green.txt proves
the repaired public case against installed source eda902627bc96e626887b06f69f66bc3c43499e3.
All 34 service cases pass with the revised adapter (quarantine-armed-service-suite.txt). Full source/CI proof remains required before re-closing #7 and final plan closure.
User production-root selection remains pending; production indexing stays disabled.

Memory disposition: forbidden; no personal memory write authorized.
