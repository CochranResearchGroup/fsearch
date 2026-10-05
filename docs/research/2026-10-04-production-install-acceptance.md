# Installed production acceleration acceptance — 2026-10-04

Installed source: `f3e98fb06012ac8d250549d1cb0b491d93454c3e` on `feature/7-warm-local-service`. Source review compares the nonempty three-dot diff from `5ec26bab`; Standards and Spec each have zero accepted blocking findings. Source qualification includes all 15 Meson targets, three million-name corpora, 38 exhaustive-oracle CLI/socket comparisons and zero indexed-root file calls across traced CLI/supervisor/worker processes.

The three commands in `~/.local/bin` now resolve to `~/.local/share/fsearch/runtimes/f3e98fb06012ac8d250549d1cb0b491d93454c3e/bin`. Their hashes exactly match reviewed/measured build artifacts and the installation manifest. The previous `7e3a7f1b` runtime is preserved. Installation used the already authorized commit/install scope, without a user service, production snapshot, scan, mount admission or MCP configuration change.

Installed CLI acceptance passed all 15 tests; installed service acceptance passed all 25 tests. The independently launched installed million-name varied corpus passes the same gates: combined high-water RSS 128,284 KiB (limit 131,072), worst selective socket p95 9.04 ms, complete short 18.02 ms, Unicode 5.28 ms and complete path 13.46 ms. Worker identity remained stable across all warm queries. Each warm socket/native query has 100 samples; fresh CLI costs are separate. Broad result-limited timings remain excluded from completed-search acceptance.

The fresh process/resource census finds zero remaining FSearch processes after all owned tests terminate. This confirms test cleanup; it does not claim a continuously running production service. Commands start query service on demand from an explicitly supplied private snapshot/socket.

Rollback is explicit: after stopping any instance started from the new runtime, replace the three command symlinks with the corresponding `previous_links` targets in [installed-manifest.json](production-evidence/installed-manifest.json). The previous runtime remains intact, and neither versioned directory needs deletion. The installer also restores changed links if installation readback itself fails.

The local implementation and installed packet are complete. The branch has not been pushed or merged; tracker updates must say so. Safe refresh (#3), monitoring (#4), snapshot replacement (#8), and file-searcher MCP (#20) remain separate open scopes. This is fast cached query serving, not completed live indexing or universal Everything performance.

Memory disposition: forbidden. Durable personal memory writes require an explicit user request, which was not given; the closeout records a non-write receipt only.

The frozen qualification supplied to the installer is preserved as `production-evidence/installation-input-qualification.json`; its exact digest matches the installed manifest. This is separate from the qualification ledger subsequently updated with installed acceptance. The evidence-only commit adds no runtime source change. Raw compiler/test receipts retain original whitespace, while the hand-authored source and document whitespace check passes.
