"""Calling foundation — the contracts HELIX owns and AJ supervises.

What is here
------------
* the call state machine from the approved calling architecture, with an explicit
  ``UNKNOWN`` state for "the adapter cannot tell us";
* ports for contact resolution and the device bridge, so no KDE Connect or
  GSConnect call is scattered through the core;
* :class:`CallingService`, which enforces "confirm before dialing", prevents
  duplicate calls, and refuses to claim a state the bridge could not report.

What is deliberately absent
---------------------------
No audio handling, no SIP/VoIP provider, no auto-answer, no recording, no
emergency-call automation. Voice conversation and a real phone call are separate
capabilities and must not share state.

Verified environment note (2026-11-09): GSConnect is running and one phone
("Redmi A3") is paired and connected. That proves a device bridge exists; it does
**not** prove that dialing, call events or audio routing work through it. Those
remain UNVERIFIED until tested through the adapter.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from . import errors, ids


class CallState(str, Enum):
    IDLE = "IDLE"
    REQUESTED = "REQUESTED"
    CONTACT_RESOLVING = "CONTACT_RESOLVING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    PREPARING = "PREPARING"
    DIALING = "DIALING"
    RINGING = "RINGING"
    CONNECTED = "CONNECTED"
    ENDED = "ENDED"
    BUSY = "BUSY"
    NO_ANSWER = "NO_ANSWER"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"

    @property
    def terminal(self) -> bool:
        return self in {
            CallState.ENDED, CallState.BUSY, CallState.NO_ANSWER,
            CallState.FAILED, CallState.CANCELLED,
        }


CALL_TRANSITIONS: Dict[CallState, tuple] = {
    CallState.IDLE: (CallState.REQUESTED,),
    CallState.REQUESTED: (CallState.CONTACT_RESOLVING, CallState.FAILED, CallState.CANCELLED),
    CallState.CONTACT_RESOLVING: (
        CallState.AWAITING_CONFIRMATION, CallState.FAILED, CallState.CANCELLED,
    ),
    CallState.AWAITING_CONFIRMATION: (
        CallState.PREPARING, CallState.CANCELLED, CallState.FAILED,
    ),
    CallState.PREPARING: (CallState.DIALING, CallState.FAILED, CallState.CANCELLED),
    CallState.DIALING: (
        CallState.RINGING, CallState.CONNECTED, CallState.BUSY, CallState.NO_ANSWER,
        CallState.FAILED, CallState.UNKNOWN, CallState.CANCELLED,
    ),
    CallState.RINGING: (
        CallState.CONNECTED, CallState.NO_ANSWER, CallState.FAILED, CallState.UNKNOWN,
        CallState.CANCELLED,
    ),
    CallState.CONNECTED: (CallState.ENDED, CallState.UNKNOWN),
    CallState.UNKNOWN: (CallState.CONNECTED, CallState.ENDED, CallState.FAILED),
    CallState.ENDED: (),
    CallState.BUSY: (),
    CallState.NO_ANSWER: (),
    CallState.FAILED: (),
    CallState.CANCELLED: (),
}


@dataclass(frozen=True)
class Contact:
    """A resolved contact. ``phone`` is never logged in full by callers."""

    contact_id: str
    display_name: str
    phone: str
    source: str = "unknown"

    def masked(self) -> str:
        digits = "".join(ch for ch in self.phone if ch.isdigit())
        if len(digits) <= 4:
            return "•" * len(digits)
        return f"{'•' * (len(digits) - 4)}{digits[-4:]}"

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "display_name": self.display_name,
            "phone_masked": self.masked(),
            "source": self.source,
        }


class AmbiguousContact(errors.CallingError):
    """More than one contact matched. The caller must ask, never guess."""

    code = errors.CALLING_AMBIGUOUS_CONTACT

    def __init__(self, query: str, candidates: List[Contact]):
        super().__init__(
            f"{len(candidates)} contacts match {query!r}; ask the user which one",
            code=errors.CALLING_AMBIGUOUS_CONTACT,
            detail={"candidates": [c.to_public_dict() for c in candidates]},
        )
        self.candidates = candidates


class ContactResolver(Protocol):
    """HELIX-side contact lookup."""

    def resolve(self, query: str) -> List[Contact]:  # pragma: no cover - protocol
        ...


@dataclass
class BridgeCapabilities:
    """What a device bridge says it can do. Defaults are all-false on purpose."""

    can_open_dialer: bool = False
    can_place_call: bool = False
    can_receive_call_events: bool = False
    can_answer_call: bool = False
    can_reject_call: bool = False
    can_end_call: bool = False
    can_read_call_state: bool = False
    can_select_sim: bool = False
    can_route_audio: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return dict(self.__dict__)


class DeviceBridge(Protocol):
    """A phone bridge (GSConnect/KDE Connect, a native dialer, or a VoIP API)."""

    name: str

    def available(self) -> bool:  # pragma: no cover - protocol
        ...

    def capabilities(self) -> BridgeCapabilities:  # pragma: no cover - protocol
        ...

    def open_dialer(self, number: str) -> Dict[str, Any]:  # pragma: no cover - protocol
        ...

    def place_call(self, number: str) -> Dict[str, Any]:  # pragma: no cover - protocol
        ...


class NullDeviceBridge:
    """Reports no capability. Used when nothing is verified."""

    name = "none"

    def available(self) -> bool:
        return False

    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities()

    def open_dialer(self, number: str) -> Dict[str, Any]:
        raise errors.CallingError(
            f"no device bridge is available; cannot open a dialer for {number[:2]}…"
        )

    def place_call(self, number: str) -> Dict[str, Any]:
        raise errors.CallingError("no device bridge is available; no call was placed")


@dataclass
class CallRecord:
    call_id: str
    requested_by: str = "user"
    contact: Optional[Contact] = None
    state: CallState = CallState.IDLE
    task_id: str = ""
    bridge: str = "none"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""
    verified: bool = False

    def transition(self, state: CallState, detail: str = "") -> "CallRecord":
        if state == self.state:
            return self
        if state not in CALL_TRANSITIONS.get(self.state, ()):
            raise errors.CallingError(
                f"illegal call transition {self.state.value} -> {state.value}",
                code=errors.CALLING_INVALID_STATE,
            )
        self.state = state
        self.updated_at = time.time()
        event: Dict[str, Any] = {"state": state.value, "at": self.updated_at}
        if detail:
            event["detail"] = detail[:300]
        self.events.append(event)
        return self

    @property
    def terminal(self) -> bool:
        return self.state.terminal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "requested_by": self.requested_by,
            "contact": self.contact.to_public_dict() if self.contact else None,
            "state": self.state.value,
            "task_id": self.task_id,
            "bridge": self.bridge,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "events": self.events,
            "error": self.error,
            "verified": self.verified,
        }


class CallingService:
    """Prepare, confirm and place calls under AJ policy.

    The service refuses to claim more than the bridge reports. If the bridge
    cannot read call state, the record stays ``UNKNOWN`` — never optimistically
    ``CONNECTED``.
    """

    def __init__(self, resolver: Optional[ContactResolver] = None,
                 bridge: Optional[DeviceBridge] = None,
                 authorizer=None,
                 audit=None):
        self.resolver = resolver
        self.bridge = bridge or NullDeviceBridge()
        self.authorizer = authorizer
        self.audit = audit
        self._calls: Dict[str, CallRecord] = {}
        self._lock = threading.RLock()

    # --- preparation -----------------------------------------------------
    def prepare(self, query: str, *, requested_by: str = "user") -> CallRecord:
        """Resolve a contact and stop before dialing."""
        with self._lock:
            record = CallRecord(call_id=ids.new_call_id(), requested_by=requested_by,
                                bridge=getattr(self.bridge, "name", "none"))
            self._calls[record.call_id] = record
        record.transition(CallState.REQUESTED, f"query={query[:40]}")
        if self.resolver is None:
            record.transition(CallState.FAILED, "no contact resolver configured")
            record.error = "no contact resolver configured"
            return record
        record.transition(CallState.CONTACT_RESOLVING)
        try:
            matches = list(self.resolver.resolve(query))
        except Exception as exc:
            record.transition(CallState.FAILED, str(exc)[:200])
            record.error = errors.normalize(exc).message
            return record
        if not matches:
            record.transition(CallState.FAILED, "no contact matched")
            record.error = f"no contact matched {query!r}"
            return record
        if len(matches) > 1:
            record.transition(CallState.FAILED, "ambiguous contact")
            record.error = "ambiguous contact; ask the user"
            return record
        record.contact = matches[0]
        record.transition(CallState.AWAITING_CONFIRMATION, "contact resolved")
        return record

    # --- dialing ---------------------------------------------------------
    def confirm_and_dial(self, call_id: str, *, approval_token: str = "") -> CallRecord:
        """Place the call. Requires an approval token for the calling capability."""
        record = self._calls.get(call_id)
        if record is None:
            raise errors.CallingError(f"unknown call {call_id!r}")
        if record.state is not CallState.AWAITING_CONFIRMATION:
            raise errors.CallingError(
                f"call is {record.state.value}, not awaiting confirmation",
                code=errors.CALLING_INVALID_STATE,
            )
        if record.contact is None:
            raise errors.CallingError("no resolved contact to dial")

        capabilities = self.bridge.capabilities()
        if not (capabilities.can_place_call or capabilities.can_open_dialer):
            record.transition(CallState.FAILED, "bridge exposes no dialing capability")
            record.error = ("bridge exposes no dialing capability: it can neither "
                            "place a call nor open a dialer")
            return record

        if self.authorizer is not None:
            from .capability import CapabilitySpec
            spec = CapabilitySpec(
                capability_id="helix.place_call",
                name="Place a phone call",
                description="Dial a resolved contact on the paired phone",
                owner_agent="HELIX",
                execution_adapter=f"device_bridge:{getattr(self.bridge, 'name', 'none')}",
                required_permissions=("phone_call",),
                risk_level=3,
            )
            decision = self.authorizer.authorize(
                spec,
                payload={"call_id": call_id, "contact": record.contact.contact_id},
                approval=approval_token,
                user_requested=True,
            )
            if not decision.allowed:
                record.error = decision.reason
                record.events.append({"state": record.state.value,
                                      "detail": f"blocked: {decision.reason}",
                                      "at": time.time()})
                return record

        record.transition(CallState.PREPARING)
        record.transition(CallState.DIALING, "handing off to the bridge")
        try:
            outcome = self.bridge.place_call(record.contact.phone)
        except Exception as exc:
            record.transition(CallState.FAILED, str(exc)[:200])
            record.error = errors.normalize(exc).message
            return record

        reported = str((outcome or {}).get("state", "")).upper()
        try:
            record.transition(CallState(reported) if reported else CallState.UNKNOWN,
                              "bridge reported state")
        except ValueError:
            record.transition(CallState.UNKNOWN, f"bridge reported {reported!r}")
        record.verified = bool((outcome or {}).get("verified", False))
        if self.audit is not None:
            self.audit.record(
                "place_call",
                agent="HELIX",
                capability="helix.place_call",
                permission_level=3,
                authorization="approval-token" if approval_token else "none",
                result=record.state.value,
                external_side_effect=True,
                detail=f"bridge={record.bridge} verified={record.verified}",
            )
        return record

    # --- state -----------------------------------------------------------
    def status(self, call_id: str) -> CallRecord:
        record = self._calls.get(call_id)
        if record is None:
            raise errors.CallingError(f"unknown call {call_id!r}")
        return record

    def hang_up(self, call_id: str) -> CallRecord:
        record = self.status(call_id)
        capabilities = self.bridge.capabilities()
        if not capabilities.can_end_call:
            raise errors.CallingError(
                "this bridge cannot end calls; capability is unverified"
            )
        record.transition(CallState.ENDED, "ended by user")
        return record

    def cancel(self, call_id: str) -> bool:
        record = self._calls.get(call_id)
        if record is None or record.terminal:
            return False
        record.transition(CallState.CANCELLED, "cancelled before dialing")
        return True

    def all_calls(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._calls.values()]
