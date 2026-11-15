import json
import threading
import time
from pathlib import Path

import pytest

from aj.capability import CapabilityRegistry, CapabilitySpec, OWNER_AJ
from aj.config import load
from aj.errors import AjError
from aj.execution_domain import RUNNING
from aj.runtime import assemble
from aj.scheduler import (
    ADMITTED,
    ALREADY_ACTIVE_OR_UNCERTAIN,
    AUTHORIZATION_REQUIRED,
    CAPABILITY_UNAVAILABLE,
    DEADLINE_EXCEEDED,
    DEFERRED_CAPACITY_ACTIVE,
    DEFERRED_PERSISTENCE_UNHEALTHY,
    DEFERRED_UNKNOWN_CAPACITY,
    DEPENDENCY_BLOCKED,
    ELIGIBLE,
    PERSISTENCE_UNAVAILABLE,
    RECOVERY_OR_REVIEW_REQUIRED,
    TERMINAL,
    Scheduler,
)


def make_cfg(tmp_path, **sched):
    base_sched = {
        "enabled": True,
        "global_max_active_executions": 2,
        "global_max_admitted_waiting": 10,
        "max_dispatch_per_run": 5,
        "max_workers": 1,
        "aging_seconds": 0,
    }
    base_sched.update(sched)
    return load(env={}, overrides={
        "core": {"data_dir": str(tmp_path), "audit_dir": str(tmp_path / "audit")},
        "runtime": {"persist_tasks": True, "persist_memory": False},
        "scheduler": base_sched,
    })


def make_aj(tmp_path, **sched):
    return assemble(make_cfg(tmp_path, **sched))


def register_internal(aj, cap_id="test.read", risk=0, adapter="internal:echo"):
    spec = CapabilitySpec(
        capability_id=cap_id, name="t", description="",
        owner_agent=OWNER_AJ, execution_adapter=adapter,
        risk_level=risk, availability="available", verification_status="verified",
        required_permissions=("read",) if risk == 0 else (),
        replay_safe=True, retry_safe=True,
    )
    aj.registry.register(spec)
    return spec


def authorize_task(aj, task_id):
    # move to AUTHORIZED through normal-ish transitions for deterministic setup
    for st in ("UNDERSTANDING", "PLANNED", "AUTHORIZED"):
        rec = aj.tasks.get(task_id)
        if rec.status == st:
            continue
        if rec.can_transition(st):
            aj.tasks.transition(task_id, st)


def test_eligible_task_identified_correctly(tmp_path):
    aj = make_aj(tmp_path)
    register_internal(aj)
    rec = aj.tasks.create("hello", capability_id="test.read")
    authorize_task(aj, rec.task_id)
    sched = Scheduler(aj)
    d = sched.evaluate_eligibility(rec.task_id)
    assert d.eligible is True
    assert d.reason_code == ELIGIBLE
    assert "eligible" in d.explanation.lower()


def test_unauthorized_and_terminal_and_dependency_blocked_not_eligible(tmp_path):
    aj = make_aj(tmp_path)
    register_internal(aj)
    sched = Scheduler(aj)

    wa = aj.tasks.create("need approval", capability_id="test.read")
    aj.tasks.transition(wa.task_id, "UNDERSTANDING")
    aj.tasks.transition(wa.task_id, "PLANNED")
    aj.tasks.transition(wa.task_id, "WAITING_FOR_APPROVAL")
    d = sched.evaluate_eligibility(wa.task_id)
    assert not d.eligible and d.reason_code == AUTHORIZATION_REQUIRED

    done = aj.tasks.create("done", capability_id="test.read")
    for st in ("UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING", "VERIFYING", "COMPLETED"):
        aj.tasks.transition(done.task_id, st)
    d = sched.evaluate_eligibility(done.task_id)
    assert not d.eligible and d.reason_code == TERMINAL

    dep = aj.tasks.create("dep missing", capability_id="test.read")
    dep.depends_on = ["missing-task-id"]
    aj.tasks.save(dep, "deps")
    aj.tasks.transition(dep.task_id, "UNDERSTANDING")
    aj.tasks.transition(dep.task_id, "PLANNED")
    aj.tasks.transition(dep.task_id, "BLOCKED", "deps")
    d = sched.evaluate_eligibility(dep.task_id)
    assert not d.eligible and d.reason_code == DEPENDENCY_BLOCKED
    assert "missing-task-id" in d.explanation


def test_already_running_or_active_lease_not_dispatched_again(tmp_path):
    aj = make_aj(tmp_path)
    register_internal(aj)
    rec = aj.tasks.create("run", capability_id="test.read")
    rec.request_payload = {"text": "run"}
    aj.tasks.save(rec, "payload")
    authorize_task(aj, rec.task_id)
    aj.tasks.transition(rec.task_id, "EXECUTING")
    sched = Scheduler(aj)
    d = sched.evaluate_eligibility(rec.task_id)
    assert not d.eligible and d.reason_code == ALREADY_ACTIVE_OR_UNCERTAIN

    # active lease on authorized task => not eligible/admitted for duplicate dispatch
    rec2 = aj.tasks.create("leased", capability_id="test.read")
    rec2.request_payload = {"text": "leased"}
    aj.tasks.save(rec2, "payload")
    authorize_task(aj, rec2.task_id)
    lease = aj.leases.acquire(rec2.task_id, "execute", worker_id="other")
    try:
        d2 = sched.evaluate_eligibility(rec2.task_id)
        assert not d2.eligible and d2.reason_code == ALREADY_ACTIVE_OR_UNCERTAIN
        res = sched.run_once()
        assert rec2.task_id not in res["selected"]
    finally:
        try:
            aj.leases.release(lease)
        except Exception:
            pass


def test_admission_success_and_reasons(tmp_path):
    aj = make_aj(tmp_path, global_max_active_executions=2)
    register_internal(aj)
    rec = aj.tasks.create("ok", capability_id="test.read")
    authorize_task(aj, rec.task_id)
    sched = Scheduler(aj)
    elig = sched.evaluate_eligibility(rec.task_id)
    adm = sched.evaluate_admission(rec.task_id, eligibility=elig)
    assert elig.eligible
    assert adm.admitted and not adm.deferred
    assert adm.reason_code == ADMITTED
    assert adm.explanation


def test_capacity_exhaustion_defers_admission(tmp_path):
    aj = make_aj(tmp_path, global_max_active_executions=1)
    register_internal(aj)
    # occupy active slot with an executing task
    busy = aj.tasks.create("busy", capability_id="test.read")
    authorize_task(aj, busy.task_id)
    aj.tasks.transition(busy.task_id, "EXECUTING")

    rec = aj.tasks.create("wait", capability_id="test.read")
    authorize_task(aj, rec.task_id)
    sched = Scheduler(aj)
    adm = sched.evaluate_admission(rec.task_id)
    assert not adm.admitted and adm.deferred
    assert adm.reason_code == DEFERRED_CAPACITY_ACTIVE
    assert "capacity" in adm.explanation.lower()


def test_unknown_capacity_and_persistence_failure_fail_closed(tmp_path):
    # unknown capacity: force active count failure
    aj = make_aj(tmp_path, global_max_active_executions=2)
    register_internal(aj)
    rec = aj.tasks.create("x", capability_id="test.read")
    rec.request_payload = {"text": "x"}
    aj.tasks.save(rec, "payload")
    authorize_task(aj, rec.task_id)
    sched = Scheduler(aj)
    sched._active_execution_count = lambda: (None, "capacity probe failed")
    adm = sched.evaluate_admission(rec.task_id)
    assert not adm.admitted and adm.deferred
    assert adm.reason_code == DEFERRED_UNKNOWN_CAPACITY

    # persistence failure in durable mode: durable intent/evidence append must fail closed
    aj2 = make_aj(tmp_path / "p2", global_max_active_executions=2)
    register_internal(aj2)
    rec2 = aj2.tasks.create("y", capability_id="test.read")
    rec2.request_payload = {"text": "y"}
    aj2.tasks.save(rec2, "payload")
    authorize_task(aj2, rec2.task_id)
    sched2 = Scheduler(aj2)
    led = sched2._ledger_store()
    def boom(*a, **k):
        raise OSError("disk I/O")
    led.append = boom  # simulate durable evidence write failure
    res = sched2.run_once()
    # dispatch should be deferred/fail-closed (no unsafe success, no state progression)
    assert res["completed"] == 0
    assert aj2.tasks.get(rec2.task_id).status == "AUTHORIZED"
    assert any(not r.get("ok", False) for r in res.get("results", [])) or rec2.task_id not in res.get("selected", [])


def test_deterministic_priority_fifo_and_fairness_aging(tmp_path):
    aj = make_aj(tmp_path, global_max_active_executions=5, max_dispatch_per_run=5, aging_seconds=1)
    register_internal(aj)
    ids = []
    # lower priority older task vs higher priority newer task
    a = aj.tasks.create("a", capability_id="test.read"); a.priority = 1; aj.tasks.save(a, "p"); authorize_task(aj, a.task_id)
    b = aj.tasks.create("b", capability_id="test.read"); b.priority = 5; aj.tasks.save(b, "p"); authorize_task(aj, b.task_id)
    sched = Scheduler(aj)
    q = sched.queue()
    assert [r["task_id"] for r in q[:2]] == [b.task_id, a.task_id]

    # FIFO within same effective group: same priority, earlier created first
    aj2 = make_aj(tmp_path / "fifo", global_max_active_executions=5, max_dispatch_per_run=5, aging_seconds=0)
    register_internal(aj2)
    t1 = aj2.tasks.create("t1", capability_id="test.read"); t1.priority = 1; aj2.tasks.save(t1, "p"); authorize_task(aj2, t1.task_id)
    time.sleep(0.01)
    t2 = aj2.tasks.create("t2", capability_id="test.read"); t2.priority = 1; aj2.tasks.save(t2, "p"); authorize_task(aj2, t2.task_id)
    q2 = Scheduler(aj2).queue()
    assert [r["task_id"] for r in q2[:2]] == [t1.task_id, t2.task_id]

    # aging prevents indefinite starvation (effective priority boost)
    aj3 = make_aj(tmp_path / "age", global_max_active_executions=5, max_dispatch_per_run=5, aging_seconds=1)
    register_internal(aj3)
    old = aj3.tasks.create("old", capability_id="test.read"); old.priority = 0; old.request_payload = {"text": "old"}; aj3.tasks.save(old, "p"); authorize_task(aj3, old.task_id)
    new = aj3.tasks.create("new", capability_id="test.read"); new.priority = 1; new.request_payload = {"text": "new"}; aj3.tasks.save(new, "p"); authorize_task(aj3, new.task_id)
    # save() preserves canonical created_at; adjust in-store timestamps for deterministic aging.
    aj3.tasks._tasks[old.task_id].created_at = time.time() - 20
    aj3.tasks._tasks[new.task_id].created_at = time.time()
    q3 = Scheduler(aj3).queue()
    assert q3[0]["task_id"] == old.task_id  # aged above newer higher base priority


def test_dispatch_uses_5a4_execution_domain_reuses_leases_and_records_reasons(tmp_path):
    aj = make_aj(tmp_path, global_max_active_executions=2, max_dispatch_per_run=2)
    register_internal(aj)
    rec = aj.tasks.create("exec", capability_id="test.read")
    rec.request_payload = {"text": "exec"}
    aj.tasks.save(rec, "payload")
    authorize_task(aj, rec.task_id)
    sched = Scheduler(aj)
    res = sched.run_once()
    assert res["completed"] == 1, res
    task = aj.tasks.get(rec.task_id)
    assert task.current_execution_id.startswith("exc_")
    assert aj.executions.get(task.current_execution_id) is not None
    assert "decisions" in res and res["decisions"]
    # dispatch intent/result evidence persisted
    led_path = Path(aj.config.get("core.data_dir")) / "scheduler_decisions.jsonl"
    assert led_path.is_file()
    kinds = [json.loads(l).get("kind") for l in led_path.read_text().splitlines() if l.strip()]
    assert "dispatch_intent" in kinds

    # repeated runs do not create duplicate active execution/dispatch
    before = len(aj.executions.list(task_id=task.task_id))
    res2 = sched.run_once()
    assert task.task_id not in res2["selected"]
    assert len(aj.executions.list(task_id=task.task_id)) == before


def test_bounded_concurrency_backpressure_and_monitoring(tmp_path):
    aj = make_aj(tmp_path, global_max_active_executions=2, global_max_admitted_waiting=1,
                 max_dispatch_per_run=1, max_workers=1)
    register_internal(aj)
    t1 = aj.tasks.create("t1", capability_id="test.read"); t1.request_payload={"text":"t1"}; aj.tasks.save(t1,"p"); authorize_task(aj, t1.task_id)
    t2 = aj.tasks.create("t2", capability_id="test.read"); t2.request_payload={"text":"t2"}; aj.tasks.save(t2,"p"); authorize_task(aj, t2.task_id)
    sched = Scheduler(aj)
    res = sched.run_once(limit=10, workers=5)
    assert res["limits"]["effective_limit"] == 1
    assert res["limits"]["effective_workers"] == 1
    assert len(res["selected"]) <= 1

    mon = sched.inspect()
    assert "counts" in mon and "eligible" in mon and "deferred" in mon and "reasons" in mon
    assert mon["counts"]["tasks_total"] >= 2
    assert "persistence" in mon


def test_recovery_required_and_expired_lease_not_blindly_eligible(tmp_path):
    aj = make_aj(tmp_path)
    register_internal(aj)
    rr = aj.tasks.create("rr", capability_id="test.read")
    authorize_task(aj, rr.task_id)
    aj.tasks.transition(rr.task_id, "RECOVERY_REQUIRED", "manual")
    d = Scheduler(aj).evaluate_eligibility(rr.task_id)
    assert not d.eligible and d.reason_code == RECOVERY_OR_REVIEW_REQUIRED

    # expired lease => uncertain, not eligible for blind redispatch
    rec = aj.tasks.create("exp", capability_id="test.read")
    authorize_task(aj, rec.task_id)
    lease = aj.leases.acquire(rec.task_id, "execute", worker_id="w", ttl=0.01)
    time.sleep(0.02)
    d2 = Scheduler(aj).evaluate_eligibility(rec.task_id)
    assert not d2.eligible and d2.reason_code in (ALREADY_ACTIVE_OR_UNCERTAIN, RECOVERY_OR_REVIEW_REQUIRED)
    try:
        # best effort cleanup not required
        pass
    finally:
        try:
            aj.leases.release(lease)
        except Exception:
            pass


def test_legacy_records_loadable_and_no_external_runtime_enabled(tmp_path):
    cfg = make_cfg(tmp_path)
    aj = assemble(cfg)
    register_internal(aj)
    out = aj.handle("say hi", capability_id="test.read")
    assert out.ok, out
    # reload
    aj2 = assemble(cfg)
    task = aj2.tasks.get(out.task_id)
    assert task is not None
    # Hermes remains not attached
    assert aj2.execution.describe().get("integration_status") == "NOT ATTACHED" or aj2.execution.describe().get("available") is False


def test_deadline_exceeded_ineligible(tmp_path):
    aj = make_aj(tmp_path)
    register_internal(aj)
    rec = aj.tasks.create("late", capability_id="test.read")
    rec.deadline = time.time() - 10
    aj.tasks.save(rec, "deadline")
    authorize_task(aj, rec.task_id)
    d = Scheduler(aj).evaluate_eligibility(rec.task_id)
    assert not d.eligible and d.reason_code == DEADLINE_EXCEEDED
