# 01 — Baseline and Git Preservation

## Stage A audit (2026-11-14)

### AJ root
- Root: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- Branch: `main`, HEAD: `468fdcebece5b25f02e53add4928d3650ef175f4`, ahead 1 of `origin/main`

### Pre-existing preserved state (before 4B.2 changes)
All pre-existing tracked modifications and untracked files from prior phases preserved (not staged, not committed, not cleaned, not reset):
- **Tracked M:** `aj/__main__.py, aj/config.py, aj/diagnostics.py, aj/orchestrator.py, aj/recovery.py, aj/runtime.py, aj/task.py, aj/transfer.py, tests/test_foundation.py, tests/test_orchestrator.py, tests/test_path_config_hardening.py, tests/test_phase2.py, tests/test_phase3.py, tests/test_step_c_gap_closure.py`
- **Pre-existing/unrelated untracked:** prior audit dirs (`MASTER_CORE_AUDIT_2026-11-13/`, `PHASE_3F_IDENTITY_TRUST_2026-11-13/`, `PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/`, `PHASE_4B_0_DESIGN_LOCK_2026-11-13/`, `PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/`), modules/tests from prior phases (`aj/authorization.py, aj/consistency.py, aj/operation_evidence.py, aj/storage_diagnostics.py, integrations/`, multiple untracked test files), plus 4B.1 implementation artifacts (`aj/hermes_adapter.py, aj/hermes_contract.py, tests/test_phase4b1_hermes_adapter.py, tests/test_phase4b1_hermes_security_faults.py`).

### Other repositories (untouched)
- `JARVIS` `audit/consolidation-2026-11-06` `d93c702...` untracked `chat_history/2026-11-04.md, 2026-11-05.md` (preserved).
- `AI_WORKSPACE/helix` `audit/consolidation-2026-11-06` `99c7a38...` clean.
- `Drive/hermes/helix` (`~/helix`) `main` `e8a64cf...` dirty/diverged (tracked M/D + untracked) — **untouched**.
- Hermes source `~/.hermes/hermes-agent` detached `2bd378ed...` clean, runtime `v0.23.0` (`hermes --version`), wrapper `~/.local/bin/hermes`; gateway running (read-only evidence). No Hermes source/runtime/config changes.

### Current reported baseline (rerun, pre-4B.2 code edits in this phase)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` (AJ/): **exit 0, ok true, 23/23 checks, failures [], attached {jarvis:false, helix:false, hermes:"NOT ATTACHED"}**.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` (AJ/): **446 passed, 13 warnings, 0 failed** (51.07s). Warnings unchanged/pre-existing: `gi.overrides` PyGIDeprecationWarning + 12 fork-in-multithread DeprecationWarnings in `tests/test_phase3.py`.
- Defaults verified in source: `feature_flags.hermes_execution_adapter=false`, `execution.runtime="none"`, `execution.hermes.enabled=false`, `execution.hermes.capability_status_read_enabled=false`.

### Phase 4B.1/4B.0 inspected (actual files)
- `AJ/ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/00-09` and `PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/00-09` reviewed.
- Implementation/tests: `aj/hermes_contract.py`, `aj/hermes_adapter.py`, `aj/config.py`, `aj/runtime.py`, `aj/orchestrator.py`, `tests/test_hermes_contract.py`, `tests/test_phase4b1_hermes_adapter.py`, `tests/test_phase4b1_hermes_security_faults.py`.

### After 4B.2 (post-implementation/test, AJ-only)
- **4B.2 modifications/additions:** modified `aj/hermes_adapter.py`, `aj/hermes_contract.py`, `aj/runtime.py` (reliability hardening of existing read-only adapter: bounded incremental subprocess collection + process-group timeout/kill/reap, stricter fail-closed config validation, improved best-effort redaction, honest observation/evidence fields); added `tests/test_phase4b2_reliability_hardening.py` and `ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/` docs.
- **Preservation:** all pre-existing tracked M and untracked files remain present; no files staged/committed/pushed/merged/rebased/reset/cleaned; no unrelated deletions/moves; no JARVIS/HELIX/Hermes/Drive-helix modifications.
- **Final `git status --short` (AJ):** same pre-existing entries plus 4B.2 artifacts (37 total status lines), including `?? ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/` and `?? tests/test_phase4b2_reliability_hardening.py`; 4B.1 files remain modified/untracked as before with 4B.2 hardening applied.