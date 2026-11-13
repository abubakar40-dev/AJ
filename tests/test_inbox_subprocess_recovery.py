import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

AJ_ROOT = Path(__file__).resolve().parents[1]


def _run(args, cwd=None, extra_env=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(AJ_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(args, cwd=str(cwd or AJ_ROOT), env=env, capture_output=True, text=True)


def _jout(proc):
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    return json.loads(proc.stdout)


def test_subprocess_capture_process_and_restart_visibility():
    """Real subprocess boundary: capture/process in one process, inspect in a fresh process."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        p = _run([sys.executable, "-m", "aj", "inbox", "--root", str(root), "capture", "--text", "https://example.com/restart", "--json"], AJ_ROOT)
        cap = _jout(p)["capture"]
        cid = cap["capture_id"]
        assert cap["status"] in ("ready", "queued", "processing")
        p2 = _run([sys.executable, "-m", "aj", "inbox", "--root", str(root), "show", cid, "--json"], AJ_ROOT)
        shown = _jout(p2)["capture"]
        assert shown["capture_id"] == cid
        assert shown["status"] == "ready"
        assert (root / "index" / "inbox.sqlite3").exists()
        assert (root / "originals").exists()
        assert shown.get("extracted_text_path") or shown.get("extracted_meta_path")
