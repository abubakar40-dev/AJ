# 46 — Phase 5A.6R5 Canonical Requirement Recovery

**Date:** 2026-11-14  
**Phase:** 5A.6R5 (audit/provenance recovery; no broad implementation).  
**Objective:** recover authoritative original requirements (45 scenarios, crash windows A–J, acceptance criteria, source prompt/spec) before further corrective work.

## 1. Repository and safety baseline (verified)

- **Repository:** `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- **Branch:** `main`
- **HEAD:** `468fdcebece5b25f02e53add4928d3650ef175f4` (expected historical HEAD; unchanged)
- **Git status count:** **57 entries** (17 tracked modified, 40 untracked status entries as reported by `git status --short`; `git ls-files --others --exclude-standard` lists 180 untracked files including files within untracked audit directories)
- **Tracked modifications (17, preserved):** `aj/__main__.py`, `aj/config.py`, `aj/diagnostics.py`, `aj/ids.py`, `aj/orchestrator.py`, `aj/receipts.py`, `aj/recovery.py`, `aj/runtime.py`, `aj/scheduler.py`, `aj/task.py`, `aj/transfer.py`, `tests/test_foundation.py`, `tests/test_orchestrator.py`, `tests/test_path_config_hardening.py`, `tests/test_phase2.py`, `tests/test_phase3.py`, `tests/test_step_c_gap_closure.py`
- **Untracked (representative/preserved):** 5A modules/tests (`aj/authorization.py`, `aj/delegation.py`, `aj/execution_domain.py`, `aj/consistency.py`, `aj/operation_evidence.py`, `aj/storage_diagnostics.py`, `aj/hermes_*`, `integrations/`, multiple `tests/test_phase*` incl. 5A.4–5A.6R4), and audit folders `MASTER_CORE_AUDIT_2026-11-13/`, `PHASE_3F_*` … `PHASE_4B_6_*`, `PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/` (docs `00`–`45` present).
- **Changes since 5A.6R4 (observed):** none in working tree content beyond this audit session's read-only inspection/command execution; docs `40`–`45`, `aj/orchestrator.py`, `aj/delegation.py`, `tests/test_phase5a6r4_gap_closure.py` remain as recorded at 5A.6R4 close.
- **Protected repositories/states (untouched):** JARVIS, HELIX, Hermes repositories/configuration/services not modified. Hermes remains **NOT ATTACHED**. `hermes.gateway.ensure` not implemented/enabled/executed/authorized. No destructive Git operations, staging, commits, pushes, merges, rebases, resets, cleans, tags, or history rewrites performed.

## 2. Recovery search scope and actions (read-only)

Inspected/searched (all available AJ project material in repo and workspace where applicable):
- **`ENGINEERING_AUDIT/` (all subfolders):** MASTER_CORE_AUDIT, PHASE_3F, PHASE_4A, PHASE_4B_0–4B_6, PHASE_5A (`00`–`45`), READINESS_AUDIT, IMPLEMENTATION_PHASE_03_1/04.
- **Earlier Phase 5A planning/design:** `PHASE_5A.../00`–`13` (baseline, domain/scheduler/orchestration audits, proposals, decision registers, stage reports) and `14`–`24` (5A.4/5A.5/5A.6 implementation/test/verification).
- **Project-level docs:** `README.md`, `docs/` (01–10).
- **Git history (read-only):** `git log`/`git log --name-only` (2 commits total: `62b12ac` initial baseline, `468fdce` path hardening; no requirement-spec commits).
- **Workspace-level search:** grep for "45 scenarios", "crash window", "A–J/A-J", "section 13", "tests 1-45" in `/run/media/abubakargcx/My Drive/AI_WORKSPACE`.
- **Targeted searches:** exact/related phrases (`"Child transition automatically triggers parent reconciliation"`, `"Permission reduction after assignment"`, `"Child state persisted, parent reconciliation not started"`, `"section 13"`, `"tests 1–45"`), scenario/checklist/prompt/acceptance patterns in AJ repo.

No fabrication performed. `36_PHASE_5A_6R3_45_SCENARIO_CERTIFICATION_MATRIX.md` treated as reconstructed, not original.

## 3. Discovered sources (requirements-related)

| Exact path | Source type | Version/date (if available) | Original or reconstructed | Relationship to 45 scenarios / A–J | Evidence supporting authority |
|---|---|---|---|---|---|
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/36_PHASE_5A_6R3_45_SCENARIO_CERTIFICATION_MATRIX.md` | Audit/certification matrix (repo artifact) | 2026-11-14 (doc header) | **Reconstructed** | Enumerates scenarios 1–45 and records PASS/PARTIAL/UNTESTED results; cites "Authoritative 5A.6R2 scenario set (section 13, 1–45)" but states verbatim list not found in `30–34`. | Internal traceability artifact only; explicitly non-original per `35`, `41`. |
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/35_PHASE_5A_6R3_PRE_IMPLEMENTATION_GAP_AUDIT.md` | Pre-implementation audit | 2026-11-14 | **Reconstructed (list capture) / provenance note** | Restates scenarios 1–45 and crash windows A–J as "authoritative 5A.6R2 requirement set (section 13 tests 1–45 and section 6 crash windows A–J)"; notes verbatim text not found in `30–34`. | Best in-repo reconstruction record; provenance explicitly unverified. |
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/30_PHASE_5A_6R2_PRE_IMPLEMENTATION_AUDIT.md` | Audit (5A.6R2 entry) | 2026-11-14 | **Project record (reconstructed references)** | References crash/race recovery "A–J windows", 45-scenario certification gap, and 5A.6R2 closure plan; does not list verbatim 45/A–J definitions. | Shows requirements were active in 5A.6R2 context but not as recoverable original artifact. |
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/33_PHASE_5A_6R2_TEST_AND_VERIFICATION.md` | Test/verification report | 2026-11-14 | **Project record (reconstructed reference)** | States "full 45 enumerated 5A.6R2 scenarios are not individually certified" and lists gap areas; no verbatim list. | Evidence of requirement pressure, not source text. |
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/34_PHASE_5A_6R2_VERIFICATION_REPORT.md` | Final 5A.6R2 report (INCOMPLETE) | 2026-11-14 | **Project record (reconstructed reference)** | Cites 45-scenario certification incomplete, crash windows A–J not fully closed/proven, acceptance criteria partially satisfied. | Historical verdict artifact; no original definitions. |
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/37`–`39` (5A.6R3 docs) | Audit/fixes/verification/final report | 2026-11-14 | **Reconstructed/project records** | Use/certify scenarios 1–45 and windows A–J per `35`/`36`; reiterate provenance not verbatim in `30–34`. | Downstream certification artifacts, not original source. |
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/40`–`45` (5A.6R4 docs) | Audit/traceability/matrix/fixes/verification/final report | 2026-11-14 | **Reconstructed/project records + provenance finding** | `41` records original-source non-recovery (UNVERIFIED); `42` disposes 28 gaps against `35`/`36` IDs. | Confirms non-recovery within repo; still not original source. |
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/25`–`29` (5A.6R docs) | Gap audit, implementation, authz/aggregation/recovery, tests, final report | 2026-11-14 | **Project records** | Refer to 57-scenario/closure context in 5A.6R (different framing from 45/A–J) and gaps; no verbatim 45/A–J original list. | Contextual history; not original 45/A–J source. |
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/00`–`24` | 5A.0–5A.6 planning/design/implementation docs | 2026-11-14 (per folder context) | **Project planning/design records** | Contain concurrency/recovery scenario analyses (e.g. 12/20 assessed scenarios), domain proposals, acceptance criteria for stages 5A.0–5A.5/5A.6; **no verbatim 45-scenario list or A–J crash-window definitions** matching 5A.6R2/5A.6R3 set. | Authoritative for earlier stage intent, but not the 45/A–J source. |
| Git commits (`62b12ac`, `468fdce`) | VCS history (read-only) | 2026-11-13 | **Original repo history (limited)** | No commit messages/blobs containing 45 scenarios, A–J windows, or 5A.6R2 requirement prompt/spec. | Confirms no recoverable requirement text in git history. |
| `README.md`, `docs/*` | Project documentation | existing | **Project documentation** | No 45-scenario/A–J requirement set. | Not a source for 5A.6R2 acceptance list. |

## 4. Original requirement recovery result

- **Original 45-scenario list:** **NOT RECOVERED** as a preserved original artifact (no exact path/name/version/date/provenance-established source found).
- **Original crash-window A–J definitions:** **NOT RECOVERED** as a preserved original artifact.
- **Original acceptance criteria for 5A.6R2/5A.6R3 45/A–J certification:** **NOT RECOVERED** as a distinct original artifact; only reconstructed/derived criteria appear in `30`–`45`.
- **Source prompt/specification that introduced those requirements:** **NOT RECOVERED** in repository, workspace search results, or git history. The closest in-repo attribution is "authoritative 5A.6R2 requirement set (section 13 tests 1–45 and section 6 crash windows A–J)" referenced in `35`/`36`/`41`, but the external/original directive text is absent.

**Conclusion:** Original-source provenance for the 45 scenarios and crash windows A–J remains **UNVERIFIED / NOT RECOVERED**. The reconstructed 5A.6R3 matrix (`35`/`36`) is the only enumerated in-repo list and must not be treated as the original source. Any inability to establish original provenance is explicitly recorded; this requires explicit user decision for baseline acceptance (see Doc `50`).
