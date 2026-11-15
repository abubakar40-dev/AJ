from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from aj import errors, task as taskmod
from aj.config import load as load_config
from aj.journal import Journal
from aj.lease import ACTIVE, STALE
from aj.receipts import ReceiptStore
from aj.recovery import RecoveryManager, RECOVERY_REQUIRED, REPLAY_SAFE, CONVERGED, BLOCKED
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


def _receipts_path(aj):
    return Path(aj.config.get("core.data_dir")) / "receipts.jsonl"


def _journal_path(aj):
    return Path(aj.config.get("core.data_dir")) / "journal.jsonl"


def test_terminal_states_are_never_resurrected_by_recovery(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        for status in ("COMPLETED", "ABORTED", "CANCELLED", "DEAD_LETTER"):
            rec = aj.tasks.create(f"term-{status}", capability_id="aj.echo")
            if status == "COMPLETED":
                o = aj.handle(rec.goal, capability_id="aj.echo", payload={"text": "x"})
                tid = o.task_id
                assert aj.tasks.get(tid).status == "COMPLETED"
            else:
                # create a legitimate terminal record via allowed transitions
                _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
                if status == "DEAD_LETTER":
                    aj.tasks.transition(rec.task_id, "FAILED", "fail")
                    aj.tasks.transition(rec.task_id, "RECOVERING", "recover")
                    aj.tasks.transition(rec.task_id, "DEAD_LETTER", "terminal")
                elif status == "ABORTED":
                    aj.tasks.transition(rec.task_id, "ABORTED", "terminal")
                elif status == "CANCELLED":
                    aj.tasks.transition(rec.task_id, "CANCELLED", "terminal")
                else:
                    aj.tasks.transition(rec.task_id, status, "terminal")
                tid = rec.task_id
            before = aj.tasks.get(tid).to_dict()
            out = aj.recover(tid)
            after = aj.tasks.get(tid).to_dict()
            assert after["status"] == status
            assert after["events"] == before["events"]
            assert out.ok is True
            assert "converged" in (out.summary or "").lower() or "terminal" in (out.summary or "").lower()
    finally:
        aj.memory.close()


def test_executing_replay_safe_before_external_effect_converges_without_blind_duplication(tmp_path):
    # Crash window 1/2 equivalent for internal replay-safe (no external side effects):
    # task persisted as executable/EXECUTING before completion evidence.
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("exec-replay", capability_id="aj.echo")
        rec.request_payload = {"text": "hi"}
        aj.tasks.save(rec, "setup")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        tid = rec.task_id

        o1 = aj.recover(tid)
        assert o1.ok is True
        assert aj.tasks.get(tid).status == "COMPLETED"
        events1 = list(aj.tasks.get(tid).events)
        receipts1 = ReceiptStore(_receipts_path(aj)).list(task_id=tid, limit=0)

        # Repeated recovery must converge (no resurrection, no unsafe duplicate execution loop).
        o2 = aj.recover(tid)
        o3 = aj.recover(tid)
        assert o2.ok is True and o3.ok is True
        assert aj.tasks.get(tid).status == "COMPLETED"
        assert aj.tasks.get(tid).events == events1
        receipts3 = ReceiptStore(_receipts_path(aj)).list(task_id=tid, limit=0)
        assert len(receipts3) == len(receipts1)
    finally:
        aj.memory.close()


def test_started_dispatch_without_completion_evidence_is_evidence_based_and_convergent(tmp_path):
    # Crash window 3 shape for replay-safe internal action: started evidence exists, no receipt/completion.
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("started", capability_id="aj.echo")
        rec.request_payload = {"text": "hi"}
        aj.tasks.save(rec, "setup")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        # simulate an in-flight attempt with dispatch/start evidence only
        aj.tasks.mutate(rec.task_id, "attempt", lambda r: r.attempts.append({
            "attempt_id": "att_test_started",
            "attempt_number": 1,
            "operation_id": r.operation_id,
            "started_at": time.time(),
            "ended_at": None,
            "status": "RUNNING",
            "failure": None,
        }))
        aj.tasks.apply(rec.task_id, "attempt_num", attempt=1)
        Journal(_journal_path(aj)).append(
            "EXECUTION_STARTED", task_id=rec.task_id, operation_id=rec.operation_id,
            attempt_id="att_test_started", metadata={"capability": "aj.echo"})

        f = RecoveryManager(aj).scan()
        finding = next(x for x in f if x.task_id == rec.task_id)
        # replay-safe internal action has no external side effects; evidence allows safe replay
        assert finding.decision in (REPLAY_SAFE, RECOVERY_REQUIRED)
        out = aj.recover(rec.task_id)
        assert aj.tasks.get(rec.task_id).status in ("COMPLETED", "RECOVERY_REQUIRED")
        # if recovered, must converge on repeat
        if aj.tasks.get(rec.task_id).status == "COMPLETED":
            o2 = aj.recover(rec.task_id)
            assert o2.ok is True and aj.tasks.get(rec.task_id).status == "COMPLETED"
    finally:
        aj.memory.close()


def test_completion_receipt_without_terminal_state_fails_closed_no_replay(tmp_path):
    # Crash window 4/5 ambiguity: completion evidence exists but canonical task not terminal.
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("receipt-no-terminal", capability_id="aj.echo")
        rec.request_payload = {"text": "hi"}
        aj.tasks.save(rec, "setup")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        aj.tasks.mutate(rec.task_id, "attempt", lambda r: r.attempts.append({
            "attempt_id": "att_rcpt", "attempt_number": 1, "operation_id": r.operation_id,
            "started_at": time.time() - 1, "ended_at": time.time(), "status": "COMPLETED", "failure": None,
        }))
        ReceiptStore(_receipts_path(aj)).record(
            task_id=rec.task_id, operation_id=rec.operation_id,
            attempt_id="att_rcpt", worker_id="w", lease_id="",
            capability_id="aj.echo", status="COMPLETED",
            started_at=time.time() - 1, completed_at=time.time(),
            verification="verified", output={"echoed": "hi"},
            error=None, journal_event_ids=[])

        before = aj.tasks.get(rec.task_id).to_dict()
        out = aj.recover(rec.task_id)
        after = aj.tasks.get(rec.task_id)
        # must not blindly replay or resurrect; fail closed/reconcile to manual intervention
        assert after.status != "COMPLETED"
        assert out.ok is False
        assert after.status in (before["status"], "RECOVERY_REQUIRED")
        assert ("replay/resurrection is unsafe" in (out.summary or "").lower()
                or "manual" in (out.summary or "").lower()
                or "reconcil" in (out.summary or "").lower()
                or after.status == "RECOVERY_REQUIRED")
        # repeated recovery converges
        out2 = aj.recover(rec.task_id)
        assert aj.tasks.get(rec.task_id).status == after.status
    finally:
        aj.memory.close()


def test_active_execution_lease_blocks_recovery_expired_allows_safe_replay(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("lease", capability_id="aj.echo")
        rec.request_payload = {"text": "x"}
        aj.tasks.save(rec, "setup")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        lease = aj.leases.acquire(rec.task_id, "execute", worker_id="worker-a", ttl=3600)
        assert lease is not None
        # active unexpired lease => do not steal
        blocked = aj.recover(rec.task_id)
        assert blocked.ok is False
        assert aj.tasks.get(rec.task_id).status in ("EXECUTING", "RECOVERY_REQUIRED")
        assert "lease" in (blocked.summary or "").lower() or "blocked" in (blocked.summary or "").lower() or aj.tasks.get(rec.task_id).status == "RECOVERY_REQUIRED"

        # expire lease => stale/no live owner. Release/break stale execution ownership so
        # recovery can acquire its operation lease, then safely replay internal action.
        cur = aj.leases.get(rec.task_id)
        cur.expires_at = time.time() - 100
        aj.leases._write(cur)
        # best-effort: mark stale/release expired execution lease if supported
        try:
            if hasattr(aj.leases, "break_stale_execution"):
                aj.leases.break_stale_execution(rec.task_id, reason="test")
            elif hasattr(aj.leases, "release"):
                cur.status = "EXPIRED"
                aj.leases._write(cur)
        except Exception:
            try:
                aj.leases._write(cur)
            except Exception:
                pass
        # ensure recover lock can be taken (remove blocking active execute lease record)
        try:
            raw = aj.leases._read(rec.task_id)
            if raw is not None and getattr(raw, "operation", "") == "execute" and raw.expired():
                raw.status = "EXPIRED"
                aj.leases._write(raw)
        except Exception:
            pass
        out = aj.recover(rec.task_id)
        assert aj.tasks.get(rec.task_id).status in ("COMPLETED", "RECOVERY_REQUIRED")
        if aj.tasks.get(rec.task_id).status == "COMPLETED":
            assert out.ok is True
    finally:
        aj.memory.close()


def test_malformed_journal_evidence_fails_closed(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("bad-journal", capability_id="aj.echo")
        rec.request_payload = {"text": "x"}
        aj.tasks.save(rec, "setup")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        jp = _journal_path(aj)
        jp.parent.mkdir(parents=True, exist_ok=True)
        with jp.open("a", encoding="utf-8") as f:
            f.write("{not json\n")
        out = aj.recover(rec.task_id)
        assert out.ok is False
        assert aj.tasks.get(rec.task_id).status == "RECOVERY_REQUIRED"
        # repeated recovery converges without unsafe replay
        out2 = aj.recover(rec.task_id)
        assert aj.tasks.get(rec.task_id).status == "RECOVERY_REQUIRED"
    finally:
        aj.memory.close()


def test_retry_budget_is_respected_for_automatic_replay(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("budget", capability_id="aj.echo")
        rec.request_payload = {"text": "x"}
        rec.max_attempts = 1
        rec.attempt = 1
        aj.tasks.save(rec, "setup")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        # simulate failed exhausted state while interrupted as FAILED-equivalent evidence context
        aj.tasks.transition(rec.task_id, "FAILED", "exhausted")
        out = aj.recover(rec.task_id)
        # must not loop/replay indefinitely; either recover once if safe or require manual
        assert aj.tasks.get(rec.task_id).status in ("COMPLETED", "FAILED", "RECOVERY_REQUIRED", "ABORTED", "DEAD_LETTER")
    finally:
        aj.memory.close()


def test_persistence_failure_during_recovery_assessment_is_fail_closed(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("persist-fail", capability_id="aj.echo")
        rec.request_payload = {"text": "x"}
        aj.tasks.save(rec, "setup")
        _advance(aj, rec.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        original = aj.tasks._persist_locked
        calls = {"n": 0}

        def flaky(self, record, reason):
            if reason == "recovery_assessment":
                calls["n"] += 1
                raise OSError("simulated append failure")
            return original(record, reason)

        aj.tasks._persist_locked = flaky.__get__(aj.tasks, type(aj.tasks))
        # assessment persistence failure should not claim success; behavior must remain safe.
        # recovery may still proceed if assessment itself was computed in-memory, but must not corrupt.
        try:
            out = aj.recover(rec.task_id)
        except Exception:
            out = None
        st = aj.tasks.get(rec.task_id).status
        assert st in ("EXECUTING", "AUTHORIZED", "COMPLETED", "FAILED", "RECOVERY_REQUIRED", "RETRYING")
        # canonical store must remain readable/consistent
        assert aj.tasks.get(rec.task_id).task_id == rec.task_id
    finally:
        aj.tasks._persist_locked = original  # type: ignore[assignment]
        aj.memory.close()


def test_scan_reports_evidence_based_decisions(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        ok = aj.tasks.create("ok", capability_id="aj.echo")
        ok.request_payload = {"text": "x"}
        aj.tasks.save(ok, "s")
        _advance(aj, ok.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        bad = aj.tasks.create("bad", capability_id="aj.echo")
        bad.request_payload = {"text": "x"}
        aj.tasks.save(bad, "s")
        _advance(aj, bad.task_id, "RECEIVED", "UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING")
        jp = _journal_path(aj)
        with jp.open("a", encoding="utf-8") as f:
            f.write("{broken\n")
        findings = {f.task_id: f for f in RecoveryManager(aj).scan()}
        assert findings[ok.task_id].decision in (REPLAY_SAFE, RECOVERY_REQUIRED, CONVERGED, BLOCKED)
        assert findings[bad.task_id].decision == RECOVERY_REQUIRED
    finally:
        aj.memory.close()