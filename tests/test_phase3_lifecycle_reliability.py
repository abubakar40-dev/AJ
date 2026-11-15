"""Phase 3 lifecycle and crash-recovery reliability regression tests.

Focused, isolated tests that document verified behavior/guarantees without
modifying real runtime data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aj import errors
from aj.audit import read_events
from aj.capability import AVAILABLE, VERIFIED, CapabilityRegistry, CapabilitySpec
from aj.config import load as load_config
from aj.recovery import RECOVERY_REQUIRED, RecoveryManager
from aj.runtime import assemble
from aj.task import RECEIVED, TaskStore

AJ_ROOT = Path(__file__).resolve().parent.parent


def _cfg(tmp_path: Path, name: str = "data"):
    return load_config(None, env={}, overrides={"core": {
        "data_dir": str(tmp_path / name),
        "audit_dir": str(tmp_path / name / "audit"),
        "memory_path": str(tmp_path / name / "memory.sqlite3"),
    }})


def _subprocess_json(tmp_path, *args, cfg=None, env_extra=None):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HOME"] = str(tmp_path / "home")
    env["TMPDIR"] = str(tmp_path / "tmp")
    env.pop("AJ_INBOX_ROOT", None)
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)
    if env_extra:
        env.update(env_extra)
    cmd = [sys.executable, "-m", "aj"]
    if cfg is not None:
        cfg_path = tmp_path / "sub-config.json"
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        cmd.extend(["--config", str(cfg_path)])
    cmd.extend(args)
    p = subprocess.run(cmd, cwd=str(AJ_ROOT), env=env,
                       capture_output=True, text=True, timeout=60)
    return p


def test_normal_completion_persists_terminal_state_attempt_and_audit(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        o = aj.handle("ok", capability_id="aj.echo", payload={"text": "hi"})
        assert o.ok and o.status == "COMPLETED"
        r = aj.tasks.get(o.task_id)
        assert r.status == "COMPLETED" and r.terminal
        assert r.summary == "aj.echo completed"
        assert len(r.attempts) == 1 and r.attempts[0]["status"] == "COMPLETED"
        assert r.errors == []
        ev = read_events(tmp_path / "data" / "audit", task_id=o.task_id, limit=0).events
        actions = [e["action"] for e in ev]
        assert "task_received" in actions and "authorized" in actions and "executed" in actions
        # restart visibility
        aj.memory.close()
        aj2 = assemble(_cfg(tmp_path))
        try:
            r2 = aj2.tasks.get(o.task_id)
            assert r2.status == "COMPLETED" and r2.summary == "aj.echo completed"
        finally:
            aj2.memory.close()
    finally:
        try:
            aj.memory.close()
        except Exception:
            pass


def test_capability_exception_fails_task_visibly_with_audit(tmp_path):
    from aj.actions import InternalActions, echo
    from aj.agents import AgentRegistry
    from aj.audit import AuditLog, JsonlAuditSink
    from aj.execution import SkillRegistry, UnavailableExecutionAdapter
    from aj.memory import MemoryStore
    from aj.orchestrator import Aj
    from aj.permissions import Authorizer
    from aj.actions import specs as internal_specs

    def boom(args):
        raise RuntimeError("boom")

    reg = CapabilityRegistry(internal_specs())
    reg.register(CapabilitySpec(
        capability_id="aj.boom", name="boom", description="", owner_agent="AJ",
        execution_adapter="internal:boom", risk_level=0, availability=AVAILABLE,
        verification_status=VERIFIED, replay_safe=False,
    ), replace=True)
    aj = Aj(registry=reg, agents=AgentRegistry(), authorizer=Authorizer(),
            audit=AuditLog(JsonlAuditSink(tmp_path / "data" / "audit")),
            tasks=TaskStore(tmp_path / "data"),
            execution=UnavailableExecutionAdapter(), skills=SkillRegistry(),
            config=_cfg(tmp_path), memory=MemoryStore(tmp_path / "data" / "memory.sqlite3"),
            actions=InternalActions({"echo": echo, "boom": boom}))
    try:
        o = aj.handle("boom", capability_id="aj.boom")
        assert not o.ok and o.status == "FAILED"
        r = aj.tasks.get(o.task_id)
        assert r.status == "FAILED" and not r.terminal
        assert r.errors and r.errors[0]["code"] == "execution_failed"
        ev = read_events(tmp_path / "data" / "audit", task_id=o.task_id, limit=0).events
        assert "failed" in [e["action"] for e in ev]
        # persisted failure remains visible after restart
        aj.memory.close()
        aj2 = assemble(_cfg(tmp_path))
        try:
            assert aj2.tasks.get(o.task_id).status == "FAILED"
        finally:
            aj2.memory.close()
    finally:
        try:
            aj.memory.close()
        except Exception:
            pass


def test_interrupted_replay_safe_executing_task_recovers_to_completed(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("exec crash", capability_id="aj.echo")
        rec.request_payload = {"text": "hi"}
        for s in ["UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING"]:
            aj.tasks.transition(rec.task_id, s)
        aj.tasks.save(rec, "exec")
        tid = rec.task_id
        aj.memory.close()
        aj2 = assemble(_cfg(tmp_path))
        try:
            scan = [f.to_dict() for f in RecoveryManager(aj2).scan() if f.task_id == tid]
            assert scan and scan[0]["decision"] == "replay_safe"
            out = RecoveryManager(aj2).recover(tid)
            assert out["outcomes"][0]["ok"] is True
            assert aj2.tasks.get(tid).status == "COMPLETED"
        finally:
            aj2.memory.close()
    finally:
        try:
            aj.memory.close()
        except Exception:
            pass


def test_interrupted_non_replay_safe_executing_task_requires_recovery(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        from aj.capability import CapabilitySpec
        aj.registry.register(CapabilitySpec(
            capability_id="aj.nr", name="nr", description="", owner_agent="AJ",
            execution_adapter="internal:echo", risk_level=0, availability=AVAILABLE,
            verification_status=VERIFIED, replay_safe=False,
        ), replace=True)
        rec = aj.tasks.create("nr exec", capability_id="aj.nr")
        rec.request_payload = {"text": "x"}
        for s in ["UNDERSTANDING", "PLANNED", "AUTHORIZED", "EXECUTING"]:
            aj.tasks.transition(rec.task_id, s)
        aj.tasks.save(rec, "exec")
        tid = rec.task_id
        aj.memory.close()
        aj2 = assemble(_cfg(tmp_path))
        try:
            aj2.registry.register(CapabilitySpec(
                capability_id="aj.nr", name="nr", description="", owner_agent="AJ",
                execution_adapter="internal:echo", risk_level=0, availability=AVAILABLE,
                verification_status=VERIFIED, replay_safe=False,
            ), replace=True)
            scan = [f.to_dict() for f in RecoveryManager(aj2).scan() if f.task_id == tid]
            assert scan and scan[0]["decision"] == RECOVERY_REQUIRED
            out = RecoveryManager(aj2).recover(tid)
            assert out["outcomes"][0]["ok"] is False
            assert out["outcomes"][0]["requires_user_decision"] is True
            assert aj2.tasks.get(tid).status == "RECOVERY_REQUIRED"
        finally:
            aj2.memory.close()
    finally:
        try:
            aj.memory.close()
        except Exception:
            pass


def test_recovery_of_completed_task_converges_idempotently(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        o = aj.handle("done", capability_id="aj.echo", payload={"text": "x"})
        assert aj.tasks.get(o.task_id).status == "COMPLETED"
        # Phase 3C: terminal tasks must never be resurrected/replayed; repeated recovery converges.
        r1 = aj.recover(o.task_id)
        r2 = aj.recover(o.task_id)
        assert r1.ok is True and r1.status == "COMPLETED"
        assert r2.ok is True and r2.status == "COMPLETED"
        assert "converged" in (r1.summary or "").lower() or "terminal" in (r1.summary or "").lower()
        assert aj.tasks.get(o.task_id).status == "COMPLETED"
    finally:
        aj.memory.close()


def test_idempotency_key_same_request_replays_without_duplicate_task(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        o1 = aj.handle("idem", capability_id="aj.echo", payload={"text": "x"}, idempotency_key="k1")
        o2 = aj.handle("idem", capability_id="aj.echo", payload={"text": "x"}, idempotency_key="k1")
        assert o1.ok and o2.ok
        assert o1.task_id == o2.task_id
        assert "idempotent replay" in o2.summary.lower()
        o3 = aj.handle("idem", capability_id="aj.echo", payload={"text": "y"}, idempotency_key="k1")
        assert not o3.ok and "conflict" in o3.summary.lower()
        # no key => distinct tasks (separate requests)
        o4 = aj.handle("n", capability_id="aj.echo", payload={"text": "x"})
        o5 = aj.handle("n", capability_id="aj.echo", payload={"text": "x"})
        assert o4.task_id != o5.task_id
    finally:
        aj.memory.close()


def test_mandatory_audit_failure_aborts_before_execution(tmp_path):
    from aj.actions import default_actions
    from aj.agents import AgentRegistry
    from aj.audit import AuditLog
    from aj.capability import CapabilityRegistry
    from aj.execution import SkillRegistry, UnavailableExecutionAdapter
    from aj.memory import MemoryStore
    from aj.orchestrator import Aj
    from aj.permissions import Authorizer
    from aj.actions import specs as internal_specs

    class BadSink:
        def write(self, event):
            if getattr(event, 'action', '') == 'authorized':
                raise IOError("disk full")

    aj = Aj(registry=CapabilityRegistry(internal_specs()), agents=AgentRegistry(),
            authorizer=Authorizer(), audit=AuditLog(BadSink()),
            tasks=TaskStore(tmp_path / "data"),
            execution=UnavailableExecutionAdapter(), skills=SkillRegistry(),
            config=_cfg(tmp_path), memory=MemoryStore(tmp_path / "data" / "memory.sqlite3"),
            actions=default_actions())
    try:
        o = aj.handle("audit fail", capability_id="aj.echo", payload={"text": "x"})
        assert not o.ok and o.status == "ABORTED"
        assert "audit" in o.summary.lower() or any(e.get("code") == "storage_error" for e in o.errors)
        r = aj.tasks.get(o.task_id)
        assert r.status == "ABORTED"
        # no executed audit event / no successful completion
        assert r.summary == "" or "completed" not in r.summary.lower()
    finally:
        aj.memory.close()


def test_corrupted_task_storage_reports_load_errors_and_remains_operable(tmp_path):
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "tasks.jsonl").write_text(
        '{"reason":"created","task":{"task_id":"t1","goal":"x","status":"RECEIVED","operation_id":"op1"}}\n'
        'NOTJSON\n',
        encoding="utf-8",
    )
    aj = assemble(_cfg(tmp_path))
    try:
        assert len(aj.tasks.all()) == 1
        assert len(aj.tasks.load_errors) == 1
        o = aj.handle("after corrupt", capability_id="aj.echo", payload={"text": "y"})
        assert o.ok and o.status == "COMPLETED"
    finally:
        aj.memory.close()


def test_approval_required_action_waits_and_does_not_execute(tmp_path):
    from aj.actions import default_actions
    from aj.agents import AgentRegistry
    from aj.audit import AuditLog, JsonlAuditSink
    from aj.capability import CapabilityRegistry, CapabilitySpec
    from aj.execution import SkillRegistry, UnavailableExecutionAdapter
    from aj.memory import MemoryStore
    from aj.orchestrator import Aj
    from aj.permissions import ApprovalGate, Authorizer
    from aj.actions import specs as internal_specs

    reg = CapabilityRegistry(internal_specs())
    reg.register(CapabilitySpec(
        capability_id="aj.cons", name="c", description="", owner_agent="AJ",
        execution_adapter="internal:echo", risk_level=3, availability=AVAILABLE,
        verification_status=VERIFIED,
    ), replace=True)
    sink_dir = tmp_path / "data" / "audit"
    aj = Aj(registry=reg, agents=AgentRegistry(),
            authorizer=Authorizer(gate=ApprovalGate()),
            audit=AuditLog(JsonlAuditSink(sink_dir)),
            tasks=TaskStore(tmp_path / "data"),
            execution=UnavailableExecutionAdapter(), skills=SkillRegistry(),
            config=_cfg(tmp_path), memory=MemoryStore(tmp_path / "data" / "memory.sqlite3"),
            actions=default_actions())
    try:
        o = aj.handle("need approval", capability_id="aj.cons", payload={"text": "x"})
        assert not o.ok and o.status == "WAITING_FOR_APPROVAL"
        assert o.requires_user_decision is True
        r = aj.tasks.get(o.task_id)
        assert r.status == "WAITING_FOR_APPROVAL"
        ev = read_events(sink_dir, task_id=o.task_id, limit=0).events
        assert "executed" not in [e["action"] for e in ev]
    finally:
        aj.memory.close()


def test_cli_run_task_recover_and_repeated_recovery_visibility(tmp_path):
    cfg_data = {"core": {
        "data_dir": str(tmp_path / "data"),
        "audit_dir": str(tmp_path / "data" / "audit"),
        "memory_path": str(tmp_path / "data" / "memory.sqlite3"),
    }}
    # normal run
    p = _subprocess_json(tmp_path, "--json", "run", "--capability", "aj.echo", "--text", "hello", cfg=cfg_data)
    assert p.returncode == 0, p.stderr + p.stdout
    j = json.loads(p.stdout)
    assert j["ok"] and j["status"] == "COMPLETED"
    tid = j["task_id"]
    # task visible
    p = _subprocess_json(tmp_path, "--json", "task", tid, cfg=cfg_data)
    assert p.returncode == 0
    assert json.loads(p.stdout)["task"]["status"] == "COMPLETED"
    # recover completed task -> convergent/idempotent no-op (3C: terminal tasks never replayed/resurrected)
    p = _subprocess_json(tmp_path, "--json", "recover", "--task", tid, cfg=cfg_data)
    assert p.returncode == 0, p.stderr + p.stdout
    pj = json.loads(p.stdout)
    outcomes = pj.get("outcomes", [])
    assert outcomes and outcomes[0]["ok"] is True
    assert outcomes[0]["status"] == "COMPLETED"
    assert "converged" in (outcomes[0].get("summary") or "").lower() or "terminal" in (outcomes[0].get("summary") or "").lower()
    # repeated recovery remains convergent
    p2 = _subprocess_json(tmp_path, "--json", "recover", "--task", tid, cfg=cfg_data)
    assert p2.returncode == 0, p2.stderr + p2.stdout
    pj2 = json.loads(p2.stdout)
    assert pj2.get("outcomes", [{}])[0].get("status") == "COMPLETED"
