"""Test bootstrap: make ``aj`` importable without installing anything."""

from __future__ import annotations

import sys
from pathlib import Path

AJ_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = AJ_ROOT.parent

if str(AJ_ROOT) not in sys.path:
    sys.path.insert(0, str(AJ_ROOT))


def make_config(**overrides):
    """Config with no environment leakage and no on-disk writes."""
    from aj.config import load

    base = {
        "runtime": {"persist_tasks": False, "persist_memory": False},
        "core": {"require_verification_before_execute": True},
    }
    for key, value in overrides.items():
        if isinstance(value, dict):
            base.setdefault(key, {}).update(value)
    return load(env={}, overrides=base)
