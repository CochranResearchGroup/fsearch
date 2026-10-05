# FSearch headless engine research

Status: initial research and synthetic experiment complete; production decisions pending.
Source: upstream master d531eb3b50560fb7d9ba731787100d827f4e1e8a, cloned 2026-10-04.
Fork: https://github.com/CochranResearchGroup/fsearch

Question: can we reuse FSearch's persisted index and query engine in a bounded,
headless interface without querying the indexed filesystem?
Allowed sources: this pinned source tree, upstream build/tests, and executed
synthetic fixtures. Stop when the engine seam, filesystem hazards and minimal
headless experiment have been established. No real mount scan or installation.

## Findings

- `src/meson.build` builds `libfsearch.a`, but includes application/UI resources,
  widgets and engine sources together, with GTK required globally. There is an
  existing library target, not a clean separately packaged headless engine.
- `src/fsearch.c:738` implements database updating without constructing a GUI;
  `:790` handles that option before ordinary activation. Search options at `:634`
  instead activate the application. An existing no-display update path is not a
  structured search interface or proof of freedom from GTK dependencies.
- `src/fsearch_database_file.c:1224` exposes direct database loading into an index
  store; `src/fsearch_database_index_store.c:1402` exposes searching; search views
  expose result entries. These are the first seams to exercise.
- Ordinary name, extension, size and modification-time matchers consume cached
  entry data (`src/fsearch_query.c:207`, `src/fsearch_query_matchers.c`). Path
  strings are assembled from cached parents (`src/fsearch_query_match_data.c:88`).
  This is not a blanket guarantee for every search function.
- Content-type matching calls `db_entry_append_content_type`, which invokes
  `g_file_query_info` on the indexed path (`src/fsearch_database_entry.c:282`).
  An index-only API must restrict or redesign this feature; merely exposing all
  existing query syntax can reintroduce filesystem probes.
- Construction of an index store creates monitoring/worker loops and a root
  reappearance timer (`src/fsearch_database_index_store.c:730`). The timer can
  `g_file_test` and rescan indexed roots (`:630`). A production query-only mode
  must explicitly disable autonomous filesystem activity, including these paths.
- `src/fsearch_database_scan.c:129` calls `opendir`, `readdir` and `fstatat`.
  The different-device check at `:190` and exclusions at `:196` come AFTER the
  `fstatat` call. Therefore the one-filesystem option and exclusions do not
  prevent the first operation on excluded storage. Cancellation between calls
  cannot interrupt a kernel-blocked syscall.
- Search uses a shared worker pool/collection queue and mutable views
  (`src/fsearch_database_index_store.c:1353`). The database layer locks the
  store for search/sort (`src/fsearch_database.c`). API concurrency must follow
  that ownership contract, not invoke store searches concurrently without locks.
- Cancellation exposes incomplete results, already covered by
  `src/tests/test_database_index_store.c`. Reuse that distinction in the API.

## Initial proposed boundary (not an approved ADR)

A query process loads a trusted per-user snapshot and returns bounded JSON from
cached name/path/size/time fields. It does not construct GtkApplication, start
root scans/monitors, expose content-type probing, or fall back to scanning after
load failure. Index updates run separately against explicitly admitted roots,
with mount checks before traversal and process containment. The existing
file-searcher provides MCP routing; this fork owns the reusable search engine.

## Build evidence

Initial Meson setup failed because `itstool` was missing. Using ephemeral
`uvx --with ninja --with itstool meson` supplied build tools without system
installation. The installed GTK/GIO/PCRE2/ICU development dependencies were found.
Automatic sccache selection stalled the compiler clients; stopped only this build's process tree and selected `CC=/usr/bin/gcc`. Full build completed successfully. All 13 upstream Meson test targets passed with DISPLAY and WAYLAND_DISPLAY removed. See `headless-evidence/baseline-testlog.txt`.

## Synthetic experiment

Source: `src/prototypes/headless_probe.c` and `run_headless_probe.py`, throwaway research code on `research/headless-engine`. No production files modified; no commits made.

Built the probe against the existing static library, without GtkApplication or gtk_init. It indexed exactly five synthetic files in a temporary directory, persisted the snapshot, removed that directory, then loaded and queried the snapshot in separate short-lived processes.

`headless-evidence/summary.json` and per-case strace receipts show:

- Filename, output-limit, extension, empty-result and pre-cancelled searches produced parseable JSON with expected result counts and completeness.
- Quote and newline filenames survived JSON serialization.
- Zero indexed-root file syscalls were observed for those five runs after the root was deleted.
- The contenttype negative control produced six indexed-root file syscalls. This is an observed hazard, not merely a suspected one.
- A missing database failed without scanning fallback.
- The binary dynamically loads Pango but no GTK/GDK shared library (`headless-evidence/linkage.txt`). The current compile still requires GTK headers and the upstream build still builds its GUI. No GTK-free packaging claim.

These are tiny, short-lived, synthetic observations. They do not establish arbitrary query safety, long-lived timer safety, monitoring behavior, performance, memory scaling, concurrent requests, corrupt/untrusted database safety, or production mount containment. Output is bounded AFTER matching; engine result collection is not bounded by the output limit. The probe accepts trusted inputs only and is not a public API.

## Reproduce

From this repository:

```sh
CC=/usr/bin/gcc uvx --with ninja --with itstool meson setup /tmp/fsearch-headless-baseline-build .
uvx --with ninja --with itstool meson compile -C /tmp/fsearch-headless-baseline-build -j 4
env -u DISPLAY -u WAYLAND_DISPLAY uvx --with ninja --with itstool meson test -C /tmp/fsearch-headless-baseline-build --print-errorlogs
cc -std=gnu11 -D_GNU_SOURCE -D_FILE_OFFSET_BITS=64 -I src -I /tmp/fsearch-headless-baseline-build -I /tmp/fsearch-headless-baseline-build/src src/prototypes/headless_probe.c /tmp/fsearch-headless-baseline-build/src/libfsearch.a $(pkg-config --cflags --libs gtk+-3.0 gio-unix-2.0 libpcre2-8 icu-uc) -lm -o /tmp/fsearch-headless-baseline-build/headless_probe
python src/prototypes/run_headless_probe.py /tmp/fsearch-headless-baseline-build/headless_probe docs/research/headless-evidence
```

The runner creates and removes only its own temporary fixture. Do not point the probe's build command at real roots. Build prerequisites: GCC, GTK/GIO/PCRE2/ICU development libraries, pkg-config, gettext and strace. Meson/ninja/itstool are supplied by uvx.

## Recommended next slice

A bounded JSON CLI loading a private, trusted snapshot, with an explicit query-only store lifecycle. Restrict query features that perform metadata access; preserve incomplete vs empty results. Prove output/work limits and shutdown before wrapping the interface with file-searcher's existing MCP. Separate index updates from serving queries and qualify mount containment independently. These are recommendations awaiting the design interview, not accepted ADRs.

## Open decisions

1. JSON CLI first or persistent API first?
2. Cached per-user filename visibility vs current permission revalidation?
3. Initial admitted roots and mount-policy representation?
4. Required freshness, index size, latency and memory thresholds?
5. Upstream-compatible optional headless build vs a larger engine extraction?

No MCP registration, runtime installation, real-root indexing or personal
memory write is authorized by this research packet.

## Subsequent approved implementation

The operator approved the five-ticket breakdown and first CLI slice. See `2026-10-04-cli-acceptance.md` for the local implementation, tests, comparative benchmark and remaining integration gates. Earlier probe evidence above remains historical.
