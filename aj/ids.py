"""Identifier generation.

Task ids are used in audit lines, agent requests and call records, so they are
sortable (timestamp first) and short enough to read aloud. They are not security
tokens and carry no authority.
"""

from __future__ import annotations

import datetime as _dt
import uuid

_TASK_PREFIX = "aj"


def new_task_id(prefix: str = _TASK_PREFIX) -> str:
    """Return a new sortable task id, e.g. ``aj_20261109T011500_1f3a9c2b``."""
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def new_child_id(parent_task_id: str) -> str:
    """Return a child task id that keeps its parent visible in the string."""
    parent = (parent_task_id or _TASK_PREFIX).strip()
    return f"{parent}/c_{uuid.uuid4().hex[:8]}"


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:10]}"


def new_skill_id(name: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in (name or "").lower()).strip("_")
    return f"skill_{slug or 'unnamed'}_{uuid.uuid4().hex[:6]}"
