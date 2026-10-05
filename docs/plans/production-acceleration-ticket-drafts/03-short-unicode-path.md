# Accelerate short, Unicode and path queries without semantic loss

## What to build

Short literals, Unicode normalization/case queries and parent-path matches preserve exact semantics while meeting the approved workload latency and memory targets.

## Acceptance criteria

- [ ] One/two-character searches remain arbitrary substring searches.
- [ ] Unicode and raw-byte handling preserve authoritative matcher behavior without false-negative candidates.
- [ ] Basename-only filtering cannot omit parent-path matches.
- [ ] Duplicate order, literal punctuation and typed filters agree with an exhaustive oracle.
- [ ] Measured fallback cases are visible; incomplete results never establish an empty search.

## Blocked by

Ticket 2: compact native candidate serving.
