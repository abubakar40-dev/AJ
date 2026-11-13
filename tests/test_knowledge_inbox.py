"""Phase 2: AJ Personal Knowledge Inbox tests."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from aj.inbox import (
    InboxStore, capture_file, capture_text, capture_url,
    process_capture, process_pending, retry_failed, inbox_summary,
    READY, FAILED, QUEUED, ARCHIVED,
)


def test_capture_and_process_text_and_url_and_file():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        # URL capture
        r = capture_url(store, "https://example.com/path?q=1", capture_method="cli")
        assert r["status"] == QUEUED
        assert r["source_kind"] == "url"
        assert r["source_platform"] in ("example.com", "unknown") or r["source_platform"]
        out = process_capture(store, r["capture_id"])
        assert out["status"] in (READY, FAILED)  # network may fail, but state transition must be consistent
        assert out["processed_at"] is not None
        assert out["extracted_text_path"]
        assert Path(out["extracted_text_path"]).exists()

        # file capture
        p = Path(d) / "notes.txt"
        p.write_text("hello inbox\n", encoding="utf-8")
        rf = capture_file(store, p, capture_method="drag_file")
        assert rf["status"] == QUEUED
        outf = process_capture(store, rf["capture_id"])
        assert outf["status"] == READY
        assert "hello inbox" in Path(outf["extracted_text_path"]).read_text(encoding="utf-8")

        # text capture
        rt = capture_text(store, "some important note", capture_method="paste")
        assert rt["source_kind"] == "text"
        outt = process_capture(store, rt["capture_id"])
        assert outt["status"] == READY

        s = inbox_summary(store)
        assert s["active"] >= 3
        assert s["counts"]["ready"] >= 2


def test_duplicate_detection_and_archive_and_retry():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        p = Path(d) / "a.txt"
        p.write_text("dup content", encoding="utf-8")
        r1 = capture_file(store, p)
        r2 = capture_file(store, p)
        assert r2.get("duplicate_of") == r1["capture_id"] or json.loads(r2.get("extra_json") or "{}").get("duplicate_detected")

        # force failure scenario: process a pdf-like missing extractor? easier: manually mark failed then retry
        rt = capture_text(store, "retry me")
        store.update_status(rt["capture_id"], FAILED, error_details="boom")
        rec = retry_failed(store, rt["capture_id"])
        assert rec["status"] == READY
        assert rec["error_details"] is None

        arc = store.archive(rt["capture_id"])
        assert arc["status"] == ARCHIVED
        assert arc["archived"] == 1
        listed = store.list(include_archived=False)
        assert all(x["capture_id"] != rt["capture_id"] for x in listed)


def test_annotations_and_persistence():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        r = capture_text(store, "annotate me")
        process_capture(store, r["capture_id"])
        store.annotate(r["capture_id"], notes="my note", tags=["a", "b"])
        # reopen store
        store2 = InboxStore(d)
        got = store2.get(r["capture_id"])
        assert got is not None
        assert got["user_annotations"] == "my note"
        assert json.loads(got["tags"]) == ["a", "b"]
        assert got["status"] == READY
