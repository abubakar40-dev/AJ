"""F2 durable authorization context / stale-policy protection (real paths)."""

from __future__ import annotations

from aj.agents import AgentRegistry
from aj.audit import AuditLog, MemoryAuditSink
from aj.capability import CapabilityRegistry, CapabilitySpec, OWNER_AJ
from aj.execution import SkillRegistry, UnavailableExecutionAdapter
from aj.orchestrator import Aj
from aj.permissions import ApprovalGate, Authorizer
from aj.scheduler import Scheduler
from aj.task import WAITING_FOR_APPROVAL, COMPLETED

from conftest import make_config


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
        version="1",
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
        version="1",
    )
    base.update(kw)
    return CapabilitySpec(**base)


def make_env(*specs, actions=None, gate=None):
    sink = MemoryAuditSink()
    actions = actions or RecordingActions()
    aj = Aj(
        registry=CapabilityRegistry(specs),
        agents=AgentRegistry(),
        authorizer=Authorizer(gate=gate or ApprovalGate()),
        audit=AuditLog(sink),
        tasks=__import__("aj.task", fromlist=["TaskStore"]).TaskStore(),
        execution=UnavailableExecutionAdapter(),
        skills=SkillRegistry(),
        config=make_config(),
        actions=actions,
    )
    return aj, sink, actions


def authorize_consequential_task(aj, payload=None, spec_id="test.side_effect"):
    gate = aj.authorizer.gate
    payload = payload or {"goal": "do side effect", "target": "A"}
    approval = gate.issue(spec_id, payload)
    outcome = aj.handle("do side effect", capability_id=spec_id, payload=payload,
                        approval=approval.token, user_requested=True)
    return outcome, payload


def test_authorized_consequential_resumes_when_context_unchanged():
    aj, sink, actions = make_env(side_effect_cap())
    outcome, payload = authorize_consequential_task(aj)
    assert outcome.ok
    task_id = outcome.task_id
    # simulate interruption before completion by resetting to AUTHORIZED with same bound context
    record = aj.tasks.get(task_id)
    # task completed; create a continuation-style authorized record with same context
    record2 = aj.tasks.create("cont", capability_id="test.side_effect")
    record2.request_payload = payload
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record2.task_id, st)
    spec = aj.registry.get("test.side_effect")
    decision = aj.authorizer.authorize(spec, payload=payload, approval="", user_requested=True, actor="user")
    aj.tasks.transition(record2.task_id, "AUTHORIZED", "prior authorization")
    record2.authorization_context = aj._compute_authorization_context(record2, spec, payload, decision)
    aj.tasks.save(record2, "authorized")
    actions.calls.clear()

    out2 = aj.resume(record2.task_id)
    assert out2.ok
    assert aj.tasks.get(record2.task_id).status == COMPLETED
    assert len(actions.calls) == 1
    assert actions.calls[0][1]["target"] == "A"


def test_resume_refuses_when_capability_version_changes_materially():
    aj, sink, actions = make_env(side_effect_cap(version="1"))
    _, payload = authorize_consequential_task(aj)
    record = aj.tasks.create("cont", capability_id="test.side_effect")
    record.request_payload = payload
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, st)
    spec = aj.registry.get("test.side_effect")
    decision = aj.authorizer.authorize(spec, payload=payload, approval="", user_requested=True, actor="user")
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, payload, decision)
    aj.tasks.save(record, "authorized")
    aj.registry.register(side_effect_cap(version="2"), replace=True)
    actions.calls.clear()

    out = aj.resume(record.task_id)
    assert not out.ok
    assert actions.calls == []
    assert aj.tasks.get(record.task_id).status == "RECOVERY_REQUIRED"
    assert aj.tasks.get(record.task_id).requires_user_decision is True
    assert any(e.get("action") == "policy_denied" and e.get("authorization") == "stale"
               for e in sink.events)
    if aj.journal is not None:
        assert any(e.get("event_type") == "TASK_RECOVERY_REQUIRED" and (e.get("metadata") or {}).get("stale_authorization")
                   for e in aj.journal.events(task_id=record.task_id, limit=0))


def test_resume_refuses_when_risk_becomes_stricter():
    aj, sink, actions = make_env(read_cap(risk_level=1))
    # authorize as low-risk/user-authorized style via handle (allowed with user_requested)
    out = aj.handle("read", capability_id="test.read_only", payload={"goal": "read"}, user_requested=True)
    assert out.ok
    record = aj.tasks.create("cont", capability_id="test.read_only")
    record.request_payload = {"goal": "read"}
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, st)
    spec = aj.registry.get("test.read_only")
    decision = aj.authorizer.authorize(spec, payload=record.request_payload, approval="", user_requested=True, actor="user")
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, record.request_payload, decision)
    aj.tasks.save(record, "authorized")
    aj.registry.register(read_cap(risk_level=3), replace=True)
    actions.calls.clear()

    out2 = aj.resume(record.task_id)
    assert not out2.ok
    assert actions.calls == []
    assert aj.tasks.get(record.task_id).status == "RECOVERY_REQUIRED"
    assert aj.tasks.get(record.task_id).requires_user_decision is True


def test_resume_refuses_when_required_approval_level_increases():
    aj, sink, actions = make_env(read_cap(risk_level=2))  # user-requested allowed
    record = aj.tasks.create("cont", capability_id="test.read_only")
    record.request_payload = {"goal": "read"}
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, st)
    spec = aj.registry.get("test.read_only")
    decision = aj.authorizer.authorize(spec, payload=record.request_payload, approval="", user_requested=True, actor="user")
    assert decision.allowed
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, record.request_payload, decision)
    aj.tasks.save(record, "authorized")
    aj.registry.register(read_cap(risk_level=3), replace=True)
    actions.calls.clear()

    out = aj.resume(record.task_id)
    assert not out.ok
    assert actions.calls == []
    assert aj.tasks.get(record.task_id).status == "RECOVERY_REQUIRED"


def test_resume_refuses_when_capability_becomes_forbidden():
    aj, sink, actions = make_env(side_effect_cap(forbidden=False))
    _, payload = authorize_consequential_task(aj)
    record = aj.tasks.create("cont", capability_id="test.side_effect")
    record.request_payload = payload
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, st)
    spec = aj.registry.get("test.side_effect")
    decision = aj.authorizer.authorize(spec, payload=payload, approval="", user_requested=True, actor="user")
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, payload, decision)
    aj.tasks.save(record, "authorized")
    aj.registry.register(side_effect_cap(forbidden=True), replace=True)
    actions.calls.clear()

    out = aj.resume(record.task_id)
    assert not out.ok
    assert actions.calls == []
    assert aj.tasks.get(record.task_id).status in ("ABORTED", "RECOVERY_REQUIRED", "FAILED")


def test_resume_refuses_when_capability_becomes_unavailable():
    aj, sink, actions = make_env(side_effect_cap(availability="available"))
    _, payload = authorize_consequential_task(aj)
    record = aj.tasks.create("cont", capability_id="test.side_effect")
    record.request_payload = payload
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, st)
    spec = aj.registry.get("test.side_effect")
    decision = aj.authorizer.authorize(spec, payload=payload, approval="", user_requested=True, actor="user")
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, payload, decision)
    aj.tasks.save(record, "authorized")
    aj.registry.register(side_effect_cap(availability="unavailable"), replace=True)
    actions.calls.clear()

    out = aj.resume(record.task_id)
    assert not out.ok
    assert actions.calls == []


def test_resume_refuses_when_payload_fingerprint_changes():
    aj, sink, actions = make_env(side_effect_cap())
    _, payload = authorize_consequential_task(aj)
    record = aj.tasks.create("cont", capability_id="test.side_effect")
    record.request_payload = payload
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, st)
    spec = aj.registry.get("test.side_effect")
    decision = aj.authorizer.authorize(spec, payload=payload, approval="", user_requested=True, actor="user")
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, payload, decision)
    # mutate stored payload after authorization context recorded
    record.request_payload = {"goal": "do side effect", "target": "B"}
    aj.tasks.save(record, "authorized")
    actions.calls.clear()

    out = aj.resume(record.task_id)
    assert not out.ok
    assert actions.calls == []
    assert aj.tasks.get(record.task_id).status == "RECOVERY_REQUIRED"


def test_legacy_or_missing_authorization_context_fails_closed_for_consequential():
    aj, sink, actions = make_env(side_effect_cap())
    record = aj.tasks.create("legacy", capability_id="test.side_effect")
    record.request_payload = {"goal": "legacy"}
    for st in ("UNDERSTANDING", "PLANNED", "AUTHORIZED"):
        aj.tasks.transition(record.task_id, st)
    record.authorization_context = {}
    aj.tasks.save(record, "authorized")
    actions.calls.clear()

    out = aj.resume(record.task_id)
    assert not out.ok
    assert actions.calls == []
    assert aj.tasks.get(record.task_id).status in ("WAITING_FOR_APPROVAL", "RECOVERY_REQUIRED", "ABORTED")


def test_malformed_authorization_context_fails_closed_for_consequential():
    aj, sink, actions = make_env(side_effect_cap())
    record = aj.tasks.create("malformed", capability_id="test.side_effect")
    record.request_payload = {"goal": "malformed"}
    for st in ("UNDERSTANDING", "PLANNED", "AUTHORIZED"):
        aj.tasks.transition(record.task_id, st)
    record.authorization_context = {"capability_id": "test.side_effect", "risk_level": "not-an-int"}
    aj.tasks.save(record, "authorized")
    actions.calls.clear()

    out = aj.resume(record.task_id)
    assert not out.ok
    assert actions.calls == []


def test_legacy_missing_context_non_consequential_may_continue_if_not_stricter():
    # documented backward-compatible behavior: non-consequential legacy tasks without
    # durable context are not silently blocked if current spec remains safely executable
    # and no stricter consequential policy is detected.
    aj, sink, actions = make_env(read_cap())
    record = aj.tasks.create("legacy read", capability_id="test.read_only")
    record.request_payload = {"goal": "legacy read"}
    for st in ("UNDERSTANDING", "PLANNED", "AUTHORIZED"):
        aj.tasks.transition(record.task_id, st)
    record.authorization_context = {}
    aj.tasks.save(record, "authorized")

    out = aj.resume(record.task_id)
    assert out.ok
    assert aj.tasks.get(record.task_id).status == COMPLETED
    assert len(actions.calls) == 1


def test_revalidation_failure_creates_audit_and_journal_evidence_and_no_side_effect():
    aj, sink, actions = make_env(side_effect_cap(version="1"))
    _, payload = authorize_consequential_task(aj)
    record = aj.tasks.create("cont", capability_id="test.side_effect")
    record.request_payload = payload
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, st)
    spec = aj.registry.get("test.side_effect")
    decision = aj.authorizer.authorize(spec, payload=payload, approval="", user_requested=True, actor="user")
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, payload, decision)
    aj.tasks.save(record, "authorized")
    aj.registry.register(side_effect_cap(version="2"), replace=True)
    actions.calls.clear()

    out = aj.resume(record.task_id)
    assert not out.ok
    assert actions.calls == []
    assert any(e.get("action") == "policy_denied" and e.get("authorization") == "stale" for e in sink.events)
    if aj.journal is not None:
        assert any(e.get("event_type") == "TASK_RECOVERY_REQUIRED" and e.get("task_id") == record.task_id
                   for e in aj.journal.events(task_id=record.task_id, limit=0))


def test_fresh_approval_permits_intended_operation_after_stale_refusal():
    # Existing workflow support: a stale/refused continuation does not execute, but a
    # fresh authorization (new approval token bound to current capability/payload) can
    # authorize the intended consequential operation as a new/explicit request.
    aj, sink, actions = make_env(side_effect_cap(version="1"))
    _, payload = authorize_consequential_task(aj)
    record = aj.tasks.create("cont", capability_id="test.side_effect")
    record.request_payload = payload
    for st in ("UNDERSTANDING", "PLANNED"):
        aj.tasks.transition(record.task_id, st)
    spec = aj.registry.get("test.side_effect")
    decision = aj.authorizer.authorize(spec, payload=payload, approval="", user_requested=True, actor="user")
    aj.tasks.transition(record.task_id, "AUTHORIZED", "prior authorization")
    record.authorization_context = aj._compute_authorization_context(record, spec, payload, decision)
    aj.tasks.save(record, "authorized")
    aj.registry.register(side_effect_cap(version="2"), replace=True)
    actions.calls.clear()

    refused = aj.resume(record.task_id)
    assert not refused.ok and actions.calls == []
    assert aj.tasks.get(record.task_id).status == "RECOVERY_REQUIRED"

    # fresh approval for current capability version/payload authorizes intended operation
    approval = aj.authorizer.gate.issue("test.side_effect", payload)
    fresh = aj.handle("do side effect", capability_id="test.side_effect", payload=payload,
                      approval=approval.token, user_requested=True)
    assert fresh.ok
    assert any(c[1].get("target") == "A" for c in actions.calls)
