# AJ Phase 4: Architecture

## Overview

This document describes the architecture of AJ's reliable local execution engine after Phase 4 completion.

## Core Abstractions

### 1. Two-Lease-Family System

AJ uses two lease families sharing the same backing store, with clear dispatch logic:

#### Operation Leases
- **Purpose**: Serialize conflicting mutations (cancel, retry, recovery, authorization changes)
- **Acquisition**: `acquire_operation(task_id, operation)` 
- **Release**: `release_operation(task_id)`
- **Key Guarantee**: Expired lease never authorizes mutation - requires explicit `break_stale_operation()` operator action
- **Ownership**: Task-level, survives worker crashes (lease expires, operator must break it)

#### Execution Leases
- **Purpose**: Identify the worker executing a task and control heartbeat/expiry
- **Acquisition**: `acquire_execution(task_id)` 
- **Release**: `release_execution(task_id)`
- **Heartbeat**: `renew_execution_lease(task_id)` - extends expiry
- **Key Guarantee**: Prevents simultaneous workers from executing one task
- **Ownership**: Worker-level, held only while task is actively executing

#### Dispatch Logic in `acquire()`
```python
# Two-family dispatch
if operation_type == "execute":
    # Execution lease family
    return self.acquire_execution(task_id)
elif operation_type in ("cancel", "retry", "recover"):
    # Operation lease family  
    return self.acquire_operation(task_id, operation_type)
```

### 2. Task State Machine

The task state machine (TRANSITIONS dict) governs all valid state changes:

```
RECEIVED -> UNDERSTANDING -> PLANNED -> AUTHORIZED -> EXECUTING -> VERIFYING -> COMPLETED/FAILED
           |                     |              |
           +-> WAITING_FOR_APPROVAL (policy conf)
           +-> RECOVERY_REQUIRED (interrupted)
           +-> CANCEL_REQUESTED (cancel pending)
           +-> FAILED (execution error)
           
Terminal: COMPLETED, ABORTED, CANCELLED, DEAD_LETTER
```

Valid reverse transitions exist for recovery paths:
- FAILED -> RECOVERING -> RETRYING -> EXECUTING (retry)
- FAILED -> ESCALATED -> COMPLETED (human decision)
- AUTHORIZED -> RECOVERY_REQUIRED (interrupted execution)
- RECOVERY_REQUIRED -> AUTHORIZED (replay-safe replay)

### 3. Control Plane Flow (Aj.handle())

```
1. Create task record
2. Route request (JARVIS/HELIX/default)
3. Transition: RECEIVED -> UNDERSTANDING -> PLANNED
4. Check dependencies (block if unsatisfied)
5. Authorize (may enter WAITING_FOR_APPROVAL)
6. Transition: AUTHORIZED -> acquire execution lease
7. _execute(): transition to EXECUTING
8. Run action (internal or through agent)
9. Transition: VERIFYING -> COMPLETED/FAILED
10. Persist result and evidence
11. Release execution lease
12. Return TaskOutcome
```

### 4. Worker Lifecycle

```
Worker Startup:
1. Identify worker (pid, host, worker_id)
2. Register with orchestrator (optional)
3. Begin heartbeat loop (renew execution lease)

Task Claiming:
1. Scheduler discovers pending task
2. Acquire execution lease on task
3. If lease acquired: proceed to execution
4. If lease held: task is being executed elsewhere

Execution:
1. Start attempt (record RUNNING attempt)
2. Execute action (internal or agent)
3. Persist result/evidence
4. Transition task to VERIFYING/COMPLETED/FAILED
5. Finish attempt (mark ended_at, add failure if any)
6. Create receipt (durable evidence)
7. Release execution lease

Graceful Shutdown:
1. Stop heartbeat loop
2. Release execution lease (or it expires)
3. Persist final state
4. Exit cleanly

Unexpected Termination:
1. Lease expires (no heartbeat within timeout)
2. Recovery assesses task state
3. If execution intent persisted but result missing: RECOVERY_REQUIRED
4. If result persisted: task remains COMPLETED
5. If neither: task can be re-attempted
```

### 5. Journal and Receipt Pipeline

```
Task Accepted
  → TASK_ACCEPTED journal event
  → task.created memory event

Authorized  
  → TASK_SCHEDULED journal event (with lease_id)
  → task.authorized memory event

Execution Started
  → EXECUTION_STARTED journal event (attempt_id, lease_id)
  → _start_attempt(): attempt record with started_at

Action Executing
  → action execute record (capability, arguments)
  → evidence appended

Execution Result
  → EXECUTION_RESULT_RECORDED journal event
  → EXECUTION_VERIFIED journal event
  → receipt recorded (attempt_id, status, verification, output/errors)

Completion
  → VERIFYING -> COMPLETED/FAILED transition
  → _finish_attempt(): attempt record with ended_at, failure
  → tasks.save(record, "completed"/"error")
  → audit.record("executed" / "failed")
  → memory.append_event("task.completed"/"task.failed")
  → receipt recorded with final status

Recovery
  → RECOVERY_STARTED journal event
  → recovery attempt (replay-safe or manual required)
  → task state transitions (RECOVERY_REQUIRED, RETRYING, etc.)
```

### 6. Recovery Manager

```
scan(): Scan all tasks for recovery opportunities
  - Find FAILED tasks with attempts
  - Find tasks in RECOVERY_REQUIRED state
  - Find tasks with expired leases and no completion evidence
  - Return list of findings with decisions: "recovery_required", "idempotent", "manual"

recover(task_id): Replay one interrupted task
  - Hold recover lease on task
  - Check spec.replay_safe (must be "internal:" adapter)
  - If replay_safe: execute _execute() with recovery route
  - If not replay_safe: require manual recovery
  - Transition task to RECOVERY_REQUIRED if needs decision
  - Return outcome with outcomes list

Key Decisions:
- "recovery_required": Task has incomplete execution, needs operator intervention
- "idempotent": Task can be safely replayed (internal:"internal:" actions only)
- "manual": Task requires human decision (retry budget exhausted, policy denied, etc.)
```

### 7. Scheduler Design

```
Eligibility Checking (per task):
1. Authorization: task.status == AUTHORIZED or scheduler can authorize
2. Dependencies: all depends_on tasks have status COMPLETED
3. Priority: respect task.priority field
4. Deadline: check task.deadline (not past)
5. Retry: if task.attempt >= max_attempts, mark as exhausted
6. Concurrency: check worker concurrency limit
7. Lease: task not already leased by another worker

Task Discovery:
1. Query all non-terminal tasks
2. Filter by eligibility
3. Sort by: priority (desc), then created_at (asc)
4. Return ordered list

Claiming:
1. Scheduler acquires execution lease on first eligible task
2. If lease acquired: task is claimed, scheduler moves to next
3. If lease held: task is in execution, scheduler skips and tries next
4. Persist scheduling decision in journal

Recovery After Restart:
1. On startup, scan for tasks with expired leases
2. Re-evaluate eligibility (leases may have been held)
3. Re-queue eligible tasks for scheduling
4. Do not re-queue tasks with active leases (another worker may have claimed them)
```

### 8. Idempotency Store

```
Persistence: JSON file at data_dir/idempotency.json
Structure: {capability_id: {idempotency_key: {task_id, status, result, timestamp}}}

Operations:
- claim(capability_id, key): Claim idempotency key
  - If key already claimed with same task_id: return existing outcome (idempotent replay)
  - If key claimed with different task_id: return Conflict error
  - If key not claimed: create claim, create task, return new outcome

- lookup(capability_id, key): Check if key exists
  - Return claimed task_id and status if found
  - Return None if not found

Guarantees:
- Atomic claim operation (via file lock or atomic read-write)
- Concurrent claim attempts: one succeeds, others get Conflict
- Key scoping by capability_id (different capabilities can use same key)
- Restart persistence (survives process restart)
- No prevention of legitimate new tasks (only prevents duplicate submission of same key)
```

### 9. Backup and Restore

```
Backup (transfer.backup_directory(config, backup_path)):
1. Read all persistent stores from config:
   - tasks.jsonl (TaskStore)
   - audit/ events-*.jsonl (AuditLog)
   - receipts.jsonl (ReceiptStore)
   - idempotency.json (IdempotencyStore)
   - journal.jsonl (Journal)
   - memory.sqlite3 (MemoryStore)
   - leases (LeaseManager backing store)
   - schema metadata

2. Write to backup directory as backup.json (full dump)
   - Include schema version metadata
   - Include all record counts and sizes

3. Create manifest with:
   - Backup timestamp
   - Record counts per store
   - Schema version
   - Export check sum

Verify (transfer.verify_backup(backup_path)):
1. Read manifest from backup
2. Validate schema version
3. Check record counts match
4. Verify no malformed records (or report them)
5. Return {"ok": True/False, "counts": {...}, "malformed": N}

Restore (transfer.import_file(config, backup_path)):
1. Read backup.json
2. Write all records to new data directory
3. Overwrite existing live state (dry-run mode available)
4. Return report: {"tasks": N, "imported_memory": M, "conflicts": C}

Dry-Run Mode:
- import_file(..., dry_run=True) returns task count and conflicts
- Does NOT write to live state
- Used to verify backup integrity before restore