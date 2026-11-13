"""Orchestrator tests: routing, policy, lifecycle, failure, recovery, Hermes gate."""

from __future__ import annotations

import pytest

from aj.agents import AgentRegistry
from aj.audit import AuditLog, MemoryAuditSink
from aj.capability import CapabilityRegistry, CapabilitySpec
from aj.contracts import AgentResult
from aj.execution import SkillRegistry, UnavailableExecutionAdapter
from aj.orchestrator import Aj, Router, build
from aj.permissions import ApprovalGate, Authorizer
from aj.task import COMPLETED, ESCALATED, FAILED

from conftest import make_config


class FakeAgent:
    def __init__(self, name, result=None):
        self.name = name
        self.result = result
        self.requests = []

    def available(self):
        return True

    def describe(self):
        return {"name": self.name, "available": True, "adapter": "fake"}

    def execute(self, request):
        self.requests.append(request)
        return self.result or AgentResult(
            task_id=request.task_id, agent=self.name, status="completed",
            summary="done", evidence=[{"checked": True}],
        )


def capability(**kw):
    base = dict(
        capability_id="jarvis.web_search", name="Search", description="",
        owner_agent="JARVIS", execution_adapter="jarvis.tool", risk_level=0,
        availability="available", verification_status="verified",
    )
    base.update(kw)
    return CapabilitySpec(**base)


def make_aj(*specs, agents=None, gate=None, execution=None, config=None):
    sink = MemoryAuditSink()
    return Aj(
        registry=CapabilityRegistry(specs),
        agents=agents or AgentRegistry([FakeAgent("JARVIS"), FakeAgent("HELIX")]),
        authorizer=Authorizer(gate=gate or ApprovalGate()),
        audit=AuditLog(sink),
        tasks=__import__("aj.task", fromlist=["TaskStore"]).TaskStore(),
        execution=execution or UnavailableExecutionAdapter(),
        skills=SkillRegistry(),
        config=config or make_config(),
    ), sink


def test_calling_language_routes_to_helix():
    assert Router().route("call Ali please").owner_agent == "HELIX"
    assert Router().route("write a report").owner_agent == "JARVIS"


def test_explicit_capability_routes_to_its_owner():
    registry = CapabilityRegistry([capability()])
    route = Router().route("anything", capability_id="jarvis.web_search",
                          registry=registry)
    assert route.owner_agent == "JARVIS"


def test_successful_delegation_completes_with_evidence():
    aj, sink = make_aj(capability())
    outcome = aj.handle("search the web", capability_id="jarvis.web_search")
    assert outcome.ok and outcome.status == COMPLETED
    assert outcome.result is not None and outcome.result.evidence
    actions = [e["action"] for e in sink.events]
    for expected in ("task_received", "authorized", "delegated"):
        assert expected in actions


def test_unknown_capability_fails_with_a_specific_code():
    aj, _ = make_aj()
    outcome = aj.handle("search", capability_id="nope.missing")
    assert not outcome.ok
    assert outcome.errors[0]["code"] == "capability_not_found"
    assert outcome.status == FAILED


def test_forbidden_capability_is_aborted_not_confirmed():
    aj, _ = make_aj(capability(forbidden=True, risk_level=3))
    outcome = aj.handle("do it", capability_id="jarvis.web_search")
    assert not outcome.ok and outcome.status == "ABORTED"
    assert "permanently disabled" in outcome.summary


def test_unverified_availability_blocks_execution():
    aj, _ = make_aj(capability(availability="unavailable"))
    outcome = aj.handle("do it", capability_id="jarvis.web_search")
    assert not outcome.ok
    assert outcome.errors[0]["code"] == "capability_unavailable"


def test_consequential_action_waits_for_approval_then_runs():
    gate = ApprovalGate()
    aj, _ = make_aj(capability(risk_level=3, capability_id="helix.send_message",
                               owner_agent="HELIX"), gate=gate)
    first = aj.handle("message Ali", capability_id="helix.send_message")
    assert first.requires_user_decision and first.status == "WAITING_FOR_APPROVAL"
    assert not first.ok

    approval = gate.issue("helix.send_message", {"goal": "message Ali"})
    second = aj.handle("message Ali", capability_id="helix.send_message",
                       approval=approval.token)
    assert second.ok and second.status == COMPLETED


def test_changed_payload_invalidates_the_approval():
    gate = ApprovalGate()
    aj, _ = make_aj(capability(risk_level=3, capability_id="helix.send_message",
                               owner_agent="HELIX"), gate=gate)
    approval = gate.issue("helix.send_message", {"goal": "message Ali"})
    outcome = aj.handle("message someone else", capability_id="helix.send_message",
                        approval=approval.token)
    assert not outcome.ok and "approval rejected" in outcome.summary


def test_hermes_capability_fails_while_no_runtime_is_attached():
    aj, _ = make_aj(capability(capability_id="hermes.execute_skill", owner_agent="HERMES",
                               risk_level=2, verification_status="verified"))
    outcome = aj.handle("run the skill", capability_id="hermes.execute_skill")
    assert not outcome.ok
    assert outcome.errors[0]["code"] == "execution_unavailable"
    assert aj.status()["execution"]["integration_status"] == "NOT ATTACHED"


def test_agent_failure_produces_failed_task_and_audit():
    failing = FakeAgent("JARVIS", AgentResult(
        task_id="x", agent="JARVIS", status="rejected", summary="not reachable",
        errors=[{"code": "agent_unavailable", "message": "not reachable"}],
    ))
    aj, sink = make_aj(capability(), agents=AgentRegistry([failing]))
    outcome = aj.handle("search", capability_id="jarvis.web_search")
    assert not outcome.ok and outcome.status == FAILED
    assert any(e["action"] == "delegated" and e["result"] == "rejected" for e in sink.events)


def test_retry_is_bounded_and_escalates_instead_of_looping():
    failing = FakeAgent("JARVIS", AgentResult(
        task_id="x", agent="JARVIS", status="rejected", summary="nope",
    ))
    aj, _ = make_aj(capability(), agents=AgentRegistry([failing]))
    first = aj.handle("search", capability_id="jarvis.web_search")
    assert first.status == FAILED

    task = aj.tasks.get(first.task_id)
    task.max_attempts = 1
    escalated = aj.retry(first.task_id)
    assert escalated.status == ESCALATED and escalated.requires_user_decision


def test_cancel_is_recorded():
    aj, sink = make_aj(capability())
    record = aj.tasks.create("pending work")
    assert aj.cancel(record.task_id) is True
    assert any(e["action"] == "task_cancelled" for e in sink.events)


def test_build_loads_declared_capabilities_from_the_workspace():
    aj = build(make_config())
    assert aj.registry.find("helix.place_call") is not None
    assert aj.registry.find("hermes.execute_skill").verification_status == "planned"
    # JARVIS's own catalogue is imported, not copied.
    jarvis_specs = aj.registry.by_owner("JARVIS")
    if jarvis_specs:  # present when the JARVIS checkout is alongside AJ
        assert any(s.capability_id == "jarvis.web_search" for s in jarvis_specs)
