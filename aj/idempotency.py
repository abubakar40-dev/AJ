"""Persistent idempotency keys scoped to a capability.

This is at-most-once *within this local store*: a second submission with the same
scope/key returns the first task instead of executing again. It does not claim
exactly-once semantics for external side effects.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .locking import file_lock


class IdempotencyStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> Dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: Dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(dir=str(self.path.parent),
                                          prefix=self.path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, sort_keys=True, indent=2)
                handle.flush()
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def lookup(self, scope: str, key: str) -> str:
        return str(self._read().get(f"{scope}:{key}", {}).get("task_id", ""))

    @contextmanager
    def claim(self, scope: str, key: str) -> Iterator[Dict[str, Any]]:
        box: Dict[str, Any] = {"task_id": "", "claimed": False}
        with file_lock(str(self.path) + ".lock", timeout=5.0):
            data = self._read()
            existing = data.get(f"{scope}:{key}")
            if existing:
                box["task_id"] = str(existing.get("task_id", ""))
            yield box
            if box.get("claimed") and box.get("task_id"):
                data[f"{scope}:{key}"] = {"task_id": box["task_id"],
                                          "scope": scope}
                self._write(data)

    def all(self) -> Dict[str, Any]:
        return self._read()
