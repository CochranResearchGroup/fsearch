# Column-filter candidate review

Frozen baseline: e21164c4. Candidate: 3d0eb0c3.
Comparison: `git diff e21164c4...3d0eb0c3 -- src/fsearch_headless.c`.
Reviewed serially against AGENTS.md, CONTRIBUTING.md, runtime-proof.md and the frozen query/memory requirements in Plan 0004. This review covers the column layout and bounded prefetch delta; it does not close the wider refresh, monitoring or MCP program.

## Standards

- nonblocking_backlog: repeated literal plane indices 192/191/190 couple allocation and flag lookup to the fixed signature representation. Named constants would reduce future drift. The current representation is internally consistent; no documented hard violation was found.
- rejected: the column allocation is speculative additional indexing. It replaces the prior allocation with the same signature bits, maintains the 32 MiB cap, and is supported by the measured selective-query requirement.

## Spec

- No blocking finding in this delta. Every ctz operation is guarded by nonzero bits. Allocation rounds to complete 64-rank words and checks the cap before multiplication/allocation. Rank and future-block accesses remain within the indexed count; prefetch additionally checks current chunk boundaries before retrieving pointers.
- Column intersection preserves the original required-bit test. Metadata planes retain the same non-ASCII/uppercase flags. Parent matches bypass basename rejection as before; exact matching remains authoritative. Future candidate prefetch retains the explicit work charge.
- Source evidence: sixteen regression targets pass, 38 CLI/socket oracle comparisons pass with indexed-root isolation, all three million-name corpora pass unchanged gates, and all three replacement-overlap fixtures pass the separate 256 MiB gate. Broad result-limited queries are not complete-search qualification. Sampled overlap measurements do not prove absence of unobserved instantaneous peaks.
- needs_evidence: installed acceptance and installed performance are still required. Synthetic roots do not establish production filesystem health or authorize root admission.

Summary: Standards has one nonblocking backlog item and no blocker; Spec has no source blocker and one installed-evidence gate.
