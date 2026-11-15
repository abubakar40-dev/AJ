# 14 — Execution Domain Foundation Implementation (Stage 5A.4)

**Status:** Implemented (minimal, AJ-local foundation). **Stage 5A.4 only.** No 5A.5 scheduler/admission implementation performed.  
**Baseline:** AJ `main@468fdcebece5b25f02e53add4928d3650ef175f4`, 45 pre-existing git status entries preserved at stage start (14 tracked M, 31 untracked). 5A.0–5A.3 docs (`00`–`13`) read as guidance (proposed architecture, not blanket implementation authorization).  
**Protected boundaries preserved:** Hermes **NOT ATTACHED** (read-only `hermes.status.read` boundary unchanged), `hermes gateway ensure` not implemented/enabled/executed/authorized; JARVIS/HELIX/Hermes source/runtime/config/services untouched; no real sub-agents, no agent heartbeat/remote transport, no live task transport, no fan-out/aggregation implementation.

---

## 1. What changed and why

**Problem (5A.1/5A.3):** AJ lacked a first-class `execution_id`/Execution entity (execution was implicit in task lifecycle + attempts/leases/evidence), creating ambiguity for future orchestration, correlation, and recovery.

**Implemented (minimum viable foundation):**
- Added AJ-owned stable `execution_id` generation (`exc_*`) and a first-class **Execution** domain (`ExecutionRecord`, conservative lifecycle/state machine, `ExecutionStore` append-only JSONL persistence, fail-closed writes/validation).
- Made **Task ≠ Execution ≠ Attempt** explicit in persisted/runtime linkage: `TaskRecord.current_execution_id` / `execution_ids`, attempt records carry `execution_id`, receipts/journal correlation include execution linkage (additive metadata), and execution records track `attempt_ids/current_attempt_id`.
- Integrated execution lifecycle into orchestrator execution/attempt flow (`_ensure_execution`, `_start_attempt`, `_finish_attempt`, `_execute`) while preserving existing task lifecycle, attempt semantics/IDs, receipt/journal stores, lease system, authorization, evidence, and recovery behavior.
- Wired execution store into `Aj` (and build/runtime path via persisted `data_dir`) as `executions.jsonl` alongside existing stores; no new database, no storage relocation, no NTFS/SQLite “fix”, no config/feature-flag/runtime/service changes.

**Why this shape:** smallest reliable foundation (AD-02/AD-03/AD-07 aligned) that removes identity ambiguity without introducing scheduler/admission, sub-agent runtime, duplicate lease/identity systems, or unverified external/runtime semantics.

---

## 2. Current vs new architecture (relevant slice)

| Aspect | Before (current) | After (5A.4 foundation) | Compatibility |
|---|---|---|---|
| Execution identity | Implicit (no `execution_id`) | **First-class AJ-owned `execution_id`** (`exc_*`) + `ExecutionRecord` | Existing task/operation/attempt IDs preserved |
| Task/Execution/Attempt | Collapsed/implicit | **Explicit linkage:** Task owns executions; Execution owns attempts (`execution_id` on attempts/record) | Task lifecycle unchanged; attempts remain append-only per task |
| Persistence | Tasks/attempts in task store; receipts/journal/leases separate | **`executions.jsonl` (append-only, fail-closed)** + additive linkage fields/metadata | Existing stores/schemas remain readable/usable |
| Correlation | task/operation/attempt/lease/journal/receipt | Same + `execution_id` correlation in task/attempt/receipt metadata/journal metadata | Additive only |
| Leases | Per-task execution lease (`LeaseManager`) | **Unchanged**; execution record may reference lease for correlation only | **No duplicate lease system** |
| Dispatch/scheduling/admission/agents | Unchanged | Unchanged | No 5A.5, no real sub-agents/runtime |

---

## 3. Identity and relationship model

- **`task_id`**: logical work identity (existing, preserved).
- **`operation_id`**: task-scoped operation correlation (existing, preserved; single per task in current model).
- **`execution_id`**: **new, AJ-owned, stable** identity for one concrete orchestration/execution lifecycle of a task (`ids.new_execution_id()`; never fabricated external runtime id).
- **`attempt_id`**: concrete try identity (`att_*`, existing generation/preservation).
- **Relationships:** `Task (1) -> Executions (0..N over time, 1 in current flow) -> Attempts (0..N)`. Task stores `current_execution_id` and `execution_ids`; attempts store `execution_id`; execution stores `task_id/operation_id/correlation_id`, `attempt_ids/current_attempt_id`, optional `lease_id/agent_id/assignment_id` (correlation only).
- **Lease identity remains distinct** from execution identity (existing task execution lease semantics preserved).

---

## 4. Execution lifecycle (conservative, implemented)

**States:** `CREATED`, `READY`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`, `UNKNOWN`, `RECOVERY_REQUIRED` (terminal: `COMPLETED|FAILED|CANCELLED`).

| Transition | Allowed | Notes |
|---|---|---|
| `CREATED -> READY` | yes | dispatch prepared in current flow |
| `CREATED|READY -> RUNNING` | yes | attempt started |
| `RUNNING -> COMPLETED` | yes | attempt/task outcome completed (conservative mapping) |
| `RUNNING -> FAILED|CANCELLED` | yes | attempt/task failure/cancel outcome mapping |
| `CREATED|READY|RUNNING -> UNKNOWN|RECOVERY_REQUIRED` | yes | ambiguity/crash-window/reconciliation (representable) |
| `UNKNOWN -> RECOVERY_REQUIRED` | yes | escalation to manual/conservative handling |
| `RECOVERY_REQUIRED -> READY|RUNNING|FAILED|CANCELLED|UNKNOWN` | yes | controlled recovery outcomes only as evidence supports (no auto-success) |
| any terminal -> * | **no** (unless explicit forced internal use, not normal path) | illegal transitions fail safely |
| invalid/unknown state or illegal edge | **no** | `AjError` raised |

**Entry/persistence/recovery meaning:** every state change appends a validated execution record/event in `ExecutionStore` (append-only). `UNKNOWN` and `RECOVERY_REQUIRED` are first-class representable outcomes (no conversion to success). Transitions are checked; illegal transitions fail closed/safely (no silent corruption).

---

## 5. Persistence, idempotency, and fail-closed behavior

- **Persistence:** `ExecutionStore` (`aj/execution_domain.py`) appends JSONL records with schema/shape validation, per-path file lock, and atomic append semantics as supported by existing locking/file patterns; loads and validates on init (malformed/newer/invalid records fail closed).
- **Fail-closed:** create/save/transition/load/append errors raise (`AjError`/storage error) rather than fabricating persisted state or success. Orchestrator execution-creation path persists execution before/with dispatch-attempt linkage so persistence failure does not silently claim execution was recorded.
- **Idempotency (AJ-local only):** existing idempotency/lease/task semantics preserved. `_ensure_execution` reuses current task execution when present (local, in-process/task-record scoped) and does not create duplicate current execution for the same linked context. **No exactly-once execution or external side-effect guarantee is claimed.**
- **Non-atomicity:** cross-store writes (tasks, executions, receipts, journal, leases, evidence) remain **non-atomic**; partial/crash windows can produce ambiguity and must be handled as `UNKNOWN`/`RECOVERY_REQUIRED` where applicable.

---

## 6. Evidence, correlation, leases, and recovery

- **Correlation (additive):** execution id linked to task/operation/attempt and carried in attempt records, receipt `metadata.execution_id`, and journal event metadata; existing task/operation/attempt/lease/correlation fields preserved for audit/evidence consumers.
- **Leases:** existing `LeaseManager` execution/operation lease semantics **preserved and reused**; execution identity/record is conceptually distinct from lease identity (no second lease system, no lease behavior redesign).
- **Recovery:** conservative and compatible with existing recovery model; execution domain can represent `UNKNOWN`/`RECOVERY_REQUIRED` states. No automatic assumption of success on crash/unknown external outcome/persistence ambiguity. Existing recovery/invariants/consistency checks remain intact.

---

## 7. Security and boundaries

- Fail-closed authorization behavior preserved; `local_trust` remains **not authenticated identity**; no privilege escalation, no fake authenticated identity, no implicit authorization.
- Execution/child linkage (future) must not gain permissions by inheritance; this phase does not implement permission inheritance or delegation runtime.
- Hermes/JARVIS/HELIX boundaries unchanged and untouched; no lifecycle actions.

---

## 8. Compatibility notes

- Backward-compatible record loading: legacy task records without execution fields normalize safely (`current_execution_id=""`, `execution_ids=[]`).
- Existing attempt ID format/semantics preserved; receipt/journal schemas extended only additively.
- `Aj`/runtime/build accept optional `executions` store; when no persisted data dir/store is available, execution persistence is unavailable (existing in-memory/non-persisted contexts remain functional without fabricating durable execution records).
- No production storage/config/flags changed; no dependency/runtime transport/Hermes enablement.

---

## 9. Known limitations and unresolved risks (honest)

- **NTFS-backed workspace / SQLite-WAL reliability risk remains unresolved** (intermittent `disk I/O error` possible in some environments/tests historically). Not fixed; no storage relocation/config “fix” applied.
- **No cross-store atomicity**; crash windows can leave partially correlated state (tasks/executions/receipts/journal/leases).
- **No exactly-once** execution or external side-effect guarantee; ambiguous outcomes must remain `UNKNOWN` where evidence is insufficient.
- Execution lifecycle mapping in 5A.4 is **minimal/conservative** and aligned to current single-process dispatch/attempt flow; full dispatch-intent/admission/assignment/multi-execution-per-task orchestration is **not implemented** (deferred to later approved phases).
- Full restart/crash-window reconciliation across all stores and external runtimes is not exhaustively proven in this phase.
- `local_trust` is not authenticated identity; no new authn/provenance guarantees.

*Anything beyond the implemented foundation described above remains proposed/deferred unless separately implemented and verified.*
