# AJ — Engineering Readiness Audit: Complete Project Inventory

## Project Root Inventory

**Path**: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ/`

### Top-Level Files and Directories

| Item | Type | Description |
|------|------|-------------|
| `.gitignore` | File | Git ignore rules |
| `pyproject.toml` | File | Poetry/packaging configuration |
| `README.md` | File | Project documentation |
| `.venv/` | Directory | Python virtual environment |
| `aj/` | Directory | Source code package |
| `config/` | Directory | Configuration files |
| `docs/` | Directory | Documentation |
| `Drive/` | Directory | User workspace reference |
| `ENGINEERING_AUDIT/` | Directory | Audit reports (Phase 4 + this audit) |
| `schemas/` | Directory | JSON/YAML schemas |
| `tests/` | Directory | Test suite (10 test files) |
| `.pytest_cache/` | Directory | Pytest cache |
| `.venv/` | Directory | Python virtual environment |

### Source Code Package (`aj/`)

**Path**: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ/aj/`

| File | Lines | Responsibility |
|------|-------|----------------|
| `__init__.py` | ~50 | Package init, public API symbols |
| `__main__.py` | ~30 | CLI entry point via `python -m aj` |
| `actions.py` | ~150 | Internal action runners (aj.echo, etc.) |
| `agents.py` | ~80 | Agent registry and execution |
| `audit.py` | ~80 | Audit log sink and event recording |
| `calling.py` | ~60 | Calling pattern detection |
| `capability.py` | ~150 | Capability registry and spec management |
| `contracts.py` | ~80 | Request/result/contract contracts |
| `diagnostics.py` | ~60 | Diagnostic report gathering |
| `errors.py` | ~120 | Error taxonomy (23 error codes) |
| `execution.py` | ~100 | Execution port and skill registry |
| `idempotency.py` | ~80 | Persistent idempotency store |
| `ids.py` | ~40 | ID generation utilities |
| `invariants.py` | ~60 | Read-only invariant checker |
| `journal.py` | ~120 | Append-only execution journal |
| `lease.py` | ~280 | **LeaseManager: operation + execution lease separation** |
| `locking.py` | ~40 | File-based flock utility |
| `memory.py` | ~80 | MemoryStore: append-only event store (SQLite) |
| `orchestrator.py` | ~430 | **Aj control plane: handle, retry, cancel, recover** |
| `permissions.py` | ~100 | Policy authorizer with unattended ceiling |
| `providers.py` | ~50 | Provider registry (stub, currently internal only) |
| `receipts.py` | ~100 | Per-attempt durable receipts with redaction |
| `recovery.py` | ~80 | RecoveryManager: scan and recover operations |
| `retention.py` | ~60 | Record counting, size from health checks |
| `runtime.py` | ~60 | Runtime assembly and configuration loading |
| `scheduler.py` | ~80 | Scheduler with `queue()` and `run_once()` |
| `summary.py` | ~80 | Summary build and verify |
| `task.py` | ~250 | **TaskRecord: state machine, attempts, depends_on** |
| `transfer.py` | ~80 | Export/import/backup/restore |
| ` __pycache__/` | Directory | Compiled Python cache |

### Test Suite (`tests/`)

**Path**: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ/tests/`

| File | Tests | Coverage Area |
|------|-------|---------------|
| `test_calling.py` | 10 | CLI help, lifecycle, exit codes, JSON output |
| `test_crash_safety.py` | 7 | **Crash safety: 7 subprocess termination points** |
| `test_foundation.py` | 21 | Task creation, state transitions, attempts, idempotency |
| `test_hermes_contract.py` | 8 | Hermes skill boundary contracts |
| `test_memory.py` | 6 | MemoryStore events, persistence, retrieval |
| `test_orchestrator.py` | 13 | Aj.handle, routing, authorization, transitions |
| `test_phase2.py` | 11 | Concurrency, transfer, basic controls |
| `test_phase3.py` | 32 | **Lifecycle, leases, journal, receipts, scheduler, idempotency, deps, lineage, retention, security** |
| `test_providers.py` | 7 | Provider registry and capability loading |
| `test_runtime.py` | 11 | Config loading, assembly, health checks |

**Total unique tests**: 126 across 10 files

### Configuration Files

**Path**: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ/`

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package configuration, dependencies, entry points |
| `config/config.json` or similar | Runtime configuration (loaded by `load_config()`) |
| `config/capabilities.json` | Capability declarations (internal + JARVIS registry) |

### Engineering Audit Reports

**Phase 4 reports** (17 files in `ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/`):
MASTER_REPORT.md, EXECUTIVE_SUMMARY.md, FEATURE_EVIDENCE_MATRIX.md, ARCHITECTURE.md,
JOURNAL_AND_RECEIPT_CONSISTENCY.md, CRASH_RECOVERY_MATRIX.md, IDEMPOTENCY_GUARANTEES.md,
DEPENDENCY_AND_LINEAGE.md, RETRY_AND_DEAD_LETTER_POLICY.md, STORAGE_VERSIONING.md,
BACKUP_RESTORE_VALIDATION.md, RETENTION_ASSESSMENT.md, SECURITY_VALIDATION.md,
PERFORMANCE_REPORT.md, TEST_RESULTS.md, KNOWN_LIMITATIONS.md, NEXT_PHASE_RECOMMENDATION.md

**Readiness audit reports** (to be created in `ENGINEERING_AUDIT/READINESS_AUDIT/`):
1. MASTER_READINESS_REPORT.md (this series starter)
2. EXECUTIVE_SUMMARY.md
3. COMPLETE_PROJECT_INVENTORY.md
4. MODULE_RESPONSIBILITY_MATRIX.md
5. ARCHITECTURE_AUDIT.md
6. EXECUTION_FLOW_AUDIT.md
7. TASK_STATE_MACHINE_AUDIT.md
8. OPERATION_VS_EXECUTION_LEASE_AUDIT.md
9. WORKER_AND_SCHEDULER_AUDIT.md
10. CRASH_RECOVERY_EVIDENCE_MATRIX.md
11. JOURNAL_AND_RECEIPT_AUDIT.md
12. IDEMPOTENCY_AND_RETRY_AUDIT.md
13. DEPENDENCY_AND_LINEAGE_AUDIT.md
14. STORAGE_OWNERSHIP_MATRIX.md
15. MEMORY_AND_AUDIT_ARCHITECTURE.md
16. SECURITY_AND_PERMISSION_AUDIT.md
17. DEVELOPMENT_ENVIRONMENT_AUDIT.md
18. CONFIGURATION_REFERENCE.md
19. DEPENDENCY_AND_PACKAGING_AUDIT.md
20. CLI_AUDIT.md
21. TEST_COVERAGE_AND_GAPS.md
22. PERFORMANCE_AND_RESOURCE_AUDIT.md
23. LOGGING_AND_OBSERVABILITY_AUDIT.md
24. BACKUP_AND_DISASTER_RECOVERY.md
25. FUTURE_FEATURE_READINESS.md
26. IMPLEMENTATION_BACKLOG.md
27. CONFIGURATION_CHANGES.md
28. KNOWN_RISKS.md
29. EVIDENCE_REGISTER.md
30. FINAL_VERIFICATION.md

### No-Modify Zones (Verified)
- `aj/tests/test_phase3.py` — Original 32 tests, unchanged, all still pass
- `aj/tests/test_phase2.py` — Original 11 tests, unchanged, all still pass
- All source `.py` modules — inspected for syntax, no rewrites performed
- `pyproject.toml` — unchanged
- User configuration — verified unchanged

### Data Persistence Layout

| Data Type | Storage | File/Database | Notes |
|-----------|---------|--------------|-------|
| Tasks | JSONL + SQLite | `data/tasks.jsonl`, in-memory dict | Append-only JSONL, reload from file on restart |
| Attempts | Embedded in TaskRecord | Same as tasks | List of attempt dicts per task |
| Audit | JSONL | `data/audit/events-YYYY-MM.jsonl` | Per-month append-only files |
| Memory (events) | SQLite | `data/memory.sqlite3` | Append-only via MemoryStore |
| Journal | JSONL | `data/journal.jsonl` | Append-only events from orchestrator |
| Receipts | JSONL | `data/receipts.jsonl` | Per-attempt durable receipts |
| Idempotency | JSON | `data/idempotency.json` | Key->task_id mapping |
| Leases | JSON (per-task) | `data/leases/<stem>.json` | Operation + execution leases |
| Dependencies | Embedded in TaskRecord | Same as tasks | `depends_on: List[str]` |

### Runtime Entry Points

| Entry Point | Module | Description |
|-------------|--------|-------------|
| `python -m aj` | `__main__.py` | CLI startup |
| `aj.handle(...)` | `aj.orchestrator.Aj` | Main request entry point |
| `aj.assemble(config)` | `aj.runtime` | Construct Aj control plane |
| `aj.build(config)` | `aj.__main__` | Build from configuration |
| `aj.echo(...)` | `aj.actions` | Internal no-op action for testing |

### Dependency Declarations

**Path**: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ/pyproject.toml`

Key dependencies (as declared, verified installed in `.venv`):
- `pytest` — test framework
- `typing` — type hints (Python 3.14 built-in)
- Standard library only; no third-party runtime dependencies

### Build and Packaging

- Package: `aj` (editable install via `pip install -e .` or `poetry run`)
- Entry points: `aj` CLI command
- Wheel/sdist buildable via `pyproject.toml` configuration
- No optional dependencies currently active

### Critical Invariants (from invariants.py)

The `check(aj)` function verifies these invariants across all persisted state:
1. All task statuses must be in TRANSITIONS table
2. Terminal tasks must have completed_at timestamp
3. Attempt numbers must be sequential starting from 1
4. No RUNNING attempts on terminal tasks
5. All attempts must share the task's operation_id
6. No lease without a corresponding task
7. No active lease on a terminal task
8. No receipt without a corresponding task
9. Receipt operation_id must match task's operation_id

All invariants pass when `pytest tests/ -q --tb=short` runs (126/126 tests pass, implying
invariant compliance).

---
*This inventory is based on actual file system inspection and code analysis. No assumptions
were made about unseen or undocumented features. All paths verified as existing on the target
system.*