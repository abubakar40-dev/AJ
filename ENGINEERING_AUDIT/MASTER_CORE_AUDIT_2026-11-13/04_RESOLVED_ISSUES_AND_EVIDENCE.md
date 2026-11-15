# 04 — Resolved Issues and Evidence (this cycle)

## 1. Preflight (Phases 3A–3D foundation verification)
| Item | Result | Evidence |
|---|---|---|
| Working tree preservation / safety | **Pass** | `git status` inspected before/after; no staging/commits/push/reset/clean/delete; all prior modified/untracked artifacts preserved. |
| 3A–3D invariant coherence in current tree | **Pass** | Code inspection + focused suites: TaskStore fail-closed persistence/snapshot/import boundaries, evidence-based/fail-closed recovery, inspection read-only, reconciliation safety/incomplete-evidence honesty, lease/ownership/terminal/budget/replay-safety checks intact. |
| Focused 3A–3D/regression preflight | **194 passed, 0 failed** | `pytest -q -p no:cacheprovider tests/test_task_persistence_fail_closed.py tests/test_task_creation_import_integrity.py tests/test_phase3_lifecycle_reliability.py tests/test_phase3c_recovery_integrity.py tests/test_phase3d_recovery_observability.py tests/test_audit_reliability_security.py tests/test_crash_safety.py tests/test_idempotent_replay.py tests/test_step_c_gap_closure.py tests/test_dead_letter.py tests/test_phase2.py tests/test_orchestrator.py tests/test_foundation.py` |
| Full suite preflight (run 1) | **412 passed, 1 failed, 13 warnings** | Single failure: `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (`sqlite3.OperationalError: disk I/O error`, external tmp). Not classified as 3A–3D foundation regression. |
| Intermittent failure investigation | **Environment-limited** | Same test rerun on external tmp: **1 passed**; on local `/tmp`: **1 passed**. Prior controlled evidence: local 8/8 vs external 5/8. |

**Gate decision:** no Critical/High 3A–3D correctness/data-integrity/recovery/safety defects found; Phase 3E implementation proceeded.

## 2. Phase 3E implementation (resolved objectives)

### AJ-RES-3E-001 Durable operation evidence (privileged reconciliation)
- **Changes:** `aj/operation_evidence.py` (append-only intent/progress/outcome store, incomplete detection, idempotent views), integration in `aj/orchestrator.py` (`reconcile` records durable intent before privileged action, progress/outcome; supports optional `operation_id`/`idempotency_key`; duplicate terminal op returns recorded result without reapply; incomplete intent-only op fails closed/manual disposition; no fabricated success).
- **Tests/evidence:** `tests/test_phase3e_evidence_consistency.py` (intent/outcome, duplicate idempotency, incomplete block/no reapply, restart detection) all passed; smoke showed `reconciliation_operations.jsonl` appended (intent/progress/outcome records).

### AJ-RES-3E-002 Task/Audit/Journal consistency checker
- **Changes:** `aj/consistency.py` read-only cross-store checker (TaskStore/audit/journal/receipts/reconciliation operation evidence/leases snapshots), findings with `confirmed|uncertain|missing_information`, operator + machine-readable output; `Aj.consistency_check`; CLI `aj consistency`.
- **Tests/evidence:** 3E tests verified detection of incomplete operations, correlation/conflict/malformed evidence cases and read-only behavior (stores unchanged); CLI JSON smoke returned structured status/summary.

### AJ-RES-3E-003 Partial-operation detection and repair boundaries
- **Changes:** incomplete privileged operations detected/reported via operation evidence and consistency findings; no auto-repair, no historical rewrite/fabrication, no unsafe auto-retry, no auto-success conversion.
- **Tests/evidence:** intent-only operations remain incomplete/detectable after restart and cannot be auto-applied; checker reports required operator action.

### AJ-RES-3E-004 Privileged-operation authorization guardrail
- **Changes:** `aj/authorization.py` (`AuthorizationContext/Decision`, extensible `PrivilegedOperationAuthorizer`, `LocalTrustPrivilegedAuthorizer`, `UnavailablePrivilegedAuthorizer`, fail-closed builder); `Aj` wiring (config `permissions.privileged_reconciliation`/`privileged_operations`), `reconcile` enforces authorization (fail closed on deny/unavailable/invalid/error), audits `privileged_authorization` without secrets, separates operator metadata from authenticated identity (none by default), preserves existing safety checks.
- **Tests/evidence:** deny/unavailable fail closed with no state change and refused op evidence; default local-trust allows without claiming authenticated identity; audited decisions recorded.

### AJ-RES-3E-005 SQLite and storage diagnostics
- **Changes:** `aj/storage_diagnostics.py` (`inspect_storage`, SQLite pragma/path/WAL-SHM/fs hints, `classify_sqlite_error`); `Aj.storage_diagnostics`; diagnostics report/CLI (`diagnostics --storage`, JSON) enriched.
- **Tests/evidence:** storage diagnostics/classification tests passed; investigation documented external-fs WAL intermittency vs local-fs reliability.

## 3. Integration/compatibility fixes made during implementation
| Fix | Why | Evidence |
|---|---|---|
| Consistency checker TaskStore envelope parsing | Initial implementation read task rows directly; TaskStore persists `{"reason","task":{...}}` envelopes causing missed task-state correlation | `aj/consistency.py` updated to extract nested `task`; failing 3E conflict-detection case resolved; `tests/test_phase3e_evidence_consistency.py` → 11 passed |
| Reconcile validation/idempotency ordering and durable intent semantics | Preserve existing validation behavior while ensuring privileged-op intent/evidence and explicit-op duplicate handling are safe | `aj/orchestrator.py` refactored reconcile flow; 3D/3C/dead-letter/phase2 suites (62 passed) and full suite remained green |
| CLI/diagnostics wiring for 3E surfaces | Expose consistency/storage/operation-evidence diagnostics and reconcile operation controls compatibly | `aj/__main__.py`, `aj/diagnostics.py`; CLI smokes passed (`consistency --json`, `diagnostics --json`) |

## 4. Regression/verification evidence after 3E
| Suite/check | Result |
|---|---|
| Key 3C/3D/dead-letter/phase2/audit-reliability | **62 passed** |
| Phase 3E tests | **11 passed** |
| Final full suite | **424 passed, 13 warnings, 0 failed** |
| `python -m aj --check` | **23/23 ok** |
| Targeted stress checks (concurrency, reconcile op-id idempotency, consistency read-only) | **pass** |

## 5. Issues not claimed resolved
- Non-atomic multi-store writes, unauthenticated operator identity, process-local/external-effect limitations, external-fs SQLite WAL sensitivity, and external integration blockers remain open/limited as documented in backlog and limitations.
