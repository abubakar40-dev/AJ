"""Local export, import, backup and restore verification.

Design rules
------------
* Export is deterministic JSON with redacted key-like fields.
* Import is conservative: it validates first, refuses id conflicts, never
  deletes, and supports a dry run.
* Backup is a single export file plus a SHA-256 manifest, written atomically.
* Summaries are derived: they are rebuilt after import, not trusted as data.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import errors
from .audit import AuditEvent, JsonlAuditSink, _redact, read_events
from .config import Config, memory_path, require_path
from .memory import MemoryStore
from .summary import build as build_summary
from .task import TaskRecord, TaskStore

FORMAT = "aj-export"
VERSION = 1


def _redact_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _redact(str(k), _redact_object(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_object(v) for v in value]
    return value


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".",
                                     suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False,
                      sort_keys=True, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def collect(config: Config) -> Dict[str, Any]:
    """Gather all local state into one deterministic, redacted document."""
    data_dir = require_path(config, "core.data_dir")
    store = TaskStore(data_dir)
    tasks = sorted((r.to_dict() for r in store.all()), key=lambda t: t["task_id"])

    audit = read_events(require_path(config, "core.audit_dir"), limit=0)

    memory_events: List[Dict[str, Any]] = []
    summaries: List[Dict[str, Any]] = []
    store_path = memory_path(config)
    if store_path.is_file():
        memory_store = MemoryStore(store_path)
        try:
            memory_events = [e.to_dict() for e in reversed(
                memory_store.events(limit=10_000_000))]
            summaries = memory_store.summaries(limit=100_000)
        finally:
            memory_store.close()

    return {
        "format": FORMAT,
        "version": VERSION,
        "created_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tasks": _redact_object(tasks),
        "audit": _redact_object(audit.events),
        "memory": _redact_object(memory_events),
        "summaries": summaries,
        "counts": {
            "tasks": len(tasks),
            "audit": len(audit.events),
            "memory": len(memory_events),
            "summaries": len(summaries),
        },
    }


def validate(data: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(data, dict):
        return ["export is not a JSON object"]
    if data.get("format") != FORMAT:
        problems.append(f"format must be {FORMAT!r}")
    if data.get("version") != VERSION:
        problems.append(f"unsupported version {data.get('version')!r}")
    for key in ("tasks", "audit", "memory", "summaries"):
        if not isinstance(data.get(key), list):
            problems.append(f"{key} must be a list")
    tasks = data.get("tasks") or []
    if isinstance(tasks, list):
        ids = [t.get("task_id") for t in tasks if isinstance(t, dict)]
        if len(ids) != len(set(ids)):
            problems.append("duplicate task ids in export")
        for task in tasks:
            if not isinstance(task, dict) or not task.get("task_id"):
                problems.append("every task needs a task_id")
                break
    return problems


def export_file(config: Config, output: str | Path) -> Dict[str, Any]:
    data = collect(config)
    path = Path(output).expanduser()
    _atomic_write_json(path, data)
    return {"path": str(path), "counts": data["counts"],
            "bytes": path.stat().st_size}


def import_file(config: Config, source: str | Path, *,
                dry_run: bool = False) -> Dict[str, Any]:
    path = Path(source).expanduser()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise errors.StorageError(f"export file not found: {path}") from None
    except ValueError as exc:
        raise errors.StorageError(f"{path}: invalid JSON: {exc}") from exc
    problems = validate(data)
    if problems:
        raise errors.Conflict(f"invalid export: {'; '.join(problems)}")

    data_dir = require_path(config, "core.data_dir")
    store = TaskStore(data_dir)
    existing_ids = {record.task_id for record in store.all()}
    incoming_ids = [task["task_id"] for task in data["tasks"]]
    conflicts = sorted(existing_ids.intersection(incoming_ids))

    store_path = memory_path(config)
    existing_memory: List[Tuple[Any, ...]] = []
    if store_path.is_file():
        memory_store = MemoryStore(store_path)
        try:
            existing_memory = [(e.kind, e.task_id, e.content, e.at, e.source)
                               for e in memory_store.events(limit=10_000_000)]
        finally:
            memory_store.close()
    incoming_memory = [(e.get("kind"), e.get("task_id"), e.get("content"),
                        e.get("at"), e.get("source")) for e in data["memory"]]
    duplicates = sum(1 for item in incoming_memory if item in existing_memory)

    report = {
        "dry_run": dry_run,
        "source": str(path),
        "tasks": len(incoming_ids),
        "audit": len(data["audit"]),
        "memory": len(incoming_memory),
        "memory_duplicates_skipped": duplicates,
        "summaries": len(data["summaries"]),
        "conflicts": conflicts,
    }
    if conflicts:
        raise errors.Conflict(
            "import refused: task ids already exist in this store: "
            + ", ".join(conflicts[:5])
        )
    if dry_run:
        return report

    for task in data["tasks"]:
        store.save(TaskRecord.from_dict(task), "imported")

    sink = JsonlAuditSink(require_path(config, "core.audit_dir"))
    for event in data["audit"]:
        if isinstance(event, dict):
            sink.write(AuditEvent.from_dict(event))

    imported_memory = 0
    if incoming_memory and store_path.parent:
        store_path.parent.mkdir(parents=True, exist_ok=True)
    if incoming_memory:
        memory_store = MemoryStore(store_path)
        try:
            for item in incoming_memory:
                if item in existing_memory:
                    continue
                kind, task_id, content, at, source = item
                memory_store.append_event(str(kind or "imported"),
                                          str(content or ""),
                                          source=str(source or ""),
                                          task_id=str(task_id or ""),
                                          at=float(at) if at else None)
                imported_memory += 1
            build_summary(memory_store)
        finally:
            memory_store.close()

    report["imported_memory"] = imported_memory
    report["summaries_rebuilt"] = 1 if imported_memory or data["memory"] else 0
    return report


def backup_directory(config: Config, directory: str | Path) -> Dict[str, Any]:
    root = Path(directory).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    backup = root / "backup.json"
    exported = export_file(config, backup)
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = {
        "format": FORMAT,
        "version": VERSION,
        "created_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sha256": digest,
        "bytes": exported["bytes"],
        "counts": exported["counts"],
    }
    _atomic_write_json(root / "manifest.json", manifest)
    return {"directory": str(root), "sha256": digest, **exported}


def verify_backup(directory: str | Path) -> Dict[str, Any]:
    root = Path(directory).expanduser()
    manifest_path = root / "manifest.json"
    backup_path = root / "backup.json"
    if not manifest_path.is_file() or not backup_path.is_file():
        raise errors.StorageError(f"no backup manifest/backup.json in {root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    data = json.loads(backup_path.read_text(encoding="utf-8"))
    problems = validate(data)
    ok = digest == manifest.get("sha256") and not problems
    return {"ok": ok, "directory": str(root), "sha256": digest,
            "manifest_sha256": manifest.get("sha256"),
            "problems": problems, "counts": manifest.get("counts")}
