# Source review: contained refresh and warm replacement

Frozen implementation: `925ecf27`. Baseline: `0edb1451f7870bf699485ddae4d7e6b02e36b26a`.
Diff: `git diff 0edb1451...925ecf27`. Commit: Implement contained refresh and explicit warm replacement (#3, #8).
Review performed serially in the primary context. Source tests are not installed acceptance.
Standards sources: CONTRIBUTING.md, AGENTS.md, docs/agents/codex-stack.md, docs/agents/runtime-proof.md.
Spec sources: current GitHub issues #3 and #8, docs/specs/0002-warm-filename-service.md, docs/plans/0004-safe-refresh-and-replacement.md.

## Standards

- `nonblocking_backlog`: possible duplicated code in supervisor resource-limit setup in `fsearch_service.py` and `fsearch_refresh.py`. Both deliberately enforce the same parent/child ceilings. A shared lifecycle helper would reduce drift; current public limit assertions pass.
- `nonblocking_backlog`: dense one-line control flow in the new refresh module and replacement methods makes error-path review harder. This resembles existing service style, but a focused formatting pass would improve maintenance. No documented repository rule requires a formatter.
- `rejected`: trailing-whitespace failures in generated Meson/compiler receipts. Raw evidence is intentionally preserved byte-for-byte; source/documentation checks excluding raw receipts pass. Do not rewrite failed receipts to manufacture a clean check.

## Spec

- `blocking`, resolved in follow-up working tree: refresh reply validation accepted malformed `ready`/`error` objects. Missing identity or non-object error data could violate the structured-failure boundary. Added object-shape validation and public injected variants; retained red/green receipts `review-protocol-shape-red.txt` and `review-protocol-shape-green.txt`.
- `needs_evidence`: installed runtime qualification is missing. Meson still marks the two refresh commands `install: false`; the installed commands still identify the earlier runtime. This is an explicit installation gate, not a claim that #3/#8 are closed.
- `needs_evidence`: source tests separately prove refresh preservation and warm replacement, but a combined refresh-while-serving acceptance scenario is still required before installation.
- No accepted scope-creep finding: the monitoring startup handshake repairs the reproduced compatibility-fixture failure and preserves GUI monitoring flags. Snapshot-only stores bypass that lifecycle. The bounded 200-run result supplements, rather than replaces, full regressions.

Summary: Standards has two accepted nonblocking findings; Spec has one resolved blocker and two evidence gates. Installation remains unqualified.

Follow-up: the public combined acceptance scenario now passes (`refresh-while-serving.txt`). During an injected delayed refresh and after atomic publication, the warm service retains the old worker/results/identity. Explicit replacement then exposes the added file with the acknowledged new identity. This resolves the combined source evidence gate. The refresh CLI and native scanner are now enabled for Meson installation, with executable mode on the Python CLI; installed acceptance remains pending. The service test target explicitly depends on the scanner and its fault adapter. These follow-up changes are subject to the full regression receipt before commit.
