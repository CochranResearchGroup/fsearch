# Plan0006 attribute-only permission transition diagnosis

State RED_REPRODUCED; M3/M4 IN_PROGRESS, M5/M6 pending.
Source30dd289abb345fb635bc60070f1f02a1cf8f4151, feat/incremental-generations,
/home/ecochran76/worktrees/fsearch-incremental-generations.
Full objective,600MiB/1.25GiB aggregate,1s/10s visibility and soak gates unchanged.

Frozen control: fixed approved owned fixture /home/ecochran76/worktrees/fsr-q-20261010/owned,
final durable-batch staged runtime (m4-durable-batch-final-runtime-identity.json),
unchanged installed helper/configuration/capabilities. Create a readable directory
and child, wait for child query visibility, chmod directory000, create a later
same-parent regular sentinel and wait for its visibility. Fresh rebuild must
exclude directory/subtree; native serving and a fresh normal MCP must agree.
This is a correctness control; rebuild/MCP launch time is not a1s freshness
measurement. Guard45s/unit65s,1280MiB/no swap/CPU150percent/Tasks128, existing
host-pressure thresholds. Restore permissions and reap owned processes finally.

Run:
python3 src/tests/test_broker_process.py <final-runtime> <frontend> <boundary>
--actual-fixture-dir /home/ecochran76/worktrees/fsr-q-20261010
--actual-permission-transition --durable-catalog
Use the same reviewed systemd/run_pressure_guard wrapper as adjacent receipts.
The option is intentionally explicit and not registered as an expected-green
synthetic suite case. Production code is unchanged.

Original assembled run fails at fresh MCP result equality. Native and fresh
MCP return directory and child while coverage claims watching/source_drained;
rebuilt oracle returns0 and excluded_permissions1. Minimize by moving the
transition directly after qualified startup, removing unrelated create/ancestor
rename controls. Same failure repeats in2.743s, cgrouppeak139399168bytes/swap0,
exit1 and no host-pressure stop. Minimized sequence3/event2 proves later regular
source progress. Evidence prefixes m3-permission-transition-first- and
m3-permission-transition-minimized-; native/oracle and fresh MCP JSON retained.
Five exact recorded PID/start/boot identities absent after each run, fixture
outputs archived without deletion. No installed helper/root change or reboot.

Ranked hypotheses after red:
1. Fixed helper does not subscribe to attribute events: confirmed source mark
   subscribes CREATE/DELETE/RENAME/ONDIR/EVENT_ON_CHILD, omits FAN_ATTRIB.
2. Decoder rejects attribute mask: confirmed SUPPORTED mask omits0x4, so simply
   changing the mark would cause unsupported_mask rather than reconciliation.
3. Sink lacks directory-self transition handling: current namespace side model
   rejects '.' and expects named child side2 plus target. This is an additional
   required protocol seam, not proof of actual attribute delivery.

Authoritative ABI reference:
[fanotify(7)](https://man7.org/linux/man-pages/man7/fanotify.7.html) describes
FAN_ATTRIB metadata changes and DFID_NAME '.' identifying a directory itself.
[fanotify_init(2)](https://man7.org/linux/man-pages/man2/fanotify_init.2.html)
describes directory-FID/name reporting. Retain actual ABI capture as a gate;
synthetic encoding cannot qualify the new kernel event path.

Required next source packet (freeze before implementation): decode attribute
records including directory-self identity; contain/admit before secondary
metadata access/export; translate accepted directory identity through the
private parent map, revalidate child against its recorded parent/basename,
retire inaccessible subtree, retain regular filename eligibility independent
of content readability, and re-admit newly readable excluded subtrees.
Unknown/outside handles remain unprobed/unexported. Root changes and ambiguity
must produce truthful sticky gap; only subsequent drain can establish watching.
Do not treat ATTRIB as CREATE or allow '.' in ordinary child-path operations.

An excluded-directory identity strategy must cover permission restoration as
well as removal. The current map holds accepted inventory handles only, so a
restored initially excluded directory is not safely resolvable merely because
an attribute event names its self handle. Define bounded, rooted metadata
provenance for this case or explicitly reject the design; silent drop and
whole-root polling are not substitutes for the full objective.

Reviewable activation must pin the revised helper build/hash/event mask,
unchanged fixed root, unit/capability/resource limits, rollback identity and
actual raw ABI/minimized deny/restore/root/outside tests. Current authority covers
fixed-helper invocations; replacing that installed privileged helper requires
a concrete operator-approved activation packet. Source design/preparation may
continue. No new observation/privilege/installation authority is inferred from
this red result. No repair or M3 acceptance claimed.

Durable-batch memory reconciled completed_visible without retry; episode
0bd9e21b-53e2-4764-8259-32edcb776779, repository receipt
m4-durable-batch-reconciliation-visible.json.

Harness regression:3/3 existing assembled CLI/MCP, dirty-startup preservation
and static-permission startup controls pass under the same bounds. No production
source changed; the new explicit actual permission test remains red.
Memory disposition queued through graphiti-runtime remember; preserve
m3-permission-transition-memory-receipt.json and reconcile before related retry.
