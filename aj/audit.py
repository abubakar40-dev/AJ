"""Audit trail.

One JSON object per line, appended, never rewritten. Fields follow the approved
audit requirement: timestamp, actor, agent, task id, capability, requested
action, permission level, authorization, execution result, error, external side
effect.

Rules
-----
* Never write a secret. Key names matching the redaction hints have their value
  replaced; other values are truncated so a pasted document cannot flood the log.
* Never let a logging failure break the action; the failure is reported on stderr
  and the caller continues.
* Files are created 0600 inside the user's data directory, one per month.
* Sinks are pluggable so tests use memory and production uses disk.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol

from . import errors
from .locking import file_lock

DEFAULT_AUDIT_DIR = Path(os.path.expanduser("~")) / ".local" / "share" / "aj" / "audit"
_NULL_PATH_TEXT = {"none", "null"}


def _validate_audit_directory(directory: str | Path) -> Path:
    if directory is None:
        raise errors.ConfigError("core.audit_dir must be a path string, not null")
    if isinstance(directory, bool):
        raise errors.ConfigError("core.audit_dir must be a path string, not a boolean")
    if not isinstance(directory, (str, Path)):
        raise errors.ConfigError(
            f"core.audit_dir must be a path string, not {type(directory).__name__}")
    text = str(directory).strip()
    if not text:
        raise errors.ConfigError("core.audit_dir must be a non-empty path")
    if text.lower() in _NULL_PATH_TEXT:
        raise errors.ConfigError(
            f"core.audit_dir must be a filesystem path, not {text!r}")
    return Path(text).expanduser()

SECRET_HINTS = (
    "token", "password", "passwd", "secret", "api_key", "apikey", "authorization",
    "cookie", "session", "credential", "wstoken", "private_key", "key",
)
MAX_VALUE_CHARS = 300


def _redact(key: str, value: Any) -> Any:
    lowered = (key or "").lower()
    if any(hint in lowered for hint in SECRET_HINTS):
        return "[redacted]"
    if isinstance(value, str):
        return value if len(value) <= MAX_VALUE_CHARS else value[:MAX_VALUE_CHARS] + "…"
    if isinstance(value, Mapping):
        return {str(k): _redact(str(k), v) for k, v in list(value.items())[:40]}
    if isinstance(value, (list, tuple)):
        return [_redact("", v) for v in list(value)[:20]]
    return value


@dataclass(frozen=True)
class AuditEvent:
    """One recorded action or decision."""

    action: str
    actor: str = "user"
    agent: str = "AJ"
    task_id: str = ""
    operation_id: str = ""
    attempt_id: str = ""
    capability: str = ""
    permission_level: int = 0
    authorization: str = ""
    result: str = ""
    error: str = ""
    external_side_effect: bool = False
    detail: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "at": self.at or _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "actor": self.actor,
            "agent": self.agent,
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "attempt_id": self.attempt_id,
            "capability": self.capability,
            "action": self.action,
            "permission_level": self.permission_level,
            "authorization": self.authorization,
            "result": self.result,
            "error": self.error,
            "external_side_effect": self.external_side_effect,
            "detail": self.detail[:500] if isinstance(self.detail, str) else "",
            "params": {str(k): _redact(str(k), v) for k, v in (self.params or {}).items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


class AuditSink(Protocol):
    def write(self, event: AuditEvent) -> None:  # pragma: no cover - protocol
        ...


class MemoryAuditSink:
    """In-memory sink for tests and for dry runs."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def write(self, event: AuditEvent) -> None:
        self.events.append(event.to_dict())


class JsonlAuditSink:
    """Append-only monthly JSONL files, mode 0600."""

    def __init__(self, directory: str | Path = DEFAULT_AUDIT_DIR, clock=None):
        self.directory = _validate_audit_directory(directory)
        self._clock = clock or _dt.datetime.now

    def path_for_now(self) -> Path:
        return self.directory / f"events-{self._clock().strftime('%Y-%m')}.jsonl"

    def write(self, event: AuditEvent) -> None:
        path = self.path_for_now()
        if path.name == "events-.jsonl":
            raise errors.ConfigError(f"core.audit_dir resolved to invalid path {path.parent!s}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(str(path) + ".lock", exclusive=True, timeout=5.0):
            fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False,
                                        default=str) + "\n")
                handle.flush()


@dataclass(frozen=True)
class AuditRecordResult:
    event: Optional[AuditEvent]
    persisted: bool
    error: str = ""
    mandatory: bool = False


class AuditLog:
    """Facade the rest of the control plane calls."""

    def __init__(self, sink: Optional[AuditSink] = None):
        self.sink: AuditSink = sink or JsonlAuditSink()
        self._recent: List[Dict[str, Any]] = []

    def record(
        self,
        action: str,
        *,
        actor: str = "user",
        agent: str = "AJ",
        task_id: str = "",
        operation_id: str = "",
        attempt_id: str = "",
        capability: str = "",
        permission_level: int = 0,
        authorization: str = "",
        result: str = "",
        error: str = "",
        external_side_effect: bool = False,
        detail: str = "",
        params: Optional[Mapping[str, Any]] = None,
        mandatory: bool = False,
    ) -> AuditEvent:
        event = AuditEvent(
            action=action, actor=actor, agent=agent, task_id=task_id,
            operation_id=operation_id, attempt_id=attempt_id,
            capability=capability, permission_level=int(permission_level),
            authorization=authorization, result=result, error=error,
            external_side_effect=external_side_effect, detail=detail,
            params=dict(params or {}),
        )
        try:
            self.sink.write(event)
        except Exception as exc:
            if mandatory:
                raise
            print(f"[aj.audit] could not write audit entry: {exc}", file=sys.stderr)
            failure = {"action": action, "persisted": False, "error": str(exc),
                       "task_id": task_id, "capability": capability}
            self._recent.append(failure)
            if len(self._recent) > 200:
                del self._recent[:-200]
            return event
        self._recent.append(event.to_dict())
        if len(self._recent) > 200:
            del self._recent[:-200]
        return event

    def try_record(self, *args, mandatory: bool = False, **kwargs) -> AuditRecordResult:
        try:
            event = self.record(*args, mandatory=mandatory, **kwargs)
            return AuditRecordResult(event=event, persisted=True, mandatory=mandatory)
        except Exception as exc:
            return AuditRecordResult(event=None, persisted=False, error=str(exc), mandatory=mandatory)

    def recent(self) -> List[Dict[str, Any]]:
        return list(self._recent)


def read_jsonl(path: str | Path, limit: int = 50) -> List[Dict[str, Any]]:
    """Read the most recent entries from an audit file (debug helper)."""
    path = Path(path)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    out: List[Dict[str, Any]] = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


@dataclass(frozen=True)
class AuditReadResult:
    """Read-only view over persisted audit files."""

    events: List[Dict[str, Any]]
    files: List[str]
    malformed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"events": self.events, "files": self.files,
                "malformed": self.malformed}


def read_events(directory: str | Path = DEFAULT_AUDIT_DIR, *, limit: int = 50,
                task_id: str = "", action: str = "",
                agent: str = "") -> AuditReadResult:
    """Read persisted audit events without modifying them.

    Malformed lines are counted, never rewritten or dropped from the file.
    Results stay in file order; ``limit`` keeps the most recent matches.
    """
    root = _validate_audit_directory(directory)
    files = sorted(root.glob("events-*.jsonl")) if root.is_dir() else []
    collected: List[Dict[str, Any]] = []
    malformed = 0
    for path in files:
        try:
            with file_lock(str(path) + ".lock", exclusive=False, timeout=5.0):
                lines = path.read_text(encoding="utf-8",
                                       errors="replace").splitlines()
        except OSError:
            malformed += 1
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                malformed += 1
                continue
            if not isinstance(event, dict):
                malformed += 1
                continue
            if task_id and event.get("task_id") != task_id:
                continue
            if action and event.get("action") != action:
                continue
            if agent and str(event.get("agent", "")).upper() != agent.upper():
                continue
            collected.append(event)
    if limit and limit > 0:
        collected = collected[-limit:]
    return AuditReadResult(collected, [str(p) for p in files], malformed)


def iter_events(events: Iterable[AuditEvent]) -> List[str]:
    """Serialise events, useful for export and tests."""
    return [json.dumps(e.to_dict(), ensure_ascii=False, default=str) for e in events]
