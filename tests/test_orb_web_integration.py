from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from aj.config import load
from aj.inbox import InboxStore, capture_file, capture_text, capture_url, process_capture
from aj.orb_web import map_record_to_item, snapshot_state, web_gui_available


AJ_ROOT = Path(__file__).resolve().parents[1]
VENV_PY = AJ_ROOT / ".venv" / "bin" / "python"


def _run(args, env_extra=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(AJ_ROOT) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(args, cwd=str(AJ_ROOT), env=env, capture_output=True, text=True)


def test_map_record_to_item_statuses_and_fields():
    base = {
        "capture_id": "cap_1",
        "original_filename": "doc.pdf",
        "mime_type": "application/pdf",
        "file_size": 100,
        "captured_at": "2026-11-11T10:00:00+00:00",
        "archived": 0,
        "source_kind": "file",
        "error_details": None,
    }
    assert map_record_to_item({**base, "status": "queued"})["status"] == "queued"
    assert map_record_to_item({**base, "status": "incoming"})["status"] == "queued"
    assert map_record_to_item({**base, "status": "processing"})["status"] == "uploading"
    ready = map_record_to_item({**base, "status": "ready"})
    assert ready["status"] == "completed"
    assert ready["transferredBytes"] == 100
    failed = map_record_to_item({**base, "status": "failed", "error_details": "boom"})
    assert failed["status"] == "error"
    assert failed["errorMessage"] == "boom"
    assert map_record_to_item({**base, "status": "archived"}) is None


def test_snapshot_state_reflects_real_inbox_records():
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        txt = Path(d) / "note.txt"
        txt.write_text("hello world", encoding="utf-8")
        rec = capture_text(store, "hello capture", capture_method="paste")
        rec2 = capture_file(store, txt, capture_method="drag_file")
        process_capture(store, rec["capture_id"])
        process_capture(store, rec2["capture_id"])
        state = snapshot_state(store)
        assert state["connection"] == "connected"
        assert state["storageRoot"] == str(store.root)
        assert state["capabilities"]["retry"] is True
        assert state["capabilities"]["chat"] is False
        assert state["capabilities"]["pause"] is False
        ids = {i["id"] for i in state["items"]}
        assert rec["capture_id"] in ids
        assert rec2["capture_id"] in ids
        assert all(i["status"] in {"queued", "uploading", "completed", "error", "cancelled", "paused"} for i in state["items"])


def test_web_gui_available_and_dist_present():
    ok, reason = web_gui_available()
    # In this development environment the bundle and WebKitGTK are expected;
    # if not, the reason must be explicit rather than crashing.
    if ok:
        assert reason == ""
        assert (AJ_ROOT / "orb_ui" / "dist" / "index.html").is_file()
    else:
        assert isinstance(reason, str) and reason


def test_system_python_orb_reports_web_ui_when_available():
    r = _run(["/usr/bin/python3", "-m", "aj.orb", "--check-gui"])
    if r.returncode != 0:
        # If unavailable, must fail clearly.
        assert r.stderr or r.stdout
        return
    j = json.loads(r.stdout)
    assert j.get("ok") is True
    assert j.get("gtk") is True
    # Web UI is the integrated target on hosts with WebKit2 + bundle.
    if j.get("webkit"):
        assert j.get("ui") == "web"
        assert j.get("dist", "").endswith("orb_ui/dist/index.html")


def test_cli_orb_check_gui_json_shape_preserved():
    r = _run([str(VENV_PY), "-m", "aj", "orb", "--check-gui", "--json"])
    assert r.returncode in (0, 5)
    j = json.loads(r.stdout)
    assert "ok" in j and "gtk" in j and "inbox_root" in j
    assert "ui" in j
