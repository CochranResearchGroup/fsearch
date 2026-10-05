# Tracker acceptance map

Owner: ecochran76. State: prepared; exact-head CI/main custody still required.
Native publication: PR #14. File-searcher integration: PR #21, merged at
19acc4b02a01c0893568da9012b7acd9e955f81a. This map does not close tickets itself.

| Issue | Qualified outcome and current evidence |
|---|---|
| #2 | Versioned bounded private snapshot CLI, typed matching/filters, byte paths, cached freshness, no root probes, lifecycle/fault bounds. cli-acceptance.md and installed 15 CLI cases in monitor-install-acceptance. Cold/warm scope in cli-benchmark-plan and cli-evidence/benchmark.json. |
| #3 | Explicit root admission, openat2/Landlock boundary, failed/interrupted publication preservation, serialized quarantine/recovery and repaired moved-parent race. Plan 0004, refresh-install-acceptance, installed 12 refresh cases and monitor-evidence/installed/move-race. |
| #4 | Contained watch generations, nested changes, overflow/offline/failure, serialized refresh, shutdown/recovery and no query root probes. Spec 0003-contained-monitoring, monitor-install-acceptance, installed 20 supervisor/10 worker cases. CI private-state fixture corrected without weakening production. |
| #6/#7 | Private resident service, bounded queue/frames/resources, cancellation and durable quarantine/recovery. warm-service spec/ADR, service-acceptance, installed 34 service cases and three-corpus performance qualification. |
| #8 | Accepted identity replacement, at most two workers, old-result preservation, no root scans, bounded overlap and uncertain-retirement quarantine. Plan 0004, installed service cases and three installed replacement-overlap receipts. |
| #9-#13 | Approved native acceleration, Unicode lifetime repair, compact candidate/oracle parity, short/Unicode/path semantics, actual socket latency/resource qualification, fault/isolation and reversible installation. production-acceleration spec, production-install-acceptance and refresh-evidence/column-prefetch-installed/performance-qualification.json. Existing checked criteria remain; main custody pending. |
| file-searcher #20 | Optional explicit FSearch config, existing find/lookup contract, cached preparation/byte identity, faults with SQLite fallback, actual packaged/installed MCP, syscall control, 426-case suite and passing PR #21 CI. file-searcher notes fsearch-mcp-review and installed-identity. Native dependency publication still pending. |
| #5 | Packaged native/MCP and reversible runtime qualification exists. Production storage/root admission and default activation are separately undirected; no synthetic benchmark grants that authority. Keep wider adoption item open with this boundary and a concrete next decision. |
| #1 | Parent's implementation sequence is locally qualified; publication/tracker custody in progress. Keep the broader parent open while #5 adoption remains undirected. |

Verification on 2026-10-04: all seven installed native commands match exact
10170cfe artifact hashes and symlink targets; 28 installed/performance evidence
files match their recorded digests. Query CLI/worker/service hashes equal the
three-corpus performance-qualified artifacts. Fresh publication requalification
passes 19 targets; explicit 022-umask corrected monitor fixture passes 20 cases.
Synthetic workload evidence does not qualify the operator's actual storage.

Memory disposition: forbidden; no personal memory write authorized.
