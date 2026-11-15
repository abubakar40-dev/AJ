import json
from pathlib import Path

import pytest

from aj.errors import AjError
from aj.execution_domain import (
    CANCELLED,
    COMPLETED,
    CREATED,
    FAILED,
    READY,
    RECOVERY_REQUIRED,
    RUNNING,
    UNKNOWN,
    ExecutionRecord,
    ExecutionStore,
)
from aj.ids import new_execution_id
from aj.runtime import assemble

from aj.config import load


def make_aj(tmp_path):
    cfg = load(env={}, overrides={
        "core": {"data_dir": str(tmp_path), "audit_dir": str(tmp_path / "audit")},
        "runtime": {"persist_tasks": True, "persist_memory": False},
    })
    return assemble(cfg)


def test_execution_creation_and_stable_id_linked_to_task(tmp_path):
    aj = make_aj(tmp_path)
    out = aj.handle("say hello", capability_id="aj.echo")
    assert out.ok
    task = aj.tasks.get(out.task_id)
    assert task.current_execution_id.startswith("exc_")
    assert task.current_execution_id in task.execution_ids
    execs = aj.executions.list(task_id=task.task_id)
    assert len(execs) == 1
    assert execs[0].execution_id == task.current_execution_id
    assert execs[0].task_id == task.task_id
    assert execs[0].operation_id == task.operation_id
    # Task != Execution != Attempt
    assert task.task_id != execs[0].execution_id
    assert task.attempts
    assert task.attempts[-1]["attempt_id"] != execs[0].execution_id


def test_execution_attempt_relationship_and_correlation(tmp_path):
    aj = make_aj(tmp_path)
    out = aj.handle("say hello", capability_id="aj.echo")
    task = aj.tasks.get(out.task_id)
    att = task.attempts[-1]
    assert att["execution_id"] == task.current_execution_id
    ex = aj.executions.get(task.current_execution_id)
    assert ex is not None
    assert att["attempt_id"] in ex.attempt_ids
    assert ex.current_attempt_id == att["attempt_id"]

    receipts = aj.receipts.list(task_id=task.task_id, limit=0)
    assert receipts
    assert receipts[-1].get("attempt_id") == att["attempt_id"]
    assert (receipts[-1].get("metadata") or {}).get("execution_id") == task.current_execution_id

    events = aj.journal.events(task_id=task.task_id, limit=0)
    assert events
    started = [e for e in events if e.get("event_type") == "EXECUTION_STARTED"]
    assert started
    assert (started[-1].get("metadata") or {}).get("execution_id") == task.current_execution_id


def test_valid_and_invalid_execution_transitions():
    rec = ExecutionRecord(execution_id=new_execution_id(), task_id="task-1", operation_id="op-1")
    rec.transition(READY)
    rec.transition(RUNNING)
    rec.transition(COMPLETED)
    assert rec.status == COMPLETED
    assert rec.terminal
    with pytest.raises(AjError):
        rec.transition(RUNNING)  # terminal

    rec2 = ExecutionRecord(execution_id=new_execution_id(), task_id="task-1")
    with pytest.raises(AjError):
        rec2.transition(COMPLETED)  # illegal from CREATED
    with pytest.raises(AjError):
        rec2.transition("MADE_UP")


def test_multiple_attempts_under_one_execution(tmp_path):
    aj = make_aj(tmp_path)
    # create a failing task that can be retried (aj.echo is replay_safe/retry path via recovery/retry semantics on FAILED)
    rec = aj.tasks.create("retry probe", capability_id="aj.echo")
    rec.request_payload = {"goal": "retry probe"}
    aj.tasks.save(rec, "payload")
    for st in ("UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING", "FAILED"):
        aj.tasks.transition(rec.task_id, st)
    # seed a first attempt/execution context explicitly (simulate prior failed run)
    rec = aj.tasks.get(rec.task_id)
    ex = aj._ensure_execution(rec, reason="seed")
    aj._transition_execution(rec, RUNNING, detail="seed")
    aj._start_attempt(rec)
    rec = aj.tasks.get(rec.task_id)
    aj._finish_attempt(rec, "FAILED", AjError("boom"))
    aj.tasks.save(rec, "seed_failed")
    first_xid = rec.current_execution_id
    first_attempts = len(rec.attempts)

    out = aj.retry(rec.task_id)
    assert out.ok
    task = aj.tasks.get(rec.task_id)
    # same task, additional attempt(s); execution domain remains explicit and linked
    assert task.task_id == rec.task_id
    assert len(task.attempts) >= first_attempts + 1
    # current implementation reuses current execution context for task retries (minimal 5A.4)
    assert task.current_execution_id == first_xid
    ex2 = aj.executions.get(first_xid)
    assert ex2 is not None
    assert len(ex2.attempt_ids) >= 2


def test_execution_persistence_and_reload(tmp_path):
    cfg = load(env={}, overrides={
        "core": {"data_dir": str(tmp_path), "audit_dir": str(tmp_path / "audit")},
        "runtime": {"persist_tasks": True, "persist_memory": False},
    })
    aj = assemble(cfg)
    out = aj.handle("say hello", capability_id="aj.echo")
    task = aj.tasks.get(out.task_id)
    xid = task.current_execution_id
    assert (tmp_path / "executions.jsonl").is_file()

    aj2 = assemble(cfg)
    ex = aj2.executions.get(xid)
    assert ex is not None
    assert ex.task_id == task.task_id
    assert ex.status in (COMPLETED, RUNNING, READY, CREATED)
    task2 = aj2.tasks.get(task.task_id)
    assert task2.current_execution_id == xid
    assert xid in task2.execution_ids


def test_execution_persistence_failure_is_fail_closed(tmp_path):
    aj = make_aj(tmp_path)
    # Force persistence failure: replace file path with a directory so append open fails.
    bad = tmp_path / "executions.jsonl"
    if bad.exists():
        bad.unlink()
    bad.mkdir()
    aj.executions.path = bad
    with pytest.raises(AjError):
        aj.handle("say hello", capability_id="aj.echo")


def test_unknown_and_recovery_required_outcomes_representable(tmp_path):
    # Execution domain can represent unknown/recovery-required without claiming success.
    store = ExecutionStore(tmp_path / "executions.jsonl")
    rec = ExecutionRecord(execution_id=new_execution_id(), task_id="t1", operation_id="o1")
    store.create(rec)
    store.transition(rec.execution_id, RUNNING)
    store.transition(rec.execution_id, UNKNOWN, detail="external outcome unknown")
    ex = store.get(rec.execution_id)
    assert ex.status == UNKNOWN
    store.transition(rec.execution_id, RECOVERY_REQUIRED, detail="needs review")
    assert store.get(rec.execution_id).status == RECOVERY_REQUIRED
    # still not success/fabricated completion
    assert store.get(rec.execution_id).status != COMPLETED


def test_idempotent_execution_creation_local_reuse(tmp_path):
    aj = make_aj(tmp_path)
    task = aj.tasks.create("x", capability_id="aj.echo")
    ex1 = aj._ensure_execution(task)
    aj.tasks.save(task, "exec_linked")
    ex2 = aj._ensure_execution(aj.tasks.get(task.task_id))
    assert ex1 is not None and ex2 is not None
    assert ex1.execution_id == ex2.execution_id
    assert aj.executions.list(task_id=task.task_id).__len__() == 1


def test_execution_distinct_from_lease(tmp_path):
    aj = make_aj(tmp_path)
    out = aj.handle("say hello", capability_id="aj.echo")
    task = aj.tasks.get(out.task_id)
    xid = task.current_execution_id
    lease = aj.leases.get(task.task_id)  # execution lease may or may not be active post-run
    # execution identity is AJ-owned domain record; lease is coordination primitive (different concept)
    if lease is not None:
        assert xid != lease.lease_id
    ex = aj.executions.get(xid)
    assert ex is not None
    assert ex.execution_id == xid
    # no duplicate lease system introduced; lease manager API unchanged conceptually
    assert hasattr(aj, "leases") and hasattr(aj.leases, "get")
