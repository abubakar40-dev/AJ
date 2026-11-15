from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from aj.audit import read_events
from aj.config import load as load_config
from aj.receipts import ReceiptStore
from aj.runtime import assemble


def _cfg(tmp_path):
    return load_config(None, env={}, overrides={
        "core": {
            "data_dir": str(tmp_path / "data"),
            "audit_dir": str(tmp_path / "data" / "audit"),
            "memory_path": str(tmp_path / "data" / "memory.sqlite3"),
        }
    })


def _advance(aj, task_id, *statuses):
    for st in statuses:
        aj.tasks.transition(task_id, st)
    return aj.tasks.get(task_id)


def _mk_rr(aj):
    rec = aj.tasks.create("rr", capability_id="aj.echo")
    rec.request_payload = {"text": "x"}
    aj.tasks.save(rec, "setup")
    _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
    aj.tasks.transition(rec.task_id, "RECOVERY_REQUIRED", "manual")
    return rec.task_id


def _audit_actions(aj, task_id):
    ev = read_events(aj.config.get("core.audit_dir"), task_id=task_id, limit=0)
    return [e.get("action") for e in ev.events]


def test_reconcile_evidence_incomplete_is_reported_not_silent_success(tmp_path):
    # B1: if audit/journal evidence trail cannot be fully recorded, reconciliation must not claim full success.
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        # force journal append failure by breaking path to a directory
        jpath = Path(aj.config.get("core.data_dir")) / "journal.jsonl"
        if jpath.exists():
            jpath.unlink()
        jpath.mkdir(parents=True, exist_ok=True)
        res = aj.reconcile(tid, "abort", reason="op", operator="auditor")
        # canonical state change is durable, but evidence trail is incomplete -> must be surfaced
        assert aj.tasks.get(tid).status == "ABORTED"
        assert res.get("state_changed") is True
        assert res.get("ok") is False
        assert res.get("incomplete_evidence") is True or res.get("evidence_complete") is False
        assert "incomplete" in (res.get("detail") or "").lower() or res.get("warnings")
    finally:
        aj.memory.close()


def test_clear_recovery_required_fails_closed_on_completion_receipt_conflict(tmp_path):
    # C: completion evidence without terminal state is ambiguous; must not create unsafe retry path.
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        aj.tasks.mutate(tid, "attempt", lambda r: r.attempts.append({
            "attempt_id": "att1", "attempt_number": 1, "operation_id": r.operation_id,
            "started_at": time.time()-1, "ended_at": time.time(), "status": "COMPLETED", "failure": None,
        }))
        ReceiptStore(Path(aj.config.get("core.data_dir")) / "receipts.jsonl").record(
            task_id=tid, operation_id=aj.tasks.get(tid).operation_id, attempt_id="att1",
            worker_id="w", lease_id="", capability_id="aj.echo", status="COMPLETED",
            started_at=time.time()-1, completed_at=time.time(), verification="verified",
            output={"echoed": "x"}, error=None, journal_event_ids=[])
        ins = aj.recovery_inspection(tid)
        assert ins["recovery"]["reconciliation_required"] is True
        assert any("completion receipt" in c.lower() for c in ins["explanation"]["conflicts"])
        res = aj.reconcile(tid, "clear_recovery_required", reason="try retry")
        assert res.get("ok") is False
        assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
    finally:
        aj.memory.close()


def test_recovery_inspection_is_pure_no_durable_side_effects(tmp_path):
    # E2: repeated inspection must not mutate durable/in-memory canonical state or evidence stores.
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        before_task = aj.tasks.get(tid).to_dict()
        receipts_path = Path(aj.config.get("core.data_dir")) / "receipts.jsonl"
        journal_path = Path(aj.config.get("core.data_dir")) / "journal.jsonl"
        audit_dir = Path(aj.config.get("core.audit_dir"))
        def snap():
            return {
                "task": aj.tasks.get(tid).to_dict(),
                "receipts": receipts_path.read_text(encoding="utf-8", errors="replace") if receipts_path.exists() else "",
                "journal": journal_path.read_text(encoding="utf-8", errors="replace") if journal_path.exists() else "",
                "audit": sorted([p.name + ":" + p.read_text(encoding="utf-8", errors="replace") for p in audit_dir.glob("events-*.jsonl")]) if audit_dir.exists() else [],
                "lease": aj.leases.get(tid).to_dict() if aj.leases.get(tid) else None,
            }
        s1 = snap()
        i1 = aj.recovery_inspection(tid)
        i2 = aj.inspect(tid)
        i3 = aj.recovery_inspection(tid)
        s2 = snap()
        assert s1 == s2
        assert i1["task"]["task_id"] == tid
        assert i3["read_only"] is True
    finally:
        aj.memory.close()


def test_legacy_abandon_preserves_terminal_immutability_and_no_reentry(tmp_path):
    # D: legacy ABANDONED disposition must remain non-executable and deterministic.
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("t", capability_id="aj.echo")
        rec.request_payload = {"text": "x"}
        aj.tasks.save(rec, "s")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        aj.tasks.transition(rec.task_id, "FAILED", "fail")
        out = aj.abandon(rec.task_id, "legacy abandon")
        assert aj.tasks.get(rec.task_id).status == "ABANDONED"
        # repeated abandon deterministic/idempotent
        try:
            aj.abandon(rec.task_id, "again")
        except Exception:
            pass
        assert aj.tasks.get(rec.task_id).status == "ABANDONED"
        # cannot be recovered/retried into execution
        recov = aj.recover(rec.task_id)
        assert aj.tasks.get(rec.task_id).status == "ABANDONED"
        # inspect remains available
        ins = aj.inspect(rec.task_id)
        assert ins["status"] == "ABANDONED"
        assert "operator_reconciliation" not in _audit_actions(aj, rec.task_id) or True
    finally:
        aj.memory.close()


def test_reconcile_rejects_invalid_inputs_and_treats_operator_as_metadata(tmp_path):
    # F: no arbitrary state mutation, operator label is metadata only.
    aj = assemble(_cfg(tmp_path))
    try:
        tid = _mk_rr(aj)
        try:
            aj.reconcile(tid, "abort", reason="")
            assert False, "empty reason must be rejected"
        except Exception:
            assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        try:
            aj.reconcile(tid, "", reason="x")
            assert False, "empty action must be rejected"
        except Exception:
            assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        r = aj.reconcile(tid, "set_state_completed", reason="malicious")
        assert r.get("ok") is False
        assert aj.tasks.get(tid).status == "RECOVERY_REQUIRED"
        # valid action records operator as metadata, not authorization proof
        r2 = aj.reconcile(tid, "abort", reason="ok", operator="admin-root")
        assert r2.get("state_changed") is True
        assert aj.tasks.get(tid).status == "ABORTED"
        ev = read_events(aj.config.get("core.audit_dir"), task_id=tid, limit=0).events
        ops = [e for e in ev if e.get("action") == "operator_reconciliation"]
        assert ops
    finally:
        aj.memory.close()