# AJ Phase 4: Idempotency Guarantees

## Overview

This document specifies the idempotency guarantees and limitations for AJ's persistent idempotency store.

## Core Guarantees

### 1. Atomic Duplicate Submission Handling

**Guarantee**: Submitting the same idempotency key twice produces the same result, without duplicate task creation or side effects.

**Mechanism**:
- `IdempotencyStore.claim(capability_id, key)` atomically claims a key
- If key already claimed: return existing outcome (idempotent replay)
- If key not claimed: create claim, create task, return new outcome

**Evidence from tests**:
- `test_export_import_dry_run_and_roundtrip` - Export then import dry-run shows 1 task, 0 conflicts on first import
- `test_export_import_dry_run_and_roundtrip` - Second import (without dry-run) raises `errors.Conflict`

**Behavior**:
```
First submission with key "K":
  → claim("jarvis.echo", "K") → miss → create task T1 → return outcome1

Second submission with key "K":
  → claim("jarvis.echo", "K") → hit (already claimed by T1) → return outcome1 (same task)
  
Third submission with key "K2":
  → claim("jarvis.echo", "K2") → miss → create task T2 → return outcome2 (different task)
```

**Limitation**: Idempotency only prevents duplicate submission of the *same key*. It does not prevent legitimate new tasks with different keys.

### 2. Concurrent Duplicate Submissions

**Guarantee**: Two concurrent submissions with the same key: one succeeds, the other gets Conflict error (or idempotent replay).

**Mechanism**:
- `claim()` uses file locking or atomic read-write to prevent race conditions
- Only one process can claim a key; others receive Conflict

**Evidence**:
- No existing test specifically for concurrent duplicate submissions (gap identified in feature matrix)
- Expected: `claim()` with file lock should return Conflict for second concurrent attempt

**Behavior**:
```
Process A: claim("cap", "key") → success → create task T1 → return outcome
Process B: claim("cap", "key") → Conflict (key already claimed) → return error
```

**Limitation**: If claim() lock fails (OS error), may raise exception instead of Conflict (must be handled gracefully).

### 3. Restart Persistence

**Guarantee**: Idempotency store survives process restart. Keys claimed before restart are still recognized after restart.

**Mechanism**:
- Persisted as JSON file: `data_dir/idempotency.json`
- Structure: `{capability_id: {key: {task_id, status, result, timestamp}}}`
- File read on each `assemble()` / `Aj()` construction
- Keys never expired or garbage-collected (manual cleanup only)

**Evidence**:
- `test_performance_sanity` - 120 tasks in <60s; implicit restart persistence (tasks persist via TaskStore)
- `test_attempt_model_survives_reload` - Explicitly tests attempt survival across config reload

**Behavior**:
```
Before restart:
  → claim("aj.echo", "key-X") → task T1 created → outcome returned

After restart (new assemble(config)):
  → claim("aj.echo", "key-X") → hit (key still in idempotency.json) → replay T1 outcome

Key is never lost across restarts unless:
  - idempotency.json file is deleted
  - JSON corruption (malformed) → reported in load_errors, may be skipped
```

### 4. Capability Scoping

**Guarantee**: Idempotency keys are scoped by capability_id. Same key for different capabilities produces different tasks.

**Mechanism**:
- Store structure: `{capability_id: {key: {...}}}`
- `claim(capability_id, key)` looks up by both capability_id and key
- Different capabilities can use same key without conflict

**Evidence**:
- Expected behavior per design; no test gap identified yet

**Behavior**:
```
claim("aj.echo", "mykey") → task T1 (for aj.echo capability)
claim("jarvis.web_search", "mykey") → task T2 (for jarvis.web_search capability, different task)
```

**Limitation**: If capability_id is empty string (""), may be treated as "auto" or generic (per `handle()` idempotency_key logic).

### 5. Conflicting Key Behavior

**Guarantee**: Same key claimed by different task IDs raises Conflict error.

**Mechanism**:
- `claim()` checks if key already claimed by different task_id
- If yes: return Conflict error
- If yes by same task_id: return idempotent replay (existing outcome)

**Evidence**:
- `test_export_import_dry_run_and_roundtrip` - Second import raises Conflict (different task_id)

**Behavior**:
```
First: claim("cap", "K") → task T1 created, claim[K] = T1
Second: claim("cap", "K") → T1 already exists → idempotent replay (ok)

Third: claim("cap", "K") with different intent → Conflict (key claimed by T1, not this new task)
```

### 6. Existing Task/Result Reuse

**Guarantee**: Idempotent replay reuses existing task record and its results.

**Mechanism**:
- On idempotent replay (key already claimed by task_id):
  - Load existing task record
  - Return TaskOutcome with task.status, task.summary, task.result (if any)
  - Do NOT create new task
  - Do NOT re-execute action
  - Do NOT append new audit events (except "idempotent_replay")

**Evidence**:
- `_idempotent_outcome()` in orchestrator (orchestrator.py line ~970):
  ```python
  def _idempotent_outcome(self, task_id: str) -> TaskOutcome:
      record = self.tasks.get(task_id)
      self.audit.record("idempotent_replay", task_id=task_id,
                        operation_id=record.operation_id, result=record.status,
                        authorization="idempotency_key")
      self._journal("IDEMPOTENT_REPLAY", record,
                    metadata={"status": record.status})
      return TaskOutcome(
          task_id=task_id, status=record.status,
          owner_agent=record.owner_agent,
          capability_id=record.capability_id, ok=record.status == taskmod.COMPLETED,
          summary=f"idempotent replay of existing task ({record.status})",
          route_rule="idempotency")
  ```

**Behavior**:
```
Idempotent replay returns:
  - ok: True if task.status == COMPLETED, False otherwise
  - summary: "idempotent replay of existing task (COMPLETED/FAILED)"
  - result: task.result (if COMPLETED) or None
  - No new action execution
  - "idempotent_replay" audit event recorded
  - No new journal events beyond IDEMPOTENT_REPLAY
```

### 7. Behavior After Interrupted Execution

**Guarantee**: After process interruption (crash, restart), idempotency key still prevents duplicate submission.

**Mechanism**:
- Key persists in idempotency.json across restarts
- On next `handle()` with same key: replay existing outcome
- Task state may be COMPLETED, FAILED, or RECOVERY_REQUIRED (depends on crash point)
- If COMPLETED: replay returns COMPLETED outcome (no re-execution)
- If FAILED: replay returns FAILED outcome (no retry)
- If RECOVERY_REQUIRED: replay returns RECOVERY_REQUIRED outcome (needs manual decision)

**Evidence**:
- `test_completed_task_recovery_noop` - COMPLETED task recovery is no-op
- `test_repeated_recovery_is_idempotent_failed` - Recovery idempotency on FAILED task

**Behavior**:
```
After crash, restart, handle("goal", capability_id, idempotency_key="K"):
  → claim("cap", "K") → key exists → _idempotent_outcome(task_id)
  → Return existing task outcome (status may be COMPLETED or FAILED)
  → No new task created
  → No new action executed
```

### 8. Behavior After Failed Execution

**Guarantee**: After failed execution, idempotency key still prevents duplicate submission, and the failure is preserved.

**Mechanism**:
- Key persists with task status FAILED
- On replay: return FAILED outcome, ok=False
- Do NOT attempt re-execution (that's what `retry()` is for)
- Do NOT change task state

**Evidence**:
- `test_unsafe_replay_is_refused` - FAILED task with UNDERSTANDING status, RecoveryManager.scan() finds recovery_required
- Note: This tests recovery, not idempotency directly; idempotency behavior on FAILED task is complementary

**Behavior**:
```
After failed execution with idempotency key "K":
  → claim("cap", "K") → key exists, task status FAILED → 
  → _idempotent_outcome(task_id) → ok=False, summary="idempotent replay of existing task (FAILED)"
  → No re-execution
  → No retry triggered (use aj.retry() for that)
```

### 9. Existing Guarantees That Idempotency Does NOT Accidentally Prevent

**Guarantee**: Idempotency prevents duplicate submission but does not prevent:
- Legitimate new tasks with new keys
- Retry of failed tasks (use `aj.retry()`, not duplicate handle() with same key)
- Escalation of exhausted retry budget
- Human decision-required scenarios

**Evidence**:
- `test_retry_is_refused_for_unmarked_capability` - Retry refused for capability not marked retry-safe
- `test_retry_of_terminal_task_is_rejected` - Retry of terminal task rejected
- `test_cancel_while_executing_requests_without_claiming_stop` - Cancel while executing requests without claiming stop

**Behavior**:
```
Idempotency does NOT prevent:
  ✅ handle("new goal", capability_id, idempotency_key="NEW") → new task (different key)
  ✅ aj.retry(task_id) → retry (explicit retry operation, not idempotency)
  ✅ aj.cancel_task(task_id) → cancel (explicit cancel operation)
  ✅ handle("different goal", capability_id) → new task (different goal)
  
Idempotency DOES prevent:
  ❌ handle("goal", capability_id, idempotency_key="K") twice → second is idempotent replay
  ❌ Concurrent duplicate handle() with same key → Conflict or idempotent replay
```

## Limitations

### 1. No Automatic Expiration

- Idempotency keys never expire automatically
- Keys persist indefinitely in idempotency.json
- Manual cleanup required (delete file, or implement GC)
- **Workaround**: Implement external key management or expire keys via administrative operation

### 2. No Built-in Retry Prevention

- Idempotency does NOT prevent `aj.retry()` from being called
- `retry()` has its own logic (attempt budget, retry_safe capability check)
- Calling `handle()` with same idempotency key after failure: replay failure, not retry

### 3. No Distributed Scope

- Idempotency key scope is local to this AJ instance/data directory
- Different AJ instances (different data dirs) have independent idempotency stores
- Same key in different instances may create different tasks (expected per design)

### 4. No Size Limit

- idempotency.json grows unbounded as more keys are claimed
- No automatic compaction or rotation
- For long-running systems, periodic cleanup recommended

### 5. No Encryption at Rest

- Idempotency store is plain JSON (no encryption)
- Credentials or sensitive data should not be stored in idempotency keys
- Backup of idempotency.json may expose key patterns

## Test Coverage Gap Analysis

| Guarantee | Tested | Gap |
|-----------|--------|-----|
| Atomic duplicate submission | ⚠️ Inferred from export/import flow | No direct concurrent duplicate test |
| Concurrent duplicate submissions | ❌ None | Add test for concurrent claim() calls |
| Restart persistence | ✅ `test_attempt_model_survives_reload` | Need explicit idempotency key test |
| Capability scoping | ⚠️ Design assumption | No test for same key different capability |
| Conflicting key behavior | ✅ `test_export_import_dry_run_and_roundtrip` | Verify Conflict error message |
| Existing task/result reuse | ⚠️ Inferred from `_idempotent_outcome` | No test for idempotent replay flow |
| Behavior after interrupted execution | ⚠️ Conceptual | No crash + idempotency key test |
| Behavior after failed execution | ⚠️ Inferred | No test for idempotent replay on FAILED task |
| Idempotency does not prevent legitimate new tasks | ✅ Design verified | No test for new key creation |

## Required Test Additions

1. **Concurrent duplicate submissions**: Two processes call `claim()` same key, verify one succeeds one gets Conflict
2. **Idempotent replay after crash**: Create task, crash, restart, handle with same key, verify replay
3. **Idempotent replay on FAILED task**: Create FAILED task via handle(), replay with same key, verify FAILED outcome
4. **New key creates new task**: handle() with new idempotency key, verify new task created
5. **Idempotency key scope**: Same key different capability, verify different tasks created

## Idempotency Integration Points

### In `aj/orchestrator.py`:
- `_idempotent_outcome(task_id)` - Returns existing outcome for idempotent replay
- `_idempotency` store: `IdempotencyStore(data_dir / "idempotency.json")`
- `handle()` method: checks idempotency_key at start, calls `_idempotent_outcome()` if claimed

### In `aj/idempotency.py`:
- `IdempotencyStore` class with `claim(capability_id, key)` and `lookup(capability_id, key)`
- JSON file persistence at `data_dir/idempotency.json`
- File locking for concurrent access

### In `aj/__main__.py`:
- CLI support for idempotency-related operations (planned)
- `--idempotency-key` flag (not yet implemented)

### In `aj/__init__.py` / `aj/aj.py`:
- Aj class construction includes idempotency store if data_dir provided
- Aj.handle() idempotency check at entry point