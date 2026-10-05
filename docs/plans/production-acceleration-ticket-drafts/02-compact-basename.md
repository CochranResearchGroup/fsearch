# Serve selective basename queries through compact native candidates

## What to build

Selective filename queries return exact ordered results through the CLI and warm socket while staying within approved aggregate memory and latency gates.

## Acceptance criteria

- [ ] Candidate selection is a proven superset; exact matching and typed filters remain authoritative.
- [ ] Compact representation qualifies on repetitive and high-entropy one-million-name fixtures without relaxing approved caps.
- [ ] Index construction enforces an explicit byte budget before growing allocations and safely falls back or selects another representation when a corpus exceeds it. A failed 64-entry block-posting varied-filename fixture is retained as a regression corpus.
- [ ] Common-query handling avoids eager materialization of all matches.
- [ ] Direct and resident paths share selection logic and preserve byte/result/work diagnostics.
- [ ] Real worker startup, deadlines and cancellation remain bounded.

## Blocked by

Ticket 1: Unicode lifetime repair.
