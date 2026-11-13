"""Canonical memory, independent of any provider.

Layers
------
1. ``raw_events``  — append-only. Conversations, task events, observations.
2. ``summaries``   — derived text that *points at* raw events. Never replaces them.
3. retrieval       — a plain substring search over both layers. No embeddings, no
   external service, no provider. Deliberately boring so it cannot rot.

Guarantees
----------
* There is no API that deletes raw events. Summaries can be dropped; evidence
  cannot.
* A summary must cite raw event ids that exist, or it is rejected.
* ``verify()`` re-checks every summary's citations, so a broken link is visible
  rather than assumed.
* Nothing here stores credentials or model state. ``model`` on a summary is a
  provenance label only.

The Obsidian export layer, if used, is a navigation view over this store — it is
not the database. See ``docs/01_AJ_CONTROL_PLANE.md``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, runtime_checkable

_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    source_event_ids TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT 'unknown'
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON raw_events(kind);
CREATE INDEX IF NOT EXISTS idx_events_task ON raw_events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_at ON raw_events(at);
"""


@dataclass(frozen=True)
class Event:
    id: int
    at: float
    kind: str
    source: str
    task_id: str
    content: str
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "at": self.at, "kind": self.kind, "source": self.source,
            "task_id": self.task_id, "content": self.content, "meta": self.meta,
        }


@runtime_checkable
class MemoryPort(Protocol):
    """Provider-independent canonical memory boundary.

    Raw authoritative records (events) and derived records (summaries/index views)
    are separate concerns; implementations must preserve raw events and provenance.
    """

    def append_event(self, kind: str, content: str, *, source: str = "",
                     task_id: str = "", meta: Optional[Mapping[str, Any]] = None,
                     at: Optional[float] = None) -> int: ...

    def events(self, *, kind: str = "", task_id: str = "", limit: int = 100,
               since: float = 0.0) -> List[Any]: ...

    def add_summary(self, kind: str, content: str, source_event_ids: Iterable[int],
                    *, model: str = "", created_by: str = "unknown") -> int: ...

    def summaries(self, *, limit: int = 100) -> List[Dict[str, Any]]: ...

    def search(self, text: str, *, limit: int = 20) -> Dict[str, Any]: ...

    def stats(self) -> Dict[str, Any]: ...

    def verify(self) -> Dict[str, Any]: ...


class MemoryStore:
    """SQLite-backed canonical memory (default local implementation of MemoryPort)."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # WAL + a busy timeout lets independent local processes append without
        # losing events; SQLite serialises writers transactionally.
        self._conn = sqlite3.connect(self.path, timeout=30.0,
                                     check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- raw -------------------------------------------------------------
    def append_event(self, kind: str, content: str, *, source: str = "",
                     task_id: str = "", meta: Optional[Mapping[str, Any]] = None,
                     at: Optional[float] = None) -> int:
        if not (kind or "").strip():
            raise ValueError("an event needs a kind")
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO raw_events(at, kind, source, task_id, content, meta) "
                "VALUES (?,?,?,?,?,?)",
                (float(at or time.time()), kind.strip(), source, task_id, content or "",
                 json.dumps(dict(meta or {}), ensure_ascii=False, default=str)),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def events(self, *, kind: str = "", task_id: str = "", limit: int = 100,
               since: float = 0.0) -> List[Event]:
        query = "SELECT * FROM raw_events WHERE at >= ?"
        args: List[Any] = [float(since)]
        if kind:
            query += " AND kind = ?"
            args.append(kind)
        if task_id:
            query += " AND task_id = ?"
            args.append(task_id)
        query += " ORDER BY id DESC LIMIT ?"
        args.append(int(limit))
        with self._lock:
            rows = self._conn.execute(query, args).fetchall()
        out = []
        for row in rows:
            try:
                meta = json.loads(row["meta"])
            except (ValueError, TypeError):
                meta = {}
            out.append(Event(row["id"], row["at"], row["kind"], row["source"],
                             row["task_id"], row["content"], meta))
        return out

    def count_events(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0])

    # --- summaries -------------------------------------------------------
    def add_summary(self, content: str, source_event_ids: Iterable[int], *,
                    kind: str = "summary", model: str = "",
                    created_by: str = "AJ") -> int:
        ids = sorted({int(i) for i in source_event_ids})
        if not ids:
            raise ValueError("a summary must cite at least one raw event")
        with self._lock:
            placeholders = ",".join("?" for _ in ids)
            found = {row[0] for row in self._conn.execute(
                f"SELECT id FROM raw_events WHERE id IN ({placeholders})", ids)}
            missing = [i for i in ids if i not in found]
            if missing:
                raise ValueError(f"summary cites events that do not exist: {missing}")
            cursor = self._conn.execute(
                "INSERT INTO summaries(at, kind, content, source_event_ids, model, created_by) "
                "VALUES (?,?,?,?,?,?)",
                (time.time(), kind, content or "", json.dumps(ids), model, created_by),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def summaries(self, *, kind: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        query = "SELECT * FROM summaries"
        args: List[Any] = []
        if kind:
            query += " WHERE kind = ?"
            args.append(kind)
        query += " ORDER BY id DESC LIMIT ?"
        args.append(int(limit))
        with self._lock:
            rows = self._conn.execute(query, args).fetchall()
        return [
            {
                "id": row["id"], "at": row["at"], "kind": row["kind"],
                "content": row["content"],
                "source_event_ids": json.loads(row["source_event_ids"]),
                "model": row["model"], "created_by": row["created_by"],
            }
            for row in rows
        ]

    def source_events(self, summary_id: int) -> List[Event]:
        summaries = [s for s in self.summaries(limit=10_000) if s["id"] == int(summary_id)]
        if not summaries:
            raise KeyError(f"unknown summary {summary_id}")
        ids = summaries[0]["source_event_ids"]
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM raw_events WHERE id IN ({','.join('?' for _ in ids)})", ids
            ).fetchall()
        return [
            Event(r["id"], r["at"], r["kind"], r["source"], r["task_id"], r["content"],
                  json.loads(r["meta"] or "{}"))
            for r in rows
        ]

    # --- retrieval -------------------------------------------------------
    def search(self, query: str, *, limit: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        needle = f"%{(query or '').strip()}%"
        if needle == "%%":
            return {"events": [], "summaries": []}
        with self._lock:
            events = self._conn.execute(
                "SELECT * FROM raw_events WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (needle, int(limit)),
            ).fetchall()
            summaries = self._conn.execute(
                "SELECT * FROM summaries WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (needle, int(limit)),
            ).fetchall()
        return {
            "events": [
                {"id": r["id"], "at": r["at"], "kind": r["kind"], "content": r["content"]}
                for r in events
            ],
            "summaries": [
                {"id": r["id"], "at": r["at"], "content": r["content"],
                 "source_event_ids": json.loads(r["source_event_ids"])}
                for r in summaries
            ],
        }

    # --- integrity -------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            events = int(self._conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0])
            summaries = int(self._conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0])
        return {"path": self.path, "raw_events": events, "summaries": summaries}

    def verify(self) -> Dict[str, Any]:
        """Check every summary citation still resolves to a raw event."""
        broken: List[Dict[str, Any]] = []
        for summary in self.summaries(limit=100_000):
            ids = summary["source_event_ids"]
            with self._lock:
                found = {row[0] for row in self._conn.execute(
                    f"SELECT id FROM raw_events WHERE id IN ({','.join('?' for _ in ids)})",
                    ids)}
            missing = [i for i in ids if i not in found]
            if missing:
                broken.append({"summary_id": summary["id"], "missing": missing})
        return {"ok": not broken, "summaries": len(self.summaries(limit=100_000)),
                "broken": broken}
