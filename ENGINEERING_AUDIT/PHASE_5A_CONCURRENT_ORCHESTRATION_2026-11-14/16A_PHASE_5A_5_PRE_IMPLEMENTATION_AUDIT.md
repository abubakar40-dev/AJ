# 16A — Phase 5A.5 Pre-Implementation Audit (Scheduler, Admission Control & Dispatch Foundation)

**Date:** 2026-11-14  
**Stage:** 5A.5 (audit-before-implementation)  
**Status:** Complete for 5A.5 entry; implementation follows this audit.

## 1. Baseline and Git safety (verified)
- Repo: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`, branch `main`, HEAD `468fdcebece5b25f02e53add4928d3650ef175f4` (unchanged).
- Git status at 5A.5 start: **49 entries** (16 tracked modified, 33 untracked), preserving all pre-5A.5/pre-existing work including 5A.4 implementation and prior audit artifacts/modules/tests. No staging/commit/push/merge/rebase/reset/clean planned.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` → **ok:true, 23/23, failures:[]**, attached `{jarvis:false, helix:false, hermes:"NOT ATTACHED"}`.
- Protected repos (JARVIS, helix copies, Hermes agent) untouched; Hermes NOT ATTACHED, `gateway.ensure` unauthorized/not implemented/not executed.

## 2. Accepted inputs inspected
- 5A.1–5A.4 decision registers/verification: `02`–`05`, `06`–`09`, `10`–`13`, `14_EXECUTION_DOMAIN_IMPLEMENTATION.md`, `15_EXECUTION_DOMAIN_TEST_AND_VERIFICATION.md`, `16_PHASE_5A_4_VERIFICATION_REPORT.md` (and 5A.0 `00`,`01` context). 5A.4 COMPLETE (521 passed, 13 warnings, 0 failures historically recorded).
- Key constraints: AJ-local foundation only, no cross-store atomicity, no exactly-once/external guarantees, NTFS/SQLite-WAL reliability unresolved, fail-closed on uncertainty, reuse 5A.4 `ExecutionRecord`/`ExecutionStore` and existing `LeaseManager`, no duplicate systems, Hermes/JARVIS/HELIX boundaries unchanged.

## 3. Current implementation traced (source-backed)
- **Scheduler (`aj/scheduler.py`):** in-process deterministic helper `SchedulerResult`, `queue()` (lists `AUTHORIZED`/`BLOCKED`, priority sort desc + task_id), `_run_one()` acquires execution lease then `aj.resume(task_id, leased=True)` with deadline dead-letter attempt, `run_once(limit, workers)` uses fixed batch and optional `ThreadPoolExecutor` over selected IDs. No admission controller, no resource model/backpressure, no durable scheduler state/dispatch ledger, no starvation protection/aging/fairness beyond sort, no explicit eligibility/admission decisions or reason-coded API, release errors swallowed, no heartbeat renewal in scheduler.
- **Task lifecycle/authz/deps (`aj/task.py`, `aj/orchestrator.py`):** states `RECEIVED/UNDERSTANDING/PLANNED/WAITING_FOR_APPROVAL/AUTHORIZED/EXECUTING/VERIFYING/COMPLETED/FAILED/RECOVERING/RETRYING/ESCALATED/ABORTED/CANCELLED/RECOVERY_REQUIRED/CANCEL_REQUESTED/BLOCKED/DEAD_LETTER`; `unsatisfied_dependencies` checks missing/non-COMPLETED/cycle members; `handle/resume/_resume_locked` enforce routing/authz/capability/policy/stale-authorization and dependency blocking/promotion paths; scheduler dispatch relies on `AUTHORIZED` and `resume`.
- **Execution domain (5A.4, `aj/execution_domain.py`, orchestrator integration):** AJ-owned `exc_*`, `ExecutionStore` append-only JSONL fail-closed, execution lifecycle/states, task↔execution↔attempt linkage and additive correlation; `LeaseManager` preserved (per-task leases, execution/operation families, flock+atomic writes, expiry/ownership semantics).
- **Evidence/persistence:** `tasks.jsonl`, `journal.jsonl`, `receipts.jsonl`, `executions.jsonl`, leases, idempotency/operation evidence/memory stores; cross-store non-atomic; storage diagnostics note NTFS/WAL/POSIX locking sensitivity.
- **Config/runtime (`aj/config.py`, `aj/runtime.py`):** strict known sections/defaults, no `scheduler` section today; runtime builds Aj/stores/execution adapter (Hermes gated/default-deny/unattached).
- **Tests/callers:** `tests/test_f2_scheduler_resume.py` (expects scheduler executes authorized read-only task and resume boundary behavior), `tests/test_f2_authorization_context.py` imports scheduler; CLI/orchestrator resume paths reference scheduler-owned progression semantics. Existing APIs/return shapes must remain compatible.

## 4. Gaps vs 5A.5 requirements (from audit/architecture)
- No explicit **eligibility** decision object/API (eligible/not eligible + machine-readable reason + explanation).
- No separate **admission** decision (admitted/deferred + reasons), no conservative capacity/resource/backpressure model, no fail-closed on unknown/unhealthy/untrusted persistence/capacity.
- No durable/explicit **dispatch intent/admission evidence** ledger integrated with scheduler decisions; duplicate-dispatch prevention relies on leases/task state but not fully reasoned/recorded for crash windows.
- Ordering deterministic by priority+task_id but no fairness/aging/starvation protection, no bounded admission/dispatch queues, `workers>1` permits unbounded-style batch submission pattern relative to policy (needs explicit bounds/backpressure).
- No scheduler monitoring/inspection view for eligibility/admission/deferral/dispatch/recovery reasons and counts (beyond basic queue/run_once result).
- Config has no validated scheduler capacity/backpressure settings.

## 5. Compatibility and safety constraints for implementation
- Preserve task lifecycle/state vocabulary and authorization/lease/execution semantics; do not bypass state machine/capability checks; do not create duplicate execution/lease systems.
- Keep `Scheduler` public API/behavior compatible for existing callers/tests (`queue`, `run_once`, `SchedulerResult` fields/shape, authorized-task execution path).
- Fail closed on persistence/read/validation/lease/capacity uncertainty; represent ambiguous crash outcomes honestly (`RECOVERY_REQUIRED`/unknown-equivalent handling per existing conventions) and never auto-repeat uncertain external side effects.
- Bounded, deterministic, single-process, no daemon/background loop, no distributed/multi-machine coordination, no uncontrolled concurrency tests, no Hermes/JARVIS/HELIX/runtime transport enablement.
- Add conservative, strictly-validated config (new `scheduler` section) with safe defaults; do not enable external execution.
- NTFS/SQLite/WAL reliability remains unresolved and must be documented; fail closed when durable intent/evidence cannot be trusted.

## 6. Minimal implementation plan (5A.5)
1. **Eligibility engine:** explicit evaluator returning structured decision (eligible/not eligible, reason_code, explanation, details) over existing task/load/authz/dependency/terminal/active-execution/lease/recovery/persistence-availability conditions.
2. **Admission control:** separate admitted/deferred decisions with reasons using conservative configurable capacity abstractions (logical slots/limits, bounded queues), unknown/unavailable/unhealthy => fail closed/defer; explicit backpressure (no unbounded submission).
3. **Deterministic scheduling/fairness:** priority bands or equivalent deterministic ordering + FIFO within group + simple aging/starvation prevention, explainable selection/deferral; bounded worker execution.
4. **Dispatch/leases/execution integration:** reuse `ExecutionStore`/`ExecutionRecord` and `LeaseManager`; persist append-only scheduler/dispatch decision evidence (ledger/events) for intent/reasons; prevent duplicate active dispatch conservatively; handle crash-window uncertainty without claiming atomicity/exactly-once.
5. **Recovery/monitoring:** observational inspection API/view (counts/reasons/active/uncertain/expired-lease/stuck/recovery hints) without mutating state.
6. **Config/tests/docs:** strict validated `scheduler` config; focused deterministic tests for required scenarios + regressions; `17`/`18`/`19` docs and evidence.

*This audit is evidence-backed and conservative; implementation will follow inspected code/contracts and will not claim guarantees beyond evidence.*
