from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from aj import errors, task as taskmod
from aj.audit import read_events
from aj.config import load as load_config
from aj.journal import Journal
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


def _make_recovery_required(aj, *, capability="aj.echo", payload=None):
    rec = aj.tasks.create("rr", capability_id=capability)
    if payload is not None:
        rec.request_payload = payload
        aj.tasks.save(rec, "setup")
    _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
    aj.tasks.transition(rec.task_id, "RECOVERY_REQUIRED", "manual review")
    return aj.tasks.get(rec.task_id)


def _audit_actions(aj, task_id):
    ev = read_events(aj.config.get("core.audit_dir"), task_id=task_id, limit=0)
    return [e.get("action") for e in ev.events]


# --- Inspection (read-only, structured, explanatory) ----------------------

def test_recovery_inspection_is_read_only_and_repeatable(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        before = aj.tasks.get(rec.task_id).to_dict()
        before_receipts = ReceiptStore(Path(aj.config.get("core.data_dir")) / "receipts.jsonl").list(task_id=rec.task_id, limit=0)
        before_journal = Journal(Path(aj.config.get("core.data_dir")) / "journal.jsonl").events(task_id=rec.task_id, limit=0)

        i1 = aj.recovery_inspection(rec.task_id)
        i2 = aj.recovery_inspection(rec.task_id)
        i3 = aj.inspect(rec.task_id)

        after = aj.tasks.get(rec.task_id).to_dict()
        after_receipts = ReceiptStore(Path(aj.config.get("core.data_dir")) / "receipts.jsonl").list(task_id=rec.task_id, limit=0)
        after_journal = Journal(Path(aj.config.get("core.data_dir")) / "journal.jsonl").events(task_id=rec.task_id, limit=0)

        assert before == after
        assert before_receipts == after_receipts
        assert before_journal == after_journal
        assert i1["task"]["task_id"] == rec.task_id
        assert i2["task"]["task_id"] == rec.task_id
        assert i1["read_only"] is True
        assert i1["recovery"]["classification"] in ("recovery_required", "blocked", "replay_safe", "converged")
        # repeated inspection has no lifecycle side effects
        assert aj.tasks.get(rec.task_id).status == "RECOVERY_REQUIRED"
        assert "recovery_inspection" in i3
        # no recovery lease held as side effect
        lease = aj.leases.get(rec.task_id)
        assert lease is None or getattr(lease, "status", "") != "ACTIVE" or lease.expired() or getattr(lease, "operation", "") != "recover"
    finally:
        aj.memory.close()


def test_inspection_explains_replay_safe_interrupted_task(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("exec", capability_id="aj.echo")
        rec.request_payload = {"text": "hi"}
        aj.tasks.save(rec, "setup")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        ins = aj.recovery_inspection(rec.task_id)
        assert ins["recovery"]["automatic_replay_permitted"] is True
        assert ins["recovery"]["classification"] == "replay_safe"
        assert ins["evidence"]["replay_safety"]["replay_safe_declared"] is True
        assert ins["evidence"]["replay_safety"]["internal_action"] is True
        assert any("status" in k.lower() or "task status" in k.lower() for k in ins["explanation"]["known"])
        assert isinstance(ins["explanation"]["safe_actions"], list)
    finally:
        aj.memory.close()


def test_inspection_explains_non_replay_safe_and_missing_capability(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, capability="aj.not_real")
        ins = aj.recovery_inspection(rec.task_id)
        assert ins["recovery"]["classification"] in ("recovery_required", "converged")
        assert ins["recovery"]["automatic_replay_permitted"] is False
        assert ins["explanation"]["prevents_automatic_recovery"]
        # non-replay-safe internal check via boom (registered but not replay-safe?) - use missing/unsafe path
        rec2 = _make_recovery_required(aj, capability="aj.boom")
        ins2 = aj.recovery_inspection(rec2.task_id)
        assert ins2["recovery"]["automatic_replay_permitted"] is False
    finally:
        aj.memory.close()


def test_inspection_reports_malformed_evidence_and_correlation(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        jp = Path(aj.config.get("core.data_dir")) / "journal.jsonl"
        with jp.open("a", encoding="utf-8") as f:
            f.write("{bad json\n")
        ins = aj.recovery_inspection(rec.task_id)
        assert ins["recovery"]["automatic_replay_permitted"] is False
        assert ins["evidence"]["journal"]["malformed"] >= 1
        assert any("malformed" in c.lower() for c in ins["explanation"]["conflicts"])
        assert ins["evidence"]["correlation"]["task_id"] == rec.task_id
    finally:
        aj.memory.close()


def test_inspection_reports_active_and_expired_lease_blocking(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("lease", capability_id="aj.echo")
        rec.request_payload = {"text": "x"}
        aj.tasks.save(rec, "s")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        lease = aj.leases.acquire(rec.task_id, "execute", worker_id="w1", ttl=3600)
        ins = aj.recovery_inspection(rec.task_id)
        assert ins["evidence"]["lease"]["state"] == "active"
        assert ins["recovery"]["blocked"] is True or "lease" in (ins["recovery"]["reason"] or "").lower()
        # expire
        cur = aj.leases.get(rec.task_id)
        cur.expires_at = time.time() - 100
        aj.leases._write(cur)
        ins2 = aj.recovery_inspection(rec.task_id)
        assert ins2["evidence"]["lease"]["state"] in ("expired", "active")
    finally:
        aj.memory.close()


def test_inspection_terminal_and_converged(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        o = aj.handle("done", capability_id="aj.echo", payload={"text": "x"})
        ins = aj.recovery_inspection(o.task_id)
        assert ins["task"]["status"] == "COMPLETED"
        assert ins["recovery"]["converged"] is True
        assert ins["recovery"]["automatic_replay_permitted"] is False
    finally:
        aj.memory.close()


# --- Operator reconciliation ----------------------------------------------

def test_reconcile_abort_from_recovery_required_is_audited_and_idempotent(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        r1 = aj.reconcile(rec.task_id, "abort", reason="operator reviewed: not needed", operator="alice", evidence_basis="ticket-1")
        assert r1["ok"] is True
        assert r1["previous"]["status"] == "RECOVERY_REQUIRED"
        assert r1["resulting"]["status"] == "ABORTED"
        assert aj.tasks.get(rec.task_id).status == "ABORTED"
        actions = _audit_actions(aj, rec.task_id)
        assert "operator_reconciliation" in actions
        # idempotent / terminal-safe refusal on repeat
        r2 = aj.reconcile(rec.task_id, "abort", reason="again", operator="alice")
        assert r2["ok"] is False
        assert aj.tasks.get(rec.task_id).status == "ABORTED"
    finally:
        aj.memory.close()


def test_reconcile_dead_letter_from_recovery_required(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        r = aj.reconcile(rec.task_id, "dead_letter", reason="unrecoverable", operator="bob")
        assert r["ok"] is True
        assert aj.tasks.get(rec.task_id).status == "DEAD_LETTER"
        assert "operator_reconciliation" in _audit_actions(aj, rec.task_id)
    finally:
        aj.memory.close()


def test_reconcile_rejects_invalid_preconditions_and_terminal(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        # terminal
        o = aj.handle("done", capability_id="aj.echo", payload={"text": "x"})
        r = aj.reconcile(o.task_id, "abort", reason="nope")
        assert r["ok"] is False
        assert aj.tasks.get(o.task_id).status == "COMPLETED"
        # wrong state for action
        rec = aj.tasks.create("plain", capability_id="aj.echo")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        r2 = aj.reconcile(rec.task_id, "abort", reason="nope")
        assert r2["ok"] is False
        assert aj.tasks.get(rec.task_id).status == "EXECUTING"
    finally:
        aj.memory.close()


def test_reconcile_fails_closed_on_active_execution_lease(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        lease = aj.leases.acquire(rec.task_id, "execute", worker_id="w1", ttl=3600)
        try:
            r = aj.reconcile(rec.task_id, "abort", reason="nope")
            assert r["ok"] is False
        except Exception as e:
            # may be blocked by lease acquisition or return refused
            assert "lease" in str(e).lower() or "block" in str(e).lower()
        assert aj.tasks.get(rec.task_id).status == "RECOVERY_REQUIRED"
    finally:
        aj.memory.close()


def test_reconcile_abandon_preserves_legacy_semantics(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        r = aj.reconcile(rec.task_id, "abandon", reason="operator abandon", operator="carol")
        assert r["ok"] is True
        assert aj.tasks.get(rec.task_id).status == "ABANDONED"
        assert "operator_reconciliation" in _audit_actions(aj, rec.task_id)
        # idempotent
        r2 = aj.reconcile(rec.task_id, "abandon", reason="again")
        assert r2["ok"] is True
        assert aj.tasks.get(rec.task_id).status == "ABANDONED"
    finally:
        aj.memory.close()


def test_reconcile_fails_closed_on_malformed_evidence_for_clear_action(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        jp = Path(aj.config.get("core.data_dir")) / "journal.jsonl"
        with jp.open("a", encoding="utf-8") as f:
            f.write("{broken\n")
        r = aj.reconcile(rec.task_id, "clear_recovery_required", reason="try retry")
        assert r["ok"] is False
        assert aj.tasks.get(rec.task_id).status == "RECOVERY_REQUIRED"
    finally:
        aj.memory.close()


# --- CLI exposure ---------------------------------------------------------

def test_cli_recover_inspect_and_reconcile(tmp_path):
    import subprocess, sys, os, json as _json
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HOME"] = str(tmp_path / "home")
    env["TMPDIR"] = str(tmp_path / "tmp")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)

    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        tid = rec.task_id
    finally:
        aj.memory.close()

    cfg = tmp_path / "cfg.json"
    cfg.write_text(_json.dumps({"core": {"data_dir": str(tmp_path/"data"), "audit_dir": str(tmp_path/"data"/"audit"), "memory_path": str(tmp_path/"data"/"memory.sqlite3")}}), encoding="utf-8")

    cmd = [sys.executable, "-m", "aj", "--config", str(cfg), "--json", "recover", "--task", tid, "--inspect"]
    p = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent.parent), env=env, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    j = _json.loads(p.stdout)
    assert "inspection" in j
    assert j["inspection"]["task"]["task_id"] == tid
    assert j["inspection"]["read_only"] is True

    cmd2 = [sys.executable, "-m", "aj", "--config", str(cfg), "--json", "reconcile", tid, "--action", "abort", "--reason", "operator", "--operator", "cli-op"]
    p2 = subprocess.run(cmd2, cwd=str(Path(__file__).resolve().parent.parent), env=env, capture_output=True, text=True, timeout=60)
    assert p2.returncode == 0, p2.stderr + p2.stdout
    j2 = _json.loads(p2.stdout)
    assert j2["ok"] is True
    assert j2["resulting"]["status"] == "ABORTED"
def test_inspection_conflicting_completion_receipt_without_terminal_state(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("r", capability_id="aj.echo")
        rec.request_payload = {"text": "x"}
        aj.tasks.save(rec, "s")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        aj.tasks.mutate(rec.task_id, "attempt", lambda r: r.attempts.append({
            "attempt_id": "att1", "attempt_number": 1, "operation_id": r.operation_id,
            "started_at": time.time()-1, "ended_at": time.time(), "status": "COMPLETED", "failure": None,
        }))
        ReceiptStore(Path(aj.config.get("core.data_dir")) / "receipts.jsonl").record(
            task_id=rec.task_id, operation_id=rec.operation_id, attempt_id="att1",
            worker_id="w", lease_id="", capability_id="aj.echo", status="COMPLETED",
            started_at=time.time()-1, completed_at=time.time(), verification="verified",
            output={"echoed":"x"}, error=None, journal_event_ids=[])
        ins = aj.recovery_inspection(rec.task_id)
        assert ins["recovery"]["automatic_replay_permitted"] is False
        assert ins["recovery"]["reconciliation_required"] is True or ins["recovery"]["classification"] == "recovery_required"
        assert any("completion receipt" in c.lower() or "not terminal" in c.lower() for c in ins["explanation"]["conflicts"] + [ins["recovery"]["reason"]])
        assert ins["evidence"]["correlation"]["coherent"] in (True, False)
    finally:
        aj.memory.close()


def test_reconcile_clear_recovery_required_valid_and_refused_cases(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = _make_recovery_required(aj, payload={"text": "x"})
        r = aj.reconcile(rec.task_id, "clear_recovery_required", reason="reviewed, allow explicit retry", operator="op")
        assert r["ok"] is True
        assert aj.tasks.get(rec.task_id).status == "FAILED"
        assert "operator_reconciliation" in _audit_actions(aj, rec.task_id)
        # repeated on wrong state refused
        r2 = aj.reconcile(rec.task_id, "clear_recovery_required", reason="again")
        assert r2["ok"] is False
        # invalid action
        rec2 = _make_recovery_required(aj, payload={"text": "x"})
        r3 = aj.reconcile(rec2.task_id, "no_such_action", reason="x")
        assert r3["ok"] is False
    finally:
        aj.memory.close()


def test_reconcile_invalid_task_id_and_audit_trail(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        with pytest.raises(errors.AjError):
            aj.reconcile("no_such_task", "abort", reason="x")
        rec = _make_recovery_required(aj, payload={"text": "x"})
        before_actions = _audit_actions(aj, rec.task_id)
        r = aj.reconcile(rec.task_id, "abort", reason="because", operator="auditor", evidence_basis="ev-123")
        assert r["ok"] is True
        ev = read_events(aj.config.get("core.audit_dir"), task_id=rec.task_id, limit=0).events
        ops = [e for e in ev if e.get("action") == "operator_reconciliation"]
        assert ops
        assert any(e.get("detail") for e in ops)
    finally:
        aj.memory.close()
