# 00 — Phase 4B.2 Master Report — Reliability Hardening

**Project:** AJ ↔ Hermes integration (existing capability only)  
**Phase:** 4B.2 — Reliability Hardening  
**Date:** 2026-11-14  
**Final status:** **COMPLETE**

## Executive summary
Phase 4B.2 inspected Phase 4B.0/4B.1 design and implementation, preserved all pre-existing Git/user changes, and applied evidence-backed, minimal additive hardening to the existing read-only `hermes.status.read` adapter (`hermes gateway status`, fixed argv, CLI subprocess, `aj.hermes.execution.v0`, `local_trust`, default-disabled). Improvements: bounded **incremental** stdout/stderr collection, timeout enforcement with process-group/pid termination and bounded reap/cleanup, stricter fail-closed config/provenance validation for explicit enablement, expanded best-effort secret redaction, and conservative observation-based outcome classification without semantic health inference or fabricated IDs. Deterministic 4B.2 tests added (10), 4B.1/contract suites preserved, full AJ regression and health checks pass, and controlled isolated live repeated read-only verification succeeded. No capability scope expansion; Hermes/JARVIS/HELIX/runtime configs untouched.

## Scope (allowed, implemented)
- CLI resolution/provenance validation hardening (fail-closed invalid/argument-like paths, sanitized resolved-path evidence)
- Config validation fail-closed for explicit enablement (`strict_config`, type/range/bound checks)
- Subprocess lifecycle safety, timeout, termination/kill/reap, partial bounded output preservation
- stdout/stderr bounds enforced **during collection** (incremental, capped, drain-to-EOF)
- Output validation/classification (conservative `exit_zero|nonzero_exit|timeout`, untrusted raw text retained, no semantic health inference)
- Best-effort redaction expansion (Bearer/Basic, key/value/header, credential URLs, env-style secrets)
- Error classification (spawn/dep unavailable/timeout/nonzero/signal) and honest evidence
- Deterministic fault-injection/unit tests; repeated controlled read-only live verification
- Documentation and diagnostics evidence

## Explicitly out of scope (not done)
No new Hermes capabilities/commands, no agent/skill/MCP/tool execution, no shell/Python general execution, no `--deep/--full`, no browser/desktop/filesystem/messaging/financial/remote-admin ops, no JARVIS/HELIX integration, no memory unification, no provider routing/service infra, no Docker/Honcho/paid APIs, no repo consolidation/migration, no Hermes/JARVIS/HELIX source or runtime/config changes.

## Evidence

| Check | Result |
|---|---|
| Pre-4B.2 rerun baseline | `pytest -q`: 446 passed, 13 warnings, 0 failed; `aj --check`: 23/23 ok, Hermes NOT ATTACHED |
| New 4B.2 tests | `tests/test_phase4b2_reliability_hardening.py`: **10 passed** |
| 4B.1+4B.2+contract targeted | **31 passed** (`test_phase4b1_*`, `test_phase4b2_*`, `test_hermes_contract.py`) |
| Full regression (final) | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`: **456 passed, 13 warnings, 0 failed** (60.79s) |
| Health/self-check (final) | `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check`: **exit 0, ok true, 23/23, failures [], attached.hermes "NOT ATTACHED"** |
| Controlled live read-only verification | Isolated in-memory enablement, temp dirs, 3 repeated `hermes.status.read` probes: **all completed**, fixed argv, `collection=bounded_incremental`, `hermes_execution_id=null`, defaults restored/not persisted |
| SQLite concurrency observation (unrelated) | `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` 5 isolated repeats: 2 passed / 3 failed (`sqlite3.OperationalError: disk I/O error` or locked) — intermittent environment flake, not caused by 4B.2; final full suite passed |

## What changed (AJ-only)
- **Modified:** `aj/hermes_adapter.py` (threaded bounded incremental runner, process-group timeout/terminate/kill/reap, strict config validation, provenance/collection/signal/truncation evidence, conservative observation/notes), `aj/hermes_contract.py` (expanded best-effort redaction), `aj/runtime.py` (fail-closed validation for explicit hermes enablement).
- **Added:** `tests/test_phase4b2_reliability_hardening.py`, `ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/00-09`.
- **Intentionally unchanged:** contract `aj.hermes.execution.v0` semantics/capability/command, allowlist/authz/local_trust model, default-disabled flags/values, no-shell/fixed-argv invariant, AJ recovery/evidence architecture, JARVIS/HELIX/Hermes code/runtime/services/configs, unrelated tests and pre-existing user changes.

## Preservation
All pre-existing tracked modifications and untracked files preserved; no staging/commits/push/merge/rebase/reset/clean. 4B.2 changes are additive/hardening on 4B.1 AJ artifacts only. Details: `01_BASELINE_AND_GIT_PRESERVATION.md`.

## Limitations and risks
- Redaction is best-effort (not complete guarantee); CLI output unstructured/untrusted/truncatable.
- `exit_zero` is process outcome, not semantic health proof; no Hermes-native IDs/cancellation; `local_trust` non-authenticated.
- Process cleanup best-effort (platform/descendant edge cases possible). No cross-store atomicity/exactly-once claims.
- Intermittent `test_phase3` concurrent writer flake observed in environment (unrelated, documented).

## Recommendation
**Phase 4B.3 conditionally justified only for further reliability/observability/fault-handling/recovery/security hardening of the same read-only `hermes.status.read` boundary** (no capability expansion). See `09_PHASE_4B_3_READINESS_RECOMMENDATION.md`.