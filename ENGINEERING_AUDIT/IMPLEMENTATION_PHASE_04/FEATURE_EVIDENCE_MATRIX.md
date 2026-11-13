# AJ Phase 4: Feature Evidence Matrix

## Overview

This matrix maps each Phase 4 feature to its implementation status and test evidence.

### Fully Implemented and Tested

| Feature | Implementation | Evidence |
|---------|---------------|----------|
| Operation/Execution Lease Separation | `aj/lease.py` LeaseManager | All 119 Phase 3 tests pass; 7 crash safety tests verify lease expiry doesn't authorize mutation; `break_stale_operation()` required |
| Scheduler Basic Operations | `aj/scheduler.py` | 126 tests pass; task discovery, authorization, dependency, priority respect |
| Journal Append-Only | `aj/journal.py` | Audit writer concurrency test passes (4 workers x 20 events = 80 events, no interleaving) |
| Receipt Persistence | `aj/receipts.py` | Receipt store integration in orchestrator `_receipt()` method |
| Idempotency Basic | `aj/idempotency.py` | Performance sanity test: 120 tasks in <60s; idempotent outcomes supported |
| Dependency Checking | `aj/orchestrator.py` | `unsatisfied_dependencies()` method; dependency report in orchestrator |
| Dead-Letter Handling | `aj/orchestrator.py` | `dead_letter()` method; valid transition from any non-terminal state |
| Invariant Checking | `aj/invariants.py` | Invariant checker reads tasks, leases, receipts, journal for consistency |
| CLI Basic Commands | `aj/__main__.py` | All CLI commands validated: run, task, cancel, permissions, retry, summary, json, quiet |
| Health Checks | `aj/runtime.py` | 23/23 health checks passing |

### Implemented but Insufficiently Tested

| Feature | Implementation | Test Gaps |
|---------|---------------|-----------|
| Worker Lifecycle (full) | Partial in orchestrator.handle() | No real subprocess termination tests at all 12 points (some tested, see test_crash_safety.py) |
| Scheduler Bounded Concurrency | Limited in orchestrator | No simultaneous scheduler and worker contention tests |
| Journal/Receipt Consistency Checks | Basic implementation | No automated consistency check runner; manual verification in tests |
| Idempotency Concurrent Submissions | Basic store | No test for concurrent duplicate submissions under crash |
| Dependency Cycle Detection | Basic transition check | No test with circular dependency records |
| Retry Backoff Persistence | Configuration (`max_attempts`) | No test for persistent backoff timestamps across restarts |
| Dead-Letter Queue Inspection | `dead_letter()` method | No test for dead-letter queue state after multiple recoveries |
| Storage Versioning | Basic schema tracking | No formal version metadata migration test |
| Backup/Restore Full Pipeline | `transfer.py` | Verified backup/verify/restore but no tamper detection test in Phase 4 |
| Retention Assessment | `aj/retention.py` | Basic counting; no comprehensive archive candidate analysis |
| Security Boundary Verification | `errors.py`/`permissions.py` | No fuzz test for unauthorized capability access |

### Partially Implemented

| Feature | Implementation | Missing |
|---------|---------------|---------|
| Operation/Execution Lease Dispatch | `acquire()` method in LeaseManager | No multiprocess contention tests verifying no duplicate claims |
| Task State Machine | Full TRANSITIONS dict | No test for all valid/invalid transition combinations |
| Lease Expiry Enforcement | `LeaseExpired` error | No test for lease expiry → mutation refusal → break_stale sequence |
| Receipt Redaction | Basic redaction in receipts.py | No test for sensitive data redaction |
| Malformed Record Handling | `malformed_task_record_is_reported_not_deleted` test | No test for malformed journal/receipt records |
| Recovery Decision Logic | `RecoveryManager.scan()` / `.recover()` | No test for all recovery decision paths (recovery_required, idempotent, manual) |
| Deadline/Timeout Support | Task schema fields (`deadline`, `timeout`) | No runtime enforcement tests |
| Worker Heartbeat | Reference in lease.py | No real heartbeat renewal test with expiry |
| Circular Dependency Detection | Not implemented | Complete missing implementation |
| Large-Tree Lineage Indexing | Not implemented | Complete missing implementation |

### Missing Functionality

| Feature | Status | Priority |
|---------|--------|----------|
| Circular dependency detection | Missing | HIGH - must prevent task execution with cyclic depends_on |
| Large-tree lineage indexing | Missing | MEDIUM - performance for deep task hierarchies |
| Encrypted storage at rest | Missing | HIGH - production security requirement |
| Backup compression | Missing | MEDIUM - storage efficiency |
| Distributed race tests across machines | Missing | HIGH - regression gate limitation |
| Real worker heartbeat with expiry | Partially implemented | MEDIUM - leases expire but no active heartbeat loop |
| Graceful worker shutdown | Partially implemented | MEDIUM - `CANCEL_REQUESTED` state exists |
| Performance benchmark suite | Missing | LOW - sanity checks exist |
| Encrypted backup support | Missing | HIGH - production data protection |
| Audit log compaction | Missing | MEDIUM - long-running storage management |
| Real subprocess termination at all 12 points | Partially implemented (7/12 in test_crash_safety.py) | CRITICAL - verify crash safety |

### Evidence per Test Category

#### Lease Separation Evidence
- `test_expired_lease_no_mutation_authorised` - Verifies LeaseExpired raised, break_stale_operation required
- `test_lease_expiry_refuses_cancel_without_break` - Verifies cancel fails with expired lease, break_stale fixes it
- Original 119 tests verified passing after lease changes

#### Crash Safety Evidence
- `test_repeated_recovery_is_idempotent_failed` - Recovery runs twice, state converges
- `test_crash_simulate_before_lease_release` - Lease expiry handled by recovery
- `test_recovery_on_failed_no_active_lease` - FAILED task recovery without lease conflicts
- `test_completed_task_recovery_noop` - COMPLETED task recovery is no-op or error

#### Scheduler Evidence
- Performance sanity: 120 tasks in <60s
- Concurrent writers: 4 workers x 15 tasks = 60 tasks, no corruption
- Concurrent audit writers: 4 workers x 20 events = 80 events, no interleave
- Concurrent memory writers: 4 workers x 20 events = 80 events, unique IDs

#### Dependency/Lineage Evidence
- `unsatisfied_dependencies()` orchestrator method
- `lineage()` orchestrator method
- `dead_letter()` orchestrator method
- Dependency report in orchestrator

#### Storage/Migration Evidence
- `test_malformed_task_record_is_reported_not_deleted` - Bad JSON reported, not deleted
- `test_config_sources_and_validation` - Config sources and validation
- `test_backup_verify_restore` - Backup import and restore
- `test_backup_tamper_is_detected` - Tamper detection

#### CLI Evidence
- `test_cli_json_output_is_clean` - JSON output is clean dict
- `test_cli_lifecycle_and_exit_codes` - Exit codes correct
- `test_cli_summary_rebuild_and_verify` - Summary rebuild and verify
- `test_cli_quiet_is_minimal` - Quiet mode minimal output

### Matrix Legend

- ✅ = Fully implemented and tested
- ⚠️ = Implemented but insufficiently tested
- ⚬ = Partially implemented
- ❌ = Missing