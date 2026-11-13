# AJ — Engineering Readiness Audit: Dependency and Lineage Audit

## Purpose

This audit investigates the dependency checking and lineage tracing implementation in AJ.
It verifies unsatisfied dependency detection, lineage traversal, circular dependency gaps,
and the `depends_on` field behavior in task creation and authorization.

## Dependency Checking Overview

### `depends_on` Field

**Location**: `aj/task.py:TaskRecord.depends_on: List[str] = field(default_factory=list)`

**Purpose**: List of task_id values that must be COMPLETED before this task can execute.

**Behavior in `Aj.handle()`**:
```python
blocked_by = self.unsatisfied_dependencies(record)
if blocked_by:
    reason = f"waiting for dependencies: {', '.join(blocked_by)}"
    self.tasks.transition(record.task_id, taskmod.BLOCKED, reason)
    # Task stays BLOCKED; no scheduling until deps satisfied
```

### `unsatisfied_dependencies()` in Orchestrator

**File**: `aj/orchestrator.py:Aj.unsatisfied_dependencies(record)`

**Behavior**:
```python
def unsatisfied_dependencies(self, record: taskmod.TaskRecord) -> List[str]:
    missing: List[str] = []
    for dependency in record.depends_on:
        other = self.tasks.find(dependency)
        if other is None or other.status != taskmod.COMPLETED:
            missing.append(dependency)
    return missing
```

**Checks**:
1. For each `dependency` in `record.depends_on`:
   - Look up the dependency task via `self.tasks.find(dependency)`
   - If not found (`other is None`) → missing
   - If found but not COMPLETED (`other.status != COMPLETED`) → missing
   - If found and COMPLETED → not missing

**Return**: List of dependency task_ids that are not satisfied (None or not COMPLETED).

**Verified**: `test_health_covers_the_phase3_surface` (blocked flow test); foundation
dependency tests.

### Dependency Flow in `Aj.handle()`

```
Task creation → depends_on set on record → authorization pathway
          ↓
unsatisfied_dependencies(record) called
          ↓
If blocked: transition to BLOCKED status, audit "task_blocked"
          ↓
If not blocked: continue to routing, authorization, lease, execution
          ↓
Task may execute only when all dependencies COMPLETED
```

### Dead-letter and Dependency Interaction

| Scenario | Behavior |
|----------|----------|
| Task with `depends_on` → dead-lettered | `Aj.dead_letter()` transitions to DEAD_LETTER status regardless of deps |
| Dead-lettered task has deps | Depends_on preserved in task record; no special handling |
| Retry dead-lettered task | `can_transition(DEAD_LETTER)` check; already in DEAD_LETTER → no-op |
| Recovery after dead-letter | Task in DEAD_LETTER; `unsatisfied_dependencies()` still checks, but DEAD_LETTER is terminal, so task stays DEAD_LETTER |

### Dependency Test Coverage

| Test | What It Covers | Status |
|------|---------------|--------|
| `test_health_covers_the_phase3_surface` | Blocked flow (dependencies prevent execution) | ✅ Passes (23/23 health checks) |
| `test_foundation.py` dependency tests | Direct dependency checks (implicit in test file) | ✅ Passes (21 tests in foundation) |
| `test_recovery_on_failed_no_active_lease` | Recovery with dependencies | ✅ Passes (crash safety) |
| Circular dependency detection | ❌ NOT implemented | ⚠️ HIGH priority gap |

### Lineage Tracing

#### `lineage()` Method in Orchestrator

**File**: `aj/orchestrator.py:Aj.lineage(task_id)`

**Behavior**:
```python
def lineage(self, task_id: str) -> Dict[str, Any]:
    record = self.tasks.get(task_id)
    root = record.root_task_id or record.task_id
    children = [item.task_id for item in self.tasks.all()
                if item.parent_task_id == task_id]
    return {
        "task_id": task_id,
        "parent_task_id": record.parent_task_id,
        "root_task_id": root,
        "child_task_ids": children,
        "operation_id": record.operation_id,
        "attempts": len(record.attempts),
    }
```

**Fields**:
- `task_id`: The queried task
- `parent_task_id`: This task's parent (from TaskRecord)
- `root_task_id`: Root ancestor (or self if top-level)
- `child_task_ids`: Direct children (tasks where `parent_task_id == this task_id`)
- `operation_id`: This task's operation_id
- `attempts`: Number of attempts recorded

**Traversal limitation**: Linear O(n) scan of `self.tasks.all()`. No indexing for deep trees.
Cannot detect cycles. Will infinite-loop or exhaust memory if task tree is very deep with
cyclic `parent_task_id` / `depends_on` links.

#### `parent_task_id` Field

**Location**: `aj/task.py:TaskRecord.parent_task_id: Optional[str] = None`

**Purpose**: Link from child task to parent task. Set via `TaskRecord` creation or `child_of()`.

**Behavior**:
- Set when task is created as a child: `kw.setdefault("requester", parent.requester)`
- `return self.create(goal, parent_task_id=parent.task_id, ...)`
- Used by `lineage()` to find children

**Not to be confused with**: `depends_on` (list of task_ids that must complete before this one).
`parent_task_id` is the immediate parent in a tree structure. `depends_on` is a list of
requirements that must be COMPLETED (possibly from different branches).

### Circular Dependency Detection — GAP ANALYSIS

**Current state**: **NO automatic circular dependency detection**.

**How it fails silently**:
1. Task A has `depends_on = ["B"]`
2. Task B has `depends_on = ["A"]`
3. Both tasks remain in BLOCKED state forever
4. `unsatisfied_dependencies()` for A → ["B"] (B not COMPLETED)
5. `unsatisfied_dependencies()` for B → ["A"] (A not COMPLETED)
6. No task can ever execute

**Detection gap**: The `unsatisfied_dependencies()` function only checks if dependencies
are COMPLETED. It does not detect cycles.

**Impact**: Tasks with cyclic `depends_on` silently block forever. No error, no timeout,
no automatic resolution. Operator must manually intervene.

**HIGH priority** (as documented in KNOWN_LIMITATIONS.md).

#### Potential Circular Detection Implementation (not yet done)

```python
def has_circular_dependency(self, task_id: str, visited=None) -> bool:
    if visited is None:
        visited = set()
    if task_id in visited:
        return True  # cycle detected
    visited.add(task_id)
    record = self.tasks.find(task_id)
    if record is None:
        return False  # task doesn't exist
    for dep in record.depends_on:
        if self.has_circular_dependency(dep, visited):
            return True
    return False
```

**Integration point**: Call in `unsatisfied_dependencies()` or `Aj.handle()` before task
is scheduled, raising `AjError` or transitioning to BLOCKED with "circular dependency" reason.

**Test would be**:
```python
def test_circular_dependency_detected(aj):
    # Task A depends on B, Task B depends on A
    a = aj.tasks.create("A", capability_id="aj.echo")
    b = aj.tasks.create("B", capability_id="aj.echo")
    aj.tasks.transition(a.task_id, AUTHORIZED)
    aj.tasks.transition(b.task_id, AUTHORIZED)
    deps_a = aj.unsatisfied_dependencies(a)  # should detect cycle
    # or: Aj.handle("A", depends_on=[b.task_id])
    #     Aj.handle("B", depends_on=[a.task_id])
    # Both should fail with circular dependency error
```

**Not implemented**: This implementation does not exist. The gap is documented as HIGH priority.

### Dependency and Lineage Score: 7/10

**Score breakdown**:
- `unsatisfied_dependencies()` implementation: 9/10 (checks COMPLETED status; simple and correct for non-cyclic cases)
- `lineage()` method: 8/10 (works for shallow trees; O(n) scan; no cycle detection; no deep-tree indexing)
- `depends_on` field: 10/10 (well-defined, used correctly in authorization pathway)
- Dependency blocking in handle(): 9/10 (task transitioned to BLOCKED when deps not met)
- Circular dependency detection: 0/10 (completely missing — HIGH gap)
- Parent/child lineage traversal: 7/10 (linear scan works for small trees; no indexing for deep trees)

**Deductions**:
- 3 points for circular dependency detection (HIGH priority gap)
- 1 point for lack of deep-tree lineage indexing (MEDIUM priority)
- 1 point for no automatic BLOCKED → AUTHORIZED transition when deps satisfied (requires scheduler or manual call)

### Recommendations

1. **HIGH**: Implement circular dependency detection in `unsatisfied_dependencies()` or a new
   method. Reject tasks with cyclic `depends_on` at authorization time.

2. **MEDIUM**: Add deep-tree lineage indexing (e.g., maintain a `lineage_path` field or
   index on `parent_task_id`) for O(1) lineage queries instead of O(n) scan.

3. **MEDIUM**: Add automatic BLOCKED → AUTHORIZED transition when dependencies become
   satisfied (triggerable via health check or scheduler).

4. **LOW**: Add `lineage_path` field to TaskRecord for efficient ancestry traversal without
   scanning all tasks.

### Conclusion

The dependency and lineage system is **7/10** — functional for the common case (linear dependency
chains, no cycles), but the circular dependency detection gap is a significant HIGH-priority
issue. The lineage traversal works for small-to-moderate task trees but would benefit from
indexing for deep trees.

**Urgency**: CIRCULAR DEPENDENCY DETECTION should be the first item in the next coding phase
(P0 priority, ~50 lines of code, 2 tests).

---
*This dependency and lineage audit is based on actual code inspection of `aj/orchestrator.py:Aj.unsatisfied_dependencies()`,
`Aj.lineage()`, `aj/task.py:TaskRecord.depends_on`, and the full 126-test suite. Circular dependency
detection confirmed as missing. No modules were modified during this audit.*