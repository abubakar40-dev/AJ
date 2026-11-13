"""F2: permission enforcement at execution boundaries.

Tests prove real execution paths (handle/retry/recover/scheduler resume where
applicable) enforce authorization, not only policy helper checks.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aj.agents import AgentRegistry
from aj.audit import AuditLog, MemoryAuditSink
from aj.capability import CapabilityRegistry, CapabilitySpec, OWNER_AJ
from aj.contracts import AgentResult
from aj.execution import SkillRegistry, UnavailableExecutionAdapter
from aj.orchestrator import Aj
from aj.permissions import ApprovalGate, Authorizer, CONFIRM, DENY
from aj.task import FAILED, RECOVERING, RETRYING, WAITING_FOR_APPROVAL

from conftest import make_config


class FakeAgent:
    name = "JARVIS"

    def __init__(self):
        self.calls = 0

    def available(self):
        return True

    def describe(self):
        return {"name": "JARVIS", "available": True}

    def execute(self, request):
        self.calls += 1
        return AgentResult(
            task_id=request.task_id,
            agent="JARVIS",
            status="completed",
            summary="ok",
            evidence=[{"checked": True}],
        )


class RecordingActions:
    def __init__(self):
        self.calls = []

    def names(self):
        return ["write_probe"]

    def run(self, name, arguments=None):
        self.calls.append((name, dict(arguments or {})))
        return {"ran": name}


def side_effect_capability(**kw):
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


def read_only_capability(**kw):
    base = dict(
        capability_id="test.read_only",
        name="Read only",
        description="read-only test capability",
        owner_agent=OWNER_AJ,
        execution_adapter="internal:write_probe",
        risk_level=0,
        availability="available",
        verification_status="verified",
        retry_safe=True,
        replay_safe=True,
        required_permissions=("read",),
    )
    base.update(kw)
    return CapabilitySpec(**base)


def make_aj(*specs, config=None, gate=None, actions=None):
    sink = MemoryAuditSink()
    aj = Aj(
        registry=CapabilityRegistry(specs),
        agents=AgentRegistry([FakeAgent()]),
        authorizer=Authorizer(gate=gate or ApprovalGate()),
        audit=AuditLog(sink),
        tasks=__import__("aj.task", fromlist=["TaskStore"]).TaskStore(),
        execution=UnavailableExecutionAdapter(),
        skills=SkillRegistry(),
        config=config or make_config(),
        actions=actions or RecordingActions(),
    )
    return aj, sink


def test_unauthorized_side_effecting_capability_cannot_execute_via_handle():
    actions = RecordingActions()
    aj, sink = make_aj(side_effect_capability(), actions=actions)
    outcome = aj.handle("do side effect", capability_id="test.side_effect")
    assert not outcome.ok
    assert outcome.requires_user_decision
    assert outcome.status == WAITING_FOR_APPROVAL
    assert actions.calls == []
    assert any(e["action"] == "awaiting_approval" for e in sink.events)


def test_permitted_read_only_capability_executes():
    actions = RecordingActions()
    aj, sink = make_aj(read_only_capability(), actions=actions)
    outcome = aj.handle("read", capability_id="test.read_only")
    assert outcome.ok
    assert outcome.status == "COMPLETED"
    assert len(actions.calls) == 1
    assert any(e["action"] == "authorized" for e in sink.events)


def test_valid_approval_allows_intended_operation():
    gate = ApprovalGate()
    actions = RecordingActions()
    aj, sink = make_aj(side_effect_capability(), gate=gate, actions=actions)
    payload = {"goal": "do side effect"}
    first = aj.handle("do side effect", capability_id="test.side_effect", payload={})
    assert first.requires_user_decision
    assert actions.calls == []
    approval = gate.issue("test.side_effect", {"goal": "do side effect"})
    second = aj.handle("do side effect", capability_id="test.side_effect",
                       payload={}, approval=approval.token)
    assert second.ok
    assert len(actions.calls) == 1
    assert any(e["action"] == "executed" and e["result"] == "completed"
               for e in sink.events)


def test_approval_for_one_operation_cannot_authorize_different_operation():
    gate = ApprovalGate()
    actions = RecordingActions()
    aj, sink = make_aj(side_effect_capability(), gate=gate, actions=actions)
    approval = gate.issue("test.side_effect", {"goal": "operation A", "target": "A"})
    outcome = aj.handle("operation B", capability_id="test.side_effect",
                        payload={"goal": "operation B", "target": "B"},
                        approval=approval.token)
    assert not outcome.ok
    assert actions.calls == []
    assert "approval rejected" in outcome.summary.lower() or "different" in outcome.summary.lower()


def test_expired_or_invalid_approval_rejected():
    gate = ApprovalGate()
    actions = RecordingActions()
    aj, _ = make_aj(side_effect_capability(), gate=gate, actions=actions)
    outcome = aj.handle("do side effect", capability_id="test.side_effect",
                        approval="not-a-real-token")
    assert not outcome.ok
    assert actions.calls == []
    assert outcome.status in ("ABORTED", "FAILED", "WAITING_FOR_APPROVAL")


def test_retry_cannot_bypass_permission_denial_for_consequential_capability():
    actions = RecordingActions()
    aj, sink = make_aj(side_effect_capability(), actions=actions)
    # Create a failed task record directly (simulating prior failed authorized run)
    record = aj.tasks.create("do side effect", capability_id="test.side_effect")
    record.request_payload = {"goal": "do side effect"}
    for status in ("UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING", "FAILED"):
        aj.tasks.transition(record.task_id, status)
    aj.tasks.save(record, "failed_setup")
    actions.calls.clear()

    outcome = aj.retry(record.task_id)
    assert not outcome.ok
    assert actions.calls == []
    assert "retry refused" in outcome.summary.lower() or "authorization" in outcome.summary.lower()
    assert any(e["action"] == "retry_refused" for e in sink.events)


def test_retry_with_valid_fresh_approval_allows_consequential_capability():
    gate = ApprovalGate()
    actions = RecordingActions()
    aj, sink = make_aj(side_effect_capability(), gate=gate, actions=actions)
    record = aj.tasks.create("do side effect", capability_id="test.side_effect")
    record.request_payload = {"goal": "do side effect"}
    for status in ("UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING", "FAILED"):
        aj.tasks.transition(record.task_id, status)
    aj.tasks.save(record, "failed_setup")
    actions.calls.clear()

    approval = gate.issue("test.side_effect", {"goal": "do side effect"})
    outcome = aj.retry(record.task_id, approval=approval.token)
    assert outcome.ok
    assert outcome.status == "COMPLETED"
    assert len(actions.calls) == 1


def test_recovery_cannot_bypass_permission_denial_for_consequential_capability():
    actions = RecordingActions()
    aj, sink = make_aj(side_effect_capability(), actions=actions)
    record = aj.tasks.create("do side effect", capability_id="test.side_effect")
    record.request_payload = {"goal": "do side effect"}
    for status in ("UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING"):
        aj.tasks.transition(record.task_id, status)
    aj.tasks.save(record, "interrupted_setup")
    actions.calls.clear()

    outcome = aj.recover(record.task_id)
    assert not outcome.ok
    assert actions.calls == []
    assert "recovery required" in outcome.summary.lower() or "authorization" in outcome.summary.lower()
    assert any(e["action"] == "recovery_refused" for e in sink.events)


def test_missing_permission_metadata_fails_safely_for_consequential_path():
    # A capability without proper registration/metadata context should not execute
    # as a side-effecting action through an unknown/invalid path.
    actions = RecordingActions()
    aj, _ = make_aj(actions=actions)
    outcome = aj.handle("do unknown", capability_id="no.such.capability")
    assert not outcome.ok
    assert actions.calls == []
    assert outcome.errors and outcome.errors[0]["code"] == "capability_not_found"


def test_permission_decisions_produce_audit_evidence():
    gate = ApprovalGate()
    actions = RecordingActions()
    aj, sink = make_aj(side_effect_capability(), gate=gate, actions=actions)
    aj.handle("do side effect", capability_id="test.side_effect")
    assert any(e["action"] == "awaiting_approval" and e["capability"] == "test.side_effect"
               for e in sink.events)

    approval = gate.issue("test.side_effect", {"goal": "do side effect"})
    aj.handle("do side effect", capability_id="test.side_effect", approval=approval.token)
    assert any(e["action"] == "authorized" for e in sink.events)
    assert any(e["action"] == "executed" for e in sink.events)


def test_forbidden_capability_never_executes_even_with_approval():
    gate = ApprovalGate()
    actions = RecordingActions()
    aj, sink = make_aj(side_effect_capability(forbidden=True), gate=gate, actions=actions)
    approval = gate.issue("test.side_effect", {"goal": "do side effect"})
    outcome = aj.handle("do side effect", capability_id="test.side_effect",
                        approval=approval.token)
    assert not outcome.ok
    assert outcome.status == "ABORTED"
    assert actions.calls == []
    assert any(e["action"] == "failed" or e.get("result") == "failed" for e in sink.events) or "permanently disabled" in outcome.summary
