"""Helpers to install/remove AJ Orb autostart for the current user.

Installation is explicit (not automatic). Generated entry uses the AJ project
checkout and prefers `python -m aj orb --system-python` so GTK can run via
system Python while AJ package/config/storage remain canonical.
"""
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

DESKTOP_ID = "aj-orb.desktop"


def desktop_entry(exec_cmd: str) -> str:
    return f"""[Desktop Entry]
Type=Application
Version=1.0
Name=AJ Orb
Comment=AJ floating capture orb for the personal knowledge inbox
Exec={exec_cmd}
Icon=emblem-documents
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""


def autostart_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))) / "autostart"


def default_exec_cmd() -> str:
    aj_root = Path(__file__).resolve().parent.parent
    py = sys.executable
    # Prefer smart launcher: tries current interpreter, falls back to system python for GTK.
    inner = (
        f"cd {shlex.quote(str(aj_root))} && "
        f"PYTHONPATH={shlex.quote(str(aj_root))}${{PYTHONPATH:+:$PYTHONPATH}} "
        f"{shlex.quote(py)} -m aj orb --system-python"
    )
    return f"/bin/bash -lc {shlex.quote(inner)}"


def install(exec_cmd: str | None = None) -> Path:
    if exec_cmd is None:
        exec_cmd = default_exec_cmd()
    d = autostart_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / DESKTOP_ID
    p.write_text(desktop_entry(exec_cmd), encoding="utf-8")
    return p


def remove() -> bool:
    p = autostart_dir() / DESKTOP_ID
    if p.exists():
        p.unlink()
        return True
    return False
