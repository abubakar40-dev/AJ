"""Import JARVIS's own capability catalogue into the AJ registry.

Why import instead of copy
--------------------------
JARVIS already declares 25 tool capabilities with risk tiers in
``JARVIS/core/capabilities.py``. Copying them here would create two authorities
that drift. Instead this adapter loads that module *by file path* (it is
dependency-free), translates its tiers into AJ permission levels, and registers
the result.

Nothing is written to JARVIS. The import is read-only and happens only when AJ is
built with ``capability.load_jarvis_registry`` enabled.

Verification status
-------------------
JARVIS capabilities are registered as ``implemented_unverified``: the November
2026 audit found the code reachable and the tests passing, but browser and
desktop automation were not demonstrated on this machine. Two entries carry a
more specific status because that audit produced evidence either way.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List, Optional

from ..capability import (
    AVAILABILITY_UNKNOWN,
    IMPLEMENTED_UNVERIFIED,
    PARTIAL,
    CapabilityRegistry,
    CapabilitySpec,
)
from ..permissions import level_from_tier

MODULE_NAME = "aj_jarvis_core_capabilities"

# Evidence from audit/2026-11-06 (JARVIS_COMPLETE_AUDIT.md, FEATURE_TO_CODE_TRACEABILITY.md).
_KNOWN_STATUS = {
    "browser_control": (PARTIAL, "18 declared actions; page/desktop reliability unverified"),
    "computer_control": (PARTIAL, "input synthesis present; reliability unverified"),
    "cmd_control": (IMPLEMENTED_UNVERIFIED, "arbitrary shell; consequential tier"),
    "send_message": (IMPLEMENTED_UNVERIFIED, "requires confirmation token"),
}

_EXECUTION_ADAPTER = "jarvis.tool"


def _load_module(jarvis_root: Path):
    path = jarvis_root / "core" / "capabilities.py"
    if not path.is_file():
        return None
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]
    spec = importlib.util.spec_from_file_location(MODULE_NAME, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(MODULE_NAME, None)
        return None
    return module


def load(jarvis_root: str | Path) -> List[CapabilitySpec]:
    """Return AJ capability specs translated from JARVIS's registry."""
    root = Path(jarvis_root).expanduser()
    module = _load_module(root)
    if module is None:
        return []
    specs: List[CapabilitySpec] = []
    for capability in module.all_capabilities().values():
        level = level_from_tier(capability.tier)
        status, note = _KNOWN_STATUS.get(
            capability.name, (IMPLEMENTED_UNVERIFIED, "")
        )
        if capability.forbidden_actions:
            note = (note + "; " if note else "") + (
                "forbidden actions: " + ", ".join(sorted(capability.forbidden_actions))
            )
        specs.append(
            CapabilitySpec(
                capability_id=f"jarvis.{capability.name}",
                name=capability.name,
                description=capability.description or capability.name,
                owner_agent="JARVIS",
                execution_adapter=_EXECUTION_ADAPTER,
                required_permissions=tuple(
                    ["tool." + capability.name]
                ),
                risk_level=level,
                availability=AVAILABILITY_UNKNOWN,
                verification_status=status,
                side_effects=("consequential tier",) if level >= 3 else (),
                forbidden=False,
                source=str(root / "core" / "capabilities.py"),
                notes=note,
            )
        )
    return specs


def load_into(registry: CapabilityRegistry, jarvis_root: str | Path) -> int:
    """Register JARVIS capabilities; returns how many were added."""
    specs = load(jarvis_root)
    for spec in specs:
        registry.register(spec)
    return len(specs)
