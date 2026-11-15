"""Phase 2 tests: persistence, restart, recovery, summaries, integrity, CLI."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aj import errors
from aj import summary as summary_mod
from aj.actions import InternalActions, echo
from aj.actions import specs as internal_specs
from aj.agents import AgentRegistry
from aj.audit import AuditLog, MemoryAuditSink
from aj.capability import AVAILABLE, VERIFIED, CapabilityRegistry, CapabilitySpec
from aj.execution import SkillRegistry, UnavailableExecutionAdapter
from aj.memory import MemoryStore
from aj.orchestrator import Aj
from aj.permissions import ApprovalGate, Authorizer
from aj.recovery import RecoveryManager
from aj.runtime import health
from aj.task import (
    AUTHORIZED,
    COMPLETED,
    EXECUTING,
    FAILED,
    PLANNED,
    RECOVERY_REQUIRED,
    UNDERSTANDING,
    TaskStore,
)

from conftest import make_config

AJ_ROOT = Path(__file__).resolve().parent.parent


def _boom(arguments):
    raise RuntimeError("intentional failure")


def extra_spec(*, capability_id="aj.sensitive", risk_level=0,
               adapter="internal:echo", replay_safe=False):
    return CapabilitySpec(
        capability_id=capability_id, name=capability_id, description="",
        owner_agent="AJ", execution_adapter=adapter, risk_level=risk_level,
        availability=AVAILABLE, verification_status=VERIFIED,
        replay_safe=replay_safe,
    )


def make_aj(*, tasks, memory=None, audit_sink=None, specs=(), config=None):
    registry = CapabilityRegistry()
    registry.register_many(internal_specs())
    registry.register_many(specs)
    return Aj(
        registry=registry,
        agents=AgentRegistry(),
        authorizer=Authorizer(gate=ApprovalGate()),
        audit=AuditLog(audit_sink or MemoryAuditSink()),
        tasks=tasks,
        execution=UnavailableExecutionAdapter(),
        skills=SkillRegistry(),
        config=config or make_config(),
        memory=memory,
        actions=InternalActions({"echo": echo, "boom": _boom}),
    )


def _raw_digest(store: MemoryStore) -> str:
    rows = [event.to_dict() for event in store.events(limit=100_000)]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str)
                          .encode("utf-8")).hexdigest()


# --- persistence and restart --------------------------------------------
def test_task_survives_a_process_style_restart(tmp_path):
    directory = tmp_path / "tasks"
    store = TaskStore(directory)
    aj = make_aj(tasks=store)
    outcome = aj.handle("echo", capability_id="aj.echo",
                        payload={"text": "persist me"})
    assert outcome.ok

    reopened = TaskStore(directory)
    record = reopened.get(outcome.task_id)
    assert record.status == COMPLETED
    assert record.request_payload == {"text": "persist me"}
    assert [event["status"] for event in record.events][-1] == COMPLETED
    assert reopened.load_errors == []


def test_failed_task_is_persisted_with_its_error(tmp_path):
    directory = tmp_path / "tasks"
    store = TaskStore(directory)
    aj = make_aj(tasks=store,
                 specs=[extra_spec(capability_id="aj.boom",
                                   adapter="internal:boom")])
    outcome = aj.handle("boom", capability_id="aj.boom")
    assert not outcome.ok and outcome.status == FAILED

    reopened = TaskStore(directory)
    record = reopened.get(outcome.task_id)
    assert record.status == FAILED
    assert record.errors[0]["code"] == "execution_failed"
    assert any(event["status"] == FAILED for event in record.events)


def test_corrupted_record_is_reported_and_history_is_not_deleted(tmp_path):
    directory = tmp_path / "tasks"
    store = TaskStore(directory)
    valid = store.create("valid task")
    path = directory / "tasks.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{not json}\n")
        handle.write(json.dumps({"task": {"task_id": "broken", "goal": "g",
                                          "status": "NOT_A_STATUS",
                                          "created_at": 1}}) + "\n")

    reopened = TaskStore(directory)
    assert [record.task_id for record in reopened.all()] == [valid.task_id]
    assert len(reopened.load_errors) == 2
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3


# --- recovery ------------------------------------------------------------
def test_interrupted_task_is_detected_and_never_blindly_replayed(tmp_path):
    directory = tmp_path / "tasks"
    store = TaskStore(directory)
    record = store.create("unsafe", capability_id="aj.boom")
    store.transition(record.task_id, UNDERSTANDING)
    store.transition(record.task_id, PLANNED)
    store.transition(record.task_id, AUTHORIZED)

    sink = MemoryAuditSink()
    aj = make_aj(tasks=store, audit_sink=sink,
                 specs=[extra_spec(capability_id="aj.boom",
                                   adapter="internal:boom")])
    manager = RecoveryManager(aj)
    findings = manager.scan()
    assert len(findings) == 1 and findings[0].decision == "recovery_required"

    outcome = manager.recover(record.task_id)["outcomes"][0]
    assert outcome["ok"] is False
    assert store.get(record.task_id).status == RECOVERY_REQUIRED
    assert not any(event["action"] == "executed" for event in sink.events)
    assert any(event["action"] == "recovery_refused" for event in sink.events)


def test_replay_safe_task_recovers_without_losing_history(tmp_path):
    directory = tmp_path / "tasks"
    store = TaskStore(directory)
    record = store.create("echo", capability_id="aj.echo")
    record.request_payload = {"text": "recover me"}
    store.save(record, "test-setup")
    for status in (UNDERSTANDING, PLANNED, AUTHORIZED, EXECUTING):
        store.transition(record.task_id, status)
    before = list(store.get(record.task_id).events)

    sink = MemoryAuditSink()
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    aj = make_aj(tasks=store, memory=memory, audit_sink=sink)
    outcome = RecoveryManager(aj).recover(record.task_id)["outcomes"][0]

    assert outcome["ok"] is True and outcome["status"] == COMPLETED
    assert outcome["task_id"] == record.task_id
    recovered = store.get(record.task_id)
    assert recovered.status == COMPLETED
    assert recovered.events[:len(before)] == before
    assert len(recovered.events) > len(before)
    assert any(event["action"] == "recovery_started" for event in sink.events)
    kinds = [event.kind for event in memory.events(task_id=record.task_id, limit=50)]
    assert "task.recovery" in kinds and "task.completed" in kinds

    # Repeated recovery must converge idempotently (3C): terminal tasks are not replayed/mutated.
    converged = RecoveryManager(aj).recover(record.task_id)["outcomes"][0]
    assert converged["ok"] is True and converged["status"] == COMPLETED
    assert converged["task_id"] == record.task_id
    assert "converged" in converged.get("summary", "").lower() or "terminal" in converged.get("summary", "").lower()
    assert store.get(record.task_id).status == COMPLETED
    assert store.get(record.task_id).events == recovered.events
    assert len([e for e in sink.events if e.get("action") == "recovery_started"]) == 1
    memory.close()


# --- summaries and integrity --------------------------------------------
def test_summary_rebuild_is_deterministic_and_leaves_raw_events_untouched(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.append_event("task.created", "goal", task_id="t1",
                       meta={"status": "RECEIVED"})
    store.append_event("task.authorized", "allowed", task_id="t1",
                       meta={"capability": "aj.echo", "permission_level": 0})
    store.append_event("task.completed", "done", task_id="t1",
                       meta={"status": "COMPLETED", "capability": "aj.echo"})
    before = _raw_digest(store)

    first = summary_mod.build(store)
    second = summary_mod.build(store)
    assert first["content"] == second["content"]
    assert first["source_event_ids"] == second["source_event_ids"]
    assert first["payload"]["task_count"] == 1
    assert first["payload"]["by_kind"]["task.completed"] == 1
    assert _raw_digest(store) == before
    assert store.count_events() == 3

    assert summary_mod.delete(store, first["summary_id"]) is True
    assert summary_mod.delete(store, second["summary_id"]) is True
    assert store.summaries(kind="task_digest") == []
    rebuilt = summary_mod.build(store)
    assert rebuilt["content"] == first["content"]
    assert _raw_digest(store) == before
    assert store.verify()["ok"] is True
    store.close()


# --- audit / memory correlation -----------------------------------------
def test_audit_and_memory_share_the_task_id_and_lifecycle(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    sink = MemoryAuditSink()
    aj = make_aj(tasks=TaskStore(), memory=memory, audit_sink=sink)
    outcome = aj.handle("say hi", capability_id="aj.echo",
                        payload={"text": "hi"})
    assert outcome.ok

    actions = [event["action"] for event in sink.events]
    for expected in ("task_received", "authorized", "executed"):
        assert expected in actions
    assert {event["task_id"] for event in sink.events} == {outcome.task_id}

    events = memory.events(task_id=outcome.task_id, limit=50)
    kinds = [event.kind for event in events]
    assert {"task.created", "task.authorized", "task.completed"} <= set(kinds)
    assert {event.task_id for event in events} == {outcome.task_id}
    memory.close()


# --- health --------------------------------------------------------------
def test_health_includes_phase2_components():
    report = health(make_config())
    assert report["ok"] is True, report["failures"]
    for name in ("task_persistence", "audit_reader", "memory_reader",
                 "recovery", "summary", "cli"):
        assert report["checks"][name]["ok"] is True, name


# --- CLI ----------------------------------------------------------------
def _write_config(tmp_path) -> Path:
    data = tmp_path / "data"
    config = {
        "core": {"data_dir": str(data),
                 "audit_dir": str(data / "audit"),
                 "memory_path": str(data / "memory.sqlite3")},
        "runtime": {"persist_tasks": True, "persist_memory": True},
    }
    path = tmp_path / "aj.config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _cli(config_path: Path, *argv, timeout=120):
    completed = subprocess.run(
        [sys.executable, "-m", "aj", "--config", str(config_path), *argv],
        cwd=str(AJ_ROOT), capture_output=True, text=True, timeout=timeout,
    )
    payload = json.loads(completed.stdout) if completed.stdout.strip() else None
    return completed, payload


def test_cli_run_inspect_and_query_round_trip(tmp_path):
    config_path = _write_config(tmp_path)
    completed, payload = _cli(
        config_path, "run", "--capability", "aj.echo",
        "--input", '{"message":"phase 2 test"}', "--json",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    outcome = payload
    assert outcome["ok"] is True and outcome["status"] == COMPLETED
    assert outcome["output"] == {"echo": "phase 2 test"}
    task_id = outcome["task_id"]

    completed, payload = _cli(config_path, "tasks", "--json")
    assert completed.returncode == 0
    assert [task["task_id"] for task in payload["tasks"]] == [task_id]

    completed, payload = _cli(config_path, "task", task_id, "--json")
    assert completed.returncode == 0
    record = payload["task"]
    assert record["status"] == COMPLETED
    assert [event["status"] for event in record["events"]][-1] == COMPLETED

    completed, payload = _cli(config_path, "audit", "--task", task_id, "--json")
    assert completed.returncode == 0
    assert {event["task_id"] for event in payload["events"]} == {task_id}
    assert any(event["action"] == "executed" for event in payload["events"])

    completed, payload = _cli(config_path, "memory", "--task", task_id, "--json")
    assert completed.returncode == 0
    kinds = [event["kind"] for event in payload["events"]]
    assert "task.completed" in kinds and payload["stats"]["raw_events"] == 3

    completed, payload = _cli(config_path, "recover", "--json")
    assert completed.returncode == 0
    assert payload["findings"] == []


def test_cli_refuses_non_internal_capabilities(tmp_path):
    config_path = _write_config(tmp_path)
    completed, payload = _cli(config_path, "run", "--capability",
                              "jarvis.web_search", "--json")
    assert completed.returncode == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] in ("capability_unavailable",
                                        "capability_not_found")


def test_cli_rejects_unknown_capability_and_bad_input(tmp_path):
    config_path = _write_config(tmp_path)
    completed, payload = _cli(config_path, "run", "--capability", "aj.nope",
                              "--json")
    assert completed.returncode == 4  # not found, per the phase 3 exit map
    assert payload["error"]["code"] == "capability_not_found"

    completed, payload = _cli(config_path, "run", "--capability", "aj.echo",
                              "--input", "not json", "--json")
    assert completed.returncode == 5  # configuration failure
    assert payload["error"]["code"] == "config_invalid"
