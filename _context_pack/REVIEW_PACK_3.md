# _context_pack/REVIEW_PACK_3.md

Round 3 S0 closure evidence pack (verbatim required artifacts).

===== STEP 3 change table (ENGINEERING_AUDIT/S0_CLOSURE/STEP3_CHANGE_TABLE.md) =====
# STEP 3 — D-001 impact: before/after fix evidence

## Commands / artifacts
- Before-fix B3 (NameError): `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_BEFORE_FIX.txt`
- After-fix B3 (PASS): `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_AFTER_FIX.txt`
- Before-fix existing suite (`pytest -q`, clean committed snapshot, no `tests/s0_proof`): `/tmp/s0_round3_suite_before_d001.txt` → **576 passed, 1 failed, 13 warnings** (`tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` failed with `sqlite3.OperationalError: disk I/O error` on NTFS workspace tmp path; known intermittent/environment-sensitive OPEN issue)
- After-fix existing suite (`pytest -q --ignore=tests/s0_proof`): `/tmp/s0_round3_suite_after_d001_existing.txt` → **577 passed, 13 warnings** (sqlite test passed in this run)
- After-fix all suite including `tests/s0_proof`: `/tmp/s0_round3_suite_after_d001_all.txt` → **581 passed, 9 xfailed, 13 warnings**
- Conflict message capture (with fix): `ENGINEERING_AUDIT/S0_CLOSURE/D001_CONFLICT_MESSAGES_AFTER_FIX.json`

## Test result changes (every observed change)
| Test / scope | Before D-001 fix | After D-001 fix | Attribution |
|---|---|---|---|
| `tests/s0_proof/test_s0_characterization.py::test_b3_parent_with_all_required_children_completed_completes` | FAIL (`NameError: aggregate_parent_progress` -> `Conflict ... unverifiable (NameError)`) | PASS | **D-001 fix** (intended) |
| `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` | FAIL (`sqlite3.OperationalError: disk I/O error`, NTFS workspace tmp) | PASS (in compared after-fix run) | **Intermittent/environment-sensitive variance (OPEN, not attributed to D-001)** |
| All other existing tests (`--ignore=tests/s0_proof`, excluding above) | PASS (576) | PASS (576) | No change observed |

**Conclusion:** no deterministic regression in existing tests attributed to D-001. The only deterministic behavior change observed is correction of delegated-parent completion guard evaluation (from NameError/unverifiable to real aggregation).

## Conflict messages for delegation completion-blocking cases (with fix applied)
Source: `D001_CONFLICT_MESSAGES_AFTER_FIX.json` (reproduced via real Aj/delegation flows) and verified passing tests.

| Scenario / representative test(s) | `raises Conflict` site(s) | Message with fix (real reason) | Previously passed only because of NameError? | Notes |
|---|---|---|---|---|
| Required child unresolved, parent completion attempted | `tests/test_phase5a6r2_parent_lifecycle.py:130` (`test_parent_completion_blocked_when_required_child_unresolved`), `:152` (`test_parent_completion_blocked_direct_guard`) | `parent task ... cannot complete: required child work unresolved/uncertain/manual-review` with `detail.aggregation` (e.g. waiting/unresolved, `can_complete=false`) | **YES (wrong reason).** Guard called undefined `aggregate_parent_progress` -> caught -> `Conflict(... delegation state unverifiable (NameError))`; tests asserted only `Conflict`, so they passed but for wrong reason. | With fix, correct aggregation-based block. |
| Required child failed, parent completion attempted | `tests/test_phase5a6r2_parent_lifecycle.py::test_required_child_failure_prevents_false_completion` (asserts aggregation/cannot-complete; may also block transition if attempted) / reproduced case | same Conflict class/message family with aggregation showing failed required child, `can_complete=false` | **YES if it reached guarded COMPLETED transition and asserted only Conflict.** Guard path would have thrown NameError-wrapped unverifiable Conflict before fix. | Reproduced case shows real aggregation reason after fix. |
| Unknown/recovery-required/manual-review child blocks completion | `tests/test_phase5a6r2_parent_lifecycle.py::test_unknown_or_recovery_required_child_blocks_completion`, `tests/test_phase5a6r3_scenario_certification.py::test_s7_s11_required_failure_and_manual_review_prevent_completion` | aggregation-based cannot-complete/manual-review when evaluated | **Potentially YES for wrong reason** in any path that attempted guarded non-force parent COMPLETED and only checked Conflict/blocked outcome; before fix such guard evaluation was NameError -> unverifiable Conflict. | Tests primarily assert aggregation flags; completion-guard wrong-reason exposure depends on whether guarded transition was invoked. |
| Incorrect completed parent detection scenario (guard blocks proper completion attempt) | `tests/test_phase5a6r3_scenario_certification.py:258` (`test_s16_s31_incorrect_completed_parent_detected`) | aggregation-based cannot-complete Conflict when transition attempted | **YES (wrong reason)** for the `pytest.raises(Conflict)` on `aj.tasks.transition(..., COMPLETED)` at ~258 (guarded path). | Test later simulates contradictory persisted state for detection; the guarded transition assertion would have passed for wrong reason before fix. |
| Same idempotency key, different spec (delegate) | `tests/test_phase5a6r_delegation_closure.py:126` (`test_same_idempotency_key_different_spec_rejected`) | `same delegation idempotency key with different specification` | **NO.** Different code path (`delegate` idempotency validation), unaffected by D-001. | Included for completeness of `raises(Conflict)` sites in target files. |

## Wrong-reason summary (as required)
- **Previously passed only because of NameError (`unverifiable (NameError)`), not real aggregation reason:** completion-guarding assertions that expected `Conflict` when transitioning a delegated parent to `COMPLETED` (non-force) while children unresolved/failed/manual-review — notably `test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_when_required_child_unresolved` (~130), `::test_parent_completion_blocked_direct_guard` (~152), and `test_phase5a6r3_scenario_certification.py::test_s16_s31_incorrect_completed_parent_detected` (~258). Any equivalent guarded path in `test_required_child_failure_prevents_false_completion`, `test_unknown_or_recovery_required_child_blocks_completion`, or `test_s7_s11_required_failure_and_manual_review_prevent_completion` would also have been masked if it relied on the guard raising Conflict.
- **Real aggregation reason (after fix):** `Conflict` with message `cannot complete: required child work unresolved/uncertain/manual-review` and `detail.aggregation` populated (e.g. `waiting_for_children`, failed counts, `can_complete=false`, `requires_manual_review` as applicable).
- **Unrelated to D-001:** `test_same_idempotency_key_different_spec_rejected` (idempotency Conflict) — not due to NameError before or after.
- No existing tests in target files were edited; this is a reporting-only audit.


===== Conflict messages (after fix) (ENGINEERING_AUDIT/S0_CLOSURE/D001_CONFLICT_MESSAGES_AFTER_FIX.json) =====
{
  "direct_guard": {
    "exc": "Conflict",
    "msg": "parent task aj_20261115T155040_cb37172b cannot complete: required child work unresolved/uncertain/manual-review",
    "detail_summary": "aggregation shows waiting/required unresolved, can_complete false"
  },
  "child_failed": {
    "exc": "Conflict",
    "msg": "parent task aj_20261115T155040_6c4710e4 cannot complete: required child work unresolved/uncertain/manual-review",
    "detail_summary": "aggregation shows failed required child, can_complete false"
  },
  "idempotency_conflict": {
    "exc": "Conflict",
    "msg": "same delegation idempotency key with different specification",
    "note": "not from completion guard; unaffected by D-001"
  }
}

===== Final test file (tests/s0_proof/test_s0_characterization.py) =====
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


===== 58_POLICY_DECISIONS.md (ENGINEERING_AUDIT/S0_CLOSURE/58_POLICY_DECISIONS.md) =====
--- DOC 58 (decisions approved by delegation of the owner, v1) ---
D1 REQUIRED/OPTIONAL
- child_spec gets `required: bool`. Missing => required=true, recorded in child
  evidence as classification_source="default_required".
- Present but not a real bool (string, 0/1, null) => REJECT delegation creation
  with a validation error.
- Legacy persisted records without the field: all children required,
  classification_source="legacy_default_required". Read-time default only; NO
  rewriting of persisted data.
- aggregation_policy interplay: all_required: children with required=true must
  all be COMPLETED, optional ones never block unless unresolved. subset_required:
  if both required_child_ids and per-child `required` are given they must agree
  or creation is rejected; if only required_child_ids is given, listed refs are
  required and the rest optional. any_sufficient: `required` is recorded but not
  used for the completion rule.
D2 PARENT OUTCOME (child state classes)
- completed: COMPLETED. failed: FAILED, ABORTED, DEAD_LETTER, ABANDONED.
  cancelled: CANCELLED. unresolved/ambiguous: every other state, plus missing,
  unloadable or contradictory child records.
- Required child failed or cancelled => parent cannot complete; reconcile moves
  parent to FAILED with evidence "required_child_failed|cancelled".
- Required child unresolved/ambiguous => parent cannot complete, flagged manual
  review (requires_user_decision), status otherwise unchanged.
- Optional child failed or cancelled => parent MAY complete; evidence lists
  "optional_children_not_completed". Optional child unresolved => blocks
  completion until resolved (operator resolves via existing reconcile actions).
- NO partial-success status. Success only if all required COMPLETED and no
  unresolved child remains.
- The parent COMPLETED guard applies REGARDLESS of force=True.
D3 ABANDONED
- Add ABANDONED to aj/task.py constants, TERMINAL and TRANSITIONS. Legal source
  states = exactly the set Aj.abandon accepts today (derive from code and
  tests/test_dead_letter.py, do not widen). EXECUTING and CANCEL_REQUESTED stay
  excluded unless an existing test demands otherwise. Remove force=True from
  abandon once the edge is legal. Reload/import/event validation must accept
  ABANDONED; completed_at is set; legacy persisted ABANDONED records must load.
D4 ADMIN/SCHEDULER
- Aj.requeue on a delegated task: BLOCKED.
- dead_letter/abandon on a delegated child: allowed only through operator
  reconcile, must write delegation evidence and trigger parent reconcile.
- dead_letter/abandon on a parent with non-terminal children: BLOCKED.
- Scheduler (eligibility AND again under lease before dispatch) must verify for
  a delegated child: parent not CANCELLED/CANCEL_REQUESTED/ABORTED/DEAD_LETTER,
  delegation record active and linked, permission snapshot still a subset.
  Otherwise defer with a recorded reason.
- Cancelling a parent cancels non-terminal children through each child's own
  cancel flow (EXECUTING => CANCEL_REQUESTED, cooperative), records delegation
  evidence, and moves open assignments to CANCELLED.
D5 UNSUPPORTED CLAIMS (T-11)
- Anything the system cannot actually do (remote agent transport, exactly-once
  external effects, authenticated identity, Hermes attachment) must be rejected
  or reported as UNSUPPORTED, never silently accepted.
--- END DOC 58 ---


---
## D3 REFINEMENT (S0 round 3, derived from code + tests; not widening)
**Current implementation (observed):** `Aj.abandon` (`aj/orchestrator.py`) refuses only if status is already `ABANDONED`, then performs `self.tasks.transition(task_id, "ABANDONED", ..., force=True, reason="abandoned")` (bypasses `TaskRecord.can_transition`/terminal checks). Therefore in practice it accepts broadly (any non-ABANDONED state), including terminal/active states unless separately prevented — this is broader than policy intent.

**Tests observed (`tests/test_dead_letter.py`):** abandon exercised from FAILED (direct/after flow), from PLANNED (after requeue), and idempotent behavior when already ABANDONED; no test requires abandoning EXECUTING or CANCEL_REQUESTED; no test requires abandoning COMPLETED.

**Doc 58 D3 refinement (approved policy target):**
- Legal source states for `ABANDONED` = **FAILED, DEAD_LETTER, RECOVERY_REQUIRED, ESCALATED**.
- Everything else refused: all other terminal states (COMPLETED, ABORTED, CANCELLED, ABANDONED) and all active/non-listed states (including EXECUTING and CANCEL_REQUESTED).
- `Aj.abandon` must explicitly validate source state and **must no longer rely on `force=True`** once `ABANDONED` edges are legal in FSM/TRANSITIONS.
- `ABANDONED` must be added to `aj/task.py` constants, `TERMINAL`, and `TRANSITIONS` for the legal source states only; reload/import/event validation must accept `ABANDONED`; `completed_at` set; legacy persisted `ABANDONED` records must load (D3). **No aj/ implementation performed in this S0 round except D-001 defect fix below.**

## D-001 DEFECT FIXED: missing import (authorized, S0 round 3)
- **Defect:** `aj/orchestrator.py` imported `AssignmentStore, DelegationStore, LogicalAgentStore, detect_delegation_anomalies` from `.delegation` but omitted `aggregate_parent_progress`. `_before_task_transition` (delegation-parent `COMPLETED` guard, non-force) calls `aggregate_parent_progress(...)`, causing `NameError` caught and wrapped as `Conflict("... delegation state unverifiable (NameError)")`. Effect: every non-force completion of a delegated parent blocked as unverifiable (including legitimate completions); existing Conflict-expecting tests could pass for wrong reason.
- **Fix applied (only authorized source edit):** added `aggregate_parent_progress` to that import in `aj/orchestrator.py` (line ~51). No other source changes; `except Exception` handling unchanged.
- **Evidence before fix:** `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_BEFORE_FIX.txt` — `test_b3_parent_with_all_required_children_completed_completes` failed with `NameError: name 'aggregate_parent_progress' is not defined` -> `aj.errors.Conflict: ... unverifiable (NameError)`.
- **Evidence after fix:** `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_AFTER_FIX.txt` — same B3 test PASSED. `ENGINEERING_AUDIT/S0_CLOSURE/D001_CONFLICT_MESSAGES_AFTER_FIX.json` shows completion guard now raises real aggregation-based `Conflict` (with `aggregation` detail, no `NameError`/`unverifiable`).
- **Suite impact:** existing suite (`--ignore=tests/s0_proof`) before fix: 576 passed, 1 failed (intermittent NTFS sqlite disk I/O), 13 warnings; after fix: 577 passed, 13 warnings (sqlite test passed in that run). No deterministic regression attributed to D-001. Completion-blocking delegation tests asserting `Conflict` on guarded parent completion previously could pass for wrong reason (NameError-wrapped unverifiable); with fix they pass with real aggregation reasons (see STEP 3 change table in REVIEW_PACK_3 / report).


===== CALLABLE_INVENTORY_S0.md v2 (ENGINEERING_AUDIT/S0_CLOSURE/CALLABLE_INVENTORY_S0.md) =====
# CALLABLE_INVENTORY_S0.md v2 (E2)

**Status:** NOT exhaustive. AST-based enumeration of `aj/*.py` plus prior grep comparison; dispositions are evidence-informed but conservative. Every enumerated AST entry below has a final disposition: `GUARDED` / `S2-FIX` / `BLOCK-PER-D4` / `UNSUPPORTED` / `NOT VERIFIABLE` (with reason).

## Tools / commands (exact)
```bash
# grep (prior/round 2)
grep -rn "\.tasks\.transition(" aj tests
grep -rn "force=True" aj tests
grep -n "tasks\.transition = _guarded_transition\|_orig_transition\|_before_task_transition" aj/orchestrator.py
grep -rn "dead_letter\|requeue\|abandon\|Aj\." aj/runtime.py
grep -rn "def _cmd_" aj/__main__.py

# AST (round 3)
python3 ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph.py
# outputs: ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph_results.json, ast_callgraph_results.txt
```

## AST vs grep comparison
- AST parsed `aj/*.py` (146 call-site entries recorded in `ast_callgraph_results.json/.txt`) for targets: tasks.transition, TaskRecord.transition, dead_letter, requeue, abandon, delegate, _prepare_delegated_child_for_scheduling, _reconcile_delegation_parent, resume, retry, recover, cancel_task, cancel, run_once, _dispatch_one, reconcile, import_record, save, mutate (and transition-qualified forms).
- Grep previously enumerated `.tasks.transition` call sites across `aj/` and `tests/` and found no direct `.tasks.transition` in `aj/orb.py`, `aj/orb_web.py`, `aj/orb_autostart.py`, `aj/inbox.py`, `aj/inbox_cli.py`; AST of `aj/*.py` likewise found no transition-target call sites in those modules but did find `save` in `aj/orb.py` (see table).
- AST adds structured caller/function context within `aj/*.py`; grep remains necessary for `tests/` and raw text patterns (e.g. `force=True`) not modeled as call targets. No additional **missed production `.tasks.transition` callers in `aj/*.py`** beyond grep were identified by this AST pass (grep already covered them); AST surfaced broader target-call inventory (save/mutate/resume/cancel/reconcile/import_record etc.) for disposition.
- **force=True (grep, production):** `aj/orchestrator.py:3438` (requeue DEAD_LETTER->PLANNED), `aj/orchestrator.py:3496` (-> ABANDONED). No `force=True` in `tests/`. Monkeypatch in `Aj.__init__` wraps `tasks.transition` (pre `_before_task_transition`, post hook) — D-001 fixed guard evaluation bug.

## Disposition summary (key surfaces, Doc58)
| Surface / callable family | Disposition | Reason (evidence-based) |
|---|---|---|
| `Aj.tasks.transition` via monkeypatched guard (`_before_task_transition`, D-001 fixed) | **GUARDED** (partial) | Guard now evaluates aggregation correctly; but `force=True` bypasses completion guard and semantic policies (D2) not enforced; not all required invariants satisfied. |
| `Aj.requeue` (delegated tasks) | **BLOCK-PER-D4 / S2-FIX** | Must be BLOCKED for delegated tasks (Doc58 D4). A2b xfail shows not blocked. |
| `Aj.dead_letter` / `Aj.abandon` (delegated child, direct) | **BLOCK-PER-D4 / S2-FIX** | Allowed only via operator reconcile with delegation evidence + parent reconcile (D4). A2a/A2c xfail. |
| `Aj.abandon` source-state validation / no `force` reliance | **S2-FIX (S1/D3 impl)** | Must restrict to FAILED, DEAD_LETTER, RECOVERY_REQUIRED, ESCALATED and refuse others (D3 refinement). A8 xfail. |
| `dead_letter`/`abandon` on parent with non-terminal children | **BLOCK-PER-D4 / S2-FIX** | Doc58 D4 requires BLOCKED; not proven/enforced. |
| `_prepare_delegated_child_for_scheduling` | **S2-FIX** | Needs full current delegation/authority/parent-state enforcement per D4; partial. |
| `Scheduler.run_once` / `_dispatch_one` (eligibility + pre-dispatch under lease) | **S2-FIX** | Must verify parent not cancelled/cancel-requested/aborted/dead-letter, delegation active+linked, permission snapshot subset (D4). A3 xfail. |
| Parent cancellation propagation to non-terminal children | **S2-FIX** | A4 xfail; cooperative child cancel flow + evidence/assignment updates required (D4). |
| Parent COMPLETED regardless of `force=True` (D2) | **S2-FIX** | A5 xfail; completion guard currently bypassed when `force=True`. |
| `Aj.delegate` validation (D1 required bool, D5/T-11 unsupported claims) | **S2-FIX** | A6/A7 xfail; explicit required classification, malformed rejection, unsupported-claim rejection/reporting missing. |
| `TaskStore.import_record` / import CLI (`_cmd_import` -> `transfer.import_file`) | **GUARDED** (structural) | Validates status/schema/history/conflicts; cannot load arbitrary/invalid statuses (ABANDONED currently invalid). Caller provenance/trust **NOT VERIFIABLE**. |
| `aj/runtime.py` direct `tasks.transition` (self-check helpers) | **NOT VERIFIABLE** | Diagnostic/temp-context usage observed; production impact/coverage not fully proven. |
| Orb (`aj/orb*.py`, CLI wiring) | **NOT VERIFIABLE** | No direct `.tasks.transition` found; indirect task mutation coupling unproven. `orb.py:save` observed (UI/state persistence context) — disposition **NOT VERIFIABLE** for task-lifecycle safety. |
| Inbox (`aj/inbox*.py`, CLI) | **NOT VERIFIABLE** | No direct `.tasks.transition` found; inbox-domain retry/requeue distinct from task FSM; coupling to AJ task mutations unproven. |
| Unsupported claims/capabilities surfaces (remote transport, exactly-once external, authenticated identity, Hermes attachment) | **UNSUPPORTED** (must reject/report per D5/T-11) | Enforcement not proven across surfaces (A7 xfail). |

## Enumerated AST call-site dispositions (aj/*.py)

| File:Line | Caller | Call | Target | Disposition | Reason |
|---|---|---|---|---|---|
| `aj/__main__.py:439` | `_cmd_cancel` | `aj.cancel_task` | `cancel_task` | **NOT VERIFIABLE** | CLI entrypoint; delegated-context blocking/guarding per D4 not proven |
| `aj/__main__.py:457` | `_cmd_retry` | `aj.retry` | `retry` | **NOT VERIFIABLE** | CLI entrypoint; delegated-context blocking/guarding per D4 not proven |
| `aj/__main__.py:775` | `_cmd_recover` | `manager.recover` | `recover` | **NOT VERIFIABLE** | CLI entrypoint; delegated-context blocking/guarding per D4 not proven |
| `aj/__main__.py:800` | `_cmd_reconcile` | `aj.reconcile` | `reconcile` | **NOT VERIFIABLE** | CLI entrypoint; delegated-context blocking/guarding per D4 not proven |
| `aj/calling.py:264` | `prepare` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:266` | `prepare` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:269` | `prepare` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:273` | `prepare` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:277` | `prepare` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:281` | `prepare` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:285` | `prepare` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:304` | `confirm_and_dial` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:333` | `confirm_and_dial` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:334` | `confirm_and_dial` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:338` | `confirm_and_dial` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:344` | `confirm_and_dial` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:347` | `confirm_and_dial` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:376` | `hang_up` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/calling.py:383` | `cancel` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/execution_domain.py:256` | `transition` | `rec.transition` | `transition` | **NOT VERIFIABLE** | observed call-site; coverage not proven |
| `aj/execution_domain.py:257` | `transition` | `self.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orb.py:615` | `on_draw` | `cr.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:315` | `handle` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:331` | `handle` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:337` | `handle` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:338` | `handle` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:344` | `handle` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:386` | `handle` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:391` | `handle` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:414` | `handle` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:418` | `handle` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:439` | `handle` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:445` | `handle` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:490` | `_retry_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:492` | `_retry_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:495` | `_retry_locked` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:512` | `_retry_locked` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:534` | `_retry_locked` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:563` | `_retry_locked` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:583` | `_retry_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:585` | `_retry_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:628` | `_cancel_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:632` | `_cancel_locked` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:649` | `_cancel_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:664` | `cancel` | `self.cancel_task` | `cancel_task` | **NOT VERIFIABLE** | core callable present; Doc58 delegated-safety coverage across all paths/contexts not fully proven (some BLOCK-PER-D4 needed) |
| `aj/orchestrator.py:1018` | `_recover_locked` | `self.tasks.mutate` | `mutate` | **GUARDED** | TaskStore.mutate enforces lifecycle-field protection; caller correctness/invariants not fully proven |
| `aj/orchestrator.py:1092` | `_recover_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1094` | `_recover_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1100` | `_recover_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1173` | `_require_manual_recovery` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1184` | `_require_manual_recovery` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1308` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1348` | `_execute` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1349` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1351` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1356` | `_execute` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1423` | `_execute` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1425` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1431` | `_execute` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1449` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1450` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1455` | `_execute` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1499` | `_execute` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1501` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1503` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1512` | `_execute` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1527` | `_execute` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1619` | `_execute_calling` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1625` | `_execute_calling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1631` | `_execute_calling` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:1656` | `_execute_calling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1658` | `_execute_calling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:1666` | `_execute_calling` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:2009` | `_handle_stale_authorization` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2012` | `_handle_stale_authorization` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:2058` | `_resume_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2075` | `_resume_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2097` | `_resume_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2116` | `_resume_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2120` | `_resume_locked` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:2147` | `_resume_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2169` | `_resume_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2188` | `_resume_locked` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2192` | `_resume_locked` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:2251` | `dead_letter` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:2254` | `dead_letter` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:2775` | `_record_operator_reconciliation` | `self.tasks.mutate` | `mutate` | **GUARDED** | TaskStore.mutate enforces lifecycle-field protection; caller correctness/invariants not fully proven |
| `aj/orchestrator.py:2851` | `_record_operator_reconciliation` | `self.tasks.mutate` | `mutate` | **GUARDED** | TaskStore.mutate enforces lifecycle-field protection; caller correctness/invariants not fully proven |
| `aj/orchestrator.py:3247` | `reconcile` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3269` | `reconcile` | `self.dead_letter` | `dead_letter` | **S2-FIX** | Doc58 D4: delegated child dead_letter/abandon allowed only via operator reconcile with delegation evidence+parent reconcile; direct path not delegation-safe (A2a/A2c xfail) |
| `aj/orchestrator.py:3279` | `reconcile` | `self.abandon` | `abandon` | **S2-FIX** | Doc58 D4: delegated child dead_letter/abandon allowed only via operator reconcile with delegation evidence+parent reconcile; direct path not delegation-safe (A2a/A2c xfail) |
| `aj/orchestrator.py:3307` | `reconcile` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3437` | `requeue` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3455` | `requeue` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3494` | `abandon` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3502` | `abandon` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3562` | `_transition_execution` | `rec.transition` | `transition` | **NOT VERIFIABLE** | core callable present; Doc58 delegated-safety coverage across all paths/contexts not fully proven (some BLOCK-PER-D4 needed) |
| `aj/orchestrator.py:3563` | `_transition_execution` | `self.executions.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3597` | `_start_attempt` | `erec.transition` | `transition` | **NOT VERIFIABLE** | core callable present; Doc58 delegated-safety coverage across all paths/contexts not fully proven (some BLOCK-PER-D4 needed) |
| `aj/orchestrator.py:3598` | `_start_attempt` | `self.executions.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3599` | `_start_attempt` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3618` | `_finish_attempt` | `erec.transition` | `transition` | **NOT VERIFIABLE** | core callable present; Doc58 delegated-safety coverage across all paths/contexts not fully proven (some BLOCK-PER-D4 needed) |
| `aj/orchestrator.py:3619` | `_finish_attempt` | `self.executions.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3624` | `_finish_attempt` | `erec.transition` | `transition` | **NOT VERIFIABLE** | core callable present; Doc58 delegated-safety coverage across all paths/contexts not fully proven (some BLOCK-PER-D4 needed) |
| `aj/orchestrator.py:3625` | `_finish_attempt` | `self.executions.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3660` | `_fail` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3666` | `_fail` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3778` | `_mark_delegation_reconciliation_pending` | `self.delegations.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:3808` | `_on_task_transition` | `self._reconcile_delegation_parent` | `_reconcile_delegation_parent` | **NOT VERIFIABLE** | core callable present; Doc58 delegated-safety coverage across all paths/contexts not fully proven (some BLOCK-PER-D4 needed) |
| `aj/orchestrator.py:3831` | `reconcile_delegation_parent` | `self._reconcile_delegation_parent` | `_reconcile_delegation_parent` | **NOT VERIFIABLE** | core callable present; Doc58 delegated-safety coverage across all paths/contexts not fully proven (some BLOCK-PER-D4 needed) |
| `aj/orchestrator.py:3942` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3957` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3960` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3976` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3985` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:3996` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:4002` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:4005` | `_prepare_delegated_child_for_scheduling` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:4008` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:4011` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | `tasks.transition` | **GUARDED** | Aj.__init__ monkeypatch routes through _before_task_transition/_on_task_transition (D-001 fixed guard eval); specific semantic correctness still depends on S1-S3 fixes for Doc58 gaps |
| `aj/orchestrator.py:4026` | `_prepare_delegated_child_for_scheduling` | `self.tasks.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:4052` | `_reconcile_delegation_parent` | `self._prepare_delegated_child_for_scheduling` | `_prepare_delegated_child_for_scheduling` | **S2-FIX** | must enforce full current delegation/parent authority checks per Doc58 D4; partial checks observed |
| `aj/orchestrator.py:4113` | `_reconcile_delegation_parent` | `self.delegations.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:4321` | `delegate` | `self.delegations.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:4352` | `delegate` | `self.delegations.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:4392` | `delegate` | `self._prepare_delegated_child_for_scheduling` | `_prepare_delegated_child_for_scheduling` | **S2-FIX** | must enforce full current delegation/parent authority checks per Doc58 D4; partial checks observed |
| `aj/orchestrator.py:4422` | `delegate` | `self.delegations.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/orchestrator.py:4432` | `delegate` | `self._reconcile_delegation_parent` | `_reconcile_delegation_parent` | **NOT VERIFIABLE** | core callable present; Doc58 delegated-safety coverage across all paths/contexts not fully proven (some BLOCK-PER-D4 needed) |
| `aj/orchestrator.py:4443` | `delegate` | `self.delegations.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/recovery.py:92` | `_recover_one` | `self.aj.recover` | `recover` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/runtime.py:163` | `_check_tasks` | `store.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/runtime.py:164` | `_check_tasks` | `store.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/runtime.py:246` | `_check_task_persistence` | `store.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/runtime.py:247` | `_check_task_persistence` | `store.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/runtime.py:303` | `_check_recovery` | `aj.tasks.transition` | `tasks.transition` | **NOT VERIFIABLE** | self-check/diagnostic helper context; production-path intent/coverage not fully proven |
| `aj/runtime.py:422` | `_check_cancel_retry` | `aj.cancel_task` | `cancel_task` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/runtime.py:428` | `_check_cancel_retry` | `aj.tasks.transition` | `tasks.transition` | **NOT VERIFIABLE** | self-check/diagnostic helper context; production-path intent/coverage not fully proven |
| `aj/runtime.py:429` | `_check_cancel_retry` | `aj.retry` | `retry` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/scheduler.py:720` | `_dispatch_one` | `self.aj.dead_letter` | `dead_letter` | **NOT VERIFIABLE** | observed call-site; coverage not proven |
| `aj/scheduler.py:740` | `_dispatch_one` | `self.aj.resume` | `resume` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/scheduler.py:836` | `run_once` | `self._dispatch_one` | `_dispatch_one` | **S2-FIX** | Doc58 D4: scheduler eligibility and pre-dispatch-under-lease must verify parent not cancelled/revoked/aborted/dead_letter, delegation active+linked, permission subset (A3 xfail) |
| `aj/scheduler.py:839` | `run_once` | `self._dispatch_one` | `_dispatch_one` | **S2-FIX** | Doc58 D4: scheduler eligibility and pre-dispatch-under-lease must verify parent not cancelled/revoked/aborted/dead_letter, delegation active+linked, permission subset (A3 xfail) |
| `aj/task.py:628` | `update` | `self.save` | `save` | **GUARDED** | store-controlled persistence/validation semantics in TaskStore/controlled paths; full misuse-surface not exhaustively proven |
| `aj/task.py:650` | `transition` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/task.py:665` | `cancel` | `record.transition` | `transition` | **NOT VERIFIABLE** | callable/use observed; full safety/coverage per Doc58 not proven |
| `aj/transfer.py:176` | `import_file` | `store.import_record` | `import_record` | **GUARDED** | TaskStore.import_record validates structure/status/history and rejects conflicts; provenance/authorization of caller is separate (NOT VERIFIABLE in S0) |

## What AST cannot see (explicit)
- Dynamic dispatch: `getattr`, `setattr`, function pointers/callables stored in variables/containers, reflection-based invocation.
- Runtime mutation/indirection: monkeypatching/wrapper behavior beyond static syntax (except where known), decorators altering call semantics at runtime, dependency injection targets.
- Concurrency/callback paths: thread targets, async callbacks, registered hooks invoked indirectly, signal handlers, scheduler/executor internals beyond direct calls.
- Non-Python / external / process boundaries: CLI subprocess invocations, shell commands, RPC/IPC, UI event loops, external services.
- `tests/` not enumerated by this AST script run (grep used for tests/`force=True`); generated/dynamic code not analyzed.
- Semantic correctness, authorization sufficiency, race safety, and cross-store atomicity are not proven by call-site presence.

## Explicitly still unproven / not closed
- Exhaustive wrapper/UI/background/external integration call graph and every admin/operator/CLI path for delegated contexts (Doc58 D4).
- All runtime non-diagnostic production paths, orb/inbox indirect task-mutation coupling.
- That every relevant mutation occurs on Aj-wrapped stores (bypassing monkeypatch guard) in all contexts.
- Full AST + runtime confirmation of every `force=True`-equivalent or bypass path.


===== PROOF_SPECS.md (ENGINEERING_AUDIT/S0_CLOSURE/PROOF_SPECS.md) =====
# PROOF_SPECS (S0 E3)

Purpose: executable proof specifications for INV-01..INV-10 and T-01..T-12 (Doc 54 / Doc 58 intent). Each item states setup, invocation, authoritative persisted record(s), expected result, forbidden result, stage (S1–S4) for implementation/proof, and covering test (existing/new). Items that cannot honestly be tested are marked explicitly. **No implementation performed in S0.**

## Legend
- **Authoritative persisted record:** record(s) that constitute ground truth for the assertion (tasks.jsonl, delegations.jsonl, assignments.jsonl, scheduler_decisions.jsonl, leases/state, receipts/journal/audit where applicable).
- **Stage:** planned stage to implement/fix and/or prove (S1 policy/model, S2 authz/scheduler/admin guards, S3 lifecycle/cancel/reconcile, S4 crash/concurrency feasible boundaries). S0 = spec/evidence only.
- **Status note:** `UNTESTABLE NOW` = cannot honestly be tested without seams/decisions/mechanisms not present; must not be claimed VERIFIED.

## INV-01 — Authorization must fail closed
| Field | Spec |
|---|---|
| Setup | Delegated parent+child (real Aj/TaskStore/Scheduler, persisted /tmp). Construct cases: valid current delegation/permission/linkage; missing/malformed/revoked delegation record; parent cancelled/revoked/aborted/dead_letter; child unlinked; widened/contradictory permission envelope; unverifiable state. |
| Invocation | Exercise each supported entry point: delegation prep/authorization, scheduler eligibility/admission+pre-dispatch under lease, resume/execute boundary, retry/recover/reconcile/CLI-admin paths as applicable per inventory disposition. |
| Authoritative persisted record | `tasks.jsonl` (child/parent status, events, authorization_context/delegation evidence), `delegations.jsonl`, `assignments.jsonl`, `scheduler_decisions.jsonl`, audit/receipt/journal where emitted. |
| Expected | Valid+current state may proceed only where authorized; all invalid/missing/malformed/revoked/unverifiable/widened/contradictory cases **rejected or deferred** with traceable reason/evidence; no unauthorized child execution/dispatch. |
| Forbidden | Unauthorized dispatch/execution; success on unverifiable/missing/revoked authority; silent widening; dispatch when parent cancelled/revoked or delegation inactive/unlinked. |
| Stage | S1/S2 (classification/guards/scheduler/admin blocking), S4 for race timing where feasible. |
| Covering test | Existing: partial coverage in delegation/scheduler tests (some now corrected for real reasons post D-001). New/needed: per-path negative matrix incl. `tests/s0_proof/test_s0_characterization.py::test_a2a_*`, `a2b`, `a2c`, `a3` (currently xfail characterizations) and exhaustive path tests per inventory S2-FIX/BLOCK-PER-D4 items. |
| Untestable now? | **Exhaustive “every supported/alternative/administrative path” untestable now** until inventory fully closed and all paths guarded/blocked; dynamic external revocation/IAM-style proofs **NOT VERIFIABLE/UNSUPPORTED**. |

## INV-02 — Delegated permission narrowing
| Field | Spec |
|---|---|
| Setup | Delegation requests with explicit permission contexts: valid narrowing intersections; missing/malformed/ambiguous contexts; widened requested/effective sets; contradictory snapshots; post-assignment reduction/revocation scenarios. |
| Invocation | `Aj.delegate` validation/creation; prep/authorization boundaries; execution guard revalidation; any mutation path touching permission envelope. |
| Authoritative persisted record | `delegations.jsonl` (request/evidence), child task `authorization_context.delegation.permission_decision` snapshots in `tasks.jsonl`, assignment records. |
| Expected | Effective permissions = intersection/narrowing-only; missing/malformed/unverifiable/widened/contradictory rejected fail-closed; boundary revalidation against current state per approved design. |
| Forbidden | Privilege escalation/widening; acceptance of malformed/ambiguous permission data; snapshot-only equality treated as sufficient where revalidation required. |
| Stage | S1 (model/validation) + S2 (boundary revalidation). |
| Covering test | Existing: delegation foundation/closure tests cover parts. New: `test_a6` aspects (classification context) indirect; dedicated narrowing/adversarial matrix needed. |
| Untestable now? | Full current-source revalidation across all boundaries **NOT VERIFIABLE** until implemented/proven. |

## INV-03 — Parent lifecycle correctness
| Field | Spec |
|---|---|
| Setup | Parent with required/optional children (per D1 once implemented): children in completed/failed/cancelled/unresolved/ambiguous/missing/unloadable/contradictory states; aggregation policies (all_required, subset_required, any_sufficient). |
| Invocation | Child transitions, reconciliation, and parent completion attempts including direct `tasks.transition(..., COMPLETED, force=True)` and any other completion-capable path. |
| Authoritative persisted record | Child+parent `tasks.jsonl` states/events, `delegations.jsonl` reconciliation evidence/aggregation snapshots. |
| Expected | Parent COMPLETED only when all required COMPLETED and no unresolved child remains (per D2); required failed/cancelled => cannot complete (reconcile moves parent to FAILED with evidence as specified); unresolved/ambiguous required => blocked + manual review; optional semantics per D2; **guard applies regardless of `force=True`**. |
| Forbidden | False completion with unresolved/failed/cancelled required child; partial-success mapped to COMPLETED; silent optional default for missing/malformed classification. |
| Stage | S1 (classification/state mapping) + S3 (guards/reconcile semantics). |
| Covering test | Existing: post D-001 completion guard now real in covered cases. New/needed: `test_a5` (xfail), `test_b5` (PASS for current aggregation block), `test_a6`/T-04, full D1/D2 matrix. |
| Untestable now? | **Final approved outcome-state mapping (D2/Doc57 decision #2) dependent** for some cases; cannot claim full conformance until decided/implemented. |

## INV-04 — Cancellation safety
| Field | Spec |
|---|---|
| Setup | Delegated parent with non-terminal children in various states (AUTHORIZED, EXECUTING, WAITING_FOR_APPROVAL, etc.), active assignments; in-flight dispatch/recovery windows where feasible. |
| Invocation | `cancel_task(parent)` / cancellation transitions; scheduler dispatch attempts; child prep/resume/retry/recover; late child completion/failure outcomes; recovery after cancellation. |
| Authoritative persisted record | Parent/child `tasks.jsonl`, `delegations.jsonl`/assignment state, scheduler decisions/leases, audit/journal evidence. |
| Expected | Durable parent cancellation prevents prohibited prep/dispatch; parent cancel propagates to non-terminal children via child cancel flow (EXECUTING => CANCEL_REQUESTED cooperative) with delegation evidence and assignment updates (D4); no resurrection of prohibited work; ambiguous outcomes unresolved/non-success. |
| Forbidden | Dispatch/prep/execute under cancelled/revoked parent authority; children left silently active/orphaned; late outcomes silently creating success or overwriting authoritative terminal states. |
| Stage | S2 (scheduler/dispatch guards) + S3 (orchestration/cancel propagation) + S4 (race boundaries). |
| Covering test | `test_a2a/a2b/a2c` (xfail), `test_a3` (xfail), `test_a4` (xfail); existing scheduler/guard tests partial. |
| Untestable now? | True race/late-outcome/interruption safety **needs S4 seams/boundaries**; instant stop of external side effects **UNSUPPORTED**. |

## INV-05 — Reconciliation correctness and boundedness
| Field | Spec |
|---|---|
| Setup | Delegations with consistent, unchanged, stale, contradictory, or partially missing records; concurrent mutating/apply calls (single-process controlled); dry-run vs apply. |
| Invocation | `reconcile_delegation_parent` / `Aj.reconcile_delegation_parent` (dry-run, apply), monitoring/status reads, anomaly detection; repeated calls. |
| Authoritative persisted record | `delegations.jsonl` evidence/history/reconciliation markers, affected `tasks.jsonl`/assignment records when apply mutates. |
| Expected | Idempotent/no-op on unchanged state; dry-run no authoritative mutation; apply records provenance/outcome; bounded batch respected; contradictions/unverifiable inputs fail closed or explicit unresolved; read-only monitoring non-mutating. |
| Forbidden | Duplicate logical outcomes; dry-run/monitor mutation; unbounded processing claims; silent auto-repair of unverifiable contradictions. |
| Stage | S3 (correctness/safety) + S4 (concurrency/stale-writer where feasible). |
| Covering test | Existing r2/r3/r4 reconciliation tests cover parts; need contradiction/stale-writer/duplicate-apply race matrix. |
| Untestable now? | Proven stale-writer protection and multi-store interruption atomicity **NOT VERIFIABLE** without mechanisms/seams. |

## INV-06 — Crash and recovery honesty
| Field | Spec |
|---|---|
| Setup | Persisted states at derived boundaries (see CRASH_FEASIBILITY): interrupted task transitions, dispatch intent/lease/start/result splits, delegation multi-record writes, recovery-required/abandoned/ambiguous records. |
| Invocation | Process restart/reload, `RecoveryManager`/recover flows, scheduler re-evaluation, reconciliation/inspection. |
| Authoritative persisted record | All relevant append-only stores on disk at interruption point and after recovery attempt. |
| Expected | Supported boundaries recover or become explicitly unresolved/manual-review with evidence; no silent success; no duplicate authoritative transitions on repeated recovery. |
| Forbidden | Fabricated success from ambiguous/incomplete state; resurrection of prohibited work; claiming recovery for unsupported boundaries. |
| Stage | S4 (feasible boundaries only) + S5 constraints for storage. |
| Covering test | `test_a1`, `test_a1b` (xfail characterizations for ABANDONED/load/resurrection gap); existing recovery tests partial. |
| Untestable now? | **Most crash windows NOT VERIFIABLE/need S4 seams**; OS/power/fs failures **UNSUPPORTED**; original A–H **UNRECOVERED**. |

## INV-07 — Concurrency and stale-state safety
| Field | Spec |
|---|---|
| Setup | Controlled single-process concurrent operations: mutating reconciliations, dispatch attempts, cancel-vs-complete, recovery-vs-dispatch, duplicate apply, assignment/execution mutations (where representable). |
| Invocation | Thread/process-coordinated harness within declared boundary; repeated runs. |
| Authoritative persisted record | Task/delegation/assignment/lease/scheduler ledgers showing consistent final state and no contradictory authoritative outcomes. |
| Expected | No silently contradictory authoritative outcomes; no stale overwrite in demonstrated boundary; idempotent handling where specified. |
| Forbidden | Universal concurrency/multi-process/distributed correctness claims; silent corruption/duplication. |
| Stage | S3/S4 (mechanism-backed tests within feasible boundary). |
| Covering test | Some concurrent reconciliation tests exist; sqlite/storage concurrency experiments (E6) are storage-specific. |
| Untestable now? | Multi-process/distributed and many race classes **NOT VERIFIABLE/UNSUPPORTED**; stale-writer mechanism proof pending. |

## INV-08 — Anomaly visibility
| Field | Spec |
|---|---|
| Setup | Inject/construct supported anomaly classes: missing/inconsistent delegation records, contradictory terminal states, stuck/ambiguous operations, stale aggregation, incorrect completed parent, missing linkage/provenance, expired/uncertain lease (detectable). |
| Invocation | `detect_delegation_anomalies` / `delegation_monitor` / inspection APIs (read-only). |
| Authoritative persisted record | Unchanged authoritative stores before/after detection; monitor findings with ids/evidence. |
| Expected | Each supported anomaly detected/surfaced with affected ids and available evidence; detection read-only. |
| Forbidden | Silent mutation by detection; presenting known inconsistencies as healthy. |
| Stage | S3 (detector completeness) + S4 where anomaly arises from races/crash. |
| Covering test | Existing anomaly/monitor tests partial; full class-by-class fixtures needed. |
| Untestable now? | Complete coverage/certification for all classes **UNVERIFIABLE** now. |

## INV-09 — Evidence and auditability
| Field | Spec |
|---|---|
| Setup | Operations across authorize/reject/dispatch/cancel/reconcile/recover/transition paths including failures and ambiguities. |
| Invocation | Execute each supported decision path. |
| Authoritative persisted record | Correlatable ids and records across tasks, attempts, executions, assignments, delegations, receipts/journal/audit/operation-evidence as applicable. |
| Expected | Traceable, non-fabricated evidence for decisions and rejections/ambiguities; missing evidence surfaced as uncertainty. |
| Forbidden | Evidence rewritten to claim success; atomic cross-store guarantees claimed. |
| Stage | S1–S4 (cross-cutting). |
| Covering test | Existing tests touch evidence; comprehensive per-decision matrix missing. |
| Untestable now? | Full coverage across every supported path **UNVERIFIABLE** now. |

## INV-10 — Honest system boundaries
| Field | Spec |
|---|---|
| Setup | Requests/claims for unsupported capabilities: remote agent transport/execution, exactly-once external effects, cross-store atomicity, authenticated identity, Hermes attachment, distributed correctness. |
| Invocation | Delegation/CLI/runtime/reporting surfaces where such claims could be made or accepted. |
| Authoritative persisted record | Request/response records, task/delegation evidence, logs/reports showing rejection or explicit UNSUPPORTED reporting. |
| Expected | Rejected/blocked or explicitly reported **UNSUPPORTED**; no silent acceptance or false capability claim. |
| Forbidden | Silent acceptance of unsupported claims; reporting success/capability without proof. |
| Stage | S1/S2 (validation/guards/reporting). |
| Covering test | `test_a7_t11_unsupported_capability_claim_rejected` (xfail characterization: remote agent transport claim currently accepted). |
| Untestable now? | All possible surfaces not exhaustively enumerated (**inventory closure required**). |

---

## T-01 — Authz paths positive/negative
- **Setup:** Valid vs missing/malformed/revoked/widened delegation & permission contexts for each supported path (prep, scheduler eligibility, dispatch/lease recheck, resume/execute, retry/recover, reconcile/admin as applicable).
- **Invocation:** Call each path with constructed contexts.
- **Authoritative persisted record:** Task/delegation/assignment/scheduler decision/audit records showing decision and no side effects on reject.
- **Expected:** Authorized only on valid/current; otherwise fail closed/defer/reject.
- **Forbidden:** Unauthorized execution/dispatch; success on invalid state.
- **Stage:** S1/S2. **Covering test:** partial existing; needs exhaustive matrix (see A2/A3). **Untestable now:** until all paths enumerated/blocked.

## T-02 — Revocation/cancellation lifecycle/race
- **Setup:** Post-assignment revocation or durable parent cancellation before/at prep/dispatch/execute/retry/recover.
- **Invocation:** Timed sequences (and race harness where feasible).
- **Authoritative persisted record:** State transitions, scheduler decisions, guard outcomes, lease/dispatch evidence.
- **Expected:** Prohibited actions blocked; no success.
- **Forbidden:** Prep/dispatch/execute after durable cancellation/revocation.
- **Stage:** S2/S3/S4. **Covering test:** A2/A3/A4 (xfail). **Untestable now:** race timing proofs need S4 seams.

## T-03 — Parent outcome / required vs optional
- **Setup:** Required satisfied vs pending/running/failed/cancelled/unresolved/ambiguous; optional cases per explicit policy.
- **Invocation:** Child outcomes + reconciliation + parent completion attempts (incl. force).
- **Authoritative persisted record:** Child/parent tasks, aggregation evidence.
- **Expected:** COMPLETED only when policy satisfied; never unsafe/partial-as-success.
- **Forbidden:** False completion, partial-as-success.
- **Stage:** S1/S3. **Covering test:** A4/A5/B5/A6. **Untestable now:** pending approved mapping for all cases.

## T-04 — Missing/malformed/contradictory classification
- **Setup:** `child_spec.required` missing, non-bool (`"maybe"`, 0/1, null), contradictory with `required_child_ids`/policy as applicable.
- **Invocation:** `Aj.delegate` creation/validation.
- **Authoritative persisted record:** `delegations.jsonl` request/evidence (or rejection evidence/error).
- **Expected:** Missing => required true + `classification_source=default_required`; non-bool => validation rejection; legacy read-time default without persisted rewrite.
- **Forbidden:** Silent optional default; accepting malformed classification.
- **Stage:** S1. **Covering test:** `test_a6_t04...` (xfail). **Untestable now:** legacy compatibility behavior until implemented.

## T-05 — Cancel vs completion/dispatch/recovery/prep; late outcome
- **Setup:** Races and sequences: cancel concurrent with child completion/dispatch/recovery/prep; late child outcome after cancel; resurrection attempts.
- **Invocation:** Interleaved operations (controlled harness).
- **Authoritative persisted record:** Task/assignment/delegation/scheduler/lease evidence timeline.
- **Expected:** No invalid overwrite/success/resurrection; outcomes traceable or unresolved.
- **Forbidden:** Prohibited prep/dispatch, silent success, resurrection.
- **Stage:** S3/S4. **Covering test:** A2/A3/A4 (xfail, partial). **Untestable now:** deterministic race/late-outcome proofs need seams.

## T-06 — Reconciliation idempotency/bounds/contradictions
- **Setup:** Repeated reconcile, dry-run, apply, batch bounds, contradictory/stale/duplicate concurrent actions.
- **Invocation:** `reconcile_delegation_parent` variants and concurrent calls.
- **Authoritative persisted record:** Delegation reconciliation history/evidence, record snapshots.
- **Expected:** Idempotent/no-op on unchanged; no mutation in dry-run; bounded; fail-closed on contradictions.
- **Forbidden:** Duplicate logical outcomes, mutation in dry-run, unbounded work, silent corruption.
- **Stage:** S3/S4. **Covering test:** existing reconciliation tests partial. **Untestable now:** stale-writer/concurrent proofs limited.

## T-07 — Restart/persistence-boundary recovery
- **Setup:** Declared supported interruption boundaries (derived, CRASH_FEASIBILITY) and ambiguous cases.
- **Invocation:** Simulated interruption/restart (seam or boundary-specific harness) then recovery.
- **Authoritative persisted record:** Durable pre/post store states and recovery outcomes.
- **Expected:** Recover or explicit unresolved/manual-review; never silent success/duplication.
- **Forbidden:** Fabricated success, duplication.
- **Stage:** S4. **Covering test:** A1/A1b (xfail). **Untestable now:** most boundaries need S4 seams; original A–H unrecovered.

## T-08 — Controlled concurrency/races
- **Setup:** Completion-vs-cancel, recovery-vs-dispatch, stale writer, duplicate apply (single-process declared boundary).
- **Invocation:** Controlled concurrent harness.
- **Authoritative persisted record:** Consistent authoritative records/snapshots/logs.
- **Expected:** No contradictory authoritative outcome/silent overwrite.
- **Forbidden:** Multi-process/distributed claims; silent corruption.
- **Stage:** S4. **Covering test:** limited existing. **Untestable now:** many races/seams unavailable.

## T-09 — Anomaly detection (supported classes)
- **Setup:** Each supported anomaly class present vs healthy state.
- **Invocation:** Monitor/detection APIs.
- **Authoritative persisted record:** Findings with ids/evidence; authoritative stores unchanged.
- **Expected:** Detected/surfaced accurately; read-only.
- **Forbidden:** Mutation, false healthy presentation.
- **Stage:** S3. **Covering test:** existing partial. **Untestable now:** full certified class coverage.

## T-10 — Evidence/traceability for decisions and failures
- **Setup:** Key decisions and rejections/ambiguities across supported paths.
- **Invocation:** Execute paths.
- **Authoritative persisted record:** Correlated task/execution/delegation/assignment/receipt/journal/audit records.
- **Expected:** Traceable evidence; uncertainty surfaced; no fabricated success.
- **Forbidden:** Missing evidence treated as success, cross-store atomicity claims.
- **Stage:** S1–S4. **Covering test:** partial. **Untestable now:** exhaustive coverage.

## T-11 — Unsupported capability/claim attempts
- **Setup:** Unsupported claims/capabilities: remote agent transport, exactly-once external effects, cross-store atomicity, authenticated identity, Hermes attachment, distributed correctness.
- **Invocation:** Submit via delegation/other relevant surfaces.
- **Authoritative persisted record:** Rejection/error or explicit UNSUPPORTED response/evidence; no created capability effect.
- **Expected:** Rejected/blocked or explicitly reported **UNSUPPORTED**.
- **Forbidden:** Silent acceptance or false capability.
- **Stage:** S1/S2. **Covering test:** `test_a7_t11_unsupported_capability_claim_rejected` (xfail; attempts remote agent transport claim). **Untestable now:** all surfaces not enumerated.

## T-12 — SQLite/WAL investigation/disposition
- **Setup:** Path/FS variants and concurrency/init modes per matrix; targeted concurrent memory writer test with controlled env.
- **Invocation:** `sqlite_wal_experiment.py` matrix; repeated `test_concurrent_memory_writers_keep_every_event` (E6 runs).
- **Authoritative persisted record:** `sqlite_wal_matrix_results.json`, `sqlite_wal_matrix_summary.txt`, `E6_ntfs_default_tmpdir.json`, `E6_ntfs_tmpdir_tmp.json`, suite logs.
- **Expected:** Facts recorded; hypotheses labelled; no false stability claim.
- **Forbidden:** Fix in S0, weakening tests, claiming resolved without disposition.
- **Stage:** S5 (experiments/disposition), constrains certification. **Covering test:** N/A (investigation). **Untestable now:** definitive root-cause attribution not complete (**OPEN**).


===== CRASH_FEASIBILITY.md (ENGINEERING_AUDIT/S0_CLOSURE/CRASH_FEASIBILITY.md) =====
# CRASH_FEASIBILITY (S0 E5)

## Scope and honesty
- **Original A–H crash/interruption list:** **UNRECOVERED / not present as a closed, authoritative list in accessible S0 artifacts reviewed this round.** This document does **not** invent that list. Candidate boundaries below are derived from **actual persistence/write ordering observed in current code** (read-only inspection).
- Classification per boundary: **testable now / needs a fault-injection seam in S4 / NOT VERIFIABLE / UNSUPPORTED** (with reason). No seams invented.
- Single-process, local stores, non-atomic multi-store behavior assumed per current architecture; cross-store atomicity/exactly-once external effects remain out of scope.

## Observed persistence/write-order facts (code-derived)
- **Task store (`aj/task.py:TaskStore`)**: append-only JSONL (`tasks.jsonl`) written under store `_lock` then file lock; `_persist_locked` writes line, flushes; on append failure attempts reconciliation/reload and raises `StorageError` (fail-closed). `save/transition/cancel/mutate/create/import` persist via `_persist_locked`; `after_transition` callback fires after durable persist+snapshot.
- **Aj orchestration (`aj/orchestrator.py`)**: wraps `tasks.transition` with `_before_task_transition` (pre-check) then original transition (which persists) then `_on_task_transition` (post-persist hook). Many flows do: state transitions (each persisted) + `tasks.save`/audit/journal/receipts in varying orders depending on path; journal append (`self.journal.append`) and audit/receipt operations are separate stores/calls (non-atomic across stores). Delegation child creation includes direct canonical mutation under `tasks._lock` and `_persist_locked(..., "delegated_child_created")` in delegate flow.
- **Scheduler dispatch (`aj/scheduler.py:_dispatch_one`)**: durable mode records `dispatch_intent` (required) -> acquires lease -> recheck -> may record deadline/abort -> records `dispatch_started` (required in durable mode) -> calls `aj.resume(...)` -> records `dispatch_result`/error (best-effort in some paths) -> releases lease in finally. Intent/result evidence via `DispatchLedger` append-only file (separate from task store).
- **Leases (`aj/lease.py`)**: file-backed JSON state + lock/journal interactions (append-only style operations observed); acquire/release/heartbeat are separate persisted steps.
- **Delegation/assignment stores (`aj/delegation.py`)**: append-only JSONL stores (`AppendOnlyJsonlStore`) with file locks; delegation/assignment/agent records appended/saved independently.
- **Journal/receipts/execution stores**: separate append-only/file stores referenced in orchestrator/scheduler (e.g. `journal.append`, receipts, `ExecutionStore` create/save). No cross-store transaction.

## Boundary candidates (derived from real write order)

| ID | Boundary candidate (derived) | Persistence/write sequence observed | Failure/crash window (if interrupted) | Classification | Rationale / notes |
|---|---|---|---|---|---|
| B1 | Task transition persisted vs post-transition side effects | `tasks.transition` -> `_persist_locked(task jsonl)` durable; then `after_transition`/`_on_task_transition` hook and later orchestration steps (journal/audit/receipts/memory/execution records/reconcile) may run separately | Task state/event advanced durably but downstream evidence/reconciliation/side records missing or partial | **needs a fault-injection seam in S4** (for deterministic interruption proof); partially observable today only via ad-hoc interruption, not certified | Multi-store, non-atomic. Some hooks best-effort. |
| B2 | Dispatch intent recorded vs lease/dispatch start/result | Scheduler: `dispatch_intent` ledger append (durable mode) -> `leases.acquire` -> recheck -> `dispatch_started` append -> `aj.resume` -> `dispatch_result`/error append -> `lease.release` | Intent without lease/start, or lease/start without result, or result without release evidence (depending on point) | **needs a fault-injection seam in S4** | Observed ordering explicit in `_dispatch_one`; recovery/inspection must treat ambiguity honestly. |
| B3 | Task state change vs execution/attempt/receipt/journal records | Orchestrator execution/resume paths interleave task transitions, execution store updates, journal events, receipts, audit; orders vary by path | Inconsistent views across task/execution/receipt/journal stores | **needs a fault-injection seam in S4** | Cross-store non-atomic; existing recovery attempts to assess conservatively but boundaries not deterministically proven. |
| B4 | Delegation/child creation multi-record writes | `delegate`: creates/persists delegation intent, creates child task(s) (persist), mutates/persists delegated child context/lineage, creates assignments, saves delegation status, may append journal, triggers reconciliation (which may save delegation evidence) — multiple stores/steps | Partial delegation/child/assignment/provenance with orphaned or inconsistent linkage | **needs a fault-injection seam in S4** (and/or targeted harness); **NOT VERIFIABLE** as complete set without seams | Append-only stores but no atomicity; failure handling records recovery/failed status in some cases, completeness unproven. |
| B5 | Reconciliation read/compute vs delegation evidence persistence | `_reconcile_delegation_parent`: computes aggregation/snapshots, may prepare children (mutating task states) in apply mode, then appends/saves delegation evidence/history | Apply side effects without final evidence, or stale/partial evidence markers | **needs a fault-injection seam in S4** | Idempotency/hash logic exists; interruption behavior not deterministically proven. |
| B6 | Persistence append failure during task mutation | `_persist_locked` failure path: attempts reload/reconcile in-memory to last durable state or removes; raises `StorageError` | In-memory vs durable divergence window minimized by in-lock handling, but callers/upper layers may observe error after partial external effects in composite operations | **testable now** for single-store append-failure behavior via existing failure-injection hooks/tests patterns (limited) / **needs seam in S4** for composite multi-store flows | Single-store fail-closed behavior partially evidenced; composite guarantees **NOT VERIFIABLE** without seams. |
| B7 | SQLite memory store init/WAL pragma/commit (canonical memory) | `MemoryStore.__init__`: connect -> `PRAGMA journal_mode=WAL` -> `PRAGMA busy_timeout=30000` -> executescript schema -> commit (single DB) | Init/open/pragma failure leaves DB unavailable or partially initialized; concurrent init sensitive (see E6) | **testable now** for observed error modes (experiments run) but **NOT VERIFIABLE** as fully reliable across all target env/fs/concurrency without disposition/fix; crash-during-commit specifics **needs seam** | Storage-specific; OPEN (T-12). |
| B8 | Lease acquire/renew/release vs task/dispatch state | Lease operations persisted separately; scheduler/orchestrator coordinate but not atomically | Lease held without corresponding dispatch/result state, or expired/uncertain lease vs task state | **needs a fault-injection seam in S4** | Observed in code; detectors/read models surface some anomalies but recovery correctness not fully proven. |

## Unsupported / not verifiable (explicit)
- **OS crash, power loss, filesystem/journal failure, disk corruption, partial sector writes:** **NOT VERIFIABLE** in S0 (no controlled fault environment/seams). **UNSUPPORTED** to claim safety without demonstrated evidence.
- **Cross-store atomic recovery guarantees:** **UNSUPPORTED** (architecture is multi-store, append-only, non-atomic).
- **Exactly-once external side effects / duplicate external delivery after interruption:** **UNSUPPORTED**.
- **Multi-process/multi-host recovery correctness:** **NOT VERIFIABLE / UNSUPPORTED** within current declared scope.
- **Original A–H mapping:** **UNRECOVERED**; cannot certify coverage of that specific list.

## S4 seam needs (no seams invented)
Deterministic proof for B1–B5, B8 and composite aspects of B6/B7 requires fault-injection seams at controlled points (e.g. after intent persist before lease acquire, after task persist before downstream record, before/after delegation record appends) — **to be designed/authorized in S4 only if feasible**. S0 provides boundary identification and classification only.


===== SQLITE_DISPOSITION.md (ENGINEERING_AUDIT/S0_CLOSURE/SQLITE_DISPOSITION.md) =====
# SQLITE_DISPOSITION (S0 E6, read-only investigation)

## 1) Facts (observed)

### `aj/memory.py` (lines 95–130, verbatim context recorded)
- `sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)` then `row_factory` set.
- Under `_lock`: executes `PRAGMA journal_mode=WAL` (line 116), then `PRAGMA busy_timeout=30000` (117), then `executescript(_SCHEMA)` (118), then `commit()`.
- **Order:** Python `sqlite3.connect(..., timeout=30.0)` is set at connection creation; **`PRAGMA journal_mode=WAL` is executed before `PRAGMA busy_timeout=30000`** is set in this sequence (busy_timeout PRAGMA comes after WAL pragma). No read-first/check of existing journal_mode before setting WAL; no retry/backoff on locked/disk I/O.

### Environment
- `env | grep -i tmp` (this session): `TMPDIR=/home/abubakargcx/easy-diffusion/tmp` (also other tmp-related vars present, e.g. GNOME_SETUP_DISPLAY path). `TMPDIR` was set in environment.

### Prior controlled matrix (round 2, `sqlite_wal_matrix_results.json`/summary, `sqlite3 3.46.1`)
- Path types: `/tmp` tempdir on tmpfs, ext4 under `~` (`/dev/sda2`), `/dev/shm` tmpfs, NTFS workspace (`/dev/sda4 ntfs3`). Variants: fork×4 no-precreate, fork×4 precreate WAL in parent, 1 process, spawn×4; 20 runs/cell.
- **Single-process (`v3`)**: 20/20 pass on all path types.
- **NTFS workspace (concurrent)**: v1 9/20, v2 17/20, v4 15/20. First failures sampled: `sqlite3.OperationalError: disk I/O error` at `aj/memory.py:116` (`PRAGMA journal_mode=WAL`), journal_mode readback `wal`, integrity `ok` in sampled record.
- **tmpfs/dev_shm (concurrent, some variants):** intermittent `database is locked` at/around WAL init in sampled failures.
- **Real AJ memory config:** `core.memory_path=""`, `core.data_dir="/home/abubakargcx/.local/share/aj"` on ext4 home (not NTFS workspace).

### E6 targeted runs (this round, no edits) — `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`, 10 runs each
| Condition | Pass | Fail | Evidence |
|---|---:|---:|---|
| Default env TMPDIR (`/home/abubakargcx/easy-diffusion/tmp` in shell env) | 8 | 2 | `E6_ntfs_default_tmpdir.json` (failures at runs 4,6; rc=1) |
| `TMPDIR=/tmp` | 10 | 0 | `E6_ntfs_tmpdir_tmp.json` |

**Caveat (fact):** pytest `tmp_path` location is controlled by pytest basetemp/config and may differ from `TMPDIR`; these results are recorded as-run under the specified env vars without asserting tmp_path filesystem equivalence. Earlier full-suite failures showed NTFS workspace basetemp paths (`/run/media/.../easy-diffusion/tmp/pytest-of-*`) producing `disk I/O error` at `memory.py:116`.

### Full-suite observations (this environment)
- Baseline context: 577 passed / 13 warnings (intermittent history for the concurrent memory writer test noted).
- Round 3 before D-001 (clean snapshot): 576 passed, 1 failed (`test_concurrent_memory_writers_keep_every_event`, `disk I/O error` at `memory.py:116`, NTFS tmp), 13 warnings.
- Round 3 after D-001 (existing tests): 577 passed, 13 warnings (same test passed in that run).

## 2) Labelled hypotheses (not proven)
- **H1 (storage/FS sensitivity):** NTFS `ntfs3` + SQLite WAL/shared-memory/locking semantics under multi-process concurrent init/writes is a likely contributor to `disk I/O error` seen at WAL pragma/init on workspace paths. **Hypothesis, not attributed to AJ logic defect.**
- **H2 (init ordering/contention):** `PRAGMA journal_mode=WAL` executes before `PRAGMA busy_timeout=30000` is set (connect timeout exists but busy handler/timeout PRAGMA ordering differs), which may increase sensitivity to lock contention at WAL setup under concurrency. **Hypothesis.**
- **H3 (TMPDIR/tmp location correlation):** improved pass rate with `TMPDIR=/tmp` in targeted runs may correlate with different temp placement or reduced contention; because pytest tmp_path/basetemp behavior not proven identical to `TMPDIR`, causality is **unproven**.
- **H4 (fork/multi-process semantics):** concurrent forked access patterns can interact with sqlite connections/file locks differently across filesystems; pre-creating WAL reduced but did not eliminate NTFS failures in matrix (sample). **Hypothesis.**

## 3) Planned S5 experiments (no fix in S0)
- **Read-before-set WAL:** check current `journal_mode` first; set `PRAGMA journal_mode=WAL` only if not already `wal` (idempotent/reduced contention on reopen).
- **Ordering/hardening:** ensure effective busy timeout/handler is in place for initialization path as appropriate (evaluate `connect timeout`, `busy_timeout` PRAGMA timing, and `sqlite3_busy_timeout` API) — **design only, not implemented**.
- **Retry with backoff:** bounded retry on transient `database is locked` / `disk I/O error` during WAL init/open with jittered backoff and explicit failure classification; must not mask persistent corruption or broaden claims.
- **Controlled reruns:** repeat matrix on NTFS, ext4, tmpfs with/without precreated WAL, fork vs spawn, and with pytest basetemp pinned per filesystem to remove TMPDIR ambiguity; capture first-failure traceback, errno where available, and journal_mode.
- **Disposition goal:** evidence-backed attribution or explicit bounded limitation (e.g. NTFS workspace not a supported path for concurrent WAL-backed memory store) — to be decided in S5 with proof.

## 4) Disposition (S0)
**OPEN (T-12 / Doc 54 §16).** Facts recorded; hypotheses labelled; no `aj/memory.py` changes made. Not sufficient to claim product defect fix or universal reliability; real AJ default data dir observed on ext4 home.


===== E1–E6 table (from S0_CLOSURE_REPORT.md) =====
| Item | Status | Evidence file(s) | Notes |
|---|---|---|---|
| E1 Characterization (A1–A8 xfail gaps, B1–B5 controls after D-001) | PASS (evidence produced) | `tests/s0_proof/test_s0_characterization.py`, `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_BEFORE_FIX.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_AFTER_FIX.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/_step4_new_tests.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/_runxfail_*`, `ENGINEERING_AUDIT/S0_CLOSURE/_full_suite_round3_final.txt` | Final characterization in suite: **11 xfailed** (A1,A1b,A2a,A2b,A2c,A3,A4,A5,A6,A7,A8) expose gaps; **B1–B5 pass** as controls (B3/B5 validate real aggregation guard post D-001). No unexpected XPASS. |
| E2 Callable inventory (AST + grep, dispositions) | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph.py`, `ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph_results.json`, `ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph_results.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/CALLABLE_INVENTORY_S0.md` (v2) | 146 AST call-site entries in `aj/*.py` with dispositions (GUARDED/S2-FIX/BLOCK-PER-D4/UNSUPPORTED/NOT VERIFIABLE). **Not exhaustive**; AST cannot see dynamic dispatch/runtime indirection/callbacks/non-Python/CLI subprocess/UI coupling/tests beyond grep. |
| E3 Proof specs INV-01..10 / T-01..12 | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/PROOF_SPECS.md` | Setup/invocation/authoritative persisted record/expected/forbidden/stage/covering test specified; untestable-now/NOT VERIFIABLE items marked explicitly. No implementation in S0. |
| E4 Policy decisions & D-001/STEP 3 analysis artifacts | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/58_POLICY_DECISIONS.md`, `ENGINEERING_AUDIT/S0_CLOSURE/STEP3_CHANGE_TABLE.md`, `ENGINEERING_AUDIT/S0_CLOSURE/D001_CONFLICT_MESSAGES_AFTER_FIX.json` | Doc 58 D1–D5 captured + D3 refinement (legal ABANDONED sources FAILED/DEAD_LETTER/RECOVERY_REQUIRED/ESCALATED; refuse others; abandon must validate source and not rely on force once legal). D-001 defect fixed and evidenced; wrong-reason Conflict audit documented. |
| E5 Crash feasibility (derived boundaries, A–H unrecovered) | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/CRASH_FEASIBILITY.md` | Original A–H list **UNRECOVERED** (not invented). Boundaries B1–B8 derived from real persistence/write ordering; classified testable-now/needs S4 seam/NOT VERIFIABLE/UNSUPPORTED. No seams invented. |
| E6 SQLite/WAL disposition (facts/hypotheses, targeted runs) | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/SQLITE_DISPOSITION.md`, `ENGINEERING_AUDIT/S0_CLOSURE/sqlite_wal_matrix_results.json`, `ENGINEERING_AUDIT/S0_CLOSURE/sqlite_wal_matrix_summary.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/E6_ntfs_default_tmpdir.json`, `ENGINEERING_AUDIT/S0_CLOSURE/E6_ntfs_tmpdir_tmp.json` | Facts: `memory.py` connect timeout 30 then `PRAGMA journal_mode=WAL` then `busy_timeout=30000` (no read-first/retry). Default env TMPDIR `/home/abubakargcx/easy-diffusion/tmp`. E6 concurrent writer 10x default: 8 pass/2 fail; 10x `TMPDIR=/tmp`: 10 pass/0 fail (pytest tmp_path FS equivalence not proven). Disposition **OPEN**. |
