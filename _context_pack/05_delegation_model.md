# 05 Delegation Model (read-only)

## Dataclass/schema definitions (full source locations)

### `aj/delegation.py` (module doc: "Agent assignment, task delegation, and hierarchical orchestration foundation (5A.6).")

**Assignment status constants** (`aj/delegation.py:46-56`):
```python
AS_PROPOSED = "PROPOSED"
AS_ASSIGNED = "ASSIGNED"
AS_ACCEPTED = "ACCEPTED"
AS_RUNNING = "RUNNING"
AS_COMPLETED = "COMPLETED"
AS_FAILED = "FAILED"
AS_CANCELLED = "CANCELLED"
AS_RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
AS_REJECTED = "REJECTED"
AS_UNKNOWN = "UNKNOWN"

ASSIGNMENT_STATUSES = {
    AS_PROPOSED, AS_ASSIGNED, AS_ACCEPTED, AS_RUNNING, AS_COMPLETED, AS_FAILED,
    AS_CANCELLED, AS_RECOVERY_REQUIRED, AS_REJECTED, AS_UNKNOWN,
}
```

**`LogicalAgentRecord`** (`aj/delegation.py:122-177`, `@dataclass`):
- Fields: `agent_id: str`, `kind: str = "logical"` (internal|logical), `capabilities: List[str] = []`, `availability: str = "available"` (available|unavailable|unknown), `trust_level: str = "unverified"` (trusted|verified|unverified), `provenance: Dict[str,Any] = {}` (local/logical/internal), `capacity: Dict[str,Any] = {}`, `enabled: bool = True`, `schema_version: int = 1`, `created_at`, `updated_at`.
- `to_dict()` includes all fields; `from_dict()` validates/normalizes (agent_id required, kind/availability/trust constrained, capabilities normalized).

**`DelegationRequest`** (`aj/delegation.py:179-314`, `@dataclass`):
- Fields: `schema_version: int = 1`, `parent_task_id: str = ""`, `requested_work: str = ""`, `required_capabilities: List[str] = []`, `child_specs: List[Dict[str,Any]] = []`, `permission_context: Dict[str,Any] = {}`, `provenance: Dict[str,Any] = {}`, `idempotency_key: str = ""`, `aggregation_policy: str = "all_required"` (`all_required|any_sufficient|subset_required`), `required_child_ids: List[str] = []` (for subset_required, logical refs), `priority: int = 0`, `deadline: Optional[float] = None`, `max_children: int = 10`.
- `spec_hash()` = SHA256 of canonical JSON (`schema_version,parent_task_id,requested_work,required_capabilities,child_specs,aggregation_policy,required_child_ids,priority,deadline,max_children`).
- `validate(cls,data,*,config_max_children=20)` enforces: parent_task_id required, requested_work required, aggregation_policy in allowed set, bounds (child_specs non-empty and <= max_children/config_max_children), idempotency_key normalization, child_refs uniqueness, required capabilities explicit (per-child `required_capabilities` or inherited), permission_context/provenance dict-or-empty. No explicit per-child required/optional classification field.

**`DelegationRecord`** (`aj/delegation.py:316-360`, `@dataclass`):
- Fields: `delegation_id: str`, `request: DelegationRequest`, `root_task_id: str = ""`, `child_task_ids: List[str] = []`, `child_refs: Dict[str,str] = {}` (logical child_ref -> task_id), `status: str = "RECORDED"`, `reason: str = ""`, `evidence: Dict[str,Any] = {}`, `created_at`, `updated_at`, `schema_version: int = 1`.
- `to_dict()` serializes `request` via `request.to_dict()`; `from_dict()` reconstructs.

**`AssignmentRecord`** (`aj/delegation.py:362-453`, `@dataclass`):
- Fields: `assignment_id: str`, `delegation_id: str`, `parent_task_id: str`, `child_task_id: str`, `agent_id: str`, `capability_id: str = ""`, `status: str = AS_PROPOSED`, `logical_internal: bool = True`, `reason: str = ""`, `match: Dict[str,Any] = {}`, `permission_decision: Dict[str,Any] = {}`, `evidence: Dict[str,Any] = {}`, `created_at`, `updated_at`, `schema_version: int = 1`.
- State machine: `_ASSIGNMENT_TRANSITIONS` allows e.g. PROPOSED->ASSIGNED/REJECTED/CANCELLED, ASSIGNED->ACCEPTED/RUNNING/FAILED/CANCELLED/RECOVERY_REQUIRED/REJECTED/UNKNOWN, terminal-like sets include COMPLETED/FAILED/CANCELLED/RECOVERY_REQUIRED/REJECTED/UNKNOWN with limited recovery paths; `transition()` enforces unless `force=True`.

**Stores** (`aj/delegation.py`):
- `AppendOnlyJsonlStore` (`455+`): generic append-only JSONL by record id (path, flocked append, in-memory index from latest snapshot semantics as implemented), `append/get/all`.
- `DelegationStore` (`530+`, wraps `AppendOnlyJsonlStore`): indexes by `delegation_id`, `idempotency_key`, `parent_task_id`; `create/save/get/find_by_idempotency/list_for_parent/all`.
- `AssignmentStore` (`596+`): `create/save/get/all/list_for_child/list_for_delegation/active_for_child`.
- `LogicalAgentStore` (`641+`): `save/upsert/get/all`.

**Policy/logic functions** (`aj/delegation.py`): `compute_root_task_id`, `validate_parent_chain`, `_capability_state`, `match_agent` (deterministic, fail-closed), `narrow_permissions` (intersection-only, fail-closed on missing/ambiguous), `aggregate_parent_progress` (policies `all_required|any_sufficient|subset_required`, computes counts/can_complete/requires_manual_review/manual-review reasons), `_child_snapshot_hash`, `detect_delegation_anomalies` (read-only best-effort detectors incl. incorrect_completed_parent, incomplete delegation, stale aggregation, stuck assignments, recovery_required assignments, parent-child disagreements, etc.).

### `aj/execution_domain.py` (module doc: "First-class Execution domain foundation (Phase 5A.4).")

**`ExecutionRecord`** (`aj/execution_domain.py:51-140+`, `@dataclass`):
- States: `CREATED, READY, RUNNING, COMPLETED, FAILED, CANCELLED, UNKNOWN, RECOVERY_REQUIRED`; `TERMINAL={COMPLETED,FAILED,CANCELLED}`; explicit `TRANSITIONS`.
- Fields: `execution_id, task_id, operation_id="", status=CREATED, correlation_id="", agent_id="", assignment_id="", lease_id="", current_attempt_id="", attempt_ids=[], reason="", schema_version=1, created_at, updated_at, completed_at, metadata={}, events=[]`.
- `transition()` validates state/terminal/edge unless `force`; appends event. `ExecutionStore` provides append-only JSONL persistence with fail-closed validation.

### `aj/task.py` (Task fields relevant to delegation/execution)

**`TaskRecord`** selected fields (`aj/task.py:89-137`): `task_id, operation_id, goal, requester, owner_agent, status=RECEIVED, permission_level, capability_id, provider, request_payload, result, error, parent_task_id, child_task_ids, created_at, updated_at, completed_at, attempt, max_attempts, schema_version, approval_required, approval_fingerprint, warnings, recovery, attempts, depends_on, priority, deadline, root_task_id, requires_user_decision, summary, events, authorization_context, current_execution_id, execution_ids`.  
`to_dict()/from_dict` persist these fields (incl. delegation-related linkage `parent_task_id`, `child_task_ids`, `root_task_id`, `authorization_context`).

### Logical Agent (runtime)

`LogicalAgentRecord` is the modeled/logical agent entity stored in `LogicalAgentStore`; `Aj.delegate` seeds/uses logical agents (`_seed_logical_agents`) and records `match`/`logical_internal` in assignments and child delegation context. No real remote agent transport. (UNVERIFIED beyond inspected model/usage.)

## `required` / `optional` / `mandatory` / `critical` occurrences (grep evidence)

Command: `grep -rn 'required\|optional\|mandatory\|critical' aj/delegation.py aj/orchestrator.py aj/task.py`

**Key findings (file:line excerpts):**
- `aj/delegation.py:185,194,195,203,209,219,229,242,252,253,256,268,293-296,301,311`: `required_capabilities`, `aggregation_policy="all_required"`, `required_child_ids` fields/serialization/validation (`"aggregation_policy must be all_required, any_sufficient, or subset_required"`); child specs require explicit capabilities.
- `aj/delegation.py:723,726,728,753,754,763`: `match_agent(required_capabilities, ...)` fails closed on `no_required_capabilities` / no matching agent.
- `aj/delegation.py:817,818,823,856-892,945,958,1086`: `aggregate_parent_progress(..., aggregation_policy="all_required", required_child_task_ids=...)` computes required status set, `can_complete` over required/subset, `requires_manual_review`; anomalies include `incorrect_completed_parent` severity `critical`, `recovery_required_assignment` severity `high`.
- `aj/delegation.py:683`: `parent_task_id is required`.
- `aj/orchestrator.py:398,402,425,429,455,460`: `mandatory=True` / `"mandatory security audit..."` in authz/audit paths.
- `aj/orchestrator.py:936,1163,1168,1182,1184,1194,1206,2462,2464,2468,2537,2571,2574,2874,2969,2971,3005,3221,3223,3297,3299,3307,3314,3315,3748,3752,4059,4194,4215`: "manual reconciliation required"/"recovery required"/`reconciliation action is required`/`reason is required`/`clear_recovery_required` semantics and parent completion block "required child work unresolved...".
- `aj/orchestrator.py:4310,4314`: delegation creation requires explicit child capabilities (`required_capabilities must be explicit`).
- `aj/task.py:107,208`: `approval_required` field persisted.
- **No explicit per-child `required`/`optional` classification field found in `DelegationRequest.child_specs` schema** (validated structure carries `child_ref`, `goal`, `required_capabilities`, `capability_id`, `permission_context`, `request_payload`, `priority`, `deadline` only). Classification is implicit via delegation-level `aggregation_policy`/`required_child_ids`.

## Parent completion guarded (exact function, file:line, transitions covered/not covered)

- **Pre-transition guard (block unsafe completion):** `aj/orchestrator.py:3733-3760` `Aj._before_task_transition(self, task_id, status, detail="", *, force=False, reason="transition")`
  - Wired in `Aj.__init__` by monkey-patching `self.tasks.transition` to call guard before original transition (`aj/orchestrator.py:235-241`), and `self.tasks.after_transition = self._on_task_transition` (`236`).
  - **Covers:** non-forced transition where `status == taskmod.COMPLETED` and parent has delegations (`_delegations_for_parent(task_id)` non-empty). For each delegation computes `aggregate_parent_progress(...)` and raises `errors.Conflict` if `not can_complete` or `requires_manual_review` or aggregation/check unverifiable (fail-closed).
  - **Does not cover:** forced completions (`force=True` bypass), transitions to states other than `COMPLETED`, completion paths that bypass this patched `tasks.transition` (UNVERIFIED exhaustively), or correctness of aggregation policy/classification semantics beyond implemented checks.
- **Post-transition hook/reconciliation:** `aj/orchestrator.py:3782-3818` `Aj._on_task_transition(...)` triggers bounded `_reconcile_delegation_parent(..., apply_parent_policy=True)` on child transitions (when linked); updates delegation evidence/pending markers on errors. Not a completion authorization by itself.
- **Explicit reconciliation API:** `aj/orchestrator.py:3820-3833` `Aj.reconcile_delegation_parent(...)` (dry-run default; apply requires explicit flag) -> `_reconcile_delegation_parent` (`4030+`) computes aggregation/evidence; apply may prepare children and persist evidence but does not itself force parent completion in inspected code.

## Persisted formats (JSONL/SQLite): files, examples, schema/version fields

**JSONL (append-oriented, lock-backed in stores):**
- **Tasks:** `TaskStore` at `<core.data_dir>/tasks.jsonl` (or provided dir/file per implementation). Records are JSON objects per line with `schema_version` (TaskRecord `schema_version=1`), lifecycle/status, events, attempts, `authorization_context`, execution/delegation linkage fields, etc. (`aj/task.py`).
- **Delegations:** `DelegationStore` / `AppendOnlyJsonlStore` file named `delegations.jsonl` under AJ data dir (path constructed in orchestrator assembly; exact base path: `config.get("core.data_dir")`/derived, UNVERIFIED exact filename join without full assembly trace but store accepts path; created as `.../delegations.jsonl` in typical Phase 5A usage/tests). Record example shape (redacted): `{"record_id":"<delegation_id>","delegation":{"schema_version":1,"delegation_id":"dlg_...","request":{"schema_version":1,"parent_task_id":"tsk_...","requested_work":"...","required_capabilities":[...],"child_specs":[{"child_ref":"c1","goal":"...","required_capabilities":[...]}],"permission_context":{},"provenance":{},"idempotency_key":"...","aggregation_policy":"all_required","required_child_ids":[],"priority":0,"deadline":null,"max_children":10},"root_task_id":"tsk_...","child_task_ids":["tsk_child..."],"child_refs":{"c1":"tsk_child..."},"status":"COMPLETED_CREATION|RECORDED|FAILED|RECOVERY_REQUIRED|...","reason":"...","evidence":{...},"created_at":<float>,"updated_at":<float>}}`.
- **Assignments:** `assignments.jsonl` (similar append-only). Example (redacted): `{"record_id":"asg_...","assignment":{"schema_version":1,"assignment_id":"asg_...","delegation_id":"dlg_...","parent_task_id":"tsk_...","child_task_id":"tsk_...","agent_id":"agent:logical:...","capability_id":"...","status":"ASSIGNED|...","logical_internal":true,"reason":"...","match":{...},"permission_decision":{...},"evidence":{...},"created_at":<float>,"updated_at":<float>}}`.
- **Logical agents:** `logical_agents.jsonl`. Example (redacted): `{"record_id":"agent:logical:...","agent":{"schema_version":1,"agent_id":"agent:logical:...","kind":"logical","capabilities":[...],"availability":"available","trust_level":"unverified","provenance":{"local":true,...},"capacity":{},"enabled":true,"created_at":<float>,"updated_at":<float>}}`.
- **Executions:** `executions.jsonl` (ExecutionStore, append-only). Example (redacted): `{"schema_version":1,"execution_id":"exe_...","task_id":"tsk_...","operation_id":"...","status":"RUNNING|COMPLETED|FAILED|...","correlation_id":"...","agent_id":"...","assignment_id":"...","lease_id":"...","current_attempt_id":"...","attempt_ids":[...],"reason":"...","created_at":<float>,"updated_at":<float>,"completed_at":<float|null>,"metadata":{},"events":[{"status":"...","at":<float>,"detail":"..."}]}`.
- **Receipts/journal/audit/operation evidence/scheduler ledger:** separate stores/files exist (`aj/receipts.py`, `aj/journal.py`, `aj/audit.py`, `aj/operation_evidence.py`, `aj/scheduler.py` `DispatchLedger`) with append-oriented evidence; exact schemas vary by module (see source). Not exhaustively enumerated here.

**SQLite:**
- **MemoryStore:** `<core.memory_path>` / typically `memory.sqlite3` (e.g. `<data_dir>/memory.sqlite3`), schema created via `executescript(_SCHEMA)` in `aj/memory.py::MemoryStore.__init__` (`_SCHEMA` includes `events` table, `summaries`/related tables as defined in `aj/memory.py`), WAL behavior subject to SQLite/filesystem defaults and pragmas at runtime (see `07_sqlite_wal_evidence.md`). Not used as delegation/execution/task authoritative store except memory evidence.
- **No SQLite schema observed for delegation/assignment/execution/task records** in inspected modules (JSONL/file-backed stores used).

**Schema/version fields observed:** `schema_version` present on TaskRecord (1), ExecutionRecord (1), DelegationRequest/DelegationRecord/AssignmentRecord/LogicalAgentRecord (1), Lease (SCHEMA_VERSION=1). Stores may include envelope `record_id` + typed payload.
