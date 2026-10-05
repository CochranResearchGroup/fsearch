# FSearch filename discovery

FSearch maintains searchable knowledge of file and folder names within selected storage locations.

## Language

**Indexed root**:
A folder selected as the starting point for collecting filename information.
_Avoid_: Drive (an indexed root may be a folder within a drive).

**Snapshot**:
A saved view of indexed names and metadata from an earlier observation of indexed roots.
_Avoid_: Live filesystem view.

**Cached visibility**:
Filename knowledge retained from an earlier observation under the index owner's access rights. It does not assert the owner's current access to the named file.
_Avoid_: Current permission check.

**Approved root**:
An indexed root explicitly admitted for indexing after its storage and mount boundaries have been reviewed.
_Avoid_: Healthy root (a successful probe does not establish admission).

**Incomplete search**:
A search that stopped before all eligible entries were considered. Its results do not establish that all matches have been found.
_Avoid_: No matches (an incomplete search may have found none).

**Accepted snapshot**:
A snapshot admitted for serving after its format, ownership and indexing outcome have been qualified. It may be older than the latest attempted update.
_Avoid_: Latest snapshot (an attempted update may fail qualification).

**Search candidate**:
A cached entry selected as a possible match. Selection alone does not establish that it satisfies the requested literal query and filters.
_Avoid_: Match (before exact verification).

**Exact verification**:
Applying the authoritative literal matcher and requested filters to a search candidate. Every returned match must pass this step.
_Avoid_: Filesystem verification (this operation uses cached filename knowledge).
