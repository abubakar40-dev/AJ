"""Task lifecycle.

One task record is created for every request AJ accepts, and every delegated
child task gets its own record. The record is the accountability object: who
asked, who owns it, what it was allowed to do, what happened, and what is still
unresolved.

States
------
::

    RECEIVED -> UNDERSTANDING -> PLANNED -> AUTHORIZED -> EXECUTING -> VERIFYING
                                                            |            |
                                                            v            v
                                                          FAILED      COMPLETED
                                                            |
                                                            v
                                                       RECOVERING
                                                       /   |    \\
                                                  RETRY  ESCALATE ABORTED

``WAITING_FOR_APPROVAL`` is entered instead of ``AUTHORIZED`` when policy says the
action needs a human. ``CANCELLED`` is reachable from any non-terminal state.

Terminal states never transition again. A late result for a terminal task is
recorded as a note, not as a resurrection.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import errors, ids
from .locking import file_lock

RECEIVED = "RECEIVED"
UNDERSTANDING = "UNDERSTANDING"
PLANNED = "PLANNED"
WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
AUTHORIZED = "AUTHORIZED"
EXECUTING = "EXECUTING"
VERIFYING = "VERIFYING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
RECOVERING = "RECOVERING"
RETRYING = "RETRYING"
ESCALATED = "ESCALATED"
ABORTED = "ABORTED"
CANCELLED = "CANCELLED"
# A persisted task that cannot be replayed safely waits here for a human.
RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
# A running task was asked to stop; execution was not forcibly interrupted.
CANCEL_REQUESTED = "CANCEL_REQUESTED"
# Dependency-blocked work; not final.
BLOCKED = "BLOCKED"
# Permanently abandoned after a human/policy decision; preserves all history.
DEAD_LETTER = "DEAD_LETTER"

# A task is *final* when nothing more may happen to it. FAILED is deliberately
# not final: failure is the entry point of the recovery path.
TERMINAL = (COMPLETED, ABORTED, CANCELLED, DEAD_LETTER)

TRANSITIONS: Dict[str, tuple] = {
    RECEIVED: (UNDERSTANDING, FAILED, CANCELLED, ABORTED, RECOVERY_REQUIRED),
    UNDERSTANDING: (PLANNED, FAILED, CANCELLED, ABORTED, RECOVERY_REQUIRED),
    PLANNED: (AUTHORIZED, WAITING_FOR_APPROVAL, CANCELLED, ABORTED, FAILED,
              RECOVERY_REQUIRED, BLOCKED),
    WAITING_FOR_APPROVAL: (AUTHORIZED, CANCELLED, ABORTED, FAILED, RECOVERY_REQUIRED),
    AUTHORIZED: (EXECUTING, CANCELLED, ABORTED, RECOVERY_REQUIRED),
    EXECUTING: (VERIFYING, FAILED, CANCELLED, ABORTED, RECOVERY_REQUIRED,
                CANCEL_REQUESTED),
    VERIFYING: (COMPLETED, FAILED, CANCELLED, ABORTED, RECOVERY_REQUIRED),
    FAILED: (RECOVERING, ABORTED, ESCALATED, DEAD_LETTER),
    RECOVERING: (RETRYING, ESCALATED, ABORTED, DEAD_LETTER),
    RETRYING: (EXECUTING, FAILED, ABORTED),
    ESCALATED: (CANCELLED, ABORTED, COMPLETED, DEAD_LETTER),
    RECOVERY_REQUIRED: (AUTHORIZED, FAILED, ABORTED, CANCELLED, DEAD_LETTER),
    CANCEL_REQUESTED: (CANCELLED, COMPLETED, FAILED, ABORTED, DEAD_LETTER),
    BLOCKED: (AUTHORIZED, PLANNED, CANCELLED, FAILED, DEAD_LETTER,
              RECOVERY_REQUIRED),
    COMPLETED: (),
    ABORTED: (),
    CANCELLED: (),
    DEAD_LETTER: (),
}


@dataclass
class TaskRecord:
    """One unit of accountable work."""

    task_id: str
    goal: str
    operation_id: str = field(default_factory=lambda: ids.new_task_id("op"))
    schema_version: int = 1
    requester: str = "user"
    owner_agent: str = "AJ"
    parent_task_id: Optional[str] = None
    capability_id: str = ""
    permission_level: int = 0
    approval_required: bool = False
    request_payload: Dict[str, Any] = field(default_factory=dict)
    status: str = RECEIVED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    attempt: int = 1
    max_attempts: int = 3
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    actions_not_taken: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recovery: Dict[str, Any] = field(default_factory=dict)
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    priority: int = 0
    deadline: Optional[float] = None
    root_task_id: Optional[str] = None
    requires_user_decision: bool = False
    summary: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    # Durable evidence of the authorization that moved this task to AUTHORIZED.
    # Used to detect stale-policy / materially changed execution context on resume.
    authorization_context: Dict[str, Any] = field(default_factory=dict)
    # First-class execution domain linkage (5A.4). AJ-owned execution identities;
    # Task != Execution != Attempt. Backward-compatible for legacy records.
    current_execution_id: str = ""
    execution_ids: List[str] = field(default_factory=list)

    # --- transitions -----------------------------------------------------
    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL

    def can_transition(self, status: str) -> bool:
        return status in TRANSITIONS.get(self.status, ())

    def transition(self, status: str, detail: str = "", *, force: bool = False) -> "TaskRecord":
        if status == self.status:
            return self
        if not force and not self.can_transition(status):
            raise errors.AjError(
                f"task {self.task_id}: illegal transition {self.status} -> {status}",
                code=errors.CALLING_INVALID_STATE,
                detail={"from": self.status, "to": status},
            )
        if self.terminal and not force:
            raise errors.AjError(
                f"task {self.task_id} is already final ({self.status})",
                code=errors.CALLING_INVALID_STATE,
            )
        self.status = status
        self.updated_at = time.time()
        if status in TERMINAL:
            self.completed_at = self.updated_at
        event: Dict[str, Any] = {"status": status, "at": self.updated_at}
        if detail:
            event["detail"] = detail[:500]
        self.events.append(event)
        return self

    # --- evidence --------------------------------------------------------
    def record_action(self, action: str, detail: str = "", **extra: Any) -> "TaskRecord":
        self.actions_taken.append({"action": action, "detail": detail[:500],
                                   "at": time.time(), **extra})
        self.updated_at = time.time()
        return self

    def record_skipped(self, action: str, reason: str) -> "TaskRecord":
        self.actions_not_taken.append({"action": action, "reason": reason[:500],
                                       "at": time.time()})
        return self

    def record_error(self, error: Any, *, stage: str = "") -> "TaskRecord":
        payload = error.to_dict() if hasattr(error, "to_dict") else {"message": str(error)}
        payload["stage"] = stage
        payload["at"] = time.time()
        self.errors.append(payload)
        self.updated_at = time.time()
        return self

    def note(self, message: str) -> "TaskRecord":
        self.warnings.append(message[:500])
        return self

    # --- serialisation ---------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "schema_version": self.schema_version,
            "parent_task_id": self.parent_task_id,
            "root_task_id": self.root_task_id,
            "goal": self.goal,
            "requester": self.requester,
            "owner_agent": self.owner_agent,
            "capability_id": self.capability_id,
            "request_payload": self.request_payload,
            "permission_level": self.permission_level,
            "approval_required": self.approval_required,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "actions_taken": self.actions_taken,
            "actions_not_taken": self.actions_not_taken,
            "artifacts": self.artifacts,
            "evidence": self.evidence,
            "errors": self.errors,
            "warnings": self.warnings,
            "recovery": self.recovery,
            "attempts": self.attempts,
            "depends_on": self.depends_on,
            "priority": self.priority,
            "deadline": self.deadline,
            "requires_user_decision": self.requires_user_decision,
            "summary": self.summary,
            "events": self.events,
            "authorization_context": (
                dict(self.authorization_context)
                if isinstance(getattr(self, "authorization_context", None), dict)
                else ({} if not getattr(self, "authorization_context", None) else {"_raw": str(self.authorization_context)})
            ),
            "current_execution_id": str(getattr(self, "current_execution_id", "") or ""),
            "execution_ids": list(getattr(self, "execution_ids", []) or []),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRecord":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        values = {k: v for k, v in data.items() if k in known}
        ac = values.get("authorization_context")
        if ac is not None and not isinstance(ac, dict):
            values["authorization_context"] = {}
        if not values.get("operation_id") and values.get("task_id"):
            values["operation_id"] = f"op-{values['task_id']}"
        if values.get("current_execution_id") is None:
            values["current_execution_id"] = ""
        if values.get("execution_ids") is None:
            values["execution_ids"] = []
        return cls(**values)


class TaskStore:
    """Thread-safe task records with append-only persistence and ownership boundary.

    Contracts:
    - **Normal creation:** ``create``/``child_of`` establish new tasks in a valid
      initial lifecycle state (RECEIVED) with store-generated/validated identity
      conventions and persist fail-closed.
    - **Existing-record update:** ``save``/``update`` apply snapshot data to an
      existing canonical record but preserve store-controlled lifecycle/identity/
      history fields (``status``, ``events``, ``completed_at``, ids, schema,
      ``created_at``); unknown IDs are rejected (not a creation/import path).
    - **Import/restore:** ``import_record`` explicitly adopts validated historical
      records (including legitimate terminal states/event history) for transfer/
      restore, rejects invalid/conflicting records, and never overwrites existing
      canonical history. Trust/provenance/authorization for import initiation is
      the caller's responsibility; TaskStore enforces structural validation and
      fails closed.

    Authoritative in-memory state lives only in ``_tasks`` and is mutated only by
    store-controlled operations under ``self._lock``. Public read/mutation APIs
    return deep-copied snapshots (never live aliases of ``_tasks`` objects).
    Lifecycle changes go through ``transition``/``cancel`` (or controlled forced
    transitions explicitly allowed by store APIs/callers).

    Persistence is append-only JSONL. On append failure, persistence is fail-closed:
    ``StorageError`` is raised after in-lock reconciliation to last durable state
    (or removal if unrecoverable). ``_on_persist_failure`` is a deterministic
    test/debug seam and must not become a production control mechanism.

    ``after_transition`` (optional) is a best-effort callback invoked after a
    lifecycle transition/cancellation has been durably persisted: ``(snapshot,
    previous_status, new_status, reason)``. It must not assume cross-store
    atomicity and must not raise to break committed task state.
    """

    def __init__(self, persist_dir: Optional[str | Path] = None, *,
                 after_transition=None):
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = threading.RLock()
        self._path: Optional[Path] = None
        self.load_errors: List[Dict[str, Any]] = []
        self.after_transition = after_transition
        if persist_dir:
            self._path = Path(persist_dir) / "tasks.jsonl"
            self.reload()

    @staticmethod
    def _snapshot(record: TaskRecord) -> TaskRecord:
        """Deep-copy a record so callers cannot alias authoritative in-memory state."""
        return TaskRecord.from_dict(copy.deepcopy(record.to_dict()))

    # --- creation --------------------------------------------------------
    def create(
        self,
        goal: str,
        *,
        requester: str = "user",
        owner_agent: str = "AJ",
        parent_task_id: Optional[str] = None,
        capability_id: str = "",
        permission_level: int = 0,
        task_id: Optional[str] = None,
        max_attempts: int = 3,
    ) -> TaskRecord:
        goal = (goal or "").strip()
        if not goal:
            raise errors.AjError("a task needs a goal", code=errors.CONFIG_INVALID)
        record = TaskRecord(
            task_id=task_id or ids.new_task_id(),
            goal=goal,
            requester=requester,
            owner_agent=owner_agent.upper(),
            parent_task_id=parent_task_id,
            capability_id=capability_id,
            permission_level=int(permission_level),
            max_attempts=max(1, int(max_attempts)),
        )
        with self._lock:
            self._tasks[record.task_id] = record
            self._persist_locked(record, "created")
            return self._snapshot(record)

    def child_of(self, parent: TaskRecord, goal: str, **kw: Any) -> TaskRecord:
        kw.setdefault("requester", parent.requester)
        kw.setdefault("owner_agent", parent.owner_agent)
        rec = self.create(
            goal,
            parent_task_id=parent.task_id,
            task_id=ids.new_child_id(parent.task_id),
            **kw,
        )
        # Preserve explicit root lineage for delegated/orchestrated hierarchies.
        root = parent.root_task_id or parent.task_id
        if getattr(rec, "root_task_id", None) != root:
            # store-controlled field update via mutate/apply not allowed for lineage safety in general;
            # set directly on canonical managed record and persist.
            with self._lock:
                current = self._tasks.get(rec.task_id)
                if current is not None:
                    current.root_task_id = root
                    self._persist_locked(current, "root_linked")
                    return self._snapshot(current)
        return rec

    # --- access ----------------------------------------------------------
    def get(self, task_id: str) -> TaskRecord:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise errors.AjError(f"unknown task {task_id!r}", code="task_not_found")
            return self._snapshot(record)

    def find(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            record = self._tasks.get(task_id)
            return self._snapshot(record) if record is not None else None

    def all(self) -> List[TaskRecord]:
        with self._lock:
            return [self._snapshot(self._tasks[k]) for k in sorted(self._tasks)]

    def active(self) -> List[TaskRecord]:
        with self._lock:
            return [self._snapshot(self._tasks[k]) for k in sorted(self._tasks)
                    if not self._tasks[k].terminal]

    def query(self, *, status: str = "", limit: int = 0,
              newest_first: bool = True) -> List[TaskRecord]:
        """Deterministic listing with optional status filter and limit."""
        with self._lock:
            records = [self._tasks[k] for k in sorted(self._tasks)]
            if status:
                records = [r for r in records if r.status == status.upper()]
            if newest_first:
                records = list(reversed(records))
            if limit and limit > 0:
                records = records[:limit]
            return [self._snapshot(r) for r in records]

    # --- persistence -----------------------------------------------------
    def reload(self) -> Dict[str, Any]:
        """Rebuild in-memory state from the append-only file.

        The file is never rewritten. Malformed lines are reported in
        ``load_errors`` and skipped, so one bad record cannot hide the rest or
        cause history to be discarded.
        """
        with self._lock:
            return self._reload_locked()

    def _reload_locked(self) -> Dict[str, Any]:
        """Reload implementation. Call with ``self._lock`` held."""
        loaded: Dict[str, TaskRecord] = {}
        load_errors: List[Dict[str, Any]] = []
        lines = 0
        if self._path is not None and self._path.is_file():
            try:
                with file_lock(str(self._path) + ".lock", exclusive=False,
                               timeout=5.0):
                    raw_lines = self._path.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
            except OSError as exc:
                load_errors.append(
                    {"line": 0, "error": f"could not read {self._path}: {exc}"}
                )
                raw_lines = []
            for number, line in enumerate(raw_lines, start=1):
                if not line.strip():
                    continue
                lines += 1
                try:
                    envelope = json.loads(line)
                    data = envelope.get("task", envelope)
                    record = TaskRecord.from_dict(data)
                except Exception as exc:
                    load_errors.append(
                        {"line": number, "error": f"{type(exc).__name__}: {exc}"}
                    )
                    continue
                if record.status not in TRANSITIONS:
                    load_errors.append(
                        {"line": number,
                         "error": f"unknown task status {record.status!r}"}
                    )
                    continue
                loaded[record.task_id] = record
        self.load_errors = load_errors
        self._tasks = loaded
        return {"tasks": len(loaded), "lines": lines,
                "errors": list(self.load_errors)}

    def close(self) -> None:
        """Close the task store (no-op for in-memory stores).

        The TaskStore is in-memory only; persistence is handled via the
        append-only JSONL file. This method is provided for compatibility
        with test scenarios that simulate process restart.
        """
        return None

    def save(self, record: TaskRecord, reason: str = "update") -> TaskRecord:
        """Update an existing canonical task record and append it to the log.

        Callers may pass a snapshot/copy (e.g. from read or mutation APIs).
        For existing tasks, snapshot data is applied to the canonical managed
        record but store-controlled lifecycle/identity/history fields are
        preserved (``task_id``, ``operation_id``, ``schema_version``,
        ``created_at``, ``status``, ``events``, ``completed_at``), so callers
        cannot bypass legal transitions or fabricate lifecycle history.

        ``save`` is not a creation or import API: unknown task IDs are rejected.
        Use ``create``/``child_of`` for normal new tasks and ``import_record``
        for validated historical transfer/import/restore.
        """
        with self._lock:
            current = self._tasks.get(record.task_id)
            if current is None:
                raise errors.AjError(
                    f"cannot save unknown task {record.task_id!r}; "
                    "use create() for new tasks or import_record() for validated restore/import",
                    code=errors.CALLING_INVALID_STATE,
                    detail={"task_id": getattr(record, "task_id", ""), "reason": reason},
                )
            if current is record:
                canonical = current
            else:
                # snapshot/update path: apply to canonical managed record.
                # Status and event history are store-controlled lifecycle state;
                # snapshot values cannot override/bypass canonical lifecycle.
                data = copy.deepcopy(record.to_dict())
                data["task_id"] = current.task_id
                data["operation_id"] = current.operation_id
                data["schema_version"] = current.schema_version
                data["created_at"] = current.created_at
                data["status"] = current.status
                data["events"] = copy.deepcopy(current.events)
                data["completed_at"] = current.completed_at
                canonical = TaskRecord.from_dict(data)
                self._tasks[current.task_id] = canonical
            self._persist_locked(canonical, reason)
            return self._snapshot(canonical)

    # --- import / restore ------------------------------------------------
    @staticmethod
    def _validate_import_record(record: TaskRecord) -> None:
        """Validate a historical record for explicit import/restore.

        Validation is strict enough to reject arbitrary/invalid initial state but
        permissive enough to preserve legitimate historical records (including
        terminal states and existing event history). Trust boundary: callers of
        import/restore are responsible for provenance/authorization; this method
        enforces structural/lifecycle consistency and fails closed on invalid data.
        """
        tid = getattr(record, "task_id", None)
        if not isinstance(tid, str) or not tid.strip():
            raise errors.Conflict("import record requires a non-empty task_id")
        oid = getattr(record, "operation_id", None)
        if not isinstance(oid, str) or not oid.strip():
            raise errors.Conflict(f"import record {tid}: operation_id must be a non-empty string")
        schema = getattr(record, "schema_version", None)
        if schema != 1:
            raise errors.Conflict(
                f"import record {tid}: unsupported schema_version {schema!r}")
        status = getattr(record, "status", None)
        if status not in TRANSITIONS:
            raise errors.Conflict(
                f"import record {tid}: invalid status {status!r}")
        goal = getattr(record, "goal", None)
        if not isinstance(goal, str):
            raise errors.Conflict(f"import record {tid}: goal must be a string")
        created_at = getattr(record, "created_at", None)
        if not isinstance(created_at, (int, float)):
            raise errors.Conflict(f"import record {tid}: created_at must be numeric")
        updated_at = getattr(record, "updated_at", None)
        if updated_at is not None and not isinstance(updated_at, (int, float)):
            raise errors.Conflict(f"import record {tid}: updated_at must be numeric")
        completed_at = getattr(record, "completed_at", None)
        if completed_at is not None and not isinstance(completed_at, (int, float)):
            raise errors.Conflict(f"import record {tid}: completed_at must be numeric")
        if status in TERMINAL and completed_at is None:
            # legitimate terminal records are expected to carry completion time
            raise errors.Conflict(
                f"import record {tid}: terminal status {status} requires completed_at")
        if status not in TERMINAL and completed_at is not None:
            raise errors.Conflict(
                f"import record {tid}: non-terminal status {status} cannot have completed_at")
        events = getattr(record, "events", None)
        if events is None:
            events = []
        if not isinstance(events, list):
            raise errors.Conflict(f"import record {tid}: events must be a list")
        prev_at = None
        prev_status = RECEIVED
        for idx, ev in enumerate(events):
            if not isinstance(ev, dict):
                raise errors.Conflict(f"import record {tid}: events[{idx}] must be an object")
            ev_status = ev.get("status")
            if ev_status not in TRANSITIONS:
                raise errors.Conflict(
                    f"import record {tid}: events[{idx}] has invalid status {ev_status!r}")
            ev_at = ev.get("at")
            if not isinstance(ev_at, (int, float)):
                raise errors.Conflict(
                    f"import record {tid}: events[{idx}] has non-numeric at")
            if prev_at is not None and ev_at < prev_at:
                raise errors.Conflict(
                    f"import record {tid}: events are not chronologically ordered")
            # Event history must represent known states and be chronologically
            # consistent. Forced/exceptional transitions exist in legitimate
            # historical records (e.g. requeue/abandon), so edge legality is not
            # enforced strictly here beyond known statuses and final consistency.
            prev_at = ev_at
            prev_status = ev_status
        if events:
            last_status = events[-1].get("status")
            if last_status != status:
                raise errors.Conflict(
                    f"import record {tid}: status {status!r} inconsistent with last event {last_status!r}")
            if isinstance(completed_at, (int, float)) and completed_at < events[-1]["at"]:
                raise errors.Conflict(
                    f"import record {tid}: completed_at precedes last event")
        elif status != RECEIVED:
            # allow RECEIVED without events (initial create snapshot), otherwise require history
            raise errors.Conflict(
                f"import record {tid}: non-initial status {status!r} requires event history")
        # basic container/type shape checks for common structured fields
        for fname, expected in (
            ("request_payload", dict), ("authorization_context", dict),
            ("recovery", dict), ("actions_taken", list), ("actions_not_taken", list),
            ("artifacts", list), ("evidence", list), ("errors", list),
            ("warnings", list), ("attempts", list), ("depends_on", list),
            ("execution_ids", list),
        ):
            val = getattr(record, fname, None)
            if val is not None and not isinstance(val, expected):
                raise errors.Conflict(
                    f"import record {tid}: {fname} must be a {expected.__name__}")
        # ensure record is serializable/canonicalizable (JSON-native import shape)
        try:
            json.dumps(record.to_dict(), ensure_ascii=False)
        except Exception as exc:
            raise errors.Conflict(
                f"import record {tid}: not serializable: {exc}") from exc

    def import_record(self, record: TaskRecord | Dict[str, Any], *,
                      reason: str = "imported") -> TaskRecord:
        """Explicitly import/restore a validated historical task record.

        This is the only path for adopting a task ID not already present in the
        store (e.g. transfer import/restore). It preserves legitimate historical
        state (including terminal states and event history) after validation and
        fails closed on invalid/conflicting input. It must not overwrite existing
        canonical task history: existing IDs are rejected as conflicts.
        """
        try:
            source = TaskRecord.from_dict(copy.deepcopy(record)) if isinstance(record, dict) else record
            candidate = self._snapshot(source)
        except Exception as exc:
            raise errors.Conflict(f"invalid import record: {exc}") from exc
        self._validate_import_record(candidate)
        with self._lock:
            existing = self._tasks.get(candidate.task_id)
            if existing is not None:
                raise errors.Conflict(
                    f"import refused: task id already exists in this store: {candidate.task_id}",
                    detail={"task_id": candidate.task_id},
                )
            canonical = self._snapshot(candidate)
            self._tasks[canonical.task_id] = canonical
            self._persist_locked(canonical, reason)
            return self._snapshot(canonical)

    def update(self, record: TaskRecord, reason: str = "update") -> TaskRecord:
        return self.save(record, reason)

    # --- mutation --------------------------------------------------------
    def _fire_after_transition(self, snapshot: TaskRecord, previous_status: str,
                               new_status: str, reason: str) -> None:
        cb = getattr(self, "after_transition", None)
        if cb is None or previous_status == new_status:
            return
        try:
            cb(snapshot, previous_status, new_status, reason)
        except Exception:
            # Must not break committed/durable task transition.
            pass

    def transition(self, task_id: str, status: str, detail: str = "",
                   *, force: bool = False, reason: str = "transition") -> TaskRecord:
        hook = None
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise errors.AjError(f"unknown task {task_id!r}", code="task_not_found")
            previous = record.status
            record.transition(status, detail, force=force)
            self._persist_locked(record, reason)
            snap = self._snapshot(record)
            hook = (snap, previous, record.status, reason)
        if hook is not None:
            self._fire_after_transition(*hook)
        return snap

    def cancel(self, task_id: str) -> bool:
        hook = None
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record.terminal:
                return False
            previous = record.status
            record.transition(CANCELLED, "cancelled")
            self._persist_locked(record, "cancelled")
            snap = self._snapshot(record)
            hook = (snap, previous, CANCELLED, "cancelled")
        if hook is not None:
            self._fire_after_transition(*hook)
        return True

    def apply(self, task_id: str, reason: str = "update", **changes: Any) -> TaskRecord:
        """Apply controlled field updates to the canonical record and persist."""
        protected = {"task_id", "operation_id", "schema_version", "created_at",
                     "status", "events"}
        with self._lock:
            current = self._tasks.get(task_id)
            if current is None:
                raise errors.AjError(f"unknown task {task_id!r}", code="task_not_found")
            data = copy.deepcopy(current.to_dict())
            for key, value in changes.items():
                if key in protected:
                    raise errors.AjError(
                        f"task field {key!r} is store-controlled",
                        code=errors.CALLING_INVALID_STATE,
                    )
                data[key] = copy.deepcopy(value)
            canonical = TaskRecord.from_dict(data)
            self._tasks[task_id] = canonical
            self._persist_locked(canonical, reason)
            return self._snapshot(canonical)

    def mutate(self, task_id: str, reason: str, fn) -> TaskRecord:
        """Run a controlled in-place mutation on the canonical record and persist."""
        with self._lock:
            current = self._tasks.get(task_id)
            if current is None:
                raise errors.AjError(f"unknown task {task_id!r}", code="task_not_found")
            before_status = current.status
            before_events = len(current.events)
            fn(current)
            if current.status != before_status or len(current.events) != before_events:
                # status/events must change only through store lifecycle operations
                raise errors.AjError(
                    f"task {task_id}: lifecycle state changes must use TaskStore.transition/cancel",
                    code=errors.CALLING_INVALID_STATE,
                )
            self._persist_locked(current, reason)
            return self._snapshot(current)

    # --- persistence -----------------------------------------------------
    def _persist(self, record: TaskRecord, reason: str) -> None:
        with self._lock:
            self._persist_locked(record, reason)

    def _persist_locked(self, record: TaskRecord, reason: str) -> None:
        """Append one record snapshot or fail closed.

        Must run under ``self._lock`` so no other thread on this store instance
        can observe/mutate a failed in-memory mutation before reconciliation and
        error propagation complete. Lock order: store ``_lock`` (RLock) then
        cross-process ``file_lock``; re-entrant ``_reload_locked`` is safe.
        """
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps({"reason": reason, "task": record.to_dict()},
                              ensure_ascii=False, default=str)
            with file_lock(str(self._path) + ".lock", exclusive=True,
                           timeout=5.0):
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
                    fh.flush()
        except OSError as exc:
            # Persistence failure must never be treated as successful durable
            # progress. Reconcile in-memory state to the last durably persisted
            # history where possible so callers cannot continue with a healthy-
            # looking but non-durable task state.
            if self._path is not None:
                try:
                    self._reload_locked()
                except Exception:
                    self._tasks.pop(record.task_id, None)
            try:
                self._on_persist_failure(record, reason, exc)
            except Exception:
                # Test/debug hook must never mask the required persistence failure.
                pass
            raise errors.StorageError(
                f"could not persist task record for {record.task_id} ({reason}): {exc}",
                detail={
                    "task_id": record.task_id,
                    "reason": reason,
                    "path": str(self._path),
                },
            ) from exc

    def _on_persist_failure(self, record: TaskRecord, reason: str,
                            exc: OSError) -> None:
        """Test/debug seam invoked under ``self._lock`` after failed-append
        reconciliation/removal and before raising ``StorageError``. Default no-op.
        Exceptions are swallowed by callers so the required persistence failure is
        never masked; blocking or misuse can stall this store instance's lock."""
        return None
