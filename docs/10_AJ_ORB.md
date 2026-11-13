# 10 — AJ Orb (Desktop Capture Interface)

**Status:** IMPLEMENTED (WebKitGTK Claude UI host + canonical backend wiring) / AUTOMATED VERIFIED / **LIVE DESKTOP VERIFICATION REQUIRED**  
**Date:** 2026-11-11 (web UI integration checkpoint)  
**Scope:** AJ Orb subsystem + minimum supporting AJ interfaces (CLI, inbox storage resolution, launch helpers). Selected Claude Sonnet 5.5 UI integrated as the presentation layer; AJ Python remains the authoritative backend.

## Purpose

AJ Orb is the lightweight desktop capture front-end for the canonical AJ Knowledge Inbox. It captures files, URLs, and clipboard/text content into the same durable `InboxStore` used by `aj inbox` and worker flows (no duplicate inbox/queue/database).

## Architecture (current)

- **Integrated UI (preferred):** vendored React/Vite single-file UI in `AJ/orb_ui/` (`dist/index.html`, 292.77 kB) embedded in **WebKitGTK 4.1 + GTK3** by `AJ/aj/orb_web.py`. The UI is presentation-only and communicates via `webkit.messageHandlers.aj` (intents) and host-pushed state (`__AJ_SET_STATE`), region/input-shape hints, and host drop events. Original generated UI remains preserved in `aj-orb-ui-generation/`.
- **Desktop host/backend:** Python host owns windowing (transparent undecorated always-on-top overlay, dynamic input regions), drag-and-drop (`text/uri-list`/files/URLs/text), native file picker, clipboard paste, open inbox/storage, quit, position persistence, and a background capture/process/retry worker. All operations use canonical inbox APIs (`InboxStore`, `capture_file/url/text`, `process_capture`, `retry_failed`, `inbox_summary`) with no parallel storage.
- **Legacy fallback:** GTK3/Cairo orb (`AJ/aj/orb.py` implementation) retained as fallback when WebKit UI/bundle unavailable, or forced via `python -m aj.orb --gtk`.
- **CLI/runtime integration:** `aj orb` / `python -m aj orb` resolve canonical inbox root, preflight storage writability, prefer web host when available, and fall back to system Python GTK runtime when the current interpreter lacks GUI deps. Flags preserved: `--inbox-root`, `--debug`, `--check-gui`, `--system-python`, `--json` (plus `--gtk` fallback). `--check-gui` reports `ok`, `gtk`, `webkit`, `ui`, `inbox_root`, and `dist` when available.
- **Honest capabilities:** retry and capture/open actions are real; pause/cancel/chat/byte-progress are not faked (disabled when unsupported). Status mapping is truthful (queued/processing/uploading-active/ready-completed/failed; archived excluded from active UI snapshot).

## Canonical storage/config

Resolution precedence (unchanged): explicit arg/override > `AJ_INBOX_ROOT` > `config.core.inbox_root` > `config.core.data_dir/knowledge-inbox` > legacy default `~/.local/share/aj/knowledge-inbox`. No silent fallback to Home when configured/explicit storage is unavailable; hosts preflight writability and surface errors.

- **Observed active root (no override):** `~/.local/share/aj/knowledge-inbox` (Home inbox preserved, **not migrated**).
- **Workspace-central storage:** set `AJ_INBOX_ROOT` or `core.inbox_root`/`core.data_dir` to an approved writable path under the AI workspace (e.g. `.../AJ/data/knowledge-inbox`), ensure mount/WAL suitability, then launch with that root. Migration requires quiesced stop/backup/copy/integrity/reopen and explicit approval; keep Home rollback until verified.

## GNOME Wayland notes (honest)

Target: GNOME on Wayland (Mutter). Session evidence shows Wayland session with XWayland/GDK X11 display available (`DISPLAY=:0`, `GDK_BACKEND=x11` in observed environment), which may help window/input behavior, but **not proven** as sufficient for full acceptance.

**VERIFICATION REQUIRED on live desktop:** visibility/accessibility on focus/app/workspace/maximize/lock/unlock/suspend, cross-app Nautilus drag-and-drop acceptance, notification rendering, click-through/input-region correctness, monitor/scaling behavior, restart position persistence UX, and long-run CPU/RAM/responsiveness (i5-7300U, 8 GB, Intel HD 620). If the floating overlay is unsuitable under Mutter, a GNOME-native/hybrid architecture (e.g. Nautilus/clipboard/chooser flows, or approved Shell extension + IPC) must be chosen and proven rather than forcing GTK behavior.

Reliable fallback/complement paths remain: `aj inbox` CLI, hardened `AJ/scripts/send_to_aj.py`, Nautilus Scripts installer (`AJ/scripts/install_nautilus_send_to_aj.sh`, prepared, **not host-installed**), clipboard/file chooser/URL/text capture.

## Launch / checks

From `AJ/`:

```bash
# GUI/runtime check (current interpreter)
PYTHONPATH=. .venv/bin/python -m aj orb --check-gui --json

# Preferred integrated UI check/launch (system Python with GTK3+WebKit2 4.1 + bundle)
PYTHONPATH=. /usr/bin/python3 -m aj.orb --check-gui
PYTHONPATH=. /usr/bin/python3 -m aj orb --inbox-root "<canonical-inbox-root>"

# Auto-fallback launch from venv entrypoint
PYTHONPATH=. .venv/bin/python -m aj orb --system-python

# Force legacy GTK/Cairo orb (fallback)
PYTHONPATH=. /usr/bin/python3 -m aj.orb --gtk --inbox-root "<canonical-inbox-root>"
```

## Verification status (2026-11-11)

- **AUTOMATED VERIFIED:** `cd AJ && PYTHONPATH=. .venv/bin/python -m pytest -q` → **252 passed, 0 failed**. `cd AJ && PYTHONPATH=. .venv/bin/python -m aj --check` → **exit 0, ok true**, Hermes **NOT ATTACHED**.
- **AUTOMATED VERIFIED (web host):** system Python `python -m aj.orb --check-gui` reports `ok/gtk/webkit/ui=web` with `dist`; import/mapping/snapshot smoke and `tests/test_orb_web_integration.py` pass; UI bundle built (`AJ/orb_ui/dist/index.html`).
- **NOT VERIFIED:** live interactive GNOME Wayland acceptance, real cross-app DnD, screenshots of running UI, notifications, long-run behavior, Nautilus host integration, and real Home→workspace migration.
