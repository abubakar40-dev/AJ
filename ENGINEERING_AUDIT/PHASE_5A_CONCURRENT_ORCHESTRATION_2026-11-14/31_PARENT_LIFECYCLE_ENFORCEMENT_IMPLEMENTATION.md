# 31 — Parent Lifecycle Enforcement Implementation (Stage 5A.6R2)

**Status:** Corrective closure implementation applied on preserved 5A.6/5A.6R foundations (partial closure).  
**Baseline:** `main@468fdcebece5b25f02e53add4928d3650ef175f4`, 54 git status entries at 5A.6R2 start (preserved).

## 1. Central child-transition hooks (implemented)

- **`aj/task.py` (`TaskStore`)**: added optional `after_transition` callback and hook dispatch after durably persisted lifecycle transitions/cancellations (`transition`, `cancel`), invoked outside store lock with `(snapshot, previous_status, new_status, reason)`; callback failures do not break committed task transitions.
- **`aj/orchestrator.py` (`Aj.__init__`)**: wired `tasks.after_transition = _on_task_transition` and wrapped `tasks.transition` with `_before_task_transition` guard (central enforcement boundary) plus thread-local/RLock re-entrancy protection for delegation reconciliation.

## 2. Automatic parent reconciliation / pending handling

- **`_on_task_transition`**: for delegation-related child task transitions with parent linkage, triggers bounded/idempotent delegation reconciliation (`_reconcile_delegation_parent(..., apply_parent_policy=True)`); on failure records best-effort durable pending marker in delegation evidence (`reconciliation_pending`) without rolling back committed child state.
- **`_before_task_transition`**: blocks transition of delegation-parent tasks to `COMPLETED` when current delegation aggregation indicates unresolved/uncertain/manual-review/unsafe completion (including required children not verifiably complete, unknown/recovery-required/manual-review states, or unverifiable delegation state) — fail closed.

## 3. Aggregation, idempotency, and evidence

- **`_reconcile_delegation_parent`** (enhanced): computes child-state snapshot hash, deterministic aggregation (`aggregate_parent_progress`), stale/unchanged detection, and persists append-only reconciliation evidence on delegation records (`last_reconciliation`, bounded `reconciliation_history`, trigger/actor/provenance, incorrect-parent-completion observation). Idempotent/no-op when snapshot unchanged; no contradictory logical outcomes from repeated runs.
- **Explicit API:** `Aj.reconcile_delegation_parent(parent_task_id, dry_run=..., apply=..., batch_size=..., actor=...)` provides bounded dry-run (read-only, no delegation mutation/preparation side effects) and explicit apply (mutating, provenance/evidence recorded). Default behavior is inspection/dry-run when mode unspecified.

## 4. Parent state policy (enforced/represented)

- Parent `COMPLETED` prevented at transition boundary when required child outcomes are not verified complete/safe (`can_complete` false or manual-review/uncertainty present).
- Aggregation continues to represent required/optional semantics (`all_required|any_sufficient|subset_required`), waiting/incomplete/failed/cancelled/unknown/recovery/manual-review states; historical reconciliation evidence preserved in bounded history snapshots.
- Incorrect completed parent (terminal COMPLETED contradicting current child evidence) is detectable and recorded; automatic regression from valid terminal task state is not performed by illegal task transitions (conservative/manual-review posture).

## 5. Scheduler/execution/authorization boundaries preserved

- 5A.5 scheduler/admission/dispatch, 5A.4 execution domain/store, existing `LeaseManager`, authorization/journal/receipts/recovery conventions reused.
- Delegated-permission execution guard remains enforced in existing resume/execute boundaries; no new execution paths introduced. No real remote transport, no daemon/distributed execution.

## 6. Limitations

- Automatic enforcement focuses on preventing false parent completion and triggering/evidencing reconciliation; full policy-driven parent task terminal-state transitions for all failure/cancellation/partial/manual-review cases are not exhaustively implemented.
- Child preparation during apply reconciliation may perform state transitions (bounded) but dispatch remains scheduler-owned; hook re-entrancy guarded but complex multi-actor flows not exhaustively proven.
- Cross-store non-atomicity remains; pending markers/evidence are best-effort and reconciliation remains the source of explicit recovery. No exactly-once/cross-store atomicity/distributed correctness claimed.
