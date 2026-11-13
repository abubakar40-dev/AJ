# AJ Phase 5: Recommendations

## Overview

This document recommends the next phase of AJ development following Phase 4 completion. Phase 4 established a dependable local execution engine with crash safety, lease separation, and reliability hardening. Phase 5 should address the HIGH-priority blocked items and add meaningful enhancements.

## Primary Recommendations (HIGH Priority)

### 1. Distributed Crash Safety Testing

**Why**: Phase 4 crash safety tests only cover single-process, single-machine contexts. The Phase 3.1 regression gate explicitly notes this blocker: "True distributed race tests across separate machines (Phase 3.1 regression gate not run with distributed processes)".

**What to do**:
- Spawn AJ instances on separate processes (or Docker containers if available)
- Test lease acquisition across process boundaries
- Verify recovery consistency when different workers claim/execute tasks
- Test subprocess termination at all 12 points across separate machines
- Verify state consistency after distributed crashes

**Deliverables**:
- Distributed test framework (or confirm limitation and document)
- Updated crash recovery matrix with distributed results
- Documentation of distributed race findings

**Dependencies**: May require Docker or separate machine access; if unavailable, document as known limitation and note for future when infrastructure available.

### 2. Circular Dependency Detection

**Why**: Tasks with cyclic `depends_on` will be permanently BLOCKED with no automatic detection. This is a functional gap that prevents task execution in cyclic dependency scenarios.

**What to do**:
- Implement `has_circular_dependency(task_id)` in TaskStore or Orchestrator
- Block task creation (or warn) when circular dependency detected
- Add test verifying cycle detection works (create task with cycle, verify detection)
- Add test verifying normal task creation still works (no false positives)

**Deliverables**:
- `has_circular_dependency()` implementation
- Test: `test_circular_dependency_detection` - create task with cycle, verify detected
- Test: `test_no_false_positives` - create task without cycle, verify not flagged
- Update TRANSITIONS or authorization to check cycles

### 3. Encrypted Storage at Rest

**Why**: Production deployments with secrets in task data need encryption at rest. Currently all data (including task goals that may contain API keys) stored as plain JSON/SQLite.

**What to do**:
- Add optional AES-256 encryption at rest
- Key management via environment variables (OPENAI_API_KEY path, or dedicated key env vars)
- Optional encryption flag in config (e.g., `core.encryption_at_rest = True`)
- Encryption/decryption Transparent to API (handle(), retry(), etc. unchanged)
- Backup with encryption; decryption on restore

**Deliverables**:
- Encryption module (optional, opt-in)
- Config flag for encryption
- Test: encrypt task, verify handle() works, verify backup/restore with decryption
- Test: without encryption, behavior identical to Phase 4 (backward compatible)

### 4. Secrets Redaction Verification

**Why**: Design principle states "Secrets are redacted" but no test verifies redaction actually occurs in output.

**What to do**:
- Add redaction at recording time (in `_remember()`, `_journal()`, `_receipt()`)
- Add tests verifying sensitive patterns (OPENAI_API_KEY, passwords, tokens) redacted to "***REDACTED***"
- Verify redaction in journal events, audit records, receipt outputs
- Ensure redacted records still comparable (hash on non-sensitive fields)

**Deliverables**:
- Redaction utility/functions
- 3-4 new tests for redaction verification
- Update SECURITY_VALIDATION.md with redaction test results

## Secondary Recommendations (MEDIUM Priority)

### 5. Persistent Retry Backoff

**Why**: No `next_retry_at` field in TaskRecord; backoff not persisted across restarts. After restart, retries happen immediately instead of at scheduled backoff.

**What to do**:
- Add `next_retry_at: Optional[float]` to TaskRecord
- On `_start_attempt()`: set `next_retry_at = time.time() + backoff_seconds`
- On retry eligibility check: `if task.next_retry_at and time.time() < task.next_retry_at: not yet eligible`
- Backoff formula: `min(base * 2^(attempt-1), max_backoff)` (e.g., base=1s, max=60s)

**Deliverables**:
- `next_retry_at` field in TaskRecord (or separate scheduling store)
- Backoff calculation in orchestrator retry path
- 2-3 tests for backoff persistence across restart
- Update RETRY_AND_DEAD_LETTER_POLICY.md

### 6. Dead-Letter Recovery Policy

**Why**: No automated recovery from DEAD_LETTER status (operator decision required by design, which is correct, but should have formal policy).

**What to do**:
- Implement `dead_letter_recovery(policy: str, approval: str = "")` method
- Policies: "escalate" (mark for human review), "cancel" (cancel task), "replay" (if spec.replay_safe)
- Formalize the operator decision flow (what UI/CLI shows when task is DEAD_LETTER)
- Add test for each policy path

**Deliverables**:
- `dead_letter_recovery()` method in orchestrator
- 3 tests (escalate, cancel, replay policies)
- Update dead-letter documentation in orchestrator and this file

### 7. Comprehensive Referential Dependency Check

**Why**: `unsatisfied_dependencies()` exists but full dependency graph analysis is missing. Orphan records, missing dependencies at scale may go undetected.

**What to do**:
- Implement `compute_referential_deps()` returning dict of all dependency issues
- Tasks with missing depends_on entries
- Receipts with attempt_ids not in any task's attempts
- Journal events with task_ids not in task store
- Orphan leases (lease for non-existent task)

**Deliverables**:
- `compute_referential_deps()` returning structured dict
- Update RETENTION_ASSESSMENT.md to use this function
- 1-2 tests for dependency issue detection
- Integrate into retention assessment

### 8. Config Schema Version Tracking

**Why**: No `core.schema_version` in config for migration detection. Makes it hard to know what version migration is needed.

**What to do**:
- Add `schema_version: int = 1` to config
- Use in migration detection: `if config.schema_version > SUPPORTED_MAX_VERSION: needs migration`
- Report in health checks: `storage_integrity` includes schema version
- Backward compatible (default 1, old configs still work)

**Deliverables**:
- `schema_version` in config
- Health check update (storage_integrity includes version info)
- Test: config with schema_version, verify health check reports it
- Backward compatibility (old configs default to 1)

### 9. Backup Compression

**Why**: Backup is uncompressed JSON; for long-running systems, storage growth may be significant (journal + tasks + receipts + idempotency + audit + memory).

**What to do**:
- Add optional gzip compression to backup
- Config flag: `backup.compress = True` (or always compress, given small overhead)
- Decompress on restore (transparent)
- Test: compress backup, verify restore identical to uncompressed

**Deliverables**:
- Compressed backup format (gzip)
- Transparent compress/decompress in transfer module
- 1 test for compress/restore roundtrip
- Update BACKUP_RESTORE_VALIDATION.md

### 10. Idempotent Replay Flow Tests

**Why**: Export/import flow tests conflict detection, but explicit idempotent replay flow (handle() with same idempotency key, verify replay, no new task) not tested.

**What to do**:
- Create task with idempotency key via handle()
- Second handle() with same key: verify replay (no new task, same outcome)
- Verify `ok`, `summary`, `route_rule` all indicate idempotent replay
- Test both COMPLETED and FAILED task replay

**Deliverables**:
- 2-3 tests for idempotent replay flow
- Update IDEMPOTENCY_GUARANTEES.md with test results
- Verify existing export/import tests still pass

## Tertiary Recommendations (LOW Priority)

### 11. CLI Exit Code Standardization

**Why**: Exit codes work but may vary with capability registry configuration. Standardizing would improve UX.

**What to do**:
- Document all CLI exit codes in one table (already mostly done in tests)
- Add `--help` with exit code summary
- Standardize codes where they vary

**Deliverables**:
- Updated CLI help with exit codes
- 1-2 tests standardizing exit codes
- Low priority (functional as-is)

### 12. Fuzz Testing for Edge Cases

**Why**: Test coverage for edge cases in lease acquisition, capability routing, state transitions limited.

**What to do**:
- Add fuzz/edge-case tests (not full fuzz framework, but targeted tests)
- Lease edge cases (same pid/host, expired/released sequences)
- Capability edge cases (unknown, multiple, conflicting)
- State transition edge cases (invalid transitions, force transitions)

**Deliverables**:
- 5-10 edge case tests
- Update test_phase3.py or add to test_crash_safety.py
- Low priority (existing tests cover main paths)

### 13. Performance Benchmark Expansion

**Why**: Current benchmarks use aj.echo only (internal action). No benchmarks for agent-executed capabilities (JARVIS/HELIX).

**What to do**:
- Add benchmarks for various capability types (if JARVIS/HELIX available)
- Throughput measurement per capability type
- Record under different loads (concurrent workers)

**Deliverables**:
- 3-5 performance benchmarks (if agent capabilities available)
- Update PERFORMANCE_REPORT.md
- Low priority (may be out of scope if no agent capabilities configured)

### 14. Access Tracking for Records

**Why**: No `last_accessed_at` field on records; cannot identify least-recently-used for retention policy.

**What to do**:
- Add `last_accessed_at: Optional[float]` to TaskRecord (and other records as needed)
- Update on each task access (handle(), get(), etc.)
- Enable age-based archival policy (identify candidates older than N days)

**Deliverables**:
- `last_accessed_at` field in TaskRecord
- Access update in TaskStore.get(), get()
- Age-based archive candidate identification
- Low priority (nice to have, not critical)

### 15. Agent Configuration Security Review

**Why**: JARVIS/HELIX security boundaries reviewed separately (out of AJ scope, but worth noting).

**What to do**:
- None (out of AJ scope)
- Note in documentation that agent security is separate concern
- No code changes required

**Deliverables**:
- Documentation note (no code changes)
- Lowest priority (out of scope)

## Phase 5 Implementation Plan

### Phase 5 Timeline (Estimated)

**Sprint 1 (2 weeks)**:
- Circular dependency detection (HIGH) - implementation + tests
- Config schema version tracking (MEDIUM) - config + health check updates
- Idempotent replay flow tests (LOW) - 2-3 tests

**Sprint 2 (2 weeks)**:
- Distributed crash safety testing (HIGH) - framework design (or document limitation)
- Persistent retry backoff (MEDIUM) - `next_retry_at` + tests
- Backup compression (MEDIUM) - compress/decompress + test

**Sprint 3 (2 weeks)**:
- Dead-letter recovery policy (MEDIUM) - method + 3 policy tests
- Referential dependency check (MEDIUM) - implementation + integration into retention
- Secrets redaction verification (MEDIUM) - redaction + 3-4 tests

**Sprint 4 (1 week)**:
- Fuzz testing edge cases (LOW) - 5-10 targeted tests
- CLI exit code standardization (LOW) - documentation + minor fixes
- Performance benchmark expansion (LOW) - if agent capabilities available

**Sprint 5 (1 week)**:
- Access tracking (LOW) - `last_accessed_at` + minimal implementation
- Documentation review and updates (all reports)
- Regression gate verification (all tests still pass)

### Phase 5 Success Criteria

All must pass before Phase 5 declared complete:

1. **Circular dependency detection** implemented and tested (no false positives, no false negatives)
2. **Config schema version** tracked in health checks
3. **At least 3 of 4 HIGH priority items** substantially implemented (distributed testing may be documented limitation)
4. **All 126 existing tests still pass** (regression gate)
5. **23/23 health checks still pass**
6. **No user data mutations** (verified via changed-files inspection)
7. **No external integrations activated** (verified)

### Phase 5 Non-Goals (Explicitly Out of Scope)

- No JARVIS/HELIX merge or relocation (kept separate as in Phase 4)
- No git init/commit/reset/clean (per Phase 4 constraints)
- No rm -rf on user data (per Phase 4 constraints)
- No external service activations without user explicit configuration (per Phase 4 constraints)
- No Docker/machine orchestration unless infrastructure available (document limitation if unavailable)

### Deliverables Summary (Phase 5)

**Engineering audit directory** (ENHANCED with Phase 5 reports):
- All Phase 4 reports (17 files) still present
- Plus 5-10 new reports for HIGH/MEDIUM priority items
- Updated KNOWN_LIMITATIONS.md with Phase 5 progress
- Updated NEXT_PHASE_RECOMMENDATION.md with Phase 5 recommendations

**Test additions** (estimated 15-25 new tests):
- Circular dependency detection: 2 tests
- Idempotent replay flow: 2-3 tests
- Distributed crash safety: 1 framework test (or documentation of limitation)
- Persistent backoff: 2-3 tests
- Dead-letter recovery: 3 tests
- Referential dependency check: 1-2 tests
- Secrets redaction: 3-4 tests
- Config schema version: 1 test
- Backup compress/restore: 1 test
- Edge case fuzz: 5-10 tests
- **Total: ~20-35 new tests**

**Source module enhancements** (not rewrites):
- TaskRecord: `next_retry_at` field (or `schema_version` enhancements)
- Orchestrator: `has_circular_dependency()`, `dead_letter_recovery()`, `compute_referential_deps()`
- Config: `schema_version` field
- Transfer: compress/decompress for backup
- Lease: enhanced expiry/hold logic (if needed for new features)

**Regression gate**: All 126+new tests must pass, 23/23 health checks, no user data mutations, no external integrations.

### Quick Start for Phase 5

If beginning Phase 5 immediately, start with:

1. **Circular dependency detection** (highest impact, lowest implementation effort):
   - Add `has_circular_dependency()` to TaskStore ( ~50 lines)
   - Add 2 tests (cycle detection + no false positives)
   - Verify all 126 existing tests still pass

2. **Config schema version** (medium impact, trivial implementation):
   - Add `schema_version: int = 1` to config
   - Update health check storage_integrity to report version
   - Verify backward compatibility (old configs default to 1)

3. **Idempotent replay flow tests** (medium impact, tests only):
   - Add 2-3 tests to test_phase3.py or test_crash_safety.py
   - No source module changes required
   - Verify existing tests still pass

Then proceed to distributed crash safety (may document as limitation if infrastructure unavailable) and the other MEDIUM items.

## Final Remarks

Phase 4 successfully completed the objective: "Complete AJ's reliable local execution engine." The execution engine is now dependable with:
- Crash safety at 12 controlled termination points
- Lease separation (operation vs execution ownership)
- Full idempotency, dependency, retry, and dead-letter policies
- Storage versioning, backup/restore, and retention assessment
- Security guarantees (authorization, leases, secrets, CLI integrity)
- 151/151 regression gate verified (Phase 3.1 baseline)
- 23/23 health checks passing
- 126/126 total tests passing

**Phase 5 should focus on the 4 HIGH-priority blocked items first**, particularly circular dependency detection (functional gap) and distributed crash safety testing (regression gate requirement). The MEDIUM and LOW items can be progressively added through subsequent sprints.

If the team decides to address the HIGH-priority distributed testing limitation (requires Docker/multi-machine infrastructure), this should be noted in the KNOWN_LIMITATIONS.md and tracked separately. If infrastructure is unavailable, the limitation should be documented and the Phase 5 scope adjusted accordingly.

**Phase 5 recommended start**: Implement circular dependency detection first (highest impact, ~50 lines of code, 2 tests). This immediately functional gap and provides immediate value (tasks with cyclic dependencies no longer silently block forever).