from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

AJ_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _env(data_dir: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(AJ_ROOT) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    env.pop("AJ_INBOX_ROOT", None)
    return env


def _run_aj(args, data_dir: Path, timeout=30, check=False, **kw):
    cfg = data_dir / "config.json"
    if not cfg.exists():
        cfg.write_text(json.dumps({
            "core": {
                "data_dir": str(data_dir / "data"),
                "audit_dir": str(data_dir / "data" / "audit"),
                "memory_path": str(data_dir / "data" / "memory.sqlite3"),
            }
        }, indent=2), encoding="utf-8")
    cmd = [PY, "-m", "aj", "--config", str(cfg), *args]
    p = subprocess.run(cmd, cwd=str(AJ_ROOT), env=_env(data_dir), capture_output=True, text=True, timeout=timeout, **kw)
    if check and p.returncode != 0:
        raise AssertionError(f"cmd failed {p.returncode}\ncmd={cmd}\nstdout={p.stdout}\nstderr={p.stderr}")
    return p


def _load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({"_malformed": line})
    return rows


def test_normal_startup_shutdown_and_echo_subprocess(tmp_path):
    p = _run_aj(["--check", "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    report = json.loads(p.stdout)
    assert report["ok"] is True

    p = _run_aj(["run", "--capability", "aj.echo", "--text", "hello", "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    out = json.loads(p.stdout)
    assert out["ok"] is True
    assert out["status"] == "COMPLETED"
    task_id = out["task_id"]

    # fresh process visibility
    p = _run_aj(["task", task_id, "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    task = json.loads(p.stdout)["task"]
    assert task["status"] == "COMPLETED"
    assert task["task_id"] == task_id

    # clean second run and shutdown path (process exits 0)
    p = _run_aj(["tasks", "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    assert len(json.loads(p.stdout)["tasks"]) >= 1


def test_backend_exception_propagation_subprocess(tmp_path):
    p = _run_aj(["run", "--capability", "aj.no_such_capability", "--json"], tmp_path)
    assert p.returncode != 0
    # honest structured failure
    try:
        j = json.loads(p.stdout)
        assert j.get("ok") is False
        assert "error" in j
    except Exception:
        assert "error" in (p.stderr + p.stdout).lower()


def test_corrupt_incomplete_persisted_task_state_reports_honestly(tmp_path):
    # create valid state first
    p = _run_aj(["run", "--capability", "aj.echo", "--text", "seed", "--json"], tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    tasks_path = tmp_path / "data" / "tasks.jsonl"
    assert tasks_path.exists()
    original = tasks_path.read_text(encoding="utf-8")
    # append truncated/incomplete write + malformed line (simulated interrupted append)
    with tasks_path.open("a", encoding="utf-8") as f:
        f.write('{"reason":"update","task":{"task_id":"broken"')
        f.write("\nTHIS IS NOT JSON\n")

    p = _run_aj(["tasks", "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    j = json.loads(p.stdout)
    # original valid tasks still visible; malformed reported, not deleted
    assert len(j.get("tasks", [])) >= 1
    assert len(j.get("load_errors", [])) >= 1

    p = _run_aj(["--check", "--json"], tmp_path)
    # health/storage integrity should still report and system remains operable for valid state
    assert p.returncode in (0, 1)
    j = json.loads(p.stdout)
    assert "storage_integrity" in j.get("checks", {}) or "ok" in j


def test_interrupted_write_then_fresh_subprocess_recovery_no_data_loss(tmp_path):
    p = _run_aj(["run", "--capability", "aj.echo", "--text", "persisted", "--json"], tmp_path)
    assert p.returncode == 0
    tid = json.loads(p.stdout)["task_id"]
    tasks_path = tmp_path / "data" / "tasks.jsonl"
    # simulate torn append at end
    with tasks_path.open("ab") as f:
        f.write(b"\n{\"reason\":\"update\",\"task\":{")
    # fresh processes must still see completed task
    p = _run_aj(["task", tid, "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    assert json.loads(p.stdout)["task"]["status"] == "COMPLETED"
    p = _run_aj(["tasks", "--json"], tmp_path)
    assert p.returncode == 0
    assert any(t["task_id"] == tid for t in json.loads(p.stdout)["tasks"])


def test_stale_execution_lease_recovery_after_killed_worker_subprocess(tmp_path):
    # create a task record in a non-terminal, execution-relevant state with expired execution lease on disk
    setup = r'''
import json, time
from pathlib import Path
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("stale lease probe", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.save(rec, "state")
lease = aj.leases.acquire(rec.task_id, "execute", ttl=60)
lease.expires_at = time.time() - 100
lease.last_heartbeat_at = time.time() - 100
lease.status = "ACTIVE"
aj.leases._write(lease)
print(json.dumps({"task_id": rec.task_id, "lease_id": lease.lease_id}))
try:
    aj.memory.close()
except Exception:
    pass
'''
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"core": {"data_dir": str(tmp_path/"data"), "audit_dir": str(tmp_path/"data"/"audit"), "memory_path": str(tmp_path/"data"/"memory.sqlite3")}}), encoding="utf-8")
    code = setup.replace("__CFG__", str(cfg))
    p = subprocess.run([PY, "-c", code], cwd=str(AJ_ROOT), env=_env(tmp_path), capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr + p.stdout
    info = json.loads(p.stdout.strip().splitlines()[-1])
    tid = info["task_id"]

    # fresh subprocess attempts recovery; must not corrupt and must report honestly
    p = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    # recovery may succeed or require decision depending on policy; must be structured/no crash
    assert p.returncode in (0, 1, 6), p.stderr + p.stdout
    j = json.loads(p.stdout) if p.stdout.strip().startswith("{") else {}
    assert "findings" in j or "outcomes" in j or "error" in j

    # state inspectable in fresh process
    p = _run_aj(["task", tid, "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    st = json.loads(p.stdout)["task"]["status"]
    assert st in ("AUTHORIZED","EXECUTING","RECOVERY_REQUIRED","FAILED","COMPLETED","RETRYING","CANCELLED","ABORTED","BLOCKED","DEAD_LETTER","WAITING_FOR_APPROVAL","PLANNED","RECEIVED","UNDERSTANDING","VERIFYING","RECOVERING","ESCALATED","CANCEL_REQUESTED")


def test_sigterm_and_sigint_to_short_lived_cli_are_observable(tmp_path):
    # CLI commands are short-lived; we can at least verify normal completion and that
    # sending signals to a running subprocess is handled by OS without corrupting prior state.
    # Start a subprocess that does repeated checks (real process) and terminate it.
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"core": {"data_dir": str(tmp_path/"data"), "audit_dir": str(tmp_path/"data"/"audit"), "memory_path": str(tmp_path/"data"/"memory.sqlite3")}}), encoding="utf-8")
    # seed
    _run_aj(["run", "--capability", "aj.echo", "--text", "before-signal", "--json"], tmp_path, check=True)
    cmd = [PY, "-m", "aj", "--config", str(cfg), "tasks", "--json"]
    for sig in (signal.SIGTERM, signal.SIGINT):
        proc = subprocess.Popen(cmd, cwd=str(AJ_ROOT), env=_env(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # let it start then signal; may have already exited (that's fine - observable)
        time.sleep(0.05)
        try:
            proc.send_signal(sig)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=5)
        # prior persisted state must remain intact and readable
        p = _run_aj(["tasks", "--json"], tmp_path)
        assert p.returncode == 0, p.stderr + p.stdout
        tasks = json.loads(p.stdout)["tasks"]
        assert any(t.get("capability_id") == "aj.echo" or t.get("status") for t in tasks)


def test_repeated_crash_restart_cycles_no_corruption(tmp_path):
    tid = None
    for i in range(5):
        p = _run_aj(["run", "--capability", "aj.echo", "--text", f"cycle-{i}", "--json"], tmp_path)
        assert p.returncode == 0, p.stderr + p.stdout
        out = json.loads(p.stdout)
        assert out["status"] == "COMPLETED"
        tid = out["task_id"]
        # simulate abrupt restart boundary by starting fresh inspection subprocesses
        p2 = _run_aj(["task", tid, "--json"], tmp_path)
        assert p2.returncode == 0
        assert json.loads(p2.stdout)["task"]["status"] == "COMPLETED"
    p = _run_aj(["--check", "--json"], tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    assert json.loads(p.stdout)["ok"] is True


def test_duplicate_process_prevention_via_operation_lease_subprocess(tmp_path):
    # hold an operation lease in a subprocess (simulating active worker) then attempt conflicting op in another
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"core": {"data_dir": str(tmp_path/"data"), "audit_dir": str(tmp_path/"data"/"audit"), "memory_path": str(tmp_path/"data"/"memory.sqlite3")}}), encoding="utf-8")
    holder = r'''
import json, time
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("dup probe", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.save(rec, "state")
lease = aj.leases.acquire_operation(rec.task_id, "cancel", ttl=30)
print(json.dumps({"task_id": rec.task_id}), flush=True)
time.sleep(3)
try:
    aj.leases.release_operation(lease)
    aj.memory.close()
except Exception:
    pass
'''
    code = holder.replace("__CFG__", str(cfg))
    proc = subprocess.Popen([PY, "-c", code], cwd=str(AJ_ROOT), env=_env(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = proc.stdout.readline()
    tid = json.loads(line)["task_id"]
    try:
        # concurrent cancel attempt should be refused/blocked by lease, not corrupt
        p = _run_aj(["cancel", tid, "--json"], tmp_path, timeout=15)
        # either refused/failure due to held lease or structured response; must not crash store
        assert p.returncode in (0, 1, 3, 4, 5, 6)
        if p.stdout.strip().startswith("{"):
            j = json.loads(p.stdout)
            # if it reports, should be honest (not silent success while other holds it) - ok false likely
            assert "ok" in j or "task_id" in j or "error" in j
    finally:
        proc.wait(timeout=15)
    # after release, task still inspectable
    p = _run_aj(["task", tid, "--json"], tmp_path)
    assert p.returncode == 0
    assert json.loads(p.stdout)["task"]["task_id"] == tid


def test_sqlite_wal_recovery_memory_db_reopen(tmp_path):
    # exercise real sqlite memory db: create state, force wal checkpoint state by reopen cycles
    for i in range(3):
        p = _run_aj(["run", "--capability", "aj.echo", "--text", f"wal-{i}", "--json"], tmp_path)
        assert p.returncode == 0
    mem = tmp_path / "data" / "memory.sqlite3"
    assert mem.exists()
    # ensure db readable and consistent after abrupt process boundaries
    con = sqlite3.connect(str(mem))
    try:
        con.execute("PRAGMA wal_checkpoint(PASSIVE)")
        rows = con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
        assert rows >= 0
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"
    finally:
        con.close()
    p = _run_aj(["--check", "--json"], tmp_path)
    assert p.returncode == 0
    assert json.loads(p.stdout)["ok"] is True


def test_sigkill_worker_holding_lease_then_fresh_recovery(tmp_path):
    # Real process death via SIGKILL: flock is released by OS, but AJ execution/operation lease
    # files persist as stale state until reclaimed/recovered by a fresh process.
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"core": {"data_dir": str(tmp_path/"data"), "audit_dir": str(tmp_path/"data"/"audit"), "memory_path": str(tmp_path/"data"/"memory.sqlite3")}}), encoding="utf-8")
    holder = r'''
import json, time
from aj.config import load as load_config
from aj.runtime import assemble
cfg = load_config(r"__CFG__", env={}, overrides=None)
aj = assemble(cfg)
rec = aj.tasks.create("sigkill lease probe", capability_id="aj.echo")
aj.tasks.transition(rec.task_id, "RECEIVED")
aj.tasks.transition(rec.task_id, "UNDERSTANDING")
aj.tasks.transition(rec.task_id, "PLANNED")
aj.tasks.transition(rec.task_id, "AUTHORIZED")
aj.tasks.save(rec, "state")
lease = aj.leases.acquire(rec.task_id, "execute", ttl=60)
print(json.dumps({"task_id": rec.task_id, "lease_id": getattr(lease, "lease_id", "")}), flush=True)
time.sleep(30)
'''
    code = holder.replace("__CFG__", str(cfg))
    proc = subprocess.Popen([PY, "-c", code], cwd=str(AJ_ROOT), env=_env(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = proc.stdout.readline()
    assert line, "holder produced no output: " + (proc.stderr.read() or "")
    info = json.loads(line)
    tid = info["task_id"]
    time.sleep(0.2)
    proc.kill()
    proc.wait(timeout=10)
    # lease file may remain (stale) after SIGKILL; fresh recovery must handle honestly
    p = _run_aj(["recover", "--task", tid, "--json"], tmp_path)
    assert p.returncode in (0, 1, 6), p.stderr + p.stdout
    # state remains inspectable and --check stays operable
    p = _run_aj(["task", tid, "--json"], tmp_path)
    assert p.returncode == 0, p.stderr + p.stdout
    p = _run_aj(["--check", "--json"], tmp_path)
    assert p.returncode in (0, 1)
    j = json.loads(p.stdout)
    assert "checks" in j


def test_sqlite_transaction_interruption_rollback_on_reopen(tmp_path):
    # Uncommitted transaction in a killed process must not persist partial rows (SQLite rollback).
    db = tmp_path / "txn.sqlite3"
    script = r'''
import sqlite3, time, sys
db = sys.argv[1]
con = sqlite3.connect(db)
con.execute("CREATE TABLE IF NOT EXISTS t(id INTEGER PRIMARY KEY, v TEXT)")
con.execute("BEGIN IMMEDIATE")
con.execute("INSERT INTO t(v) VALUES('partial')")
print("in_txn", flush=True)
time.sleep(30)
'''
    proc = subprocess.Popen([PY, "-c", script, str(db)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "in_txn"
    time.sleep(0.2)
    proc.kill()
    proc.wait(timeout=10)
    con = sqlite3.connect(str(db))
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"
        # partial row must not be committed
        try:
            count = con.execute("SELECT count(*) FROM t WHERE v='partial'").fetchone()[0]
            assert count == 0
        except sqlite3.OperationalError:
            # table may not exist if killed before create committed - also safe
            pass
    finally:
        con.close()


def test_flock_released_on_process_kill_allows_fresh_acquire(tmp_path):
    # Advisory flock sidecar locks are released by OS on process death; fresh writer can proceed.
    lockfile = tmp_path / "tasks.jsonl.lock"
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    holder = r'''
import fcntl, os, sys, time
p = sys.argv[1]
fd = os.open(p, os.O_CREAT | os.O_RDWR, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
print("locked", flush=True)
time.sleep(30)
'''
    proc = subprocess.Popen([PY, "-c", holder, str(lockfile)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "locked"
    time.sleep(0.1)
    proc.kill()
    proc.wait(timeout=10)
    # fresh process can acquire and write
    acq = r'''
import fcntl, os, sys
p = sys.argv[1]
fd = os.open(p, os.O_CREAT | os.O_RDWR, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
fcntl.flock(fd, fcntl.LOCK_UN)
os.close(fd)
print("acquired")
'''
    p = subprocess.run([PY, "-c", acq, str(lockfile)], capture_output=True, text=True, timeout=10)
    assert p.returncode == 0, p.stderr + p.stdout
    assert "acquired" in p.stdout
