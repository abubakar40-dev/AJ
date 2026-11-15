# 17 — Scheduler, Admission Control & Dispatch Foundation Implementation (Stage 5A.5)

**Status:** Implemented (minimal, AJ-local, single-process, non-daemon foundation). **Stage 5A.5 only.** No 5A.6 work performed.  
**Baseline:** `main@468fdcebece5b25f02e53add4928d3650ef175f4`, 49 pre-existing git status entries preserved at 5A.5 start (16 tracked M, 33 untracked). 5A.0–5A.4 docs (`00`–`16`) and 5A.2/5A.4 guidance inspected; 5A.4 COMPLETE accepted as input.  
**Boundaries preserved:** Hermes **NOT ATTACHED** (read-only boundary unchanged), `hermes gateway ensure` not implemented/enabled/executed/authorized; JARVIS/HELIX/Hermes source/runtime/config/services untouched; no real sub-agents, fan-out/aggregation, remote/multi-machine workers, agent heartbeat/runtime transport, persistent daemon/background scheduler, new runtimes, or capability escalation.

---

## 1. Actual architecture implemented

`aj/scheduler.py` now provides separated, explicit foundations (no collapsed monolith):
- **Eligibility engine:** `EligibilityDecision` + `evaluate_eligibility(task_id, ...)` (decision only; no reservation/dispatch). 
- **Admission control:** `AdmissionDecision` + `evaluate_admission(task_id, eligibility=..., selected_active, selected_waiting)` (separate from eligibility; admitted/deferred with reasons).
- **Scheduler/selection:** deterministic candidate ordering and bounded selection in `queue()`/`run_once()` with priority+aging fairness and explicit backpressure limits.
- **Dispatch:** `_dispatch_one()` records durable intent/evidence (durable mode), acquires/rechecks under existing execution lease, resumes via existing orchestrator path, records outcome evidence; bounded submission only.
- **Monitoring (observational):** `inspect()` returns counts/reasons/eligible/ineligible/admitted/deferred/active/uncertain/expired-lease indicators and dispatch-evidence summary without mutating task state.

Compatibility preserved: `Scheduler.queue(...)`, `Scheduler.run_once(limit, workers)`, and `SchedulerResult` core fields/shape remain usable by existing callers/tests; result/queue entries now carry additive decision/dispatch metadata.

## 2. Eligibility and admission contracts

**Eligibility (`eligible` / `not eligible`):** machine-readable `reason_code` + human-readable `explanation` + details. Evaluates (conservatively): task loadability, terminal/non-schedulable states, authorization/approval-required state, dependency-blocked state, deadline exceeded, active/in-flight states, recovery/manual-review conditions, active or expired/uncertain execution lease and uncertain execution state (fail closed), capability availability/blockers via existing orchestrator/registry semantics, and persistence trust for dispatch in durable mode. Not eligible merely by queue presence.

Key reason codes: `ELIGIBLE`, `TERMINAL`, `AUTHORIZATION_REQUIRED`, `RECOVERY_OR_REVIEW_REQUIRED`, `DEPENDENCY_BLOCKED`, `DEADLINE_EXCEEDED`, `ALREADY_ACTIVE_OR_UNCERTAIN`, `UNRESOLVED_DISPATCH_INTENT` (where applicable), `NOT_SCHEDULABLE_STATE`, `CAPABILITY_UNAVAILABLE`, `PERSISTENCE_UNAVAILABLE`.

**Admission (`admitted` / `deferred`, separate):** requires eligible task and trusted persistence/capacity; returns explicit reason/explanation. Conservative checks: scheduler enabled, persistence health (durable mode), trusted active-capacity count (fail closed if unknown), configured logical limits (`global_max_active_executions`, `global_max_admitted_waiting`, `max_dispatch_per_run`, `max_workers`), per-run selected accounting (backpressure), and lease conflict/uncertainty. Unknown/unhealthy/untrusted capacity or persistence => deferred/fail closed.

Admission reason codes include: `ADMITTED`, `DEFERRED_NOT_ELIGIBLE`, `DEFERRED_SCHEDULER_DISABLED`, `DEFERRED_PERSISTENCE_UNHEALTHY`, `DEFERRED_UNKNOWN_CAPACITY`, `DEFERRED_CAPACITY_ACTIVE`, `DEFERRED_CAPACITY_WAITING`, `DEFERRED_DUPLICATE_OR_LEASE_CONFLICT`.

## 3. Ordering, fairness, and backpressure

- Deterministic ordering in `queue()`: `effective_priority` desc, base `priority` desc, `created_at` asc, `task_id` asc.
- **Effective priority / starvation prevention:** bounded aging boost `+floor(wait/max(aging_seconds,∞))` (capped) when `aging_seconds > 0`; deterministic and configurable; no starvation claim beyond implemented deterministic boost.
- **FIFO within group:** stable by `created_at` then `task_id` for equal effective/base priority.
- **Backpressure/bounds:** `run_once` enforces `effective_limit = min(limit, max_dispatch_per_run)` and `effective_workers = min(workers, max_workers)`; admits/selects only within run/waiting/active bounds; no unbounded submission. `workers>1` uses a bounded `ThreadPoolExecutor` only over the explicitly selected, admitted plan (each item lease-guarded and independently evidenced).

## 4. Resource model and configuration

`aj/config.py` adds strictly-validated `scheduler` section with conservative defaults (logical, **not measured host limits**): `enabled` (bool, default `true`), `global_max_active_executions` (int>=1, default 1), `global_max_admitted_waiting` (int>=0, default 10), `max_dispatch_per_run` (int>=1, default 5), `max_workers` (int>=1, default 1), `aging_seconds` (int>=0, default 300). Malformed/unsafe values rejected by `validate()`; no unsafe coercion; external runtimes/Hermes remain disabled.

Unknown resource availability/capacity is explicit and fails closed at admission/dispatch (`DEFERRED_UNKNOWN_CAPACITY` / persistence-unhealthy handling). No monitoring dependency introduced; logical capacity is separate from observed host resources.

## 5. Dispatch lifecycle and integration (5A.4 execution + existing leases)

- **Execution domain:** reuses accepted 5A.4 `ExecutionRecord`/`ExecutionStore` and orchestrator execution linkage (`exc_*`, task↔execution correlation) via existing `aj.resume(..., leased=True)` path; no duplicate execution entity/store.
- **Leases:** reuses existing `LeaseManager` execution leases (`acquire/release`, ownership/expiry semantics) only; no second lease system.
- **Dispatch intent/evidence:** append-only `scheduler_decisions.jsonl` (durable task data dir) records `dispatch_intent`, `dispatch_deferred/aborted/error`, `dispatch_started`, `dispatch_result`, `dispatch_deadline` events with task/operation/execution context, reasons, timestamps, and lease/result details as available. In **durable mode**, intent/start evidence persistence failures fail closed (dispatch deferred/aborted, no uncertain resume). In **ephemeral in-memory task-store mode**, durable intent ledger is not applicable and compatibility dispatch behavior is preserved.
- **Conservative duplicate/crash handling:** eligibility/admission reject active/expired/uncertain lease and uncertain execution states; dispatch rechecks under claimed lease (`allow_lease_worker` for owned lease), defers on conflicts/recheck failure, and records evidence; repeated runs do not create duplicate active dispatch when state/leases are known-safe. Crash-window ambiguity remains possible across stores (no atomic multi-record operations) and is treated conservatively/represented by existing uncertainty/recovery conventions where evidence is insufficient; **no exactly-once and no cross-store atomicity claimed**.

## 6. Monitoring and recovery behavior

`inspect()` is observational (no mutation): exposes config snapshot, persistence trust, active-execution estimate, eligibility/admission/deferral counts and reason histograms, eligible/ineligible/admitted/deferred/uncertain-or-recovery lists, expired lease observations, and dispatch-evidence availability/count. Recovery remains conservative and evidence-oriented; scheduler does not silently perform recovery or mutate task state, and does not auto-repeat work on uncertain outcomes.

## 7. Known limitations

- AJ-local, single-process, bounded foundation only; no distributed scheduler, no multi-machine coordination, no daemon/always-running loop, no real sub-agent/runtime transport.
- **No exactly-once, no cross-store atomicity** across task/execution/lease/journal/receipt/evidence stores; crash windows can leave ambiguous/uncertain outcomes requiring conservative handling/manual review per existing conventions.
- **NTFS/SQLite/WAL reliability risk remains unresolved** (workspace on NTFS-mounted drive; historical intermittent I/O/WAL issues). No NTFS repair, no storage relocation/migration, no mount/config changes performed. Scheduler fails closed when durable persistence/intent evidence cannot be trusted.
- `local_trust` is not authenticated identity; no authenticated identity/cross-store guarantees added.
- Resource model is configurable/logical (not measured host CPU/RAM/IO); admission is conservative and fail-closed on unknown capacity/health.
- ExecutionStore remains minimal AJ-local append-only foundation (per 5A.4); scheduler uses existing resume/execution paths and does not implement runtime fan-out.
- Hermes/JARVIS/HELIX remain unattached/untouched; external execution flags/runtimes not enabled by this phase.

*Smallest correct, bounded, recoverable, testable 5A.5 foundation consistent with inspected AJ behavior and 5A.1–5A.4 constraints.*
