# 01 — Baseline and Repository Preservation

## Initial baseline (before 4B.3 code/test changes)
- **AJ root:** `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- **Branch/HEAD:** `main` @ `468fdcebece5b25f02e53add4928d3650ef175f4` (`origin/main [ahead 1]`)
- **Initial `git status --short` (preserved, pre-existing):**
  - Tracked M (14): `aj/__main__.py, aj/config.py, aj/diagnostics.py, aj/orchestrator.py, aj/recovery.py, aj/runtime.py, aj/task.py, aj/transfer.py, tests/test_foundation.py, tests/test_orchestrator.py, tests/test_path_config_hardening.py, tests/test_phase2.py, tests/test_phase3.py, tests/test_step_c_gap_closure.py`
  - Untracked (pre-existing/prior phases): `ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/`, `aj/authorization.py, aj/consistency.py, aj/hermes_adapter.py, aj/hermes_contract.py, aj/operation_evidence.py, aj/storage_diagnostics.py, integrations/`, prior untracked tests incl. `tests/test_phase4b1_hermes_adapter.py`, `tests/test_phase4b1_hermes_security_faults.py`, `tests/test_phase4b2_reliability_hardening.py`, etc.
- **Baseline verification (rerun):**
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` → **exit 0, ok true, 23/23 checks, failures [], attached {jarvis:false, helix:false, hermes:"NOT ATTACHED"}**
  - Full suite baseline (pre-4B.3): **456 passed, 13 warnings, 0 failed** (from 4B.2 completion state)
- **Defaults verified:** `feature_flags.hermes_execution_adapter=false`, `execution.runtime="none"`, `execution.hermes.enabled=false`, `execution.hermes.capability_status_read_enabled=false`.

## Protected repositories/systems (untouched)
- `JARVIS` `audit/consolidation-2026-11-06` `d93c702...` with untracked `chat_history/2026-11-04.md, 2026-11-05.md` (preserved).
- `AI_WORKSPACE/helix` `audit/consolidation-2026-11-06` `99c7a38...` clean.
- `Drive/hermes/helix` (`~/helix`) `main` `e8a64cf...` dirty/diverged — untouched.
- Hermes source `~/.hermes/hermes-agent` detached `2bd378ed...` clean, runtime `v0.23.0` — untouched. No Hermes/JARVIS/HELIX/service/env/KDE Connect/Obsidian/canonical memory modifications.

## Final state (after 4B.3 work)
- **Branch/HEAD unchanged:** `main` @ `468fdce...`
- **Final `git status --short` (39 lines):** all pre-existing tracked M and untracked entries preserved; 4B.3 additions/modifications only:
  - **Modified (hardened, AJ-only):** `aj/hermes_adapter.py`, `aj/hermes_contract.py` (4B.1 artifacts further hardened for redaction/cli_path fail-closed in 4B.3; already modified/untracked in prior phases).
  - **Added:** `tests/test_phase4b3_security_assurance.py`, `ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/` (docs 00–12).
  - No other protected/repo files changed.
- **Preservation confirmation:** no files staged, no commits, no push/merge/rebase/reset/clean/history rewrite/destructive operations. All original user/pre-existing modifications and untracked files remain. No persistent Hermes enablement; `aj --check` reports Hermes NOT ATTACHED.