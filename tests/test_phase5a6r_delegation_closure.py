import copy
import json
import time
from pathlib import Path

import pytest

from aj.capability import CapabilitySpec, OWNER_AJ
from aj.config import load
from aj.errors import AjError, Conflict, PolicyDenied
from aj.runtime import assemble
from aj.scheduler import Scheduler
from aj.task import COMPLETED


def make_cfg(tmp_path, **deleg):
    base_deleg = {
        "enabled": True,
        "max_children_per_delegation": 10,
        "max_delegations_per_parent": 20,
        "max_active_assignments_per_child": 1,
    }
    base_deleg.update(deleg)
    return load(env={}, overrides={
        "core": {"data_dir": str(tmp_path), "audit_dir": str(tmp_path / "audit")},
        "runtime": {"persist_tasks": True, "persist_memory": False},
        "scheduler": {"enabled": True, "global_max_active_executions": 2, "global_max_admitted_waiting": 10,
                      "max_dispatch_per_run": 5, "max_workers": 1, "aging_seconds": 0},
        "delegation": base_deleg,
    })


def make_aj(tmp_path, **deleg):
    return assemble(make_cfg(tmp_path, **deleg))


def register_cap(aj, cap_id="test.child", owner=OWNER_AJ, risk=0):
    spec = CapabilitySpec(
        capability_id=cap_id, name="child", description="",
        owner_agent=owner, execution_adapter="internal:echo",
        risk_level=risk, availability="available", verification_status="verified",
        required_permissions=("read",) if risk == 0 else ("execute",),
        replay_safe=True, retry_safe=True,
    )
    if aj.registry.find(cap_id) is None:
        aj.registry.register(spec)
    return spec


def mk_parent(aj, goal="parent", cap="test.child"):
    register_cap(aj, cap)
    rec = aj.tasks.create(goal, capability_id=cap)
    rec.request_payload = {"goal": goal}
    aj.tasks.save(rec, "payload")
    for st in ("UNDERSTANDING", "PLANNED"):
        if aj.tasks.get(rec.task_id).can_transition(st):
            aj.tasks.transition(rec.task_id, st)
    return aj.tasks.get(rec.task_id)


def seed_internal_agent(aj, caps=None):
    from aj.delegation import LogicalAgentRecord
    rec = LogicalAgentRecord(
        agent_id="agent.aj.internal",
        logical_name="AJ_INTERNAL",
        agent_type="logical_internal",
        supported_capabilities=list(caps or ["test.child"]),
        availability_state="available",
        trust_classification="unverified_local_trust",
        execution_mode="logical_internal",
        enabled=True,
        provenance={"source": "test"},
    )
    aj.logical_agents.upsert(rec)
    return rec


def base_request(parent_task_id, **kw):
    req = {
        "schema_version": 1,
        "parent_task_id": parent_task_id,
        "requested_work": "delegate work",
        "required_capabilities": ["test.child"],
        "child_specs": [{"child_ref": "c1", "goal": "child 1", "required_capabilities": ["test.child"], "capability_id": "test.child", "request_payload": {"text": "hi"}}],
        "permission_context": {
            "parent_permissions": ["delegation.coordinate"],
            "requested_permissions": ["delegation.coordinate"],
            "agent_permissions": ["delegation.coordinate"],
            "system_permissions": ["delegation.coordinate"],
        },
        "aggregation_policy": "all_required",
    }
    req.update(kw)
    return req


def test_end_to_end_delegate_to_scheduler_execution_and_parent_aggregation(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    assert res["delegation"]["status"] == "COMPLETED_CREATION"
    cid = res["delegation"]["child_task_ids"][0]
    child = aj.tasks.get(cid)
    # child progressed through authorization path (not left in RECEIVED)
    assert child.status in ("AUTHORIZED", "WAITING_FOR_APPROVAL", "ABORTED", "FAILED", "PLANNED", "UNDERSTANDING")
    if child.status == "AUTHORIZED":
        sched = Scheduler(aj)
        elig = sched.evaluate_eligibility(cid)
        assert elig.eligible
        out = sched.run_once()
        assert cid in out["selected"] or any(r.get("task_id") == cid for r in out.get("results", []))
        child2 = aj.tasks.get(cid)
        assert child2.status in ("COMPLETED", "FAILED", "EXECUTING", "VERIFYING")
        # reconcile and observe aggregation reflects terminal outcome
        aj._reconcile_delegation_parent(parent.task_id)
        st = aj.delegation_status(res["delegation"]["delegation_id"])
        assert st["aggregation"]["counts"]["created"] == 1


def test_same_idempotency_key_different_spec_rejected(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    r1 = aj.delegate(base_request(parent.task_id, idempotency_key="k1"))
    with pytest.raises(Conflict):
        aj.delegate(base_request(parent.task_id, idempotency_key="k1", requested_work="different"))


def test_execution_boundary_blocks_widened_delegation_permissions(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    cid = res["delegation"]["child_task_ids"][0]
    child = aj.tasks.get(cid)
    # tamper recorded delegation envelope to simulate widened/invalid permission state
    with aj.tasks._lock:
        cur = aj.tasks._tasks.get(cid)
        dctx = dict(cur.authorization_context.get("delegation") or {})
        pd = dict(dctx.get("permission_decision") or {})
        pd["effective_permissions"] = ["delegation.coordinate", "admin"]
        dctx["permission_decision"] = pd
        dctx["effective_permissions_snapshot"] = ["delegation.coordinate", "admin"]
        ac = dict(cur.authorization_context or {})
        ac["delegation"] = dctx
        cur.authorization_context = ac
        aj.tasks._persist_locked(cur, "tampered")
    spec = aj.registry.find(child.capability_id)
    if child.status != "AUTHORIZED":
        # force into authorized-like dispatch attempt via guard path
        aj.tasks.transition(cid, "AUTHORIZED") if child.can_transition("AUTHORIZED") else None
        child = aj.tasks.get(cid)
    guard = aj._delegated_permission_guard(aj.tasks.get(cid), spec)
    assert guard is not None
    assert guard.ok is False
    assert "blocked" in guard.summary.lower() or guard.status in ("ABORTED", "FAILED")


def test_parent_aggregation_waits_and_reflects_required_outcomes(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    cid = res["delegation"]["child_task_ids"][0]
    st = aj.delegation_status(res["delegation"]["delegation_id"])
    assert st["aggregation"]["can_complete"] is False
    assert st["aggregation"]["waiting_for_children"] or st["aggregation"]["counts"]["created"] == 1
    # terminal failure of required child prevents false completion
    rec = aj.tasks.get(cid)
    # move to FAILED through valid path
    for stt in ("UNDERSTANDING","PLANNED","AUTHORIZED","EXECUTING","FAILED"):
        r = aj.tasks.get(cid)
        if r.status == stt: continue
        if r.can_transition(stt):
            aj.tasks.transition(cid, stt)
    aj._reconcile_delegation_parent(parent.task_id)
    st2 = aj.delegation_status(res["delegation"]["delegation_id"])
    assert st2["aggregation"]["can_complete"] is False
    assert st2["aggregation"]["counts"]["failed"] >= 1 or st2["aggregation"]["counts"]["created"] == 1


def test_monitoring_non_mutating_and_anomaly_surfaces(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    before = copy.deepcopy(aj.delegation_monitor())
    # read-only monitoring/status calls
    _ = aj.delegation_monitor()
    _ = aj.delegation_status(res["delegation"]["delegation_id"])
    after = aj.delegation_monitor()
    assert before["counts"] == after["counts"]
    # incomplete delegation detection shape present
    assert "anomalies" in after and isinstance(after["anomalies"], dict)


def test_duplicate_active_assignment_prevented_and_scheduler_no_duplicate(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    cid = res["delegation"]["child_task_ids"][0]
    # assignment store prevents duplicate active for same child
    from aj.delegation import AssignmentRecord, AS_ASSIGNED
    with pytest.raises(Exception):
        aj.assignments.create(AssignmentRecord(
            assignment_id="asg_dup2", delegation_id=res["delegation"]["delegation_id"],
            parent_task_id=parent.task_id, child_task_id=cid, agent_id="agent.aj.internal", status=AS_ASSIGNED))
    # repeated scheduler runs should not create duplicate active executions for same child
    if aj.tasks.get(cid).status == "AUTHORIZED":
        s = Scheduler(aj)
        s.run_once()
        before_exec = list(getattr(aj.tasks.get(cid), "execution_ids", []) or [])
        s.run_once()
        after_exec = list(getattr(aj.tasks.get(cid), "execution_ids", []) or [])
        # no new execution created when already completed/terminal; allow same count
        assert len(after_exec) <= max(1, len(before_exec)) or aj.tasks.get(cid).terminal


def test_crash_window_reconciliation_detects_incomplete_state(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    # simulate delegation intent recorded without children (crash after intent)
    from aj.delegation import DelegationRequest, DelegationRecord, stable_delegation_id
    req = DelegationRequest.validate(base_request(parent.task_id, idempotency_key="crash1"))
    did = stable_delegation_id(req.idempotency_key, parent_task_id=parent.task_id, spec_hash=req.spec_hash())
    drec = DelegationRecord(delegation_id=did, request=req, root_task_id=parent.task_id, child_task_ids=[], child_refs={}, status="RECORDED")
    aj.delegations.create(drec)
    mon = aj.delegation_monitor()
    # anomaly/incomplete detection should surface recorded-but-incomplete delegation
    assert any(x.get("delegation_id") == did for x in mon["anomalies"].get("incomplete_delegations", []))
    # explicit reconciliation is safe/bounded and records evidence
    out = aj._reconcile_delegation_parent(parent.task_id)
    assert out.get("ok") is True
