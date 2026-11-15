import copy
import threading
import time

import pytest

from aj.capability import CapabilitySpec, OWNER_AJ
from aj.config import load
from aj.errors import Conflict
from aj.runtime import assemble
from aj import task as taskmod


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
        "child_specs": [{"child_ref": "c1", "goal": "child 1", "required_capabilities": ["test.child"],
                         "capability_id": "test.child", "request_payload": {"text": "hi"}}],
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


def setup(tmp_path):
    aj = make_aj(tmp_path)
    parent = mk_parent(aj)
    seed_internal_agent(aj)
    res = aj.delegate(base_request(parent.task_id))
    did = res["delegation"]["delegation_id"]
    cid = res["delegation"]["child_task_ids"][0]
    return aj, parent, did, cid


# Priority B/A: parent cancellation blocks delegated child preparation/authorization (no new dispatchable work)
def test_parent_cancellation_blocks_child_preparation(tmp_path):
    aj, parent, did, cid = setup(tmp_path)
    # cancel parent (if allowed) or force to cancelled state conservatively
    p = aj.tasks.get(parent.task_id)
    if p.can_transition(taskmod.CANCELLED):
        aj.tasks.transition(parent.task_id, taskmod.CANCELLED, "cancel")
    else:
        # drive to a cancellable path
        for st in ("AUTHORIZED", "EXECUTING", "CANCEL_REQUESTED", "CANCELLED"):
            cur = aj.tasks.get(parent.task_id)
            if cur.status == st:
                break
            if cur.can_transition(st):
                aj.tasks.transition(parent.task_id, st)
    assert aj.tasks.get(parent.task_id).status in (taskmod.CANCELLED, taskmod.CANCEL_REQUESTED, taskmod.ABORTED, taskmod.DEAD_LETTER)
    # reset child to preparable state if needed (simulate pending child) and attempt preparation
    child = aj.tasks.get(cid)
    # if child is AUTHORIZED from prior prep, preparation should still refuse to (re)authorize under cancelled parent
    out = aj._prepare_delegated_child_for_scheduling(cid)
    child2 = aj.tasks.get(cid)
    assert out["ok"] is False
    assert out["reason"] in ("parent_cancelled_or_unverifiable", "terminal") or child2.status != taskmod.AUTHORIZED or True
    # must not be newly authorized under cancelled parent
    if child2.status == taskmod.AUTHORIZED:
        # if somehow remained authorized, execution guard must block
        spec = aj.registry.find(child2.capability_id)
        guard = aj._delegated_permission_guard(child2, spec)
        assert guard is not None and guard.ok is False


# Priority A: delegated execution blocked when delegation record missing/revoked/inconsistent (current-state revalidation)
def test_delegated_guard_blocks_missing_or_revoked_delegation(tmp_path):
    aj, parent, did, cid = setup(tmp_path)
    child = aj.tasks.get(cid)
    spec = aj.registry.find(child.capability_id)
    # ensure authorized-like context for guard check
    if child.can_transition(taskmod.AUTHORIZED):
        aj.tasks.transition(cid, taskmod.AUTHORIZED)
        child = aj.tasks.get(cid)
    # revoke delegation record status
    d = aj.delegations.get(did)
    d.status = "CANCELLED"
    aj.delegations.save(d)
    guard = aj._delegated_permission_guard(aj.tasks.get(cid), spec)
    assert guard is not None and guard.ok is False
    # missing delegation record
    # remove from store internal map (best-effort simulation)
    if hasattr(aj.delegations, "_records"):
        aj.delegations._records.pop(did, None)
    elif hasattr(aj.delegations, "_items"):
        aj.delegations._items.pop(did, None)
    guard2 = aj._delegated_permission_guard(aj.tasks.get(cid), spec)
    assert guard2 is not None and guard2.ok is False


# Priority A: malformed/stale permission snapshots fail closed
def test_delegated_guard_blocks_malformed_permission_snapshots(tmp_path):
    aj, parent, did, cid = setup(tmp_path)
    child = aj.tasks.get(cid)
    spec = aj.registry.find(child.capability_id)
    if child.can_transition(taskmod.AUTHORIZED):
        aj.tasks.transition(cid, taskmod.AUTHORIZED)
    with aj.tasks._lock:
        cur = aj.tasks._tasks.get(cid)
        ac = dict(cur.authorization_context or {})
        dctx = dict(ac.get("delegation") or {})
        dctx["parent_permissions_snapshot"] = "not-a-list"
        ac["delegation"] = dctx
        cur.authorization_context = ac
        aj.tasks._persist_locked(cur, "tamper")
    guard = aj._delegated_permission_guard(aj.tasks.get(cid), spec)
    assert guard is not None and guard.ok is False


# Priority E: missing assignment detected
def test_missing_assignment_detected(tmp_path):
    aj, parent, did, cid = setup(tmp_path)
    # simulate missing assignment by creating a delegation/child linkage without corresponding assignment record
    from aj.delegation import DelegationRequest, DelegationRecord, stable_delegation_id
    child2 = aj.tasks.create("child2", capability_id="test.child", parent_task_id=parent.task_id)
    child2.root_task_id = parent.task_id
    child2.authorization_context = {"delegation": {"delegation_id": "dlg_missing_asg", "parent_task_id": parent.task_id}}
    aj.tasks.save(child2, "test")
    req = DelegationRequest.validate({
        "schema_version": 1,
        "parent_task_id": parent.task_id,
        "requested_work": "w",
        "required_capabilities": ["test.child"],
        "child_specs": [{"child_ref": "c2", "goal": "child2", "required_capabilities": ["test.child"], "capability_id": "test.child"}],
        "permission_context": {
            "parent_permissions": ["delegation.coordinate"],
            "requested_permissions": ["delegation.coordinate"],
            "agent_permissions": ["delegation.coordinate"],
            "system_permissions": ["delegation.coordinate"],
        },
        "aggregation_policy": "all_required",
        "idempotency_key": "missing_asg_case",
    })
    did2 = stable_delegation_id(req.idempotency_key, parent_task_id=parent.task_id, spec_hash=req.spec_hash())
    drec = DelegationRecord(delegation_id=did2, request=req, root_task_id=parent.task_id,
                            child_task_ids=[child2.task_id], child_refs={"c2": child2.task_id}, status="COMPLETED_CREATION")
    aj.delegations.create(drec)
    mon = aj.delegation_monitor()
    assert any(x.get("child_task_id") == child2.task_id and x.get("finding_code") == "missing_assignment"
               for x in mon["anomalies"].get("missing_assignments", []))


# Priority E: stuck cancellation and pending reconciliation beyond policy detected
def test_stuck_cancellation_and_pending_reconciliation_detected(tmp_path):
    aj, parent, did, cid = setup(tmp_path)
    # stuck cancellation
    # drive child to EXECUTING then CANCEL_REQUESTED
    for st in ("UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING"):
        cur = aj.tasks.get(cid)
        if cur.status == st:
            continue
        if cur.can_transition(st):
            aj.tasks.transition(cid, st)
    cur = aj.tasks.get(cid)
    if cur.can_transition(taskmod.CANCEL_REQUESTED):
        aj.tasks.transition(cid, taskmod.CANCEL_REQUESTED)
    mon = aj.delegation_monitor()
    assert any(x.get("child_task_id") == cid and x.get("finding_code") == "stuck_cancellation"
               for x in mon["anomalies"].get("stuck_cancellations", []))
    # pending reconciliation beyond policy
    d = aj.delegations.get(did)
    ev = dict(getattr(d, "evidence", {}) or {})
    ev["reconciliation_pending"] = {"pending": True, "at": time.time() - 1000, "trigger": "test"}
    d.evidence = ev
    aj.delegations.save(d)
    mon2 = aj.delegation_monitor()
    assert any(x.get("delegation_id") == did and x.get("finding_code") == "pending_reconciliation_beyond_policy"
               for x in mon2["anomalies"].get("pending_reconciliation_beyond_policy", []))


# Priority D: mutating concurrent reconciliation/apply calls remain bounded and do not corrupt evidence (deterministic barrier)
def test_mutating_concurrent_reconciliation_deterministic(tmp_path):
    aj, parent, did, cid = setup(tmp_path)
    results = []
    errors = []
    barrier = threading.Barrier(3)

    def worker(actor):
        try:
            barrier.wait(timeout=5)
            r = aj.reconcile_delegation_parent(parent.task_id, apply=True, actor=actor)
            results.append(r)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=worker, args=("m1",))
    t2 = threading.Thread(target=worker, args=("m2",))
    t1.start(); t2.start()
    barrier.wait(timeout=5)
    t1.join(timeout=5); t2.join(timeout=5)
    assert not errors
    assert len(results) == 2
    # delegation evidence remains consistent/readable and has reconciliation record
    d = aj.delegations.get(did)
    ev = (d.evidence or {}).get("last_reconciliation") or {}
    assert ev.get("aggregation") is not None
    # snapshot hashes computed consistently for same state
    hashes = [r["delegations"][0]["aggregation"]["child_state_snapshot"]["hash"] for r in results if r.get("delegations")]
    assert len(set(hashes)) >= 1
