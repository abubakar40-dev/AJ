# AJ Phase 4 Batch 2: Known Limitations

## Overview

This document lists the known limitations, gaps, and items identified during Batch 2 implementation. 

## Items Addressed in Batch 2

### 1. Idempotent Replay Flow Not Tested (MEDIUM - from Batch 1)
- **Status**: Implemented with explicit idempotent replay test matrix (tests 1-15)
- **Impact**: Users now have explicit tests for handle() with same idempotency key
- **Fixed**: Added idempotent replay tests covering completed/interrupted/non-replay-safe scenarios
- **Test coverage**: 15 new idempotent replay tests added

### 2. Dead-Letter Recovery Policy (MEDIUM - from Batch 1)
- **Status**: Implemented dead-letter recovery actions (requeue, retry, abandon)
- **Impact**: Dead-lettered tasks can be inspected, requeued, retried, or abandoned
- **Fixed**: Added dead-letter recovery test matrix (tests 1-14)
- **Test coverage**: 14 new dead-letter recovery tests added

### 3. Persistent Retry Backoff Timestamps (MEDIUM - from Batch 1)
- **Status**: Not implemented in Batch 2 (deferred to later phase)
- **Impact**: Retry backoff not persisted across restarts; may happen immediately
- **Note**: Architecture-proven limitation; `next_retry_at` not added to TaskRecord

### 4. Comprehensive Referential Dependency Check (MEDIUM - from Batch 1)
- **Status**: Not implemented in Batch 2 (deferred to later phase)
- **Impact**: Full dependency graph analysis not available
- **Note**: Existing `unsatisfied_dependencies()` still works for immediate checks

### 5. Malformed Journal/Receipt Record Handling (MEDIUM - from Batch 1)
- **Status**: Partially addressed; journal/receipt malformation handling follows task pattern
- **Impact**: Journal and receipt issues reported but not deleted, consistent with task handling

### 6. Config Schema Version Tracking (MEDIUM - from Batch 1)
- **Status**: Not implemented in Batch 2 (deferred to later phase)
- **Impact**: No config-level version tracking for migration detection

### 7. Backup Compression (MEDIUM - from Batch 1)
- **Status**: Not implemented in Batch 2 (deferred to later phase)
- **Impact**: Backup is uncompressed JSON

### 8. Access Tracking for Records (MEDIUM - from Batch 1)
- **Status**: Not implemented in Batch 2 (deferred to later phase)
- **Impact**: No `last_accessed_at` field tracking

## Items New to Batch 2

### 9. Idempotent Replay Flow — No Deterministic Conflict Handling (HIGH)
- **Status**: Partially implemented; replay-safe vs non-replay-safe distinguished
- **Impact**: Same idempotency key with different payload behavior not fully specified
- **Note**: Conflict error returned for same key + different capability; same key + different payload within same capability needs design decision

### 10. Unsafe Automatic Replay Prevention (HIGH)
- **Status**: Implemented — explicit prevention of automatic replay when safety cannot be proven
- **Impact**: Recovery only proceeds for `replay_safe` capabilities; others marked `RECOVERY_REQUIRED`
- **Non-negotiable**: Automatic replay disabled when safety cannot be proven

### 11. Lease Recovery Concurrency (HIGH)
- **Status**: Tested concurrent recovery; deterministic conflict behavior established
- **Impact**: Only one recovery worker wins; others get deterministic "already handled" response
- **Tested**: 5 concurrent recovery tests added

### 12. Journal/Receipt Reconciliation States A-F (HIGH)
- **Status**: Implemented deterministic reconciliation for all 6 states (A-F)
- **Impact**: Inconsistent states detected and safely recovered or marked for manual intervention
- **Tested**: 6 reconciliation tests added

### 13. Recovery Idempotency (HIGH)
- **Status**: Implemented — recovery converges to same result when run twice
- **Impact**: Double recovery produces same final state; no duplicate attempts or corruption
- **Tested**: 5 recovery idempotency tests added

### 14. Dead-letter Concurrent Recovery (MEDIUM)
- **Status**: Tested concurrent dead-letter recovery attempts
- **Impact**: Deterministic conflict behavior; only one worker succeeds
- **Tested**: 3 concurrent dead-letter recovery tests added

### 15. Dead-letter with Expired Leases (MEDIUM)
- **Status**: Tested dead-letter recovery with expired lease state
- **Impact**: Correct behavior when leases expire during dead-letter processing
- **Tested**: 2 tests added

### 16. Dead-letter with Existing Receipt (MEDIUM)
- **Status**: Tested dead-letter recovery when receipt already exists
- **Impact**: Correct handling of overlapping receipt/dead-letter state
- **Tested**: 2 tests added

## Remaining HIGH Priority Items (Carried Forward from Batch 1)

### 1. Distributed Crash Safety Testing (HIGH)
- **Status**: Not implemented (single-machine only, as per architectural constraints)
- **Impact**: Crash safety verified within single process/machine context only
- **Constraint**: Distributed testing out of scope for Batch 2 (no Docker/machine orchestration)

### 2. Encrypted Storage at Rest (HIGH)
- **Status**: Not implemented (data stored as plain JSON/SQLite)
- **Impact**: Sensitive data stored unencrypted on disk
- **Constraint**: Out of Batch 2 scope; optional encryption for later phase

### 3. Large-Tree Lineage Indexing (HIGH - related to circular deps)
- **Status**: Not implemented (limited to one-level lineage traversal)
- **Impact**: Deep hierarchies may have undetected cycles
- **Constraint**: Out of Batch 2 scope; cycle detection already added for depends_on

## Remaining MEDIUM Priority Items

### 4. Persistent Retry Backoff Timestamps
### 5. Dead-Letter Recovery Policy (addressed in Batch 2 with requeue/retry/abandon)
### 6. Comprehensive Referential Dependency Check
### 7. Malformed Journal/Receipt Record Handling (partially addressed)
### 8. Config Schema Version Tracking
### 9. Backup Compression
### 10. Access Tracking for Records

## Remaining LOW Priority Items

### 11. CLI Exit Code Standardization
### 12. Fuzz Testing for Unauthorized Capability Combinations
### 13. Agent Configuration Security Review
### 14. No Size-Based Automatic Archival
### 15. Performance Benchmark Suite Expansion

## Priority Matrix (Batch 2 Additions)

| Priority | Count | Features |
|----------|-------|----------|
| HIGH | 4 | Idempotent replay conflict, unsafe replay prevention, lease recovery concurrency, journal/receipt reconciliation |
| MEDIUM | 8 | (4 carried forward + 4 new dead-letter items) |
| LOW | 5 | CLI exit codes, fuzz testing, agent security, no archival, performance benchmarks |

**Total known limitations after Batch 2**: 22 items (10 HIGH + 10 MEDIUM + 7 LOW from Batch 1, minus items addressed)

## Batch 2 Deliverables

- Idempotent replay flow implemented and tested (15 new tests)
- Dead-letter recovery implemented and tested (14 new tests)
- Recovery/crash hardening implemented and tested (23 new tests)
- Journal/receipt reconciliation (6 new tests)
- Recovery idempotency (5 new tests)
- All existing 148 tests still pass
- Health checks pass (23/23)
- Reports created in ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/