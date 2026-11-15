# 05 — Test and Stress Results

## 1. Environment and commands
- **Workdir:** `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- **Python/PYTHONPATH:** system `python3` with `PYTHONPATH=/home/abubakargcx/.local/lib/python3.14/site-packages:$PWD`
- **Isolation:** per-run `HOME`/`TMPDIR` (mostly under `/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/...`; one SQLite probe on `/tmp`)
- **Flags:** `PYTHONDONTWRITEBYTECODE=1`, `python3 -m pytest -q -p no:cacheprovider`

## 2. Executed test results

| Run | Command | Result |
|---|---|---|
| Preflight focused 3A–3D/regression | `pytest ... tests/test_task_persistence_fail_closed.py tests/test_task_creation_import_integrity.py tests/test_phase3_lifecycle_reliability.py tests/test_phase3c_recovery_integrity.py tests/test_phase3d_recovery_observability.py tests/test_audit_reliability_security.py tests/test_crash_safety.py tests/test_idempotent_replay.py tests/test_step_c_gap_closure.py tests/test_dead_letter.py tests/test_phase2.py tests/test_orchestrator.py tests/test_foundation.py` | **194 passed in 27.54s** (`EXIT 0`) |
| Preflight full suite (run 1) | `pytest -q -p no:cacheprovider` | **412 passed, 1 failed, 13 warnings in 50.68s** (`EXIT 1`) |
| Failing test rerun (external tmp) | `pytest tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` | **1 passed in 0.41s** (`EXIT 0`) |
| Failing test rerun (local `/tmp`) | same, with `TMPDIR` on `/tmp` | **1 passed in 0.13s** (`EXIT 0`) |
| Post-3E key regressions | `pytest tests/test_phase3d_recovery_observability.py tests/test_audit_reliability_security.py tests/test_phase3c_recovery_integrity.py tests/test_dead_letter.py tests/test_phase2.py` | **62 passed in 6.12s** (`EXIT 0`) |
| Phase 3E tests | `pytest tests/test_phase3e_evidence_consistency.py` | **11 passed in 0.41s** (`EXIT 0`) |
| **Final full suite** | `pytest -q -p no:cacheprovider` | **424 passed, 13 warnings in 46.85s** (`EXIT 0`) |

## 3. Preflight intermittent failure analysis
- **Failure:** `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` — `sqlite3.OperationalError: disk I/O error` during `PRAGMA journal_mode=WAL` in forked worker (external tmp mount).
- **Classification:** **environment/filesystem-limited**, not a reproducible AJ core logic regression.
- **Evidence:** passed on immediate rerun (external tmp) and on local `/tmp`; prior controlled runs 8/8 local vs 5/8 external; final full suite passed (424/0). Diagnostics now classify SQLite disk I/O/locking conditions.

## 4. Stress/failure/adversarial checks (targeted)

| Check | Method | Result | Notes |
|---|---|---|---|
| Concurrent request handling | 10-thread `aj.handle` (`aj.echo`) in isolated runtime | **Pass** (10 unique task IDs, all terminal outcomes) | Local in-process/threaded stress; not distributed. |
| Privileged reconcile op-id idempotency | Same `operation_id` submitted twice after terminal outcome | **Pass** (`state_changed` once, duplicate returned `idempotent_duplicate`, no reapply) | Prevents duplicate application for known terminal op. |
| Incomplete operation (crash window simulation) | Intent recorded without outcome; restart/check/reconcile | **Pass** (3E tests) | Detected as incomplete, no auto-retry/auto-success/duplicate apply. |
| Consistency checker read-only | Snapshot operation-evidence file before/after `consistency_check` | **Pass** (unchanged, status reported) | No store mutation. |
| Authorization fail-closed | deny/unavailable privileged auth config | **Pass** (3E tests) | No state change; refused outcome/audit recorded. |
| Recovery/reconciliation adversarial scenarios | 3C/3D/audit-reliability suites (leases, conflicts, malformed/missing evidence, terminal/ownership, inspection purity, CLI behavior) | **Pass** (covered suites green) | Includes clear-to-retry conflict fail-closed and incomplete evidence surfacing. |
| Crash/persistence/idempotency/resume | `test_crash_safety.py`, `test_idempotent_replay.py`, `test_step_c_gap_closure.py`, `test_step_c_subprocess_crash_matrix.py`, `test_f2_scheduler_resume.py`, persistence/import suites | **Pass** | Existing verified scenarios; not exhaustive of all possible crash points/environments. |
| Runtime health/self-check | `python -m aj --check` (isolated) | **Pass (23/23)** | Local foundation checks only. |
| Invariants sample | `aj.invariants.check` after execution | **Pass (`ok: true`, no issues)** | Sample runtime state. |

## 5. Warnings observed (non-failing)
- `PyGIDeprecationWarning` from system `gi` (`GLib.unix_signal_add_full`) — environment/system package warning.
- `DeprecationWarning: use of fork() may lead to deadlocks in the child` in multiprocess tests — known test/runtime behavior in multi-threaded process context; tests passed.

## 6. Coverage/verification gaps (honest)
- No live external integrations exercised (real JARVIS/HELIX task endpoints, Hermes runtime, live provider APIs/transports/credentials, real telephony bridge control).
- Stress tests were local/process-scoped, not distributed or long-soak.
- Full crash matrix across every multi-store boundary/phase not formally proven; 3E improves detection/reporting, not atomicity.
- Filesystem-dependent behavior (SQLite WAL) varies by environment; supported-fs preflight enforcement not yet automated.
- Inbox/orb GUI and some environment-dependent paths not fully validated in this headless audit run beyond available tests/smokes.
