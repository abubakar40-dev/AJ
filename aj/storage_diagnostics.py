"""Storage and SQLite diagnostics (Phase 3E).

Read-only diagnostics and error classification. Does not move user data, does not
weaken concurrency behavior, and does not silently retry away genuine failures.
"""

from __future__ import annotations

import os
import sqlite3
import stat
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


def _path_info(path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {"path": str(path), "exists": path.exists()}
    try:
        if path.exists():
            st = path.stat()
            info.update({
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "size": st.st_size if path.is_file() else None,
                "mode": oct(stat.S_IMODE(st.st_mode)),
                "mtime": st.st_mtime,
            })
            # mount/device hints (best-effort, Linux)
            try:
                info["dev"] = st.st_dev
            except Exception:
                pass
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def classify_sqlite_error(exc: BaseException) -> Dict[str, Any]:
    msg = str(exc)
    name = type(exc).__name__
    lower = msg.lower()
    cls = "sqlite_error"
    likely = []
    if "disk i/o error" in lower:
        cls = "sqlite_disk_io_error"
        likely = [
            "filesystem does not reliably support SQLite WAL/shared-memory/locking semantics",
            "external/network/removable filesystem or mount with impaired fsync/lock behavior",
            "storage exhaustion or transient device I/O fault",
        ]
    elif "database is locked" in lower or "database is busy" in lower:
        cls = "sqlite_locked"
        likely = ["concurrent writer contention", "busy_timeout too low for workload", "stale lock holder on unreliable fs"]
    elif "readonly" in lower:
        cls = "sqlite_readonly"
        likely = ["path permissions or mount is read-only"]
    elif "unable to open database file" in lower:
        cls = "sqlite_open_failed"
        likely = ["missing directory", "permissions", "invalid path"]
    elif "malformed" in lower or "corrupt" in lower:
        cls = "sqlite_corruption"
        likely = ["database corruption or interrupted non-atomic filesystem behavior"]
    return {
        "type": name,
        "class": cls,
        "message": msg[:500],
        "likely_causes": likely,
    }


def sqlite_runtime_info(db_path: str | Path) -> Dict[str, Any]:
    path = Path(db_path)
    out: Dict[str, Any] = {
        "database": _path_info(path),
        "wal": _path_info(Path(str(path) + "-wal")),
        "shm": _path_info(Path(str(path) + "-shm")),
        "journal_mode": None,
        "busy_timeout": None,
        "synchronous": None,
        "wal_autocheckpoint": None,
        "user_version": None,
        "errors": [],
    }
    if not path.exists():
        return out
    try:
        conn = sqlite3.connect(str(path), timeout=1.0)
        try:
            conn.execute("PRAGMA busy_timeout=1000")
            for key in ("journal_mode", "busy_timeout", "synchronous", "wal_autocheckpoint", "user_version"):
                try:
                    row = conn.execute(f"PRAGMA {key}").fetchone()
                    out[key] = row[0] if row else None
                except Exception as exc:
                    out["errors"].append(f"pragma_{key}:{type(exc).__name__}:{exc}")
        finally:
            conn.close()
    except Exception as exc:
        out["errors"].append(classify_sqlite_error(exc))
    return out


def inspect_storage(config: Optional[Mapping[str, Any]] = None, *, data_dir: str | Path = "", memory_path: str | Path = "") -> Dict[str, Any]:
    """Read-only storage diagnostics for AJ data dir and SQLite memory store."""
    cfg = config or {}
    try:
        # best effort resolve from config-like mapping
        core = cfg.get("core") if isinstance(cfg, dict) else {}
        if not isinstance(core, dict):
            core = {}
    except Exception:
        core = {}
    if not data_dir:
        data_dir = str(core.get("data_dir") or "")
    if not memory_path:
        memory_path = str(core.get("memory_path") or "")
        if not memory_path and data_dir:
            memory_path = str(Path(data_dir) / "memory.sqlite3")

    result: Dict[str, Any] = {
        "ts": time.time(),
        "data_dir": _path_info(Path(data_dir)) if data_dir else None,
        "memory_sqlite": sqlite_runtime_info(memory_path) if memory_path else None,
        "notes": [],
    }
    # Filesystem hints
    try:
        if data_dir:
            st = os.statvfs(str(data_dir))
            result["filesystem"] = {
                "f_bsize": st.f_bsize,
                "f_frsize": getattr(st, "f_frsize", None),
                "f_blocks": st.f_blocks,
                "f_bfree": st.f_bfree,
                "f_bavail": st.f_bavail,
                "f_files": st.f_files,
                "f_ffree": st.f_ffree,
            }
    except Exception as exc:
        result["filesystem_error"] = f"{type(exc).__name__}: {exc}"

    # Known environment caveat from investigation
    result["notes"].append(
        "SQLite WAL with concurrent forked writers requires reliable POSIX file locking/shared-memory semantics; "
        "external/network mounts may intermittently fail with 'disk I/O error' despite passing on local filesystems."
    )
    return result
