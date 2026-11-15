"""Phase 4B.6 isolated design-evidence tests (AJ-side only).

These tests use fake Hermes executables/results and mock runners to validate
proposed AJ decision/mapping patterns for a future `hermes.gateway.ensure`
capability. They do NOT invoke real `hermes gateway ensure`, do NOT prove native
Hermes behavior/idempotency/concurrency, and do NOT authorize implementation.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


# --- fake runner / verdict mapping helpers (design prototypes, isolated) ---

EXIT_READY = 0
EXIT_INVALID = 2
EXIT_INCOMPATIBLE = 3
EXIT_AUTH = 4
EXIT_DEADLINE = 5
EXIT_DRAINING = 6
EXIT_INACCESSIBLE = 7


def fixed_argv(hermes: str, timeout: int) -> list[str]:
    return [hermes, "gateway", "ensure", "--json", "--timeout", str(int(timeout))]


def aj_outcome_from_ensure(exit_code: int, payload: dict | None, *, process_timed_out: bool = False):
    """Conservative AJ-side mapping prototype (honest/unknown-preserving)."""
    if process_timed_out:
        return {"status": "timeout", "final": "unknown", "manual_review": True, "reason": "aj_subprocess_timeout"}
    p = payload or {}
    state = p.get("state")
    reason = p.get("reason_code")
    if exit_code == EXIT_READY and state == "ready":
        return {"status": "completed", "final": "ready", "manual_review": False, "reason": reason}
    if exit_code == EXIT_INVALID:
        return {"status": "rejected", "final": "rejected", "manual_review": False, "reason": reason or "invalid_invocation"}
    if exit_code in (EXIT_INCOMPATIBLE, EXIT_AUTH):
        return {"status": "failed", "final": state or "failed", "manual_review": True, "reason": reason}
    if exit_code == EXIT_DRAINING:
        return {"status": "failed", "final": state or "draining", "manual_review": True, "reason": reason}
    if exit_code == EXIT_DEADLINE or state == "starting":
        # ambiguous: start may have been requested/effect may continue
        return {"status": "timeout", "final": "unknown", "manual_review": True, "reason": reason or "deadline"}
    if exit_code == EXIT_INACCESSIBLE:
        return {"status": "failed", "final": state or "inaccessible", "manual_review": True, "reason": reason}
    return {"status": "unknown", "final": "unknown", "manual_review": True, "reason": reason or "unmapped"}


def precondition_decision(observed: dict) -> dict:
    """State-gated action decision prototype (fail-closed)."""
    st = observed.get("state")
    if st == "ready":
        return {"action": "attach_read_only", "mutating": False, "allow": True}
    if st == "starting":
        return {"action": "observe_wait", "mutating": False, "allow": True}
    if st in ("stopped", "absent"):
        # lifecycle mutation (start) only with explicit separate authorization in future policy
        return {"action": "ensure_start_candidate", "mutating": True, "allow": False, "requires": "start_permission"}
    if st == "incompatible":
        return {"action": "manual_review_or_replace_permission", "mutating": True, "allow": False, "requires": "replace_permission"}
    if st in ("retiring", "draining"):
        return {"action": "observe_wait", "mutating": False, "allow": True}
    # unavailable, partially started, unknown, read-back unavailable, contradictory
    return {"action": "fail_closed_manual_review", "mutating": False, "allow": False, "manual_review": True}


# --- tests ---

def test_fixed_argv_shape_no_shell():
    argv = fixed_argv("/usr/bin/hermes", 30)
    assert argv == ["/usr/bin/hermes", "gateway", "ensure", "--json", "--timeout", "30"]
    assert " " not in "".join(argv[:3])  # not a shell string; caller must not use shell=True
    assert all(isinstance(a, str) for a in argv)


def test_ready_verdict_maps_to_completed_ready_without_mutation_claim():
    p = {"state": "ready", "reason_code": None, "endpoint": {"api_origin": "http://127.0.0.1:1"}}
    out = aj_outcome_from_ensure(EXIT_READY, p)
    assert out["status"] == "completed" and out["final"] == "ready" and out["manual_review"] is False
    assert precondition_decision({"state": "ready"}) == {"action": "attach_read_only", "mutating": False, "allow": True}


def test_deadline_starting_is_ambiguous_unknown_no_autoretry():
    p = {"state": "starting", "reason_code": "deadline", "endpoint": None}
    out = aj_outcome_from_ensure(EXIT_DEADLINE, p)
    assert out["status"] == "timeout" and out["final"] == "unknown" and out["manual_review"] is True
    # process timeout without payload also ambiguous
    out2 = aj_outcome_from_ensure(124, None, process_timed_out=True)
    assert out2["final"] == "unknown" and out2["manual_review"] is True


def test_inaccessible_incompatible_conflict_require_manual_review():
    for code, payload in [
        (EXIT_INACCESSIBLE, {"state": "inaccessible", "reason_code": "runtime_exited"}),
        (EXIT_INCOMPATIBLE, {"state": "incompatible", "reason_code": "runtime_protocol"}),
        (EXIT_INACCESSIBLE, {"state": "conflict", "reason_code": "service_scope_conflict"}),
    ]:
        out = aj_outcome_from_ensure(code, payload)
        assert out["manual_review"] is True
        assert out["status"] in ("failed", "timeout", "unknown", "rejected")


def test_invalid_invocation_is_rejected_not_executed():
    out = aj_outcome_from_ensure(EXIT_INVALID, {"state": "inaccessible", "reason_code": "invalid_invocation"})
    assert out["status"] == "rejected" and out["manual_review"] is False


def test_state_gating_fails_closed_for_unknown_and_mutating_states():
    for st in ("unavailable", "partially_started", "unknown", "readback_unavailable", "contradictory", None):
        d = precondition_decision({"state": st})
        assert d["allow"] is False
        assert d.get("manual_review", True) is True or d["action"].startswith("fail_closed")
    assert precondition_decision({"state": "stopped"})["mutating"] is True
    assert precondition_decision({"state": "stopped"})["allow"] is False
    assert precondition_decision({"state": "incompatible"})["mutating"] is True


def test_fake_hermes_executable_json_contract_isolated(tmp_path: Path):
    """Isolated fake executable proving AJ can parse bounded JSON; not real Hermes."""
    fake = tmp_path / "fake_hermes.py"
    fake.write_text(
        "import json,sys\n"
        "assert sys.argv[1:4]==['gateway','ensure','--json']\n"
        "print(json.dumps({'state':'ready','reason_code':None,'endpoint':{'api_origin':'http://127.0.0.1:9'}}))\n",
        encoding="utf-8",
    )
    cp = subprocess.run([sys.executable, str(fake), "gateway", "ensure", "--json", "--timeout", "5"],
                        capture_output=True, text=True, timeout=10, check=False)
    assert cp.returncode == 0
    payload = json.loads(cp.stdout.strip())
    out = aj_outcome_from_ensure(cp.returncode, payload)
    assert out["final"] == "ready" and out["manual_review"] is False


def test_duplicate_requests_require_independent_identity_and_policy_not_native_proof():
    # Design assertion: AJ must track per-operation identity; duplicates are AJ policy decisions.
    op_a = {"task_id": "t1", "operation_id": "o1", "attempt_id": "a1", "correlation_id": "c1"}
    op_b = {"task_id": "t1", "operation_id": "o2", "attempt_id": "a1", "correlation_id": "c1"}
    assert op_a["operation_id"] != op_b["operation_id"]
    # Even same request intent cannot assume native Hermes idempotency (evidence absent) -> no auto-retry proof.
    assert aj_outcome_from_ensure(EXIT_DEADLINE, {"state": "starting", "reason_code": "deadline"})["manual_review"] is True


def test_secret_redaction_boundary_design_note():
    # Isolated design check: sensitive tokens must never be placed in argv; payload/log evidence must be redacted.
    secret = "sk-proj-TESTSECRET1234567890"
    argv = fixed_argv("/usr/bin/hermes", 10)
    assert secret not in " ".join(argv)
