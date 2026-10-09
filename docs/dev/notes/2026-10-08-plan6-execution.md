# Plan 0006 execution checkpoint

Status: IN_PROGRESS. Parent #26, active M1 #27.
Goal execution started 2026-10-09T01:34:28Z (operator local date 2026-10-08).
Operator stop limit: before 3 hours or 2,000,000 tokens. Checkpoint deadline reserved at 2026-10-09T04:19:28Z, 15 minutes before the time limit. Check token accounting at each milestone; stop with a restart-safe checkpoint before either limit.

Current implementation: /tmp/fsearch-incremental-generations, feat/incremental-generations, based on master 2f313c82. No prototype branch merged. Native catalog code and lifecycle tests are real source, but not connected to production serving yet. Installed service is unchanged. Full plan remains open; the 24-hour synthetic and 72-hour installed soaks cannot be completed within this execution window.

Pressure policy for owned experiments: MemoryMax=1.25 GiB, MemorySwapMax=0, CPUQuota=150%, Nice=10, IOWeight=10 in isolated transient user cgroups. Guard samples host memory/I/O PSI and owned descendants every 200 ms; denies launch below 8 GiB available or memory-full avg10 >2% or I/O-full avg10 >15%. Sustained violations for 10 seconds stop the owned workload. Record exact cgroup memory.peak and swap.peak in addition to sampled RSS/PSS. Do not change unrelated workloads or installed limits.

First run suite: 22 native groups pass, including generation lifetime/churn tests and injected allocation/corruption failures. The first regression launch failed because systemd PATH lacked uvx; a subsequent incorrect guessed uvx path also failed before tests. Both are retained as runner failures, not test passes. Correct absolute executable /home/linuxbrew/.linuxbrew/bin/uvx was verified before the successful run.

Next work: finish staged M1 resource and sanitizer checks; qualify full native matching/order across generation transitions, then integrate the catalog/query engine for M2. No milestone accepted yet.
