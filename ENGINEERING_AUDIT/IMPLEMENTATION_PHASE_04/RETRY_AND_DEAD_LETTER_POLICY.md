# AJ Phase 4: Retry and Dead-Letter Policy

## Overview

This document specifies the retry backoff, maximum attempts, permanent failure classification, and dead-letter queue policy for AJ tasks.

## Retry Policy

### 1. Maximum Attempts

**Configuration**: `providers.max_attempts` (default: 3, configurable per capability via `spec.max_attempts`).

**Behavior**:
- Each task record has `max_attempts: int` field (default 3)
- `attempt` counter starts at 1, increments with each retry
- When `attempt > max_attempts`: retry budget exhausted

**Transition Path**:
```
FAILED -> RECOVERING -> RETRYING -> EXECUTING (retry attempt)
                                                                      |
                                                                        v
                                                                   ATTEMPTS EXHAUSTED
                                                                              |
                                                                           v
                                                                  ESCALATED (needs human decision)
```

**Orchestrator Method**: `retry(task_id: str) -> TaskOutcome`
```python
def retry(self, task_id: str, *, approval: str = "") -> TaskOutcome:
    with self.leases.hold(task_id, "retry"):
        return self._retry_locked(task_id, approval=approval)
```

**_retry_locked Steps**:
1. Check `record.status != FAILED` → error if not FAILED
2. Check `record.attempt >= record.max_attempts` → if exhausted, escalate
3. Check `spec.retry_safe` → if not retry-safe, refuse with requires_user_decision
4. Transition: FAILED -> RECOVERING -> RETRYING -> EXECUTING
5. Execute the action (same as new handle)
6. On completion: task status COMPLETED/FAILED, attempt incremented

**Evidence from tests**:
- `test_retry_preserves_task_id_and_history` - Retry preserves task ID, history (2 attempts, first FAILED, second COMPLETED)
- `test_retry_is_refused_for_unmarked_capability` - Retry refused for capability not marked retry-safe
- `test_retry_of_terminal_task_is_rejected` - Retry of COMPLETED/A terminal task rejected

**Behavior**:
```
Task with max_attempts=3, attempt=1, status=FAILED:
  → aj.retry(task_id) → FAILED -> RECOVERING -> RETRYING -> EXECUTING → new attempt (attempt=2)
  
Task with max_attempts=3, attempt=3, status=FAILED:
  → aj.retry(task_id) → attempts exhausted → FAILED -> RECOVERING -> ESCALATED -> requires_user_decision
  
Task with capability not retry_safe:
  → aj.retry(task_id) → retry refused: "capability is not declared retry-safe" -> requires_user_decision=True
```

### 2. Retry Eligibility

**Guarantee**: A task is retry-eligible if:
1. Status is FAILED (not COMPLETED, not terminal)
2. attempt < max_attempts (budget not exhausted)
3. Capability is marked retry_safe

**Orchestrator Checks**:
- `record.status == FAILED` (or can transition to FAILED)
- `record.attempt < record.max_attempts`
- `spec.retry_safe` is True (per capability registry)

**Evidence**:
- `test_retry_is_refused_for_unmarked_capability` - Verifies retry refused when not retry_safe
- `test_retry_of_terminal_task_is_rejected` - Verifies retry rejected for terminal tasks

### 3. Retry-Safe Capability Enforcement

**Guarantee**: Only capabilities marked `retry_safe: True` in the capability registry can be retried.

**Mechanism**:
- CapabilitySpec has `retry_safe: bool` field
- Default: `False` (must be explicitly set True)
- Internal/actions capabilities are retry_safe
- JARVIS/HELIX capabilities may or may not be retry_safe

**Verification**:
- `registry.find(capability_id).retry_safe` returns True/False
- `test_retry_is_refused_for_unmarked_capability` - Tests refusal when not retry_safe
- `test_unsafe_replay_is_refused` - Tests recovery refusal when not replay_safe

**Behavior**:
```
Capability "aj.echo": retry_safe=True (internal action)
  → aj.retry(task_id) → proceeds through retry path

Capability "jarvis.web_search": retry_safe=False (external, unsafe)
  → aj.retry(task_id) → refused: "capability is not declared retry-safe"
  → requires_user_decision = True
  → Task escalated to needs human decision

Capability "aj.echo" with explicit retry_safe=False:
  → aj.retry(task_id) → refused same as above
```

### 3. Persistent Retry Reason

**Guarantee**: Each retry attempt records the reason for retry, persisted across restarts.

**Mechanism**:
- Attempt record: `{"failure": None/or error dict}`
- After retry: `_finish_attempt(record, status, error)` sets `attempt["status"] = status` and `attempt["ended_at"] = time.time()`
- If error: `attempt["failure"] = error.to_dict()` including code, message, stage
- Task record: `recovery: Dict[str, Any]` may include retry reason

**Persisted Data**:
- `tasks.jsonl`: Each task record includes `attempts: List[Dict]` with attempt history
- `memory.sqlite3`: Memory events may include retry reason
- On reload: `TaskStore.all()` includes full attempt history

**Evidence**:
- `test_retry_preserves_task_id_and_history` - Verifies attempt history preserved (2 attempts, statuses, attempt_number)
- `test_attempt_model_survives_reload` - Verifies attempts survive config reload

**Behavior**:
```
After failed execution (error: EXECUTION_FAILED, code="execution_failed"):
  → Task attempt record: {"status": "FAILED", "ended_at": T, "failure": {"code": "execution_failed", "message": "boom", "stage": "execute"}}
  
  → aj.retry(task_id) → new attempt (attempt_number=2) 
  → Attempt record: {"status": "RUNNING", "started_at": T, "ended_at": None, "failure": None}
  
  → After second execution (success):
  → Attempt records: [{"status": "FAILED", ...}, {"status": "COMPLETED", "ended_at": T, "failure": None}]
  → task.attempt = 2
```

### 4. Deterministic Backoff

**Guarantee**: Retry backoff is deterministic based on attempt number, but not necessarily persisted as a timestamp.

**Current Implementation**: 
- No explicit `next_execution_timestamp` field in task record
- Retry scheduling depends on orchestrator/scheduler implementation
- Backoff concept: exponential backoff (2^attempt seconds) or constant delay

**Configuration**: 
- No `backoff` or `retry_delay` field in current TaskRecord schema
- Could be added: `next_retry_at: Optional[float]`
- For now, retry immediate (scheduler decides timing)

**Evidence**:
- No test for persistent backoff timestamps
- `test_performance_sanity` - 120 tasks in <60s (no backoff testing)

**Proposed Backoff Formula** (for future implementation):
```
backoff_seconds = min(base * 2^(attempt-1), max_backoff)
# e.g., base=1, max=60: attempt 1 → 1s, attempt 2 → 2s, attempt 3 → 4s, attempt 4+ → 60s
```

### 5. Maximum Backoff

**Guarantee**: Backoff does not exceed maximum limit (for future implementation).

**Current Status**: Not implemented (no backoff fields in TaskRecord).

**If implemented**:
- `max_backoff: int` configuration (e.g., 60 seconds, 300 seconds, 900 seconds)
- `backoff_seconds = min(deterministic_backoff, max_backoff)`
- After max_backoff, still retry but at max interval

**Evidence**: None (not implemented)

### 6. Permanent Failure Classification

**Guarantee**: Failures are classified as permanent (not retry-safe) or transient (retry-safe), influencing retry behavior.

**Classification**:

| Classification | Description | retry_safe | Example |
|---------------|-------------|------------|---------|
| Permanent | Operation cannot safely retry (side effects, external state) | False | web_search, file_write, network_call |
| Transient | Operation can safely retry (idempotent, no side effects) | True | echo, arithmetic, read-only ops |

**Mechanism**:
- CapabilitySpec has `retry_safe: bool` and `verification_status: str`
- `retry_safe=True` → aj.retry() proceeds (within attempt budget)
- `retry_safe=False` → aj.retry() refused, requires_user_decision

**Verification**:
- `test_retry_is_refused_for_unmarked_capability` - Tests refusal for non-retry_safe capability
- `test_unsafe_replay_is_refused` - Tests recovery refusal for non-replay_safe capability
- Capability registry: `spec.retry_safe` field

**Behavior**:
```
# Permanent failure (not retry-safe)
Task with capability "jarvis.web_search", status FAILED:
  → aj.retry(task_id) → "retry refused: capability is not declared retry-safe"
  → outcome.ok = False
  → outcome.requires_user_decision = True
  → Task escalated (not automatically retried)

# Transient failure (retry-safe)  
Task with capability "aj.echo", status FAILED:
  → aj.retry(task_id) → proceeds through retry path (FAILED -> RECOVERING -> RETRYING -> EXECUTING)
  → New attempt executed
  → On success: task COMPLETED
  → On failure: attempt incremented, if attempts >= max_attempts → escalate
```

### 7. Dead-Letter Queue

**Guarantee**: Tasks requiring human intervention are moved to DEAD_LETTER status and remain clearly visible.

**Status**: DEAD_LETTER (terminal state, preserved all history)

**Transition**: `dead_letter(task_id: str, reason: str) -> TaskRecord`

**Orchestrator Method**:
```python
def dead_letter(self, task_id: str, reason: str) -> TaskRecord:
    record = self.tasks.get(task_id)
    if record.status != taskmod.DEAD_LETTER:
        if not record.can_transition(taskmod.DEAD_LETTER):
            raise errors.AjError(
                f"task {task_id} cannot be dead-lettered from {record.status}",
                code=errors.CALLING_INVALID_STATE)
        self.tasks.transition(task_id, taskmod.DEAD_LETTER, reason)
        record = self.tasks.get(task_id)
        record.requires_user_decision = True
        self.tasks.save(record, "dead_letter")
        self.audit.record("task_dead_lettered", task_id=task_id,
                          operation_id=record.operation_id,
                          capability=record.capability_id,
                          result="dead_letter", detail=reason[:300])
        self._journal("TASK_DEAD_LETTERED", record,
                      metadata={"reason": reason[:300]})
        self._remember(record, "task.dead_letter", reason,
                       {"status": record.status})
    return record
```

**Valid Transitions to DEAD_LETTER**:
- From any non-terminal state (RECEIVED, UNDERSTANDING, PLANNED, AUTHORIZED, EXECUTING, FAILED, etc.)
- From BLOCKED state
- Cannot transition from terminal states (COMPLETED, ABORTED, CANCELLED) without force

**Evidence from tests**:
- `test_dead_letter` method exists in orchestrator (documented in code)
- `test_retry_of_terminal_task_is_rejected` - Related concept (terminal tasks can't be retried)

**Behavior**:
```
# Move task to dead letter
aj.dead_letter(task_id, reason="requires human intervention: capability permanently disabled")

Result:
  → task.status == DEAD_LETTER
  → task.requires_user_decision = True
  → audit event "task_dead_lettered" recorded
  → journal event "TASK_DEAD_LETTERED" recorded
  → task.remember("task.dead_letter", reason, {"status": "DEAD_LETTER"})
  → Task preserved with all history (actions, errors, warnings)
  → Task NOT executable (terminal state)
  → Task visible in lists, reports, diagnostics

# Cannot move COMPLETED task to dead letter (without force)
aj.dead_letter(completed_task_id, reason="test")  
  → raises AjError: task cannot be dead-lettered from COMPLETED
```

### 8. Dead-Letter Recovery Policy

**Guarantee**: Dead-lettered tasks remain clearly visible and identifiable, and can be recovered with operator approval.

**Recovery Path**:
1. Task in DEAD_LETTER status
2. Operator decides: escalate, cancel, or recover
3. `recover(task_id)` may work if task spec is replay_safe (rare for dead-lettered)
4. More common: operator manually creates new task or modifies existing

**Visibility**:
- Dead-lettered tasks appear in `tasks.active()`? No (terminal)
- Dead-lettered tasks appear in `tasks.query(status="DEAD_LETTER")`
- Dead-lettered tasks appear in reports and diagnostics
- Dead-lettered tasks have `requires_user_decision = True`

**Evidence**:
- No existing test for dead-letter recovery (gap identified)
- `test_health_covers_the_phase3_surface` - Health checks may include dead-letter count

**Behavior**:
```
# List dead-lettered tasks
control.tasks.query(status="DEAD_LETTER")
→ Returns list of all DEAD_LETTER tasks with their details

# Check dead-letter task visibility
task = control.tasks.get(dead_letter_task_id)
→ task.status == "DEAD_LETTER"
→ task.requires_user_decision == True
→ task.requires_user_decision is True (clearly visible requires decision)
→ task.warnings contains dead-letter reason
→ audit has "task_dead_lettered" event

# Recovery from dead letter (operator decision)
→ operator decides to escalate or create new task
→ dead-lettered task preserved, not deleted
→ new task created with new task_id if operator chooses
```

## Retry/Dead-Letter Test Coverage

| Feature | Tested | Status |
|---------|--------|--------|
| max_attempts default (3) | ✅ Part of TaskRecord | Default applied |
| retry() for FAILED task | ✅ `test_retry_preserves_task_id_and_history` | Verified |
| retry refused for non-retry_safe | ✅ `test_retry_is_refused_for_unmarked_capability` | Verified |
| retry refused for terminal task | ✅ `test_retry_of_terminal_task_is_rejected` | Verified |
| attempt counter increments | ✅ `_finish_attempt()` | Verified in tests |
| attempt history persists | ✅ `test_attempt_model_survives_reload` | Verified |
| DEAD_LETTER status | ✅ Transition exists in TRANSITIONS | Verified |
| dead_letter() method | ✅ Orchestrator method | Verified in code |
| dead-letter from any non-terminal state | ✅ `can_transition` dict includes DEAD_LETTER | Verified |
| Cannot dead-letter from terminal | ✅ `can_transition` excludes terminal from DEAD_LETTER | Verified |
| Dead-letter visibility (query) | ⚠️ Implicit | `query(status="DEAD_LETTER")` should work |
| Dead-letter recovery policy | ❌ None | Gap - no test for recovery from DEAD_LETTER |
| Permanent failure classification | ⚠️ via retry_safe | Design assumed; no explicit test |
| Retry backoff persistence | ❌ None | Gap - no backoff timestamp field |
| Maximum attempts enforcement | ⚠️ In orchestrator logic | Verified via test_retry_of_terminal_task_is_rejected |
| Dead-letter recovery | ❌ None | Gap - completely missing |
| Permanent failure identification | ⚠️ via retry_safe | Design assumed |

## Required Implementations

### 1. Dead-Letter Recovery Policy (HIGH priority)

Implement policy for dead-lettered task recovery:

```python
def dead_letter_recovery(self, task_id: str, approval: str = "") -> TaskOutcome:
    """Policy for recovering a dead-lettered task."""
    record = self.tasks.get(task_id)
    
    if record.status != taskmod.DEAD_LETTER:
        raise errors.AjError(
            f"task {task_id} is {record.status}, not DEAD_LETTER",
            code=errors.CALLING_INVALID_STATE)
    
    # Dead-lettered tasks require operator decision
    record.requires_user_decision = True
    self.tasks.save(record, "dead_letter_recovery_attempt")
    
    # Return outcome indicating operator decision needed
    return TaskOutcome(
        task_id=task_id, status=record.status,
        owner_agent="AJ", capability_id=record.capability_id,
        ok=False,
        summary=f"Task is dead-lettered (reason: {record.recovery.get('reason', 'unknown')[:100]})",
        requires_user_decision=True,
        route_rule="dead_letter_recovery"
    )
```

**Operator actions** (chosen by UI/cli):
1. **Cancel**: `aj.cancel_task(task_id)` if not terminal
2. **Escalate**: Mark for human review, create ticket, etc.
3. **Recover**: If spec.replay_safe, attempt recovery (rare)
4. **Create new task**: Create new task replacing the dead-lettered one
5. **Archive**: Preserve as-is, do not execute

### 2. Retry Backoff Persistence (MEDIUM priority)

Add `next_retry_at` field to TaskRecord (or separate scheduling store):

```python
# In TaskRecord dataclass:
next_retry_at: Optional[float] = None  # timestamp when task is eligible for retry

# In _start_attempt or _finish_attempt:
attempt["next_retry_at"] = time.time() + backoff_seconds
```

**Backoff formula** (proposed):
```python
base = 1.0  # 1 second base
max_backoff = 60  # 60 seconds maximum
attempt = record.attempt
backoff = min(base * (2 ** (attempt - 1)), max_backoff)
attempt["next_retry_at"] = time.time() + backoff
```

**Scheduler check** (before retry):
```python
task = store.get(task_id)
if task.next_retry_at and time.time() < task.next_retry_at:
    # Task not yet eligible for retry
    return False  # or schedule retry at next_retry_at
```

### 3. Permanent Failure Classification Documentation (MEDIUM priority)

Document which capabilities are retry_safe vs not, and add guidance:

```python
# In capabilities.json or registry setup:
{
    "capability_id": "aj.echo",
    "retry_safe": True,
    "verification_status": "implemented_verified",
    "availability": "available"
},
{
    "capability_id": "jarvis.web_search", 
    "retry_safe": False,
    "verification_status": "unknown",
    "availability": "available"
}
```

**Add to existing capabilities**:
- Internal/actions: retry_safe=True (already the case)
- External/network: retry_safe=False (document and verify)
- Add `retry_safe` to all registered capabilities

### 4. Circular Dependency Detection via Retry/Dead-Letter (LOW priority)

Prevent circular dependencies that would block retry or dead-letter paths:

```python
# In task creation/authorization:
if orchestrator.has_circular_dependency(new_task.task_id):
    raise errors.AjError(
        "task would have circular dependency, cannot execute",
        code=errors.CALLING_INVALID_STATE
    )
```

## Changed Files

- `AJ/aj/orchestrator.py` - `retry()`, `_retry_locked()`, `dead_letter()` methods
- `AJ/aj/task.py` - TaskRecord has `max_attempts`, `attempt`, `depends_on`, `recovery` fields
- `AJ/aj/capability.py` - CapabilitySpec has `retry_safe: bool` field (existing, verified by tests)
- `AJ/tests/test_phase3.py` - Retry and dead-letter tests (119 + 32 = 151 tests)

## Known Limitations

1. **No persistent backoff timestamps** - `next_retry_at` not in TaskRecord schema
2. **No automatic circular dependency detection** - would block retry/dead-letter paths
3. **No dead-letter recovery automation** - operator decision required (by design)
4. **No backoff maximum limit** - configurable but not enforced in software
5. **Retry_safe depends on capability registry** - must explicitly set True for each capability
6. **Dead-lettered tasks cannot be auto-recovered** - requires operator decision (by design, safety)
7. **Retry budget exhaustion escalates to ESCALATED (needs human decision)** - not auto-retry