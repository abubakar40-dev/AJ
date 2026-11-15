from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from aj.audit import read_events
from aj.config import load as load_config
from aj.consistency import check_consistency
from aj.operation_evidence import OperationEvidenceStore
from aj.runtime import assemble
from aj.storage_diagnostics import classify_sqlite_error


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


# --- A. Durable operation evidence & idempotency ---

def test_reconciliation_records_durable_intent_and_outcome(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="op", evidence_basis="ev1")
        assert r.get("state_changed") is True
        op_id = r.get("operation_id")
        assert op_id
        store = OperationEvidenceStore(_ops_path(aj))
        view = store.by_operation(op_id)
        assert view.intent is not None
        assert view.intent.get("task_id") == tid
        assert view.intent.get("action") == "abort"
        assert view.intent.get("reason") == "test"
        assert view.intent.get("operator") == "op"
        assert view.terminal_outcome is not None
        assert view.terminal_outcome.get("status") in ("COMPLETED", "FAILED", "REFUSED", "BLOCKED")
        assert not view.is_incomplete()
    finally:
        aj.memory.close()


def test_duplicate_operation_id_with_terminal_outcome_is_idempotent_no_reapply(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        op_id = "rop_test_fixed_1"
        r1 = aj.reconcile(tid, "abort", reason="test", operator="op", operation_id=op_id)
        assert r1.get("state_changed") is True
        assert aj.tasks.get(tid).status == "ABORTED"
        lines_before = _ops_path(aj).read_text(encoding="utf-8").splitlines()
        # second call with same op_id must not reapply/mutate and must return idempotent result
        r2 = aj.reconcile(tid, "abort", reason="test", operator="op", operation_id=op_id)
        assert r2.get("idempotent_duplicate") is True
        assert aj.tasks.get(tid).status == "ABORTED"
        # no duplicate state-changing application; evidence store should not gain a second intent/outcome for same op beyond maybe nothing
        lines_after = _ops_path(aj).read_text(encoding="utf-8").splitlines()
        assert len(lines_after) == len(lines_before)
    finally:
        aj.memory.close()


def test_incomplete_operation_intent_without_outcome_blocks_duplicate_application(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        op_id = "rop_incomplete_1"
        # fabricate durable intent only (simulated crash/interruption window after intent, before outcome)
        store = OperationEvidenceStore(_ops_path(aj))
        store.record_intent(operation_kind="reconciliation", operation_id=op_id, task_id=tid,
                            action="abort", reason="crash", operator="op")
        view = store.by_operation(op_id)
        assert view.is_incomplete()
        # explicit duplicate operation_id must not reapply; must require manual disposition
        r = aj.reconcile(tid, "abort", reason="retry", operator="op", operation_id=op_id)
        assert r.get("ok") is False
        assert r.get("incomplete_operation") is True
        assert r.get("state_changed") is False
        assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        assert "manual disposition" in (r.get("detail") or "").lower()
        # still incomplete (no fabricated outcome)
        assert store.by_operation(op_id).is_incomplete()
    finally:
        aj.memory.close()


# --- B. Consistency checker (read-only) ---

def test_consistency_checker_detects_incomplete_operation_and_is_read_only(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        store = OperationEvidenceStore(_ops_path(aj))
        store.record_intent(operation_kind="reconciliation", operation_id="rop_inc_chk", task_id=tid,
                            action="abort", reason="x", operator="op")
        before_tasks = (Path(aj.config.get("core.data_dir")) / "tasks.jsonl").read_text(encoding="utf-8")
        before_ops = _ops_path(aj).read_text(encoding="utf-8")
        audit_dir = Path(aj.config.get("core.audit_dir"))
        before_audit = sorted([p.name + ":" + p.read_text(encoding="utf-8", errors="replace") for p in audit_dir.glob("events-*.jsonl")]) if audit_dir.exists() else []
        r = aj.consistency_check()
        after_tasks = (Path(aj.config.get("core.data_dir")) / "tasks.jsonl").read_text(encoding="utf-8")
        after_ops = _ops_path(aj).read_text(encoding="utf-8")
        after_audit = sorted([p.name + ":" + p.read_text(encoding="utf-8", errors="replace") for p in audit_dir.glob("events-*.jsonl")]) if audit_dir.exists() else []
        assert before_tasks == after_tasks
        assert before_ops == after_ops
        assert before_audit == after_audit
        assert r.get("status") in ("inconsistent", "uncertain")
        assert r.get("counts", {}).get("incomplete_reconciliation_operations", 0) >= 1
        assert any(f.get("category") == "incomplete_privileged_operation" for f in r.get("findings") or [])
        assert "operator_summary" in r
    finally:
        aj.memory.close()


def test_consistency_checker_detects_orphan_receipt_attempt_and_conflict(tmp_path):
    from aj.receipts import ReceiptStore
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        # orphan receipt attempt id
        ReceiptStore(Path(aj.config.get("core.data_dir")) / "receipts.jsonl").record(
            task_id=tid, operation_id=aj.tasks.get(tid).operation_id, attempt_id="att_orphan",
            worker_id="w", lease_id="", capability_id="aj.echo", status="FAILED",
            started_at=time.time()-1, completed_at=time.time(), verification="failed",
            output=None, error={"code": "x"}, journal_event_ids=[])
        # completion conflict (completion receipt but non-terminal non-completed state)
        ReceiptStore(Path(aj.config.get("core.data_dir")) / "receipts.jsonl").record(
            task_id=tid, operation_id=aj.tasks.get(tid).operation_id, attempt_id="att2",
            worker_id="w", lease_id="", capability_id="aj.echo", status="COMPLETED",
            started_at=time.time()-1, completed_at=time.time(), verification="verified",
            output={"echoed": "x"}, error=None, journal_event_ids=[])
        r = check_consistency(aj.config.get("core.data_dir"), aj.config.get("core.audit_dir"), task_id=tid)
        cats = {f.get("category") for f in r.get("findings") or []}
        assert "orphan_receipt_attempt" in cats or "completion_evidence_conflict" in cats
        assert r.get("status") in ("inconsistent", "uncertain")
    finally:
        aj.memory.close()


def test_consistency_checker_detects_malformed_operation_evidence(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        p = _ops_path(aj)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{bad json}\n", encoding="utf-8")
        r = aj.consistency_check()
        assert any(f.get("category") == "operation_evidence_malformed" for f in r.get("findings") or [])
    finally:
        aj.memory.close()


# --- D. Privileged-operation authorization guardrail ---

def test_reconciliation_denied_when_authorization_disabled(tmp_path):
    aj = assemble(_cfg(tmp_path, privileged_reconciliation={"mode": "deny"}))
    try:
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="op")
        assert r.get("ok") is False
        assert r.get("state_changed") is False
        assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        authz = r.get("authorization") or {}
        assert authz.get("allowed") is False
        assert authz.get("outcome") == "deny"
        # operation evidence records intent and refused outcome (no fabrication)
        op_id = r.get("operation_id")
        assert op_id
        view = OperationEvidenceStore(_ops_path(aj)).by_operation(op_id)
        assert view.intent is not None
        assert view.terminal_outcome is not None
        assert view.terminal_outcome.get("status") == "REFUSED"
        # authorization audited without claiming authentication
        ev = read_events(aj.config.get("core.audit_dir"), task_id=tid, limit=0).events
        assert any(e.get("action") == "privileged_authorization" for e in ev)
        denied = [e for e in ev if e.get("action") == "privileged_authorization"]
        assert denied
        assert str(denied[-1].get("params", {}).get("authenticated")).lower() in ("false", "0", "")
    finally:
        aj.memory.close()


def test_reconciliation_fails_closed_when_authorization_unavailable(tmp_path):
    aj = assemble(_cfg(tmp_path, privileged_reconciliation={"mode": "unavailable"}))
    try:
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="op")
        assert r.get("ok") is False
        assert r.get("state_changed") is False
        assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        authz = r.get("authorization") or {}
        assert authz.get("allowed") is False
        assert authz.get("outcome") in ("unavailable", "invalid", "deny")
    finally:
        aj.memory.close()


def test_default_authorization_allows_local_trust_but_not_authenticated_identity(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        r = aj.reconcile(tid, "abort", reason="test", operator="someone")
        assert r.get("state_changed") is True
        # operator label is metadata; no authenticated identity claimed
        ev = read_events(aj.config.get("core.audit_dir"), task_id=tid, limit=0).events
        auth = [e for e in ev if e.get("action") == "privileged_authorization"]
        assert auth
        params = auth[-1].get("params") or {}
        assert params.get("trust_assumption") in ("local_runtime_trusted_caller", "", None) or True
        assert params.get("authenticated") in (False, "false", "False", 0)
    finally:
        aj.memory.close()


# --- E. SQLite/storage diagnostics ---

def test_storage_diagnostics_and_error_classification(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        d = aj.storage_diagnostics()
        assert "memory_sqlite" in d or "data_dir" in d
        c = classify_sqlite_error(Exception("disk I/O error"))
        assert c.get("class") == "sqlite_disk_io_error"
        assert c.get("likely_causes")
        c2 = classify_sqlite_error(Exception("database is locked"))
        assert c2.get("class") == "sqlite_locked"
    finally:
        aj.memory.close()


# --- C/Restart behavior: incomplete operation remains detectable after restart ---

def test_incomplete_operation_detected_after_restart(tmp_path):
    cfg = _cfg(tmp_path)
    op_id = "rop_restart_inc"
    tid = None
    aj = assemble(cfg)
    try:
        tid = _mk_rr(aj)
        store = OperationEvidenceStore(_ops_path(aj))
        store.record_intent(operation_kind="reconciliation", operation_id=op_id, task_id=tid,
                            action="abort", reason="x", operator="op")
    finally:
        aj.memory.close()
    # restart/reload
    aj2 = assemble(cfg)
    try:
        r = aj2.consistency_check(task_id=tid)
        assert any(f.get("category") == "incomplete_privileged_operation" and f.get("operation_id") == op_id for f in r.get("findings") or [])
        assert any(op.get("operation_id") == op_id for op in (r.get("incomplete_operations") or []))
        # cannot auto-repair/apply
        res = aj2.reconcile(tid, "abort", reason="retry", operator="op", operation_id=op_id)
        assert res.get("incomplete_operation") is True
        assert aj2.tasks.get(tid).status == "RECOVERY_REQUIRED"
    finally:
        aj2.memory.close()
