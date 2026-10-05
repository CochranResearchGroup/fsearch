# Keep approved-root snapshots fresh through contained monitoring

Published: https://github.com/CochranResearchGroup/fsearch/issues/4

Status: READY; owner: ecochran76; honor blocking dependencies.

## Parent

https://github.com/CochranResearchGroup/fsearch/issues/1

## What to build

Changes beneath approved roots refresh filename knowledge with truthful freshness and coverage while the query process remains independent of filesystem activity.

## Acceptance criteria

- [ ] Synthetic create/rename/delete events reach a new accepted snapshot.
- [ ] Overflow, offline-root, failed-worker and restart states are explicit; last accepted snapshot remains usable.
- [ ] Monitoring cannot expand roots or bypass refresh admission/quarantine.
- [ ] Query CLI continues to perform no root metadata calls; monitor shutdown/restart proves resource cleanup.

## Blocked by

https://github.com/CochranResearchGroup/fsearch/issues/3.
