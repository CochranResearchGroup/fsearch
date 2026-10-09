# Native candidate selection and sorted overlay merge

State: CLOSED
Issue: https://github.com/CochranResearchGroup/fsearch/issues/25
Baseline: 9002f969ff6d67bca2b3ce110584c9cc1e86b0d5

Owned synthetic events only. Extract the existing native signature helpers without changing their behavior; use them for immutable base bitplanes and exact-match the bounded delta separately. Merge files then folders in native basename comparator order. Suppress shadowed/deleted identities and descendants, preserve path fallback. Native comparator has no tie-break for equal basenames: qualify sorted groups, record exact-order discrepancies rather than inventing an API guarantee. Check full result sets and limited prefixes outside ambiguous ties.

128-file correctness matrix, ancestor moves/deletion, Unicode/raw bytes, duplicate basenames, signature false positives, short/empty literals, filter modes and budget deferral. Run existing native tests for the shared-helper refactor. 100k then 1m only if 100k <200 MiB worker peak and <30 seconds; timeout 60 seconds and worker address-space cap 1 GiB. Record builder/startup cost separately. No installation, real watcher, compaction, live root scan or production aggregate-memory claim. Capture prototype branch outside master, tracker and one memory disposition.

Outcome: 4,536 result/comparator-group comparisons, 81 bounded prefixes and all 20 native test groups pass. Gated 1m run completed. See docs/research/2026-10-08-native-overlay-merge.md. Next: bounded compaction and concurrent view publication under synthetic events.
