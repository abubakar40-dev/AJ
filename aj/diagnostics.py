"""Read-only operator diagnostics.

Reports paths, counts, malformed-record counts, last writes, lock state and
configuration origins. Never prints secret values and never mutates storage.
"""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import Any, Dict

from .audit import read_events
from .config import Config, memory_path, require_path
from .locking import lock_status
from .memory import MemoryStore
from .task import TaskStore
from .storage_diagnostics import inspect_storage, sqlite_runtime_info, classify_sqlite_error
from .operation_evidence import OperationEvidenceStore


def _iso(value: float) -> str:
    if not value:
        return ""
    return _dt.datetime.fromtimestamp(float(value)).astimezone().isoformat(
        timespec="seconds"
    )


def _mtime(path: Path) -> str:
    try:
        return _iso(path.stat().st_mtime)
    except OSError:
        return ""


def gather(config: Config) -> Dict[str, Any]:
    data_dir = require_path(config, "core.data_dir")
    tasks_path = data_dir / "tasks.jsonl"
    store = TaskStore(data_dir)
    records = store.all()
    last_task = max(records, key=lambda r: r.updated_at, default=None)

    audit_dir = require_path(config, "core.audit_dir")
    audit = read_events(audit_dir, limit=0)
    last_audit = audit.events[-1] if audit.events else None

    store_path = memory_path(config)
    memory: Dict[str, Any] = {"path": str(store_path), "exists": store_path.is_file()}
    summaries: Dict[str, Any] = {"count": 0, "last": None}
    if store_path.is_file():
        memory_store = MemoryStore(store_path)
        try:
            stats = memory_store.stats()
            memory.update(stats)
            rows = memory_store.summaries(limit=1)
            summaries = {"count": stats.get("summaries", 0),
                         "last": rows[0] if rows else None}
        finally:
            memory_store.close()

    # Phase 3E: operation evidence and SQLite/storage diagnostics (read-only)
    op_path = data_dir / "reconciliation_operations.jsonl"
    op_store = OperationEvidenceStore(op_path)
    op_views = op_store.list_operations()
    incomplete_ops = [v.to_dict() for v in op_views if v.is_incomplete()]
    storage_diag = inspect_storage(config.as_dict() if hasattr(config, "as_dict") else {}, data_dir=data_dir, memory_path=store_path)

    return {
        "storage": {
            "data_dir": str(data_dir),
            "tasks": {"path": str(tasks_path), "exists": tasks_path.is_file(),
                      "bytes": tasks_path.stat().st_size if tasks_path.is_file() else 0,
                      "last_write": _mtime(tasks_path)},
            "audit": {"dir": str(audit_dir), "files": len(audit.files),
                      "last_write": _mtime(Path(audit.files[-1]))
                      if audit.files else ""},
            "memory": memory,
        },
        "tasks": {
            "records": len(records),
            "malformed": len(store.load_errors),
            "errors": store.load_errors[:20],
            "last": {"task_id": last_task.task_id, "status": last_task.status,
                     "updated_at": _iso(last_task.updated_at)}
            if last_task else None,
        },
        "audit": {
            "events": len(audit.events),
            "malformed": audit.malformed,
            "last": {"action": last_audit.get("action", ""),
                     "task_id": last_audit.get("task_id", ""),
                     "at": last_audit.get("at", "")} if last_audit else None,
        },
        "summaries": summaries,
        "locks": {
            "tasks": lock_status(str(tasks_path) + ".lock"),
            "journal": lock_status(str(data_dir / "journal.jsonl.lock")),
            "receipts": lock_status(str(data_dir / "receipts.jsonl.lock")),
            "reconciliation_operations": lock_status(str(op_path) + ".lock"),
        },
        "operation_evidence": {
            "path": str(op_path),
            "operations": len(op_views),
            "incomplete_operations": len(incomplete_ops),
            "incomplete": incomplete_ops[:20],
        },
        "sqlite_storage": storage_diag,
        "configuration": {
            "sources": getattr(config, "sources", {}),
            "sections": sorted(config.as_dict()),
        },
        "platform": {"pid": os.getpid()},
    }
