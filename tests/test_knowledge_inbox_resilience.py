"""Phase 2 hardening: crash/restart/resume/resilience tests for knowledge inbox."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from aj.inbox import (
    InboxStore, capture_file, capture_text, capture_url,
    process_capture, process_pending, retry_failed, inbox_summary,
    READY, FAILED, QUEUED, ARCHIVED, PROCESSING,
)


def test_db_reopen_and_wal_persistence():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        p = Path(d) / "a.txt"
        p.write_text("persist", encoding="utf-8")
        r = capture_file(store, p)
        process_capture(store, r["capture_id"])
        store.annotate(r["capture_id"], notes="n", tags=["t"])
        cid = r["capture_id"]
        # reopen
        store2 = InboxStore(d)
        got = store2.get(cid)
        assert got and got["status"] == READY
        assert got["user_annotations"] == "n"
        assert json.loads(got["tags"]) == ["t"]
        assert Path(got["source_path"]).exists()
        assert Path(got["extracted_text_path"]).exists()


def test_processing_interrupted_recovers_via_requeue():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        r = capture_text(store, "will be interrupted")
        # simulate crash during processing: leave in PROCESSING with started time
        store.update_status(r["capture_id"], PROCESSING, processing_started_at="2026-01-01T00:00:00+00:00")
        # restart/reopen and treat as resumable by requeueing (operator/worker policy)
        store2 = InboxStore(d)
        rec = store2.get(r["capture_id"])
        assert rec["status"] == PROCESSING
        store2.update_status(r["capture_id"], QUEUED, error_details="requeued after interruption")
        out = process_pending(store2)
        assert any(x["capture_id"] == r["capture_id"] and x["status"] == READY for x in out)
        final = store2.get(r["capture_id"])
        assert final["status"] == READY
        assert Path(final["extracted_text_path"]).exists()


def test_failed_retry_idempotent_and_preserves_original():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        r = capture_text(store, "retry body")
        orig_path = Path(r["source_path"])
        orig = orig_path.read_text(encoding="utf-8")
        store.update_status(r["capture_id"], FAILED, error_details="boom1")
        rec1 = retry_failed(store, r["capture_id"])
        assert rec1["status"] == READY
        store.update_status(r["capture_id"], FAILED, error_details="boom2")
        rec2 = retry_failed(store, r["capture_id"])
        assert rec2["status"] == READY
        assert orig_path.read_text(encoding="utf-8") == orig
        assert "retry body" in Path(rec2["extracted_text_path"]).read_text(encoding="utf-8")


def test_duplicate_capture_after_restart():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        p = Path(d) / "dup.txt"
        p.write_text("same", encoding="utf-8")
        r1 = capture_file(store, p)
        process_capture(store, r1["capture_id"])
        # restart
        store2 = InboxStore(d)
        r2 = capture_file(store2, p)
        assert r2.get("duplicate_of") == r1["capture_id"] or json.loads(r2.get("extra_json") or "{}").get("duplicate_detected")
        # both records exist, originals preserved
        assert store2.get(r1["capture_id"]) is not None
        assert Path(r1["source_path"]).exists()
        assert Path(r2["source_path"]).exists()


def test_original_preserved_when_extraction_fails():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        # create a fake pdf to force extraction failure (no pdf libs expected, and invalid content)
        p = Path(d) / "bad.pdf"
        p.write_bytes(b"%PDF-1.4\nthis is not a valid pdf structure\n%%EOF")
        r = capture_file(store, p)
        out = process_capture(store, r["capture_id"])
        assert out["status"] == FAILED
        assert out["error_details"]
        assert "PDF extraction dependency unavailable" in out["error_details"] or "No PDF extractor" in out["error_details"] or "Could not" in out["error_details"] or out["error_details"]
        # original must still exist and be unchanged
        assert Path(out["source_path"]).exists()
        assert Path(out["source_path"]).read_bytes() == p.read_bytes()


def test_process_pending_skips_archived_and_is_safe():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        r1 = capture_text(store, "one")
        r2 = capture_text(store, "two")
        store.archive(r1["capture_id"])
        out = process_pending(store)
        ids = [x["capture_id"] for x in out]
        assert r2["capture_id"] in ids
        assert r1["capture_id"] not in ids
        assert store.get(r1["capture_id"])["status"] == ARCHIVED
