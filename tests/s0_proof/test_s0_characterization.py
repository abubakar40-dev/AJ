"""S0 characterization tests (Doc 58 / S0 closure, round 2 validated).

These tests document CURRENT behavior against required invariants and are expected
to expose gaps. Each characterization test is marked xfail(strict=True) with the
invariant/T-id it proves when the current implementation does not satisfy the
target invariant. Positive controls B1-B4 must PASS now.

Uses real Aj/TaskStore/Scheduler boundaries, real persisted files in /tmp,
no mocks of the guard under test.

--runxfail evidence (recorded in ENGINEERING_AUDIT/S0_CLOSURE/RUNXFAIL_EVIDENCE.txt):
- A1 fails at intended assertion: `assert found.status == "ABANDONED"` while reloaded
  task loads as DEAD_LETTER because ABANDONED append entry is invalid/skipped on reload
  (ABANDONED not in TRANSITIONS/validation for load). Not a setup/fixture error.
- A2a fails at intended assertion: delegated child dead_letter not blocked when parent
  cancelled (operation applicable/succeeds path observed per setup) -> assertion that
  dead_letter must be blocked fails.
- A2b fails at intended assertion: delegated child requeue not blocked when parent
  cancelled (requeue succeeded after dead_letter in characterized path).
- A2c fails at intended assertion: delegated child abandon not blocked when parent
  cancelled (`abandon_succeeded`).
- A3 fails at intended assertion: cancelled-parent delegated child was selected/dispatched
  by scheduler (eligibility/admission allowed selection).
- A4 fails at intended assertion: child left in unsafe/active state EXECUTING after parent
  cancel.
- A5 fails at intended assertion: parent force-completed to COMPLETED despite unresolved
  required child (`raised=None status=COMPLETED`).
- A6 fails at intended assertion: missing `required` not recorded/coerced as True
  (fail-closed required default absent).
- A7 fails at intended assertion: unsupported claim/capability not rejected/reported as
  unsupported (delegation accepted).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aj.capability import CapabilitySpec, OWNER_AJ
from aj.config import load
from aj.runtime import assemble
from aj.scheduler import Scheduler
from aj import task as taskmod


def make_cfg(data_dir: Path, **overrides):
    base = {
        "core": {"data_dir": str(data_dir), "audit_dir": str(data_dir / "audit")},
        "runtime": {"persist_tasks": True, "persist_memory": False},
        "scheduler": {
            "enabled": True,
            "global_max_active_executions": 2,
            "global_max_admitted_waiting": 10,
            "max_dispatch_per_run": 5,
            "max_workers": 1,
            "aging_seconds": 0,
        },
        "delegation": {
            "enabled": True,
            "max_children_per_delegation": 10,
            "max_delegations_per_parent": 20,
            "max_active_assignments_per_child": 1,
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return load(env={}, overrides=base)


def make_aj(data_dir: Path, **overrides):
    return assemble(make_cfg(data_dir, **overrides))


def register_cap(aj, cap_id="test.child", owner=OWNER_AJ, adapter="internal:echo", risk_level=0):
    spec = CapabilitySpec(
        capability_id=cap_id,
        name=cap_id,
        description="test capability",
        owner_agent=owner,
        execution_adapter=adapter,
        required_permissions=("read",),
        risk_level=risk_level,
        availability="available",
        verification_status="verified",
        replay_safe=True,
        retry_safe=True,
    )
    aj.registry.register(spec)
    return spec


def seed_internal_agent(aj, caps):
    from aj.delegation import LogicalAgentRecord

    rec = LogicalAgentRecord(
        agent_id="agent.aj.internal",
        logical_name="AJ_INTERNAL",
        agent_type="logical_internal",
        supported_capabilities=list(caps),
        availability_state="available",
        trust_classification="unverified_local_trust",
        execution_mode="logical_internal",
        enabled=True,
        provenance={"source": "s0_proof"},
    )
    aj.logical_agents.upsert(rec)
    return rec


def delegation_request(parent_task_id, cap_id="test.child", child_ref="c1", **kw):
    req = {
        "schema_version": 1,
        "parent_task_id": parent_task_id,
        "requested_work": "delegate work",
        "required_capabilities": [cap_id],
        "child_specs": [
            {
                "child_ref": child_ref,
                "goal": "child goal",
                "required_capabilities": [cap_id],
                "capability_id": cap_id,
            }
        ],
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


def create_planned_parent(aj, cap_id="test.child", goal="parent goal"):
    register_cap(aj, cap_id)
    parent = aj.tasks.create(goal, capability_id=cap_id)
    parent.request_payload = {"goal": goal}
    aj.tasks.save(parent, "payload")
    aj.tasks.transition(parent.task_id, taskmod.UNDERSTANDING, "s0")
    aj.tasks.transition(parent.task_id, taskmod.PLANNED, "s0")
    return aj.tasks.get(parent.task_id)


def create_delegated_child(aj):
    """Create a delegated parent+child pair via real delegation path."""
    parent = create_planned_parent(aj, "test.child")
    seed_internal_agent(aj, ["test.child"])
    res = aj.delegate(delegation_request(parent.task_id, "test.child"))
    did = res["delegation"]["delegation_id"]
    cid = res["delegation"]["child_task_ids"][0]
    return parent.task_id, cid, did, res


@pytest.fixture
def ext4_tmpdir():
    # Task requires real persisted files in a tmp dir ON EXT4 (use /tmp).
    with tempfile.TemporaryDirectory(prefix="aj_s0_proof_", dir="/tmp") as d:
        yield Path(d)


@pytest.mark.xfail(strict=True, reason="INV-ABANDONED/Doc58 D3: ABANDONED must be formal terminal+loadable")
def test_a1_abandon_survives_reload_and_list(ext4_tmpdir):
    """A1 (INV/Doc58 D3): abandon a task, rebuild TaskStore from disk, assert it is
    still loaded and listed as ABANDONED with preserved history.
    Intended failure (current): reload skips ABANDONED record (status not in
    TRANSITIONS/validation), so task is not loaded as ABANDONED (may load as prior
    DEAD_LETTER snapshot or be missing)."""
    aj = make_aj(ext4_tmpdir)
    rec = aj.tasks.create("task to abandon")
    aj.tasks.transition(rec.task_id, taskmod.UNDERSTANDING)
    aj.tasks.transition(rec.task_id, taskmod.PLANNED)
    aj.tasks.transition(rec.task_id, taskmod.AUTHORIZED)
    aj.tasks.transition(rec.task_id, taskmod.EXECUTING)
    aj.tasks.transition(rec.task_id, taskmod.FAILED, "fail")
    aj.dead_letter(rec.task_id, "dl")
    aj.abandon(rec.task_id, "abandon now")
    assert aj.tasks.get(rec.task_id).status == "ABANDONED"

    store2 = taskmod.TaskStore(ext4_tmpdir)
    found = store2.find(rec.task_id)
    assert found is not None and found.status == "ABANDONED", (
        f"expected ABANDONED task loadable after reload; found={getattr(found,'status',None)} "
        f"load_errors={store2.load_errors}"
    )
    assert rec.task_id in [t.task_id for t in store2.all()]


@pytest.mark.xfail(strict=True, reason="Doc58 D4: delegated child dead_letter blocked unless operator reconcile with evidence when parent cancelled")
def test_a2a_dead_letter_on_delegated_child_blocked_when_parent_cancelled(ext4_tmpdir):
    """A2a (Doc58 D4): dead_letter on a delegated child whose parent is CANCELLED must
    be blocked or allowed only via operator reconcile with delegation evidence+parent reconcile.
    Intended failure (current): unsafe direct dead_letter succeeds or is not delegation-safe."""
    aj = make_aj(ext4_tmpdir)
    parent_id, child_id, _did, _res = create_delegated_child(aj)
    aj.tasks.transition(parent_id, taskmod.CANCELLED, "cancel parent")
    # drive child to a state where dead_letter is applicable
    c = aj.tasks.get(child_id)
    if c.status == taskmod.AUTHORIZED:
        aj.tasks.transition(child_id, taskmod.EXECUTING, "exec")
        aj.tasks.transition(child_id, taskmod.FAILED, "fail")
    elif c.can_transition(taskmod.FAILED):
        aj.tasks.transition(child_id, taskmod.FAILED, "fail")
    c = aj.tasks.get(child_id)
    if c.status != taskmod.FAILED:
        pytest.xfail(f"setup could not reach FAILED for dead_letter applicability (status={c.status})")
    # direct Aj.dead_letter must be blocked/delegation-safe
    blocked = False
    try:
        aj.dead_letter(child_id, "try dl")
    except Exception:
        blocked = True
    assert blocked, f"delegated child dead_letter not blocked with cancelled parent (status={aj.tasks.get(child_id).status})"


@pytest.mark.xfail(strict=True, reason="Doc58 D4: Aj.requeue blocked for delegated tasks")
def test_a2b_requeue_on_delegated_child_blocked_when_parent_cancelled(ext4_tmpdir):
    """A2b (Doc58 D4): Aj.requeue on a delegated task must be BLOCKED (and cannot bypass
    cancelled-parent/delegation safety). Intended failure (current): requeue succeeds."""
    aj = make_aj(ext4_tmpdir)
    parent_id, child_id, _did, _res = create_delegated_child(aj)
    aj.tasks.transition(parent_id, taskmod.CANCELLED, "cancel parent")
    c = aj.tasks.get(child_id)
    # make child DEAD_LETTER if possible so requeue path is directly applicable
    if c.status == taskmod.AUTHORIZED:
        aj.tasks.transition(child_id, taskmod.EXECUTING, "exec")
        aj.tasks.transition(child_id, taskmod.FAILED, "fail")
        aj.tasks.transition(child_id, taskmod.DEAD_LETTER, "dl")
    elif c.status == taskmod.FAILED:
        aj.tasks.transition(child_id, taskmod.DEAD_LETTER, "dl")
    elif c.can_transition(taskmod.FAILED):
        aj.tasks.transition(child_id, taskmod.FAILED, "fail")
        aj.tasks.transition(child_id, taskmod.DEAD_LETTER, "dl")
    c = aj.tasks.get(child_id)
    if c.status != taskmod.DEAD_LETTER:
        pytest.xfail(f"setup could not reach DEAD_LETTER for requeue applicability (status={c.status})")
    blocked = False
    try:
        aj.requeue(child_id)
    except Exception:
        blocked = True
    assert blocked, f"delegated child requeue not blocked (status={aj.tasks.get(child_id).status})"


@pytest.mark.xfail(strict=True, reason="Doc58 D4: delegated child abandon blocked unless operator reconcile with evidence when parent cancelled")
def test_a2c_abandon_on_delegated_child_blocked_when_parent_cancelled(ext4_tmpdir):
    """A2c (Doc58 D4): abandon on a delegated child whose parent is CANCELLED must be
    blocked or allowed only via operator reconcile with delegation evidence+parent reconcile.
    Intended failure (current): direct abandon succeeds."""
    aj = make_aj(ext4_tmpdir)
    parent_id, child_id, _did, _res = create_delegated_child(aj)
    aj.tasks.transition(parent_id, taskmod.CANCELLED, "cancel parent")
    blocked = False
    try:
        aj.abandon(child_id, "try abandon")
    except Exception:
        blocked = True
    assert blocked, f"delegated child abandon not blocked with cancelled parent (status={aj.tasks.get(child_id).status})"


@pytest.mark.xfail(strict=True, reason="Doc58 D4/INV-04: scheduler must not dispatch delegated child with cancelled/revoked parent")
def test_a3_scheduler_does_not_dispatch_child_of_cancelled_parent(ext4_tmpdir):
    """A3 (Doc58 D4): Scheduler eligibility and pre-dispatch (under lease) must verify
    parent not cancelled/revoked/aborted/dead_letter and delegation active/linked.
    Intended failure (current): child selected/dispatched despite cancelled parent."""
    aj = make_aj(ext4_tmpdir)
    parent_id, child_id, _did, _res = create_delegated_child(aj)
    aj.tasks.transition(parent_id, taskmod.CANCELLED, "cancel parent")
    sched = Scheduler(aj)
    res = sched.run_once(limit=10, workers=1)
    dispatched = res.get("selected") or []
    child_after = aj.tasks.get(child_id)
    assert child_id not in dispatched, f"child dispatched despite cancelled parent: {res}"
    assert child_after.status not in (taskmod.EXECUTING, taskmod.COMPLETED, taskmod.VERIFYING), child_after.status


@pytest.mark.xfail(strict=True, reason="Doc58 D4/INV-04: cancelling parent must safely handle active delegated children")
def test_a4_cancel_parent_cancels_or_safely_handles_running_children(ext4_tmpdir):
    """A4 (Doc58 D4): cancelling a parent must cancel non-terminal children through each
    child's own cancel flow (EXECUTING => CANCEL_REQUESTED, cooperative), with delegation
    evidence/assignment updates. Intended failure (current): child left EXECUTING/active."""
    aj = make_aj(ext4_tmpdir)
    parent_id, child_id, _did, _res = create_delegated_child(aj)
    child = aj.tasks.get(child_id)
    if child.status == taskmod.AUTHORIZED:
        aj.tasks.transition(child_id, taskmod.EXECUTING, "simulate running")
    # cancel parent via AJ flow
    try:
        aj.cancel_task(parent_id)
    except Exception:
        aj.tasks.transition(parent_id, taskmod.CANCELLED, "force cancel parent")
    child_after = aj.tasks.get(child_id)
    assert child_after.status in (
        taskmod.CANCELLED, taskmod.CANCEL_REQUESTED, taskmod.ABORTED,
        taskmod.RECOVERY_REQUIRED, taskmod.DEAD_LETTER, taskmod.FAILED,
    ), f"child left in unsafe/active state {child_after.status} after parent cancel"


@pytest.mark.xfail(strict=True, reason="Doc58 D2/INV-03: parent COMPLETED guard applies regardless of force=True")
def test_a5_force_complete_parent_blocked_with_unresolved_required_child(ext4_tmpdir):
    """A5 (Doc58 D2, INV-03): parent cannot complete while required child unresolved;
    COMPLETED guard applies REGARDLESS of force=True. Intended failure (current): forced
    completion succeeds."""
    aj = make_aj(ext4_tmpdir)
    parent_id, child_id, _did, _res = create_delegated_child(aj)
    assert aj.tasks.get(child_id).status != taskmod.COMPLETED
    raised = None
    try:
        aj.tasks.transition(parent_id, taskmod.COMPLETED, "force complete", force=True)
    except Exception as e:
        raised = e
    parent = aj.tasks.get(parent_id)
    assert raised is not None or parent.status != taskmod.COMPLETED, (
        f"parent force-completed despite unresolved required child; raised={raised} status={parent.status}"
    )


@pytest.mark.xfail(strict=True, reason="Doc58 D1/T-04: missing/malformed required classification must fail closed (default required)")
def test_a6_t04_missing_or_malformed_required_classification(ext4_tmpdir):
    """A6 (T-04, Doc58 D1): child_spec.required bool; missing => required=true with
    classification_source default_required; present but not real bool => reject delegation
    creation with validation error. Intended failure (current): no explicit required field/
    validation/enforcement."""
    aj = make_aj(ext4_tmpdir)
    parent = create_planned_parent(aj, "test.child")
    seed_internal_agent(aj, ["test.child"])
    req_missing = delegation_request(parent.task_id, "test.child")
    res1 = aj.delegate(req_missing)
    d = (res1.get("delegation") or res1)
    specs = (d.get("request") or {}).get("child_specs") or []
    missing_ok = bool(specs) and specs[0].get("required") is True
    # malformed: present but not real bool => must be rejected
    req_malformed = delegation_request(
        parent.task_id, "test.child",
        child_specs=[{
            "child_ref": "c1", "goal": "child 1", "required_capabilities": ["test.child"],
            "capability_id": "test.child", "required": "maybe",
        }],
        idempotency_key="idem-malformed",
    )
    malformed_rejected = False
    try:
        aj.delegate(req_malformed)
    except Exception:
        malformed_rejected = True
    assert missing_ok and malformed_rejected, (
        f"expected missing=>required True and malformed=>rejected; "
        f"missing_ok={missing_ok} malformed_rejected={malformed_rejected} specs={specs}"
    )


@pytest.mark.xfail(strict=True, reason="Doc54 T-11 / Doc58 D5: unsupported capability/claim (e.g. remote agent transport) must be rejected or reported UNSUPPORTED")
def test_a7_t11_unsupported_capability_claim_rejected(ext4_tmpdir):
    """A7 (T-11, INV-10, Doc58 D5): attempt an unsupported capability/claim that the
    system cannot actually do — REMOTE AGENT TRANSPORT / execution on a remote agent —
    in a delegation request. Expected: rejected/blocked or explicitly reported as
    UNSUPPORTED (no silent acceptance / no false capability). Intended failure (current):
    request accepted without unsupported reporting."""
    aj = make_aj(ext4_tmpdir)
    parent = create_planned_parent(aj, "test.child")
    seed_internal_agent(aj, ["test.child"])
    req = delegation_request(parent.task_id, "test.child")
    # explicit unsupported claim: real remote agent transport/execution (not available)
    req["execution_mode"] = "remote_transport"
    req["child_specs"][0]["agent_transport"] = "remote_agent_transport"
    req["child_specs"][0]["requires_remote_agent"] = True
    unsupported_reported = False
    rejected = False
    report = None
    try:
        res = aj.delegate(req)
        report = res
        text = str(res).lower()
        unsupported_reported = ("unsupported" in text) or ("not supported" in text)
    except Exception as e:
        rejected = True
        report = str(e)
        text = str(e).lower()
        unsupported_reported = ("unsupported" in text) or ("not supported" in text)
    assert rejected or unsupported_reported, (
        f"remote agent transport (unsupported claim) silently accepted without UNSUPPORTED reporting: {report}"
    )


# --- Positive controls B1-B4 (must PASS now) ---

def test_b1_non_delegated_task_can_be_requeued_after_dead_letter(ext4_tmpdir):
    """B1 positive control: non-delegated task can be dead-lettered then requeued."""
    aj = make_aj(ext4_tmpdir)
    rec = aj.tasks.create("plain task")
    aj.tasks.transition(rec.task_id, taskmod.UNDERSTANDING)
    aj.tasks.transition(rec.task_id, taskmod.PLANNED)
    aj.tasks.transition(rec.task_id, taskmod.AUTHORIZED)
    aj.tasks.transition(rec.task_id, taskmod.EXECUTING)
    aj.tasks.transition(rec.task_id, taskmod.FAILED, "fail")
    aj.dead_letter(rec.task_id, "dl reason")
    assert aj.tasks.get(rec.task_id).status == taskmod.DEAD_LETTER
    out = aj.requeue(rec.task_id)
    assert out.status == taskmod.PLANNED
    assert aj.tasks.get(rec.task_id).status == taskmod.PLANNED


def test_b2_non_delegated_abandon_works_and_stays_abandoned_in_memory(ext4_tmpdir):
    """B2 positive control: non-delegated abandon works and remains ABANDONED in-memory.
    (Disk reload of ABANDONED is covered separately by A1 characterization.)"""
    aj = make_aj(ext4_tmpdir)
    rec = aj.tasks.create("plain task")
    aj.tasks.transition(rec.task_id, taskmod.UNDERSTANDING)
    aj.tasks.transition(rec.task_id, taskmod.PLANNED)
    aj.tasks.transition(rec.task_id, taskmod.AUTHORIZED)
    aj.tasks.transition(rec.task_id, taskmod.EXECUTING)
    aj.tasks.transition(rec.task_id, taskmod.FAILED, "fail")
    aj.dead_letter(rec.task_id, "dl")
    aj.abandon(rec.task_id, "abandon")
    assert aj.tasks.get(rec.task_id).status == "ABANDONED"
    assert rec.task_id in [t.task_id for t in aj.tasks.all()]


def test_b3_parent_with_all_required_children_completed_completes(ext4_tmpdir):
    """B3 positive control: parent with all required delegated children COMPLETED can complete
    through existing aggregation/guard path (no force)."""
    aj = make_aj(ext4_tmpdir)
    parent_id, child_id, did, _res = create_delegated_child(aj)
    # complete child through valid transitions
    c = aj.tasks.get(child_id)
    if c.status == taskmod.AUTHORIZED:
        aj.tasks.transition(child_id, taskmod.EXECUTING, "exec")
        aj.tasks.transition(child_id, taskmod.VERIFYING, "verify")
        aj.tasks.transition(child_id, taskmod.COMPLETED, "done")
    elif c.can_transition(taskmod.COMPLETED):
        aj.tasks.transition(child_id, taskmod.COMPLETED, "done")
    else:
        # drive via allowed edges best-effort
        for st in (taskmod.EXECUTING, taskmod.VERIFYING, taskmod.COMPLETED):
            cur = aj.tasks.get(child_id)
            if cur.can_transition(st):
                aj.tasks.transition(child_id, st, "progress")
    assert aj.tasks.get(child_id).status == taskmod.COMPLETED
    # ensure delegation reconciliation/aggregation observed, then complete parent
    aj.reconcile_delegation_parent(parent_id)
    # move parent to AUTHORIZED->EXECUTING->VERIFYING->COMPLETED if needed
    p = aj.tasks.get(parent_id)
    path = {
        taskmod.RECEIVED: [taskmod.UNDERSTANDING, taskmod.PLANNED, taskmod.AUTHORIZED, taskmod.EXECUTING, taskmod.VERIFYING, taskmod.COMPLETED],
        taskmod.UNDERSTANDING: [taskmod.PLANNED, taskmod.AUTHORIZED, taskmod.EXECUTING, taskmod.VERIFYING, taskmod.COMPLETED],
        taskmod.PLANNED: [taskmod.AUTHORIZED, taskmod.EXECUTING, taskmod.VERIFYING, taskmod.COMPLETED],
        taskmod.AUTHORIZED: [taskmod.EXECUTING, taskmod.VERIFYING, taskmod.COMPLETED],
        taskmod.EXECUTING: [taskmod.VERIFYING, taskmod.COMPLETED],
        taskmod.VERIFYING: [taskmod.COMPLETED],
    }
    for st in path.get(p.status, []):
        cur = aj.tasks.get(parent_id)
        if cur.status == taskmod.COMPLETED:
            break
        if cur.can_transition(st):
            aj.tasks.transition(parent_id, st, "complete parent")
    assert aj.tasks.get(parent_id).status == taskmod.COMPLETED


def test_b4_normal_non_delegated_task_runs_end_to_end(ext4_tmpdir):
    """B4 positive control: normal non-delegated task runs end to end via Aj.handle."""
    aj = make_aj(ext4_tmpdir)
    register_cap(aj, "test.echo", adapter="internal:echo")
    out = aj.handle("hello", capability_id="test.echo", payload={"text": "hi"}, user_requested=True)
    assert getattr(out, "ok", False) or getattr(out, "status", "") in (taskmod.COMPLETED, "COMPLETED")
    # verify persisted task terminal/completed when ok
    task = aj.tasks.get(out.task_id)
    assert task.status in (taskmod.COMPLETED, taskmod.WAITING_FOR_APPROVAL, taskmod.BLOCKED) or getattr(out, "ok", False)


@pytest.mark.xfail(strict=True, reason="INV no resurrection / Doc58 D3: abandoned (DEAD_LETTER->ABANDONED) must not be resurrected by requeue after reload")
def test_a1b_abandoned_dead_letter_cannot_be_requeued_after_reload(ext4_tmpdir):
    """A1b (INV no resurrection / Doc58 D3): abandon a DEAD_LETTER task, rebuild TaskStore
    from disk, then show aj.requeue on it succeeds (resurrection). Intended gap: ABANDONED
    record not loadable as ABANDONED (reload skips/loses terminal abandoned state), allowing
    prior DEAD_LETTER state/evidence to be requeued (resurrection)."""
    aj = make_aj(ext4_tmpdir)
    rec = aj.tasks.create("task to abandon")
    aj.tasks.transition(rec.task_id, taskmod.UNDERSTANDING)
    aj.tasks.transition(rec.task_id, taskmod.PLANNED)
    aj.tasks.transition(rec.task_id, taskmod.AUTHORIZED)
    aj.tasks.transition(rec.task_id, taskmod.EXECUTING)
    aj.tasks.transition(rec.task_id, taskmod.FAILED, "fail")
    aj.dead_letter(rec.task_id, "dl")
    aj.abandon(rec.task_id, "abandon now")
    assert aj.tasks.get(rec.task_id).status == "ABANDONED"

    aj2 = assemble(aj.config)
    loaded = aj2.tasks.find(rec.task_id)
    # If abandoned state were correctly preserved, requeue must not be possible.
    # Current gap: record reloads as DEAD_LETTER (or missing abandoned), so requeue succeeds.
    if loaded is None:
        pytest.xfail(f"abandoned task not loadable after reload (load_errors indicate state loss): expected resurrection-via-requeue gap check not directly applicable")
    resurrected = False
    try:
        out = aj2.requeue(rec.task_id)
        resurrected = (out.status == taskmod.PLANNED)
    except Exception:
        resurrected = False
    assert not resurrected, f"abandoned task resurrected after reload via requeue (status={getattr(loaded,'status',None)} -> {aj2.tasks.find(rec.task_id).status if aj2.tasks.find(rec.task_id) else None})"


@pytest.mark.xfail(strict=True, reason="Doc58 D3: abandon on COMPLETED must be refused and task must stay COMPLETED")
def test_a8_abandon_completed_task_refused(ext4_tmpdir):
    """A8 (Doc58 D3): abandon on a COMPLETED task must be refused and the task must stay
    COMPLETED. Intended failure (current): abandon accepts broadly (force path) and can
    abandon terminal/completed tasks."""
    aj = make_aj(ext4_tmpdir)
    rec = aj.tasks.create("done task")
    aj.tasks.transition(rec.task_id, taskmod.UNDERSTANDING)
    aj.tasks.transition(rec.task_id, taskmod.PLANNED)
    aj.tasks.transition(rec.task_id, taskmod.AUTHORIZED)
    aj.tasks.transition(rec.task_id, taskmod.EXECUTING)
    aj.tasks.transition(rec.task_id, taskmod.VERIFYING)
    aj.tasks.transition(rec.task_id, taskmod.COMPLETED, "done")
    refused = False
    try:
        aj.abandon(rec.task_id, "try abandon completed")
    except Exception:
        refused = True
    after = aj.tasks.get(rec.task_id)
    assert refused and after.status == taskmod.COMPLETED, (
        f"completed task abandon not refused/safe; refused={refused} status={after.status}"
    )


def test_b5_required_unresolved_child_blocks_parent_completion_with_aggregation_conflict(ext4_tmpdir):
    """B5 positive control (post D-001): parent with a REQUIRED child still unresolved cannot
    complete; Conflict must include aggregation detail and must not be due to NameError/unverifiable."""
    from aj.errors import Conflict
    aj = make_aj(ext4_tmpdir)
    parent_id, child_id, did, _res = create_delegated_child(aj)
    assert aj.tasks.get(child_id).status != taskmod.COMPLETED
    # drive parent to a state where COMPLETED edge is legal if not guarded
    p = aj.tasks.get(parent_id)
    for st in (taskmod.AUTHORIZED, taskmod.EXECUTING, taskmod.VERIFYING):
        cur = aj.tasks.get(parent_id)
        if cur.status == st:
            continue
        if cur.can_transition(st):
            aj.tasks.transition(parent_id, st)
    with pytest.raises(Conflict) as ei:
        aj.tasks.transition(parent_id, taskmod.COMPLETED, "must be blocked")
    msg = str(ei.value)
    detail = getattr(ei.value, "detail", None) or {}
    assert "aggregation" in detail, f"Conflict missing aggregation detail: {detail} msg={msg}"
    assert "NameError" not in msg and "unverifiable" not in msg, msg
