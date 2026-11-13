"""Boundary contracts.

These are the shapes that cross trust boundaries:

    AgentRequest / AgentResult      AJ <-> JARVIS, AJ <-> HELIX
    ExecutionRequest / Result       AJ <-> execution runtime (Hermes, later)
    SkillSpec                       a reusable execution capability and its
                                    declared permissions

They are plain dataclasses with strict ``from_dict`` validation so a malformed
message is rejected at the edge instead of producing a half-executed task.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from . import errors, ids
from .permissions import validate_level

AGENT_STATUSES = (
    "accepted", "running", "completed", "failed", "cancelled", "rejected", "unknown",
)

SKILL_REVIEW_STATES = ("draft", "tested", "reviewed", "approved", "rejected", "revoked")


@dataclass
class AgentRequest:
    """One delegated unit of work handed to a sub-agent."""

    task_id: str
    goal: str
    assigned_agent: str
    parent_task_id: Optional[str] = None
    requester: str = "user"
    constraints: List[str] = field(default_factory=list)
    allowed_capabilities: List[str] = field(default_factory=list)
    approval_policy: str = "explicit"
    timeout_seconds: int = 120
    context_references: List[str] = field(default_factory=list)
    expected_output_schema: str = ""
    idempotency_key: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.task_id:
            raise errors.AjError("agent request needs a task id", code=errors.CONFIG_INVALID)
        if not (self.goal or "").strip():
            raise errors.AjError("agent request needs a goal", code=errors.CONFIG_INVALID)
        if not self.assigned_agent:
            raise errors.AjError("agent request needs an assigned agent",
                                 code=errors.CONFIG_INVALID)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentRequest":
        return cls(
            task_id=str(data.get("task_id") or ""),
            goal=str(data.get("goal") or ""),
            assigned_agent=str(data.get("assigned_agent") or ""),
            parent_task_id=data.get("parent_task_id"),
            requester=str(data.get("requester", "user")),
            constraints=list(data.get("constraints", []) or []),
            allowed_capabilities=list(data.get("allowed_capabilities", []) or []),
            approval_policy=str(data.get("approval_policy", "explicit")),
            timeout_seconds=int(data.get("timeout_seconds", 120)),
            context_references=list(data.get("context_references", []) or []),
            expected_output_schema=str(data.get("expected_output_schema", "")),
            idempotency_key=str(data.get("idempotency_key", "")),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class AgentResult:
    """What a sub-agent must return. Missing evidence is a failure, not a pass."""

    task_id: str
    agent: str
    status: str = "unknown"
    summary: str = ""
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    actions_not_taken: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_user_decision: bool = False
    started_at: float = 0.0
    finished_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.status not in AGENT_STATUSES:
            raise errors.AjError(
                f"unknown agent result status {self.status!r}; expected one of {AGENT_STATUSES}",
                code=errors.CONFIG_INVALID,
            )

    @property
    def ok(self) -> bool:
        return self.status == "completed"

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentResult":
        return cls(
            task_id=str(data.get("task_id") or ""),
            agent=str(data.get("agent") or ""),
            status=str(data.get("status", "unknown")),
            summary=str(data.get("summary", "")),
            artifacts=list(data.get("artifacts", []) or []),
            evidence=list(data.get("evidence", []) or []),
            actions_taken=list(data.get("actions_taken", []) or []),
            actions_not_taken=list(data.get("actions_not_taken", []) or []),
            errors=list(data.get("errors", []) or []),
            warnings=list(data.get("warnings", []) or []),
            requires_user_decision=bool(data.get("requires_user_decision", False)),
            started_at=float(data.get("started_at", 0.0)),
            finished_at=float(data.get("finished_at", time.time())),
        )


@dataclass
class ExecutionRequest:
    """A request to run one skill/action through the execution runtime."""

    request_id: str
    capability_id: str
    skill_id: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    task_id: str = ""
    requested_by: str = "AJ"
    permission_level: int = 1
    approval_token: str = ""
    timeout_seconds: int = 60
    dry_run: bool = False
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.request_id:
            raise errors.AjError("execution request needs a request id",
                                 code=errors.CONFIG_INVALID)
        if not self.capability_id:
            raise errors.AjError("execution request needs a capability id",
                                 code=errors.CONFIG_INVALID)
        validate_level(self.permission_level)

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        data.pop("approval_token", None)  # never serialise an approval token
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionRequest":
        return cls(
            request_id=str(data.get("request_id") or ""),
            capability_id=str(data.get("capability_id") or ""),
            skill_id=str(data.get("skill_id", "")),
            arguments=dict(data.get("arguments", {}) or {}),
            task_id=str(data.get("task_id", "")),
            requested_by=str(data.get("requested_by", "AJ")),
            permission_level=int(data.get("permission_level", 1)),
            approval_token=str(data.get("approval_token", "")),
            timeout_seconds=int(data.get("timeout_seconds", 60)),
            dry_run=bool(data.get("dry_run", False)),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class ExecutionResult:
    """The outcome of one execution, with explicit uncertainty."""

    request_id: str
    status: str = "unknown"          # completed | failed | rejected | timeout | unknown
    output: Any = None
    error: Optional[Dict[str, Any]] = None
    side_effects: List[Dict[str, Any]] = field(default_factory=list)
    verified: bool = False
    verification: Dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.status not in ("completed", "failed", "rejected", "timeout", "unknown"):
            raise errors.AjError(
                f"unknown execution status {self.status!r}", code=errors.CONFIG_INVALID
            )

    @property
    def ok(self) -> bool:
        return self.status == "completed"

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionResult":
        return cls(
            request_id=str(data.get("request_id") or ""),
            status=str(data.get("status", "unknown")),
            output=data.get("output"),
            error=data.get("error"),
            side_effects=list(data.get("side_effects", []) or []),
            verified=bool(data.get("verified", False)),
            verification=dict(data.get("verification", {}) or {}),
            started_at=float(data.get("started_at", 0.0)),
            finished_at=float(data.get("finished_at", time.time())),
        )


@dataclass
class SkillSpec:
    """A reusable execution capability and the permissions it declares.

    A skill is *inert* until it is approved. Approval does not grant new
    permissions: the declared set is a ceiling, and AJ's authorizer still decides
    per invocation.
    """

    skill_id: str
    name: str
    description: str
    entrypoint: str = ""
    version: str = "0.1.0"
    required_capabilities: List[str] = field(default_factory=list)
    required_permissions: List[int] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    side_effects: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)
    verification_steps: List[str] = field(default_factory=list)
    approval_required: bool = True
    review_status: str = "draft"
    tests: List[Dict[str, Any]] = field(default_factory=list)
    created_by: str = "unknown"
    created_at: float = field(default_factory=time.time)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.skill_id:
            raise errors.AjError("skill needs an id", code=errors.CONFIG_INVALID)
        if self.review_status not in SKILL_REVIEW_STATES:
            raise errors.AjError(
                f"unknown skill review status {self.review_status!r}", code=errors.CONFIG_INVALID
            )
        for level in self.required_permissions:
            validate_level(int(level))

    @property
    def max_permission_level(self) -> int:
        return max([int(p) for p in self.required_permissions], default=0)

    @property
    def approved(self) -> bool:
        return self.review_status == "approved"

    @property
    def has_passing_tests(self) -> bool:
        if not self.tests:
            return False
        return all(str(t.get("status", "")).upper() == "PASS" for t in self.tests)

    def blocking_reasons(self) -> List[str]:
        """Why this skill cannot be exposed to the system yet."""
        reasons: List[str] = []
        if self.review_status != "approved":
            reasons.append(f"review_status is {self.review_status!r}, not 'approved'")
        if not self.tests:
            reasons.append("no recorded tests")
        elif not self.has_passing_tests:
            reasons.append("not every recorded test passed")
        if self.max_permission_level >= 4 and not self.approval_required:
            reasons.append("a level-4 skill must keep approval_required=True")
        if not self.verification_steps:
            reasons.append("no verification steps declared")
        return reasons

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillSpec":
        return cls(
            skill_id=str(data.get("skill_id") or ""),
            name=str(data.get("name") or ""),
            description=str(data.get("description") or ""),
            entrypoint=str(data.get("entrypoint", "")),
            version=str(data.get("version", "0.1.0")),
            required_capabilities=list(data.get("required_capabilities", []) or []),
            required_permissions=[int(p) for p in (data.get("required_permissions", []) or [])],
            inputs=dict(data.get("inputs", {}) or {}),
            outputs=dict(data.get("outputs", {}) or {}),
            side_effects=list(data.get("side_effects", []) or []),
            failure_modes=list(data.get("failure_modes", []) or []),
            verification_steps=list(data.get("verification_steps", []) or []),
            approval_required=bool(data.get("approval_required", True)),
            review_status=str(data.get("review_status", "draft")),
            tests=list(data.get("tests", []) or []),
            created_by=str(data.get("created_by", "unknown")),
            created_at=float(data.get("created_at", time.time())),
            notes=str(data.get("notes", "")),
        )


def new_request_id() -> str:
    return ids.new_task_id("exec")
