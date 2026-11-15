# 06 Tests and Baseline Run (read-only)

## Test files and test counts per file

**Command:** `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest --collect-only -q 2>&1 | tee _context_pack/_tmp_collect.txt`  
**Result (tail):** `577 tests collected in 1.02s` (warnings shown in saved output).

**Command (per-file count):** `grep -c "^def test_" tests/test_*.py`

| Test file | `def test_` count |
|---|---:|
| `tests/test_audit_reliability_security.py` | 5 |
| `tests/test_calling.py` | 10 |
| `tests/test_crash_safety.py` | 14 |
| `tests/test_dead_letter.py` | 19 |
| `tests/test_f2_authorization_context.py` | 12 |
| `tests/test_f2_permission_enforcement.py` | 11 |
| `tests/test_f2_scheduler_resume.py` | 6 |
| `tests/test_f4_audit_enforcement.py` | 4 |
| `tests/test_f5_memory_proofs.py` | 7 |
| `tests/test_foundation.py` | 21 |
| `tests/test_hermes_contract.py` | 8 |
| `tests/test_idempotent_replay.py` | 16 |
| `tests/test_inbox_subprocess_recovery.py` | 1 |
| `tests/test_knowledge_inbox.py` | 3 |
| `tests/test_knowledge_inbox_resilience.py` | 6 |
| `tests/test_memory.py` | 6 |
| `tests/test_orb_non_gui.py` | 7 |
| `tests/test_orb_web_integration.py` | 5 |
| `tests/test_orchestrator.py` | 13 |
| `tests/test_path_config_hardening.py` | 9 |
| `tests/test_phase2.py` | 11 |
| `tests/test_phase3c_recovery_integrity.py` | 9 |
| `tests/test_phase3d_recovery_observability.py` | 16 |
| `tests/test_phase3e_evidence_consistency.py` | 11 |
| `tests/test_phase3f_identity_trust_boundary.py` | 9 |
| `tests/test_phase3_lifecycle_reliability.py` | 10 |
| `tests/test_phase3.py` | 43 |
| `tests/test_phase4b1_hermes_adapter.py` | 9 |
| `tests/test_phase4b1_hermes_security_faults.py` | 4 |
| `tests/test_phase4b2_reliability_hardening.py` | 10 |
| `tests/test_phase4b3_security_assurance.py` | 16 |
| `tests/test_phase4b6_gateway_ensure_design_isolated.py` | 9 |
| `tests/test_phase5a4_execution_domain.py` | 9 |
| `tests/test_phase5a5_scheduler_admission.py` | 12 |
| `tests/test_phase5a6_delegation_foundation.py` | 8 |
| `tests/test_phase5a6r2_parent_lifecycle.py` | 11 |
| `tests/test_phase5a6r3_scenario_certification.py` | 12 |
| `tests/test_phase5a6r4_gap_closure.py` | 6 |
| `tests/test_phase5a6r_delegation_closure.py` | 7 |
| `tests/test_providers.py` | 7 |
| `tests/test_runtime.py` | 11 |
| `tests/test_secrets_redaction.py` | 9 |
| `tests/test_step_c_gap_closure.py` | 8 |
| `tests/test_step_c_subprocess_crash_matrix.py` | 12 |
| `tests/test_step_e_registry_dispatch.py` | 9 |
| `tests/test_step_f_calling_dispatcher.py` | 24 |
| `tests/test_task_creation_import_integrity.py` | 21 |
| `tests/test_task_persistence_fail_closed.py` | 22 |

> Note: collected total is 577 (pytest collection may include parameterized/generated cases beyond simple `def test_` count in some suites; collection is authoritative for run).

## Full suite run (default settings, this session)

**Command:** `cd "/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ" && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q 2>&1 | tee _context_pack/_tmp_full_suite.txt`  
**Saved:** `_context_pack/_tmp_full_suite.txt`, exit recorded in `_context_pack/_tmp_full_suite_exit.txt`

**Exact outcome:**
- `577 passed, 13 warnings in 61.68s`
- No test failures in captured output.

**Warnings summary (captured):**
- `/usr/lib/python3/dist-packages/gi/overrides/__init__.py:159: PyGIDeprecationWarning: GLib.unix_signal_add_full is deprecated; use GLibUnix.signal_add_full instead`
- `tests/test_phase3.py`: 12 warnings `DeprecationWarning: This process (...) is multi-threaded, use of fork() may lead to deadlocks in the child` from `multiprocessing/popen_fork.py:70`

(Full text preserved in `_context_pack/_tmp_full_suite.txt`.)

## `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (5 runs each)

**Commands executed (controlled, read-only test runs):**
1. Default basetemp: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (5 runs)
2. tmp basetemp: `--basetemp /tmp/aj-pytest-basetmp` (5 runs)
3. NTFS approved basetemp: `--basetemp "/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp"` (5 runs)

**Full outputs/tracebacks:** `_context_pack/_tmp_sqlite_runs.txt`

| Case | Runs | Pass | Fail | Per-run |
|---|---:|---:|---:|---|
| default | 5 | 2 | 3 | 1:FAIL, 2:FAIL, 3:PASS, 4:FAIL, 5:PASS |
| tmp_basetemp `/tmp/aj-pytest-basetmp` | 5 | 5 | 0 | 1-5:PASS |
| ntfs_basetemp `/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp` | 5 | 4 | 1 | 1-4:PASS, 5:FAIL |

**Failure signature (representative, from captured run):**
```
FAILED tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event - sqlite3.OperationalError: disk I/O error
...
  File "aj/memory.py", line 162, in __init__
    conn.executescript(_SCHEMA)
```
Fork multiprocessing context (4 workers writing shared WAL DB) as per test implementation; tracebacks in `_context_pack/_tmp_sqlite_runs.txt`.

> Environment note: default pytest temp base resolved to `/home/abubakargcx/easy-diffusion/tmp` on NTFS mount in this environment (`01_baseline.md`), which is relevant to observed sensitivity.

## Doc 54 invariants (INV-01..INV-10) and T-01..T-12: real-boundary vs helper-only vs no test (current state)

Classification basis: inspected source/tests for delegation/authorization/recovery/concurrency/reconciliation paths (Phase 5A/5A.6/5A.6R suites and related) and grep for callables; **not a proof of full coverage**. "Real-boundary" = exercises actual orchestrator/scheduler/store/task/lease/execution integration paths (possibly in-process). "Helper-only" = isolated unit logic only. "No test" = no identified test demonstrating the required boundary/condition.

| ID | Mapping (Doc 54 intent) | Current tests (citations) | Classification |
|---|---|---|---|
| INV-01 | Authorization fail-closed incl. current-state revalidation on supported delegated paths | `tests/test_f2_permission_enforcement.py` (policy/permission enforcement), `tests/test_f2_authorization_context.py` (stale authz/resume boundaries), `tests/test_phase5a6_delegation_foundation.py::test_permission_narrowing_and_fail_closed`, `tests/test_phase5a6r4_gap_closure.py::test_delegated_execution_revalidates_current_state_and_fails_closed`, `tests/test_phase5a6r4_gap_closure.py::test_delegated_child_preparation_blocks_cancelled_or_revoked_parent` | **Real-boundary (partial):** covered paths tested; exhaustive path/current-dynamic revocation coverage **not proven** (helper-level gaps remain). |
| INV-02 | Delegated permission narrowing | `tests/test_phase5a6_delegation_foundation.py::test_permission_narrowing_and_fail_closed`, `tests/test_phase5a6r4_gap_closure.py::test_delegated_execution_revalidates_current_state_and_fails_closed` (snapshot/envelope checks), delegation logic in `aj/delegation.py::narrow_permissions` exercised via integration tests | **Real-boundary (partial):** narrowing enforced in covered cases; full boundary revalidation against all current sources **not proven**. |
| INV-03 | Parent lifecycle correctness / no unsafe completion | `tests/test_phase5a6r2_parent_lifecycle.py` (guard/reconcile/aggregation behaviors), `tests/test_phase5a6r3_scenario_certification.py`, `tests/test_phase5a6r4_gap_closure.py` (indirect), `Aj._before_task_transition`/`aggregate_parent_progress` paths | **Real-boundary (partial):** completion guard and aggregation behaviors tested in scenarios; explicit required/optional classification/policy completeness per Doc 54 **no test / unverified**. |
| INV-04 | Cancellation safety (no prohibited prep/dispatch/resurrection) | `tests/test_phase5a6r4_gap_closure.py::test_delegated_child_preparation_blocks_cancelled_or_revoked_parent`, general cancel tests (`tests/test_foundation.py`, `tests/test_orchestrator.py`, `tests/test_phase3.py` etc.), scheduler conservative behavior tests (`tests/test_phase5a5_scheduler_admission.py`) | **Real-boundary (partial):** limited delegated boundaries covered; full orchestration/race/late-outcome/resurrection prevention **not proven**. |
| INV-05 | Reconciliation correctness/boundedness/idempotency | `tests/test_phase5a6r2_parent_lifecycle.py` (dry-run/apply/idempotency/batch/provenance aspects), `tests/test_phase5a6r3_scenario_certification.py`, `tests/test_phase5a6r4_gap_closure.py` (concurrent reconciliation), `tests/test_phase5a6r_delegation_closure.py` | **Real-boundary (partial):** covered behaviors tested; full stale-writer/cross-store/race safety **not proven**. |
| INV-06 | Crash and recovery honesty | `tests/test_crash_safety.py`, `tests/test_phase3c_recovery_integrity.py`, `tests/test_phase3d_recovery_observability.py`, `tests/test_phase3_lifecycle_reliability.py`, `tests/test_phase2.py` recovery cases; 5A.6R3 detection-oriented scenarios | **Real-boundary (partial):** many recovery behaviors tested; declared restart/persistence-boundary proofs for all Doc 54 boundaries (incl. A–H) **no test / unverified**. |
| INV-07 | Concurrency and stale-state safety | `tests/test_phase5a6r4_gap_closure.py` in-process concurrent reconciliation barrier case, `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (storage concurrency, environment-sensitive), lease/locking usage in other suites | **Real-boundary (partial, narrow):** limited demonstrated cases; stale-writer/cancel-vs-complete/recovery-vs-dispatch and broader races **no test / unverified**. |
| INV-08 | Anomaly visibility (read-only detection) | `tests/test_phase5a6r4_gap_closure.py` anomaly detection extensions, `tests/test_phase5a6r3_scenario_certification.py`, delegation monitor/status usage in 5A.6R suites | **Real-boundary (partial):** supported classes partially tested; complete detector/certified remediation coverage **no test / unverified**. |
| INV-09 | Evidence and auditability | `tests/test_phase5a4_execution_domain.py`, `tests/test_phase3d_recovery_observability.py`, `tests/test_audit_reliability_security.py`, delegation/reconciliation evidence assertions in 5A.6R suites, operation evidence/reconcile tests | **Real-boundary (partial):** evidence produced/checked in many paths; complete coverage across all supported decisions/failures **not proven**. |
| INV-10 | Honest system boundaries | Negative/behavioral boundary checks scattered (e.g. unsupported execution/adapter behavior in phase tests, Hermes-not-attached assumptions), no single comprehensive boundary test suite | **Partial/helper+integration evidence; no dedicated comprehensive test** demonstrating all prohibited claims rejected/reported. |

| Test matrix ID | Current tests (citations) | Classification |
|---|---|---|
| T-01 | Authz/permission/delegation negative-positive on covered paths: `tests/test_f2_permission_enforcement.py`, `tests/test_f2_authorization_context.py`, `tests/test_phase5a6_delegation_foundation.py`, `tests/test_phase5a6r4_gap_closure.py` | **Real-boundary (partial)** — not all supported paths/variants certified. |
| T-02 | Revocation/cancel timing limited: `tests/test_phase5a6r4_gap_closure.py::test_delegated_execution_revalidates_current_state_and_fails_closed`, `..._blocks_cancelled_or_revoked_parent`; some lifecycle races elsewhere | **Partial / gaps (no exhaustive lifecycle/race coverage)**. |
| T-03 | Parent completion/aggregation scenarios: `tests/test_phase5a6r2_parent_lifecycle.py`, `tests/test_phase5a6r3_scenario_certification.py` | **Partial** — explicit approved required/optional/partial policy semantics **no test**. |
| T-04 | Missing/malformed classification fail-closed per Doc 54 | **No test identified** (current model lacks explicit per-child classification enforcement as specified). |
| T-05 | Cancel vs completion/dispatch/recovery/prep/late outcomes/resurrection | **Partial** (some boundaries), comprehensive race/late-outcome/resurrection **no test**. |
| T-06 | Reconcile dry-run/apply/idempotency/bounds/provenance/concurrent | `tests/test_phase5a6r2_parent_lifecycle.py`, `tests/test_phase5a6r3_scenario_certification.py`, `tests/test_phase5a6r4_gap_closure.py` | **Real-boundary (partial)** — stale/contradiction/cross-store cases incomplete. |
| T-07 | Declared restart/persistence-boundary recovery proofs | `tests/test_crash_safety.py`, recovery suites; A–H declared boundary proofs | **Partial**; many declared boundaries **no test / unverified**. |
| T-08 | Controlled single-process mutating races (all listed scenarios) | `tests/test_phase5a6r4_gap_closure.py` (limited) | **Partial**; broad scenario set **no test**. |
| T-09 | Anomaly detection classes present/healthy read-only | `tests/test_phase5a6r4_gap_closure.py`, 5A.6R suites | **Real-boundary (partial)**. |
| T-10 | Correlatable evidence and uncertainty/no fabricated success across paths | Multiple suites as above | **Partial**. |
| T-11 | Unsupported capability/claim attempts rejected/reported | **No dedicated test identified** (scattered checks only). |
| T-12 | SQLite/WAL repro/isolation/disposition (non-weakening) | `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` + controlled runs in `_context_pack/_tmp_sqlite_runs.txt` | **Partial investigation evidence; disposition OPEN**. |

**Caveat:** This mapping is best-effort from inspected sources/tests and is not a substitute for Doc 56/57 S0 per-callable executable proof instantiation or independent verification.
