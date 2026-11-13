"""Append-only execution journal.

The journal is the ordered "what happened" stream: acceptance, scheduling,
lease, execution, result, verification, retry, recovery. It deliberately stores
no large payloads; task records remain the state authority and memory remains
canonical event content.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import errors, ids
from .audit import _redact
from .locking import file_lock

SCHEMA_VERSION = 1
MAX_METADATA_CHARS = 2000


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, *, task_id: str,
               operation_id: str = "", attempt_id: str = "",
               worker_id: str = "", lease_id: str = "",
               correlation_id: str = "",
               metadata: Optional[Mapping[str, Any]] = None) -> str:
        event_id = ids.new_task_id("evt")
        event = {
            "event_id": event_id,
            "event_type": event_type.upper(),
            "task_id": task_id,
            "operation_id": operation_id,
            "attempt_id": attempt_id,
            "worker_id": worker_id,
            "lease_id": lease_id,
            "correlation_id": correlation_id or operation_id or task_id,
            "timestamp": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "schema_version": SCHEMA_VERSION,
            "metadata": {str(k): _redact(str(k), v)
                         for k, v in (metadata or {}).items()},
        }
        line = json.dumps(event, ensure_ascii=False, default=str)
        if len(line) > MAX_METADATA_CHARS + 1000:
            event["metadata"] = {"truncated": True}
            line = json.dumps(event, ensure_ascii=False, default=str)
        with file_lock(str(self.path) + ".lock", timeout=5.0):
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        return event_id

    def events(self, *, task_id: str = "", event_type: str = "",
               attempt_id: str = "", operation_id: str = "",
               limit: int = 100) -> List[Dict[str, Any]]:
        if not self.path.is_file():
            return []
        with file_lock(str(self.path) + ".lock", exclusive=False, timeout=5.0):
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        out: List[Dict[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if int(event.get("schema_version", 0)) > SCHEMA_VERSION:
                raise errors.StorageError("journal has a newer schema version")
            if task_id and event.get("task_id") != task_id:
                continue
            if event_type and event.get("event_type") != event_type.upper():
                continue
            if attempt_id and event.get("attempt_id") != attempt_id:
                continue
            if operation_id and event.get("operation_id") != operation_id:
                continue
            out.append(event)
        if limit and limit > 0:
            out = out[-limit:]
        return out

    def count(self) -> int:
        return len(self.events(limit=0))

    def malformed(self) -> int:
        if not self.path.is_file():
            return 0
        bad = 0
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                json.loads(line)
            except ValueError:
                bad += 1
        return bad
