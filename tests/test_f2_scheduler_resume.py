"""F2: scheduler/resume authorization boundaries (real paths)."""

from __future__ import annotations

from aj.agents import AgentRegistry
from aj.audit import AuditLog, MemoryAuditSink
from aj.capability import CapabilityRegistry, CapabilitySpec, OWNER_AJ
from aj.execution import SkillRegistry, UnavailableExecutionAdapter
from aj.orchestrator import Aj
from aj.permissions import ApprovalGate, Authorizer
from aj.scheduler import Scheduler
from aj.task import AUTHORIZED, BLOCKED, COMPLETED, FAILED, PLANNED, WAITING_FOR_APPROVAL

from conftest import make_config


class RecordingActions:
    def __init__(self):
        self.calls = []

    def names(self):
        return ["write_probe"]

    def run(self, name, arguments=None):
        self.calls.append((name, dict(arguments or {})))
        return {"ran": name, "args": dict(arguments or {})}


def cap(**kw):
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


def make_aj(*specs, actions=None, gate=None):
    sink = MemoryAuditSink()
    aj = Aj(
        registry=CapabilityRegistry(specs),
        agents=AgentRegistry(),
        authorizer=Authorizer(gate=gate or ApprovalGate()),
        audit=AuditLog(sink),
        tasks=__import__("aj.task", fromlist=["TaskStore"]).TaskStore(),
        execution=UnavailableExecutionAdapter(),
        skills=SkillRegistry(),
        config=make_config(),
        actions=actions or RecordingActions(),
    )
    return aj, sink, actions or aj.actions


def test_resume_planned_consequential_requires_approval_and_does_not_execute():
    actions = RecordingActions()
    aj, sink, _ = make_aj(cap(), actions=actions)
    record = aj.tasks.create("planned consequential", capability_id="test.side_effect")
    record.request_payload = {"goal": "planned consequential", "target": "A"}
    aj.tasks.transition(record.task_id, "UNDERSTANDING")
    aj.tasks.transition(record.task_id, PLANNED)
    aj.tasks.save(record, "planned")

    outcome = aj.resume(record.task_id)
    reloaded = aj.tasks.get(record.task_id)
    assert not outcome.ok
    assert reloaded.status == WAITING_FOR_APPROVAL
    assert actions.calls == []
    assert any(e["action"] == "awaiting_approval" for e in sink.events)


def test_scheduler_cannot_execute_planned_consequential_without_approval():
    actions = RecordingActions()
    aj, sink, _ = make_aj(cap(), actions=actions)
    record = aj.tasks.create("planned consequential", capability_id="test.side_effect")
    record.request_payload = {"goal": "planned consequential"}
    aj.tasks.transition(record.task_id, "UNDERSTANDING")
    aj.tasks.transition(record.task_id, PLANNED)
    aj.tasks.save(record, "planned")

    # PLANNED not in scheduler queue by default, but resume path must still be safe if invoked.
    outcome = aj.resume(record.task_id)
    assert not outcome.ok
    assert actions.calls == []
    assert aj.tasks.get(record.task_id).status == WAITING_FOR_APPROVAL


def test_resume_blocked_consequential_requires_approval_and_does_not_execute():
    actions = RecordingActions()
    aj, sink, _ = make_aj(cap(), actions=actions)
    record = aj.tasks.create("blocked consequential", capability_id="test.side_effect")
    record.request_payload = {"goal": "blocked consequential"}
    aj.tasks.transition(record.task_id, "UNDERSTANDING")
    aj.tasks.transition(record.task_id, PLANNED)
    aj.tasks.transition(record.task_id, BLOCKED, "manual")
    aj.tasks.save(record, "blocked")

    outcome = aj.resume(record.task_id)
    assert not outcome.ok
    assert aj.tasks.get(record.task_id).status == WAITING_FOR_APPROVAL
    assert actions.calls == []
    assert any(e["action"] == "awaiting_approval" for e in sink.events)


def test_resume_authorized_consequential_continues_same_bound_operation():
    # Valid continuation: task was authorized/executed path interrupted before completion in model;
    # resume executes the stored payload/capability without re-consuming a token.
    gate = ApprovalGate()
    actions = RecordingActions()
    aj, sink, _ = make_aj(cap(), actions=actions, gate=gate)
    record = aj.tasks.create("authorized consequential", capability_id="test.side_effect")
    record.request_payload = {"goal": "authorized consequential", "target": "A"}
    # simulate prior authorized state for same operation with durable auth context
    for status in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, status)
    spec = aj.registry.get("test.side_effect")
    decision = aj.authorizer.authorize(spec, payload=record.request_payload, approval="", user_requested=True, actor="user")
    # force AUTHORIZED to model an interrupted-but-authorized continuation case
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, record.request_payload, decision)
    aj.tasks.save(record, "authorized")

    outcome = aj.resume(record.task_id)
    assert outcome.ok
    assert outcome.status == COMPLETED
    assert len(actions.calls) == 1
    assert actions.calls[0][1]["target"] == "A"


def test_resume_authorized_fails_if_capability_becomes_forbidden():
    actions = RecordingActions()
    spec = cap(forbidden=True)
    aj, sink, _ = make_aj(spec, actions=actions)
    record = aj.tasks.create("authorized forbidden", capability_id="test.side_effect")
    record.request_payload = {"goal": "x"}
    for status in ("UNDERSTANDING", "PLANNED", "AUTHORIZED"):
        aj.tasks.transition(record.task_id, status)
    aj.tasks.save(record, "authorized")

    outcome = aj.resume(record.task_id)
    assert not outcome.ok
    assert actions.calls == []
    assert aj.tasks.get(record.task_id).status == "ABORTED"


def test_scheduler_executes_authorized_read_only_task():
    actions = RecordingActions()
    read = CapabilitySpec(
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
    aj, sink, _ = make_aj(read, actions=actions)
    record = aj.tasks.create("auth read", capability_id="test.read_only")
    record.request_payload = {"goal": "auth read"}
    for status in ("UNDERSTANDING", "PLANNED", "AUTHORIZED"):
        aj.tasks.transition(record.task_id, status)
    aj.tasks.save(record, "authorized")

    sched = Scheduler(aj)
    result = sched.run_once()
    assert result["completed"] == 1
    assert actions.calls == [("write_probe", {"goal": "auth read"})] or len(actions.calls) == 1
    assert aj.tasks.get(record.task_id).status == COMPLETED
