"""Execution boundary — where Hermes will attach.

AJ, JARVIS and HELIX do not call a skill runtime directly. They build an
:class:`~aj.contracts.ExecutionRequest`, AJ authorizes it, and an
:class:`ExecutionPort` implementation runs it. Today the only implementation in
production code is :class:`UnavailableExecutionAdapter`, which reports that no
runtime is attached. That is the honest state until the owner gives the HERMES
GREEN SIGNAL.

Why a port and not an import
----------------------------
Hermes-specific code must not spread through the ecosystem. The port is the only
place that knows a runtime exists; when Hermes is verified, a
``HermesExecutionAdapter`` implements this protocol and nothing else changes.

Skill registration rules
------------------------
A skill declares a permission *ceiling*. Registration refuses to expose a skill
that is not approved, has no recorded passing tests, or declares no verification
steps. Successful execution never widens the declared permissions.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Protocol, runtime_checkable

from . import errors
from .contracts import ExecutionRequest, ExecutionResult, SkillSpec


@runtime_checkable
class ExecutionPort(Protocol):
    """The only surface AJ needs from an execution runtime."""

    name: str

    def available(self) -> bool:  # pragma: no cover - protocol
        ...

    def describe(self) -> Dict[str, object]:  # pragma: no cover - protocol
        ...

    def execute(self, request: ExecutionRequest) -> ExecutionResult:  # pragma: no cover
        ...


class UnavailableExecutionAdapter:
    """The pre-Hermes runtime: present, explicit, and inert."""

    name = "none"

    def __init__(self, reason: str = "no execution runtime is attached"):
        self.reason = reason

    def available(self) -> bool:
        return False

    def describe(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "available": False,
            "reason": self.reason,
            "integration_status": "NOT ATTACHED",
            "requires": "HERMES GREEN SIGNAL from the project owner",
        }

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise errors.ExecutionUnavailable(self.reason)


class SkillRegistry:
    """Approved skills, and the reasons unapproved ones are withheld."""

    def __init__(self, skills: Optional[List[SkillSpec]] = None):
        self._skills: Dict[str, SkillSpec] = {}
        self._withheld: Dict[str, List[str]] = {}
        for skill in skills or []:
            self.register(skill)

    def register(self, skill: SkillSpec, *, require_approved: bool = True) -> bool:
        """Add a skill if it is safe to expose. Returns whether it was exposed."""
        reasons = skill.blocking_reasons() if require_approved else []
        if reasons:
            self._withheld[skill.skill_id] = reasons
            self._skills[skill.skill_id] = skill
            return False
        self._withheld.pop(skill.skill_id, None)
        self._skills[skill.skill_id] = skill
        return True

    def get(self, skill_id: str) -> SkillSpec:
        try:
            return self._skills[skill_id]
        except KeyError:
            raise errors.CapabilityNotFound(f"skill {skill_id!r} is not registered") from None

    def approved(self) -> List[SkillSpec]:
        return [s for s in self._skills.values()
                if s.approved and not s.blocking_reasons()]

    def withheld(self) -> Dict[str, List[str]]:
        return dict(self._withheld)

    def blocking_reasons(self, skill_id: str) -> List[str]:
        skill = self.get(skill_id)
        return self._withheld.get(skill_id, skill.blocking_reasons())

    def summary(self) -> Dict[str, object]:
        return {
            "total": len(self._skills),
            "approved": len(self.approved()),
            "withheld": sorted(self._withheld),
        }


def execute(port: ExecutionPort, request: ExecutionRequest) -> ExecutionResult:
    """Run one request through a port, converting surprises into a result.

    A port that raises is a failed execution, never a success. A port that
    returns without verification is reported as ``verified=False``.
    """
    if not port.available():
        raise errors.ExecutionUnavailable(
            f"execution runtime {port.name!r} is not available"
        )
    started = time.time()
    try:
        result = port.execute(request)
    except errors.AjError:
        raise
    except Exception as exc:  # defensive: a port must not leak raw exceptions
        return ExecutionResult(
            request_id=request.request_id,
            status="failed",
            error=errors.normalize(exc).to_dict(),
            started_at=started,
        )
    if not isinstance(result, ExecutionResult):
        return ExecutionResult(
            request_id=request.request_id,
            status="failed",
            error={"code": errors.EXECUTION_FAILED,
                   "message": "execution port returned a non-ExecutionResult"},
            started_at=started,
        )
    return result
