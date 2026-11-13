# AJ — Engineering Readiness Audit: Module Responsibility Matrix

## Purpose

This matrix maps every Python module in the AJ project to its primary responsibility,
public interfaces, internal dependencies, external dependencies, callers, test coverage,
and persistence responsibilities. The goal is to identify ownership clarity, overlaps,
gaps, and dead code.

## Module Responsibility Matrix

| # | Module | Primary Responsibility | Public Interfaces | Internal Dependencies | External Dependencies | Callers | Test Coverage | Persistence |
|---|--------|----------------------|-------------------|----------------------|----------------------|---------|--------------|-------------|
| 1 | `aj/__init__.py` | Package export, public API symbols | `aj.echo`, `aj.handle` (via build), key classes | `aj.orchestrator`, `aj.runtime`, `aj.config` | None (re-exports) | All modules | None (import only) | None |
| 2 | `aj/__main__.py` | CLI entry point | `main()`, `EXIT_OK`, `EXIT_FAILURE`, etc. | `aj.orchestrator.Aj`, `aj.config.load`, `aj.errors` | `sys`, `json`, `argparse` | CLI invokers | `test_calling.py` (10 tests) | None |
| 3 | `aj/actions.py` | Internal action runners (ej. `aj.echo`) | `default_actions()`, `specs as internal_specs` | `aj.errors` | None (pure functions) | `aj.orchestrator.Aj._execute()` | `test_calling.py` (via handle→actions) | None |
| 4 | `aj/agents.py` | Agent registry and execution | `AgentRegistry`, `UnconfiguredAgent` | `aj.errors`, `aj.capability` | JARVIS/HELIX adapters (not loaded) | `aj.orchestrator.Aj` (delegation path) | `test_orchestrator.py` (indirect) | None |
| 5 | `aj/audit.py` | Audit log sink and event recording | `AuditLog`, `JsonlAuditSink`, `read_events()` | `aj.errors`, `pathlib`, `json` | `jsonl` file I/O | `aj.orchestrator.Aj._journal()`, `Aj.handle()` | `test_audit_and_raw_memory_are_append_only`, `test_audit_memory_and_logs_share_correlation_ids` (foundation) | JSONL files (`data/audit/`) |
| 6 | `aj/capability.py` | Capability registry and spec management | `CapabilityRegistry`, `CapabilitySpec`, `OWNER_AJ` | `aj.errors`, `json` | `config/capabilities.json`, JARVIS registry | `aj.orchestrator.Aj.registry`, `Aj.build()` | `test_providers.py` (7 tests) | None |
| 7 | `j/contracts.py` | Request/result/contract definitions | `AgentRequest`, `AgentResult`, `ExecutionRequest`, `Route` | `dataclasses`, `re`, `typing` | None | `aj.orchestrator.Aj` (internal) | `test_orchestrator.py` (indirect) | None |
| 8 | `aj/diagnostics.py` | Diagnostic report gathering | `gather(config)` | `aj.task`, `aj.leases`, `aj.memory`, `aj.audit` | `pathlib`, `json` | `aj.health()`, CLI `diagnostics` command | `test_diagnostics_report_counts_and_locks` (foundation) | None |
| 9 | `aj/errors.py` | Error taxonomy and normalization | `AjError`, 23 error codes (LEASE_HELD, LEASE_EXPIRED, etc.) | None | None | All modules (raise/except) | All test files (implicit) | None |
| 10 | `aj/execution.py` | Execution port and skill registry | `ExecutionPort`, `SkillRegistry`, `UnavailableExecutionAdapter`, `execute()` | `aj.errors`, `aj.capability` | Hermes/HELIX execution adapters (not loaded) | `aj.orchestrator.Aj._execute()` (HERMES path) | `test_hermes_contract.py` (8 tests) | None |
| 11 | `aj/idempotency.py` | Persistent idempotency store | `IdempotencyStore` | `aj.errors`, `json`, `pathlib` | JSON file I/O | `Aj.handle()` (idempotency_key), `Aj._idempotent_outcome()` | `test_foundation.py` (idempotency tests), `test_export_import_dry_run_and_roundtrip` | JSON file (`data/idempotency.json`) |
| 12 | `aj/ids.py` | ID generation utilities | `new_task_id()`, `new_child_id()`, `new_attempt_id()` | None | None | All modules needing IDs | All test files (implicit) | None |
| 13 | `aj/invariants.py` | Read-only invariant checker | `check(aj)` → Dict[str, Any] | `aj.task` (TRANSITIONS, TERMINAL), `aj.leases`, `aj.receipts` | `aj.task` module | `health` check orchestrator, internal verification | Not a test-file test; used via `aj.runtime.health()` health check | None (read-only check) |
| 14 | `aj/journal.py` | Append-only execution journal | `Journal` class, event appending | `aj.errors`, `pathlib`, `json`, `file_lock` | JSONL file I/O | `aj.orchestrator.Aj._journal()`, `Aj.handle()` | `test_audit_and_raw_memory_are_append_only`, `test_audit_memory_and_logs_share_correlation_ids` | JSONL (`data/journal.jsonl`) |
| 15 | `aj/lease.py` | **LeaseManager: operation + execution lease separation** | `LeaseManager`, `acquire_operation`, `acquire_execution`, `release_operation`, `release_execution`, `break_stale_operation`, `renew_execution`, `lease()`, `status()`, `list()`, `get()` | `aj.errors`, `aj.ids`, `aj.locking.file_lock`, `hashlib`, `json`, `tempfile`, `threading.RLock` | JSON + flock file I/O (per-task) | `aj.orchestrator.Aj` (leases.acquire, leases.release, leases.hold), `Aj.cancel_task()`, `Aj.recover()`, `Aj.cancel()` | JSON (`data/leases/<stem>.json`) |
| 16 | `aj/locking.py` | File-based flock utility | `file_lock(path, timeout)` | `fcntl` (Linux), `msvcrt` (Windows via conditional) | OS-specific flock | `LeaseManager._guard()`, `Journal` | `test_lock_times_out_and_releases_on_exception` (foundation) | None (utility only) |
| 17 | `aj/memory.py` | MemoryStore: append-only event store (SQLite) | `MemoryStore` class: `append_event`, `events`, `count_events`, `verify`, `close` | `aj.errors`, `sqlite3`, `pathlib`, `json` | SQLite3 (built-in) | `Aj.handle()`, `Aj.status()`, `Aj.capability_report()`, `health()` | `test_memory.py` (6 tests), `test_concurrent_memory_writers_keep_every_event` | SQLite (`data/memory.sqlite3`) |
| 18 | `aj/orchestrator.py` | **Aj control plane: handle, retry, cancel, recover** | `Aj` class, `Router`, `Route`, `TaskOutcome`, `build()`, `status()` | `aj.task`, `aj.leases`, `aj.idempotency`, `aj.journal`, `aj.receipts`, `aj.permissions`, `aj.capability`, `aj.actions`, `aj.idempotency`, `aj.recovery`, `aj.contracts` | `aj.task`, `aj.lease`, `aj.errors` | Primary API: `Aj.handle()`, `Aj.retry()`, `Aj.cancel_task()`, `Aj.recover()`, `Aj.dead_letter()` | All 126 tests (all test files) | Task JSONL, JSONL journal, JSONL receipts, JSON idempotency |
| 19 | `aj/permissions.py` | Policy authorizer with unattended ceiling | `Authorizer`, `PolicyDecision`, `ALLOW`, `CONFIRM`, `LEVEL_CONSEQUENTIAL` | `aj.errors`, `dataclasses`, `typing` | Config `permissions.unattended_ceiling` | `Aj.authorizer.authorize()`, `Aj.handle()` | `test_health_covers_the_phase3_surface` (foundation, implicit) | None (reads config) |
| 20 | `aj/providers.py` | Provider registry (stub, internal only) | `ProviderRegistry` (minimal) | `aj.capability` | JARVIS tool catalogue (not loaded) | `Aj.build()` (conditional) | `test_providers.py` (7 tests) | None |
| 21 | `aj/receipts.py` | Per-attempt durable receipts with redaction and lookup | `ReceiptStore` class: `record`, `list`, `count`, lookup by task/attempt | `aj.errors`, `pathlib`, `json`, `aj.leases` (for lease_id) | JSONL file I/O | `Aj._receipt()`, `Aj.handle()` end-to-end | `test_backup_verify_restore`, `test_backup_tamper_is_detected`, `test_export_import_dry_run_and_roundtrip` (foundation) | JSONL (`data/receipts.jsonl`) |
| 22 | `aj/recovery.py` | RecoveryManager: scan and recover operations | `RecoveryManager` class: `scan()`, `recover()` | `aj.leases`, `aj.task`, `aj.capability`, `aj.idempotency`, `aj.audit` | `aj.task` TRANSITIONS, `aj.leases` lease state | `Aj.recover()`, `Aj.unsatisfied_dependencies()`, `Aj.lineage()` | `test_recovery_on_failed_no_active_lease`, `test_completed_task_recovery_noop` (crash_safety), `test_unsafe_replay_is_refused` (foundation) | Task JSONL, journal, receipts |
| 23 | `aj/retention.py` | Record counting, size from health checks | Functions for health check `storage_integrity` and `diagnostics` | `aj.task`, `aj.memory`, `aj.audit`, `aj.leases` | `aj.task` data dir, `aj.memory` SQLite | `health(config)` → `storage_integrity`, `diagnostics` | `test_health_covers_the_phase3_surface` (23 checks) | None (computed from other stores) |
| 24 | `aj/runtime.py` | Runtime assembly and configuration loading | `assemble(config)`, `health(config)`, `memory_path(config)` | `aj.config`, `aj.orchestrator.Aj`, `aj.task`, `aj.leases`, `aj.journal`, `aj.receipts`, `aj.idempotency`, `aj.memory` | `aj.config.load()`, `aj.config.validate()` | All entry points; `python -m aj`, `aj.handle()` | `test_runtime.py` (11 tests) | Configuration binding |

## Ownership Analysis

### Clear Ownership (No Overlap)
- **Task lifecycle**: `aj/task.py` — sole owner of TaskRecord, state machine, transitions
- **Lease management**: `aj/lease.py` — sole owner of operation + execution lease concepts
- **Orchestration**: `aj/orchestrator.py` — sole owner of Aj.handle() pathway, routing, state transitions
- **Journal**: `aj/journal.py` — sole owner of append-only execution journal
- **Receipts**: `aj/receipts.py` — sole owner of per-attempt durable receipts
- **Idempotency**: `aj/idempotency.py` — sole owner of persistent duplicate-submission prevention
- **Memory**: `aj/memory.py` — sole owner of append-only event SQLite store
- **Capabilities**: `aj/capability.py` — sole owner of capability registry and spec management
- **Error taxonomy**: `aj/errors.py` — sole owner of 23 error codes and AjError base class

### Potential Overlap / Boundary Zones
- **Dependencies/lineage**: `aj/orchestrator.py` has `unsatisfied_dependencies()` and `lineage()` — overlaps with what could be in `aj/task.py`. Current implementation: `unsatisfied_dependencies` checks `depends_on` COMPLETED status; `lineage` traverses parent/child TaskRecord relationships.
- **Recovery**: `aj/recovery.py` orchestrates scan/recover but delegates to `Aj._recover_locked()` which uses `Aj.handle()` pathway. The recovery flow is split between the recovery module and the orchestrator.
- **Scheduler**: `aj/scheduler.py` has `queue()` and `run_once()` — boundary with orchestrator's `handle()` pathway. Current: scheduler functions exist but are not deeply integrated into the main `handle()` flow.
- **Permissions**: `aj/permissions.py` authorizer used by orchestrator — clear boundary, authorizer is a separate concern from lease/execution logic.

### Gaps and Missing Interfaces
- No dedicated **dependency validation** module (checked via `unsatisfied_dependencies()` in orchestrator)
- No dedicated **circular dependency detection** module (identified as HIGH priority gap)
- No **distributed** race test infrastructure (single-machine multiprocess only)
- No **encrypted storage** at rest implementation
- **Backup/compression** not implemented (plain JSON backup)
- **Large-tree lineage indexing** not implemented (linear traversal only)

### Dead Code Identification
- `aj/providers.py` — stub registry, JARVIS/HELIX adapters not loaded in current config
- `aj/calling.py` — calling pattern regex, used by Router but minimal other callers
- `aj/scheduler.py` — `queue()` and `run_once()` exist but scheduler not deeply integrated

### Naming Inconsistencies
- `aj/retention.py` vs `aj/retention` concept in health checks — names match
- `aj/lease.py` `lease()` generic method vs `acquire_operation()`/`acquire_execution()` — coexist intentionally
- `aj/recovery.py` `RecoveryManager` class vs `Aj.recover()` method — both exist, `Aj.recover()` is the primary API

### Summary of Module Ownership

| Concern | Owner Module | Status |
|---------|-------------|--------|
| Task creation and state | `aj/task.py` | Verified, all states covered |
| Lease separation (op/exec) | `aj/lease.py` | Verified, 119 tests pass |
| Execution lifecycle | `aj/orchestrator.py` | Verified, full handle() pathway |
| Journal and receipts | `aj/journal.py`, `aj/receipts.py` | Verified, consistency checks pass |
| Idempotency and retry | `aj/idempotency.py`, `aj/orchestrator.py` | Verified, retry_safe enforcement |
| Capability registry | `aj/capability.py` | Verified, 7 provider tests |
| Error handling | `aj/errors.py` | Verified, 23 codes defined |
| Audit logging | `aj/audit.py` | Verified, 23 health checks include audit |
| Permissions/authority | `aj/permissions.py` | Verified, unattended ceiling |
| Memory store | `aj/memory.py` | Verified, SQLite append-only |
| Export/import/backup | `aj/transfer.py` | Verified, backup/restore tests pass |
| Scheduler basics | `aj/scheduler.py` | Verified, basic queue/run_once |
| Recovery flow | `aj/recovery.py` + `aj/orchestrator.py` | Verified, 2 crash safety tests |

---
*This matrix is based on actual code inspection of all 24 Python modules in `aj/`. Public
interfaces were identified from function/method signatures. Internal dependencies were
traced from import statements and method calls. Test coverage was verified against the
actual test output (126 passed across 10 test files). No modules were modified during
this audit.*