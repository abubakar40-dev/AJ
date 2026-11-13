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
        return cls(**values)


class TaskStore:
    """Thread-safe task records with optional append-only persistence.

    Persistence is one JSON object per line, appended on every change. That is
    enough to reconstruct history for audit and to survive a crash mid-task,
    without introducing a database for the control plane.
    """

    def __init__(self, persist_dir: Optional[str | Path] = None):
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = threading.RLock()
        self._path: Optional[Path] = None
        self.load_errors: List[Dict[str, Any]] = []
        if persist_dir:
            self._path = Path(persist_dir) / "tasks.jsonl"
            self.reload()

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
        self._persist(record, "created")
        return record

    def child_of(self, parent: TaskRecord, goal: str, **kw: Any) -> TaskRecord:
        kw.setdefault("requester", parent.requester)
        return self.create(
            goal,
            parent_task_id=parent.task_id,
            task_id=ids.new_child_id(parent.task_id),
            **kw,
        )

    # --- access ----------------------------------------------------------
    def get(self, task_id: str) -> TaskRecord:
        with self._lock:
            record = self._tasks.get(task_id)
        if record is None:
            raise errors.AjError(f"unknown task {task_id!r}", code="task_not_found")
        return record

    def find(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def all(self) -> List[TaskRecord]:
        with self._lock:
            return [self._tasks[k] for k in sorted(self._tasks)]

    def active(self) -> List[TaskRecord]:
        return [t for t in self.all() if not t.terminal]

    def query(self, *, status: str = "", limit: int = 0,
              newest_first: bool = True) -> List[TaskRecord]:
        """Deterministic listing with optional status filter and limit."""
        records = self.all()
        if status:
            records = [r for r in records if r.status == status.upper()]
        if newest_first:
            records = list(reversed(records))
        if limit and limit > 0:
            records = records[:limit]
        return records

    # --- persistence -----------------------------------------------------
    def reload(self) -> Dict[str, Any]:
        """Rebuild in-memory state from the append-only file.

        The file is never rewritten. Malformed lines are reported in
        ``load_errors`` and skipped, so one bad record cannot hide the rest or
        cause history to be discarded.
        """
        self.load_errors = []
        loaded: Dict[str, TaskRecord] = {}
        lines = 0
        if self._path is not None and self._path.is_file():
            try:
                with file_lock(str(self._path) + ".lock", exclusive=False,
                               timeout=5.0):
                    raw_lines = self._path.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
            except OSError as exc:
                self.load_errors.append(
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
                    self.load_errors.append(
                        {"line": number, "error": f"{type(exc).__name__}: {exc}"}
                    )
                    continue
                if record.status not in TRANSITIONS:
                    self.load_errors.append(
                        {"line": number,
                         "error": f"unknown task status {record.status!r}"}
                    )
                    continue
                loaded[record.task_id] = record
        with self._lock:
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
        """Upsert one record and append it to the log."""
        with self._lock:
            self._tasks[record.task_id] = record
        self._persist(record, reason)
        return record

    def update(self, record: TaskRecord, reason: str = "update") -> TaskRecord:
        return self.save(record, reason)

    # --- mutation --------------------------------------------------------
    def transition(self, task_id: str, status: str, detail: str = "") -> TaskRecord:
        record = self.get(task_id)
        with self._lock:
            record.transition(status, detail)
        self._persist(record, "transition")
        return record

    def cancel(self, task_id: str) -> bool:
        record = self.find(task_id)
        if record is None or record.terminal:
            return False
        with self._lock:
            record.transition(CANCELLED, "cancelled")
        self._persist(record, "cancelled")
        return True

    # --- persistence -----------------------------------------------------
    def _persist(self, record: TaskRecord, reason: str) -> None:
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
        except OSError as exc:  # persistence must never break a task
            record.note(f"could not persist task record: {exc}")
