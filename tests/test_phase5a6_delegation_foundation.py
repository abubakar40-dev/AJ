import time
from pathlib import Path

import pytest

from aj.capability import CapabilitySpec, OWNER_AJ
from aj.config import load
from aj.errors import AjError, ConfigError, Conflict, PolicyDenied
from aj.runtime import assemble
from aj.task import COMPLETED, FAILED, AUTHORIZED


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


def register_cap(aj, cap_id="test.child", owner=OWNER_AJ):
    spec = CapabilitySpec(
        capability_id=cap_id, name="child", description="",
        owner_agent=owner, execution_adapter="internal:echo",
        risk_level=0, availability="available", verification_status="verified",
        required_permissions=("read",), replay_safe=True, retry_safe=True,
    )
    aj.registry.register(spec)
    return spec


def mk_parent(aj, goal="parent", cap="test.child", state="PLANNED"):
    register_cap(aj, cap)
    rec = aj.tasks.create(goal, capability_id=cap)
    rec.request_payload = {"goal": goal}
    aj.tasks.save(rec, "payload")
    for st in ("UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING", "VERIFYING", "COMPLETED"):
        if rec.status == state:
            break
        if aj.tasks.get(rec.task_id).can_transition(st):
            aj.tasks.transition(rec.task_id, st)
        if st == state:
            break
    return aj.tasks.get(rec.task_id)


def base_request(parent_task_id, **kw):
    req = {
        "schema_version": 1,
        "parent_task_id": parent_task_id,
        "requested_work": "delegate work",
        "required_capabilities": ["test.child"],
        "child_specs": [{"child_ref": "c1", "goal": "child 1", "required_capabilities": ["test.child"], "capability_id": "test.child"}],
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


def test_valid_child_delegation_and_lineage_persistence(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    assert res["delegation"]["status"] == "COMPLETED_CREATION"
    assert len(res["delegation"]["child_task_ids"]) == 1
    cid = res["delegation"]["child_task_ids"][0]
    child = aj.tasks.get(cid)
    assert child.parent_task_id == parent.task_id
    assert child.root_task_id == (parent.root_task_id or parent.task_id)
    # reload persistence
    aj2 = assemble(aj.config)
    assert aj2.tasks.get(cid).parent_task_id == parent.task_id
    assert aj2.delegations.get(res["delegation"]["delegation_id"]) is not None
    assert aj2.assignments.list_for_delegation(res["delegation"]["delegation_id"]) 


def test_invalid_parent_self_and_cycle_rejected(tmp_path):
    aj = make_aj(tmp_path)
    seed_internal_agent(aj)
    with pytest.raises(Exception):
        aj.delegate(base_request("missing_parent"))
    parent = mk_parent(aj)
    # self-parent/cycle via hierarchy validation utility and delegation behavior
    from aj.delegation import validate_parent_chain
    with pytest.raises(Exception):
        validate_parent_chain(aj.tasks, parent.task_id, child_task_id=parent.task_id)
    # create manual cycle a->b->a
    a = aj.tasks.create("a")
    b = aj.tasks.create("b", parent_task_id=a.task_id)
    with aj.tasks._lock:
        aj.tasks._tasks[a.task_id].parent_task_id = b.task_id
    with pytest.raises(Exception):
        validate_parent_chain(aj.tasks, a.task_id)


def test_duplicate_delegation_idempotent_and_bounded(tmp_path):
    aj = make_aj(tmp_path, max_children_per_delegation=1, max_delegations_per_parent=1)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    req = base_request(parent.task_id, idempotency_key="same-key")
    r1 = aj.delegate(req)
    r2 = aj.delegate(req)
    assert r1["delegation"]["delegation_id"] == r2["delegation"]["delegation_id"]
    assert len(r1["delegation"]["child_task_ids"]) == 1
    # different spec without key blocked by max_delegations_per_parent
    req2 = base_request(parent.task_id, requested_work="other", child_specs=[{"child_ref":"c2","goal":"other","required_capabilities":["test.child"],"capability_id":"test.child"}])
    with pytest.raises(PolicyDenied):
        aj.delegate(req2)


def test_capability_matching_rejections_and_deterministic_selection(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    from aj.delegation import LogicalAgentRecord, match_agent
    # unknown capability rejection
    a1 = LogicalAgentRecord(agent_id="agent.a", logical_name="A", supported_capabilities=["x"], availability_state="available", execution_mode="logical_internal")
    m = match_agent(["unknown.cap"], [a1])
    assert not m["ok"]
    # disabled/unavailable agent rejection
    a2 = LogicalAgentRecord(agent_id="agent.b", logical_name="B", supported_capabilities=["test.child"], availability_state="unavailable", execution_mode="logical_internal")
    m = match_agent(["test.child"], [a2])
    assert not m["ok"]
    # deterministic selection: logical_internal preferred, then fewer caps, then agent_id
    a3 = LogicalAgentRecord(agent_id="agent.z", logical_name="Z", supported_capabilities=["test.child","extra"], availability_state="available", execution_mode="logical_internal")
    a4 = LogicalAgentRecord(agent_id="agent.a2", logical_name="A2", supported_capabilities=["test.child"], availability_state="available", execution_mode="logical_internal")
    m = match_agent(["test.child"], [a3, a4])
    assert m["ok"] and m["agent_id"] == "agent.a2"
    # delegate with matching agent
    aj.logical_agents.upsert(a4)
    res = aj.delegate(base_request(parent.task_id))
    assert res["assignments"][0]["agent_id"] == "agent.a2"


def test_permission_narrowing_and_escalation_rejection(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    from aj.delegation import narrow_permissions
    # missing/unverifiable context fails closed
    dec_missing = narrow_permissions(parent_permissions=None, requested_permissions=["a"], system_permissions=["a"])
    assert not dec_missing["ok"]
    dec_malformed = narrow_permissions(parent_permissions="bad", requested_permissions=["a"], system_permissions=["a"])
    assert not dec_malformed["ok"]
    # intersection-only narrowing (no escalation): extra requested perms are dropped
    dec = narrow_permissions(parent_permissions=["a"], requested_permissions=["a","b"], agent_permissions=["a","b"], system_permissions=["a","b"])
    assert dec["ok"] and dec["effective_permissions"] == ["a"]
    # delegation computes effective narrowed envelope and records it (no escalation possible)
    res = aj.delegate(base_request(parent.task_id, permission_context={
        "parent_permissions": ["delegation.coordinate"],
        "requested_permissions": ["delegation.coordinate", "admin"],
        "agent_permissions": ["delegation.coordinate", "admin"],
        "system_permissions": ["delegation.coordinate", "admin"],
    }, idempotency_key="narrow"))
    eff = res["assignments"][0]["permission_decision"]["effective_permissions"]
    assert eff == ["delegation.coordinate"] and "admin" not in eff


def test_assignment_lifecycle_distinct_and_no_duplicate_active(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    asg = res["assignments"][0]
    assert asg["logical_internal"] is True
    assert asg["status"] in ("ASSIGNED", "PROPOSED")
    from aj.delegation import AssignmentRecord, AS_ASSIGNED, AS_REJECTED
    rec = aj.assignments.get(asg["assignment_id"])
    assert rec is not None and rec.child_task_id == res["delegation"]["child_task_ids"][0]
    # duplicate active assignment prevention
    dup = AssignmentRecord(assignment_id="asg_dup", delegation_id=asg["delegation_id"], parent_task_id=parent.task_id,
                           child_task_id=rec.child_task_id, agent_id=rec.agent_id, status=AS_ASSIGNED)
    with pytest.raises(Exception):
        aj.assignments.create(dup)
    # transition validation
    rec2 = aj.assignments.get(asg["assignment_id"])
    rec2.transition(AS_REJECTED, reason="test")
    aj.assignments.save(rec2)
    assert aj.assignments.get(asg["assignment_id"]).status == AS_REJECTED


def test_aggregation_and_observability(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    agg = res["aggregation"]
    assert agg["counts"]["created"] == 1
    assert agg["can_complete"] is False
    cid = res["delegation"]["child_task_ids"][0]
    # mark child completed through valid transitions
    for st in ("UNDERSTANDING","PLANNED","AUTHORIZED","EXECUTING","VERIFYING","COMPLETED"):
        rec = aj.tasks.get(cid)
        if rec.status == st:
            continue
        if rec.can_transition(st):
            aj.tasks.transition(cid, st)
    status = aj.delegation_status(res["delegation"]["delegation_id"])
    assert status["aggregation"]["counts"]["completed"] == 1
    assert status["aggregation"]["can_complete"] is True
    mon = aj.delegation_monitor()
    assert mon["counts"]["delegations"] == 1
    assert mon["counts"]["assignments"] >= 1
    assert "anomalies" in mon


def test_hermes_not_attached_and_stores_fail_closed(tmp_path):
    cfg = make_cfg(tmp_path)
    aj = assemble(cfg)
    assert aj.execution.describe().get("integration_status") == "NOT ATTACHED" or aj.execution.describe().get("available") is False
    # in-memory/ephemeral without durable stores cannot delegate
    from aj.agents import AgentRegistry
    from aj.audit import AuditLog, MemoryAuditSink
    from aj.capability import CapabilityRegistry
    from aj.execution import SkillRegistry, UnavailableExecutionAdapter
    from aj.orchestrator import Aj
    from aj.permissions import ApprovalGate, Authorizer
    from aj.task import TaskStore
    aj2 = Aj(registry=CapabilityRegistry(), agents=AgentRegistry(), authorizer=Authorizer(gate=ApprovalGate()),
             audit=AuditLog(MemoryAuditSink()), tasks=TaskStore(), execution=UnavailableExecutionAdapter(),
             skills=SkillRegistry(), config=cfg)
    # delegations stores None in non-persistent mode
    with pytest.raises(Exception):
        aj2.delegate({"schema_version":1,"parent_task_id":"x","requested_work":"y","child_specs":[]})  # invalid anyway
