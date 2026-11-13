"""Foundation tests: permissions, capabilities, task lifecycle, audit, contracts."""

from __future__ import annotations

import json
import stat

import pytest

from aj import errors
from aj.audit import AuditLog, AuditEvent, JsonlAuditSink, MemoryAuditSink
from aj.capability import (
    CapabilityRegistry,
    CapabilitySpec,
    AVAILABLE,
    IMPLEMENTED_UNVERIFIED,
    PLANNED,
    UNAVAILABLE,
)
from aj.contracts import AgentResult, ExecutionRequest, SkillSpec
from aj.permissions import (
    ALLOW,
    CONFIRM,
    DENY,
    ApprovalGate,
    Authorizer,
    level_from_tier,
)
from aj.task import (
    ABORTED,
    COMPLETED,
    EXECUTING,
    FAILED,
    RECEIVED,
    RECOVERING,
    RETRYING,
    TaskStore,
)


def spec(**kw):
    base = dict(
        capability_id="test.do",
        name="Do a thing",
        description="",
        owner_agent="AJ",
        execution_adapter="test",
        risk_level=1,
        availability=AVAILABLE,
        verification_status=IMPLEMENTED_UNVERIFIED,
    )
    base.update(kw)
    return CapabilitySpec(**base)


# --- permissions ---------------------------------------------------------
def test_tier_mapping_matches_jarvis_vocabulary():
    assert level_from_tier("read") == 0
    assert level_from_tier("local-write") == 1
    assert level_from_tier("consequential") == 3
    assert level_from_tier("forbidden") == 4


def test_authorizer_allows_low_risk_unattended():
    decision = Authorizer().authorize(spec())
    assert decision.outcome == ALLOW and decision.allowed


def test_authorizer_requires_approval_for_consequential():
    decision = Authorizer().authorize(spec(risk_level=3))
    assert decision.outcome == CONFIRM
    assert decision.requires_approval and not decision.allowed


def test_authorizer_denies_forbidden_regardless_of_approval():
    decision = Authorizer().authorize(spec(forbidden=True, risk_level=3), approval="x")
    assert decision.outcome == DENY and decision.forbidden


def test_approval_is_bound_to_payload_and_single_use():
    gate = ApprovalGate()
    authorizer = Authorizer(gate=gate)
    capability = spec(risk_level=4)
    approval = gate.issue(capability.capability_id, {"target": "a"})

    wrong = authorizer.authorize(capability, payload={"target": "b"},
                                 approval=approval.token)
    assert wrong.outcome == DENY and "changed" in wrong.reason

    ok = authorizer.authorize(capability, payload={"target": "a"},
                              approval=approval.token)
    assert ok.outcome == ALLOW

    replay = authorizer.authorize(capability, payload={"target": "a"},
                                  approval=approval.token)
    assert replay.outcome == DENY


def test_level_two_needs_an_explicit_request():
    assert Authorizer().authorize(spec(risk_level=2)).outcome == CONFIRM
    assert Authorizer().authorize(spec(risk_level=2), user_requested=True).outcome == ALLOW


# --- capability registry -------------------------------------------------
def test_registry_rejects_conflicting_redefinition():
    registry = CapabilityRegistry([spec()])
    with pytest.raises(errors.AjError):
        registry.register(spec(risk_level=3))
    registry.register(spec(risk_level=3), replace=True)
    assert registry.get("test.do").risk_level == 3


def test_executable_excludes_planned_and_unavailable():
    registry = CapabilityRegistry([
        spec(capability_id="a", availability=AVAILABLE),
        spec(capability_id="b", availability=UNAVAILABLE),
        spec(capability_id="c", verification_status=PLANNED, availability=AVAILABLE),
    ])
    assert [s.capability_id for s in registry.executable()] == ["a"]


def test_registry_loads_declarations_and_validates_owners():
    registry = CapabilityRegistry.load_json(
        __import__("pathlib").Path(__file__).resolve().parents[1] / "config" / "capabilities.json"
    )
    assert registry.get("helix.place_call").risk_level == 3
    assert registry.get("helix.place_call").owner_agent == "HELIX"
    with pytest.raises(errors.AjError):
        spec(owner_agent="SOMEONE")


# --- task lifecycle ------------------------------------------------------
def test_happy_path_transitions():
    store = TaskStore()
    record = store.create("do work")
    for status in ("UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING", "VERIFYING"):
        store.transition(record.task_id, status)
    store.transition(record.task_id, COMPLETED, "done")
    assert record.status == COMPLETED and record.terminal and record.completed_at


def test_illegal_transition_is_refused():
    record = TaskStore().create("x")
    with pytest.raises(errors.AjError):
        record.transition(COMPLETED)
    record.transition("UNDERSTANDING")
    record.transition("PLANNED")
    record.transition(ABORTED)
    with pytest.raises(errors.AjError):
        record.transition(EXECUTING)


def test_failure_recovery_path_is_bounded_by_recorded_attempts():
    record = TaskStore().create("x")
    record.transition("UNDERSTANDING")
    record.transition("PLANNED")
    record.transition("AUTHORIZED")
    record.transition(EXECUTING)
    record.transition(FAILED, "boom")
    record.transition(RECOVERING)
    record.transition(RETRYING)
    record.transition(EXECUTING)
    assert record.status == EXECUTING
    record.record_error(errors.CapabilityUnavailable("nope"), stage="executing")
    assert record.errors[-1]["code"] == errors.CAPABILITY_UNAVAILABLE


def test_child_task_keeps_parent_visible():
    store = TaskStore()
    parent = store.create("parent")
    child = store.child_of(parent, "child")
    assert child.parent_task_id == parent.task_id
    assert parent.task_id in child.task_id


def test_terminal_task_cannot_persist_new_results_silently():
    store = TaskStore()
    record = store.create("x")
    store.cancel(record.task_id)
    assert record.terminal
    assert store.cancel(record.task_id) is False


# --- audit ---------------------------------------------------------------
def test_audit_redacts_secrets_and_keeps_required_fields():
    sink = MemoryAuditSink()
    log = AuditLog(sink)
    log.record(
        "send_message", agent="JARVIS", task_id="t1", capability="jarvis.send_message",
        permission_level=3, authorization="approval", result="completed",
        params={"api_key": "sk-123", "text": "hello"}, external_side_effect=True,
    )
    event = sink.events[0]
    assert event["params"]["api_key"] == "[redacted]"
    assert event["params"]["text"] == "hello"
    for field in ("at", "actor", "agent", "task_id", "capability", "action",
                  "permission_level", "authorization", "result", "external_side_effect"):
        assert field in event


def test_jsonl_sink_writes_private_append_only_file(tmp_path):
    sink = JsonlAuditSink(tmp_path)
    log = AuditLog(sink)
    log.record("one")
    log.record("two")
    path = next(tmp_path.glob("events-*.jsonl"))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["action"] == "one"


def test_audit_event_round_trip():
    original = AuditEvent(action="a", task_id="t", permission_level=2)
    assert AuditEvent.from_dict(original.to_dict()).action == "a"


# --- contracts -----------------------------------------------------------
def test_execution_request_never_serialises_the_approval_token():
    request = ExecutionRequest(request_id="r", capability_id="c", approval_token="secret")
    assert "approval_token" not in request.to_dict()


def test_agent_result_rejects_unknown_status():
    with pytest.raises(errors.AjError):
        AgentResult(task_id="t", agent="JARVIS", status="probably-fine")


def test_skill_is_withheld_until_tested_and_approved():
    skill = SkillSpec(skill_id="s", name="s", description="", review_status="approved",
                      verification_steps=["compare output"])
    assert "no recorded tests" in skill.blocking_reasons()

    skill.tests = [{"status": "PASS"}]
    assert skill.blocking_reasons() == []

    skill.tests = [{"status": "FAIL"}]
    assert any("not every recorded test passed" in r for r in skill.blocking_reasons())


def test_level_four_skill_must_keep_approval_required():
    skill = SkillSpec(skill_id="s", name="s", description="", review_status="approved",
                      required_permissions=[4], approval_required=False,
                      tests=[{"status": "PASS"}], verification_steps=["x"])
    assert any("level-4" in r for r in skill.blocking_reasons())
