"""Phase 3B: task persistence failures must fail closed.

Controlled fault injection in isolated temp storage only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aj import errors, task as taskmod
from aj.audit import JsonlAuditSink, read_events
from aj.capability import AVAILABLE, VERIFIED, CapabilityRegistry, CapabilitySpec
from aj.config import load as load_config
from aj.runtime import assemble
from aj.task import TaskStore


def _cfg(tmp_path: Path, name: str = "data"):
    return load_config(None, env={}, overrides={"core": {
        "data_dir": str(tmp_path / name),
        "audit_dir": str(tmp_path / name / "audit"),
        "memory_path": str(tmp_path / name / "memory.sqlite3"),
    }})


def _boom_open(self, *a, **kw):
    raise OSError("simulated disk write failure")


def _boom_file_lock(*a, **kw):
    raise OSError("simulated lock/write failure")


def _fail_task_writes(monkeypatch):
    """Fail append writes to tasks.jsonl only, leaving reads/reload intact."""
    original_open = Path.open

    def selective_open(self, *a, **kw):
        mode = a[0] if a else kw.get("mode", "r")
        if str(self).endswith("tasks.jsonl") and any(m in str(mode) for m in ("a", "w", "+")):
            # allow reads; fail durability writes
            if "r" in str(mode) and "+" not in str(mode):
                return original_open(self, *a, **kw)
            raise OSError("simulated task persistence write failure")
        return original_open(self, *a, **kw)

    monkeypatch.setattr(Path, "open", selective_open)
    return original_open


def test_task_creation_persistence_failure_raises_and_leaves_no_durable_record(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    _fail_task_writes(monkeypatch)
    with pytest.raises(errors.StorageError) as excinfo:
        store.create("must persist", capability_id="aj.echo")
    err = excinfo.value
    assert err.code == errors.STORAGE_ERROR
    assert "could not persist task record" in err.message
    # failed creation must not remain as a healthy in-memory task
    assert store.all() == []
    # reload from disk: no durable record written
    monkeypatch.undo()
    fresh = TaskStore(tmp_path / "data")
    assert fresh.all() == []
    assert fresh.load_errors == []
    tasks_path = tmp_path / "data" / "tasks.jsonl"
    assert not tasks_path.exists() or tasks_path.read_text(encoding="utf-8") == ""


def test_transition_persistence_failure_raises_and_reconciles_to_last_durable_state(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    rec = store.create("persisted goal", capability_id="aj.echo")
    tid = rec.task_id
    # durable baseline is RECEIVED
    _fail_task_writes(monkeypatch)
    with pytest.raises(errors.StorageError) as excinfo:
        store.transition(tid, taskmod.UNDERSTANDING, "route")
    assert excinfo.value.code == errors.STORAGE_ERROR
    # in-memory state reconciled to last durable snapshot, not mutated success
    assert store.get(tid).status == taskmod.RECEIVED
    # restart/reload confirms no false durable transition
    monkeypatch.undo()
    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED


def test_save_persistence_failure_raises_and_reconciles(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    rec = store.create("save goal", capability_id="aj.echo")
    rec.summary = "mutated in memory"
    tid = rec.task_id
    monkeypatch.setattr(taskmod, "file_lock", _boom_file_lock)
    with pytest.raises(errors.StorageError) as excinfo:
        store.save(rec, "metadata")
    assert excinfo.value.code == errors.STORAGE_ERROR
    monkeypatch.undo()
    # reconciled/reload-visible state must not show undurable metadata progress
    fresh = TaskStore(tmp_path / "data")
    r2 = fresh.get(tid)
    assert r2.status == taskmod.RECEIVED
    assert r2.summary == ""


def test_cancel_persistence_failure_raises_and_reconciles(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    rec = store.create("cancel goal", capability_id="aj.echo")
    tid = rec.task_id
    _fail_task_writes(monkeypatch)
    with pytest.raises(errors.StorageError):
        store.cancel(tid)
    assert store.get(tid).status == taskmod.RECEIVED
    monkeypatch.undo()
    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED


def test_no_protected_execution_when_initial_task_persistence_fails(tmp_path, monkeypatch):
    from aj.actions import InternalActions

    calls = []

    def tracked_echo(args):
        calls.append(dict(args or {}))
        return {"echo": args.get("text", "")}

    aj = assemble(_cfg(tmp_path))
    try:
        aj.actions = InternalActions({"echo": tracked_echo})
        # creation-time persistence failure: task cannot be durably accepted
        _fail_task_writes(monkeypatch)
        with pytest.raises(errors.StorageError):
            aj.handle("run", capability_id="aj.echo", payload={"text": "secret"})
        assert calls == []
    finally:
        monkeypatch.undo()
        aj.memory.close()

    # after failure/restart there is no falsely successful durable task
    aj2 = assemble(_cfg(tmp_path))
    try:
        assert aj2.tasks.all() == []
        audit_events = read_events(tmp_path / "data" / "audit", limit=0).events
        assert not any(e.get("action") == "executed" for e in audit_events)
    finally:
        aj2.memory.close()


def test_no_false_success_when_completion_persistence_fails(tmp_path, monkeypatch):
    aj = assemble(_cfg(tmp_path))
    try:
        original_open = Path.open

        def selective_open(self, *a, **kw):
            mode = a[0] if a else kw.get("mode", "r")
            if "a" in str(mode) and str(self).endswith("tasks.jsonl"):
                content = self.read_text(encoding="utf-8") if self.exists() else ""
                # allow create + early lifecycle appends, fail final completion persist
                if '"reason": "completed"' in content or content.count("\n") >= 4:
                    raise OSError("simulated completion write failure")
            return original_open(self, *a, **kw)

        monkeypatch.setattr(Path, "open", selective_open)
        with pytest.raises(errors.StorageError):
            aj.handle("finish", capability_id="aj.echo", payload={"text": "hi"})
    finally:
        monkeypatch.undo()
        aj.memory.close()

    # restart: must not show durable COMPLETED success from failed final write
    aj2 = assemble(_cfg(tmp_path))
    try:
        records = aj2.tasks.all()
        assert len(records) == 1
        r = records[0]
        assert r.status != taskmod.COMPLETED
        assert r.status in (taskmod.EXECUTING, taskmod.VERIFYING, taskmod.AUTHORIZED,
                            taskmod.PLANNED, taskmod.UNDERSTANDING, taskmod.RECEIVED)
    finally:
        aj2.memory.close()


def test_attempt_or_result_progress_persistence_failure_does_not_claim_success(tmp_path, monkeypatch):
    aj = assemble(_cfg(tmp_path))
    try:
        original_open = Path.open

        def selective_open(self, *a, **kw):
            mode = a[0] if a else kw.get("mode", "r")
            if "a" in str(mode) and str(self).endswith("tasks.jsonl"):
                content = self.read_text(encoding="utf-8") if self.exists() else ""
                # fail attempt/result progress persistence before completion
                if '"reason": "attempt_started"' in content or '"reason": "result"' in content:
                    raise OSError("simulated attempt/result write failure")
            return original_open(self, *a, **kw)

        monkeypatch.setattr(Path, "open", selective_open)
        with pytest.raises(errors.StorageError):
            aj.handle("attempt", capability_id="aj.echo", payload={"text": "x"})
    finally:
        monkeypatch.undo()
        aj.memory.close()

    aj2 = assemble(_cfg(tmp_path))
    try:
        records = aj2.tasks.all()
        assert len(records) == 1
        assert records[0].status != taskmod.COMPLETED
    finally:
        aj2.memory.close()


def test_recovery_persistence_failure_propagates_and_reconciles(tmp_path, monkeypatch):
    aj = assemble(_cfg(tmp_path))
    try:
        rec = aj.tasks.create("recover persist fail", capability_id="aj.echo")
        rec.request_payload = {"text": "hi"}
        for s in [taskmod.UNDERSTANDING, taskmod.PLANNED, taskmod.AUTHORIZED, taskmod.EXECUTING]:
            aj.tasks.transition(rec.task_id, s)
        aj.tasks.save(rec, "exec")
        tid = rec.task_id
    finally:
        aj.memory.close()

    aj2 = assemble(_cfg(tmp_path))
    try:
        _fail_task_writes(monkeypatch)
        with pytest.raises(errors.StorageError):
            aj2.recover(tid)
    finally:
        monkeypatch.undo()
        aj2.memory.close()

    # last durable state before recovery attempt remains authoritative
    aj3 = assemble(_cfg(tmp_path))
    try:
        assert aj3.tasks.get(tid).status == taskmod.EXECUTING
    finally:
        aj3.memory.close()


def test_existing_append_only_persistence_still_records_history(tmp_path):
    store = TaskStore(tmp_path / "data")
    rec = store.create("history", capability_id="aj.echo")
    tid = rec.task_id
    store.transition(tid, taskmod.UNDERSTANDING, "step1")
    store.transition(tid, taskmod.PLANNED, "step2")
    store.save(store.get(tid), "update")
    path = tmp_path / "data" / "tasks.jsonl"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 4
    reasons = [json.loads(ln)["reason"] for ln in lines]
    assert reasons == ["created", "transition", "transition", "update"]
    fresh = TaskStore(tmp_path / "data")
    r = fresh.get(tid)
    assert r.status == taskmod.PLANNED
    assert len(r.events) == 2
    assert fresh.load_errors == []


def test_persistence_error_preserves_original_oserror(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    _fail_task_writes(monkeypatch)
    with pytest.raises(errors.StorageError) as excinfo:
        store.create("cause")
    assert isinstance(excinfo.value.__cause__, OSError)
    assert "simulated task persistence write failure" in str(excinfo.value.__cause__)


def test_failed_persist_reconciliation_is_atomic_for_same_store_instance(tmp_path, monkeypatch):
    """No other thread may observe/mutate a failed non-durable mutation before reconciliation."""
    import threading

    store = TaskStore(tmp_path / "data")
    rec = store.create("atomic", capability_id="aj.echo")
    tid = rec.task_id
    assert store.get(tid).status == taskmod.RECEIVED

    a_in_hook = threading.Event()
    allow_a_finish = threading.Event()
    b_done = threading.Event()
    results = {}

    original_hook = store._on_persist_failure

    def hook(record, reason, exc):
        a_in_hook.set()
        assert allow_a_finish.wait(timeout=5), "test coordinator did not release Thread A"

    monkeypatch.setattr(store, "_on_persist_failure", hook)
    _fail_task_writes(monkeypatch)

    def thread_a():
        try:
            store.transition(tid, taskmod.UNDERSTANDING, "race")
            results["a"] = ("ok", None)
        except Exception as e:
            results["a"] = ("err", e)

    def thread_b():
        a_in_hook.wait(timeout=5)
        # Must not observe failed unreconciled mutation while A holds the critical section.
        # With the fix, this blocks until A releases; then reconciled durable state is visible.
        try:
            r = store.get(tid)
            results["b"] = ("seen", r.status)
        except Exception as e:
            results["b"] = ("err", e)
        finally:
            b_done.set()

    ta = threading.Thread(target=thread_a)
    tb = threading.Thread(target=thread_b)
    ta.start()
    assert a_in_hook.wait(timeout=5), "Thread A did not reach post-reconcile hook"
    tb.start()
    # Give B a chance to run; it must not complete while A is paused in-hook (lock held).
    assert not b_done.wait(timeout=0.2), "Thread B observed/acted before reconciliation completed"
    allow_a_finish.set()
    ta.join(timeout=5)
    tb.join(timeout=5)
    assert not ta.is_alive() and not tb.is_alive()

    assert results["a"][0] == "err"
    assert isinstance(results["a"][1], errors.StorageError)
    assert results["b"] == ("seen", taskmod.RECEIVED)
    assert store.get(tid).status == taskmod.RECEIVED

    monkeypatch.undo()
    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED


def test_successful_persistence_still_allows_normal_concurrent_operations(tmp_path):
    """Ordinary successful concurrent operations remain functional after atomicity fix."""
    import threading

    store = TaskStore(tmp_path / "data")
    n = 12
    ids = []
    lock = threading.Lock()
    errors_out = []

    def worker(i):
        try:
            r = store.create(f"goal-{i}", capability_id="aj.echo")
            store.transition(r.task_id, taskmod.UNDERSTANDING, f"step-{i}")
            with lock:
                ids.append(r.task_id)
        except Exception as e:
            with lock:
                errors_out.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors_out == []
    assert len(ids) == n
    assert len(set(ids)) == n
    for tid in ids:
        assert store.get(tid).status == taskmod.UNDERSTANDING
    fresh = TaskStore(tmp_path / "data")
    assert len(fresh.all()) == n
    assert all(fresh.get(tid).status == taskmod.UNDERSTANDING for tid in ids)


def test_stale_task_record_reference_cannot_be_saved_after_reconciliation(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    rec = store.create("stale", capability_id="aj.echo")
    tid = rec.task_id
    stale = store.get(tid)
    assert stale == store.get(tid)
    assert stale is not store.get(tid)

    _fail_task_writes(monkeypatch)
    with pytest.raises(errors.StorageError):
        store.transition(tid, taskmod.UNDERSTANDING, "boom")
    monkeypatch.undo()

    # store reconciled to last durable state; stale snapshot unaffected
    assert store.get(tid).status == taskmod.RECEIVED
    assert stale.status == taskmod.RECEIVED  # snapshot from before transition; never mutated
    # attempting to save an outdated snapshot cannot advance lifecycle/state
    stale_mutated = store.get(tid)
    stale_mutated.status = taskmod.UNDERSTANDING  # caller-side mutation of snapshot only
    store.save(stale_mutated, "reinject")
    assert store.get(tid).status == taskmod.RECEIVED

    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED


def test_on_persist_failure_hook_exception_does_not_mask_storage_error(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    rec = store.create("hook", capability_id="aj.echo")
    tid = rec.task_id

    def bad_hook(record, reason, exc):
        raise RuntimeError("hook boom")

    monkeypatch.setattr(store, "_on_persist_failure", bad_hook)
    _fail_task_writes(monkeypatch)
    with pytest.raises(errors.StorageError) as excinfo:
        store.transition(tid, taskmod.UNDERSTANDING, "boom")
    assert excinfo.value.code == errors.STORAGE_ERROR
    assert excinfo.value.__cause__ is not None
    monkeypatch.undo()

    # reconciliation still completed despite hook failure
    assert store.get(tid).status == taskmod.RECEIVED
    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED


def test_get_returns_snapshot_status_mutation_does_not_affect_store_or_disk(tmp_path):
    store = TaskStore(tmp_path / "data")
    rec = store.create("snap", capability_id="aj.echo")
    tid = rec.task_id
    snap = store.get(tid)
    snap.status = taskmod.COMPLETED
    assert store.get(tid).status == taskmod.RECEIVED
    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED


def test_read_apis_return_snapshots_not_authoritative_state(tmp_path):
    store = TaskStore(tmp_path / "data")
    a = store.create("a", capability_id="aj.echo").task_id
    b = store.create("b", capability_id="aj.echo").task_id
    store.transition(a, taskmod.UNDERSTANDING)

    for getter in [
        lambda: store.get(a),
        lambda: store.find(a),
        lambda: [r for r in store.all() if r.task_id == a][0],
        lambda: [r for r in store.active() if r.task_id == a][0],
        lambda: store.query(newest_first=True)[0] if store.query(newest_first=True)[0].task_id == a else store.query(newest_first=True)[1],
    ]:
        snap = getter()
        assert snap.task_id == a
        snap.status = taskmod.COMPLETED
        snap.summary = "tampered"
        assert store.get(a).status == taskmod.UNDERSTANDING
        assert store.get(a).summary == ""

    # query filtered
    q = store.query(status=taskmod.UNDERSTANDING)
    assert len(q) == 1
    q[0].goal = "tampered"
    assert store.get(a).goal == "a"

    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(a).status == taskmod.UNDERSTANDING
    assert fresh.get(a).summary == ""
    assert fresh.get(a).goal == "a"
    assert fresh.get(b).status == taskmod.RECEIVED


def test_nested_mutations_on_snapshots_do_not_affect_authoritative_state(tmp_path):
    store = TaskStore(tmp_path / "data")
    rec = store.create("nested", capability_id="aj.echo")
    tid = rec.task_id
    store.transition(tid, taskmod.UNDERSTANDING, "step")
    snap = store.get(tid)
    snap.events.append({"status": "INJECTED", "at": 0})
    snap.errors.append({"message": "x"})
    snap.warnings.append("w")
    snap.attempts.append({"attempt_id": "fake"})
    snap.actions_taken.append({"action": "x"})
    snap.request_payload["evil"] = True
    snap.authorization_context["evil"] = True
    snap.evidence.append({"evil": True})
    snap.artifacts.append({"evil": True})
    snap.recovery["evil"] = True
    snap.depends_on.append("dep")

    current = store.get(tid)
    assert not any(e.get("status") == "INJECTED" for e in current.events)
    assert current.errors == []
    assert current.warnings == []
    assert current.attempts == []
    assert current.actions_taken == []
    assert current.request_payload == {}
    assert current.authorization_context == {}
    assert current.evidence == []
    assert current.artifacts == []
    assert current.recovery == {}
    assert current.depends_on == []

    fresh = TaskStore(tmp_path / "data")
    f = fresh.get(tid)
    assert not any(e.get("status") == "INJECTED" for e in f.events)
    assert f.errors == [] and f.attempts == [] and f.request_payload == {}


def test_cannot_bypass_legal_transition_by_mutating_snapshot_and_saving(tmp_path):
    store = TaskStore(tmp_path / "data")
    rec = store.create("bypass", capability_id="aj.echo")
    tid = rec.task_id
    snap = store.get(tid)
    snap.status = taskmod.COMPLETED
    snap.completed_at = 1.0
    store.save(snap, "evil")
    assert store.get(tid).status == taskmod.RECEIVED
    assert store.get(tid).completed_at is None
    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED
    assert fresh.get(tid).completed_at is None
    # no forged COMPLETED lifecycle event persisted
    assert not any(e.get("status") == taskmod.COMPLETED for e in fresh.get(tid).events)


def test_legitimate_store_mutation_methods_and_orchestrator_flows_still_work(tmp_path):
    aj = assemble(_cfg(tmp_path))
    try:
        o = aj.handle("ok", capability_id="aj.echo", payload={"text": "hi"})
        assert o.ok and o.status == "COMPLETED"
        r = aj.tasks.get(o.task_id)
        assert r.status == "COMPLETED" and r.terminal
        assert r.summary
        # store-controlled methods
        rec = aj.tasks.create("x", capability_id="aj.echo")
        tid = rec.task_id
        assert aj.tasks.get(tid).status == taskmod.RECEIVED
        aj.tasks.transition(tid, taskmod.UNDERSTANDING)
        aj.tasks.transition(tid, taskmod.PLANNED)
        assert aj.tasks.cancel(tid) is True
        assert aj.tasks.get(tid).status == taskmod.CANCELLED
    finally:
        aj.memory.close()
    aj2 = assemble(_cfg(tmp_path))
    try:
        assert aj2.tasks.get(o.task_id).status == "COMPLETED"
        assert aj2.tasks.get(tid).status == "CANCELLED"
    finally:
        aj2.memory.close()


def test_failed_persistence_reconciles_and_stale_snapshot_cannot_reinsert(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    rec = store.create("stale2", capability_id="aj.echo")
    tid = rec.task_id
    before = store.get(tid)
    _fail_task_writes(monkeypatch)
    with pytest.raises(errors.StorageError):
        store.transition(tid, taskmod.UNDERSTANDING)
    monkeypatch.undo()
    assert store.get(tid).status == taskmod.RECEIVED
    # old snapshot mutation cannot change authoritative state
    before.summary = "tampered"
    store.save(before, "nope")
    assert store.get(tid).status == taskmod.RECEIVED
    assert store.get(tid).summary == "tampered" or store.get(tid).summary == ""
    # status bypass still prevented
    bypass = store.get(tid)
    bypass.status = taskmod.COMPLETED
    store.save(bypass, "nope2")
    assert store.get(tid).status == taskmod.RECEIVED
    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED


def test_snapshots_do_not_alias_authoritative_state_after_reload_reconciliation(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "data")
    rec = store.create("alias", capability_id="aj.echo")
    tid = rec.task_id
    snap_before = store.get(tid)
    _fail_task_writes(monkeypatch)
    with pytest.raises(errors.StorageError):
        store.transition(tid, taskmod.UNDERSTANDING)
    monkeypatch.undo()
    snap_after = store.get(tid)
    assert snap_after.status == taskmod.RECEIVED
    # mutate previously held snapshots
    snap_before.events.append({"status": "BAD", "at": 0})
    snap_before.status = taskmod.COMPLETED
    snap_after.errors.append({"message": "bad"})
    assert store.get(tid).status == taskmod.RECEIVED
    assert not any(e.get("status") == "BAD" for e in store.get(tid).events)
    assert store.get(tid).errors == []
    # explicit reload
    store.reload()
    snap_after.events.append({"status": "BAD2", "at": 0})
    assert not any(e.get("status") == "BAD2" for e in store.get(tid).events)
    fresh = TaskStore(tmp_path / "data")
    assert fresh.get(tid).status == taskmod.RECEIVED
    assert not any(e.get("status") in ("BAD", "BAD2", "COMPLETED") for e in fresh.get(tid).events)


def test_deep_nested_snapshot_mutations_and_event_history_cannot_bypass_store(tmp_path):
    store = TaskStore(tmp_path / "data")
    rec = store.create("deep", capability_id="aj.echo")
    tid = rec.task_id
    # seed nested mutable content through controlled save
    seed = store.get(tid)
    seed.request_payload = {"a": {"b": [1, {"c": 2}]}}
    seed.recovery = {"x": {"y": [0]}}
    store.save(seed, "seed")

    # Mutating a returned snapshot (deeply nested) must not affect authoritative state without save.
    snap = store.get(tid)
    snap.request_payload["a"]["b"][1]["c"] = 999
    snap.request_payload["a"]["b"].append("evil")
    snap.recovery["x"]["y"].append(1)
    assert store.get(tid).request_payload == {"a": {"b": [1, {"c": 2}]}}
    assert store.get(tid).recovery == {"x": {"y": [0]}}

    # Saving a mutated snapshot may persist legitimate field updates, but cannot
    # bypass lifecycle/status, event history, or completion timestamp ownership.
    forged = store.get(tid)
    forged.status = taskmod.COMPLETED
    forged.events.append({"status": taskmod.COMPLETED, "at": 1, "detail": "forged"})
    forged.completed_at = 1.0
    forged.request_payload["a"]["b"][1]["c"] = 7  # legitimate data-field update
    store.save(forged, "update")
    cur = store.get(tid)
    assert cur.status == taskmod.RECEIVED
    assert cur.completed_at is None
    assert not any(e.get("detail") == "forged" or e.get("status") == taskmod.COMPLETED for e in cur.events)
    assert cur.request_payload == {"a": {"b": [1, {"c": 7}]}}
    fresh = TaskStore(tmp_path / "data")
    f = fresh.get(tid)
    assert f.status == taskmod.RECEIVED
    assert f.completed_at is None
    assert f.request_payload == {"a": {"b": [1, {"c": 7}]}}
    assert not any(e.get("detail") == "forged" for e in f.events)
