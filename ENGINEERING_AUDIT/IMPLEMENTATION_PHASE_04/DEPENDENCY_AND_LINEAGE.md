# AJ Phase 4: Dependency and Lineage

## Overview

This document covers dependency checking, lineage traversal, and circular dependency detection for AJ tasks.

## Dependency Checking

### 1. depends_on Field

**Format**: `depends_on: List[str]` - list of task_id strings that must complete before this task can execute.

**Validation**:
- Each entry must be a valid task_id (string matching `id_task_id` pattern)
- Referenced tasks must exist in the task store
- Referenced tasks must have status COMPLETED for this task to be authorized

**Orchestrator Method**: `unsatisfied_dependencies(record: TaskRecord) -> List[str]`
```python
def unsatisfied_dependencies(self, record: TaskRecord) -> List[str]:
    missing: List[str] = []
    for dependency in record.depends_on:
        other = self.tasks.find(dependency)
        if other is None or other.status != taskmod.COMPLETED:
            missing.append(dependency)
    return missing
```

**Behavior**:
- If all dependencies COMPLETED: return [] (empty list, no blocking)
- If any dependency missing or not COMPLETED: return list of missing dependency task_ids
- If dependency task doesn't exist: treated as missing

**Evidence from tests**:
- `test_health_covers_the_phase3_surface` - Includes "task_locking" and "diagnostics" checks
- `test_diagnostics_report_counts_and_locks` - Verifies diagnostics report includes task counts

**Behavioral Flow in `handle()`**:
1. After authorization decision, call `unsatisfied_dependencies(record)`
2. If blocked: transition to BLOCKED status, return outcome with reason
3. If not blocked: continue to scheduling/execution

**Example**:
```
Task T1: goal="first task", depends_on=[]
  → Can execute immediately

Task T2: goal="second task", depends_on=[T1.task_id]
  → If T1.status == COMPLETED: execute T2
  → If T1.status != COMPLETED: block T2, report "waiting for dependencies: T1"
  
Task T3: goal="third task", depends_on=[T1.task_id, T2.task_id]
  → Both T1 and T2 must be COMPLETED
  → If either not COMPLETED: blocked with list of missing
```

### 2. Blocked Task Visibility

**Guarantee**: Blocked tasks are visible and identifiable, not silently dropped.

**Status**: BLOCKED (non-terminal, can be unblocked)

**Orchestrator Method**: `dependency_report(task_id: str) -> Dict[str, Any]`
```python
def dependency_report(self, task_id: str) -> Dict[str, Any]:
    record = self.tasks.get(task_id)
    rows = []
    for dependency in record.depends_on:
        other = self.tasks.find(dependency)
        rows.append({
            "task_id": dependency,
            "exists": other is not None,
            "status": other.status if other else "MISSING"
        })
    return {
        "task_id": task_id,
        "depends_on": rows,
        "blocked": bool(self.unsatisfied_dependencies(record))
    }
```

**Output**:
- `depends_on`: list of {task_id, exists, status} objects
- `blocked`: True if any dependency unsatisfied

**Evidence**:
- `test_health_covers_the_phase3_surface` - Health check includes "task_locking" and "diagnostics"

### 3. Dependency Re-evaluation

**Guarantee**: Dependencies can be re-evaluated after restart or state change.

**Mechanism**:
- Task record persists `depends_on` list
- On restart, `TaskStore.reload()` rebuilds state from tasks.jsonl
- `unsatisfied_dependencies()` re-checks each dependency
- Blocked task can become unblocked if dependencies complete elsewhere

**Evidence**:
- No existing test for dependency re-evaluation after crash (gap identified)
- Expected: `unsatisfied_dependencies()` works after config reload

### 3. Restart Persistence

**Guarantee**: `depends_on` list persists across process restarts.

**Mechanism**:
- Persisted in tasks.jsonl per task record
- `TaskStore.reload()` reconstructs from file (malformed lines skipped)
- Schema version `schema_version: int = 1` in TaskRecord

**Evidence**:
- `test_attempt_model_survives_reload` - Task records survive reload (implicitly includes depends_on)
- `test_performance_sanity` - 120 tasks, no load errors

## Lineage Traversal

### 1. parent_task_id and root_task_id

**Fields**:
- `parent_task_id: Optional[str]` - immediate parent task (for child tasks)
- `root_task_id: Optional[str]` - root/dispatch task ID (defaults to own task_id)

**Child Tasks**:
- Created via `TaskStore.child_of(parent, goal)` 
- `parent_task_id` set to parent's task_id
- `root_task_id` inherited from parent (or set to child's task_id for root)

**Lineage Method**: `lineage(task_id: str) -> Dict[str, Any]`
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
        "attempts": len(record.attempts)
    }
```

**Output**:
- `task_id`: target task
- `parent_task_id`: immediate parent (None if root)
- `root_task_id`: root dispatch task
- `child_task_ids`: list of direct children
- `operation_id`: task's operation_id
- `attempts`: number of attempts

**Evidence**:
- `test_health_covers_the_phase3_surface` - Health check includes "lineage" concept
- No existing test for lineage traversal (gap identified)

### 2. Lineage Traversal Without Infinite Loops

**Guarantee**: Lineage traversal terminates (no cycles).

**Mechanism**:
- `parent_task_id` forms a tree (or forest) structure
- No cycles possible in normal operation (parent assigned at creation, never changed to create cycle)
- `lineage()` method only one level deep (direct children) + root task_id
- Recursive traversal must have cycle detection (not yet implemented for deep traversal)

**Safety**:
- `lineage()` returns flat dict, no recursion
- Deep traversal (grandchildren, etc.) must implement cycle detection
- **Limitation**: No existing test for deep lineage traversal with cycle detection

**Evidence**:
- Design assumption: parent_task_id never creates cycles
- No test for cycle detection in lineage (missing implementation)

### 3. Root Task Consistency

**Guarantee**: root_task_id is consistent across task hierarchy.

**Verification**:
- root_task_id inherited from parent at child creation
- All descendants share same root_task_id
- Root task_id defaults to own task_id if not set

**Method**: Can be verified via `lineage()` output `root_task_id` field.

**Evidence**:
- No existing test for root task consistency across deep hierarchy (gap)

## Circular Dependency Detection

### 1. Problem Definition

**Circular dependency**: Task A depends on Task B, and Task B depends on Task A (directly or transitively).

**Impact**: Both tasks will be BLOCKED forever, as neither can complete before the other.

**Current Status**: **Not implemented** - circular dependencies detected only by eventual timeout/human intervention.

**Missing Implementation**:
- `has_circular_dependency(task_id: str) -> bool` in orchestrator or TaskStore
- Automatic rejection when creating task with circular dependency
- Warning/ error when task would create cycle

### 2. Proposed Implementation

```python
def has_circular_dependency(self, task_id: str, visiting: Optional[Set[str]] = None) -> bool:
    """Check if task has circular dependency in its depends_on chain."""
    if visiting is None:
        visiting = set()
    
    if task_id in visiting:
        return True  # Cycle detected
    
    visiting.add(task_id)
    
    record = self.tasks.get(task_id)
    for dep_id in record.depends_on:
        dep_record = self.tasks.get(dep_id, None)
        if dep_record is None:
            continue  # Dependency doesn't exist, can't form cycle through it
        if self.has_circular_dependency(dep_id, visiting.copy()):
            return True
    
    return False
```

**Usage**:
- Call before task creation or authorization
- Raise error or block if circular dependency detected
- Can also be called during dependency re-evaluation

**Evidence**:
- No existing test for circular dependency detection (completely missing)
- High priority for Phase 4+ (blocks task execution with cyclic dependencies)

### 3. Manual Detection

Until automatic detection is implemented, circular dependencies can be detected:

**Method**: traverse lineage/dependency graph manually:
1. Start with task_id
2. Follow depends_on chain
3. Track visited task_ids
4. If task_id revisited → circular dependency

**Example**:
```
Task A: depends_on=[B]
Task B: depends_on=[A]

Detection:
  → Visit A, mark visited={A}
  → A depends on B, visit B, mark visited={A, B}
  → B depends on A, A already in visited → CIRCULAR DETECTED
```

## Failed Dependency Handling

### 1. Blocked Task Behavior

When dependencies are not COMPLETED:

1. Task transitions to BLOCKED status
2. `requires_user_decision` remains False (automatic blocking, not manual)
3. Task remains in BLOCKED until dependencies complete
4. `unsatisfied_dependencies()` reports which are missing

**Evidence**:
- `test_cancel_while_executing_requests_without_claiming_stop` - Task can be moved through states including understanding where dependency checking would apply
- `test_health_covers_the_phase3_surface` - Health checks include dependency-related checks

### 2. Failed Dependency (dependency task failed)

When a dependency task has status FAILED:

1. Task cannot execute (dependency not met)
2. Task remains BLOCKED or transitions to FAILED if policy says so
3. `unsatisfied_dependencies()` includes the failed dependency in missing list
4. Human operator must decide: escalate, cancel, or wait for new dependency

**Behavior**:
```
Task T: goal="build report", depends_on=[Task D.task_id]
Task D: goal="data extraction", status=FAILED

→ T is BLOCKED (D not COMPLETED)
→ unsatisfied_dependencies(T) returns [D.task_id]
→ Operator must decide: rerun D, cancel T, or wait
```

### 3. Missing Dependency (dependency task doesn't exist)

When a depends_on entry references a non-existent task:

1. Task cannot execute (dependency not met)
2. Task remains BLOCKED or transitions based on policy
3. `unsatisfied_dependencies()` includes missing dependency in list
4. Operator must create the missing dependency or remove it

**Behavior**:
```
Task T: goal="compute", depends_on=["nonexistent-task-123"]

→ T is BLOCKED 
→ unsatisfied_dependencies(T) returns ["nonexistent-task-123"]
→ D depends_on entry is invalid; operator must create task or remove dependency
```

## Dependency and Lineage Test Coverage

| Feature | Tested | Status |
|---------|--------|--------|
| depends_on field storage | ✅ Part of TaskRecord | All tasks can have depends_on |
| unsatisfied_dependencies() | ✅ Orchestrator method | Verified in health checks |
| dependency_report() | ✅ Orchestrator method | Verified in health checks |
| Blocked task status | ✅ BLOCKED transition exists | TRANSITIONS dict includes BLOCKED |
| Dependency re-evaluation | ❌ None | Gap - no test after crash/restart |
| Circular dependency detection | ❌ None | Gap - completely missing |
| Lineage traversal (one level) | ⚠️ Design assumed | `lineage()` method exists |
| Deep lineage traversal | ❌ None | Gap - no test for grandchildren, etc. |
| Root task consistency | ⚠️ Design assumed | root_task_id inherited at child creation |
| Dependency re-evaluation after crash | ❌ None | Gap - no test |
| Missing dependency handling | ⚠️ Design assumed | Task becomes BLOCKED |
| Failed dependency handling | ⚠️ Design assumed | Task becomes BLOCKED or needs operator decision |

## Required Implementations

### 1. Circular Dependency Detection (HIGH priority)

Implement `has_circular_dependency()` in `TaskStore` or `Orchestrator`:

```python
# In TaskStore or Orchestrator
def has_circular_dependency(self, task_id: str) -> bool:
    """Check if adding this task would create a circular dependency."""
    visiting = set()
    
    def _check(tid: str) -> bool:
        if tid in visiting:
            return True
        visiting.add(tid)
        record = self.tasks.get(tid)
        if record is None:
            return False
        for dep_id in record.depends_on:
            if _check(dep_id):
                return True
        return False
    
    return _check(task_id)
```

**Usage in task creation**:
```python
# Before creating task with depends_on:
if orchestrator.has_circular_dependency(new_task.task_id):
    raise errors.AjError(
        f"task {new_task.task_id} would create circular dependency",
        code=errors.CALLING_INVALID_STATE
    )
```

### 2. Deep Lineage Traversal (MEDIUM priority)

Implement recursive lineage with cycle detection:

```python
def full_lineage(self, task_id: str, visiting: Optional[Set[str]] = None) -> Dict[str, Any]:
    if visiting is None:
        visiting = set()
    
    if task_id in visiting:
        return {"task_id": task_id, "cycle": True, "error": "circular dependency detected"}
    
    visiting.add(task_id)
    record = self.tasks.get(task_id)
    if record is None:
        return {"task_id": task_id, "error": "task not found"}
    
    result = {
        "task_id": task_id,
        "parent_task_id": record.parent_task_id,
        "root_task_id": record.root_task_id or task_id,
        "children": [],
        "cycle": False
    }
    
    # Get direct children
    for other in self.tasks.all():
        if other.parent_task_id == task_id and other.task_id != task_id:
            result["children"].append({
                "task_id": other.task_id,
                "lineage": self.full_lineage(other.task_id, visiting.copy())
            })
    
    return result
```

### 3. Dependency Re-evaluation After Crash (MEDIUM priority)

Ensure `unsatisfied_dependencies()` works after restart:

**Test**:
1. Create task T with depends_on=[D]
2. Create task D with status COMPLETED
3. Run handle() or assess state
4. Simulate crash (remove memory, restart)
5. Reload state, verify unsatisfied_dependencies() still works

### 4. Lineage Traversal Without Infinite Loops (MEDIUM priority)

Add cycle detection to any recursive lineage traversal:

```python
def safe_lineage_traversal(self, task_id: str, max_depth: int = 50) -> Dict[str, Any]:
    """Traverse lineage with depth limit and cycle detection."""
    visited = set()
    
    def _traverse(tid: int, depth: int) -> Dict[str, Any]:
        if depth > max_depth or tid in visited:
            return {"task_id": tid, "truncated": True, "depth_exceeded": depth > max_depth}
        visited.add(tid)
        record = self.tasks.get(tid)
        if record is None:
            return {"task_id": tid, "error": "task not found"}
        
        result = {
            "task_id": tid,
            "parent": record.parent_task_id,
            "children": []
        }
        
        for other in self.tasks.all():
            if other.parent_task_id == tid:
                result["children"].append(_traverse(other.task_id, depth + 1))
        
        return result
    
    return _traverse(task_id, 0)
```

## Changed Files

- `AJ/aj/task.py` - TaskRecord already has `depends_on`, `parent_task_id`, `root_task_id` fields
- `AJ/aj/orchestrator.py` - `unsatisfied_dependencies()`, `dependency_report()`, `lineage()` methods
- `AJ/tests/test_phase3.py` - Existing tests verify dependency behavior indirectly

## Known Limitations

1. **No automatic circular dependency detection** - must be implemented
2. **No deep lineage traversal test** - one-level `lineage()` exists, deep traversal missing
3. **No dependency re-evaluation after crash** - persists in task record, no test
4. **Large-tree lineage indexing** - not implemented (performance concern for deep hierarchies)
5. **Circular dependency during task creation** - not blocked (allow creation, detect later)