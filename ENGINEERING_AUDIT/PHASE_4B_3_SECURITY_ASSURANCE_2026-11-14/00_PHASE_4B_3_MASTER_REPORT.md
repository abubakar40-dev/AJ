# 00 — Phase 4B.3 Master Report — Security Assurance + AJ SQLite Reliability Investigation

**Project:** AJ ↔ Hermes (read-only `hermes.status.read`, `aj.hermes.execution.v0`) + AJ storage reliability investigation  
**Date:** 2026-11-14  
**Phase 4B.3 status:** **PARTIALLY COMPLETE**  
**SQLite investigation status:** **ROOT_CAUSE_PARTIALLY_IDENTIFIED**

## Executive summary
Phase 4B.3 performed an evidence-driven security assurance pass on the existing AJ↔Hermes read-only boundary and a separate investigation of intermittent SQLite concurrency failures in `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`. Actual 4B.0/4B.1/4B.2 docs and source were inspected; baseline and Git preservation recorded; threat model and attack-surface mapping grounded in implementation produced. Adversarial/deterministic security tests added (47), revealing and fixing a real redaction weakness (Bearer/Basic/quoted secret leakage cases) and tightening fail-closed cli_path handling; fixed-argv/no-shell/allowlist/deny-by-default/default-disabled/`local_trust`-non-auth/honest-evidence invariants verified. Full regression and `aj --check` pass. SQLite investigation gathered filesystem and controlled reproduction evidence showing strong ntfs3/WAL-sensitivity correlation (intermittent failures on ntfs3-backed default tmp; stable on tmpfs in samples) with concurrent init contention as secondary hypothesis; root cause partially identified, no unsafe application fix applied. Phase marked PARTIALLY COMPLETE due to residual risks (TOCTOU/path trust, best-effort redaction, best-effort descendant cleanup, known multi-store non-atomicity) and incomplete elimination of all threat-model uncertainties inherent to local-boundary scope.

## Scope and separation
- **Workstream A (Security Assurance):** AJ-only inspection, threat model, adversarial testing, narrow justified hardening, regression/live-policy compliance. No capability expansion, no new commands, no persistent enablement.
- **Workstream B (SQLite investigation):** read-only diagnosis/reproduction/analysis of existing test and `MemoryStore` behavior; no storage redesign/migration/unsafe retries/semantic changes. Independent conclusion.

## Key findings
- **Critical/High (security):** none confirmed open. High-impact sanitization defect (partial Authorization token redaction) **fixed** with regression coverage. High controls (fixed argv, no shell, allowlist, deny-by-default, honest outcomes, no fabricated IDs, default-disabled) **verified intact**.
- **Medium residuals:** TOCTOU/executable provenance assumptions, best-effort redaction completeness, best-effort descendant/pipe cleanup, known cross-store non-atomicity, Hermes CLI drift.
- **SQLite:** intermittent `disk I/O error` / `database is locked` correlated with ntfs3 + concurrent forked WAL init/writes; 10/10 pass on tmpfs, mixed on ntfs3/ext4 samples.

## Implementation (AJ-only)
- `aj/hermes_contract.py`: improved best-effort redaction patterns/replacement (Authorization Bearer/Basic, quoted JSON-like secrets, key/value/env forms).
- `aj/hermes_adapter.py`: fail-closed handling for explicitly empty/invalid cli_path in permissive construction (preserve empty instead of default fallback).
- `tests/test_phase4b3_security_assurance.py`: added (47 adversarial/security regression tests).

## Verification
| Check | Result |
|---|---|
| New 4B.3 security tests | 47 passed, 0 failed |
| Targeted 4B.1/4B.2/4B.3/contract | 78 passed, 0 failed |
| Full AJ regression | **503 passed, 13 warnings, 0 failed** (47.10s) |
| `aj --check` | **23/23 ok, failures [], Hermes NOT ATTACHED** (exit 0) |
| SQLite test (10 controlled default-tmp runs) | 8 passed, 2 failed (intermittent) |
| Live Hermes verification | **Not performed** (not required; isolation/availability conditions not exercised in-session). Defaults/persistent config unchanged; `aj --check` confirms NOT ATTACHED. |

## Git preservation
- Branch/HEAD unchanged: `main` @ `468fdce...`
- All pre-existing tracked modifications and untracked files preserved; no staging/commit/push/merge/rebase/reset/clean/destructive ops.
- 4B.3 additions/modifications: modified `aj/hermes_adapter.py`, `aj/hermes_contract.py`; added `tests/test_phase4b3_security_assurance.py`, `ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/` (00–12). Protected repos (JARVIS/HELIX/Hermes/Drive-helix) untouched.

## Readiness recommendation
**Phase 4B.4: Conditional**, only with separate scope/threat-model/design review, no capability expansion by default, and explicit acceptance/mitigation plan for residuals. See `09_PHASE_4B_4_READINESS_RECOMMENDATION.md`.

## Document index
- Security: `01_BASELINE_AND_REPOSITORY_PRESERVATION.md` … `09_PHASE_4B_4_READINESS_RECOMMENDATION.md`
- SQLite: `10_SQLITE_CONCURRENCY_ROOT_CAUSE_INVESTIGATION.md`, `11_SQLITE_DIAGNOSTIC_TEST_RESULTS.md`, `12_SQLITE_REMEDIATION_RECOMMENDATION.md`