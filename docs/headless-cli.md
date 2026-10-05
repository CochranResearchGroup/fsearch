# Private snapshot JSON CLI

The Linux-only `fsearch-cli` searches a trusted owner-generated FSearch snapshot without initializing GTK or the GUI lifecycle. Build with the existing Meson dependencies; GTK development headers remain required. No runtime installation is needed to exercise the build-tree executable.

```sh
build/src/fsearch-cli --database /explicit/private/snapshot.db --query invoice --extension pdf --kind files --limit 100
```

The database must be a regular file owned by the current effective user, with no group/other permissions, at most 64 MiB. Symlink database paths are rejected. Queries never scan on load failure or check access to cached result paths. Names may remain visible after permissions change: `visibility: cached` states that policy explicitly. This is not a parser for arbitrary uploaded databases.

`--query` is a UTF-8 literal substring, at most 4096 bytes. GUI macros, glob and content-type syntax are literal text. `--path` searches the cached full path; `--match-case` enables case sensitivity. `--extension` is a literal extension without its dot; `--kind` accepts `files`, `folders`, or `all`.

Version 1 JSON reports `status`, `complete`, `truncated`, `examined`, snapshot modification age and per-root last-scan/error observations. UTF-8 paths use `path`; other filename bytes use `path: null` and `path_bytes_base64`. Coverage and freshness are saved observations, not current storage availability. Results enumerate cached files followed by folders in name order.

Defaults: 100 results, 500,000 examined candidates, 1 MiB response, 2-second worker deadline. Limits may be lowered using `--limit`, `--max-candidates`, `--max-bytes`, and `--timeout-ms`; maximums are 1000 results, 500,000 candidates, 1 MiB and 10 seconds. Response space is conservatively split between rows and metadata. Successful incomplete responses have status `result_limit`, `work_limit` or `byte_limit` and exit zero. `ok` means the eligible cached entries were exhausted. Errors have a structured `error.code`, `complete: false`, and nonzero exit.

The supervisor contains snapshot opening, loading and matching in one worker, with 512 MiB address-space and CPU limits. On deadline or SIGINT/SIGTERM it kills that worker and allows 100 ms for reaping. A kernel-blocked worker may remain: `cleanup_unproved` and `worker.reaped: false` must trigger quarantine in an eventual adapter, not automatic replacement. The deadline excludes executable startup, option parsing and a blocked stdout consumer. There is no persistent daemon or retry loop.

Warm serving is now also implemented locally; see [the service contract](warm-service.md). The one-shot path supplies cached queries only. Approved-root refresh, atomic snapshot acceptance, update quarantine, monitoring, file-searcher MCP routing and reversible installed acceptance are still open issues.
