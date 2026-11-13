"""AJ Orb web host (WebKitGTK 4.1 + GTK3).

Embeds the vendored React UI (``orb_ui/dist/index.html``) and bridges it to the
canonical AJ knowledge inbox. The Python host owns storage, capture, processing,
windowing and OS integration; the UI is a pure presentation layer.

Runs on the system interpreter that provides PyGObject/GTK3/WebKit2 (4.1).
Import-safe when WebKitGTK is unavailable so ``aj orb --check-gui`` / tests can
import the module without the GUI stack.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

GTK_AVAILABLE = False
WEBKIT_AVAILABLE = False
GTK_IMPORT_ERROR: Optional[BaseException] = None

try:  # pragma: no cover - host GUI dependency
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gdk, GLib, Gtk, WebKit2  # type: ignore

    GTK_AVAILABLE = True
    WEBKIT_AVAILABLE = True
except Exception as e:  # pragma: no cover
    GTK_IMPORT_ERROR = e
    Gtk = Gdk = GLib = WebKit2 = None  # type: ignore

try:  # pragma: no cover
    import cairo  # type: ignore
except Exception:  # pragma: no cover
    cairo = None  # type: ignore

_HAS_NOTIFY = False
if GTK_AVAILABLE:  # pragma: no cover - optional
    try:
        gi.require_version("Notify", "0.7")
        from gi.repository import Notify  # type: ignore

        Notify.init("AJ Orb")
        _HAS_NOTIFY = True
    except Exception:
        Notify = None  # type: ignore
        _HAS_NOTIFY = False

from .config import load as load_config
from .inbox import (
    ARCHIVED,
    FAILED,
    INCOMING,
    PROCESSED,
    PROCESSING,
    QUEUED,
    READY,
    InboxStore,
    capture_file,
    capture_text,
    capture_url,
    inbox_summary,
    process_capture,
    process_pending,
    resolve_inbox_root,
    retry_failed,
)

STATE_FILE_NAME = "orb_state.json"
DEFAULT_ORB_SIZE = 104
REGION_PAD = 8
SNAPSHOT_LIMIT = 80


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def dist_index_path() -> Path:
    return Path(__file__).resolve().parent.parent / "orb_ui" / "dist" / "index.html"


def web_gui_available() -> Tuple[bool, str]:
    if not (GTK_AVAILABLE and WEBKIT_AVAILABLE):
        return False, f"GTK/WebKit2 unavailable: {GTK_IMPORT_ERROR}"
    if cairo is None:
        return False, "pycairo unavailable (required for transparent input regions)"
    dist = dist_index_path()
    if not dist.is_file():
        return False, f"Orb UI bundle missing: {dist}"
    return True, ""


def _parse_ts(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        # seconds or ms
        v = float(value)
        return int(v * 1000) if v < 10_000_000_000 else int(v)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return 0
        try:
            # fromisoformat handles "+00:00"
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return int(datetime.strptime(s, fmt).timestamp() * 1000)
                except Exception:
                    pass
    return 0


def _display_name(rec: Dict[str, Any]) -> str:
    name = rec.get("original_filename") or ""
    if name:
        return str(name)
    kind = rec.get("source_kind")
    if kind == "url":
        url = str(rec.get("source_url") or rec.get("canonical_ref") or "Link")
        try:
            p = urlparse(url)
            host = p.hostname or ""
            path = (p.path or "").rstrip("/")
            tail = path.split("/")[-1] if path else ""
            label = "/".join([x for x in (host, tail) if x])
            return label or url
        except Exception:
            return url
    if kind == "text":
        return "Text capture"
    return str(rec.get("capture_id") or "Capture")


def map_record_to_item(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    status_raw = str(rec.get("status") or "")
    if int(rec.get("archived") or 0) or status_raw == ARCHIVED:
        return None
    if status_raw in (INCOMING, QUEUED):
        status = "queued"
    elif status_raw == PROCESSING:
        status = "uploading"
    elif status_raw in (READY, PROCESSED):
        status = "completed"
    elif status_raw == FAILED:
        status = "error"
    else:
        status = "queued"

    size = rec.get("file_size")
    try:
        size_bytes = int(size) if size is not None else None
    except Exception:
        size_bytes = None
    if size_bytes is not None and size_bytes < 0:
        size_bytes = None
    transferred = size_bytes if (status == "completed" and size_bytes is not None) else 0
    added = _parse_ts(rec.get("captured_at")) or int(time.time() * 1000)

    item: Dict[str, Any] = {
        "id": str(rec.get("capture_id") or ""),
        "name": _display_name(rec),
        "mimeType": rec.get("mime_type") or "",
        "sizeBytes": size_bytes,
        "transferredBytes": transferred,
        "status": status,
        "addedAt": added,
    }
    err = rec.get("error_details")
    if err and status == "error":
        item["errorMessage"] = str(err)[:300]
    return item


def snapshot_state(store: InboxStore, connection: str = "connected", error: str = "") -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    try:
        records = store.list(include_archived=False, limit=SNAPSHOT_LIMIT)
        for rec in records:
            item = map_record_to_item(rec)
            if item:
                items.append(item)
        items.sort(key=lambda x: int(x.get("addedAt") or 0), reverse=True)
        conn = connection
        conn_label = "Connected"
        storage_error = ""
    except Exception as e:
        conn = "disconnected"
        conn_label = "Storage unavailable"
        storage_error = f"{type(e).__name__}: {e}"[:240]
        if error:
            storage_error = storage_error or error
    if error and not storage_error:
        storage_error = error

    # Count-based label is truthful and useful for the compact UI.
    try:
        summary = inbox_summary(store) if conn != "disconnected" else {"counts": {}}
        counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
        ready = int(counts.get(READY, 0)) + int(counts.get(PROCESSED, 0))
        queued = int(counts.get(QUEUED, 0)) + int(counts.get(INCOMING, 0))
        proc = int(counts.get(PROCESSING, 0))
        failed = int(counts.get(FAILED, 0))
        if conn == "connected":
            conn_label = f"Ready {ready} · Queued {queued} · Processing {proc} · Failed {failed}"
    except Exception:
        pass

    return {
        "items": items,
        "connection": conn,
        "connectionLabel": conn_label,
        "capabilities": {
            "pause": False,
            "cancel": False,
            "retry": True,
            "chat": False,
            "clipboard": True,
        },
        "storageRoot": str(store.root),
        "storageError": storage_error,
    }


def notify(title: str, body: str, urgency: str = "low") -> None:
    if not _HAS_NOTIFY:
        return
    try:  # pragma: no cover - desktop side effect
        n = Notify.Notification.new(title, body, "dialog-information")
        if hasattr(Notify, "Urgency"):
            u = {
                "low": Notify.Urgency.LOW,
                "normal": Notify.Urgency.NORMAL,
                "critical": Notify.Urgency.CRITICAL,
            }.get(urgency, Notify.Urgency.LOW)
            n.set_urgency(u)
        n.set_timeout(3500)
        n.show()
    except Exception:
        pass


def _open_path(path: str) -> Tuple[bool, str]:
    try:
        subprocess.Popen(["xdg-open", path])
        return True, ""
    except Exception as e:
        return False, str(e)


def _uri_to_path(uri: str) -> Optional[str]:
    uri = (uri or "").strip()
    if not uri:
        return None
    try:
        parsed = urlparse(uri)
    except Exception:
        return None
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return None


def _state_path(store: InboxStore) -> Path:
    return store.paths["index"] / STATE_FILE_NAME


def load_orb_state(store: InboxStore) -> Dict[str, Any]:
    p = _state_path(store)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"x": 48, "y": 96, "paused": False}


def save_orb_state(store: InboxStore, state: Dict[str, Any]) -> None:
    p = _state_path(store)
    tmp = p.with_suffix(".tmp")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def _clamp_position(x: int, y: int, w: int = DEFAULT_ORB_SIZE, h: int = DEFAULT_ORB_SIZE) -> Tuple[int, int]:
    if not GTK_AVAILABLE:
        return max(0, int(x)), max(0, int(y))
    try:
        display = Gdk.Display.get_default()
        if not display:
            return max(0, int(x)), max(0, int(y))
        monitor = None
        try:
            seat = display.get_default_seat()
            pointer = seat.get_pointer() if seat else None
            if pointer:
                _, px, py = pointer.get_position()
                monitor = display.get_monitor_at_point(px, py)
        except Exception:
            monitor = None
        if monitor is None:
            try:
                monitor = display.get_primary_monitor()
            except Exception:
                monitor = None
        if monitor is None and hasattr(display, "get_n_monitors") and display.get_n_monitors() > 0:
            monitor = display.get_monitor(0)
        if monitor is None:
            return max(0, int(x)), max(0, int(y))
        geom = monitor.get_geometry()
        gx, gy, gw, gh = int(geom.x), int(geom.y), int(geom.width), int(geom.height)
        return (
            min(max(int(x), gx + 4), gx + max(4, gw - w - 4)),
            min(max(int(y), gy + 4), gy + max(4, gh - h - 4)),
        )
    except Exception:
        return max(0, int(x)), max(0, int(y))


class OrbInstanceLock:
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.fd: Optional[int] = None
        self.acquired = False

    def try_acquire(self) -> bool:
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
            try:
                import fcntl

                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            except Exception:
                pass
            try:
                os.ftruncate(self.fd, 0)
                os.write(self.fd, str(os.getpid()).encode("utf-8", errors="replace"))
            except Exception:
                pass
            self.acquired = True
            return True
        except Exception:
            return True

    def release(self) -> None:
        if self.fd is None:
            return
        try:
            import fcntl

            fcntl.flock(self.fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(self.fd)
        except Exception:
            pass
        self.fd = None
        self.acquired = False


# ---------------------------------------------------------------------------
# Web host
# ---------------------------------------------------------------------------


@dataclass
class PendingDrop:
    drop_id: str
    uris: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    text: Optional[str] = None
    files_meta: List[Dict[str, Any]] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    intent: str = "add-file"


if GTK_AVAILABLE and WEBKIT_AVAILABLE:

    class OrbWebWindow(Gtk.Window):
        def __init__(self, store: InboxStore, debug: bool = False):
            super().__init__(title="AJ Orb")
            self.store = store
            self.debug = debug
            self.state = load_orb_state(store)
            self._shutdown_done = False
            self._ui_ready = False
            self._pending_drops: Dict[str, PendingDrop] = {}
            self._state_lock = threading.RLock()
            self._q: "queue.Queue[Callable[[], None]]" = queue.Queue()
            self._worker_stop = threading.Event()
            self._refresh_pending = threading.Event()
            self._win_pos = (int(self.state.get("x", 48) or 48), int(self.state.get("y", 96) or 96))
            self._logical_regions: List[Tuple[int, int, int, int]] = []
            self._fullscreen_size: Optional[Tuple[int, int]] = None

            self.set_decorated(False)
            self.set_resizable(False)
            self.set_keep_above(True)
            self.set_skip_taskbar_hint(True)
            self.set_skip_pager_hint(True)
            self.set_app_paintable(True)
            self.set_can_focus(True)
            try:
                self.stick()
            except Exception:
                pass
            try:
                self.set_type_hint(Gdk.WindowTypeHint.DOCK)
            except Exception:
                try:
                    self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
                except Exception:
                    pass

            screen = self.get_screen()
            if screen is not None:
                visual = screen.get_rgba_visual()
                if visual is not None:
                    self.set_visual(visual)

            self._configure_fullscreen_overlay()

            self.webview = WebKit2.WebView()
            self._configure_webview(self.webview)

            self.add(self.webview)
            self.connect("delete-event", self.on_delete)
            self.connect("destroy", self.on_destroy)
            self.connect("configure-event", self._on_configure)

            self._init_dnd()

            dist = dist_index_path().resolve()
            uri = dist.as_uri()
            self.webview.load_uri(uri)

            self.worker = threading.Thread(target=self._worker_loop, daemon=True, name="aj-orb-web-worker")
            self.worker.start()

        # ----- logging -----
        def _log(self, msg: str) -> None:
            if self.debug:
                try:
                    print(f"[aj-orb-web] {msg}", file=sys.stderr)
                except Exception:
                    pass

        # ----- window / overlay -----
        def _configure_fullscreen_overlay(self) -> None:
            # Fullscreen transparent overlay lets the web UI control its own
            # position/shape inside the window while GTK receives input and DnD.
            try:
                self.fullscreen()
            except Exception:
                pass
            w, h = 1920, 1080
            try:
                display = Gdk.Display.get_default()
                monitor = display.get_primary_monitor() if display else None
                if monitor is None and display and display.get_n_monitors() > 0:
                    monitor = display.get_monitor(0)
                if monitor is not None:
                    geom = monitor.get_geometry()
                    w, h = int(geom.width), int(geom.height)
            except Exception:
                pass
            self._fullscreen_size = (w, h)
            self.set_default_size(w, h)

        def _on_configure(self, *_args):
            # Keep position clamped to the current monitor.
            self._save_position_from_state()
            return False

        # ----- webview / bridge -----
        def _configure_webview(self, webview) -> None:
            try:
                rgba = Gdk.RGBA(0, 0, 0, 0)
                webview.set_background_color(rgba)
            except Exception:
                pass
            try:
                settings = webview.get_settings()
                if settings:
                    settings.set_enable_javascript(True)
                    settings.set_enable_webgl(True)
                    settings.set_allow_file_access_from_file_urls(False)
                    settings.set_allow_universal_access_from_file_urls(False)
                    settings.set_javascript_can_access_clipboard(True)
                    settings.set_javascript_can_open_windows_automatically(False)
                    settings.set_enable_developer_extras(bool(self.debug))
            except Exception:
                pass
            try:
                ucm = webview.get_user_content_manager()
                ucm.register_script_message_handler("aj")
                ucm.connect("script-message-received::aj", self._on_script_message)
            except Exception as e:
                self._log(f"message handler error: {e}")

        def _on_script_message(self, _manager, js_result):
            try:
                val = js_result.get_js_value()
                # WebKit2 4.1 + GTK3: JSValue API
                try:
                    msg = json.loads(val.to_string())
                except Exception:
                    # fallback via JSCValue-like .to_json if present
                    if hasattr(val, "to_json"):
                        msg = json.loads(val.to_json(0))
                    else:
                        msg = None
            except Exception as e:
                self._log(f"bad bridge message: {e}")
                return
            if not isinstance(msg, dict):
                return
            self._handle_ui_message(msg)

        def _run_js(self, script: str) -> None:
            try:
                self.webview.run_javascript(script, None, None, None)
            except Exception as e:
                self._log(f"run_javascript failed: {e}")

        def _push_state(self, patch: Optional[Dict[str, Any]] = None) -> None:
            try:
                state = snapshot_state(self.store)
                if patch:
                    state.update(patch)
                js = f"window.__AJ_SET_STATE && window.__AJ_SET_STATE({json.dumps(state, ensure_ascii=False)});"
                self._run_js(js)
            except Exception as e:
                self._log(f"push_state failed: {e}")

        def _toast(self, kind: str, title: str, body: str = "") -> None:
            payload = {"kind": kind, "title": title, "body": body}
            js = f"window.__AJ_TOAST && window.__AJ_TOAST({json.dumps(payload, ensure_ascii=False)});"
            self._run_js(js)

        # ----- drag and drop -----
        def _init_dnd(self) -> None:
            try:
                targets = Gtk.TargetList.new([])
                targets.add_uri_targets(1)
                targets.add_text_targets(2)
                self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
                self.drag_dest_set_target_list(targets)
            except Exception as e:
                self._log(f"dnd init failed: {e}")
            self.connect("drag-motion", self._on_drag_motion)
            self.connect("drag-leave", self._on_drag_leave)
            self.connect("drag-data-received", self._on_drag_data)

        def _extract_drop_data(self, data) -> Tuple[List[str], List[str], List[str], Optional[str], List[Dict[str, Any]], List[str]]:
            uris: List[str] = []
            paths: List[str] = []
            urls: List[str] = []
            text: Optional[str] = None
            files_meta: List[Dict[str, Any]] = []
            unsupported: List[str] = []
            try:
                uris = list(data.get_uris() or [])
            except Exception:
                uris = []
            try:
                text = data.get_text() or None
            except Exception:
                text = None
            if not uris and text:
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                if any(ln.startswith(("file://", "http://", "https://")) for ln in lines):
                    uris = [ln for ln in lines if ln.startswith(("file://", "http://", "https://"))]
                    # keep remaining as text only if non-empty and non-uri
            for uri in uris:
                parsed = urlparse(uri)
                if parsed.scheme == "file":
                    p = unquote(parsed.path)
                    try:
                        pp = Path(p)
                        if pp.exists() and pp.is_file():
                            paths.append(str(pp))
                            try:
                                files_meta.append({"name": pp.name, "size": pp.stat().st_size, "mime": ""})
                            except Exception:
                                files_meta.append({"name": pp.name, "size": 0, "mime": ""})
                        elif pp.exists() and pp.is_dir():
                            unsupported.append(f"{pp.name} (folder not supported)")
                        else:
                            unsupported.append(p)
                    except Exception:
                        unsupported.append(p)
                elif parsed.scheme in ("http", "https"):
                    urls.append(uri)
                else:
                    unsupported.append(uri)
            # plain dropped text (non-URL)
            if text and not urls and not paths and not uris:
                pass
            elif uris and text:
                # if text is just the URI list, don't treat as note
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                if all(ln in uris for ln in lines):
                    text = None
            return uris, paths, urls, text, files_meta, unsupported

        def _on_drag_motion(self, _w, _ctx, x, y, time_):
            try:
                Gdk.drag_status(_ctx, Gdk.DragAction.COPY, time_)
            except Exception:
                pass
            # Tell UI where the pointer is in logical (CSS-like) coordinates.
            try:
                types = []  # best-effort; target list not easily introspected here
                js = f"window.__AJ_DRAG_MOVE && window.__AJ_DRAG_MOVE({int(x)}, {int(y)}, {json.dumps(types)});"
                self._run_js(js)
            except Exception:
                pass
            return True

        def _on_drag_leave(self, *_a):
            self._run_js("window.__AJ_DRAG_LEAVE && window.__AJ_DRAG_LEAVE();")

        def _on_drag_data(self, _w, _ctx, x, y, data, _info, time_):
            uris, paths, urls, text, files_meta, unsupported = self._extract_drop_data(data)
            drop_id = "d_" + uuid.uuid4().hex[:12]
            pd = PendingDrop(
                drop_id=drop_id,
                uris=uris,
                paths=paths,
                urls=urls,
                text=text,
                files_meta=files_meta,
                unsupported=unsupported,
            )
            self._pending_drops[drop_id] = pd
            payload = {
                "dropId": drop_id,
                "uris": uris,
                "text": text,
                "files": files_meta,
                "intent": None,
            }
            js = f"window.__AJ_EXTERNAL_DROP && window.__AJ_EXTERNAL_DROP({json.dumps(payload, ensure_ascii=False)});"
            self._run_js(js)
            for msg in unsupported[:3]:
                self._toast("warning", "Some items were skipped", msg)
            try:
                Gtk.drag_finish(_ctx, True, False, time_)
            except Exception:
                pass

        # ----- UI messages -----
        def _handle_ui_message(self, msg: Dict[str, Any]) -> None:
            mtype = str(msg.get("type") or "")
            self._log(f"ui msg: {mtype}")
            if mtype == "ready":
                self._ui_ready = True
                # Push initial state/position
                init = snapshot_state(self.store)
                state_js = json.dumps(init, ensure_ascii=False)
                pos = {"x": self._win_pos[0], "y": self._win_pos[1]}
                pos_js = json.dumps(pos)
                self._run_js(
                    f"window.__AJ_INITIAL_POSITION__={pos_js};"
                    f"window.__AJ_INITIAL_STATE__={state_js};"
                    f"window.__AJ_SET_STATE && window.__AJ_SET_STATE({state_js});"
                )
                self._refresh_pending.set()
                return
            if mtype == "regions":
                self._apply_regions(msg.get("regions") or [])
                return
            if mtype == "position":
                self._set_orb_position(msg.get("x"), msg.get("y"))
                return
            if mtype == "submitDrop":
                self._enqueue("submit_drop", msg)
                return
            if mtype == "captureText":
                self._enqueue("capture_text", msg)
                return
            if mtype == "pick":
                GLib.idle_add(self._open_picker, str(msg.get("intent") or "add-file"))
                return
            if mtype == "paste":
                GLib.idle_add(self._paste_clipboard)
                return
            if mtype == "retry":
                self._enqueue("retry", msg)
                return
            if mtype == "clearFinished":
                # UI hides locally; backend state remains truthful (archive is a
                # different action). Nothing to do.
                return
            if mtype == "openInbox":
                GLib.idle_add(self._open_inbox_viewer)
                return
            if mtype == "openStorage":
                GLib.idle_add(self._open_storage)
                return
            if mtype == "quit":
                GLib.idle_add(self.destroy)
                return
            if mtype == "log":
                self._log(f"ui[{msg.get('level')}]: {msg.get('message')}")
                return

        def _enqueue(self, kind: str, payload: Dict[str, Any]) -> None:
            self._q.put(lambda k=kind, p=payload: self._handle_job(k, p))

        # ----- regions / input shape -----
        def _apply_regions(self, regions: Any) -> None:
            rects: List[Tuple[int, int, int, int]] = []
            if isinstance(regions, list):
                for r in regions:
                    if not isinstance(r, dict):
                        continue
                    try:
                        x = int(float(r.get("x", 0))) - REGION_PAD
                        y = int(float(r.get("y", 0))) - REGION_PAD
                        w = int(float(r.get("w", 0))) + REGION_PAD * 2
                        h = int(float(r.get("h", 0))) + REGION_PAD * 2
                        if w > 0 and h > 0:
                            rects.append((max(0, x), max(0, y), w, h))
                    except Exception:
                        continue
            self._logical_regions = rects
            self._apply_input_shape(rects)

        def _apply_input_shape(self, rects: List[Tuple[int, int, int, int]]) -> None:
            # Combine clickable regions; pass None to make whole window clickable
            # if anything goes wrong (better than trapping the desktop).
            try:
                gwin = self.get_window()
                if gwin is None:
                    return
                if not rects:
                    # keep a small safe area near stored orb position
                    ox, oy = self._win_pos
                    rects = [(max(0, ox), max(0, oy), DEFAULT_ORB_SIZE + 40, DEFAULT_ORB_SIZE + 40)]
                if cairo is not None and hasattr(cairo, "Region") and hasattr(cairo, "RectangleInt"):
                    region = cairo.Region(cairo.RectangleInt(0, 0, 0, 0))
                    region = cairo.Region()  # empty
                    for (x, y, w, h) in rects:
                        try:
                            region.union(cairo.RectangleInt(int(x), int(y), int(w), int(h)))
                        except Exception:
                            pass
                    gwin.input_shape_combine_region(region, 0, 0)
                else:
                    gwin.input_shape_combine_region(None, 0, 0)
            except Exception as e:
                self._log(f"input shape failed: {e}")
                try:
                    gwin = self.get_window()
                    if gwin is not None:
                        gwin.input_shape_combine_region(None, 0, 0)
                except Exception:
                    pass

        # ----- position persistence -----
        def _set_orb_position(self, x: Any, y: Any) -> None:
            try:
                ix = int(float(x))
                iy = int(float(y))
            except Exception:
                return
            ix, iy = _clamp_position(ix, iy)
            self._win_pos = (ix, iy)
            self.state["x"], self.state["y"] = ix, iy
            save_orb_state(self.store, self.state)

        def _save_position_from_state(self) -> None:
            # Overlay is fullscreen; logical orb position is authoritative.
            save_orb_state(self.store, self.state)

        # ----- actions -----
        def _open_storage(self):
            ok, err = _open_path(str(self.store.root))
            if not ok:
                GLib.idle_add(self._toast, "error", "Could not open storage folder", str(err))
            return False

        def _open_inbox_viewer(self):
            try:
                aj_root = Path(__file__).resolve().parent.parent
                py = sys.executable
                env = os.environ.copy()
                existing_pp = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = str(aj_root) + (os.pathsep + existing_pp if existing_pp else "")
                cmd = [py, "-m", "aj", "inbox", "--root", str(self.store.root), "view"]
                subprocess.Popen(cmd, cwd=str(aj_root), env=env)
                GLib.idle_add(self._toast, "info", "Opening inbox viewer", "")
            except Exception as e:
                GLib.idle_add(self._toast, "error", "Could not open inbox viewer", str(e))
            return False

        def _open_picker(self, intent: str):
            try:
                dlg = Gtk.FileChooserDialog(
                    title="Add to AJ Inbox",
                    parent=self,
                    action=Gtk.FileChooserAction.OPEN,
                )
                dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
                dlg.set_select_multiple(True)
                dlg.set_local_only(True)
                resp = dlg.run()
                files = dlg.get_filenames() if resp == Gtk.ResponseType.OK else []
                dlg.destroy()
            except Exception as e:
                self._toast("error", "File chooser unavailable", str(e))
                return False
            for f in files:
                self._enqueue("capture_path", {"path": f, "intent": intent, "method": "drag_file"})
            return False

        def _paste_clipboard(self):
            try:
                cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            except Exception as e:
                self._toast("error", "Clipboard unavailable", str(e))
                return False
            # URIs first
            try:
                sel = cb.wait_for_contents(Gdk.Atom.intern("text/uri-list", False))
                if sel:
                    uris = list(sel.get_uris() or [])
                    for uri in uris:
                        parsed = urlparse(uri)
                        if parsed.scheme == "file":
                            self._enqueue("capture_path", {"path": unquote(parsed.path), "intent": "paste-clipboard", "method": "paste"})
                        elif parsed.scheme in ("http", "https"):
                            self._enqueue("capture_url", {"url": uri, "intent": "paste-clipboard", "method": "paste"})
                    if uris:
                        return False
            except Exception:
                pass
            try:
                text = cb.wait_for_text()
            except Exception:
                text = None
            if text and str(text).strip():
                self._enqueue("capture_text", {"text": text, "intent": "paste-clipboard", "method": "paste"})
            else:
                self._toast("warning", "Nothing to paste", "Clipboard is empty or unsupported.")
            return False

        # ----- worker -----
        def _worker_loop(self) -> None:
            # Periodic refresh keeps UI honest even if files change externally.
            last_refresh = 0.0
            while not self._worker_stop.is_set():
                if self._refresh_pending.is_set():
                    self._refresh_pending.clear()
                    self._idle_push()
                try:
                    job = self._q.get(timeout=0.4)
                except queue.Empty:
                    job = None
                if job is not None:
                    try:
                        job()
                    except Exception as e:
                        GLib.idle_add(self._toast, "error", "Orb action failed", f"{type(e).__name__}: {e}")
                    finally:
                        try:
                            self._q.task_done()
                        except Exception:
                            pass
                now = time.time()
                if now - last_refresh >= 2.5:
                    last_refresh = now
                    self._idle_push()

        def _idle_push(self) -> None:
            GLib.idle_add(self._push_state, None)

        def _handle_job(self, kind: str, msg: Dict[str, Any]) -> None:
            try:
                if kind == "submit_drop":
                    drop_id = str(msg.get("dropId") or "")
                    intent = str(msg.get("intent") or "add-file")
                    pd = self._pending_drops.pop(drop_id, None)
                    if pd is None:
                        GLib.idle_add(self._toast, "error", "Drop expired", "Please drop the items again.")
                        return
                    self._capture_drop(pd, intent=intent)
                elif kind == "capture_path":
                    self._capture_path(str(msg.get("path") or ""), method=str(msg.get("method") or "drag_file"))
                elif kind == "capture_url":
                    self._capture_url(str(msg.get("url") or ""), method=str(msg.get("method") or "drag_url"))
                elif kind == "capture_text":
                    self._capture_text(str(msg.get("text") or ""), method=str(msg.get("method") or "paste"))
                elif kind == "retry":
                    cid = str(msg.get("id") or msg.get("capture_id") or "")
                    self._retry(cid)
            finally:
                self._idle_push()

        def _capture_drop(self, pd: PendingDrop, intent: str = "add-file") -> None:
            accepted = 0
            failed = 0
            # Folder/unsupported already surfaced on drag-data-received
            for path in pd.paths:
                ok = self._capture_path(path, method="drag_file", notify_each=False)
                accepted += 1 if ok else 0
                failed += 0 if ok else 1
            for url in pd.urls:
                ok = self._capture_url(url, method="drag_url", notify_each=False)
                accepted += 1 if ok else 0
                failed += 0 if ok else 1
            if pd.text and not pd.paths and not pd.urls:
                ok = self._capture_text(pd.text, method="drag_text" if intent != "paste-clipboard" else "paste", notify_each=False)
                accepted += 1 if ok else 0
                failed += 0 if ok else 1
            if accepted:
                notify("AJ Orb", f"Captured {accepted} item(s)")
                GLib.idle_add(self._toast, "success", "Added to AJ", f"{accepted} item(s) captured")
            if failed and not accepted:
                GLib.idle_add(self._toast, "error", "Nothing was added", "Capture failed for the dropped item(s).")
            elif failed:
                GLib.idle_add(self._toast, "warning", "Some items failed", f"{failed} item(s) could not be captured.")

        def _capture_path(self, path: str, method: str = "drag_file", notify_each: bool = True) -> bool:
            p = Path(path).expanduser()
            if not path or not p.exists() or not p.is_file():
                if notify_each:
                    GLib.idle_add(self._toast, "error", "File not available", str(path))
                return False
            try:
                rec = capture_file(self.store, str(p), capture_method=method)
                process_capture(self.store, rec["capture_id"])
                if notify_each:
                    notify("AJ Orb", f"Captured {p.name}")
                return True
            except Exception as e:
                if notify_each:
                    GLib.idle_add(self._toast, "error", "Capture failed", str(e)[:200])
                return False

        def _capture_url(self, url: str, method: str = "drag_url", notify_each: bool = True) -> bool:
            try:
                rec = capture_url(self.store, url, capture_method=method)
                process_capture(self.store, rec["capture_id"])
                if notify_each:
                    notify("AJ Orb", "Captured link")
                return True
            except Exception as e:
                if notify_each:
                    GLib.idle_add(self._toast, "error", "Capture failed", str(e)[:200])
                return False

        def _capture_text(self, text: str, method: str = "paste", notify_each: bool = True) -> bool:
            try:
                rec = capture_text(self.store, text, capture_method=method)
                process_capture(self.store, rec["capture_id"])
                if notify_each:
                    notify("AJ Orb", "Captured text")
                return True
            except Exception as e:
                if notify_each:
                    GLib.idle_add(self._toast, "error", "Capture failed", str(e)[:200])
                return False

        def _retry(self, capture_id: str) -> bool:
            if not capture_id:
                return False
            try:
                retry_failed(self.store, capture_id)
                notify("AJ Orb", "Retry complete")
                GLib.idle_add(self._toast, "success", "Retry complete", "")
                return True
            except Exception as e:
                GLib.idle_add(self._toast, "error", "Retry failed", str(e)[:200])
                return False

        # ----- lifecycle -----
        def on_delete(self, *_a):
            self.shutdown()
            return False

        def on_destroy(self, *_a):
            self.shutdown()
            try:
                Gtk.main_quit()
            except Exception:
                pass

        def shutdown(self):
            if self._shutdown_done:
                return
            self._shutdown_done = True
            self._worker_stop.set()
            try:
                save_orb_state(self.store, self.state)
            except Exception:
                pass


def run_orb_web(
    inbox_root: Optional[str] = None,
    config: Any = None,
    debug: bool = False,
    data_dir: Optional[str] = None,
):
    ok, reason = web_gui_available()
    if not ok:
        raise RuntimeError(reason)

    explicit_root = inbox_root or data_dir
    if explicit_root:
        store = InboxStore(explicit_root, config=config)
    else:
        cfg = config or load_config()
        store = InboxStore(None, config=cfg)

    # Writability preflight (no silent fallback).
    try:
        testp = store.paths["index"] / ".aj_orb_write_test"
        testp.write_text("ok", encoding="utf-8")
        try:
            testp.unlink()
        except Exception:
            pass
    except Exception as e:
        try:
            notify("AJ Orb", f"Storage unavailable: {e}", urgency="critical")
        except Exception:
            pass
        raise RuntimeError(f"Inbox storage unavailable or not writable: {store.root}: {e}") from e

    lock = OrbInstanceLock(store.paths["index"] / "orb.lock")
    if not lock.try_acquire():
        try:
            notify("AJ Orb", "AJ Orb is already running for this inbox")
        except Exception:
            pass
        print("AJ Orb is already running for this inbox.", file=sys.stderr)
        return

    win = OrbWebWindow(store, debug=debug)
    win.show_all()
    try:
        win.present()
    except Exception:
        pass

    def _sig(*_a):
        try:
            GLib.idle_add(win.destroy)
        except Exception:
            pass

    try:
        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)
    except Exception:
        pass

    try:
        Gtk.main()
    finally:
        try:
            lock.release()
        except Exception:
            pass
        try:
            save_orb_state(store, win.state)
        except Exception:
            pass


def _parse_args(argv: Optional[List[str]] = None):
    ap = argparse.ArgumentParser(prog="python -m aj.orb_web", description="Launch AJ web orb GUI")
    ap.add_argument("--inbox-root", dest="inbox_root", default="", help="explicit inbox root path")
    ap.add_argument("--debug", action="store_true", help="verbose diagnostics to stderr")
    ap.add_argument("--check-gui", action="store_true", help="check GTK/WebKit availability and exit")
    ap.add_argument("legacy_root", nargs="?", default="", help=argparse.SUPPRESS)
    return ap.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    if args.check_gui:
        ok, reason = web_gui_available()
        payload = {"ok": ok, "gtk": GTK_AVAILABLE, "webkit": WEBKIT_AVAILABLE, "python": sys.executable}
        if ok:
            payload["dist"] = str(dist_index_path())
            print(json.dumps(payload))
            raise SystemExit(0)
        payload["error"] = reason
        print(json.dumps(payload), file=sys.stderr)
        raise SystemExit(1)
    root = args.inbox_root or args.legacy_root or None
    run_orb_web(inbox_root=root, debug=args.debug)
