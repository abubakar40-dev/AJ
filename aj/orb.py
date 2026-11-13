"""AJ Floating Capture Orb (GTK3).

Lightweight, config-aware desktop capture front-end for AJ Knowledge Inbox.
- Canonical inbox storage via AJ config/env/explicit root (no silent mis-rooting)
- Import-safe without GTK (CLI --check-gui / tests can import module)
- Asynchronous capture/processing worker (UI never blocks on extraction/fetch)
- Real drag-drop, clipboard paste, status/menu controls, position persistence
- Single-instance lock per resolved inbox root

GTK3/PyGObject is required to *run* the GUI. AJ core can remain in its own venv;
`python -m aj orb` can launch via system Python when needed.
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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

try:
    import cairo  # type: ignore
except Exception:  # pragma: no cover
    cairo = None  # type: ignore

GTK_AVAILABLE = False
GTK_IMPORT_ERROR: Optional[BaseException] = None
try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk, GLib, Gio, Pango  # type: ignore
    GTK_AVAILABLE = True
except Exception as e:  # pragma: no cover - depends on host GUI deps
    GTK_IMPORT_ERROR = e
    Gtk = Gdk = GLib = Gio = Pango = None  # type: ignore

_HAS_NOTIFY = False
if GTK_AVAILABLE:
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
ORB_SIZE = 76
PANEL_MARGIN = 8
IDLE_ANIM_MS = 220  # slow, lightweight pulse only when useful
RECENT_MAX = 12


# ---------------------------------------------------------------------------
# Storage / state helpers
# ---------------------------------------------------------------------------

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
        # Never crash UI on state save failure; storage issues are surfaced elsewhere.
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def _clamp_position(x: int, y: int, w: int = ORB_SIZE, h: int = ORB_SIZE) -> Tuple[int, int]:
    """Best-effort clamp to visible monitor/workarea; fall back safely."""
    if not GTK_AVAILABLE:
        return max(0, int(x)), max(0, int(y))
    try:
        display = Gdk.Display.get_default()
        if not display:
            return max(0, int(x)), max(0, int(y))
        # Prefer monitor at pointer/current, else primary/first.
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
        # Keep fully visible with a small margin.
        min_x = gx + 4
        min_y = gy + 4
        max_x = gx + max(4, gw - w - 4)
        max_y = gy + max(4, gh - h - 4)
        return min(max(int(x), min_x), max_x), min(max(int(y), min_y), max_y)
    except Exception:
        return max(0, int(x)), max(0, int(y))


def notify(title: str, body: str, urgency: str = "low") -> None:
    if not _HAS_NOTIFY:
        return
    try:
        n = Notify.Notification.new(title, body, "dialog-information")
        if hasattr(Notify, "Urgency"):
            u = {
                "low": Notify.Urgency.LOW,
                "normal": Notify.Urgency.NORMAL,
                "critical": Notify.Urgency.CRITICAL,
            }.get(urgency, Notify.Urgency.LOW)
            n.set_urgency(u)
        n.set_timeout(4000)
        n.show()
    except Exception:
        pass


def _open_path(path: str) -> Tuple[bool, str]:
    try:
        subprocess.Popen(["xdg-open", path])
        return True, ""
    except Exception as e:
        return False, str(e)


def _uri_to_path_or_url(uri: str) -> Tuple[Optional[str], Optional[str]]:
    uri = (uri or "").strip()
    if not uri:
        return None, None
    try:
        parsed = urlparse(uri)
    except Exception:
        return None, None
    if parsed.scheme == "file":
        return unquote(parsed.path), None
    if parsed.scheme in ("http", "https"):
        return None, uri
    return None, None


# ---------------------------------------------------------------------------
# Single-instance lock (advisory, per inbox root)
# ---------------------------------------------------------------------------

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
                # If flock unavailable, proceed best-effort (non-fatal).
                pass
            try:
                os.ftruncate(self.fd, 0)
                os.write(self.fd, str(os.getpid()).encode("utf-8", errors="replace"))
            except Exception:
                pass
            self.acquired = True
            return True
        except Exception:
            return True  # do not block launch on lock infra failure

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
# Worker
# ---------------------------------------------------------------------------

if GTK_AVAILABLE:

    class CaptureWorker:
        """Background capture/processing worker; UI updates via GLib.idle_add."""

        def __init__(self, store: InboxStore, on_event):
            self.store = store
            self.on_event = on_event
            self.q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
            self.paused = False
            self._stop = threading.Event()
            self.thread = threading.Thread(target=self.run, daemon=True, name="aj-orb-worker")
            self._paused_jobs: List[Dict[str, Any]] = []

        def start(self) -> None:
            self.thread.start()

        def stop(self) -> None:
            self._stop.set()

        def enqueue(self, job: Dict[str, Any]) -> None:
            if self.paused and job.get("type") in ("file", "url", "text"):
                # Capture acceptance is durable only after DB write; if paused, queue in-memory
                # and record explicit paused state in UI. User expects pause to prevent processing.
                self._paused_jobs.append(job)
                GLib.idle_add(self.on_event, "paused_job", "", "paused", "Capture queued while paused")
                return
            self.q.put(job)

        def drain_paused_jobs(self) -> int:
            jobs = list(self._paused_jobs)
            self._paused_jobs.clear()
            for j in jobs:
                self.q.put(j)
            return len(jobs)

        def run(self) -> None:
            while not self._stop.is_set():
                try:
                    job = self.q.get(timeout=0.25)
                except queue.Empty:
                    continue
                try:
                    self._handle(job)
                except Exception as e:
                    cid = job.get("capture_id", "")
                    GLib.idle_add(self.on_event, "error", cid, "failed", f"{type(e).__name__}: {e}")
                finally:
                    try:
                        self.q.task_done()
                    except Exception:
                        pass

        def _emit(self, kind: str, capture_id: str = "", status: str = "", detail: str = "", **extra):
            payload = {"kind": kind, "capture_id": capture_id, "status": status, "detail": detail}
            payload.update(extra)
            GLib.idle_add(self.on_event, kind, capture_id, status, detail, payload)
            return False

        def _handle(self, job: Dict[str, Any]) -> None:
            jtype = job.get("type")
            method = job.get("method", "drag_file")
            if jtype == "process_pending":
                self._emit("processing", "", "processing", "Processing pending captures...")
                rows = process_pending(self.store, limit=int(job.get("limit", 20)))
                self._emit("batch_done", "", "done", f"Processed {len(rows)} pending", count=len(rows))
                return
            if jtype == "retry_failed_all":
                failed = self.store.list(status="failed", limit=int(job.get("limit", 50)))
                ok = 0
                fail = 0
                for r in failed:
                    self._emit("processing", r.get("capture_id", ""), "processing", "Retrying...")
                    out = retry_failed(self.store, r["capture_id"])
                    if (out or {}).get("status") in ("ready", "processed"):
                        ok += 1
                        self._emit("done", r["capture_id"], out.get("status", "ready"), "", record=out)
                    else:
                        fail += 1
                        self._emit("error", r["capture_id"], "failed", (out or {}).get("error_details") or "retry failed", record=out)
                self._emit("batch_done", "", "done", f"Retried {len(failed)}: {ok} ok, {fail} failed", ok=ok, failed=fail)
                return

            # Capture + process
            if jtype == "file":
                path = job.get("path", "")
                self._emit("capturing", "", "incoming", f"Capturing file: {Path(path).name}")
                rec = capture_file(self.store, path, capture_method=method)
            elif jtype == "url":
                url = job.get("url", "")
                self._emit("capturing", "", "incoming", "Capturing URL...")
                rec = capture_url(self.store, url, capture_method=method)
            elif jtype == "text":
                txt = job.get("text", "")
                self._emit("capturing", "", "incoming", "Capturing text...")
                rec = capture_text(self.store, txt, capture_method=method)
            else:
                return

            cid = rec["capture_id"]
            self._emit("queued", cid, "queued", "Captured and queued", record=rec)
            self._emit("processing", cid, "processing", "Processing capture...", record=rec)
            out = process_capture(self.store, cid) or rec
            status = out.get("status", "failed")
            detail = out.get("error_details") or ""
            if status in ("ready", "processed"):
                self._emit("done", cid, status, "Capture ready", record=out)
            else:
                self._emit("error", cid, status, detail or "Capture failed", record=out)


    class OrbWindow(Gtk.Window):
        def __init__(self, store: InboxStore, debug: bool = False):
            super().__init__(title="AJ Orb")
            self.store = store
            self.debug = debug
            self.state = load_orb_state(store)
            self.set_decorated(False)
            self.set_resizable(False)
            self.set_default_size(ORB_SIZE, ORB_SIZE)
            self.set_size_request(ORB_SIZE, ORB_SIZE)
            self.set_keep_above(True)
            self.set_skip_taskbar_hint(True)
            self.set_skip_pager_hint(True)
            self.set_app_paintable(True)
            self.set_can_focus(True)
            # Stick to keep accessible across workspaces where supported.
            try:
                self.stick()
            except Exception:
                pass
            # Use DOCK for floating utility-like behavior on many WMs; Wayland/Mutter may
            # treat hints differently (limitation documented). Avoid accept_focus=False
            # because it can break menu interaction; we do not hide on focus loss.
            try:
                self.set_type_hint(Gdk.WindowTypeHint.DOCK)
            except Exception:
                try:
                    self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
                except Exception:
                    pass
            try:
                self.set_wmclass("aj-orb", "AJ Orb")
            except Exception:
                try:
                    self.set_role("aj-orb")
                except Exception:
                    pass

            screen = self.get_screen()
            if screen is not None:
                visual = screen.get_rgba_visual()
                if visual is not None:
                    self.set_visual(visual)

            self.mode = "paused" if self.state.get("paused") else "ready"
            self.status_line = "Paused" if self.state.get("paused") else "Ready"
            self.detail_line = "AJ capture orb"
            self.drag_over = False
            self.pulse_phase = 0.0
            self._pulse_tick = 0
            self.recent_events: List[str] = []
            self._counts = {"ready": 0, "queued": 0, "failed": 0, "processing": 0}

            self.darea = Gtk.DrawingArea()
            self.darea.set_size_request(ORB_SIZE, ORB_SIZE)
            self.darea.connect("draw", self.on_draw)
            self.add(self.darea)

            self.add_events(
                Gdk.EventMask.BUTTON_PRESS_MASK
                | Gdk.EventMask.BUTTON_RELEASE_MASK
                | Gdk.EventMask.POINTER_MOTION_MASK
                | Gdk.EventMask.ENTER_NOTIFY_MASK
                | Gdk.EventMask.LEAVE_NOTIFY_MASK
            )

            targets = [
                Gtk.TargetEntry.new("text/uri-list", 0, 1),
                Gtk.TargetEntry.new("text/plain", 0, 2),
                Gtk.TargetEntry.new("UTF8_STRING", 0, 3),
                Gtk.TargetEntry.new("STRING", 0, 4),
            ]
            self.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.DROP, targets, Gdk.DragAction.COPY)
            self.connect("drag-data-received", self.on_drag_data)
            self.connect("drag-motion", self.on_drag_motion)
            self.connect("drag-leave", self.on_drag_leave)
            self.connect("button-press-event", self.on_button_press)
            self.connect("button-release-event", self.on_button_release)
            self.connect("motion-notify-event", self.on_motion)
            self.connect("delete-event", self.on_delete)
            self.connect("destroy", self.on_destroy)

            self.dragging_window = False
            self.drag_offset = (0, 0)
            self.press_pos = (0.0, 0.0)
            self.did_move = False

            self.worker = CaptureWorker(store, self.on_worker_event)
            self.worker.paused = bool(self.state.get("paused", False))
            self.worker.start()

            x = int(self.state.get("x", 48) or 48)
            y = int(self.state.get("y", 96) or 96)
            x, y = _clamp_position(x, y)
            self.state["x"], self.state["y"] = x, y
            try:
                self.move(x, y)
            except Exception:
                pass

            self._anim_source = GLib.timeout_add(IDLE_ANIM_MS, self._tick)
            self.refresh_counts(initial=True)

        # ----- lifecycle / persistence -----
        def on_delete(self, *_args):
            self.shutdown()
            return False

        def on_destroy(self, *_args):
            self.shutdown()
            try:
                Gtk.main_quit()
            except Exception:
                pass

        def shutdown(self):
            if getattr(self, "_shutdown_done", False):
                return
            self._shutdown_done = True
            try:
                if hasattr(self, "_anim_source") and self._anim_source:
                    GLib.source_remove(self._anim_source)
            except Exception:
                pass
            try:
                if hasattr(self, "worker"):
                    self.worker.stop()
            except Exception:
                pass
            try:
                x, y = self.get_position()
                self.state["x"], self.state["y"] = int(x), int(y)
                save_orb_state(self.store, self.state)
            except Exception:
                pass

        # ----- state / UI helpers -----
        def _log(self, msg: str) -> None:
            if self.debug:
                try:
                    print(f"[aj-orb] {msg}", file=sys.stderr)
                except Exception:
                    pass

        def _remember(self, msg: str) -> None:
            ts = time.strftime("%H:%M:%S")
            self.recent_events.insert(0, f"[{ts}] {msg}")
            del self.recent_events[RECENT_MAX:]

        def refresh_counts(self, initial: bool = False):
            def work():
                try:
                    s = inbox_summary(self.store)
                    c = s.get("counts", {})
                    counts = {
                        "ready": int(c.get("ready", 0)),
                        "queued": int(c.get("queued", 0)) + int(c.get("incoming", 0)),
                        "failed": int(c.get("failed", 0)),
                        "processing": int(c.get("processing", 0)),
                    }
                except Exception as e:
                    counts = None
                    err = f"{type(e).__name__}: {e}"
                def apply():
                    if counts is not None:
                        self._counts = counts
                        if self.mode not in ("capturing", "processing", "error_flash", "success_flash", "drag"):
                            self._sync_status_text()
                    else:
                        self.status_line = "Storage error"
                        self.detail_line = err[:80]
                        self.mode = "error"
                    self.darea.queue_draw()
                    return False
                GLib.idle_add(apply)
            threading.Thread(target=work, daemon=True).start()

        def _sync_status_text(self):
            if self.worker.paused:
                self.mode = "paused"
                self.status_line = "Paused"
            elif self._counts.get("failed", 0) > 0 and self.mode == "ready":
                self.status_line = "Ready"
            elif self.mode not in ("drag", "error", "error_flash", "success_flash", "processing", "capturing"):
                self.mode = "ready"
                self.status_line = "Ready"
            c = self._counts
            self.detail_line = f"R{c.get('ready',0)} Q{c.get('queued',0)} P{c.get('processing',0)} F{c.get('failed',0)}"

        def flash(self, mode: str, text: str, detail: Optional[str] = None, ms: int = 1800):
            self.mode = mode
            self.status_line = text
            if detail is not None:
                self.detail_line = detail
            self.darea.queue_draw()
            def clear():
                self.mode = "paused" if self.worker.paused else "ready"
                self._sync_status_text()
                self.darea.queue_draw()
                return False
            GLib.timeout_add(ms, clear)

        def on_worker_event(self, kind, capture_id, status, detail, payload=None):
            payload = payload or {}
            self._log(f"event {kind} {capture_id} {status} {detail}")
            if kind in ("capturing", "queued", "processing"):
                self.mode = "processing" if kind in ("queued", "processing") else "capturing"
                self.status_line = "Learning" if kind == "capturing" else ("Queued" if kind == "queued" else "Processing")
                self.detail_line = (detail or "")[:70] or self.detail_line
                self._remember(detail or kind)
                self.darea.queue_draw()
                return False
            if kind == "paused_job":
                self.mode = "paused"
                self.status_line = "Paused"
                self.detail_line = "Job held (paused)"
                self._remember("Capture requested while paused")
                notify("AJ Orb", "Orb is paused — capture held until resumed")
                self.darea.queue_draw()
                return False
            if kind == "done":
                self._remember(f"Ready: {capture_id[:12] if capture_id else 'batch'}")
                self.flash("success_flash", "Captured", "Saved to AJ Inbox", ms=1800)
                notify("AJ Orb", "Capture ready in inbox")
                self.refresh_counts()
                return False
            if kind == "error":
                msg = (detail or "Capture failed")[:120]
                self._remember(f"Failed: {capture_id[:12]} {msg}".strip())
                self.flash("error_flash", "Issue", msg[:40], ms=3500)
                notify("AJ Orb", f"Capture failed: {msg[:90]}", urgency="normal")
                self.refresh_counts()
                return False
            if kind == "batch_done":
                self._remember(detail or "Batch complete")
                self.flash("success_flash", "Done", (detail or "")[:40], ms=2000)
                self.refresh_counts()
                return False
            self.refresh_counts()
            return False

        # ----- animation / draw -----
        def _tick(self):
            # Lightweight animation: only animate when visually meaningful.
            animate = self.drag_over or self.mode in ("capturing", "processing", "success_flash", "error_flash") or self.mode == "ready"
            if animate:
                self._pulse_tick = (self._pulse_tick + 1) % 100000
                self.pulse_phase = (self._pulse_tick * 0.18) % (2 * math.pi)
                self.darea.queue_draw()
            return True

        def on_draw(self, widget, cr):
            w = widget.get_allocated_width()
            h = widget.get_allocated_height()
            cx, cy = w / 2.0, h / 2.0
            r = min(w, h) / 2.0 - 5.0

            # transparent background
            cr.save()
            cr.set_source_rgba(0, 0, 0, 0)
            cr.set_operator(0)  # CLEAR
            cr.paint()
            cr.restore()
            cr.set_operator(2)  # OVER

            mode = self.mode
            # Palette (restrained, premium-ish dark + cyan/violet accents)
            if mode == "paused":
                core = (0.22, 0.24, 0.28, 0.96)
                glow = (0.55, 0.58, 0.62, 0.22)
                ring = (0.75, 0.78, 0.82, 0.30)
                accent = (0.70, 0.74, 0.78, 0.9)
            elif mode in ("error", "error_flash"):
                core = (0.18, 0.10, 0.12, 0.97)
                glow = (0.95, 0.30, 0.35, 0.28)
                ring = (1.0, 0.55, 0.55, 0.45)
                accent = (1.0, 0.85, 0.85, 0.95)
            elif mode in ("success_flash",):
                core = (0.08, 0.18, 0.16, 0.97)
                glow = (0.20, 0.90, 0.70, 0.26)
                ring = (0.55, 1.0, 0.85, 0.45)
                accent = (0.90, 1.0, 0.96, 0.95)
            elif mode in ("capturing", "processing") or self.drag_over:
                core = (0.06, 0.12, 0.20, 0.97)
                glow = (0.20, 0.65, 1.0, 0.30)
                ring = (0.45, 0.85, 1.0, 0.55)
                accent = (0.92, 0.98, 1.0, 0.98)
            else:  # ready
                core = (0.07, 0.10, 0.16, 0.97)
                glow = (0.35, 0.45, 1.0, 0.22)
                ring = (0.55, 0.70, 1.0, 0.38)
                accent = (0.94, 0.97, 1.0, 0.98)

            pulse = 0.5 + 0.5 * math.sin(self.pulse_phase)
            if mode == "paused":
                pulse = 0.15
            elif mode == "ready" and not self.drag_over:
                pulse *= 0.35  # very subtle idle breathing

            # outer glow
            for i, (rr, a_mult) in enumerate(((r + 4.5, 0.10), (r + 2.5, 0.16), (r + 0.5, 0.22))):
                cr.arc(cx, cy, rr + pulse * (1.2 if i == 0 else 0.6), 0, 2 * math.pi)
                cr.set_source_rgba(glow[0], glow[1], glow[2], glow[3] * a_mult * (0.7 + 0.6 * pulse))
                cr.set_line_width(2.0)
                cr.stroke()

            # core sphere (radial gradient)
            grad = None
            if cairo is not None:
                grad = cairo.RadialGradient(cx - r * 0.25, cy - r * 0.30, r * 0.2, cx, cy, r)
            elif hasattr(cr, "create_radial_gradient"):
                grad = cr.create_radial_gradient(cx - r * 0.25, cy - r * 0.30, r * 0.2, cx, cy, r)
            if grad is not None:
                grad.add_color_stop_rgba(0.0, min(1.0, core[0] + 0.22), min(1.0, core[1] + 0.22), min(1.0, core[2] + 0.28), core[3])
                grad.add_color_stop_rgba(0.55, core[0] + 0.06, core[1] + 0.06, core[2] + 0.10, core[3])
                grad.add_color_stop_rgba(1.0, max(0, core[0] - 0.03), max(0, core[1] - 0.03), max(0, core[2] - 0.02), core[3])
                cr.arc(cx, cy, r, 0, 2 * math.pi)
                cr.set_source(grad)
                cr.fill()
            else:
                cr.arc(cx, cy, r, 0, 2 * math.pi)
                cr.set_source_rgba(core[0], core[1], core[2], core[3])
                cr.fill()

            # inner ring
            cr.arc(cx, cy, r - 3.0, -math.pi * 0.8, math.pi * 1.2)
            cr.set_source_rgba(ring[0], ring[1], ring[2], ring[3] * (0.7 + 0.3 * pulse))
            cr.set_line_width(1.6)
            cr.stroke()

            # highlight arc
            cr.arc(cx, cy, r - 6.0, -math.pi * 0.95, -math.pi * 0.15)
            cr.set_source_rgba(1, 1, 1, 0.10 + 0.08 * pulse)
            cr.set_line_width(1.2)
            cr.stroke()

            # drop indicator
            if self.drag_over:
                cr.arc(cx, cy, r - 8.0, 0, 2 * math.pi)
                cr.set_source_rgba(0.45, 0.90, 1.0, 0.35)
                cr.set_line_width(2.0)
                cr.set_dash([4.0, 3.0], 0)
                cr.stroke()
                cr.set_dash([], 0)

            # AJ label
            cr.select_font_face("Sans", 0, 1)  # bold
            cr.set_font_size(18)
            label = "AJ"
            xb, yb, tw, th, xa, ya = cr.text_extents(label)
            cr.move_to(cx - tw / 2 - xb, cy - th / 2 - yb - 4)
            cr.set_source_rgba(0, 0, 0, 0.25)
            cr.show_text(label)
            cr.move_to(cx - tw / 2 - xb, cy - th / 2 - yb - 5)
            cr.set_source_rgba(accent[0], accent[1], accent[2], accent[3])
            cr.show_text(label)

            # small status dot/text cue
            cr.set_font_size(8.5)
            stext = "PAUSE" if self.worker.paused else ("DROP" if self.drag_over else "INBOX")
            xb, yb, tw, th, xa, ya = cr.text_extents(stext)
            cr.move_to(cx - tw / 2 - xb, cy + 12 - th / 2 - yb)
            cr.set_source_rgba(1, 1, 1, 0.55 if not self.drag_over else 0.85)
            cr.show_text(stext)

            return False

        # ----- drag and drop -----
        def on_drag_motion(self, widget, context, x, y, time_):
            self.drag_over = True
            self.mode = "drag"
            self.status_line = "Drop"
            self.detail_line = "Release to capture"
            self.darea.queue_draw()
            try:
                Gdk.drag_status(context, Gdk.DragAction.COPY, time_)
            except Exception:
                pass
            return True

        def on_drag_leave(self, widget, context, time_):
            self.drag_over = False
            self.mode = "paused" if self.worker.paused else "ready"
            self._sync_status_text()
            self.darea.queue_draw()

        def _enqueue_uris(self, uris: List[str], method: str = "drag_file") -> Dict[str, int]:
            counts = {"files": 0, "urls": 0, "dirs": 0, "unsupported": 0, "queued": 0}
            for uri in uris:
                path, url = _uri_to_path_or_url(uri)
                if path:
                    p = Path(path)
                    if p.is_dir():
                        counts["dirs"] += 1
                        self._remember(f"Folder drop unsupported: {p.name}")
                        continue
                    if p.exists() and p.is_file():
                        self.worker.enqueue({"type": "file", "path": str(p), "method": method})
                        counts["files"] += 1
                        counts["queued"] += 1
                    else:
                        counts["unsupported"] += 1
                        self._remember(f"Missing/unsupported file: {path}")
                elif url:
                    self.worker.enqueue({"type": "url", "url": url, "method": "drag_url"})
                    counts["urls"] += 1
                    counts["queued"] += 1
                else:
                    counts["unsupported"] += 1
            return counts

        def on_drag_data(self, widget, drag_context, x, y, data, info, time_):
            ok = False
            try:
                uris = []
                text = ""
                try:
                    uris = list(data.get_uris() or [])
                except Exception:
                    uris = []
                try:
                    text = data.get_text() or ""
                except Exception:
                    text = ""
                if not uris and text:
                    # Some sources provide URI list as text
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    if any(ln.startswith(("file://", "http://", "https://")) for ln in lines):
                        uris = lines

                if uris:
                    counts = self._enqueue_uris(uris)
                    ok = counts["queued"] > 0
                    msg_parts = []
                    if counts["files"]:
                        msg_parts.append(f"{counts['files']} file(s)")
                    if counts["urls"]:
                        msg_parts.append(f"{counts['urls']} URL(s)")
                    if counts["dirs"]:
                        msg_parts.append(f"{counts['dirs']} folder(s) not supported")
                    if counts["unsupported"]:
                        msg_parts.append(f"{counts['unsupported']} unsupported")
                    msg = ", ".join(msg_parts) or "Nothing captured"
                    self._remember(msg)
                    if counts["queued"] > 0:
                        self.flash("capturing", "Learning", msg[:40], ms=1600)
                        notify("AJ Orb", f"Capture accepted: {msg}")
                    else:
                        self.flash("error_flash", "No capture", msg[:40], ms=2600)
                        notify("AJ Orb", msg, urgency="normal")
                elif text and text.strip():
                    self.worker.enqueue({"type": "text", "text": text, "method": "drag_text"})
                    ok = True
                    self._remember("Dropped text captured")
                    self.flash("capturing", "Learning", "Text queued", ms=1400)
                    notify("AJ Orb", "Text capture accepted")
                else:
                    self.flash("error_flash", "No data", "Unsupported drop", ms=2200)
            except Exception as e:
                self.flash("error_flash", "Drop failed", str(e)[:40], ms=3000)
                notify("AJ Orb", f"Drop failed: {e}", urgency="normal")
                ok = False
            finally:
                self.drag_over = False
            try:
                Gtk.drag_finish(drag_context, ok, False, time_)
            except Exception:
                pass

        # ----- window move / click / menu -----
        def on_button_press(self, widget, event):
            self.press_pos = (event.x_root, event.y_root)
            self.did_move = False
            if event.button == 1:
                self.dragging_window = True
                try:
                    win_x, win_y = self.get_position()
                except Exception:
                    win_x, win_y = int(self.state.get("x", 48)), int(self.state.get("y", 96))
                self.drag_offset = (event.x_root - win_x, event.y_root - win_y)
                return True
            if event.button == 3:
                self.show_menu(event)
                return True
            return False

        def on_button_release(self, widget, event):
            if event.button == 1 and self.dragging_window:
                self.dragging_window = False
                dx = abs(event.x_root - self.press_pos[0])
                dy = abs(event.y_root - self.press_pos[1])
                # Persist position after move; treat tiny movement as click.
                try:
                    x, y = self.get_position()
                    x, y = _clamp_position(x, y)
                    self.move(x, y)
                    self.state["x"], self.state["y"] = int(x), int(y)
                    save_orb_state(self.store, self.state)
                except Exception:
                    pass
                if dx < 5 and dy < 5 and not self.did_move:
                    self.show_quick_status()
                return True
            return False

        def on_motion(self, widget, event):
            if self.dragging_window:
                dx = abs(event.x_root - self.press_pos[0])
                dy = abs(event.y_root - self.press_pos[1])
                if dx > 4 or dy > 4:
                    self.did_move = True
                nx = int(event.x_root - self.drag_offset[0])
                ny = int(event.y_root - self.drag_offset[1])
                nx, ny = _clamp_position(nx, ny)
                try:
                    self.move(nx, ny)
                except Exception:
                    pass
                self.state["x"], self.state["y"] = nx, ny
                return True
            return False

        # ----- actions -----
        def show_quick_status(self):
            self.refresh_counts()
            c = self._counts
            notify("AJ Orb", f"Ready {c.get('ready',0)} · Queued {c.get('queued',0)} · Processing {c.get('processing',0)} · Failed {c.get('failed',0)}")
            self.flash("ready", "AJ", self.detail_line, ms=1200)

        def choose_files(self):
            try:
                dlg = Gtk.FileChooserDialog(
                    title="Capture files into AJ Inbox",
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
                notify("AJ Orb", f"File chooser unavailable: {e}", urgency="normal")
                return
            if not files:
                return
            n = 0
            for f in files:
                p = Path(f)
                if p.is_dir():
                    self._remember(f"Folder not supported: {p.name}")
                    continue
                if p.exists() and p.is_file():
                    self.worker.enqueue({"type": "file", "path": str(p), "method": "drag_file"})
                    n += 1
            if n:
                self.flash("capturing", "Learning", f"{n} file(s) queued", ms=1600)
                notify("AJ Orb", f"{n} file(s) accepted for capture")
            else:
                notify("AJ Orb", "No supported files selected")

        def paste_clipboard(self):
            if self.worker.paused:
                notify("AJ Orb", "Orb is paused — resume to process captures")
                self.flash("paused", "Paused", "Resume to process", ms=1500)
                return
            try:
                cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            except Exception as e:
                notify("AJ Orb", f"Clipboard unavailable: {e}", urgency="normal")
                return
            # Prefer URIs, then text
            uris = []
            try:
                sel = cb.wait_for_contents(Gdk.Atom.intern("text/uri-list", False))
                if sel:
                    uris = list(sel.get_uris() or [])
            except Exception:
                uris = []
            if uris:
                counts = self._enqueue_uris(uris, method="paste")
                if counts["queued"]:
                    msg = f"Pasted {counts['queued']} item(s)"
                    if counts["dirs"]:
                        msg += f", {counts['dirs']} folder(s) unsupported"
                    self.flash("capturing", "Learning", msg[:40], ms=1600)
                    notify("AJ Orb", msg)
                else:
                    notify("AJ Orb", "Clipboard had no supported file/URL items")
                return
            try:
                text = cb.wait_for_text()
            except Exception:
                text = None
            if text and text.strip():
                self.worker.enqueue({"type": "text", "text": text, "method": "paste"})
                self.flash("capturing", "Learning", "Text queued", ms=1400)
                notify("AJ Orb", "Pasted text accepted for capture")
            else:
                notify("AJ Orb", "Clipboard is empty or unsupported")

        def toggle_pause(self):
            self.worker.paused = not self.worker.paused
            self.state["paused"] = self.worker.paused
            if not self.worker.paused:
                n = self.worker.drain_paused_jobs()
                if n:
                    self._remember(f"Resumed: released {n} held capture(s)")
                    notify("AJ Orb", f"Capture resumed ({n} held item(s) queued)")
                else:
                    notify("AJ Orb", "Capture resumed")
            else:
                notify("AJ Orb", "Capture paused")
            save_orb_state(self.store, self.state)
            self.mode = "paused" if self.worker.paused else "ready"
            self._sync_status_text()
            self.darea.queue_draw()

        def open_inbox_folder(self):
            ok, err = _open_path(str(self.store.root))
            if not ok:
                notify("AJ Orb", f"Could not open inbox folder: {err}", urgency="normal")

        def open_inbox_viewer(self):
            # Open lightweight local viewer via CLI in background (reuse canonical implementation)
            try:
                aj_root = Path(__file__).resolve().parent.parent
                py = sys.executable
                env = os.environ.copy()
                existing_pp = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = str(aj_root) + (os.pathsep + existing_pp if existing_pp else "")
                cmd = [py, "-m", "aj", "inbox", "--root", str(self.store.root), "view"]
                subprocess.Popen(cmd, cwd=str(aj_root), env=env)
                notify("AJ Orb", "Opening inbox viewer...")
            except Exception as e:
                notify("AJ Orb", f"Could not open inbox viewer: {e}", urgency="normal")

        def process_pending_now(self):
            self.worker.enqueue({"type": "process_pending", "limit": 50})
            notify("AJ Orb", "Processing pending captures...")

        def retry_failed_now(self):
            self.worker.enqueue({"type": "retry_failed_all", "limit": 100})
            notify("AJ Orb", "Retrying failed captures...")

        def copy_inbox_path(self):
            try:
                cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                cb.set_text(str(self.store.root), -1)
                cb.store()
                notify("AJ Orb", "Inbox path copied")
            except Exception as e:
                notify("AJ Orb", f"Could not copy path: {e}", urgency="normal")

        def capture_url_dialog(self):
            try:
                dlg = Gtk.Dialog(title="Capture URL", parent=self, flags=0)
                dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Capture", Gtk.ResponseType.OK)
                box = dlg.get_content_area()
                box.set_spacing(8)
                box.set_border_width(10)
                lbl = Gtk.Label(label="Enter a URL to capture into AJ Inbox:")
                lbl.set_xalign(0)
                entry = Gtk.Entry()
                entry.set_placeholder_text("https://...")
                entry.set_activates_default(True)
                box.add(lbl)
                box.add(entry)
                dlg.set_default_response(Gtk.ResponseType.OK)
                dlg.show_all()
                resp = dlg.run()
                url = (entry.get_text() or "").strip()
                dlg.destroy()
            except Exception as e:
                notify("AJ Orb", f"URL dialog unavailable: {e}", urgency="normal")
                return
            if resp != Gtk.ResponseType.OK or not url:
                return
            if not (url.startswith("http://") or url.startswith("https://")):
                notify("AJ Orb", "Please enter an http(s) URL", urgency="normal")
                return
            self.worker.enqueue({"type": "url", "url": url, "method": "drag_url"})
            self.flash("capturing", "Learning", "URL queued", ms=1400)
            notify("AJ Orb", "URL capture accepted")

        def show_storage_info(self):
            try:
                from .config import load as load_cfg
                from .inbox import resolve_inbox_root
                cfg = load_cfg()
                resolved = resolve_inbox_root(config=cfg)
            except Exception:
                cfg = None
                resolved = self.store.root
            msg = (
                f"Active inbox: {self.store.root}\n"
                f"Config-resolved: {resolved}\n"
                f"AJ_INBOX_ROOT={os.environ.get('AJ_INBOX_ROOT') or '(unset)'}\n"
                "To use workspace storage set AJ_INBOX_ROOT or core.inbox_root/data_dir in AJ config."
            )
            self._remember(f"Storage: {self.store.root}")
            try:
                dlg = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.INFO,
                                        buttons=Gtk.ButtonsType.OK, text="AJ Orb storage")
                dlg.format_secondary_text(msg)
                dlg.run()
                dlg.destroy()
            except Exception:
                notify("AJ Orb", str(self.store.root))

        def show_menu(self, event):
            menu = Gtk.Menu()

            def add(label, cb, sensitive=True):
                item = Gtk.MenuItem(label=label)
                item.connect("activate", lambda *_: cb())
                item.set_sensitive(sensitive)
                menu.append(item)
                return item

            c = self._counts
            header = Gtk.MenuItem(label=f"AJ Inbox  •  Ready {c.get('ready',0)}  Queued {c.get('queued',0)}  Failed {c.get('failed',0)}")
            header.set_sensitive(False)
            menu.append(header)
            sub = Gtk.MenuItem(label=f"Storage: {str(self.store.root)[:48]}{'…' if len(str(self.store.root))>48 else ''}")
            sub.set_sensitive(False)
            menu.append(sub)
            menu.append(Gtk.SeparatorMenuItem())

            add("Capture file(s)...", self.choose_files)
            add("Capture URL...", self.capture_url_dialog)
            add("Paste from clipboard", self.paste_clipboard)
            add("Process pending now", self.process_pending_now)
            add("Retry failed captures", self.retry_failed_now)

            menu.append(Gtk.SeparatorMenuItem())
            add("Resume capture" if self.worker.paused else "Pause capture", self.toggle_pause)
            add("Open inbox viewer", self.open_inbox_viewer)
            add("Open inbox folder", self.open_inbox_folder)
            add("Refresh status", lambda: (self.refresh_counts(), self.show_quick_status()))
            add("Copy inbox path", self.copy_inbox_path)
            add("Storage & config info...", self.show_storage_info)

            if self.recent_events:
                menu.append(Gtk.SeparatorMenuItem())
                recent = Gtk.MenuItem(label="Recent activity")
                submenu = Gtk.Menu()
                for line in self.recent_events[:8]:
                    mi = Gtk.MenuItem(label=line[:90])
                    mi.set_sensitive(False)
                    submenu.append(mi)
                recent.set_submenu(submenu)
                menu.append(recent)

            menu.append(Gtk.SeparatorMenuItem())
            add("Quit orb", self.destroy)

            menu.show_all()
            try:
                menu.popup_at_pointer(event)
            except Exception:
                menu.popup(None, None, None, None, event.button, event.time)


    def run_orb(inbox_root: Optional[str] = None, config: Any = None, debug: bool = False,
                data_dir: Optional[str] = None):
        """Launch AJ Orb GUI.

        Compatibility: older callers passed a positional `data_dir` treated as inbox root.
        Prefer `inbox_root` (explicit inbox root) or `config` for canonical resolution.
        """
        if not GTK_AVAILABLE:
            raise RuntimeError(f"GTK unavailable: {GTK_IMPORT_ERROR}")

        explicit_root = inbox_root or data_dir
        # If an explicit root is provided, treat it as the inbox root (including legacy
        # calls). If not, resolve from config/env/defaults canonically.
        if explicit_root:
            store = InboxStore(explicit_root, config=config)
        else:
            cfg = config or load_config()
            store = InboxStore(None, config=cfg)

        # Best-effort storage writability check (no silent fallback).
        try:
            testp = store.paths["index"] / ".aj_orb_write_test"
            testp.write_text("ok", encoding="utf-8")
            try:
                testp.unlink()
            except Exception:
                pass
        except Exception as e:
            # Surface clearly and abort: capturing to an unwritable/missing workspace must not
            # silently succeed elsewhere.
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

        win = OrbWindow(store, debug=debug)
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
                save_orb_state(store, load_orb_state(store) if False else win.state)
            except Exception:
                pass

else:  # pragma: no cover - GTK absent

    class CaptureWorker:
        def __init__(self, *a, **k):
            raise RuntimeError(f"GTK unavailable: {GTK_IMPORT_ERROR}")

    class OrbWindow:
        def __init__(self, *a, **k):
            raise RuntimeError(f"GTK unavailable: {GTK_IMPORT_ERROR}")

    def run_orb(inbox_root: Optional[str] = None, config: Any = None, debug: bool = False,
                data_dir: Optional[str] = None):
        raise RuntimeError(f"GTK unavailable: {GTK_IMPORT_ERROR}")


# ---------------------------------------------------------------------------
# Preferred web (WebKitGTK) host with GTK/Cairo fallback
# ---------------------------------------------------------------------------

_run_orb_gtk_legacy = run_orb


def web_orb_available() -> Tuple[bool, str]:
    try:
        from .orb_web import web_gui_available
        return web_gui_available()
    except Exception as e:
        try:
            from .orb_web import dist_index_path, GTK_AVAILABLE as _GTK, WEBKIT_AVAILABLE as _WK, GTK_IMPORT_ERROR as _ERR
            if not (_GTK and _WK):
                return False, f"GTK/WebKit2 unavailable: {_ERR}"
            p = dist_index_path()
            if not p.is_file():
                return False, f"Orb UI bundle missing: {p}"
        except Exception:
            pass
        return False, f"{type(e).__name__}: {e}"


def run_orb(inbox_root: Optional[str] = None, config: Any = None, debug: bool = False,
            data_dir: Optional[str] = None):
    """Launch AJ Orb GUI.

    Prefers the integrated WebKitGTK host (Claude UI bundle) when available;
    falls back to the legacy GTK/Cairo orb for environments without WebKit2
    or when the UI bundle is missing. Canonical inbox storage/behavior is
    preserved in both hosts.
    """
    ok, _reason = web_orb_available()
    if ok:
        from .orb_web import run_orb_web
        return run_orb_web(inbox_root=inbox_root, config=config, debug=debug, data_dir=data_dir)
    return _run_orb_gtk_legacy(inbox_root=inbox_root, config=config, debug=debug, data_dir=data_dir)


def _parse_args(argv: Optional[List[str]] = None):
    ap = argparse.ArgumentParser(prog="python -m aj.orb", description="Launch AJ capture orb GUI")
    ap.add_argument("--inbox-root", dest="inbox_root", default="", help="explicit inbox root path")
    ap.add_argument("--debug", action="store_true", help="verbose diagnostics to stderr")
    ap.add_argument("--check-gui", action="store_true", help="check GUI/runtime availability and exit")
    ap.add_argument("--gtk", dest="force_gtk", action="store_true", help="force legacy GTK/Cairo orb (fallback)")
    ap.add_argument("legacy_root", nargs="?", default="", help=argparse.SUPPRESS)
    return ap.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    if args.check_gui:
        web_ok, web_reason = web_orb_available()
        payload = {
            "ok": bool(GTK_AVAILABLE or web_ok),
            "gtk": bool(GTK_AVAILABLE),
            "webkit": bool(web_ok),
            "ui": "web" if web_ok else ("gtk" if GTK_AVAILABLE else "none"),
            "python": sys.executable,
        }
        if web_ok:
            try:
                from .orb_web import dist_index_path
                payload["dist"] = str(dist_index_path())
            except Exception:
                pass
        if not payload["ok"]:
            payload["error"] = web_reason or str(GTK_IMPORT_ERROR)
        print(json.dumps(payload), file=sys.stderr if not payload["ok"] else sys.stdout)
        raise SystemExit(0 if payload["ok"] else 1)
    root = args.inbox_root or args.legacy_root or None
    if getattr(args, "force_gtk", False):
        _run_orb_gtk_legacy(inbox_root=root, debug=args.debug)
    else:
        run_orb(inbox_root=root, debug=args.debug)
