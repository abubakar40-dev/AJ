"""Hermes boundary tests.

These tests exercise the *contract*, not Hermes. No Hermes code is imported,
started or attached — that requires the owner's HERMES GREEN SIGNAL.
"""

from __future__ import annotations

import pytest

from aj import errors
from aj.contracts import ExecutionRequest, ExecutionResult, SkillSpec
from aj.execution import (
    SkillRegistry,
    UnavailableExecutionAdapter,
    execute,
)


class RecordingPort:
    """A test double that stands in for a future adapter. Not shipped in aj/."""

    name = "recording"

    def __init__(self, result=None):
        self.requests = []
        self.result = result

    def available(self):
        return True

    def describe(self):
        return {"name": self.name, "available": True}

    def execute(self, request):
        self.requests.append(request)
        return self.result or ExecutionResult(
            request_id=request.request_id, status="completed",
            output={"ok": True}, verified=True,
        )


def request(**kw):
    base = dict(request_id="r1", capability_id="hermes.execute_skill",
                arguments={"a": 1}, permission_level=2)
    base.update(kw)
    return ExecutionRequest(**base)


def test_no_runtime_is_attached_and_it_says_so():
    port = UnavailableExecutionAdapter()
    assert port.available() is False
    description = port.describe()
    assert description["integration_status"] == "NOT ATTACHED"
    assert "GREEN SIGNAL" in description["requires"]
    with pytest.raises(errors.ExecutionUnavailable):
        port.execute(request())


def test_execute_helper_refuses_an_unavailable_port():
    with pytest.raises(errors.ExecutionUnavailable):
        execute(UnavailableExecutionAdapter(), request())


def test_contract_round_trip_preserves_arguments_and_drops_the_token():
    original = request(approval_token="secret-token")
    restored = ExecutionRequest.from_dict(original.to_dict())
    assert restored.arguments == {"a": 1}
    assert restored.approval_token == ""


def test_port_returning_a_non_result_is_a_failure_not_a_success():
    class BadPort(RecordingPort):
        def execute(self, request):
            return {"status": "completed"}

    result = execute(BadPort(), request())
    assert result.status == "failed"
    assert result.error["code"] == errors.EXECUTION_FAILED


def test_port_raising_a_random_exception_is_normalised():
    class ExplodingPort(RecordingPort):
        def execute(self, request):
            raise RuntimeError("kaboom")

    result = execute(ExplodingPort(), request())
    assert result.status == "failed"
    assert "kaboom" in result.error["message"]


def test_unverified_result_stays_unverified():
    port = RecordingPort(ExecutionResult(request_id="r1", status="completed",
                                         verified=False))
    assert execute(port, request()).verified is False


def test_skill_registry_withholds_untested_skills_and_explains_why():
    draft = SkillSpec(skill_id="s1", name="draft", description="")
    registry = SkillRegistry([draft])
    assert registry.approved() == []
    assert "review_status" in " ".join(registry.blocking_reasons("s1"))

    ready = SkillSpec(
        skill_id="s2", name="ready", description="", review_status="approved",
        tests=[{"name": "happy path", "status": "PASS"}],
        verification_steps=["read back the written value"],
        required_permissions=[1],
    )
    assert registry.register(ready) is True
    assert [s.skill_id for s in registry.approved()] == ["s2"]
    assert registry.summary() == {"total": 2, "approved": 1, "withheld": ["s1"]}


def test_skill_permission_ceiling_is_declared_not_granted():
    ready = SkillSpec(
        skill_id="s3", name="ready", description="", review_status="approved",
        tests=[{"status": "PASS"}], verification_steps=["verify"],
        required_permissions=[3],
    )
    assert ready.max_permission_level == 3
    # AJ's authorizer still decides per invocation; the skill gains nothing.
    from aj.permissions import CONFIRM, Authorizer
    from aj.capability import CapabilitySpec

    decision = Authorizer().authorize(CapabilitySpec(
        capability_id="hermes.execute_skill", name="x", description="",
        owner_agent="HERMES", execution_adapter="port", risk_level=3,
    ))
    assert decision.outcome == CONFIRM
