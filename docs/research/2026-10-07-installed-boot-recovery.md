# Installed previous-boot recovery acceptance

Owner: ecochran76. Issue: #18. Parent: #5. Accepted source and installed startup recovery; physical storage health remains open.

An unclosed WSL restart at 10:54:46 CDT on 2026-10-07 left ready-state worker records from the previous kernel. Both query units rejected startup as quarantined at 10:55:10. Built-in explicit recovery restored service; original records are preserved privately. The shared lifecycle now automatically recovers only canonical identities for all recorded workers and supervisor from one verified previous boot. Current/mixed/missing/malformed/unknown evidence remains quarantined. Exclusive locking and snapshot metadata preservation remain.

PR #19 reviewed source 7317390ed5da4928c295049887e4eb629ca1c06d merged into master 22854e80bcea87e34f5a101be15619e74ec68663. Exact-head CI 37654309779 and post-merge CI 37654500883 passed. Direct-compiler build used two jobs; complete Meson suite passed 20/20 groups serially. Initial compiler-cache stall and overflow test failures remain recorded in the plan. Unchanged lifecycle baseline reproduced overflow failure; deterministic fixture scanner delay and bounded terminal observation retain eight overflows, failure exit and byte-identical snapshot assertions.

Versioned installed runtime: ~/.local/share/fsearch/runtimes/7317390ed5da4928c295049887e4eb629ca1c06d. Prior qualified C binaries retained byte-for-byte after native production-source diff and manifest-hash checks; service script equals exact reviewed git source, unchanged monitor/refresh scripts also match. Packaged service suite passed 35 tests; monitor suite passed 21. Synthetic public startup tests cover query and monitor. Copies of both actual saved pre-restart query states were replayed in private temporary directories against copied snapshots: automatic startup succeeded, README queries returned 2/1 hits and worker absence was verified after teardown. Production state files were not fabricated to simulate a boot. No host reboot was performed.

Four approved query/monitor units select the new runtime; seven native launchers, normal config fsearch_command and both readiness scripts also select it. Original source runtime, snapshots, enabled status, result ceilings and disabled automatic restart policy remain. All four units were active, zero automatic restarts; native queries, normal fsr and fresh stored-registration MCP returned both approved roots. Root scope remains exactly file-searcher + fsearch.

Scoped rollback was prepared before changes under ~/.local/share/fsearch/operations/boot-install-20261007 (0700, sensitive files 0600). It checks unit/link/routing hashes before restoring prior units, links, configuration and readiness scripts. It preserves snapshots and unrelated settings. Backups, manifest and production-shaped-startup.json are retained privately. Rollback is prepared, not executed.

No physical-drive repair, privilege bypass, broader indexing or endurance/reboot claim. Windows reliability counters remain denied; HDD retries and WSL backing NVMe controller errors are separately tracked under #5.

Memory disposition: forbidden; personal-memory writes unauthorized.
