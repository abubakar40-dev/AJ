"""CLI integration for AJ Personal Knowledge Inbox."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import errors
from .config import Config
from .inbox import (
    InboxStore, capture_file, capture_text, capture_url,
    process_capture, process_pending, retry_failed, inbox_summary,
)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_NOT_FOUND = 4


def _emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def _store(config: Config, args) -> InboxStore:
    root = getattr(args, "inbox_root", None) or None
    if root:
        return InboxStore(root)
    # canonical config/env/default resolution (no silent mis-rooting)
    return InboxStore(None, config=config)


def _print_item(rec: Dict[str, Any], verbose: bool = False) -> None:
    print(f"{rec.get('capture_id')}  {rec.get('status')}  {rec.get('source_kind')}  {rec.get('source_platform') or '-'}")
    if rec.get('source_url'):
        print(f"  url: {rec['source_url']}")
    if rec.get('original_filename'):
        print(f"  file: {rec['original_filename']}")
    if rec.get('error_details'):
        print(f"  error: {rec['error_details']}")
    if verbose:
        for k in ("content_hash","captured_at","processed_at","extracted_text_path","source_path","duplicate_of"):
            if rec.get(k):
                print(f"  {k}: {rec[k]}")


def add_inbox_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("inbox", help="Personal knowledge inbox (capture, process, inspect)")
    p.add_argument("--root", dest="inbox_root", default="", help="override inbox data root")
    p.add_argument("--json", action="store_true", default=False)
    p.add_argument("--quiet", action="store_true", default=False)
    sp = p.add_subparsers(dest="inbox_cmd")

    cap = sp.add_parser("capture", help="capture a URL, file, or text")
    cap.add_argument("--json", action="store_true", default=False)
    cap.add_argument("--quiet", action="store_true", default=False)
    cap.add_argument("target", nargs="?", default="", help="URL, file path, or '-' for stdin/text")
    cap.add_argument("--text", default="", help="capture literal text")
    cap.add_argument("--file", dest="file_path", default="", help="capture a file by path")
    cap.add_argument("--url", dest="url_value", default="", help="capture a URL")
    cap.add_argument("--method", default="cli", help="capture method tag")
    cap.add_argument("--no-process", action="store_true", help="queue only, do not process now")

    ls = sp.add_parser("list", help="list captures")
    ls.add_argument("--json", action="store_true", default=False)
    ls.add_argument("--quiet", action="store_true", default=False)
    ls.add_argument("--status", default="")
    ls.add_argument("--all", action="store_true", help="include archived")
    ls.add_argument("--limit", type=int, default=50)

    show = sp.add_parser("show", help="show one capture")
    show.add_argument("--json", action="store_true", default=False)
    show.add_argument("--quiet", action="store_true", default=False)
    show.add_argument("capture_id")

    proc = sp.add_parser("process", help="process queued captures or one capture")
    proc.add_argument("--json", action="store_true", default=False)
    proc.add_argument("--quiet", action="store_true", default=False)
    proc.add_argument("capture_id", nargs="?", default="")
    proc.add_argument("--limit", type=int, default=20)

    ret = sp.add_parser("retry", help="retry a failed capture")
    ret.add_argument("--json", action="store_true", default=False)
    ret.add_argument("--quiet", action="store_true", default=False)
    ret.add_argument("capture_id")

    arc = sp.add_parser("archive", help="archive (soft-remove) a capture")
    arc.add_argument("--json", action="store_true", default=False)
    arc.add_argument("--quiet", action="store_true", default=False)
    arc.add_argument("capture_id")

    ann = sp.add_parser("annotate", help="add notes/tags to a capture")
    ann.add_argument("--json", action="store_true", default=False)
    ann.add_argument("--quiet", action="store_true", default=False)
    ann.add_argument("capture_id")
    ann.add_argument("--notes", default=None)
    ann.add_argument("--tags", default="", help="comma-separated tags")

    summ = sp.add_parser("summary", help="show inbox counts and root")
    summ.add_argument("--json", action="store_true", default=False)
    summ.add_argument("--quiet", action="store_true", default=False)

    orb = sp.add_parser("orb", help="launch the floating capture orb (GUI)")
    orb.add_argument("--json", action="store_true", default=False)
    orb.add_argument("--quiet", action="store_true", default=False)

    auto = sp.add_parser("autostart-install", help="install user-session autostart for the orb")
    auto.add_argument("--json", action="store_true", default=False)
    auto.add_argument("--quiet", action="store_true", default=False)
    auto2 = sp.add_parser("autostart-remove", help="remove orb autostart")
    auto2.add_argument("--json", action="store_true", default=False)
    auto2.add_argument("--quiet", action="store_true", default=False)

    view = sp.add_parser("view", help="launch local inbox inspection web UI (localhost)")
    view.add_argument("--host", default="127.0.0.1")
    view.add_argument("--port", type=int, default=8766)
    view.add_argument("--no-open", action="store_true", help="do not auto-open browser")
    view.add_argument("--json", action="store_true", default=False)
    view.add_argument("--quiet", action="store_true", default=False)

    worker = sp.add_parser("worker", help="run inbox background processing loop")
    worker.add_argument("--interval", type=float, default=3.0, help="poll interval seconds")
    worker.add_argument("--once", action="store_true", help="process pending once and exit")
    worker.add_argument("--requeue-stale-seconds", type=int, default=300, help="requeue PROCESSING items older than this")
    worker.add_argument("--json", action="store_true", default=False)
    worker.add_argument("--quiet", action="store_true", default=False)


def cmd_inbox(config: Config, args) -> int:
    store = _store(config, args)
    cmd = getattr(args, "inbox_cmd", None)
    if not cmd:
        cmd = "summary"
    try:
        if cmd == "capture":
            rec = None
            method = getattr(args, "method", "cli")
            if getattr(args, "url_value", ""):
                rec = capture_url(store, args.url_value, capture_method=method)
            elif getattr(args, "file_path", ""):
                rec = capture_file(store, args.file_path, capture_method=method)
            elif getattr(args, "text", ""):
                rec = capture_text(store, args.text, capture_method=method)
            else:
                target = getattr(args, "target", "") or ""
                if target == "-":
                    data = sys.stdin.read()
                    rec = capture_text(store, data, capture_method=method)
                elif target:
                    p = Path(target).expanduser()
                    if p.exists() and p.is_file():
                        rec = capture_file(store, p, capture_method=method)
                    elif target.startswith("http://") or target.startswith("https://"):
                        rec = capture_url(store, target, capture_method=method)
                    else:
                        rec = capture_text(store, target, capture_method=method)
                else:
                    raise errors.AjError("capture needs a URL, file path, --text, --file, --url, or '-' stdin", code=errors.CONFIG_INVALID)
            if not getattr(args, "no_process", False):
                rec = process_capture(store, rec["capture_id"]) or rec
            if getattr(args, "json", False):
                _emit({"ok": True, "capture": rec})
            elif getattr(args, "quiet", False):
                print(f"{rec['capture_id']} {rec['status']}")
            else:
                print(f"Captured: {rec['capture_id']}")
                print(f"Status: {rec['status']}")
                print(f"Kind: {rec.get('source_kind')}  Platform: {rec.get('source_platform')}")
                if rec.get('extracted_text_path'):
                    print(f"Extracted: {rec['extracted_text_path']}")
                if rec.get('error_details'):
                    print(f"Error: {rec['error_details']}")
            return EXIT_OK

        if cmd == "list":
            rows = store.list(status=(getattr(args,'status','') or None),
                              include_archived=bool(getattr(args,'all',False)),
                              limit=getattr(args,'limit',50))
            if getattr(args, "json", False):
                _emit({"ok": True, "captures": rows})
            elif getattr(args, "quiet", False):
                for r in rows:
                    print(f"{r['capture_id']} {r['status']}")
            else:
                if not rows:
                    print("No captures.")
                for r in rows:
                    _print_item(r)
            return EXIT_OK

        if cmd == "show":
            rec = store.get(args.capture_id)
            if not rec:
                raise errors.AjError(f"capture not found: {args.capture_id}", code="task_not_found")
            if getattr(args, "json", False):
                _emit({"ok": True, "capture": rec})
            else:
                _print_item(rec, verbose=True)
                if rec.get('extracted_text_path'):
                    try:
                        txt = Path(rec['extracted_text_path']).read_text(encoding='utf-8', errors='replace')
                        preview = txt[:1200]
                        print("--- extracted preview ---")
                        print(preview + ("..." if len(txt) > len(preview) else ""))
                    except Exception:
                        pass
            return EXIT_OK

        if cmd == "process":
            cid = getattr(args, 'capture_id', '') or ''
            if cid:
                rec = process_capture(store, cid)
                rows = [rec]
            else:
                rows = process_pending(store, limit=getattr(args,'limit',20))
            if getattr(args, "json", False):
                _emit({"ok": True, "processed": rows})
            else:
                if not rows:
                    print("No queued captures.")
                for r in rows:
                    print(f"{r['capture_id']} -> {r['status']}" + (f" ({r.get('error_details')})" if r.get('error_details') else ""))
            return EXIT_OK

        if cmd == "retry":
            rec = retry_failed(store, args.capture_id)
            if getattr(args, "json", False):
                _emit({"ok": True, "capture": rec})
            else:
                print(f"{rec['capture_id']} -> {rec['status']}")
            return EXIT_OK if rec.get('status') in ('ready','processed') else EXIT_FAILURE

        if cmd == "archive":
            rec = store.archive(args.capture_id)
            if not rec:
                raise errors.AjError(f"capture not found: {args.capture_id}", code="task_not_found")
            if getattr(args, "json", False):
                _emit({"ok": True, "capture": rec})
            else:
                print(f"{rec['capture_id']} archived")
            return EXIT_OK

        if cmd == "annotate":
            tags = None
            if getattr(args,'tags',''):
                tags = [t.strip() for t in args.tags.split(',') if t.strip()]
            rec = store.annotate(args.capture_id, notes=getattr(args,'notes',None), tags=tags)
            if not rec:
                raise errors.AjError(f"capture not found: {args.capture_id}", code="task_not_found")
            if getattr(args, "json", False):
                _emit({"ok": True, "capture": rec})
            else:
                print(f"{rec['capture_id']} annotated")
            return EXIT_OK

        if cmd == "summary":
            s = inbox_summary(store)
            if getattr(args, "json", False):
                _emit({"ok": True, "summary": s})
            else:
                print(f"root: {s['root']}")
                print(f"active: {s['active']}")
                for k,v in s['counts'].items():
                    print(f"  {k}: {v}")
            return EXIT_OK

        if cmd == "orb":
            try:
                from .orb import run_orb
                # pass explicit resolved inbox root so orb uses canonical store
                run_orb(inbox_root=str(store.root), config=config)
                return EXIT_OK
            except TypeError:
                # back-compat if signature differs
                try:
                    from .orb import run_orb
                    run_orb(str(store.root))
                    return EXIT_OK
                except Exception as e:
                    raise errors.AjError(f"could not launch orb: {e}", code="inbox_error") from e
            except Exception as e:
                raise errors.AjError(f"could not launch orb: {e}", code="inbox_error") from e

        if cmd == "autostart-install":
            from .orb_autostart import install
            path = install()
            if getattr(args, "json", False):
                _emit({"ok": True, "path": str(path)})
            else:
                print(f"Installed autostart: {path}")
            return EXIT_OK

        if cmd == "autostart-remove":
            from .orb_autostart import remove
            ok = remove()
            if getattr(args, "json", False):
                _emit({"ok": True, "removed": ok})
            else:
                print("Removed autostart" if ok else "No autostart entry found")
            return EXIT_OK

        if cmd == "view":
            import webbrowser
            from .inbox_view import serve
            httpd = serve(store, host=getattr(args, 'host', '127.0.0.1'), port=getattr(args, 'port', 8766))
            url = f"http://{httpd.server_address[0]}:{httpd.server_address[1]}/"
            if getattr(args, 'json', False):
                _emit({"ok": True, "url": url, "root": str(store.root)})
            elif not getattr(args, 'quiet', False):
                print(f"Inbox viewer: {url}")
                print(f"Root: {store.root}")
                print("Press Ctrl+C to stop.")
            if not getattr(args, 'no_open', False):
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                httpd.server_close()
            return EXIT_OK

        if cmd == "worker":
            import time
            from datetime import datetime, timezone
            interval = max(0.5, float(getattr(args, 'interval', 3.0)))
            stale = int(getattr(args, 'requeue_stale_seconds', 300))
            def requeue_stale():
                # recover interrupted PROCESSING items
                now = datetime.now(timezone.utc)
                rows = store.list(status='processing', limit=500)
                n = 0
                for r in rows:
                    ts = r.get('processing_started_at') or r.get('captured_at')
                    try:
                        dt = datetime.fromisoformat(ts.replace('Z','+00:00')) if ts else None
                    except Exception:
                        dt = None
                    age = (now - dt).total_seconds() if dt else 10**9
                    if age >= stale:
                        store.update_status(r['capture_id'], 'queued', error_details='requeued: stale processing/interrupted')
                        n += 1
                return n
            if getattr(args, 'once', False):
                rq = requeue_stale()
                out = process_pending(store, limit=100)
                if getattr(args,'json',False):
                    _emit({"ok": True, "requeued_stale": rq, "processed": out})
                else:
                    print(f"requeued_stale={rq} processed={len(out)}")
                return EXIT_OK
            if not getattr(args,'quiet',False):
                print(f"Inbox worker running (interval={interval}s, stale_requeue={stale}s). Ctrl+C to stop.")
            try:
                while True:
                    requeue_stale()
                    process_pending(store, limit=20)
                    time.sleep(interval)
            except KeyboardInterrupt:
                pass
            return EXIT_OK

        raise errors.AjError(f"unknown inbox command: {cmd}", code=errors.CONFIG_INVALID)
    except errors.AjError:
        raise
    except Exception as e:
        raise errors.AjError(f"inbox command failed: {type(e).__name__}: {e}", code="inbox_error") from e
