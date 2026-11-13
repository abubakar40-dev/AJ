"""Deterministic derived summaries over canonical raw events.

A summary is *derived*: it is computed from raw events, cites their ids, and can
be deleted and rebuilt to the same bytes. It never modifies, replaces or deletes
canonical history.

No model, provider or clock participates in the computation. Given the same raw
events, the content is identical.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Mapping, Optional

from .memory import Event, MemoryStore

KIND = "task_digest"


def _event_dict(event: Event) -> Dict[str, Any]:
    return {
        "id": event.id,
        "at": event.at,
        "kind": event.kind,
        "task_id": event.task_id,
        "source": event.source,
        "content": event.content,
        "meta": dict(event.meta),
    }


def digest(events: List[Event]) -> Dict[str, Any]:
    """Build the summary payload from raw events, deterministically."""
    ordered = sorted(events, key=lambda e: e.id)
    by_kind: Counter = Counter(e.kind for e in ordered)
    tasks: Dict[str, Dict[str, Any]] = {}
    capabilities = set()
    for event in ordered:
        if event.task_id:
            entry = tasks.setdefault(event.task_id, {
                "events": 0, "last_kind": "", "status": "", "capability": "",
            })
            entry["events"] += 1
            entry["last_kind"] = event.kind
            status = event.meta.get("status")
            if isinstance(status, str) and status:
                entry["status"] = status
            capability = event.meta.get("capability")
            if isinstance(capability, str) and capability:
                entry["capability"] = capability
                capabilities.add(capability)
    return {
        "event_count": len(ordered),
        "task_count": len(tasks),
        "by_kind": dict(sorted(by_kind.items())),
        "tasks": {task_id: tasks[task_id] for task_id in sorted(tasks)},
        "capabilities": sorted(capabilities),
        "first_event_id": ordered[0].id if ordered else 0,
        "last_event_id": ordered[-1].id if ordered else 0,
    }


def effective_kind(kind: str, task_id: str) -> str:
    return f"{kind}:{task_id}" if task_id else kind


def build(memory: MemoryStore, *, kind: str = KIND,
          limit: int = 100_000, task_id: str = "") -> Dict[str, Any]:
    """Compute and store one derived summary, citing every contributing event."""
    events = memory.events(limit=limit, since=0.0, task_id=task_id)
    payload = digest(events)
    content = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
    ids = sorted(event.id for event in events)
    scope = effective_kind(kind, task_id)
    summary_id: Optional[int] = None
    if ids:
        summary_id = memory.add_summary(content, ids, kind=scope,
                                        created_by="aj.summary")
    return {
        "summary_id": summary_id,
        "kind": scope,
        "task_id": task_id,
        "content": content,
        "payload": payload,
        "source_event_ids": ids,
    }


def verify(memory: MemoryStore, *, kind: str = KIND, task_id: str = "",
           limit: int = 100_000) -> Dict[str, Any]:
    """Compare a fresh deterministic rebuild with the latest stored summary."""
    events = memory.events(limit=limit, since=0.0, task_id=task_id)
    content = json.dumps(digest(events), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False)
    scope = effective_kind(kind, task_id)
    stored = memory.summaries(kind=scope, limit=1)
    stored_content = stored[0]["content"] if stored else None
    return {
        "ok": stored_content == content,
        "kind": scope,
        "task_id": task_id,
        "stored_content": stored_content,
        "rebuilt_content": content,
        "summary_id": stored[0]["id"] if stored else None,
    }


def delete(memory: MemoryStore, summary_id: int) -> bool:
    """Delete one derived summary. Raw events are untouched by construction."""
    with memory._lock:  # the store exposes no delete API for canonical rows
        cursor = memory._conn.execute("DELETE FROM summaries WHERE id = ?",
                                      (int(summary_id),))
        memory._conn.commit()
        return cursor.rowcount > 0


def summaries(memory: MemoryStore, *, kind: str = "", limit: int = 100) -> List[Mapping[str, Any]]:
    return memory.summaries(kind=kind, limit=limit)
