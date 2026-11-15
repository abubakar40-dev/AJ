# 01 — Baseline and Repository Preservation

## Verified facts (baseline, before 4B.5 doc creation)
- **AJ repo:** `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- **Branch:** `main`
- **HEAD:** `468fdcebece5b25f02e53add4928d3650ef175f4`
- **`git status --short` (41 entries, pre-existing to 4B.5):** 14 tracked modified files + 27 untracked paths including prior audit dirs (`MASTER_CORE_AUDIT_2026-11-13/`, `PHASE_3F_IDENTITY_TRUST_2026-11-13/`, `PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/`, `PHASE_4B_0_DESIGN_LOCK_2026-11-13/`, `PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/`, `PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/`, `PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/`, `PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/`), untracked AJ modules/tests (`aj/authorization.py`, `aj/consistency.py`, `aj/hermes_adapter.py`, `aj/hermes_contract.py`, `aj/operation_evidence.py`, `aj/storage_diagnostics.py`, `integrations/`, and multiple untracked tests). No 4B.5 artifacts existed at baseline capture.
- **No Git staging/commit/push/merge/rebase/reset/clean/stash performed.** No pre-existing files overwritten or removed.

## Hermes executable and source (verified)
- **Executable:** `command -v hermes` → `/home/abubakargcx/.local/bin/hermes`; `readlink -f` → `/home/abubakargcx/.local/bin/hermes`.
- **Version/install:** `hermes --version` → `Hermes Agent v0.23.0 (2026.9.24) · stable · local 2bd378ed1b8d`; Install directory `/home/abubakargcx/.hermes/hermes-agent`; Install method `git`; Python 3.14.9.
- **Source checkout:** `/home/abubakargcx/.hermes/hermes-agent` (`~/.hermes/hermes-agent`), **HEAD `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`**, branch empty (detached), `git status --short` clean at inspection time.

## Protected/out-of-scope repos (observed untouched)
| Repo | Path | Observed state |
|---|---|---|
| JARVIS | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/JARVIS` | `?? chat_history/2026-11-04.md`, `?? chat_history/2026-11-05.md` (pre-existing) |
| HELIX (workspace) | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/helix` | clean |
| HELIX (Drive candidate) | `/run/media/abubakargcx/My Drive/hermes/helix` | pre-existing dirty/diverged (multiple M/D), not modified |
| Hermes source | `/home/abubakargcx/.hermes/hermes-agent` | clean, detached `2bd378ed...`, not modified |

## AJ runtime baseline (verified read-only)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` (from AJ repo): **exit 0, `ok:true`, 23/23 checks, `failures:[]`, `attached:{jarvis:false, helix:false, hermes:"NOT ATTACHED"}`**.
- Integration flags/config: not changed in this phase (AJ source/config untouched; 4B.5 added audit docs only).

## Post-phase preservation evidence
- **Only intended additions:** `ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/` with docs `00`–`10`.
- **Final AJ `git status --short` count:** 42 entries = 41 pre-existing + 1 new untracked audit directory. No tracked content changed by 4B.5; all pre-existing modifications/untracked artifacts preserved.
- **Lifecycle actions performed:** none (`hermes gateway ensure` not executed; no start/restart/stop/enable/install performed). Hermes/JARVIS/HELIX repos untouched.
