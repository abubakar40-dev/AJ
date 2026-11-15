# 30 — Phase 5A.6R2 Pre-Implementation Audit (Parent Lifecycle Enforcement, Reconciliation & Recovery Closure)

**Date:** 2026-11-14  
**Stage:** 5A.6R2 (corrective closure, audit-before-implementation)  
**Status:** Audit complete for 5A.6R2 entry; implementation follows this audit.

## 1. Baseline, Git safety, and health (verified)

- **Repo:** `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- **Branch/HEAD (unchanged):** `main @ 468fdcebece5b25f02e53add4928d3650ef175f4`
- **`git status --short` at 5A.6R2 start:** **54 entries** (17 tracked modified, 37 untracked), all preserved. No staging/commit/push/merge/rebase/reset/clean/history rewrite planned.
  - Tracked modified: `aj/__main__.py`, `aj/config.py`, `aj/diagnostics.py`, `aj/ids.py`, `aj/orchestrator.py`, `aj/receipts.py`, `aj/recovery.py`, `aj/runtime.py`, `aj/scheduler.py`, `aj/task.py`, `aj/transfer.py`, `tests/test_foundation.py`, `tests/test_orchestrator.py`, `tests/test_path_config_hardening.py`, `tests/test_phase2.py`, `tests/test_phase3.py`, `tests/test_step_c_gap_closure.py`.
  - Untracked include preserved 5A artifacts/modules/tests and docs `25`–`29` under `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/`.
- **Health:** `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` → **ok: true, 23/23 checks passed, failures: []**, attached `{jarvis:false, helix:false, hermes:"NOT ATTACHED"}`.
- **Boundaries:** JARVIS/HELIX/Hermes repos/config/services untouched; Hermes `NOT ATTACHED`; `gateway.ensure` not implemented/enabled/executed/authorized.
- **Historical 5A.6R evidence (reported):** 15 passed (5A.6R+5A.6), 47 passed (targeted 5A.4/5A.5/compat), 548 passed / 13 warnings / 0 failures (full), 23/23 health. Actual current suite not fully rerun in this audit step (checkpoint/verified focused 15 passed previously).

## 2. Inputs inspected (5A.6R artifacts and current code)

- Docs: `25_PHASE_5A_6R_PRE_IMPLEMENTATION_GAP_AUDIT.md`, `26_DELEGATION_END_TO_END_IMPLEMENTATION.md`, `27_DELEGATION_AUTHORIZATION_AGGREGATION_AND_RECOVERY.md`, `28_PHASE_5A_6R_TEST_AND_VERIFICATION.md`, `29_PHASE_5A_6R_VERIFICATION_REPORT.md` (5A.6R INCOMPLETE; primary residuals: no automatic parent task-state enforcement on all child changes, incomplete crash/concurrency/recovery coverage, incomplete orphan/stuck/incorrect-completion detection, 57-scenario certification incomplete, non-atomic multi-store limits).
- Code inspected: `aj/task.py`, `aj/delegation.py`, `aj/orchestrator.py`, `aj/scheduler.py`, `aj/execution_domain.py`, `aj/recovery.py`, `aj/receipts.py`, `aj/ids.py`, `aj/authorization.py`, `aj/storage_diagnostics.py`, `aj/locking.py` usage patterns.
- Tests inspected (assertion intent): `tests/test_phase5a6_delegation_foundation.py`, `tests/test_phase5a6r_delegation_closure.py` (reconciliation explicit via `Aj._reconcile_delegation_parent`, aggregation/monitoring observational, execution-boundary guard via `_delegated_permission_guard`, scheduler integration demonstrated in limited path).

## 3. Current lifecycle, transition, and reconciliation behavior (traced)

### 3.1 Task lifecycle and central mutation boundary
- `TaskRecord.transition()` (`aj/task.py`) enforces allowed transitions/terminal guards and appends event.
- `TaskStore.transition()` is the canonical persisted lifecycle transition path (lock → mutate record → `_persist_locked` append snapshot). `TaskStore.cancel()` also transitions to `CANCELLED` through the store. `TaskStore.apply/mutate` prohibit status/event changes and persist controlled field updates; `import_record` validates/adopts historical records without overwriting existing IDs.
- `_persist_locked()` appends JSONL under store lock + file lock, fails closed on `OSError` with in-memory reconciliation/reload and raises `StorageError` (no durable-progress claim on failure).
- Orchestrator performs many transitions directly via `self.tasks.transition(...)` across handle/resume/execute/cancel/dead-letter/recovery/operator-reconciliation paths (e.g. RECEIVED→UNDERSTANDING→PLANNED→AUTHORIZED→EXECUTING→VERIFYING→COMPLETED, failure/retry/recovery/cancel/dead-letter/escalation branches). `_fail()` and `cancel_task()` also drive terminal/non-terminal transitions.

### 3.2 Delegation integration and current reconciliation hooks
- `Aj.delegate()` validates/matches/narrows, creates child tasks + logical assignments, prepares children via `_prepare_delegated_child_for_scheduling()` (existing planning/authorization transitions), finalizes delegation, then calls `_reconcile_delegation_parent(parent.task_id)` (best-effort, exceptions swallowed).
- `_reconcile_delegation_parent()` (mutating, bounded to parent delegations): attempts child preparation for each child, computes `aggregate_parent_progress()`, stores `delegation.evidence.last_reconciliation` snapshot (at/aggregation/children) and reason on delegation record, saves delegation. **It does not enforce parent task lifecycle state transitions** (no parent completion/failure/block/manual-review transition derived from aggregation).
- `delegation_status()` recomputes aggregation observationally on read; `delegation_monitor()` is observational and returns anomalies via `detect_delegation_anomalies()` (incomplete delegations, missing parents/child tasks, stuck/recovery-required assignments). No dry-run/apply explicit reconciliation API separation beyond current mutating helper.

### 3.3 Aggregation semantics (current)
- `aggregate_parent_progress()` (`aj/delegation.py`) derives counts/waiting/can_complete/requires_manual_review from current child task states for `all_required|any_sufficient|subset_required`; treats RECOVERY_REQUIRED/ESCALATED/CANCEL_REQUESTED/unknown/missing as manual-review blockers for completion. No snapshot/evidence id tied to aggregation result, no stale-detection marker beyond timestamp in delegation evidence, no parent terminal-state regression guard, no idempotency keying across repeated calls, no atomic coupling to task-store parent state.

### 3.4 Recovery/monitoring/scheduler boundaries
- `aj/recovery.py` provides conservative task recovery scanning/outcomes (replay_safe/recovery_required/converged/blocked) and explicit recovery delegation to orchestrator; separate from delegation reconciliation.
- 5A.5 scheduler/dispatch/lease/execution paths remain separate and must not be bypassed/duplicated; 5A.4 `ExecutionStore` and existing `LeaseManager` reused.
- Existing delegated-permission guard `_delegated_permission_guard()` enforced in `_resume_locked()` and `_execute()` for delegation-context tasks (fail-closed on missing/invalid/widened/unverifiable envelope); all supported execution entry points must remain guarded.

## 4. Missing child-transition hooks and parent enforcement gaps (5A.6R2)

| Area | Current state | Gap / risk | Narrowest safe integration point |
|---|---|---|---|
| Automatic parent reconciliation on child transitions | No post-transition hook; reconciliation only explicit (`_reconcile_delegation_parent`) and post-delegation best-effort | Relevant child transitions (authz/admission/dispatch/execution/attempt/terminal/unknown/recovery/manual-review/cancel) do not trigger parent reconciliation or durable pending marker | Add store-level post-transition notification/callback (wired by orchestrator) after successful durable transition/cancel persist, scoped to tasks with `parent_task_id` and/or active delegation linkage; fail closed to pending/manual-review evidence on hook failure without corrupting child transition result |
| Parent lifecycle/state enforcement | Aggregation stored in delegation evidence only; parent task status not derived/enforced | Parent may remain non-terminal/completable by external logic while children unresolved/unknown/recovery-required; incorrect completion not centrally prevented | Apply deterministic, evidence-backed parent policy in explicit reconciliation path (and/or guarded hook) using existing task states/vocab where possible; prevent/flag false completion and represent waiting/failure/manual-review/partial states conservatively without overwriting child results |
| Idempotent aggregation | Repeated reconciliation recomputes/saves snapshots without idempotency token or conflict detection | Duplicate/concurrent calls can churn evidence or create contradictory interpretations; stale results undetectable | Include child-state snapshot hash/version evidence in aggregation, detect unchanged state/no-op, prevent terminal regression without explicit evidence-backed policy, fail closed on conflicting snapshots |
| Crash/race recovery (A–J windows) | Non-atomic multi-store writes acknowledged; no delegation reconciliation intent/outcome records for crash windows | Interrupted parent update/evidence write, concurrent child/parent transitions, delegation-task disagreement, or contradictory terminal parent state can be ambiguous | Record reconciliation intent/outcome evidence in delegation/task-compatible append-only structures; add bounded explicit recovery/detection for stated windows; never infer external side effects |
| Orphan/stuck/inconsistent detection & explicit reconciliation | `detect_delegation_anomalies()` partial; no dry-run/apply separation, no batch-bounded explicit apply API with provenance | Required detection matrix incomplete; read-only monitoring cannot be confused with repair but repair tooling limited | Extend read-only detectors (non-mutating) and add explicit `reconcile_*` dry-run/apply operations with validated batch bounds, provenance, before/after evidence, fail-closed behavior |
| Cancellation/child isolation/policy | `cancel_task` exists; parent cancellation/delegation policy not fully enforced to stop new dispatch/creation/reconcile outcomes per policy | Unsafe dispatch or fabricated cancellation/completion possible without explicit policy enforcement | Enforce conservative policy in delegation reconciliation and preparation/dispatch-adjacent checks (without bypassing scheduler), preserve unknown outcomes, represent isolation deterministically |
| Authorization boundary regression | Guard present in `_resume_locked` and `_execute`; not exhaustively proven across all supported execution/recovery paths and post-assignment changes | Escalation/revocation/change-after-assignment risk on uncovered paths | Trace all supported execution/resume/recovery entry points; ensure guard + revalidation where applicable; add targeted regression tests |

## 5. Persistence/locking constraints (relevant)

- Task store and delegation/assignment stores are append-only JSONL with per-store file locks; **no cross-store atomicity**. Reconciliation that touches delegation evidence and (if implemented) task state must be designed as recoverable/idempotent steps with explicit evidence.
- Existing locks: task store internal `RLock` + file lock around append; scheduler/lease/orchestrator paths have their own coordination. No new transaction manager/daemon/distributed locking allowed.
- NTFS/SQLite-WAL reliability unresolved; fail closed on persistence uncertainty, prefer temp storage for deterministic tests.

## 6. Minimal safe closure plan (ordered, bounded)

1. **Central hook + pending reconciliation safety:** wire a narrow post-transition hook/callback from `TaskStore` to orchestrator (and/or orchestrator-side wrapper) to trigger bounded delegation parent reconciliation/pending marking for relevant child transitions, with failure containment and durable evidence intent where feasible.
2. **Deterministic parent aggregation/enforcement:** evolve `aggregate_parent_progress`/reconciliation to include snapshot evidence, idempotency/no-op behavior, stale/conflict detection, and conservative parent task-state enforcement per required-child/optional/unknown/recovery/manual-review/cancellation policy (no false completion, no child overwrite, preserve history).
3. **Explicit reconciliation API:** add bounded dry-run (read-only) and apply (mutating, evidence-backed, provenance-recorded) reconciliation operations; keep `delegation_monitor/status` observational/non-mutating.
4. **Detection extensions:** expand anomaly detection for orphan/lineage/linkage/missing assignment/execution-lease uncertainty/stale aggregation/incorrect completed parent/incomplete reconciliation/manual-review states.
5. **Cancellation/failure isolation/authz regressions:** enforce conservative parent-cancel and child-failure semantics in reconciliation/policy checks; verify delegated-permission guard and revalidation across supported execution paths.
6. **Tests/docs/verification:** add deterministic focused tests for required 5A.6R2 scenarios (documenting unverified claims), run 5A.4/5A.5/5A.6/5A.6R regressions, full suite, `aj --check`, and produce docs `31`–`34` with evidence-backed verdict (stop after 5A.6R2).

*Audit is evidence-backed and conservative. No implementation changes performed in this step.*