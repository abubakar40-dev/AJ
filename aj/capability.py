"""Capability registry.

The registry answers, for the whole ecosystem: what can this system actually do,
who owns it, how risky is it, and how much has it been verified?

It is metadata, not an implementation. A capability names an ``execution_adapter``
which is resolved by the owning agent (or by the execution port once Hermes is
attached). AJ never imports a tool.

Honesty rules baked into the model
----------------------------------
* ``verification_status`` starts at ``implemented_unverified`` unless evidence is
  recorded. Code existing is not evidence of working behaviour.
* ``availability`` is about the live environment, not intent: a capability whose
  bridge is not running is ``unavailable`` even though its code exists.
* Registering the same id twice with different metadata is an error rather than a
  silent overwrite, so a second definition cannot quietly win.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import errors
from .permissions import validate_level

OWNER_AJ = "AJ"
OWNER_JARVIS = "JARVIS"
OWNER_HELIX = "HELIX"
OWNER_HERMES = "HERMES"

OWNERS = (OWNER_AJ, OWNER_JARVIS, OWNER_HELIX, OWNER_HERMES)

AVAILABLE = "available"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"
AVAILABILITY_UNKNOWN = "unknown"

VERIFIED = "verified"
IMPLEMENTED_UNVERIFIED = "implemented_unverified"
PARTIAL = "partial"
EXPERIMENTAL = "experimental"
BROKEN = "broken"
STUB = "stub"
PLANNED = "planned"
UNKNOWN = "unknown"

VERIFICATION_STATES = (
    VERIFIED, IMPLEMENTED_UNVERIFIED, PARTIAL, EXPERIMENTAL, BROKEN, STUB, PLANNED, UNKNOWN,
)
AVAILABILITY_STATES = (AVAILABLE, DEGRADED, UNAVAILABLE, AVAILABILITY_UNKNOWN)


@dataclass(frozen=True)
class CapabilitySpec:
    """One declared thing the ecosystem can do."""

    capability_id: str
    name: str
    description: str
    owner_agent: str
    execution_adapter: str
    version: str = "1"
    required_permissions: Tuple[str, ...] = ()
    risk_level: int = 1
    availability: str = AVAILABILITY_UNKNOWN
    verification_status: str = IMPLEMENTED_UNVERIFIED
    supported_inputs: Tuple[str, ...] = ()
    supported_outputs: Tuple[str, ...] = ()
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    side_effects: Tuple[str, ...] = ()
    failure_modes: Tuple[str, ...] = ()
    health: str = "unknown"
    forbidden: bool = False
    # Recovery may replay this capability only when it is explicitly declared
    # safe. The default is deliberately false.
    replay_safe: bool = False
    # Retrying a failed task is opt-in by capability. Default false.
    retry_safe: bool = False
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.capability_id:
            raise errors.AjError("capability needs an id", code=errors.CONFIG_INVALID)
        if self.owner_agent not in OWNERS:
            raise errors.AjError(
                f"{self.capability_id}: owner must be one of {OWNERS}, got {self.owner_agent!r}",
                code=errors.CONFIG_INVALID,
            )
        validate_level(self.risk_level)
        if self.availability not in AVAILABILITY_STATES:
            raise errors.AjError(
                f"{self.capability_id}: unknown availability {self.availability!r}",
                code=errors.CONFIG_INVALID,
            )
        if self.verification_status not in VERIFICATION_STATES:
            raise errors.AjError(
                f"{self.capability_id}: unknown verification status "
                f"{self.verification_status!r}",
                code=errors.CONFIG_INVALID,
            )

    @property
    def executable(self) -> bool:
        """Can AJ ask for this right now?"""
        return (
            not self.forbidden
            and self.availability in (AVAILABLE, DEGRADED)
            and self.verification_status not in (BROKEN, STUB, PLANNED)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "owner_agent": self.owner_agent,
            "execution_adapter": self.execution_adapter,
            "required_permissions": list(self.required_permissions),
            "risk_level": self.risk_level,
            "availability": self.availability,
            "verification_status": self.verification_status,
            "supported_inputs": list(self.supported_inputs),
            "supported_outputs": list(self.supported_outputs),
            "input_schema": dict(self.input_schema or {}),
            "output_schema": dict(self.output_schema or {}),
            "side_effects": list(self.side_effects),
            "failure_modes": list(self.failure_modes),
            "health": self.health,
            "forbidden": self.forbidden,
            "replay_safe": self.replay_safe,
            "retry_safe": self.retry_safe,
            "source": self.source,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, source: str = "") -> "CapabilitySpec":
        try:
            return cls(
                capability_id=str(data["capability_id"]),
                name=str(data.get("name", data["capability_id"])),
                description=str(data.get("description", "")),
                owner_agent=str(data["owner_agent"]),
                execution_adapter=str(data.get("execution_adapter", "")),
                version=str(data.get("version", "1")),
                required_permissions=tuple(data.get("required_permissions", ()) or ()),
                risk_level=int(data.get("risk_level", 1)),
                availability=str(data.get("availability", AVAILABILITY_UNKNOWN)),
                verification_status=str(
                    data.get("verification_status", IMPLEMENTED_UNVERIFIED)
                ),
                supported_inputs=tuple(data.get("supported_inputs", ()) or ()),
                supported_outputs=tuple(data.get("supported_outputs", ()) or ()),
                input_schema=dict(data.get("input_schema", {}) or {}),
                output_schema=dict(data.get("output_schema", {}) or {}),
                side_effects=tuple(data.get("side_effects", ()) or ()),
                failure_modes=tuple(data.get("failure_modes", ()) or ()),
                health=str(data.get("health", "unknown")),
                forbidden=bool(data.get("forbidden", False)),
                replay_safe=bool(data.get("replay_safe", False)),
                retry_safe=bool(data.get("retry_safe", False)),
                source=source or str(data.get("source", "")),
                notes=str(data.get("notes", "")),
            )
        except KeyError as exc:
            raise errors.ConfigError(f"capability declaration missing {exc}") from exc


class CapabilityRegistry:
    """Collection of :class:`CapabilitySpec` keyed by id."""

    def __init__(self, specs: Iterable[CapabilitySpec] = ()):
        self._specs: Dict[str, CapabilitySpec] = {}
        for spec in specs:
            self.register(spec)

    # --- mutation --------------------------------------------------------
    def register(self, spec: CapabilitySpec, *, replace: bool = False) -> CapabilitySpec:
        existing = self._specs.get(spec.capability_id)
        if existing is not None:
            if existing == spec:
                return existing
            if not replace:
                raise errors.AjError(
                    f"capability {spec.capability_id!r} is already registered with "
                    "different metadata; pass replace=True only for a deliberate redefinition",
                    code=errors.CONFIG_INVALID,
                )
        self._specs[spec.capability_id] = spec
        return spec

    def register_many(self, specs: Iterable[CapabilitySpec], *, replace: bool = False) -> None:
        for spec in specs:
            self.register(spec, replace=replace)

    def set_availability(self, capability_id: str, availability: str) -> CapabilitySpec:
        spec = self.get(capability_id)
        if availability not in AVAILABILITY_STATES:
            raise errors.AjError(
                f"unknown availability {availability!r}", code=errors.CONFIG_INVALID
            )
        updated = CapabilitySpec(**{**spec.__dict__, "availability": availability})
        self._specs[capability_id] = updated
        return updated

    def set_verification(self, capability_id: str, status: str) -> CapabilitySpec:
        spec = self.get(capability_id)
        if status not in VERIFICATION_STATES:
            raise errors.AjError(
                f"unknown verification status {status!r}", code=errors.CONFIG_INVALID
            )
        updated = CapabilitySpec(**{**spec.__dict__, "verification_status": status})
        self._specs[capability_id] = updated
        return updated

    # --- reading ---------------------------------------------------------
    def get(self, capability_id: str) -> CapabilitySpec:
        try:
            return self._specs[capability_id]
        except KeyError:
            raise errors.CapabilityNotFound(
                f"capability {capability_id!r} is not registered"
            ) from None

    def find(self, capability_id: str) -> Optional[CapabilitySpec]:
        return self._specs.get(capability_id)

    def all(self) -> List[CapabilitySpec]:
        return [self._specs[k] for k in sorted(self._specs)]

    def by_owner(self, owner: str) -> List[CapabilitySpec]:
        return [s for s in self.all() if s.owner_agent == owner.upper()]

    def executable(self, owner: Optional[str] = None) -> List[CapabilitySpec]:
        return [
            s for s in self.all()
            if s.executable and (owner is None or s.owner_agent == owner.upper())
        ]

    def requiring(self, permission: str) -> List[CapabilitySpec]:
        return [s for s in self.all() if permission in s.required_permissions]

    def summary(self) -> Dict[str, Any]:
        """Counts for diagnostics and the readiness report."""
        by_owner: Dict[str, int] = {}
        by_verification: Dict[str, int] = {}
        for spec in self.all():
            by_owner[spec.owner_agent] = by_owner.get(spec.owner_agent, 0) + 1
            by_verification[spec.verification_status] = (
                by_verification.get(spec.verification_status, 0) + 1
            )
        return {
            "total": len(self._specs),
            "by_owner": by_owner,
            "by_verification": by_verification,
            "executable": len(self.executable()),
        }

    def to_dict(self) -> List[Dict[str, Any]]:
        return [spec.to_dict() for spec in self.all()]

    # --- loading ---------------------------------------------------------
    @classmethod
    def load_json(cls, path: str | Path) -> "CapabilityRegistry":
        """Load declarations from a JSON file of the form ``{"capabilities": [...]}``."""
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise errors.ConfigError(f"capability file not found: {path}") from None
        except ValueError as exc:
            raise errors.ConfigError(f"{path}: invalid JSON: {exc}") from exc
        entries = raw.get("capabilities", raw) if isinstance(raw, dict) else raw
        if not isinstance(entries, list):
            raise errors.ConfigError(f"{path}: expected a list of capabilities")
        return cls(CapabilitySpec.from_dict(e, source=str(path)) for e in entries)
