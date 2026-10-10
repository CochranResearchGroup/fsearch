# Plan0006 bounded batch synchronization error controls

State SOURCE_PACKET_QUALIFIED; source30dd289a production unchanged.
M3/M4 remain IN_PROGRESS; M5/M6 pending. Owned synthetic public supervisor seam.
Freeze before run: inject OSError(EIO) before the batch log fsync or before the
first non-log cursor-publication fsync for sequence9. Prior accepted raw-byte
entry1 is checkpointed. Batch2..9 must return catalog_journal_write_failed,
reap/discard partial native mutation view, retain sequence1 and no batch query
matches with deferred coverage and refused later mutations. Stop and remove original root and
snapshot, then recover accepted prefix1, raw bytes/stable ID and read-only
journal_tail_uncommitted. Never acknowledge the failed batch or blind retry.
Existing three process-crash cuts, publication barrier, native-gap/identity and
exact1024record controls remain unchanged. No production format/code change.
Guard70s/unit90s,1280MiB/swap0/CPU150percent/Tasks128, unchanged host gates.
Targeted11registered batch controls; no installed helper/root/reboot effect.
Reported fsync errors are not power-loss or actual disk-fault qualification.

First launch rejected before test execution by host pressure: memoryfullavg10
2.94 exceeded2.0; receipt retained. Read-only35s stability observer then required
10continuous seconds within original thresholds before launching unchanged
guard70s. First control run passes10/11, including log-sync EIO. Cursor control
incorrectly kept injecting into every later non-log fsync, including lifecycle
state cleanup, causing supervisor EOF instead of the selected-boundary response.
Preserve failure log/receipt; scope injection to exactly one selected cursor
sync call by clearing its arm before raising. No production source changes or
error/recovery assertions weakened. Re-run the same11controls.

Corrected single-cursor run still10/11 because its new expectation demanded
durablefalse even after successful recovery of the previously committed prefix.
The source contract uses durable for accepted cached state, separately from
source coverage and mutation writability. Preserve failed expectation/rawlog;
require exact prefix1, empty batch results, deferred uncommitted-tail reason
and rejected new mutation both before and after explicit restart. Add a marker
proving the selected log/cursor injection occurred, and scope both errors to
one selected sync call. These are fixture corrections, not production repair.

Final11/11 registered controls pass, guard14.909s,
cgrouppeak63979520bytes/swap0. Both fault markers prove the
selected reported sync error; public reply rejects failed group, previous
committed sequence1 survives, batch entries remain absent, uncommitted-tail
coverage is deferred and later mutation is refused before and after restart.
Recovery with original root/snapshot absent preserves raw bytes and stable ID.
Fresh OS readback finds all sampled PIDs absent in first/corrected/final runs.
Raw logs, rejected pressure preflight, stability observations and cleanup
receipt retained. Production source unchanged; no installation/reboot.
This does not close M4/M3 or qualify power-loss, aggregate/current-scale/soaks.

Memory disposition queued in openclaw_ec_main through graphiti-runtime remember;
receipt m4-batch-sync-errors-memory-receipt.json. Queue acceptance is distinct
from persistence/retrieval; reconcile exact receipt before any related retry.
