# Qualify the accelerated real worker/socket and prepare reversible installation

## What to build

The actual accelerated service is validated against frozen correctness, performance, lifecycle and resource gates, then packaged for reversible installation.

## Acceptance criteria

- [ ] At least 100 warm samples per designated query report socket p50/p95/p99 and pass approved gates.
- [ ] Peak/aggregate memory, startup and worker identity are read back directly.
- [ ] Fault, malformed-input, queue, cancellation, crash and quarantine regressions pass.
- [ ] All-process traces prove zero indexed-root query probes.
- [ ] Standards and Spec reviews use the operator-approved fixed point; findings are adjudicated.
- [ ] Installed qualification, rollback and remaining refresh/monitoring/replacement/MCP boundaries are documented truthfully.

## Blocked by

Tickets 1, 2 and 3.
