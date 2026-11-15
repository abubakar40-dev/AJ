# 06 — Scheduler & Admission Control Audit (Stage 5A.2)

**Status:** Source-backed audit of **current** AJ implementation (not proposed design). Stage 5A.2 is audit/design/verification only.  
**Baseline:** `main@468fdcebece5b25f02e53add4928d3650ef175f4`, 45 pre-existing git status entries preserved at stage start (14 tracked M, 31 untracked incl. prior phase/5A artifacts). 5A.0 (`00`,`01`) and 5A.1 (`02`–`05`) read. 4B.3/4B.4 (`00_PHASE_4B_4_MASTER_READINESS_REPORT.md`)/4B.5/4B.6 masters reviewed for scheduling/execution/persistence/security/recovery constraints.  
**Evidence basis (inspected):** `aj/scheduler.py`, `aj/task.py`, `aj/orchestrator.py` (routing/handle/resume/dependency/lease/deadline/dead-letter/authz paths), `aj/execution.py`, `aj/runtime.py`, `aj/lease.py`, `aj/recovery.py`, `aj/idempotency.py`, `aj/operation_evidence.py`, `aj/consistency.py`, `aj/invariants.py`, `aj/permissions.py`, `aj/authorization.py`, `aj/storage_diagnostics.py`, `aj/memory.py`, `aj/agents.py`, `aj/diagnostics.py`, `aj/__main__.py`; tests `tests/test_f2_scheduler_resume.py`, `tests/test_f2_authorization_context.py` (referenced), `tests/test_orchestrator.py`, `tests/test_phase3.py` (dependency/cycle evidence via grep), `tests/test_phase3_lifecycle_reliability.py`, `tests/test_phase3c_recovery_integrity.py`, `tests/test_phase3d_recovery_observability.py`, `tests/test_phase3e_evidence_consistency.py`, `tests/test_phase3f_identity_trust_boundary.py`, `tests/test_task_persistence_fail_closed.py`.

**Classification labels:** *Fully implemented and verified; Partially implemented; Interface-only; Process-local only; Mock/test-only; Missing; Unverified.* (Where confidence is limited, stated explicitly.)

---

## 1. Current scheduler implementation (actual)

### 1.1 Components and entry points
| Component | File / symbols | Actual behavior |
|---|---|---|
| Scheduler helper | `aj/scheduler.py`: `Scheduler`, `SchedulerResult`, `queue()`, `_run_one()`, `run_once()` | Deterministic in-process dispatcher over durable `TaskStore`. Claims execution lease before resuming. No persistent daemon, no admission controller, no resource manager, no worker supervisor, no persistent scheduler state. |
| Task eligibility inputs | `aj/task.py` states/`TRANSITIONS`; `aj/orchestrator.py::Aj.unsatisfied_dependencies`, `Aj.handle`, `Aj.resume/_resume_locked` | Eligibility/dispatch gated by task state, dependency satisfaction, deadline, authorization/policy/capability checks, and lease acquisition. |
| Execution claim/ownership | `aj/lease.py`: `LeaseManager.acquire/acquire_execution/release/release_execution/hold`, file-backed leases (`leases/*.json`, flock/RLock), `ACTIVE/RELEASED/STALE/EXPIRED`-derived | Execution lease (`operation="execute"`) per task; heartbeat/renew/expiry semantics exist; ownership enforced on release/renew. |
| Recovery/scan | `aj/recovery.py::RecoveryManager.scan/classify/recover`, `Aj._assess_recovery` (orchestrator) | Read-only classification over non-terminal tasks; batch auto-recovery only for `replay_safe`; single-task recovery delegates to orchestrator evidence-based path. Not scheduler-driven. |
| Persistence/evidence | `aj/task.py` (append-only `tasks.jsonl`), `aj/journal.py`, `aj/receipts.py`, `aj/idempotency.py`, `aj/operation_evidence.py`, `aj/memory.py` | Durable records exist but cross-store operations are not atomic; storage reliability on NTFS/WAL is a known risk. |

### 1.2 How a task becomes eligible (current, observed)
- **Created/accepted:** `Aj.handle()` creates task (`RECEIVED`), persists metadata, routes, moves `RECEIVED→UNDERSTANDING→PLANNED` (`aj/orchestrator.py`).
- **Dependency blocking at intake:** if `unsatisfied_dependencies(record)` non-empty, task transitions to `BLOCKED` with audit/journal/memory; handle returns non-ok outcome (not failed).
- **Authorization/admission-like gate (not a scheduler admission controller):** capability block/policy checks run; `CONFIRM` → `WAITING_FOR_APPROVAL`; `DENY/forbidden/unavailable` → `ABORTED`/`FAILED` per paths; `ALLOW` → `AUTHORIZED` with computed `authorization_context` persisted.
- **Scheduler queue view (`Scheduler.queue`):** scans `self.aj.tasks.all()` and includes only records with status in `{AUTHORIZED, BLOCKED}`. Adds `reason` for blocked deps (`waiting for ...`) or overdue deadline (`deadline exceeded`). `eligible` field computed as `not reason or reason.startswith("waiting") is False` (i.e. dependency-waiting treated as ineligible; overdue/deadline reason may appear eligible by this expression but `run_once` filters overdue out) — **semantics are mixed/presentation-oriented, not a formal admission state**.
- **Scheduler dispatch set (`Scheduler.run_once`):** candidates = queued rows where `row["status"] == AUTHORIZED` and not overdue (`deadline <= now` filtered out). Selected = first `limit` of those candidates in queue order. `BLOCKED` rows are never dispatched by `run_once` even if dependency-waiting annotation changes; blocked tasks become dispatchable only after `resume`/re-authorization moves them to `AUTHORIZED`.
- **Resume/re-evaluation (`Aj.resume/_resume_locked`):** under execution lease (or caller-held when `leased=True`) promotes eligible `BLOCKED` (deps satisfied) through `PLANNED` → authorization; may move to `WAITING_FOR_APPROVAL`/`ABORTED`/`AUTHORIZED`. Also handles `PLANNED` and `AUTHORIZED` continuation paths with stale-authorization/capability checks; consequential/approval-bound stale context fails closed (`RECOVERY_REQUIRED`/no side effect).

### 1.3 Which task states can be scheduled/dispatched
- **`Scheduler.run_once` dispatches:** only `AUTHORIZED` candidates passing deadline filter. **Classification:** Implemented (basic), **Unverified** as complete concurrency-safe dispatch semantics.
- **`Scheduler.queue` lists:** `AUTHORIZED` and `BLOCKED` (visibility/reporting). Not all queued are dispatchable.
- **`Aj.resume` can be invoked directly:** can operate on `BLOCKED`, `PLANNED`, `AUTHORIZED` (and possibly other paths depending on orchestrator logic) — broader than scheduler dispatch; authorization/lease/guards apply. **Interface/process-local behavior, partially implemented.**

### 1.4 How `run_once` works (actual)
1. Builds `candidates` from `queue(limit=0)` filtered to `status==AUTHORIZED` and not overdue.
2. `selected = candidates[:limit]` task IDs (queue order: priority desc, then `task_id`).
3. If `workers > 1` and `len(selected) > 1`: executes `_run_one` over selected via `ThreadPoolExecutor(max_workers=workers)` and `pool.map` (blocks until mapped calls complete within context).
4. Else: sequential `_run_one` per selected task.
5. Returns `{worker_id, selected, results, completed, failed}`; no durable scheduler cursor/state persisted.

**`_run_one(task_id)`:** acquires execution lease (`self.aj.leases.acquire(task_id,"execute",worker_id=...)`); on lease `AjError` returns `SKIPPED/ok=False`. Re-reads task; if deadline exceeded at execution time calls `Aj.dead_letter(task_id,"deadline exceeded before execution")` and returns failure result (note: `dead_letter` requires `RECOVERY_REQUIRED` in implementation paths seen via grep/CLI reconciliation semantics — **behavior consistency for deadline path is unverified from inspection alone**). Otherwise calls `aj.resume(task_id, leased=True)`, returns outcome. Catches `AjError` as `FAILED`. Always attempts lease release in `finally` (swallows release errors).

### 1.5 Leases: acquisition, ownership, expiry, release
- **Acquisition (`Scheduler`):** uses generic `LeaseManager.acquire(task_id,"execute")` → `acquire_execution` returning `(lease,newly_acquired)`; scheduler keeps lease object. Same worker renewing own valid lease updates heartbeat/expiry; different worker blocked by `LeaseHeld`; expired execution lease raises `LeaseExpired` (no silent mutation).
- **Scope:** one lease record per task (`leases/<stem>.json`), not per execution instance; execution lease identifies current owning worker/heartbeat. Operation leases (`cancel/retry/recover`) are distinct and can block conflicting acquisition of different operation types.
- **Release:** `Scheduler` calls `lease_mgr.release(lease)` in `finally` (auto-detects type). Failures swallowed in scheduler path → potential stuck-active lease record risk (mitigated only by expiry semantics/recovery logic elsewhere). **Unverified** end-to-end leak handling.
- **Expiry detection:** `Lease.expired(now)` / `LeaseManager.get/list` mark active expired as `EXPIRED` in returned view; file state remains `ACTIVE` until mutated. `acquire_execution` on expired active execution lease raises `LeaseExpired` rather than breaking it; operation leases similarly require explicit break-stale in some flows (`break_stale_operation` exists).
- **Persistence/guarding:** per-task flock + atomic temp-replace writes when `base_dir` set; in-memory fallback when none. History appended to `lease-history.jsonl` (best-effort around audit/journal hooks).

### 1.6 Worker count and `ThreadPoolExecutor` semantics
- `worker_id` default `scheduler-{time.time_ns()}` (process-local logical label). `run_once(workers=...)` default 1.
- `workers > 1` uses `concurrent.futures.ThreadPoolExecutor(max_workers=workers)` inside a context manager for that `run_once` call; tasks are submitted as `pool.map(_run_one, selected)` over a preselected fixed list (no dynamic work-stealing/admission loop, no queue refill within run).
- **Provides genuine independent concurrent task execution?** **Partially (in-process threads only):** multiple `_run_one` calls may run concurrently in the same process and may dispatch different tasks if each acquires its own per-task execution lease. This is **not** equivalent to a verified concurrent orchestration system (no process isolation, no backpressure, shared mutable in-memory/runtime state, shared stores/locks contention, no supervision beyond per-task try/except, no capacity/resource checks, NTFS/SQLite I/O contention risk). **Classification:** Partially implemented, process-local, **unverified** for safe sustained concurrency.
- **Worker failure:** exceptions from `aj.resume` caught in `_run_one` as `AjError` → failed result; non-`AjError` exceptions not explicitly handled inside `_run_one` (could propagate from thread to `map` result retrieval depending on path) — **unverified**. Thread pool scope ends at `run_once` return.

### 1.7 Dependencies, priority, deadlines
- **Dependencies:** `TaskRecord.depends_on` (task IDs). `Aj.unsatisfied_dependencies` returns deps that are in detected cycle set, missing, or not `COMPLETED` (uses DFS cycle detection over dependency subgraph present in dep set; expands predecessors of cycle nodes). `Aj.handle`/`resume` block on unsatisfied deps; `Scheduler.queue` annotates waiting deps for `BLOCKED` tasks.
- **Can blocked tasks become eligible later?** Yes in principle when dependencies become satisfied and `resume` (explicit/scheduler-driven only if re-authorized to `AUTHORIZED` by some path) promotes state; `run_once` does not auto-reevaluate `BLOCKED` tasks for dispatch — it only dispatches current `AUTHORIZED` candidates. **No dependency-completion event triggers scheduler wake-up.**
- **Priority enforced?** `Scheduler.queue` sorts by `(-priority, task_id)` and `run_once` takes prefix of filtered authorized candidates → coarse priority ordering at selection time. **Partially implemented; no starvation prevention/aging/fairness.**
- **Deadlines:** stored on task (`deadline` float timestamp). `queue` marks overdue reason; `run_once` excludes overdue candidates and `_run_one` rechecks and attempts `dead_letter` before resume. **No earliest-deadline-first policy; deadline enforcement interacts with task-state requirements for `dead_letter` (unverified).**

### 1.8 Persistent scheduler state / restart behavior
- **Persistent scheduler state:** **None found** (no scheduler queue/cursor/admission/dispatch ledger; selection computed from task store each call).
- **Survives process restart:** task records, leases, journal, receipts, idempotency, operation evidence persist (subject to storage reliability). In-flight thread-pool work, process-local worker identity, and any unflushed in-memory runtime state do **not** survive. Recovery is separate (`RecoveryManager`/`Aj.recover`) and conservative.

### 1.9 Other relevant observations
- **`aj resume <task> --execute` CLI:** `cmd_task` resumes without `leased=True` (acquires lease internally), then executes via `_execute_task` — separate path from scheduler; no admission control.
- **No `cancel` path in scheduler:** cancellation handled by orchestrator/CLI/task store semantics (not audited as complete concurrent cancellation here).
- **Capability/permission/authorization:** enforced in `Aj.handle/resume`/dispatch paths (`_capability_blocker`, `Authorizer`, `authorization_context`, stale-authorization fail-closed). Scheduler itself performs no independent permission check beyond relying on `AUTHORIZED` state and `resume` behavior.
- **Storage diagnostics (`aj/storage_diagnostics.py`):** read-only; notes WAL/concurrent writer sensitivity on external/network mounts and NTFS-like issues. `aj/memory.py` uses SQLite WAL.

---

## 2. Current scheduler limitations and capability classification

| Capability | Classification | Evidence / notes |
|---|---|---|
| Deterministic selection over durable task store (`queue`, priority sort) | **Partially implemented** | `aj/scheduler.py:queue/run_once`; deterministic given same store state/order fields. |
| Lease-guarded per-task dispatch claim (`acquire execute` before `resume`) | **Partially implemented** | `Scheduler._run_one`, `LeaseManager.acquire_execution`; per-task only, expired/stale edge cases complex. |
| Optional in-process multi-worker dispatch (`ThreadPoolExecutor`) | **Partially implemented / Process-local only** | Same-process threads, fixed batch, no supervision/backpressure/resource isolation. |
| Genuine concurrent orchestration (multi-task, multi-execution, supervised) | **Missing** | No admission/resource/worker-manager/execution entities/graph execution. |
| Admission control (separate from auth/task creation/execution) | **Missing** | No admission state/entity/decision log/budget checks. `AUTHORIZED` is task lifecycle, not capacity admission. |
| Concurrency/capacity limits (global/scoped/resource-aware) | **Missing** | Only caller-supplied `limit/workers`; no enforcement, no dynamic limits, no per-capability/agent/runtime limits. |
| Resource-aware scheduling/backpressure (CPU/RAM/disk/IO/SQLite health) | **Missing** | No probes, no admission gating, no pressure response. |
| Dependency-aware execution graph / event-driven unblocking | **Partially implemented** | `depends_on` checks, cycle detection, `BLOCKED` transitions; no scheduler wake-up/graph progression engine/typed deps. |
| Priority/fairness/starvation prevention | **Partially implemented** (priority only) / **Missing** (fairness/aging) | Static sort key; no quotas/aging/deadline-aware fairness. |
| Persistent scheduler/admission/dispatch state | **Missing** | Recomputed per call. |
| Duplicate-dispatch prevention across processes/runs | **Partially implemented** | Relies on per-task execution leases + durable task states; not proven comprehensive under races/storage faults. |
| Recovery integration after interruption | **Partially implemented** | Separate recovery subsystem exists; scheduler does not coordinate in-flight ambiguity; `run_once` not restart-safe orchestration loop. |
| Monitoring/observability of scheduler health/capacity/pressure | **Missing** (scheduler-specific) / **Partially implemented** (general diagnostics) | No scheduler metrics/events beyond return payload; general stores/diagnostics exist. |
| Deadline/timeout policy coherence | **Partially implemented / Unverified** | Deadline checks + `dead_letter` attempt; interaction with allowed transitions/lease/state needs verification. |
| Cancellation-aware scheduling/execution | **Missing** (in scheduler) | Scheduler ignores non-AUTHORIZED; running-task cancellation semantics external/unclear. |

**Critical non-equivalences (must hold):** multiple threads ≠ complete concurrent orchestration; multiple authorized tasks ≠ admission control; a lease ≠ complete distributed worker-ownership protocol; task state ≠ scheduler/admission state; configured worker count ≠ safe resource management; successful unit test ≠ reliable long-running execution.

---

## 3. Existing concurrency behavior — required scenario analysis

| # | Scenario | Verified behavior (source-backed) | Uncertainty / limitations |
|---|---|---|---|
| 1 | Two independent tasks are eligible simultaneously | `run_once` selects multiple `AUTHORIZED`, non-overdue candidates (sorted) up to `limit`; with `workers>1` may dispatch via ThreadPoolExecutor, each `_run_one` acquires per-task execution lease then calls `resume(..., leased=True)` (`aj/scheduler.py`). | Correctness under real parallel resume/store contention and external effects **unverified**; shared-process state; no admission/capacity/resource control. |
| 2 | More tasks are eligible than configured workers | Only `selected = candidates[:limit]`; within selected batch, parallelism capped by `max_workers=workers` in `pool.map` over fixed list. Remaining eligible tasks wait for later `run_once` call. | No persistent queue position/admission fairness/backpressure; starvation possible. |
| 3 | Two scheduler invocations overlap | No global scheduler lock observed. Each invocation independently computes candidates and attempts per-task execution lease acquisition; `LeaseHeld/LeaseExpired` -> task `SKIPPED` in that run. | Races around selection/read/write timing, duplicate attempts to claim, and lease release failures **possible/unverified**; no coordination or idempotent dispatch record. |
| 4 | Two AJ processes attempt to schedule the same task | File-backed leases use flock-guarded per-task paths and atomic writes (`aj/lease.py`), so only one holder should acquire active execution lease at a time under correct FS locking. | Correctness depends on filesystem/lock semantics (NTFS caveat) and consistent store views across processes; **unverified** end-to-end. |
| 5 | A worker exits unexpectedly | No worker supervisor. If thread dies mid-`_run_one`, lease may remain `ACTIVE` until expiry/explicit handling; `finally` may not run on hard termination. Recovery/reconciliation handled separately and conservatively. | Active in-flight side effects may be unknown; duplicate/stranded work risk; **no automatic safe reschedule proof**. |
| 6 | A lease expires while execution is still active | Execution lease expiry is time-based (`DEFAULT_TTL=30s`, renew supported by API but scheduler does not renew). `acquire_execution` rejects expired active lease with `LeaseExpired`; `renew_execution` requires non-expired active owned lease. Recovery logic treats expiry/ownership as evidence-sensitive. | Scheduler holds lease without heartbeat renewal during `resume`/execution; long-running work can outlive TTL causing expiry/ownership ambiguity. **High risk / unverified safe behavior.** |
| 7 | A task becomes blocked by a dependency | `Aj.handle` detects unsatisfied deps and transitions to `BLOCKED`; scheduler lists blocked with waiting reason but does not dispatch. `Aj.resume` on blocked requires deps satisfied and re-authorizes. | Dependency satisfaction propagation is passive (checked when paths run), not event-driven. |
| 8 | A dependency completes while the scheduler is idle | No push/wakeup. Dependent task remains `BLOCKED` until a future `handle/resume/run_once`-adjacent path or explicit resume re-evaluates and promotes it (subject to authorization). | Latency/unbounded wait until next poll/manual action. |
| 9 | A task is cancelled while queued | `run_once` selects only current `AUTHORIZED` rows at selection time; if task state changes before dispatch, dispatch still targets selected task ID and `resume`/orchestrator paths apply current-state rules. `BLOCKED` queued tasks not dispatched. | No cancellation-aware dequeue/admission revocation; race window between selection and claim/resume. **Unverified** for all states. |
| 10 | A task is cancelled while running | Scheduler has no running-task cancellation control; execution lease represents ownership, not a preemptive cancellation protocol. Orchestrator/task states include `CANCEL_REQUESTED` transitions in model, but cooperative/forced cancellation of in-flight work (esp. external) is not evidenced in scheduler. | Outcome may be ambiguous; local process stop ≠ remote stop. **Unverified.** |
| 11 | A process restarts while work is active | Durable stores/leases/journal/receipts survive (storage-dependent). In-process execution, thread pool, and live worker context lost. Recovery scan/classification is conservative/fail-closed; replay only when evidenced safe. | Ambiguous external/in-flight outcomes remain possible; no scheduler-owned restart reconciliation. |
| 12 | Persistence fails during task scheduling or completion | Task store operations fail closed/reconcile to last durable state in tested paths (`test_task_persistence_fail_closed.py`); journal/receipt/idempotency/lease writes can error per component behavior. Scheduler swallows lease release errors and returns `AjError` failures for some cases. | Partial/cross-store inconsistency possible (no ACID across stores); scheduler may have attempted/recorded ambiguous progress. **Must not assume durable intent recorded; must not silently discard work.** |

---

## 4. Readiness constraints relevant to 5A.2 (from 4B.3–4B.6)
- **Hermes boundary:** read-only `hermes.status.read` only, default-disabled/fail-closed, `local_trust` non-authenticated, AJ↔Hermes NOT ATTACHED. `hermes.gateway.ensure` **not implemented/enabled/executed/authorized** (4B.4 CONDITIONAL GO for design consideration only; 4B.5 COMPLETE/CONDITIONAL GO; 4B.6 COMPLETE/CONDITIONAL GO, design/mock-only, production implementation NO). Scheduler/admission design must remain compatible but must not assume lifecycle control or attached Hermes execution.
- **Security/trust:** deny-by-default/explicit permissions/authorization boundaries; fixed-argv no-shell invariants for Hermes boundary preserved; no fabricated external IDs/outcomes.
- **Persistence/storage:** cross-store non-atomicity accepted risk; NTFS-backed workspace/SQLite WAL intermittent `disk I/O error` risk unresolved (4B.3/4B.5/4B.6). Critical scheduling guarantees must not depend on unverified storage behavior.
- **Resources:** 8 GB / 2C4T laptop context (4B.6 resource posture provisional/unmeasured); avoid designs that assume abundant memory/CPU/disk or local services.

---

## 5. Audit conclusions (Stage 5A.2, current state)
- AJ has a **basic deterministic, lease-aware local dispatch helper** (`Scheduler`) and supporting primitives (task lifecycle, leases, recovery, evidence stores), but **no admission control, no resource-aware capacity model, no supervised concurrent execution architecture, no persistent scheduler state, and no proven safe multi-execution orchestration**.
- `ThreadPoolExecutor` with `workers>1` enables limited in-process parallel dispatch attempts but does **not** constitute safe resource-managed, restart-safe, or externally-consistent concurrency.
- Storage unreliability on NTFS/WAL, lack of cross-store atomicity, and implicit execution/attempt modeling constrain any future scheduler guarantees and require fail-closed, evidence-honest design.
