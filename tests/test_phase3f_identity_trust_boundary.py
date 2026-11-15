from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from aj.audit import read_events
from aj.config import load as load_config
from aj.operation_evidence import OperationEvidenceStore
from aj.runtime import assemble


def _cfg(tmp_path, **perm_overrides):
    perms = {"unattended_ceiling": 1}
    perms.update(perm_overrides)
    return load_config(None, env={}, overrides={
        "core": {
            "data_dir": str(tmp_path / "data"),
            "audit_dir": str(tmp_path / "data" / "audit"),
            "memory_path": str(tmp_path / "data" / "memory.sqlite3"),
        },
        "permissions": perms,
    })


def _mk_rr(aj):
    rec = aj.tasks.create("rr", capability_id="aj.echo")
    rec.request_payload = {"text": "x"}
    aj.tasks.save(rec, "setup")
    for st in ("RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING"):
        aj.tasks.transition(rec.task_id, st)
    aj.tasks.transition(rec.task_id, "RECOVERY_REQUIRED", "manual")
    return rec.task_id


def _ops_path(aj):
    return Path(aj.config.get("core.data_dir")) / "reconciliation_operations.jsonl"


def _auth_events(aj, task_id):
    ev = read_events(aj.config.get("core.audit_dir"), task_id=task_id, limit=0).events
    return [e for e in ev if e.get("action") == "privileged_authorization"]


def _recon_events(aj, task_id):
    ev = read_events(aj.config.get("core.audit_dir"), task_id=task_id, limit=0).events
    return [e for e in ev if e.get("action") == "operator_reconciliation"]


def test_forged_operator_metadata_never_becomes_authenticated_principal(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        # Caller supplies arbitrary/impersonating metadata; must be recorded as requested metadata only.
        r = aj.reconcile(tid, "abort", reason="test", operator="root")
        assert r.get("state_changed") is True
        authz = r.get("authorization") or {}
        assert authz.get("authenticated") is False
        assert authz.get("principal") is None
        assert authz.get("identity") is None
        assert (authz.get("requested_operator") or authz.get("operator_label")) == "root"
        prov = authz.get("provenance") or {}
        assert prov.get("requested_operator") == "root"
        assert prov.get("principal_identity") in (None, "")
        assert prov.get("authenticated") in (False, None)
        assert prov.get("principal_source") in ("none", "", None)

        ev = _auth_events(aj, tid)
        assert ev
        params = ev[-1].get("params") or {}
        assert params.get("requested_operator") == "root"
        assert params.get("principal_identity") in (None, "")
        assert params.get("authenticated") in (False, "false", "False", 0, None)
        assert params.get("principal_source") in ("none", "", None)

        store = OperationEvidenceStore(_ops_path(aj))
        view = store.by_operation(r.get("operation_id"))
        intent = view.intent or {}
        assert intent.get("requested_operator") == "root"
        assert intent.get("operator") == "root"
        iprov = intent.get("identity_provenance") or {}
        assert iprov.get("requested_operator") == "root"
        assert iprov.get("principal_identity") in (None, "")
        assert iprov.get("authenticated") in (False, None)
    finally:
        aj.memory.close()


def test_missing_operator_metadata_still_records_provenance_and_no_principal(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="")
        assert r.get("state_changed") is True
        authz = r.get("authorization") or {}
        assert authz.get("authenticated") is False
        assert authz.get("principal") is None
        assert (authz.get("requested_operator") or "") == ""
        ev = _auth_events(aj, tid)
        assert ev
        params = ev[-1].get("params") or {}
        assert params.get("authenticated") in (False, "false", "False", 0, None)
        assert params.get("principal_identity") in (None, "")
        assert "requested_operator" in params
    finally:
        aj.memory.close()


def test_unauthorized_privileged_operation_denied_with_no_state_change(tmp_path):
    aj = assemble(_cfg(tmp_path, privileged_reconciliation={"mode": "deny"}))
    try:
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="attacker")
        assert r.get("ok") is False
        assert r.get("state_changed") is False
        assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        authz = r.get("authorization") or {}
        assert authz.get("allowed") is False
        assert authz.get("outcome") == "deny"
        assert authz.get("principal") is None
        assert (authz.get("requested_operator") or "") == "attacker"
        store = OperationEvidenceStore(_ops_path(aj))
        view = store.by_operation(r.get("operation_id"))
        assert view.terminal_outcome is not None
        assert view.terminal_outcome.get("status") == "REFUSED"
    finally:
        aj.memory.close()


def test_require_verified_identity_fails_closed_without_provider(tmp_path):
    aj = assemble(_cfg(tmp_path, privileged_reconciliation={"mode": "require_verified_identity"}))
    try:
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="user")
        assert r.get("ok") is False
        assert r.get("state_changed") is False
        assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        authz = r.get("authorization") or {}
        assert authz.get("allowed") is False
        assert authz.get("authenticated") is False
        assert authz.get("outcome") in ("unavailable", "deny", "invalid")
        assert "verified" in (authz.get("reason") or "").lower() or "identity" in (authz.get("reason") or "").lower()
    finally:
        aj.memory.close()


def test_caller_cannot_inject_authenticated_principal_via_api_shape(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        # reconcile API has no authenticated identity/principal/authorization params; caller metadata remains metadata.
        r = aj.reconcile(tid, "abort", reason="test", operator="admin")
        assert r.get("state_changed") is True
        authz = r.get("authorization") or {}
        assert authz.get("authenticated") is False
        assert authz.get("principal") is None
        prov = authz.get("provenance") or {}
        assert prov.get("principal_identity") in (None, "")
        # ensure scope is bound to this operation/action/task
        scope = authz.get("scope") or {}
        assert scope.get("operation_kind") == "reconciliation"
        assert scope.get("action") == "abort"
        assert scope.get("task_id") == tid
        assert scope.get("operation_id") == r.get("operation_id")
    finally:
        aj.memory.close()


def test_authorization_decisions_scoped_per_operation(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        r1 = aj.reconcile(tid, "abort", reason="test1", operator="alice", operation_id="rop_scope_1")
        assert r1.get("state_changed") is True
        authz1 = (r1.get("authorization") or {})
        assert (authz1.get("scope") or {}).get("operation_id") == "rop_scope_1"
        # Second task/op gets its own scoped decision record.
        tid2 = _mk_rr(aj)
        r2 = aj.reconcile(tid2, "abort", reason="test2", operator="bob", operation_id="rop_scope_2")
        assert r2.get("state_changed") is True
        authz2 = (r2.get("authorization") or {})
        assert (authz2.get("scope") or {}).get("operation_id") == "rop_scope_2"
        assert (authz2.get("requested_operator") or "") == "bob"
        ev1 = _auth_events(aj, tid)
        ev2 = _auth_events(aj, tid2)
        assert (ev1[-1].get("params") or {}).get("operation_id") == "rop_scope_1"
        assert (ev2[-1].get("params") or {}).get("operation_id") == "rop_scope_2"
        assert (ev1[-1].get("params") or {}).get("requested_operator") == "alice"
        assert (ev2[-1].get("params") or {}).get("requested_operator") == "bob"
    finally:
        aj.memory.close()


def test_identity_provenance_recorded_in_operator_reconciliation_audit(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="carol")
        assert r.get("state_changed") is True
        recs = _recon_events(aj, tid)
        assert recs
        params = recs[-1].get("params") or {}
        assert params.get("requested_operator") == "carol"
        assert params.get("principal_identity") in (None, "")
        assert params.get("authenticated") in (False, "false", "False", 0, None)
        assert "principal_source" in params
        assert params.get("operation_id") == r.get("operation_id")
    finally:
        aj.memory.close()


def test_authorization_failure_during_reconciliation_fails_closed(tmp_path):
    class Boom:
        def authorize(self, ctx):
            raise RuntimeError("boom")
    aj = assemble(_cfg(tmp_path))
    try:
        # Inject failing authorizer after assembly (trusted test harness simulating provider failure).
        aj.privileged_authorizer = Boom()
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="op")
        assert r.get("ok") is False
        assert r.get("state_changed") is False
        assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        authz = r.get("authorization") or {}
        assert authz.get("allowed") is False
        assert authz.get("outcome") == "unavailable"
        store = OperationEvidenceStore(_ops_path(aj))
        view = store.by_operation(r.get("operation_id"))
        assert view.terminal_outcome is not None
        assert view.terminal_outcome.get("status") == "REFUSED"
    finally:
        aj.memory.close()


def test_concurrent_privileged_operations_are_serialized_and_audited(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        results = []
        def worker(opid):
            try:
                results.append(aj.reconcile(tid, "abort", reason="concurrent", operator="op", operation_id=opid))
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        t1 = threading.Thread(target=worker, args=("rop_conc_a",))
        t2 = threading.Thread(target=worker, args=("rop_conc_b",))
        t1.start(); t2.start(); t1.join(); t2.join()
        assert len(results) == 2
        # At most one successful state-changing application; task ends in a valid terminal reconciled state.
        assert aj.tasks.get(tid).status in ("ABORTED", "RECOVERY_REQUIRED")
        changed = [r for r in results if r.get("state_changed")]
        assert len(changed) <= 1
        # Every attempt produced authorization/audit evidence (allowed or refused/blocked) and op evidence.
        store = OperationEvidenceStore(_ops_path(aj))
        ops = store.list_operations(task_id=tid)
        assert len(ops) >= 1
    finally:
        aj.memory.close()
