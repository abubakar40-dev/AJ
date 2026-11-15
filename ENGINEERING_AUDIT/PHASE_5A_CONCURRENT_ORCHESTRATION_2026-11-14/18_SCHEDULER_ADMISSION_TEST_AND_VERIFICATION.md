# 18 — Scheduler, Admission Control & Dispatch Foundation Test and Verification (Stage 5A.5)

**Date:** 2026-11-14  
**Scope:** 5A.5 focused verification (deterministic/bounded) plus targeted and full regression evidence. No uncontrolled concurrency/load/stress/resource-exhaustion tests run.

## 1. Test commands executed

From `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ` with `PYTHONDONTWRITEBYTECODE=1`:

- Focused (during implementation/fix): `python3 -m pytest -q tests/test_phase5a5_scheduler_admission.py` (iterative; final **12 passed**).
- Compatibility/targeted: `python3 -m pytest -q tests/test_f2_scheduler_resume.py tests/test_f2_authorization_context.py` → **18 passed**.
- Targeted regressions: `python3 -m pytest -q tests/test_orchestrator.py tests/test_foundation.py tests/test_phase3.py` → **95 passed**.
- Execution domain / gap closure: `python3 -m pytest -q tests/test_phase5a4_execution_domain.py tests/test_step_c_gap_closure.py` → **17 passed**.
- Full suite: `python3 -m pytest -q` → **533 passed, 13 warnings, 0 failures** (47.19s).
- Health/integration state: `python3 -m aj --check` → **ok: true, 23/23 checks passed, failures: []**, attached `{jarvis:false, helix:false, hermes:"NOT ATTACHED"}` (scheduler source reported `default`).

## 2. Focused 5A.5 scenarios covered (`tests/test_phase5a5_scheduler_admission.py`)

| Scenario | Evidence | Result |
|---|---|---|
| Eligible task identified correctly (reason/explanation) | `test_eligible_task_identified_correctly` | PASS |
| Unauthorized/waiting-for-approval not eligible | `test_unauthorized_and_terminal_and_dependency_blocked_not_eligible` | PASS |
| Dependency-blocked task not eligible (reason) | same | PASS |
| Terminal task not eligible | same | PASS |
| Already running/active execution-lease task not dispatched again (duplicate prevention) | `test_already_running_or_active_lease_not_dispatched_again` | PASS |
| Eligible task admitted with explicit reasons | `test_admission_success_and_reasons` | PASS |
| Capacity exhaustion defers admission with reason | `test_capacity_exhaustion_defers_admission` | PASS |
| Unknown capacity fails closed | `test_unknown_capacity_and_persistence_failure_fail_closed` | PASS |
| Persistence/dispatch-evidence failure fails closed (durable mode), no unsafe progression | same | PASS |
| Deterministic priority ordering | `test_deterministic_priority_fifo_and_fairness_aging` | PASS |
| FIFO within applicable priority/effective group | same | PASS |
| Aging/starvation prevention (deterministic boost) | same | PASS |
| Admission/dispatch decisions include explicit reasons and evidence | dispatch/admission tests + `test_dispatch_uses_5a4_execution_domain_reuses_leases_and_records_reasons` | PASS |
| Dispatch uses accepted 5A.4 execution domain and records linkage/evidence | same | PASS |
| Existing leases reused / lease-guarded dispatch | active-lease and dispatch tests | PASS |
| Repeated scheduler runs do not create duplicate active executions/dispatch | `test_dispatch_uses_5a4_execution_domain_reuses_leases_and_records_reasons` | PASS |
| Bounded concurrency/backpressure and run limits respected | `test_bounded_concurrency_backpressure_and_monitoring` | PASS |
| Monitoring exposes useful eligibility/admission/dispatch/recovery-related counts/reasons (observational) | same | PASS |
| Recovery-required and expired/uncertain lease not blindly redispatched | `test_recovery_required_and_expired_lease_not_blindly_eligible` | PASS |
| Deadline-exceeded task not eligible | `test_deadline_exceeded_ineligible` | PASS |
| Legacy/task records loadable; external runtime/Hermes remains not attached | `test_legacy_records_loadable_and_no_external_runtime_enabled` | PASS |

**Notes on bounded scope:** tests are deterministic, single-process, and use temporary/local durable data dirs; bounded worker/dispatch settings only. Concurrent-dispatch safety is exercised conservatively via lease/eligibility/recheck/repeated-run guards and bounded pool behavior (not via uncontrolled stress). Crash-window uncertainty and non-atomic multi-store behavior are handled conservatively and not claimed as atomic/exactly-once.

## 3. Regression evidence

- `tests/test_f2_scheduler_resume.py`, `tests/test_f2_authorization_context.py`: preserved compatibility for scheduler queue/run_once and authorization/resume boundaries (**18 passed**).
- Core/foundation/orchestrator/phase3/step-c and 5A.4 execution domain suites: **112 passed** across targeted groups.
- **Full suite:** `533 passed, 13 warnings, 0 failures` (includes all existing and newly added 5A.5 tests).

## 4. Storage/environment notes

- Tests executed in repository environment using temporary test storage where applicable (pytest tmp paths) and AJ-local stores; no aggressive write/concurrency tests run on the NTFS workspace.
- Known unresolved risk remains: workspace resides on NTFS-mounted drive with historical intermittent SQLite/WAL `disk I/O` sensitivity; no NTFS repair, storage migration, or mount/config changes performed. Implementation fails closed when durable persistence/intent evidence cannot be trusted.

## 5. Failures/warnings and disposition

- No test failures in final focused, targeted, or full runs. No assertions weakened, no tests skipped/altered to obtain green results.
- Warnings observed in full run (unchanged class): PyGIDeprecationWarning from system `gi/overrides`, and `DeprecationWarning: fork()` in multi-threaded process from phase3 multiprocessing tests (12 warnings) — pre-existing/environment-related; not introduced by 5A.5.

## 6. Evidence supporting key claims

- **Explicit separate eligibility/admission:** decision objects/reason codes in `aj/scheduler.py`; tests assert codes/reasons and separation.
- **Fail-closed:** unknown capacity and durable persistence/evidence failure paths defer/block unsafe dispatch (`DEFERRED_UNKNOWN_CAPACITY`, intent/evidence append failure handling) with no state progression.
- **Deterministic ordering/fairness/backpressure:** queue sort and aging logic + bounded effective limits/workers asserted.
- **5A.4 execution/lease reuse, no duplicate dispatch:** `exc_*` linkage, execution store reads, repeated-run non-duplication, active/expired lease ineligibility.
- **No external runtime enablement:** `aj --check` and legacy/runtime assertion confirm Hermes `NOT ATTACHED`; JARVIS/HELIX untouched.
- **No exactly-once/cross-store atomicity claims:** documented in implementation/report and reflected in conservative behavior.
