"""Durable execution receipts, one per finished attempt."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import errors, ids
from .audit import _redact
from .locking import file_lock

SCHEMA_VERSION = 1


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _redact(str(k), _safe(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value[:20]]
    return _redact("", value)


class ReceiptStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, task_id: str, operation_id: str, attempt_id: str,
               worker_id: str, lease_id: str, capability_id: str,
               status: str, started_at: float, completed_at: Optional[float] = None,
               verification: str = "", output: Any = None,
               error: Optional[Mapping[str, Any]] = None,
               journal_event_ids: Optional[List[str]] = None,
               metadata: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        receipt = {
            "receipt_id": ids.new_task_id("rcpt"),
            "task_id": task_id,
            "operation_id": operation_id,
            "attempt_id": attempt_id,
            "worker_id": worker_id,
            "lease_id": lease_id,
            "capability_id": capability_id,
            "started_at": started_at,
            "completed_at": completed_at or time.time(),
            "execution_status": status,
            "verification_status": verification,
            "result": _safe(output),
            "error": _safe(dict(error or {})) or None,
            "journal_event_ids": list(journal_event_ids or []),
            "idempotency_key": "",
            "schema_version": SCHEMA_VERSION,
        }
        if metadata:
            receipt["metadata"] = _safe(dict(metadata))
        line = json.dumps(receipt, ensure_ascii=False, default=str)
        with file_lock(str(self.path) + ".lock", timeout=5.0):
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        return receipt

    def _read(self) -> List[Dict[str, Any]]:
        if not self.path.is_file():
            return []
        with file_lock(str(self.path) + ".lock", exclusive=False, timeout=5.0):
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for line in lines:
            if not line.strip():
                continue
            try:
                receipt = json.loads(line)
            except ValueError:
                continue
            if int(receipt.get("schema_version", 0)) > SCHEMA_VERSION:
                raise errors.StorageError("receipts have a newer schema version")
            out.append(receipt)
        return out

    def get(self, receipt_id: str) -> Optional[Dict[str, Any]]:
        for receipt in self._read():
            if receipt.get("receipt_id") == receipt_id:
                return receipt
        return None

    def list(self, *, task_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        rows = [r for r in self._read() if not task_id or r.get("task_id") == task_id]
        return rows[-limit:] if limit and limit > 0 else rows

    def count(self) -> int:
        return len(self._read())
