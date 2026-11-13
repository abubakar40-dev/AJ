"""F5: canonical memory integrity proofs using isolated temporary stores only."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aj import summary as summary_mod
from aj import transfer
from aj.config import Config
from aj.memory import MemoryStore


def open_store(tmp_path: Path, name: str = "memory.db") -> MemoryStore:
    return MemoryStore(tmp_path / name)


def append_sample(store: MemoryStore, task_id: str = "t1", n: int = 3):
    ids = []
    for i in range(n):
        ev = store.append_event(
            f"step.{i}",
            f"event {i} for {task_id}",
            source="test",
            task_id=task_id,
            meta={"seq": i, "task": task_id},
        )
        ids.append(ev)
    # return Event objects for convenience
    return [e for e in store.events(limit=10000, since=0.0) if e.id in set(ids)]


def event_snapshot(store: MemoryStore):
    rows = store.events(limit=10000, since=0.0)
    return [
        {
            "id": e.id,
            "at": e.at,
            "kind": e.kind,
            "task_id": e.task_id,
            "source": e.source,
            "content": e.content,
            "meta": dict(e.meta),
        }
        for e in rows
    ]


def test_raw_event_preservation_when_summary_generation_fails(tmp_path: Path):
    store = open_store(tmp_path)
    events = append_sample(store, n=4)
    before = event_snapshot(store)
    assert len(before) == 4

    # Derived-layer failure during summary persistence must not mutate raw events.
    orig_add = store.add_summary

    def boom(*a, **k):
        raise RuntimeError("simulated derived summary persistence failure")

    store.add_summary = boom  # type: ignore
    with pytest.raises(RuntimeError):
        summary_mod.build(store)
    store.add_summary = orig_add  # type: ignore

    after = event_snapshot(store)
    assert after == before
    assert store.verify().get("ok") is True
    store.close()


def test_raw_event_preservation_when_search_fails(tmp_path: Path):
    store = open_store(tmp_path)
    append_sample(store, n=3)
    before = event_snapshot(store)

    # Simulate derived/search read-path failure: search raises, raw canonical rows remain.
    orig_search = store.search

    def boom_search(*a, **k):
        raise sqlite3.OperationalError("simulated search/index failure")

    store.search = boom_search  # type: ignore
    with pytest.raises(Exception):
        store.search("event")
    store.search = orig_search  # type: ignore

    after = event_snapshot(store)
    assert after == before
    store.close()


def test_derived_data_isolation_and_rebuild_without_raw_mutation(tmp_path: Path):
    store = open_store(tmp_path)
    events = append_sample(store, n=5)
    before = event_snapshot(store)

    b1 = summary_mod.build(store)
    assert b1["summary_id"] is not None
    assert event_snapshot(store) == before

    b2 = summary_mod.build(store)
    assert b2["summary_id"] is not None
    # Repeated summary generation must not duplicate canonical events.
    assert event_snapshot(store) == before
    assert len(store.events(limit=10000, since=0.0)) == 5

    v = summary_mod.verify(store)
    assert v["ok"] is True
    assert v["rebuilt_content"] == b1["content"]

    # Delete derived summaries only; raw events untouched.
    for s in store.summaries(limit=100):
        deleted = summary_mod.delete(store, int(s["id"]))
        assert deleted is True
    assert store.summaries(limit=100) == []
    assert event_snapshot(store) == before

    b3 = summary_mod.build(store)
    assert b3["summary_id"] is not None
    assert b3["content"] == b1["content"]
    assert event_snapshot(store) == before
    store.close()


def test_summary_provenance_and_citation_integrity(tmp_path: Path):
    store = open_store(tmp_path)
    events = append_sample(store, task_id="task-xyz", n=2)
    before = event_snapshot(store)

    built = summary_mod.build(store)
    assert built["source_event_ids"] == sorted(e.id for e in events)
    summaries = store.summaries(limit=10)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["kind"] == summary_mod.KIND
    src_key = "source_event_ids" if "source_event_ids" in s else "source_events"
    src = s[src_key]
    if isinstance(src, str):
        src = json.loads(src)
    assert sorted(src) == sorted(e.id for e in events)
    assert "created_by" in s
    assert ("created_at" in s) or ("at" in s)

    # Raw events retain supported provenance/metadata.
    for ev in events:
        raw = [r for r in store.events(limit=10000, since=0.0) if r.id == ev.id][0]
        assert raw.source == "test"
        assert raw.task_id == "task-xyz"
        assert raw.meta.get("task") == "task-xyz"

    assert store.verify().get("ok") is True
    assert event_snapshot(store) == before
    store.close()


def test_fresh_process_recovery_of_canonical_events(tmp_path: Path):
    db = tmp_path / "shared.db"
    store = MemoryStore(db)
    events = append_sample(store, task_id="persist", n=3)
    expected = event_snapshot(store)
    store.close()

    code = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from aj.memory import MemoryStore
store = MemoryStore(sys.argv[2])
rows = store.events(limit=10000, since=0.0)
print(json.dumps([
  {"id": e.id, "at": e.at, "kind": e.kind, "task_id": e.task_id,
   "source": e.source, "content": e.content, "meta": dict(e.meta)}
  for e in rows
], sort_keys=True))
store.close()
'''
    proc = subprocess.run(
        [sys.executable, "-c", code, str(ROOT), str(db)],
        capture_output=True, text=True, check=True,
    )
    got = json.loads(proc.stdout.strip())
    assert got == json.loads(json.dumps(expected, sort_keys=True))


def test_corruption_detection_on_isolated_temp_store(tmp_path: Path):
    store = open_store(tmp_path)
    append_sample(store, n=2)
    # A summary citing existing events is verifiable; corrupt citation to detect issue.
    store.add_summary("ok", [1], kind="test")
    assert store.verify().get("ok") is True
    store.close()

    # Controlled corruption in disposable copy only: introduce invalid summary citation.
    import time as _t
    conn = sqlite3.connect(str(tmp_path / "memory.db"))
    conn.execute(
        "INSERT INTO summaries(at, kind, content, source_event_ids, model, created_by) VALUES (?,?,?,?,?,?)",
        (_t.time(), "bad", "bad", json.dumps([999999]), "", "test"),
    )
    conn.commit()
    conn.close()

    store2 = MemoryStore(tmp_path / "memory.db")
    result = store2.verify()
    assert result.get("ok") is False
    problems = result.get("issues") or result.get("problems") or result.get("errors") or []
    textp = json.dumps(result, default=str).lower()
    # corruption must be detected (ok False); details depend on implementation
    assert ("999999" in textp or "missing" in textp or "cite" in textp or "unknown" in textp or "dangl" in textp or problems != [] or result.get("ok") is False)
    store2.close()


def test_backup_and_verify_on_isolated_temp_store(tmp_path: Path):
    # Use existing transfer/backup mechanism on isolated temp config+stores only.
    from aj.config import load as load_config
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(env={}, overrides={
        "core": {"require_verification_before_execute": True,
                 "data_dir": str(data_dir),
                 "memory_path": str(data_dir / "memory.db"),
                 "tasks_path": str(data_dir / "tasks.json"),
                 "journal_path": str(data_dir / "journal.jsonl"),
                 "audit_dir": str(data_dir / "audit")},
        "runtime": {"persist_tasks": True, "persist_memory": True},
    })

    # Populate isolated canonical memory.
    mem_path = Path(str(config.get("core.memory_path")))
    mem_path.parent.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(mem_path)
    append_sample(store, task_id="backup", n=3)
    before = event_snapshot(store)
    store.close()

    backup_dir = tmp_path / "backup_out"
    result = transfer.backup_directory(config, backup_dir)
    assert backup_dir.exists()
    verify = transfer.verify_backup(backup_dir)
    assert verify.get("ok") is True
    assert (verify.get("problems") or []) == []

    # Original isolated store must remain intact and untouched by backup.
    store2 = MemoryStore(mem_path)
    after = event_snapshot(store2)
    assert after == before
    store2.close()
