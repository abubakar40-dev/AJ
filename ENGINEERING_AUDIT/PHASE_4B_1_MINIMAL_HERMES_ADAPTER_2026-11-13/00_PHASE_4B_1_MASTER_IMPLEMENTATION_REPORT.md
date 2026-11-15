# 00 — Phase 4B.1 Master Implementation Report

**Phase:** 4B.1 — Minimal AJ↔Hermes Execution Adapter (Controlled Implementation Spike, Read-Only Capability)  
**Date:** 2026-11-13  
**Status:** **COMPLETE (bounded scope)**

## Executive summary
Phase 4B.1 implemented the smallest AJ-controlled, contract-first, deny-by-default integration with Hermes for a single read-only capability (`hermes.status.read`) via a verified CLI subprocess interface (`hermes gateway status`), per Phase 4B.0 design lock. Stage A CLI safety gate **passed (conditional, adapter-bounded)**. A real `HermesExecutionAdapter` (ExecutionPort) and `aj.hermes.execution.v0` helpers were added, wired default-disabled/fail-closed with explicit feature/config/capability gates, integrated with execution/evidence/journal/receipt/audit flow, and covered by isolated unit/contract/security/fault-injection tests. Full AJ regression and health checks pass; controlled live AJ-mediated preflight succeeded in isolated in-memory enablement and normal runtime remains disabled/unattached.

## Actual implementation status
- [x] Phase 4B.0 design package read (`00-09`)
- [x] Git/runtime preflight recorded (AJ/JARVIS/AI_WORKSPACE helix/Drive hermes helix/~/.hermes/hermes-agent)
- [x] Hermes CLI/source/runtime inspected; exact status command safety evidence documented
- [x] CLI safety gate: **PASS (conditional, adapter-bounded)** — `01_PREFLIGHT_AND_CLI_SAFETY_VERIFICATION.md`
- [x] AJ regression baseline recorded before source changes
- [x] Minimal adapter + contract mapping implementation (`aj/hermes_adapter.py`, `aj/hermes_contract.py`)
- [x] Capability/auth/config/feature-flag wiring (default-disabled, fail-closed)
- [x] Operation evidence/journal/receipt/audit integration for HERMES execution path
- [x] Unit/contract/security/fault-injection tests added (no live Hermes dependency for normal suite)
- [x] Full regression + `python -m aj --check` passing after changes
- [x] Controlled live preflight (isolated, explicitly enabled in-memory, then restored/disabled state)
- [x] Final documentation package complete (`00-09`)

## Files created and modified (AJ-only, 4B.1)
- **Created (implementation):** `aj/hermes_contract.py`, `aj/hermes_adapter.py`
- **Modified (wiring, additive/default-safe):** `aj/config.py` (defaults: `feature_flags.hermes_execution_adapter=false`, `execution.hermes.*` disabled/bounded), `aj/runtime.py` (`_build_execution` fail-closed selection, assemble wiring), `aj/orchestrator.py` (build accepts execution, conditional `hermes.status.read` registration when enabled, HERMES execution evidence/receipt/journal/audit enrichment, safe idempotency handling)
- **Created (tests):** `tests/test_phase4b1_hermes_adapter.py`, `tests/test_phase4b1_hermes_security_faults.py`
- **Created (docs):** `ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/00`–`09`
- **Pre-existing tracked modifications/untracked files preserved:** all prior AJ M/?? entries remain present (including `aj/__main__.py, aj/diagnostics.py, aj/recovery.py, aj/task.py, aj/transfer.py`, prior test modifications, prior untracked modules/tests/audit dirs, `integrations/`, JARVIS/HELIX untracked dirty states untouched).

## Architecture decisions
- **Interface:** Hermes CLI subprocess, fixed argv `['<resolved-hermes>','gateway','status']`, `shell=False`, controlled env allowlist, bounded timeout/stdout/stderr, redaction, injectable runner for tests.
- **Capability:** `hermes.status.read` only, deny-by-default, registered/executable only when explicitly enabled; adapter/capability default-disabled.
- **Contract:** `aj.hermes.execution.v0` validation/mapping; honest status semantics (`completed/failed/rejected/timeout/unknown/requires_manual_review` vocabulary), `hermes_execution_id=null` (never fabricated).
- **Identity:** explicit `local_trust` (non-authenticated local assumption; not cryptographic/remote/multi-user auth).
- **Evidence/recovery:** task/attempt/audit/journal/receipt/memory integration with bounded sanitized payloads; no cross-store atomicity/exactly-once claims; unknown not coerced to success.

## CLI command safety evidence
`hermes gateway status` (no `--deep/--full`) selected as read-only diagnostic command from Hermes source inspection (`_cmd_status`, runtime snapshot/service-status readers) and bounded live probe (exit 0, active gateway). No session/agent/tool/skill/MCP/message mutation observed. Adapter bounds required and enforced: timeout, output caps/truncation, redaction, fixed argv, controlled env. Details: `01`, `07`, `08`.

## Test counts and results
- **Baseline (before changes):** `pytest -q` 433 passed, 13 warnings, 0 failed (39.63s); `aj --check` 23/23 ok.
- **New targeted:** `tests/test_phase4b1_hermes_adapter.py tests/test_phase4b1_hermes_security_faults.py` => 13 passed. Existing targeted sanity (`test_hermes_contract.py`, `test_foundation.py`, `test_orchestrator.py`) passed.
- **Post-change full:** `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` => **446 passed, 13 warnings, 0 failed** (64.02s). One intermediate run showed an environmental `sqlite3.OperationalError: disk I/O error` in forked `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` stress test; specific test and full suite passed on re-run (non-regression flake).
- **Health/self-check:** `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` => **exit 0, ok true, 23/23 checks, failures [], attached.hermes "NOT ATTACHED"**.

## Security findings
Fixed argv/no-shell, validated cli path, explicit capability allowlist, fail-closed validation/authz/trust checks, controlled env allowlist, bounded timeout/output, best-effort redaction, untrusted-output handling, no invented Hermes IDs, default-disabled integration. Residuals: unstructured/best-effort-redacted output, host-dependent service-status latency bounded by timeout, local_trust non-auth scope, no cooperative Hermes cancellation/native IDs, no atomicity/exactly-once claims. Details: `04`, `07`.

## Regression comparison
Baseline 433 passed / 13 warnings / 0 failed -> final 446 passed / 13 warnings / 0 failed (+13 new 4B.1 tests). No existing tests modified/weakened; `test_hermes_contract.py` and pre-existing suites preserved.

## Exact Git states before and after
- **Before (preflight, preserved):** AJ `main` `468fdce...` ahead 1, pre-existing tracked M in 12 files and extensive pre-existing untracked audit/modules/tests/integrations as recorded in `01`; JARVIS `audit/consolidation-2026-11-06` `d93c702...` (2 untracked chat history files); `AI_WORKSPACE/helix` clean `99c7a38...`; `Drive/hermes/helix` dirty/diverged `e8a64cf...` untouched; Hermes source detached `2bd378ed...` clean.
- **After (AJ only, post-implementation/test):** all pre-existing M/?? preserved; 4B.1 additions/modifications = M `aj/config.py, aj/orchestrator.py, aj/runtime.py` and ?? `aj/hermes_adapter.py, aj/hermes_contract.py, tests/test_phase4b1_hermes_adapter.py, tests/test_phase4b1_hermes_security_faults.py, ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/`. No JARVIS/HELIX/Hermes-source/runtime/symlink/service/config modifications.

## Feature flag state after testing
Default-disabled and unattached: `feature_flags.hermes_execution_adapter=false`, `execution.runtime="none"`, `execution.hermes.enabled=false`, `execution.hermes.capability_status_read_enabled=false`. Controlled live preflight used in-memory overrides only; `aj --check` confirms `attached.hermes: "NOT ATTACHED"`.

## Known limitations
- Single read-only capability (`hermes.status.read`) only; CLI text output unstructured/untrusted and may be truncated.
- `local_trust` non-authenticated; no cross-component verified identity propagation.
- No Hermes-native execution IDs, no cooperative Hermes cancellation, no exactly-once/cross-store atomicity guarantees.
- Host service-status query latency/behavior bounded but environment-dependent.

## Remaining risks
Hermes CLI/runtime behavior/version drift, unusual output/secret patterns escaping best-effort redaction, environment-specific blocking in status probes (mitigated by timeout), and future scope pressure to widen capabilities without equivalent safety gates.

## Recommended next phase
**Phase 4B.2 justified only for reliability/observability/fault-handling/recovery/security hardening of `hermes.status.read`** (not capability expansion). See `09_PHASE_4B_2_READINESS_AND_RECOMMENDATION.md`.

## Linked documents
- `01_PREFLIGHT_AND_CLI_SAFETY_VERIFICATION.md`
- `02_ADAPTER_ARCHITECTURE_AND_MODULE_MAP.md`
- `03_CONTRACT_AND_STATUS_MAPPING.md`
- `04_AUTHORIZATION_PERMISSION_AND_FEATURE_FLAGS.md`
- `05_OPERATION_EVIDENCE_AND_RECOVERY.md`
- `06_TEST_RESULTS_AND_FAULT_INJECTION.md`
- `07_SECURITY_REVIEW_AND_LIMITATIONS.md`
- `08_LIVE_INTEGRATION_VERIFICATION.md`
- `09_PHASE_4B_2_READINESS_AND_RECOMMENDATION.md`
