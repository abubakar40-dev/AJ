"""Canonical memory tests: raw records survive, summaries cite them, no deletion."""

from __future__ import annotations

import pytest

from aj.memory import MemoryStore


@pytest.fixture()
def store(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    yield store
    store.close()


def test_raw_events_are_append_only_and_queryable(store):
    first = store.append_event("conversation", "hello there", source="jarvis",
                               task_id="t1")
    second = store.append_event("task", "did a thing")
    assert (first, second) == (1, 2)
    assert store.count_events() == 2
    assert [e.content for e in store.events(limit=1)] == ["did a thing"]
    assert [e.id for e in store.events(kind="conversation")] == [first]


def test_summary_must_cite_existing_raw_events(store):
    event_id = store.append_event("conversation", "we discussed the plan")
    with pytest.raises(ValueError):
        store.add_summary("a summary with no sources", [])
    with pytest.raises(ValueError):
        store.add_summary("a summary pointing nowhere", [event_id + 99])
    summary_id = store.add_summary("plan discussed", [event_id], model="any-model")
    assert store.summaries()[0]["id"] == summary_id


def test_summary_never_replaces_the_raw_record(store):
    event_id = store.append_event("conversation", "the original words")
    store.add_summary("condensed", [event_id])
    assert store.count_events() == 1
    assert store.source_events(1)[0].content == "the original words"


def test_verify_reports_broken_citations_instead_of_hiding_them(store):
    event_id = store.append_event("conversation", "x")
    store.add_summary("y", [event_id])
    assert store.verify()["ok"] is True
    # Simulate external corruption, which the API cannot do by design.
    store._conn.execute("DELETE FROM raw_events WHERE id = ?", (event_id,))
    store._conn.commit()
    report = store.verify()
    assert report["ok"] is False and report["broken"][0]["missing"] == [event_id]


def test_search_spans_both_layers(store):
    event_id = store.append_event("conversation", "the alpha project decision")
    store.add_summary("alpha decision recorded", [event_id])
    hits = store.search("alpha")
    assert len(hits["events"]) == 1 and len(hits["summaries"]) == 1
    assert store.search("   ")["events"] == []


def test_memory_survives_reopen(tmp_path):
    path = tmp_path / "m.sqlite3"
    first = MemoryStore(path)
    first.append_event("conversation", "persisted", task_id="t9")
    first.add_summary("kept", [1])
    first.close()

    second = MemoryStore(path)
    assert second.count_events() == 1
    assert second.summaries()[0]["source_event_ids"] == [1]
    assert second.stats()["raw_events"] == 1
    second.close()
