# Work through the continuous-service tickets

State: PLANNED
Owner: Codex
Parent: [Plan0006](0006-2026-10-08-incremental-service.md)
Inputs: [specification](../../specs/0004-continuous-filename-service.md) and [ticket breakdown](../../plans/0004-continuous-service-ticket-breakdown.md)
Scope: execute the four delivery outcomes without changing Plan0006 acceptance gates.

## Current State

Catalog/query source and broker parser/bootstrap fixtures exist. An assembled broker, actual source qualification, durable recovery, combined resource acceptance and installed adoption remain unfinished. Ticket drafts are checked in; approval and tracker publication remain recorded separately. This execution guide does not grant privileged activation or installation.

## Working sequence

1. **Assemble the candidate — ticket01.** Connect the event reader, private descriptor transport, broker, updater and catalog. Exercise the complete path through normal CLI and fresh MCP clients on owned fixtures. Include startup, moves, inventory, overflow, stalls and cleanup. Prepare the concrete launcher, privileges and rollback. Checkpoint when the runnable candidate and its review packet are ready, rather than after individual component tests.
2. **Prove the actual event source — ticket02, after01.** Present the exact observation/capability request before activation. Once explicitly authorized, qualify actual delivery, privilege drop and containment on owned roots. Test outside-root churn and adversarial moves. Checkpoint with separate delivery, correctness, confinement and freshness verdicts; any failed gate stays open.
3. **Make it durable and qualify resources — ticket03, after02 for acceptance.** Implement checkpoint/replay and crash recovery; durability source preparation may start after01. Then advance through100k,~300k,1m,~3m,exact current count and10m under frozen workloads. Prove all query/freshness gates together with600MiBsteady and1.25GiBupdate limits, then complete the24-hour synthetic soak. Keep M4 durability and M5 resource verdicts separate. Checkpoint with the qualified install/rollback candidate.
4. **Adopt and prove installed reliability — ticket04, after03.** Follow operator-directed reversible installation. Verify exact installed identities and fresh CLI/MCP behavior, stop/start, failure handling, rollback and process cleanup. Complete the72-hour installed soak. Publish final evidence and audit every Plan0006 gate before program closure.

## Work rhythm and stop rules

- One substantive ticket at a time, owned by Codex, on the existing integration lane. Supporting frontend preparation can proceed independently when its contract is stable; it cannot bypass dependencies.
- At session start, read the ticket and latest receipt; verify branch, dirty work, applicable authority, goal controls and host pressure. Continue from the first unmet criterion without rerunning accepted experiments for context.
- Work through implementation, relevant tests and Standards/Spec review within the ticket. Commit coherent changes along the way. Keep progress updates frequent; user-facing checkpoints are the outcomes above or verified hard stops.
- Before each experiment freeze workload, time/resource limits, stop predicates and evidence location. Stop owned work on pressure, budget, confinement or correctness failure; preserve the accepted serving generation and failure receipts. Never raise caps or hide kernel charges to obtain a pass.
- At each checkpoint publish exact source/build identity, tests and raw receipts, current ticket state, installed-effect status and one concrete next action. Prove cleanup with fresh process/resource readback when processes ran. Keep unrelated work intact.
- Root expansion, filesystem-wide privileged observation and installation retain their explicit effect gates. No whole-drive scan, shortened soak or runtime change is implied by this plan. Preserve any active goal limits; do not silently reset them between tickets.

## Completion

This execution guide is complete only when all four outcomes have their required evidence and Plan0006's independent M1–M6 audit passes. Documentation, tracker labels, parser fixtures and staged executables alone are insufficient. Keep parent issues open until their own completion evidence is verified.
