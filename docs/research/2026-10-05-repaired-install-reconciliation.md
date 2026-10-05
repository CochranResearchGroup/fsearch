# Repaired native runtime installation and publication

Owner: ecochran76. Source: eda902627bc96e626887b06f69f66bc3c43499e3.
Native PR #14 merged at 001b056291180b6e3d087874eb9e8b3adcfb8176, exact-head CI
37261604471 passed and master CI 37261906888 passed. Original unpublished local
history remains retained; the published history omits the credential-bearing
inherited-environment line, with private original/redaction provenance preserved.

The repaired refresh supervisor arms parent-death cleanup before native loader
startup. The deterministic stopped-loader regression reproduces the old gap and
passes on the repair. Installed acceptance: 13 refresh, 20 monitor supervisor,
10 watch worker, 34 service and 15 CLI cases (92 total), all passing. New installed
query-service isolation, moved-parent refusal and actual durable file-searcher
MCP calls also pass. No production root is scanned by these owned fixtures.

Fresh release build: first configuration lacked itstool; its build prerequisite
was installed. The first test invocation omitted a full compile, so metainfo
validation could not find its generated file. After compiling, all 19 targets
pass (publication-premain-full-suite-third.txt). Original failures remain.
No test/validator gate was removed or relaxed.

The seven command links now point to the source-versioned runtime under
~/.local/share/fsearch/runtimes/eda902627bc96e626887b06f69f66bc3c43499e3/bin.
Exact hashes and previous link targets are in publication-repair-installed-manifest.json.
All unchanged compiled sources were byte-compared to the qualified original;
unchanged native artifacts were reused by exact digest, with only the repaired
refresh Python entry replaced from the committed source. Query CLI/worker/service
hashes are unchanged from the frozen installed three-corpus performance proof.
This reuses that proof explicitly; no new production-storage measurement is claimed.

Rollback was prepared before switching under
~/.local/share/fsearch/operations/premain-repair-20261004/rollback.py. Prior runtime
and seven targets are retained. That prior refresh version predates the pre-main
lifetime repair; restoring it does not establish protection against that gap.
Fresh process census before activation found zero native FSearch survivors.
Direct installed MCP readback uses file-searcher runtime 0f0f484, whose source
and wheel identity were qualified separately. File-searcher registration/default
routing and operator roots remain unchanged; no production service is activated.

Tracker reconciliation closes qualified implementation items only. Parent #1
and adoption #5 remain open for separately directed real storage/root admission
and activation. Credentials exposed in the original local log/tool output require
operator rotation; no credentials or raw environment are published here.

Memory disposition: forbidden; no personal memory write authorized.
