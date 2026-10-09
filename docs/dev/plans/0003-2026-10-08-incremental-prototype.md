# Incremental filename state prototype

State: CLOSED
Owner: Codex
Issue: https://github.com/CochranResearchGroup/fsearch/issues/23

## Current State
Accepted workspace service is unchanged. The shared HTML/Node model and 100k/1m experiments are complete; research and accepted requirements are copied from their retained research worktree for provenance.

## Question and scope
Can immutable base records plus a bounded identity-keyed overlay preserve case-sensitive literal cached-name/path results and directory move/delete semantics, with explicit incomplete/deferred coverage? Build one standalone HTML logic demo and a Node experiment driver using the same model. Synthetic records only; no filesystem watcher or native integration. No production changes, raw path discovery, real-root scans or privileged helpers.

## Frozen experiment
Correctness: 1,000 files, two nested folders, exhaustive independently maintained full-path oracle; create/delete/rename, folder move/delete/recreation, Unicode/literal punctuation, out-of-root/cycle rejection, overflow/restart, reconciliation and atomic budget rejection.
Normal model workload: 20 creates with 100 ms deliberate debounce, each followed by a full query over 100,000 records. Heavy model workload: 1,000 creates batched with 250 ms debounce followed by a full query. Measure event-submission-to-query visibility, process RSS and maxRSS. Try 1,000,000 records only if 100,000 completes within 30 seconds and peak RSS is below 200 MiB; stop each run at 45 seconds with 512 MiB V8 heap ceiling. Record all failures separately. No native result-order, ICU, non-UTF8 or watcher parity claim; full production budgets remain unqualified.

## Completion
Capture the shared model, demo, experiment receipts and verdict on prototype/incremental-filenames, with a tracker pointer. Preserve limitations and recommend one bounded native successor. No merge of throwaway code into master.

## Outcome
70 modeled oracle comparisons passed. 100k and gated 1m workloads completed. Model direction is viable; native matcher/identity ingestion, real watcher resources, production memory and freshness are unqualified. See docs/research/2026-10-08-incremental-prototype.md.
