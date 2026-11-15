# 04 Task FSM (facts only)

Source primary: `aj/task.py`

## Full contents: status constants, `TERMINAL`, `TRANSITIONS` (`aj/task.py:42-91`)

```python
RECEIVED = "RECEIVED"
UNDERSTANDING = "UNDERSTANDING"
PLANNED = "PLANNED"
WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
AUTHORIZED = "AUTHORIZED"
EXECUTING = "EXECUTING"
VERIFYING = "VERIFYING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
RECOVERING = "RECOVERING"
RETRYING = "RETRYING"
ESCALATED = "ESCALATED"
ABORTED = "ABORTED"
CANCELLED = "CANCELLED"
# A persisted task that cannot be replayed safely waits here for a human.
RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
# A running task was asked to stop; execution was not forcibly interrupted.
CANCEL_REQUESTED = "CANCEL_REQUESTED"
# Dependency-blocked work; not final.
BLOCKED = "BLOCKED"
# Permanently abandoned after a human/policy decision; preserves all history.
DEAD_LETTER = "DEAD_LETTER"

# A task is *final* when nothing more may happen to it. FAILED is deliberately
# not final: failure is the entry point of the recovery path.
TERMINAL = (COMPLETED, ABORTED, CANCELLED, DEAD_LETTER)

TRANSITIONS: Dict[str, tuple] = {
    RECEIVED: (UNDERSTANDING, FAILED, CANCELLED, ABORTED, RECOVERY_REQUIRED),
    UNDERSTANDING: (PLANNED, FAILED, CANCELLED, ABORTED, RECOVERY_REQUIRED),
    PLANNED: (AUTHORIZED, WAITING_FOR_APPROVAL, CANCELLED, ABORTED, FAILED,
              RECOVERY_REQUIRED, BLOCKED),
    WAITING_FOR_APPROVAL: (AUTHORIZED, CANCELLED, ABORTED, FAILED, RECOVERY_REQUIRED),
    AUTHORIZED: (EXECUTING, CANCELLED, ABORTED, RECOVERY_REQUIRED),
    EXECUTING: (VERIFYING, FAILED, CANCELLED, ABORTED, RECOVERY_REQUIRED,
                CANCEL_REQUESTED),
    VERIFYING: (COMPLETED, FAILED, CANCELLED, ABORTED, RECOVERY_REQUIRED),
    FAILED: (RECOVERING, ABORTED, ESCALATED, DEAD_LETTER),
    RECOVERING: (RETRYING, ESCALATED, ABORTED, DEAD_LETTER),
    RETRYING: (EXECUTING, FAILED, ABORTED),
    ESCALATED: (CANCELLED, ABORTED, COMPLETED, DEAD_LETTER),
    RECOVERY_REQUIRED: (AUTHORIZED, FAILED, ABORTED, CANCELLED, DEAD_LETTER),
    CANCEL_REQUESTED: (CANCELLED, COMPLETED, FAILED, ABORTED, DEAD_LETTER),
    BLOCKED: (AUTHORIZED, PLANNED, CANCELLED, FAILED, DEAD_LETTER,
              RECOVERY_REQUIRED),
    COMPLETED: (),
    ABORTED: (),
    CANCELLED: (),
    DEAD_LETTER: (),
}
```

## Transition/validation logic (`aj/task.py`)

- `TaskRecord.terminal` (`140-141`): `self.status in TERMINAL`.
- `TaskRecord.can_transition` (`143-144`): `status in TRANSITIONS.get(self.status, ())`.
- `TaskRecord.transition` (`146-168`): no-op if same status; if not `force` and not `can_transition` raises `AjError(CALLING_INVALID_STATE)`; if `self.terminal and not force` raises `AjError` "already final"; sets `self.status = status`, updates timestamps, sets `completed_at` when `status in TERMINAL`, appends event.
- `TaskStore.reload/_reload_locked` (`434-439`): rejects loaded records where `record.status not in TRANSITIONS` with load error `unknown task status ...` and skips them.
- `TaskStore.save` preserves store-controlled lifecycle/identity/history fields on existing records, including `status`, `events`, `completed_at` (`484-491`).
- `TaskStore.transition` (`642-656`): calls `record.transition(status, detail, force=force)`, persists, fires `after_transition`.
- `TaskStore._validate_import_record` (`499-597`): requires `status in TRANSITIONS` (`518-521`), event statuses in `TRANSITIONS` (`551-554`), terminal/non-terminal consistency with `TERMINAL` and `completed_at` (`534-540`), last event status equals record status (`568-572`), etc.
- `TaskStore.mutate` (`694-710`): forbids lifecycle changes (`status`/`events`) outside store lifecycle operations.

**Observed implication (fact):** `"ABANDONED"` is not a defined constant in `TRANSITIONS`/`TERMINAL` and would fail `status not in TRANSITIONS` checks in reload/import/event validation as written, but is set/persisted by forced transitions in orchestrator code and asserted in tests (see below).

## `ABANDONED` / `abandon` / `abandoned` occurrences (source/tests/CLI; grep with context)

Search command: `grep -rn "ABANDONED\|abandon\|abandoned" aj tests config docs`

Key matches (file:line + context, non-exhaustive display for docs; see grep output for full set):

- `aj/task.py:62` `# Permanently abandoned after a human/policy decision; preserves all history.` (comment; `DEAD_LETTER` follows — no `ABANDONED` constant)
- `aj/task.py:564` `# historical records (e.g. requeue/abandon), so edge legality is not` (import validation comment)
- `aj/orchestrator.py:2539` safe action suggestion `reconcile.dead_letter` reason "explicitly abandon unrecoverable work..."
- `aj/orchestrator.py:2873` operator reconcile doc: `- abandon: mark task as ABANDONED ...`
- `aj/orchestrator.py:3207` terminal/idempotent handling checks for string `"ABANDONED"`
- `aj/orchestrator.py:3209-3210` idempotent no-op for `action == "abandon"` when status `"ABANDONED"`
- `aj/orchestrator.py:3275-3295` operator reconcile `abandon` action: calls `self.abandon(...)`, handles idempotent `"ABANDONED"`
- `aj/orchestrator.py:3467` `def abandon(self, task_id: str, reason: str = "") -> TaskRecord:`
- `aj/orchestrator.py:3488-3510` abandon implementation: if status `"ABANDONED"` raise; `self.tasks.transition(task_id, "ABANDONED", ..., force=True, reason="abandoned")`; records error/audit `task_abandoned`/journal `TASK_ABANDONED`/memory
- `aj/consistency.py:236` `if success_receipts and status not in ("COMPLETED", "ABANDONED"):`
- `aj/__main__.py:312` CLI reconcile choices include `"abandon"`
- `tests/test_dead_letter.py` (multiple): abandon flow, idempotency, inspectability, receipts, races, assertions `status == "ABANDONED"`
- `tests/test_audit_reliability_security.py:119-141` `test_legacy_abandon_preserves_terminal_immutability_and_no_reentry` asserts `ABANDONED` behavior/idempotency/non-reentry
- `tests/test_phase3d_recovery_observability.py:233-244` reconcile abandon preserves legacy semantics / idempotent

(Full grep results recorded during analysis; no matches found in `config/`.)

## Task status set directly (bypassing normal transition validation API) / relevant status mutations

Search: `grep -rn '\.status\s*=' aj`

- `aj/task.py:160` `self.status = status` inside `TaskRecord.transition(...)` (store-controlled transition method; legality enforced unless `force=True`, and terminal/force rules applied as coded).
- `aj/lease.py` (multiple, e.g. `275,286,314,336,420,476,477,492,493,494`): `Lease.status` assignments (different domain object, not task).
- `aj/execution_domain.py:98` `self.status = status` in execution domain transition logic (execution record, not task).
- `aj/delegation.py:398` assignment status assignment in `AssignmentRecord.transition`; `4319,4350,4420,4440,4441` delegation/assignment record `status` fields updated (delegation domain).
- `aj/contracts.py:106,199` comparisons only.
- `aj/invariants.py:41` comparison.
- `aj/orchestrator.py` (numerous comparisons `record.status == ...`, plus reads); **no `record.status =` assignment found** in orchestrator except through `TaskStore.transition`/`TaskRecord.transition` paths.

**Interpretation aid (fact):** direct task status mutation outside `TaskRecord.transition` was not observed in `aj/` via `record.status = ...` (except `TaskRecord.transition` itself). Bypass of *FSM edge legality* occurs via `force=True` transitions (store/API-controlled) and by using statuses not modeled in `TRANSITIONS/TERMINAL` (e.g. `"ABANDONED"` forced).

## `force=True` transition usages (aj/tests)

Search: `grep -rn 'force=True' aj tests`

- `aj/orchestrator.py:3438` `self.tasks.transition(task_id, taskmod.PLANNED, "requeue from dead-letter", force=True, reason="requeue")` (`Aj.requeue`)
- `aj/orchestrator.py:3496` `record = self.tasks.transition(task_id, "ABANDONED", reason or "task abandoned", force=True, reason="abandoned")` (`Aj.abandon`)
- `tests/test_dead_letter.py:364` `tasks.transition(outcome.task_id, taskmod.DEAD_LETTER, "deps failed", force=True)`
- `tests/test_task_persistence_fail_closed.py:378` `tasks.transition(r.task_id, "ABORTED", "operator abort", force=True)`

CLI exposure of force is not implemented as a dedicated flag in inspected `aj/__main__.py` (UNVERIFIED for all surfaces); force is used internally by orchestrator methods above.

## Facts summary (no recommendation)
- `ABANDONED` appears in code/tests/CLI choices and is persisted via forced transition, but is **not** in `TRANSITIONS` or `TERMINAL` in `aj/task.py`.
- Reload/import validation reject statuses not in `TRANSITIONS` and enforce terminal/completed_at/event consistency against `TERMINAL`.
- `requeue` and `abandon` use `force=True` transitions; `abandon` sets a non-modeled status string.
