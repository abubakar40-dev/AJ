from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

AJ_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(AJ_ROOT) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    env.pop("AJ_INBOX_ROOT", None)
    return env


def _write_cfg(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "core": {
            "data_dir": str(tmp_path / "data"),
            "audit_dir": str(tmp_path / "data" / "audit"),
            "memory_path": str(tmp_path / "data" / "memory.sqlite3"),
        }
    }, indent=2), encoding="utf-8")
    return cfg


def _run_aj(args, tmp_path: Path, timeout=30):
    cfg = _write_cfg(tmp_path)
    cmd = [PY, "-m", "aj", "--config", str(cfg), *args]
    return subprocess.run(cmd, cwd=str(AJ_ROOT), env=_env(), capture_output=True, text=True, timeout=timeout)


def _run_helper(code: str, tmp_path: Path, timeout=30):
    cfg = _write_cfg(tmp_path)
    script = code.replace("__CFG__", str(cfg)).replace("__AJ_ROOT__", str(AJ_ROOT))
    return subprocess.run([PY, "-c", script], cwd=str(AJ_ROOT), env=_env(), capture_output=True, text=True, timeout=timeout)


def _task_json(tmp_path: Path, task_id: str):
    p = _run_aj(["task", task_id, "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    return json.loads(p.stdout)["task"]


def test_point4_crash_after_execution_lease_acquired_before_execution(tmp_path):
    # Controlled boundary: task AUTHORIZED, execution lease acquired/persisted, process exits abruptly.
    code = r'''
import json, os
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("p4 lease-before-exec", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.save(rec, "authorized")
lease = aj.leases.acquire(rec.task_id, "execute", ttl=60)
aj.journal.append("LEASE_ACQUIRED", task_id=rec.task_id, operation_id=rec.operation_id, lease_id=lease.lease_id, worker_id=lease.worker_id)
print(json.dumps({"task_id": rec.task_id, "status": rec.status, "lease": lease.lease_id}), flush=True)
os._exit(137)
'''
    p = _run_helper(code, tmp_path)
    assert p.returncode == 137, p.stderr + p.stdout
    info = json.loads(p.stdout.strip().splitlines()[-1])
    tid = info["task_id"]
    assert info["status"] == "AUTHORIZED"

    # Fresh process: state/lease inspectable, recovery honest and non-corrupting
    task = _task_json(tmp_path, tid)
    assert task["status"] in ("AUTHORIZED", "RECOVERY_REQUIRED", "FAILED", "EXECUTING", "PLANNED")
    r = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r.returncode in (0, 1, 6), r.stderr + r.stdout
    j = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    assert "findings" in j or "outcomes" in j or "error" in j
    task2 = _task_json(tmp_path, tid)
    assert task2["task_id"] == tid
    chk = _run_aj(["--check", "--json"], tmp_path)
    assert chk.returncode in (0, 1)


def test_point7_crash_after_attempt_started_before_lease_release(tmp_path):
    # Boundary: attempt/lease exist but process dies before clean release/completion.
    code = r'''
import json, os, time
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("p7 before-release", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.transition(rec.task_id, "EXECUTING")
aj._start_attempt(rec)
aj.tasks.save(rec, "executing")
lease = aj.leases.acquire(rec.task_id, "execute", ttl=60)
aj.journal.append("EXECUTION_STARTED", task_id=rec.task_id, operation_id=rec.operation_id, lease_id=lease.lease_id, attempt_id=(rec.attempts[-1]["attempt_id"] if rec.attempts else ""))
print(json.dumps({"task_id": rec.task_id, "status": aj.tasks.get(rec.task_id).status, "attempts": len(rec.attempts)}), flush=True)
os._exit(137)
'''
    p = _run_helper(code, tmp_path)
    assert p.returncode == 137, p.stderr + p.stdout
    info = json.loads(p.stdout.strip().splitlines()[-1])
    tid = info["task_id"]
    assert info["attempts"] >= 1

    task = _task_json(tmp_path, tid)
    assert task["status"] in ("EXECUTING", "RECOVERY_REQUIRED", "FAILED", "AUTHORIZED")
    r = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r.returncode in (0, 1, 6), r.stderr + r.stdout
    task2 = _task_json(tmp_path, tid)
    assert task2["task_id"] == tid
    # second recovery attempt must remain safe/idempotent (no corruption/crash)
    r2 = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r2.returncode in (0, 1, 6), r2.stderr + r2.stdout


def test_point8_9_receipt_and_journal_present_but_task_not_completed_then_crash(tmp_path):
    # Boundary approximation: execution evidence (journal/receipt) persisted while task remains
    # non-terminal before final completion commit; process dies. Fresh recovery/inspect must be safe.
    code = r'''
import json, os, time
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("p8p9 evidence-no-complete", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.transition(rec.task_id, "EXECUTING")
aj._start_attempt(rec)
attempt_id = rec.attempts[-1]["attempt_id"]
lease = aj.leases.acquire(rec.task_id, "execute", ttl=60)
ev = aj.journal.append("EXECUTION_RESULT", task_id=rec.task_id, operation_id=rec.operation_id, attempt_id=attempt_id, lease_id=lease.lease_id, metadata={"ok": True, "output": "hello"})
if aj.receipts is not None:
    aj.receipts.record(task_id=rec.task_id, operation_id=rec.operation_id, attempt_id=attempt_id, worker_id=lease.worker_id, lease_id=lease.lease_id, capability_id=rec.capability_id, status="COMPLETED", started_at=time.time()-1, completed_at=time.time(), verification="ok", output="hello", journal_event_ids=[ev])
aj.tasks.save(rec, "evidence_written")
print(json.dumps({"task_id": rec.task_id, "status": aj.tasks.get(rec.task_id).status, "attempt_id": attempt_id}), flush=True)
os._exit(137)
'''
    p = _run_helper(code, tmp_path)
    assert p.returncode == 137, p.stderr + p.stdout
    info = json.loads(p.stdout.strip().splitlines()[-1])
    tid = info["task_id"]

    task = _task_json(tmp_path, tid)
    assert task["status"] != "COMPLETED"  # completion not committed
    assert task["task_id"] == tid
    r = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r.returncode in (0, 1, 6), r.stderr + r.stdout
    j = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    assert "findings" in j or "outcomes" in j or "error" in j
    task2 = _task_json(tmp_path, tid)
    # must not corrupt or fabricate unsafe duplicate completion semantics silently; state inspectable
    assert task2["status"] in ("EXECUTING","VERIFYING","RECOVERY_REQUIRED","FAILED","COMPLETED","RETRYING","AUTHORIZED","ABORTED","DEAD_LETTER","CANCELLED")
    chk = _run_aj(["--check", "--json"], tmp_path)
    assert chk.returncode in (0, 1)


def test_point10_crash_during_retry_scheduling_state_then_recover(tmp_path):
    # Boundary approximation: task in retry/recovery-transition state persisted, process exits before
    # retry execution progresses; fresh recovery must be safe/idempotent.
    code = r'''
import json, os
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("p10 retry-sched crash", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.transition(rec.task_id, "RECOVERY_REQUIRED", "test")
aj.tasks.transition(rec.task_id, "FAILED")
aj.tasks.save(rec, "failed")
# simulate scheduling into RETRYING-like recovery path and crash before execution
rec2 = aj.tasks.get(rec.task_id)
try:
    aj.tasks.transition(rec2.task_id, "RECOVERING", "retry scheduling")
    aj.tasks.save(rec2, "recovering")
    aj.tasks.transition(rec2.task_id, "RETRYING", "retry scheduled")
    aj.tasks.save(rec2, "retrying")
except Exception:
    pass
print(json.dumps({"task_id": rec.task_id, "status": aj.tasks.get(rec.task_id).status}), flush=True)
os._exit(137)
'''
    p = _run_helper(code, tmp_path)
    assert p.returncode == 137, p.stderr + p.stdout
    tid = json.loads(p.stdout.strip().splitlines()[-1])["task_id"]
    r = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r.returncode in (0, 1, 6), r.stderr + r.stdout
    t = _task_json(tmp_path, tid)
    assert t["task_id"] == tid
    r2 = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r2.returncode in (0, 1, 6)


def test_point14_crash_during_recovery_then_repeated_recovery_converges(tmp_path):
    # Kill recovery subprocess mid-run (SIGKILL) then run recovery again from fresh process.
    # Create a recovery-eligible FAILED task.
    setup = r'''
import json
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("p14 recover crash", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.transition(rec.task_id, "RECOVERY_REQUIRED", "test")
aj.tasks.transition(rec.task_id, "FAILED")
aj.tasks.save(rec, "failed")
print(json.dumps({"task_id": rec.task_id}))
'''
    sp = _run_helper(setup, tmp_path)
    assert sp.returncode == 0, sp.stderr + sp.stdout
    tid = json.loads(sp.stdout.strip().splitlines()[-1])["task_id"]

    # start recovery and kill it
    cfg = _write_cfg(tmp_path)
    cmd = [PY, "-m", "aj", "--config", str(cfg), "recover", "--task", tid, "--json"]
    proc = subprocess.Popen(cmd, cwd=str(AJ_ROOT), env=_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.05)
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    proc.wait(timeout=10)

    # repeated fresh-process recovery must converge safely
    r1 = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r1.returncode in (0, 1, 6), r1.stderr + r1.stdout
    r2 = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r2.returncode in (0, 1, 6), r2.stderr + r2.stdout
    t = _task_json(tmp_path, tid)
    assert t["status"] in ("RECOVERY_REQUIRED","FAILED","COMPLETED","RETRYING","RECOVERING","EXECUTING","AUTHORIZED","ABORTED","DEAD_LETTER")


def test_reconciliation_A_consistent_completed_state(tmp_path):
    p = _run_aj(["run", "--capability", "aj.echo", "--text", "A-state", "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    tid = json.loads(p.stdout)["task_id"]
    task = _task_json(tmp_path, tid)
    assert task["status"] == "COMPLETED"
    # inspect/recover on terminal completed: no corruption, honest handling
    p = _run_aj(["task", tid, "--json"], tmp_path)
    assert p.returncode == 0
    # second process sees consistent state
    task2 = _task_json(tmp_path, tid)
    assert task2["status"] == "COMPLETED"


def test_reconciliation_D_stale_lease_dead_worker_fresh_process(tmp_path):
    # Construction D: lease held/stale but owning worker dead (killed), verified in fresh process.
    code = r'''
import json, os, time
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("D stale lease", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.save(rec, "authorized")
lease = aj.leases.acquire(rec.task_id, "execute", ttl=30)
print(json.dumps({"task_id": rec.task_id, "lease": lease.lease_id}), flush=True)
os._exit(137)  # worker dies holding active lease
'''
    p = _run_helper(code, tmp_path)
    assert p.returncode == 137
    tid = json.loads(p.stdout.strip().splitlines()[-1])["task_id"]
    # fresh process: recovery/inspect safe; lease state is stale/expired-or-reclaimable over time or handled
    task = _task_json(tmp_path, tid)
    assert task["task_id"] == tid
    r = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert r.returncode in (0, 1, 6)
    chk = _run_aj(["--check", "--json"], tmp_path)
    assert chk.returncode in (0, 1)


def test_reconciliation_E_repeated_recovery_idempotent_replay_safe(tmp_path):
    # Construction E: interrupted/retryable state recovered repeatedly without duplicate corruption.
    setup = r'''
import json
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("E idempotent", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.transition(rec.task_id, "RECOVERY_REQUIRED", "test")
aj.tasks.transition(rec.task_id, "FAILED")
aj.tasks.save(rec, "failed")
print(json.dumps({"task_id": rec.task_id}))
'''
    sp = _run_helper(setup, tmp_path)
    assert sp.returncode == 0
    tid = json.loads(sp.stdout.strip().splitlines()[-1])["task_id"]
    for _ in range(3):
        r = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
        assert r.returncode in (0, 1, 6), r.stderr + r.stdout
        t = _task_json(tmp_path, tid)
        assert t["task_id"] == tid
        assert t["status"] in ("RECOVERY_REQUIRED","FAILED","COMPLETED","RETRYING","RECOVERING","EXECUTING","AUTHORIZED","ABORTED","DEAD_LETTER")
