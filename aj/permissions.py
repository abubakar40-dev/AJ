"""Five-level permission model and the approval gate.

Levels
------
0  read-only          Observe. Safe unattended.
1  low-risk action    Changes this machine, reversible. Safe unattended.
2  user-authorized    A user asked for it in this task; no extra prompt.
3  consequential      Leaves the machine or is hard to undo: calls, messages,
                      purchases, destructive file operations.
4  highly sensitive   Needs a fresh, explicit confirmation immediately before
                      execution, for this exact action.

A capability may additionally be marked ``forbidden``: never allowed at any
level, with or without approval (e.g. taking an assessment on the user's LMS).

Enforcement rules
-----------------
* The level of an action is a property of the capability, not of the caller.
* An agent's confidence is never authorization.
* A level-4 (or forbidden) action cannot be approved by a task-level grant.
* Approval is single-use, bound to the capability and to a canonical
  fingerprint of the requested action, and expires.

This module is deliberately state-light: :class:`ApprovalGate` holds the tokens,
:class:`Authorizer` is pure and therefore trivial to test.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from . import errors

LEVEL_READ = 0
LEVEL_LOW_RISK = 1
LEVEL_USER_AUTHORIZED = 2
LEVEL_CONSEQUENTIAL = 3
LEVEL_SENSITIVE = 4

ALLOW = "allow"
CONFIRM = "confirm"
DENY = "deny"

LEVELS: Dict[int, Dict[str, Any]] = {
    LEVEL_READ: {
        "name": "read-only",
        "description": "Observes state; changes nothing.",
        "unattended": True,
        "needs_approval": False,
    },
    LEVEL_LOW_RISK: {
        "name": "low-risk action",
        "description": "Local and reversible.",
        "unattended": True,
        "needs_approval": False,
    },
    LEVEL_USER_AUTHORIZED: {
        "name": "user-authorized action",
        "description": "Performed because the user asked for it in this task.",
        "unattended": False,
        "needs_approval": False,
    },
    LEVEL_CONSEQUENTIAL: {
        "name": "consequential action",
        "description": "Visible outside this machine, spends money, or is hard to undo.",
        "unattended": False,
        "needs_approval": True,
    },
    LEVEL_SENSITIVE: {
        "name": "highly sensitive action",
        "description": "Requires explicit confirmation immediately before execution.",
        "unattended": False,
        "needs_approval": True,
    },
}

# Mapping from the tier names used by JARVIS/core/capabilities.py. Kept as a
# translation table rather than a second registry so there is one authority per
# level of the system.
_TIER_TO_LEVEL = {
    "read": LEVEL_READ,
    "local-write": LEVEL_LOW_RISK,
    "consequential": LEVEL_CONSEQUENTIAL,
    "forbidden": LEVEL_SENSITIVE,
}


def level_from_tier(tier: str) -> int:
    """Translate a JARVIS risk tier into an AJ permission level."""
    level = _TIER_TO_LEVEL.get((tier or "").strip().lower())
    if level is None:
        raise errors.AjError(f"unknown risk tier {tier!r}", code=errors.CONFIG_INVALID)
    return level


def level_name(level: int) -> str:
    return LEVELS.get(int(level), {}).get("name", f"level-{level}")


def validate_level(level: int) -> int:
    level = int(level)
    if level not in LEVELS:
        raise errors.AjError(f"permission level {level} is not defined", code=errors.CONFIG_INVALID)
    return level


# --- approval ------------------------------------------------------------
DEFAULT_TTL_SECONDS = 300
MAX_OUTSTANDING = 256


def canonical_fingerprint(capability_id: str, payload: Optional[Mapping[str, Any]]) -> str:
    """Stable hash of the exact action being approved."""
    try:
        body = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:  # pragma: no cover - defensive
        body = repr(sorted((payload or {}).items()))
    return hashlib.sha256(f"{capability_id}\x00{body}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Approval:
    """A user's approval for one specific capability invocation."""

    token: str
    capability_id: str
    fingerprint: str
    issued_at: float
    expires_at: float
    reason: str = ""

    @property
    def expired(self) -> bool:
        return self.expires_at <= time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "fingerprint": self.fingerprint,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "reason": self.reason,
        }


class ApprovalGate:
    """Single-use approval tokens bound to capability + action payload."""

    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS, clock=time.time):
        self._ttl = max(1, int(ttl))
        self._clock = clock
        self._lock = threading.Lock()
        self._tokens: Dict[str, Approval] = {}

    def issue(self, capability_id: str, payload: Optional[Mapping[str, Any]] = None,
              reason: str = "", ttl: Optional[int] = None) -> Approval:
        if not capability_id:
            raise errors.AjError("approval needs a capability id", code=errors.APPROVAL_INVALID)
        now = self._clock()
        approval = Approval(
            token=secrets.token_urlsafe(24),
            capability_id=capability_id,
            fingerprint=canonical_fingerprint(capability_id, payload),
            issued_at=now,
            expires_at=now + max(1, int(ttl if ttl is not None else self._ttl)),
            reason=(reason or "")[:200],
        )
        with self._lock:
            self._evict_locked(now)
            self._tokens[approval.token] = approval
        return approval

    def _evict_locked(self, now: float) -> None:
        for token in [t for t, a in self._tokens.items() if a.expires_at <= now]:
            self._tokens.pop(token, None)
        while len(self._tokens) >= MAX_OUTSTANDING:
            oldest = min(self._tokens, key=lambda t: self._tokens[t].issued_at)
            self._tokens.pop(oldest, None)

    def consume(self, token: str, capability_id: str,
                payload: Optional[Mapping[str, Any]] = None) -> Tuple[bool, str]:
        """Validate and burn a token. Returns ``(ok, reason)``."""
        if not token:
            return False, "no approval token supplied"
        now = self._clock()
        with self._lock:
            approval = self._tokens.get(token)
            if approval is None:
                return False, "unknown or already used approval"
            if approval.expires_at <= now:
                self._tokens.pop(token, None)
                return False, "approval expired"
            if approval.capability_id != capability_id:
                return False, "approval was issued for a different capability"
            if approval.fingerprint != canonical_fingerprint(capability_id, payload):
                return False, "the action changed after it was approved"
            self._tokens.pop(token, None)
        return True, "ok"

    def pending(self) -> int:
        now = self._clock()
        with self._lock:
            return sum(1 for a in self._tokens.values() if a.expires_at > now)

    def revoke_all(self) -> int:
        with self._lock:
            count = len(self._tokens)
            self._tokens.clear()
        return count


# --- decision ------------------------------------------------------------
@dataclass(frozen=True)
class PolicyDecision:
    """The result of authorizing one capability invocation."""

    outcome: str
    capability_id: str
    level: int
    reason: str
    requires_approval: bool = False
    forbidden: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.outcome == ALLOW

    @property
    def denied(self) -> bool:
        return self.outcome == DENY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "capability_id": self.capability_id,
            "level": self.level,
            "reason": self.reason,
            "requires_approval": self.requires_approval,
            "forbidden": self.forbidden,
            "metadata": self.metadata,
        }


class Authorizer:
    """Turn a capability's declared risk into allow / confirm / deny.

    ``unattended_ceiling`` is the highest level that may run with no human in the
    loop. Defaults to level 1, which matches the approved policy: reads and local
    reversible work run alone, everything else needs a person.
    """

    def __init__(self, unattended_ceiling: int = LEVEL_LOW_RISK,
                 gate: Optional[ApprovalGate] = None):
        self.unattended_ceiling = validate_level(unattended_ceiling)
        self.gate = gate or ApprovalGate()

    def authorize(
        self,
        capability,
        *,
        payload: Optional[Mapping[str, Any]] = None,
        approval: Optional[str] = None,
        user_requested: bool = False,
        actor: str = "user",
    ) -> PolicyDecision:
        capability_id = getattr(capability, "capability_id", "")
        level = validate_level(getattr(capability, "risk_level", LEVEL_LOW_RISK))
        forbidden = bool(getattr(capability, "forbidden", False))

        if forbidden:
            return PolicyDecision(
                outcome=DENY, capability_id=capability_id, level=level,
                reason="this capability is permanently disabled by policy",
                forbidden=True,
            )

        if level <= self.unattended_ceiling:
            return PolicyDecision(
                outcome=ALLOW, capability_id=capability_id, level=level,
                reason=f"{level_name(level)}: allowed unattended",
            )

        if level >= LEVEL_CONSEQUENTIAL:
            if not approval:
                return PolicyDecision(
                    outcome=CONFIRM, capability_id=capability_id, level=level,
                    reason="consequential action needs explicit approval for this exact action",
                    requires_approval=True,
                )
            ok, why = self.gate.consume(approval, capability_id, payload)
            if not ok:
                return PolicyDecision(
                    outcome=DENY, capability_id=capability_id, level=level,
                    reason=f"approval rejected: {why}", requires_approval=True,
                )
            return PolicyDecision(
                outcome=ALLOW, capability_id=capability_id, level=level,
                reason="approved by " + str(actor), metadata={"approval_reason": why},
            )

        # level 2: the user asked for it in this task, but never unattended.
        if user_requested:
            return PolicyDecision(
                outcome=ALLOW, capability_id=capability_id, level=level,
                reason="explicitly requested in this task",
            )
        return PolicyDecision(
            outcome=CONFIRM, capability_id=capability_id, level=level,
            reason="needs an explicit request from the user",
            requires_approval=False,
        )
