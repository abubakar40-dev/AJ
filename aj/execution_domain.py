"""First-class Execution domain foundation (Phase 5A.4).

An Execution is one AJ-managed orchestration/execution lifecycle for a Task.
It is distinct from Task (logical work) and Attempt (one concrete try inside an
execution). AJ owns execution identities; external runtime ids remain optional and
are never fabricated.

Persistence is append-only JSONL with fail-closed writes/validation. No cross-
store atomicity or exactly-once guarantees are claimed.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import errors
from .locking import file_lock

SCHEMA_VERSION = 1

# Conservative lifecycle states (only those supportable by current semantics).
CREATED = "CREATED"
READY = "READY"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
UNKNOWN = "UNKNOWN"
RECOVERY_REQUIRED = "RECOVERY_REQUIRED"

TERMINAL = {COMPLETED, FAILED, CANCELLED}

TRANSITIONS: Dict[str, tuple[str, ...]] = {
    CREATED: (READY, RUNNING, FAILED, CANCELLED, UNKNOWN, RECOVERY_REQUIRED),
    READY: (RUNNING, FAILED, CANCELLED, UNKNOWN, RECOVERY_REQUIRED),
    RUNNING: (COMPLETED, FAILED, CANCELLED, UNKNOWN, RECOVERY_REQUIRED),
    COMPLETED: (),
    FAILED: (),
    CANCELLED: (),
    UNKNOWN: (RECOVERY_REQUIRED,),
    RECOVERY_REQUIRED: (READY, RUNNING, FAILED, CANCELLED, UNKNOWN),
}

ALL_STATES = tuple(TRANSITIONS)


@dataclass
class ExecutionRecord:
    execution_id: str
    task_id: str
    operation_id: str = ""
    status: str = CREATED
    correlation_id: str = ""
    agent_id: str = ""
    assignment_id: str = ""
    lease_id: str = ""
    current_attempt_id: str = ""
    attempt_ids: List[str] = field(default_factory=list)
    reason: str = ""
    schema_version: int = SCHEMA_VERSION
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL

    def can_transition(self, status: str) -> bool:
        return status in TRANSITIONS.get(self.status, ())

    def transition(self, status: str, *, detail: str = "", force: bool = False) -> "ExecutionRecord":
        if status == self.status:
            return self
        if status not in ALL_STATES:
            raise errors.AjError(
                f"unknown execution state {status!r}",
                code=errors.CONFIG_INVALID,
                detail={"execution_id": self.execution_id, "to": status},
            )
        if self.terminal and not force:
            raise errors.AjError(
                f"execution {self.execution_id} is terminal ({self.status})",
                code=errors.CALLING_INVALID_STATE,
            )
        if not force and not self.can_transition(status):
            raise errors.AjError(
                f"illegal execution transition {self.status} -> {status}",
                code=errors.CALLING_INVALID_STATE,
                detail={"execution_id": self.execution_id, "from": self.status, "to": status},
            )
        self.status = status
        self.updated_at = time.time()
        if detail:
            self.reason = str(detail)[:500]
        if status in TERMINAL:
            self.completed_at = self.updated_at
        self.events.append({
            "status": status,
            "at": self.updated_at,
            "detail": (detail or "")[:500],
        })
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "status": self.status,
            "correlation_id": self.correlation_id,
            "agent_id": self.agent_id,
            "assignment_id": self.assignment_id,
            "lease_id": self.lease_id,
            "current_attempt_id": self.current_attempt_id,
            "attempt_ids": list(self.attempt_ids),
            "reason": self.reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
            "events": list(self.events),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionRecord":
        known = set(cls.__dataclass_fields__.keys())  # type: ignore[attr-defined]
        values = {k: v for k, v in dict(data).items() if k in known}
        rec = cls(
            execution_id=str(values.get("execution_id") or ""),
            task_id=str(values.get("task_id") or ""),
            operation_id=str(values.get("operation_id") or ""),
            status=str(values.get("status") or CREATED),
            correlation_id=str(values.get("correlation_id") or ""),
            agent_id=str(values.get("agent_id") or ""),
            assignment_id=str(values.get("assignment_id") or ""),
            lease_id=str(values.get("lease_id") or ""),
            current_attempt_id=str(values.get("current_attempt_id") or ""),
            attempt_ids=list(values.get("attempt_ids") or []),
            reason=str(values.get("reason") or ""),
            schema_version=int(values.get("schema_version") or SCHEMA_VERSION),
            created_at=float(values.get("created_at") or time.time()),
            updated_at=float(values.get("updated_at") or time.time()),
            completed_at=values.get("completed_at"),
            metadata=dict(values.get("metadata") or {}),
            events=list(values.get("events") or []),
        )
        return rec


def validate_record(record: ExecutionRecord) -> None:
    if record.schema_version != SCHEMA_VERSION:
        raise errors.AjError("unsupported execution schema", code=errors.CONFIG_INVALID)
    if not record.execution_id or not record.task_id:
        raise errors.AjError("execution requires execution_id and task_id", code=errors.CONFIG_INVALID)
    if record.status not in ALL_STATES:
        raise errors.AjError(f"invalid execution status {record.status!r}", code=errors.CONFIG_INVALID)
    if record.status in TERMINAL and record.completed_at is None:
        raise errors.AjError("terminal execution requires completed_at", code=errors.CONFIG_INVALID)
    if record.status not in TERMINAL and record.completed_at is not None:
        raise errors.AjError("non-terminal execution cannot have completed_at", code=errors.CONFIG_INVALID)
    if not isinstance(record.attempt_ids, list):
        raise errors.AjError("execution attempt_ids must be a list", code=errors.CONFIG_INVALID)


class ExecutionStore:
    """Append-only JSONL persistence for execution records (fail-closed)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, ExecutionRecord] = {}
        self._load()

    @property
    def lock_path(self) -> str:
        return str(self.path) + ".lock"

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            with file_lock(self.lock_path, exclusive=False, timeout=5.0):
                lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as exc:
            raise errors.AjError(f"execution store load failed: {exc}", code=errors.STORAGE_ERROR) from exc
        for idx, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    raise ValueError("record must be an object")
                rec = ExecutionRecord.from_dict(data)
                validate_record(rec)
            except Exception as exc:
                raise errors.AjError(
                    f"execution store malformed at line {idx}: {exc}",
                    code=errors.STORAGE_ERROR,
                ) from exc
            self._records[rec.execution_id] = rec

    def _append(self, record: ExecutionRecord) -> None:
        validate_record(record)
        line = json.dumps(record.to_dict(), ensure_ascii=False, default=str, sort_keys=True)
        try:
            with file_lock(self.lock_path, timeout=5.0):
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
                    handle.flush()
        except errors.AjError:
            raise
        except Exception as exc:
            raise errors.AjError(f"execution persistence failed: {exc}", code=errors.STORAGE_ERROR) from exc

    def create(self, record: ExecutionRecord) -> ExecutionRecord:
        validate_record(record)
        if record.execution_id in self._records:
            raise errors.Conflict(f"execution {record.execution_id} already exists")
        self._append(record)
        self._records[record.execution_id] = record
        return record

    def save(self, record: ExecutionRecord) -> ExecutionRecord:
        validate_record(record)
        if record.execution_id not in self._records:
            raise errors.AjError(
                f"cannot save unknown execution {record.execution_id}",
                code=errors.CALLING_INVALID_STATE,
            )
        self._append(record)
        self._records[record.execution_id] = record
        return record

    def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        return self._records.get(execution_id)

    def list(self, *, task_id: str = "") -> List[ExecutionRecord]:
        out = list(self._records.values())
        if task_id:
            out = [r for r in out if r.task_id == task_id]
        out.sort(key=lambda r: (r.created_at, r.execution_id))
        return out

    def transition(self, execution_id: str, status: str, *, detail: str = "", force: bool = False) -> ExecutionRecord:
        rec = self.get(execution_id)
        if rec is None:
            raise errors.AjError(f"unknown execution {execution_id}", code="task_not_found")
        rec.transition(status, detail=detail, force=force)
        return self.save(rec)
