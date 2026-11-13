"""Runtime foundation tests: full local lifecycle, policy, memory, health, CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aj import errors
from aj.actions import InternalActions, echo
from aj.actions import specs as internal_specs
from aj.agents import AgentRegistry
from aj.audit import AuditLog, MemoryAuditSink
from aj.capability import AVAILABLE, VERIFIED, CapabilityRegistry, CapabilitySpec
from aj.execution import SkillRegistry, UnavailableExecutionAdapter
from aj.memory import MemoryStore
from aj.orchestrator import Aj
from aj.permissions import ApprovalGate, Authorizer
from aj.providers import (
    ChatRequest,
    Gateway,
    Message,
    MockProvider,
    ModelSpec,
    ProviderRegistry,
    ProviderSpec,
)
from aj.runtime import health, run_demo
from aj.task import COMPLETED, FAILED, WAITING_FOR_APPROVAL, TaskStore

from conftest import make_config

AJ_ROOT = Path(__file__).resolve().parent.parent


def _boom(arguments):
    raise RuntimeError("intentional failure")


def extra_spec(*, capability_id="aj.sensitive", risk_level=0,
               adapter="internal:echo", forbidden=False):
    return CapabilitySpec(
        capability_id=capability_id, name=capability_id, description="",
        owner_agent="AJ", execution_adapter=adapter, risk_level=risk_level,
        availability=AVAILABLE, verification_status=VERIFIED, forbidden=forbidden,
    )


def make_runtime(tmp_path, specs=(), actions=None):
    """A fully local control plane: no agents, no execution runtime, no network."""
    sink = MemoryAuditSink()
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    registry = CapabilityRegistry()
    registry.register_many(internal_specs())
    registry.register_many(specs)
    aj = Aj(
        registry=registry,
        agents=AgentRegistry([]),
        authorizer=Authorizer(gate=ApprovalGate()),
        audit=AuditLog(sink),
        tasks=TaskStore(),
        execution=UnavailableExecutionAdapter(),
        skills=SkillRegistry(),
        config=make_config(),
        memory=memory,
        actions=actions or InternalActions({"echo": echo, "boom": _boom}),
    )
    return aj, sink, memory


# --- end-to-end ----------------------------------------------------------
def test_end_to_end_lifecycle_audits_and_persists_raw_events(tmp_path):
    aj, sink, memory = make_runtime(tmp_path)

    outcome = aj.handle("say hello", capability_id="aj.echo", payload={"text": "hello"})

    assert outcome.ok and outcome.status == COMPLETED
    assert outcome.output == {"echo": "hello"}
    assert outcome.capability_id == "aj.echo"

    actions = [event["action"] for event in sink.events]
    for expected in ("task_received", "authorized", "executed"):
        assert expected in actions

    events = memory.events(task_id=outcome.task_id, limit=50)
    kinds = [event.kind for event in events]
    assert {"task.created", "task.authorized", "task.completed"} <= set(kinds)
    for event in events:
        assert event.source == "aj" and event.task_id == outcome.task_id

    record = aj.tasks.get(outcome.task_id)
    assert record.status == COMPLETED and record.terminal
    assert any(entry["action"] == "execute" for entry in record.actions_taken)
    assert record.evidence[0]["verified"] is True


def test_permission_gate_blocks_consequential_capability_until_approved(tmp_path):
    aj, sink, memory = make_runtime(
        tmp_path, [extra_spec(capability_id="aj.sensitive", risk_level=3)]
    )

    blocked = aj.handle("do sensitive", capability_id="aj.sensitive",
                        payload={"text": "x"})
    assert not blocked.ok and blocked.status == WAITING_FOR_APPROVAL
    assert blocked.requires_user_decision
    assert not any(event["action"] == "executed" for event in sink.events)
    assert "task.completed" not in [e.kind for e in memory.events(limit=50)]

    approval = aj.authorizer.gate.issue("aj.sensitive", {"text": "x"})
    allowed = aj.handle("do sensitive", capability_id="aj.sensitive",
                        payload={"text": "x"}, approval=approval.token)
    assert allowed.ok and allowed.status == COMPLETED


def test_forbidden_capability_aborts_before_any_execution(tmp_path):
    aj, sink, _ = make_runtime(
        tmp_path,
        [extra_spec(capability_id="aj.forbidden", risk_level=3, forbidden=True)],
    )
    outcome = aj.handle("never", capability_id="aj.forbidden")
    assert not outcome.ok and outcome.status == "ABORTED"
    assert not any(event["action"] == "executed" for event in sink.events)


def test_missing_capability_fails_with_a_specific_code(tmp_path):
    aj, _, _ = make_runtime(tmp_path)
    outcome = aj.handle("do it", capability_id="aj.missing")
    assert not outcome.ok and outcome.status == FAILED
    assert outcome.errors[0]["code"] == "capability_not_found"


def test_action_failure_marks_the_task_failed_and_is_audited(tmp_path):
    aj, sink, memory = make_runtime(
        tmp_path, [extra_spec(capability_id="aj.boom", adapter="internal:boom")]
    )
    outcome = aj.handle("boom", capability_id="aj.boom")

    assert not outcome.ok and outcome.status == FAILED
    assert outcome.errors[0]["code"] == "execution_failed"
    assert "intentional failure" in outcome.summary
    assert any(event["action"] == "failed" for event in sink.events)
    assert "task.failed" in [e.kind for e in memory.events(limit=50)]


def test_invalid_task_is_rejected_and_no_record_is_created(tmp_path):
    store = TaskStore()
    with pytest.raises(errors.AjError):
        store.create("   ")
    assert store.all() == []


# --- health and CLI ------------------------------------------------------
def test_health_check_passes_with_no_network_agents_or_credentials():
    report = health(make_config())
    assert report["ok"] is True, report["failures"]
    assert report["attached"] == {"jarvis": False, "helix": False,
                                  "hermes": "NOT ATTACHED"}
    for name in ("configuration", "task_lifecycle", "permissions", "capabilities",
                 "audit", "memory", "providers", "execution", "orchestrator"):
        assert report["checks"][name]["ok"] is True, name


def test_cli_check_runs_as_a_module():
    completed = subprocess.run(
        [sys.executable, "-m", "aj", "--check"],
        cwd=str(AJ_ROOT), capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True and payload["version"]


def test_demo_proves_the_whole_lifecycle_and_persists_records(tmp_path):
    config = make_config(
        core={"data_dir": str(tmp_path), "audit_dir": str(tmp_path / "audit")},
        runtime={"persist_tasks": False, "persist_memory": True},
    )
    report = run_demo(config)

    assert report["outcome"]["ok"] is True
    assert report["outcome"]["output"] == {"echo": "hello from AJ"}
    assert report["memory"]["raw_events"] >= 3
    assert [event["kind"] for event in report["memory_events"]] == [
        "task.created", "task.authorized", "task.completed",
    ]


# --- provider abstraction ------------------------------------------------
def test_mock_provider_completes_without_network_or_credentials():
    provider = MockProvider(text="local mock reply")
    registry = ProviderRegistry(
        [ProviderSpec(slug="mock", enabled=True,
                      models=[ModelSpec("mock:default", "mock")])],
        {"mock": provider},
    )
    response = Gateway(registry).complete(
        ChatRequest(messages=(Message("user", "hi"),))
    )
    assert response.text == "local mock reply" and response.provider == "mock"
    assert len(provider.requests) == 1
    assert provider.requests[0].messages[0].content == "hi"


def test_mock_provider_failure_is_normalised_and_does_not_fall_through():
    provider = MockProvider(
        error=errors.ProviderError("down", retryable=False)
    )
    registry = ProviderRegistry(
        [ProviderSpec(slug="mock", enabled=True,
                      models=[ModelSpec("mock:default", "mock")])],
        {"mock": provider},
    )
    with pytest.raises(errors.AjError) as excinfo:
        Gateway(registry, max_attempts=1).complete(
            ChatRequest(messages=(Message("user", "hi"),))
        )
    assert excinfo.value.code == errors.PROVIDER_UNAVAILABLE
