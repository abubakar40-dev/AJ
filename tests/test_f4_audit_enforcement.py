"""F4: scoped audit policy - mandatory security audit vs best-effort diagnostics."""

from __future__ import annotations

import pytest

from aj.agents import AgentRegistry
from aj.audit import AuditLog
from aj.capability import CapabilityRegistry, CapabilitySpec, OWNER_AJ
from aj.config import Config
from aj.execution import SkillRegistry, UnavailableExecutionAdapter
from aj.orchestrator import Aj
from aj.permissions import ApprovalGate, Authorizer

from conftest import make_config


class FailingSink:
    def __init__(self, fail_actions=None):
        self.fail_actions = set(fail_actions or [])
        self.events = []
        self.failed = []

    def write(self, event):
        action = getattr(event, "action", None) or (event.get("action") if isinstance(event, dict) else None)
        if action in self.fail_actions:
            self.failed.append(action)
            raise OSError(f"simulated audit sink failure: {action}")
        self.events.append(event.to_dict() if hasattr(event, "to_dict") else event)


class RecordingActions:
    def __init__(self):
        self.calls = []

    def names(self):
        return ["write_probe"]

    def run(self, name, arguments=None):
        self.calls.append((name, dict(arguments or {})))
        return {"ran": name, "args": dict(arguments or {})}


def side_effect_cap(**kw):
    base = dict(
        capability_id="test.side_effect",
        name="Side effect",
        description="consequential test capability",
        owner_agent=OWNER_AJ,
        execution_adapter="internal:write_probe",
        risk_level=3,
        availability="available",
        verification_status="verified",
        retry_safe=True,
        replay_safe=True,
    )
    base.update(kw)
    return CapabilitySpec(**base)


def read_cap(**kw):
    base = dict(
        capability_id="test.read_only",
        name="Read only",
        description="read-only test capability",
        owner_agent=OWNER_AJ,
        execution_adapter="internal:write_probe",
        risk_level=0,
        availability="available",
        verification_status="verified",
        required_permissions=("read",),
    )
    base.update(kw)
    return CapabilitySpec(**base)


def make_aj(spec, sink, actions=None):
    actions = actions or RecordingActions()
    aj = Aj(
        registry=CapabilityRegistry([spec]),
        agents=AgentRegistry(),
        authorizer=Authorizer(gate=ApprovalGate()),
        audit=AuditLog(sink),
        tasks=__import__("aj.task", fromlist=["TaskStore"]).TaskStore(),
        execution=UnavailableExecutionAdapter(),
        skills=SkillRegistry(),
        config=make_config(),
        actions=actions,
    )
    return aj, actions


def test_mandatory_authorization_audit_failure_blocks_protected_execution():
    # "authorized" is required security evidence before executing an approved
    # consequential side effect. If it cannot be persisted, execution must not occur.
    sink = FailingSink(fail_actions={"authorized"})
    actions = RecordingActions()
    aj, actions = make_aj(side_effect_cap(), sink, actions)
    gate = aj.authorizer.gate
    payload = {"goal": "do side effect", "target": "A"}
    approval = gate.issue("test.side_effect", payload)

    outcome = aj.handle("do side effect", capability_id="test.side_effect",
                        payload=payload, approval=approval.token, user_requested=True)

    assert not outcome.ok
    assert actions.calls == [], "protected side effect must not execute when mandatory audit persistence fails"
    assert sink.failed == ["authorized"]
    # no false persisted success event for the failed mandatory write
    assert not any((e.get("action") == "authorized") for e in sink.events)
    assert outcome.status in ("FAILED", "ABORTED", "RECOVERY_REQUIRED")


def test_best_effort_diagnostic_failure_does_not_block_safe_read_only_execution():
    # Non-security diagnostic audit persistence failure must not block an unrelated
    # permitted read-only action. (task_received is treated as best-effort diagnostic
    # in this implementation unless explicitly required otherwise.)
    sink = FailingSink(fail_actions={"task_received"})
    actions = RecordingActions()
    aj, actions = make_aj(read_cap(), sink, actions)

    outcome = aj.handle("read", capability_id="test.read_only",
                        payload={"goal": "read"}, user_requested=True)

    assert outcome.ok
    assert len(actions.calls) == 1
    assert outcome.status == "COMPLETED"
    assert "task_received" in sink.failed


def test_mandatory_audit_failure_returns_accurate_structured_failure():
    sink = FailingSink(fail_actions={"authorized"})
    actions = RecordingActions()
    aj, actions = make_aj(side_effect_cap(), sink, actions)
    payload = {"goal": "do side effect"}
    approval = aj.authorizer.gate.issue("test.side_effect", payload)

    outcome = aj.handle("do side effect", capability_id="test.side_effect",
                        payload=payload, approval=approval.token, user_requested=True)

    assert not outcome.ok
    assert outcome.errors
    msg = str(outcome.errors[0].get("message", "")).lower()
    assert "audit" in msg or "persist" in msg or "mandatory" in msg
    assert actions.calls == []


def test_mandatory_awaiting_approval_audit_failure_blocks_and_reports_truthfully():
    sink = FailingSink(fail_actions={"awaiting_approval"})
    actions = RecordingActions()
    aj, actions = make_aj(side_effect_cap(), sink, actions)
    payload = {"goal": "do side effect"}

    # no approval -> should require confirmation; mandatory audit failure must not execute
    outcome = aj.handle("do side effect", capability_id="test.side_effect",
                        payload=payload, user_requested=True)

    assert not outcome.ok
    assert actions.calls == []
    assert "awaiting_approval" in sink.failed
    assert not any((e.get("action") == "awaiting_approval") for e in sink.events)
    assert outcome.errors
    msg = str(outcome.errors[0].get("message", "")).lower()
    assert "audit" in msg or "persist" in msg

