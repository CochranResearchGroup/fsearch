# Proposed production acceleration tickets

Status: APPROVED on 2026-10-04; operator said “ok go” to the concrete three-decision summary. Spec: ../specs/0003-production-filename-acceleration.md. Approved review baseline: 5ec26bab. User authorization to plan/execute is recorded; Publication is now authorized under to-tickets.

1. **Keep repeated Unicode queries within resident worker memory bounds**
   - Blocked by: none for the local source repair; integration depends on existing CLI/service seams.
   - Delivers: exact repeated Unicode responses from the same worker without per-entry allocation growth, verified through the real socket and original 100k workload.
   - Current evidence: actual socket red/green regression and all 15 Meson targets pass. Source repair complete locally; no installation.
2. **Serve selective basename queries through compact native candidates**
   - Blocked by: ticket 1.
   - Delivers: identical ordered CLI/socket results with measured lower candidate work and aggregate memory at one million names; shared direct/resident core and retained lifecycle faults.
3. **Accelerate short, Unicode and path queries without semantic loss**
   - Blocked by: ticket 2.
   - Delivers: arbitrary substring semantics, normalization/case behavior and parent-path matches meet the approved workload targets, or explicitly fail the qualification gate; bounded incomplete responses remain truthful.
4. **Qualify the accelerated real worker/socket and prepare reversible installation**
   - Blocked by: tickets 1–3.
   - Delivers: frozen performance/resource gate receipt, full regression/isolation results, two-axis review from approved baseline and concrete versioned installation/rollback package. Installation follows qualification. Existing refresh/monitoring/replacement/MCP tickets remain distinct.

Draft issue bodies are in production-acceleration-ticket-drafts/. Do not modify or close existing parent issues when publishing this breakdown. Publish native blocking links under the recorded operator approval, then implement the ready frontier on one integration branch.

## Published tracker readback

Spec: https://github.com/CochranResearchGroup/fsearch/issues/9

- Ticket 1: https://github.com/CochranResearchGroup/fsearch/issues/10
- Ticket 2: https://github.com/CochranResearchGroup/fsearch/issues/11
- Ticket 3: https://github.com/CochranResearchGroup/fsearch/issues/12
- Ticket 4: https://github.com/CochranResearchGroup/fsearch/issues/13

Native blocked-by edges verified: #11 → #10; #12 → #11; #13 → #10, #11, #12. Existing parents were not modified.
