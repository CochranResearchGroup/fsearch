# Warm service qualification gates — frozen before measurement

Build: optimized Meson release; source fixture only. Native owned temporary roots at 10,000 and 100,000 flat filenames, exact ten-hit and completed zero-hit queries. No real-root indexing or runtime installation.

Thirty subsequent Unix-socket requests after first query: p95 <= 5 ms at 10,000 and <= 30 ms at 100,000. CLI-client fresh-process latency is reported separately, not substituted for socket latency. Loaded supervisor+worker summed RSS <= 128 MiB at 100,000. During a six-second idle period, combined CPU <= 0.25 seconds, no worker-count growth, and zero indexed-root file syscalls after removing the fixture root. Cancellation/deadline and shutdown must reap owned workers; synthetic unproved reaping must quarantine with no replacement across restart.

Queue: one active and at most eight waiting requests, deadlines include queue waiting. Supervisor soft address-space ceiling 64 MiB, worker ceiling 256 MiB; maximum 16 live client connections and bounded frames/outputs. No default-adoption or installed-service claim follows from passing.
