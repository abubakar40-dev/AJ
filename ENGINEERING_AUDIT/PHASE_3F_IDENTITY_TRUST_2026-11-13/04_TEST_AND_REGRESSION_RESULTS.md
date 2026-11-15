# 04 — Phase 3F Tests and Regression Results

**Environment:** Linux, `python3`, `PYTHONPATH=/home/abubakargcx/.local/lib/python3.14/site-packages:$PWD`, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, isolated `HOME`/`TMPDIR` under `/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/...` unless noted.

## Tests added
- `tests/test_phase3f_identity_trust_boundary.py` (9 tests): forged/arbitrary operator metadata never becomes authenticated principal; missing/empty metadata preserves provenance with no principal; unauthorized deny mode fails closed with no state change/refused op evidence; `require_verified_identity` fails closed without provider; caller cannot inject authenticated principal via API shape and scope is bound; per-operation scoped authorization decisions/provenance; identity provenance in `operator_reconciliation` audit; authorization failure/exception during reconciliation fails closed; concurrent privileged operations serialized/audited with no unsafe duplicate application.

## Exact results

| Suite | Command | Result |
|---|---|---|
| 3E compatibility | `pytest -q -p no:cacheprovider tests/test_phase3e_evidence_consistency.py` | **11 passed in 0.23s** |
| 3F adversarial/identity | `pytest -q -p no:cacheprovider tests/test_phase3f_identity_trust_boundary.py` | **9 passed** (final; intermediate failures debugged and fixed) |
| 3F + 3E combined | `pytest -q -p no:cacheprovider tests/test_phase3f_identity_trust_boundary.py tests/test_phase3e_evidence_consistency.py` | **20 passed in 0.47s** |
| 3D + audit reliability regressions | `pytest -q -p no:cacheprovider tests/test_phase3d_recovery_observability.py tests/test_audit_reliability_security.py` | **17 passed in 1.82s** |
| 3C + recovery/integrity/crash/idempotency/step-c/dead-letter/phase2 regressions | `pytest -q -p no:cacheprovider tests/test_phase3c_recovery_integrity.py tests/test_phase3_lifecycle_reliability.py tests/test_task_persistence_fail_closed.py tests/test_task_creation_import_integrity.py tests/test_crash_safety.py tests/test_idempotent_replay.py tests/test_step_c_gap_closure.py tests/test_dead_letter.py tests/test_phase2.py` | **97 passed in 13.66s** |
| Core runtime/foundation/orchestrator regressions | `pytest -q -p no:cacheprovider tests/test_foundation.py tests/test_orchestrator.py tests/test_runtime.py` | **80 passed in 2.02s** (CLI behavior also covered by `test_inbox.py`, `test_phase3d_recovery_observability.py`, full suite) |
| **Full suite** | `pytest -q -p no:cacheprovider` | **433 passed, 13 warnings in 35.95s** |

## Notes
- Warnings: `PyGIDeprecationWarning` from system `gi` (`GLib.unix_signal_add_full`), and `DeprecationWarning: use of fork() may lead to deadlocks in the child` in multiprocess tests (pre-existing/environmental; tests passed).
- No intermittent failures observed in 3F runs reported above. Prior known environment caveat (external-fs SQLite WAL `disk I/O error` under specific forked-writer conditions) remains documented; full suite passed in this cycle.
- No tests weakened, skipped, or deleted. Existing assertions preserved/updated only where necessary for additive provenance fields while maintaining security semantics.