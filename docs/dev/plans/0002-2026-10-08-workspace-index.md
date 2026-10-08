# Workspace filename index

State: OPEN
Owner: Codex
Issue: https://github.com/CochranResearchGroup/fsearch/issues/21

## Current State
User authorized /home/ecochran76/workspace.local. A contained inventory found 6,761,264 entries, 617,919 readable directories, 34,223 symlinks and 45 permission-denied directories. Existing two-root services remain serving. The first candidate failed under existing prototype limits.

## Scope and acceptance
Index all readable regular files and directories beneath the workspace, including hidden/generated trees. Never follow symlinks, cross descendant mounts, read file contents, change permissions, or start SysRAG. Report permission exclusions. Keep bounded memory, snapshot size and build deadlines. Qualify synthetic exclusion tests, then build a separate candidate and verify live CLI/MCP routing. Preserve rollback copies. Monitoring must be independently qualified; do not represent cached snapshot coverage as live monitoring.

## Execution
Serialized: qualify permission exclusions and capacity, build workspace snapshot, activate cached service, switch routing, verify representative children. No parallel agent work. Completion requires installed evidence and truthful monitoring status.

## Capacity qualification
Ten-million-entry cap; 512 MiB snapshot cap; 2 GiB worker address-space cap; 256 MiB optional trigram filter cap; 800,000 watch cap. Default startup deadline remains two seconds, with bounded explicit workspace-only startup override up to thirty seconds. An initial 60-second real-root attempt timed out cleanly and preserved live indexes; workspace build deadline expands explicitly to five minutes. Query examination budget remains 500,000 and incomplete results remain explicit. Continuous monitoring is not enabled until large-root churn behavior is qualified.

## Loader capacity correction
The first complete scan reached validation at 104.42 seconds, then failed safely at the independent 96 MiB snapshot-entry arena cap. Increase that bounded arena to 1 GiB, still within the worker's 2 GiB address-space cap. Failed candidates were removed; production routing was unchanged. Successful refresh output records exact file/directory counts and exclusions.
