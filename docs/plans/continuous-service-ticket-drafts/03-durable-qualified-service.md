# Prove durable recovery and whole-service scale reliability

Status: DRAFT; not published or ready-for-agent until breakdown approval
Owner: Codex; operator: ecochran76
Parent: #26; M3 tickets additionally reference #29
Milestones: M4 and M5

## What to build

Prove durable recovery and whole-service scale reliability, delivering the complete observable outcome described by the acceptance criteria. Supporting parser/module commits are internal progress, not closure boundaries.

## Acceptance criteria

- [ ] Durable accepted-generation checkpoint/replay passes crash/append/fsync/publication/corruption matrix; restart promptly serves accepted results with honest gap coverage and no query-startup rescan.
- [ ] Stage workloads, construction/restart/compaction deadlines and seeds are frozen before runs; stage advancement follows100k,~300k,1m,~3m,exact current count,10m.
- [ ] At exact current scale, simultaneous churn/compaction/queries pass600MiBsteady,1.25GiBupdate, zero swap acceptance,1snormal/10sheavy and all Plan0006 frozen query gates.
- [ ] Four concurrent clients use the bounded queue; aggregate accounting includes broker kernel costs, retained readers, builder and supervisor; no independently summed best-case peaks.
- [ ] Full24hoursynthetic soak passes without unexplained growth, process accumulation, concealed stale state or unreconciled loss; failed gates remain separately recorded.
- [ ] Current approved workspace qualification is nondestructive and authority-bounded; owned trees carry destructive/fault workloads; pressure stops preserve accepted serving.
- [ ] M4 and M5 verdicts are distinct; a durability pass remains useful even if resource qualification fails; publish an exact install/rollback candidate only after both pass.

## Blocked by

Ticket02 for full acceptance; Ticket01 permits independent durability source preparation

## Controls

Use one validated integration lane; retain failed receipts and existing approved root scope. Labels and dependencies organize work; they do not authorize privileged observation, installation or target changes. Freeze detailed workload/resource/time limits before each experiment. Publish exact source/evidence custody at the outcome checkpoint.
