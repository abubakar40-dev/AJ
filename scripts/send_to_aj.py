#!/usr/bin/env python3
"""Send files/URLs/text to AJ Knowledge Inbox (desktop/file-manager helper).

Uses AJ's canonical inbox CLI/config-aware storage resolution so captures go to
the same inbox as AJ/orb. Reports truthful per-item results based on CLI JSON.
Does not print secrets.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def _looks_like_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _as_local_path(s: str):
    if s.startswith("file://"):
        try:
            return Path(unquote(urlparse(s).path))
        except Exception:
            return None
    # Heuristic: absolute or existing relative path treated as file path intent for integrations
    if s.startswith("/") or s.startswith("~"):
        return Path(os.path.expanduser(s))
    p = Path(s)
    # If it exists as a path, treat as path; otherwise only treat as path if it contains separators
    if p.exists():
        return p
    if os.sep in s or (os.altsep and os.altsep in s):
        return p
    return None


def _notify(title, body):
    try:
        subprocess.run(["notify-send", title, body], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def run_capture(aj_root, py, base_args, env, item, args):
    """Return (ok:bool, detail:str)."""
    # Interpret item intent safely for file-manager usage.
    if item is None and args.text is not None:
        cmd = base_args + ["--text", args.text, "--method", args.method]
        label = "text"
    else:
        s = str(item)
        p = _as_local_path(s)
        if p is not None and not _looks_like_url(s):
            if p.is_dir():
                return False, f"folder not supported: {p}"
            if not p.exists():
                return False, f"missing file: {p}"
            if not p.is_file():
                return False, f"not a regular file: {p}"
            cmd = base_args + ["--file", str(p), "--method", args.method]
            label = p.name
        elif _looks_like_url(s):
            cmd = base_args + ["--url", s, "--method", args.method]
            label = "url"
        else:
            # Explicit text payload (not a path/url). File-manager integrations should
            # pass file paths/URIs; avoid silently mis-capturing a bad path as text.
            if args.allow_text_fallback:
                cmd = base_args + ["--text", s, "--method", args.method]
                label = "text"
            else:
                return False, f"not a supported file path or URL: {s}"

    try:
        proc = subprocess.run(cmd, cwd=str(aj_root), env=env, capture_output=True, text=True)
    except Exception as e:
        return False, f"{label}: {type(e).__name__}: {e}"

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, f"{label}: {(err[-1] if err else 'capture failed')}"

    # Parse JSON result for truthful status
    try:
        data = json.loads(proc.stdout or "{}")
        if not data.get("ok", False):
            err = data.get("error") or data.get("message") or "capture failed"
            return False, f"{label}: {err}"
        cap = data.get("capture") or {}
        status = cap.get("status") or ""
        if status in ("failed", "error"):
            return False, f"{label}: {cap.get('error_details') or status}"
        # queued/incoming/ready/processing/processed are accepted durable states
        return True, f"{label}: {status or 'ok'}"
    except Exception:
        # Fallback: CLI exited 0 but output not JSON; treat cautiously
        out = (proc.stdout or "").strip()
        if "Status: failed" in out.lower() or "error" in out.lower():
            return False, f"{label}: capture reported failure"
        return True, f"{label}: captured"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Send items to AJ Knowledge Inbox")
    ap.add_argument("items", nargs="*", help="file paths, file:// URIs, URLs, or text (with --allow-text-fallback)")
    ap.add_argument("--text", default=None, help="capture literal text")
    ap.add_argument("--inbox-root", default="", help="explicit inbox root override")
    ap.add_argument("--method", default="context_menu", help="capture method tag")
    ap.add_argument("--allow-text-fallback", action="store_true", help="treat non-path/non-URL items as text")
    ap.add_argument("--no-notify", action="store_true", help="suppress desktop notification")
    ap.add_argument("--json", action="store_true", help="print JSON summary to stdout")
    args = ap.parse_args(argv)

    aj_root = Path(__file__).resolve().parent.parent
    py = aj_root / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)

    base = [str(py), "-m", "aj", "inbox", "--json"]
    if args.inbox_root:
        base += ["--root", args.inbox_root]
    base += ["capture"]

    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(aj_root) + (":" + pp if pp else "")

    results = []
    if args.text is not None:
        results.append(run_capture(aj_root, py, base, env, None, args))
    elif args.items:
        for it in args.items:
            results.append(run_capture(aj_root, py, base, env, it, args))
    else:
        data = sys.stdin.read()
        if data.strip():
            args.text = data
            results.append(run_capture(aj_root, py, base, env, None, args))
        else:
            msg = "No items provided to send to AJ."
            if args.json:
                print(json.dumps({"ok": False, "captured": 0, "failed": 0, "error": msg}))
            else:
                print(msg, file=sys.stderr)
            return 0

    ok_n = sum(1 for ok, _ in results if ok)
    fail = [d for ok, d in results if not ok]
    for d in fail:
        print(d, file=sys.stderr)

    summary = {
        "ok": len(fail) == 0,
        "captured": ok_n,
        "failed": len(fail),
        "details": [d for _, d in results],
    }
    msg = f"AJ Inbox: {ok_n} captured" + (f", {len(fail)} failed" if fail else "")
    if not args.no_notify:
        _notify("AJ Inbox", msg)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(msg)
    # Exit 0 for file-manager friendliness but truth is in message/json; callers can use --json.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
