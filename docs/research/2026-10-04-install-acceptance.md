# Local installation acceptance — 2026-10-04

The user explicitly authorized commit and installation. Source commit `7e3a7f1b9d7ea7b2bd1ff8d0bd112bb93864ea6e` on `feature/7-warm-local-service` includes the bounded CLI, resident worker, supervisor and prior source qualification. This installation is local; the branch has not been pushed or merged.

The release build at `/tmp/fsearch-warm-release-build` was built with `/usr/bin/gcc` using Meson release optimization. Its three installed artifacts match the hashes in the prior source qualification exactly. The full source suite previously passed 15 targets; direct installed verification uses only owned synthetic snapshots and the non-installed fixture/fault helpers.

The installed commands are `~/.local/bin/fsearch-cli`, `fsearch-worker`, and `fsearch-service`, symlinked to `~/.local/share/fsearch/runtimes/7e3a7f1b9d7ea7b2bd1ff8d0bd112bb93864ea6e/bin`. The sibling layout preserves cold startup and worker resolution. The manifest records exact SHA-256 values. Installation storage was read back as native ext4 (`/dev/sdd`). No existing command was overwritten.

Installed CLI tests passed all 15 cases. The initial installed service run exposed a harness cleanup race: stop acknowledges before final state writes finish, and temporary-directory deletion raced those writes. The original failed receipt is retained. The harness now performs a bounded waitpid reap of the owned supervisor before deleting its fixture directory. The corrected installed service run and process census are retained under `install-evidence/`.

The service starts on demand from an explicit private snapshot and socket. No production snapshot, user MCP registration, GUI installation, systemd unit, or real-root indexing was added. Safe refresh (#3), monitoring (#4), replacement (#8), and file-searcher MCP integration (#20) remain open. This is installed query-serving acceptance, not full adoption.

Rollback: remove the three `~/.local/bin/fsearch-*` symlinks after stopping any explicitly started instance; the versioned runtime can remain for inspection. No pre-existing binaries were replaced.

Memory disposition: forbidden; durable personal memory writes require explicit user authorization, which was not given. A machine-readable non-write receipt accompanies this acceptance.
