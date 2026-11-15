# 01 — Baseline and Preservation

## AJ baseline (recorded before 4B.4 doc/test work)
- **Repo:** `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- **Branch:** `main`
- **HEAD:** `468fdcebece5b25f02e53add4928d3650ef175f4` (ahead 1 of `origin/main`)
- **`git status --short` (40 entries, all pre-existing to 4B.4):**
  - Tracked modified (14): `aj/__main__.py`, `aj/config.py`, `aj/diagnostics.py`, `aj/orchestrator.py`, `aj/recovery.py`, `aj/runtime.py`, `aj/task.py`, `aj/transfer.py`, `tests/test_foundation.py`, `tests/test_orchestrator.py`, `tests/test_path_config_hardening.py`, `tests/test_phase2.py`, `tests/test_phase3.py`, `tests/test_step_c_gap_closure.py`
  - Untracked (pre-existing/prior phases): `ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/`, `PHASE_3F_IDENTITY_TRUST_2026-11-13/`, `PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/`, `PHASE_4B_0_DESIGN_LOCK_2026-11-13/`, `PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/`, `PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/`, `PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/`, `aj/authorization.py`, `aj/consistency.py`, `aj/hermes_adapter.py`, `aj/hermes_contract.py`, `aj/operation_evidence.py`, `aj/storage_diagnostics.py`, `integrations/`, and untracked tests including `test_audit_reliability_security.py`, `test_phase3_lifecycle_reliability.py`, `test_phase3c_recovery_integrity.py`, `test_phase3d_recovery_observability.py`, `test_phase3e_evidence_consistency.py`, `test_phase3f_identity_trust_boundary.py`, `test_phase4b1_hermes_adapter.py`, `test_phase4b1_hermes_security_faults.py`, `test_phase4b2_reliability_hardening.py`, `test_phase4b3_security_assurance.py`, `test_task_creation_import_integrity.py`, `test_task_persistence_fail_closed.py`.
- **Post-4B.4 state:** only `ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/` (docs `00`–`13`) added; no other AJ files modified, no files staged, no commits/push/merge/rebase/reset/clean/history rewrite/destructive ops.

## Protected/out-of-scope repositories (confirmed untouched)
| Repo | Path | Observed state |
|---|---|---|
| JARVIS | `AI_WORKSPACE/JARVIS` | `?? chat_history/2026-11-04.md`, `?? chat_history/2026-11-05.md` (pre-existing) |
| HELIX (workspace) | `AI_WORKSPACE/helix` | clean |
| HELIX (Drive) | `Drive/hermes/helix` | pre-existing dirty/diverged working tree (multiple M/D) |
| Hermes source/runtime | `~/.hermes/hermes-agent` | clean working tree, `Hermes Agent v0.23.0 (2026.9.24)`, detached/local `2bd378ed1b8d` |

No Hermes source/config/runtime/service modification, no persistent adapter enablement, no JARVIS/HELIX integration changes.

## Environment evidence
- `hermes --version`: `Hermes Agent v0.23.0 (2026.9.24) · stable · local 2bd378ed1b8d` (Python 3.14.9)
- `hermes status`: model `openrouter/auto` (OpenRouter), gateway running, WhatsApp platform, 0 jobs
- `hermes gateway status`: available subcommands include `status/run/start/stop/restart/install/...` (CLI inspected read-only via `--help`)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` → exit 0, `ok:true`, 23/23 checks, `failures:[]`, `attached:{jarvis:false, helix:false, hermes:"NOT ATTACHED"}`
