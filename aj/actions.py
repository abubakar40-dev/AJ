"""Safe capabilities that execute inside AJ.

Only actions implemented in this module may run without an agent or a network.
They exist so the control plane can prove its full lifecycle locally: task ->
permission -> capability -> execution -> audit -> memory -> completion.

Nothing here touches the filesystem, the network, credentials or a sub-agent.
External capabilities (JARVIS tools, HELIX calling, Hermes skills) stay behind
their own ports and are never executed in-process.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from . import errors
from .capability import (
    AVAILABLE,
    OWNER_AJ,
    VERIFIED,
    CapabilityRegistry,
    CapabilitySpec,
)

ADAPTER_PREFIX = "internal:"

Action = Callable[[Mapping[str, Any]], Dict[str, Any]]


class InternalActions:
    """A small registry of in-process actions, keyed by adapter name."""

    def __init__(self, actions: Optional[Mapping[str, Action]] = None):
        self._actions: Dict[str, Action] = dict(actions or {})

    def register(self, name: str, action: Action) -> None:
        if not (name or "").strip():
            raise errors.AjError("an internal action needs a name", code=errors.CONFIG_INVALID)
        self._actions[name] = action

    def has(self, name: str) -> bool:
        return name in self._actions

    def names(self) -> List[str]:
        return sorted(self._actions)

    def run(self, name: str, arguments: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Run one action, normalising every failure into an :class:`AjError`."""
        action = self._actions.get(name)
        if action is None:
            raise errors.CapabilityNotFound(f"internal action {name!r} is not registered")
        try:
            result = action(dict(arguments or {}))
        except errors.AjError:
            raise
        except Exception as exc:  # a failing action is a failed task, never a pass
            raise errors.ExecutionFailed(
                f"internal action {name!r} failed: {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(result, dict):
            raise errors.ExecutionFailed(
                f"internal action {name!r} returned {type(result).__name__}, not a dict"
            )
        return result


# --- actions -------------------------------------------------------------
def echo(arguments: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the supplied text unchanged. A pure, side-effect-free action."""
    text = arguments.get("text", arguments.get("message", ""))
    return {"echo": str(text)}


def health_check(arguments: Mapping[str, Any]) -> Dict[str, Any]:
    """Report that the in-process foundation action path is alive."""
    return {"healthy": True, "component": "aj.foundation"}


def default_actions() -> InternalActions:
    return InternalActions({"echo": echo, "health_check": health_check})


# --- declarations --------------------------------------------------------
def specs() -> List[CapabilitySpec]:
    """The AJ-owned capabilities that back the internal actions."""
    return [
        CapabilitySpec(
            capability_id="aj.echo",
            name="Echo",
            description="Return the supplied text. Pure; no side effects.",
            owner_agent=OWNER_AJ,
            execution_adapter=ADAPTER_PREFIX + "echo",
            required_permissions=("read",),
            risk_level=0,
            availability=AVAILABLE,
            verification_status=VERIFIED,
            supported_inputs=("text",),
            supported_outputs=("echo",),
            replay_safe=True,
            retry_safe=True,
            source="aj/actions.py",
        ),
        CapabilitySpec(
            capability_id="aj.health_check",
            name="Foundation health check",
            description="Report that the local execution path is alive.",
            owner_agent=OWNER_AJ,
            execution_adapter=ADAPTER_PREFIX + "health_check",
            required_permissions=("read",),
            risk_level=0,
            availability=AVAILABLE,
            verification_status=VERIFIED,
            supported_outputs=("healthy", "component"),
            replay_safe=True,
            retry_safe=True,
            source="aj/actions.py",
        ),
    ]


def register_specs(registry: CapabilityRegistry,
                   declarations: Optional[Iterable[CapabilitySpec]] = None) -> int:
    """Add the internal capability declarations to a registry."""
    added = 0
    for spec in declarations if declarations is not None else specs():
        registry.register(spec)
        added += 1
    return added
