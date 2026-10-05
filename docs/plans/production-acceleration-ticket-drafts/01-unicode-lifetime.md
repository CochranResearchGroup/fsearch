# Keep repeated Unicode queries within resident worker memory bounds

## What to build

Repeated literal Unicode queries keep the same resident worker and identical results without accumulating filename copies.

## Acceptance criteria

- [ ] The actual socket regression goes red on the existing leak and green on the repair.
- [ ] A 100,000-name workload with 100 warmed Unicode queries completes on one worker with bounded memory growth.
- [ ] Existing direct CLI, service lifecycle and upstream tests pass.
- [ ] Source repair and installed identity remain explicitly separate until qualified installation.

## Blocked by

None for the local repair; preserve existing service integration authority.
