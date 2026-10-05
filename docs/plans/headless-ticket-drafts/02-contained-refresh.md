# Refresh an approved root while preserving the last accepted snapshot

Published: https://github.com/CochranResearchGroup/fsearch/issues/3

Status: READY; owner: ecochran76; honor blocking dependencies.

## Parent

https://github.com/CochranResearchGroup/fsearch/issues/1

## What to build

An operator explicitly refreshes an approved root in a separate contained worker while queries continue using the last accepted snapshot.

## Acceptance criteria

- [ ] Select and document a confinement mechanism from primary-source evidence; filesystem-type/path-prefix checks alone are not claimed sufficient.
- [ ] Provider-free fixtures prove excluded mount/redirection paths are rejected before their first metadata operation.
- [ ] No implicit roots, user GUI configuration imports or whole-drive scans; Windows discovery remains with Everything.
- [ ] Publish only accepted snapshots atomically; failed or interrupted refresh leaves the previous snapshot searchable.
- [ ] Serialize updates and retain durable quarantine after unproved worker cleanup; no automatic replacement or receipt expiry.
- [ ] Failure and shutdown paths use injected adapters rather than real stalled mounts; upstream behavior remains compatible.

## Blocked by

https://github.com/CochranResearchGroup/fsearch/issues/2.
