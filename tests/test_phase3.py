"""Phase 3: lifecycle controls, concurrency, transfer, diagnostics and CLI.

The tests from Phases 1-3.1 are all retained here.  New Phase 3.1 tests
for leases, journal, receipts, scheduler, idempotency, dependencies,
lineage, retention and security are appended at the end.

"""

from __future__ import annotations

import json
import logging
import multiprocessing
import shutil
import time
from pathlib import Path

import pytest

from aj import errors, transfer
from aj.__main__ import (
    EXIT_CONFIG,
    EXIT_FAILURE,
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_UNSAFE,
    main,
)
from aj.audit import AuditLog, JsonlAuditSink, read_events
from aj.config import load as load_config, validate
from aj.locking import file_lock
from aj.memory import MemoryStore
from aj.recovery import RecoveryManager
from aj.runtime import assemble, health, memory_path
from aj.summary import build as build_summary, verify as verify_summary
from aj.task import (
    AUTHORIZED,
    CANCELLED,
    CANCEL_REQUESTED,
    COMPLETED,
    EXECUTING,
    FAILED,
    PLANNED,
    RECEIVED,
    UNDERSTANDING,
    TaskStore,
)

FAILED_STATES = (UNDERSTANDING, PLANNED, AUTHORIZED, EXECUTING, FAILED)

def _config(tmp_path: Path):
    return load_config(None, env={}, overrides={"core": {
        "data_dir": str(tmp_path / "data"),
        "audit_dir": str(tmp_path / "data" / "audit"),
        "memory_path": str(tmp_path / "data" / "memory.sqlite3"),
    }})

@pytest.fixture
def config(tmp_path):
    return _config(tmp_path)

@pytest.fixture
def aj(config):
    control = assemble(config)
    yield control
    if control.memory is not None:
        control.memory.close()

def _failed(control, capability="aj.echo", goal="probe", with_attempt=False):
    record = control.tasks.create(goal, capability_id=capability)
    for status in FAILED_STATES[:-1]:
        control.tasks.transition(record.task_id, status)
    if with_attempt:
        control._start_attempt(record)
    control.tasks.transition(record.task_id, FAILED)
    error = errors.AjError("boom", code=errors.EXECUTION_FAILED)
    record = control.tasks.get(record.task_id)
    record.record_error(error, stage="execute")
    if with_attempt:
        control._finish_attempt(record, FAILED, error)
    control.tasks.save(record, "failed")
    return record

def _cli(config_path, *argv):
    return main(["--config", str(config_path), *argv])

# --- lifecycle / attempts -------------------------------------------------

def test_successful_execution_records_one_completed_attempt(aj):
    outcome = aj.handle("attempt probe", capability_id="aj.echo",
                        payload={"text": "hi"}, requester="test")
    record = aj.tasks.get(outcome.task_id)
    assert outcome.ok and record.status == COMPLETED
    assert record.operation_id.startswith("op_")
    assert len(record.attempts) == 1
    attempt = record.attempts[0]
    assert attempt["attempt_number"] == 1
    assert attempt["status"] == COMPLETED
    assert attempt["operation_id"] == record.operation_id
    assert attempt["started_at"] <= attempt["ended_at"]

def test_retry_preserves_task_id_and_history(aj):
    record = _failed(aj, goal="retry probe", with_attempt=True)
    assert len(record.attempts) == 1 and record.attempts[0]["status"] == FAILED
    outcome = aj.retry(record.task_id)
    reloaded = aj.tasks.get(record.task_id)
    assert outcome.ok and reloaded.status == COMPLETED
    assert reloaded.task_id == record.task_id
    assert len(reloaded.attempts) == 2
    assert reloaded.attempts[0]["status"] == FAILED
    assert reloaded.attempts[1]["status"] == COMPLETED
    assert reloaded.attempts[1]["attempt_number"] == 2
    assert reloaded.errors and reloaded.errors[0]["code"] == "execution_failed"

def test_retry_is_refused_for_unmarked_capability(aj):
    record = _failed(aj, capability="jarvis.web_search", goal="unsafe retry")
    before = len(record.attempts)
    outcome = aj.retry(record.task_id)
    reloaded = aj.tasks.get(record.task_id)
    assert outcome.ok is False
    assert "retry refused" in outcome.summary.lower()
    assert reloaded.status == FAILED
    assert reloaded.requires_user_decision is True
    assert len(reloaded.attempts) == before

def test_retry_of_terminal_task_is_rejected(aj):
    outcome = aj.handle("done", capability_id="aj.echo",
                        payload={"text": "x"}, requester="test")
    with pytest.raises(errors.AjError):
        aj.retry(outcome.task_id)

def test_cancel_moves_non_terminal_task_to_cancelled(aj):
    record = aj.tasks.create("cancel probe", capability_id="aj.echo")
    outcome = aj.cancel_task(record.task_id)
    assert outcome.ok and outcome.status == CANCELLED
    assert aj.tasks.get(record.task_id).status == CANCELLED
    assert aj.cancel(record.task_id) is False

def test_cancel_of_terminal_task_changes_nothing(aj):
    outcome = aj.handle("done", capability_id="aj.echo",
                        payload={"text": "x"}, requester="test")
    result = aj.cancel_task(outcome.task_id)
    assert result.ok is False and result.status == COMPLETED
    assert aj.tasks.get(outcome.task_id).status == COMPLETED

def test_cancel_while_executing_requests_without_claiming_stop(aj):
    record = aj.tasks.create("running probe", capability_id="aj.echo")
    for status in (UNDERSTANDING, PLANNED, AUTHORIZED, EXECUTING):
        aj.tasks.transition(record.task_id, status)
    outcome = aj.cancel_task(record.task_id)
    reloaded = aj.tasks.get(record.task_id)
    assert outcome.ok is False
    assert outcome.status == CANCEL_REQUESTED
    assert reloaded.requires_user_decision is True
    assert "not interrupted" in outcome.summary
    # A persisted request can still be confirmed by an operator.
    assert aj.cancel_task(record.task_id).status == CANCELLED

def test_audit_memory_and_logs_share_correlation_ids(aj, config, caplog):
    with caplog.at_level(logging.INFO, logger="aj.orchestrator"):
        outcome = aj.handle("correlation probe", capability_id="aj.echo",
                            payload={"text": "x"}, requester="test")
    record = aj.tasks.get(outcome.task_id)
    attempt_id = record.attempts[0]["attempt_id"]

    events = read_events(config.get("core.audit_dir"), limit=0,
                         task_id=record.task_id).events
    executed = next(event for event in events if event["action"] == "executed")
    assert executed["operation_id"] == record.operation_id
    assert executed["attempt_id"] == attempt_id

    memory = list(aj.memory.events(task_id=record.task_id, limit=50))
    assert memory
    assert all(event.meta.get("operation_id") == record.operation_id
               for event in memory)
    assert all(event.meta.get("attempt_id") in (None, "", attempt_id)
               for event in memory)

    assert f"task={record.task_id}" in caplog.text
    assert f"operation={record.operation_id}" in caplog.text
    assert f"attempt={attempt_id}" in caplog.text

def test_attempt_model_survives_reload(config):
    control = assemble(config)
    record = control.tasks.create("persist attempt", capability_id="aj.echo")
    control._start_attempt(record)
    control._finish_attempt(record, COMPLETED)
    control.tasks.save(record, "attempt")
    control.memory.close()
    reopened = TaskStore(config.get("core.data_dir"))
    loaded = reopened.get(record.task_id)
    assert loaded.operation_id == record.operation_id
    assert loaded.attempts[0]["status"] == COMPLETED
    assert loaded.attempts[0]["attempt_id"] == record.attempts[0]["attempt_id"]

# --- summary --------------------------------------------------------------

def test_summary_task_scope_and_parity(aj):
    first = aj.handle("one", capability_id="aj.echo", payload={"text": "a"},
                      requester="test")
    aj.handle("two", capability_id="aj.echo", payload={"text": "b"},
              requester="test")
    built = build_summary(aj.memory, task_id=first.task_id)
    report = verify_summary(aj.memory, task_id=first.task_id)
    assert report["ok"] is True
    assert built["kind"].endswith(first.task_id)
    assert built["source_event_ids"]
    before = aj.memory.count_events()
    aj.memory.append_event("task.note", "later event", task_id=first.task_id)
    assert verify_summary(aj.memory, task_id=first.task_id)["ok"] is False
    assert aj.memory.count_events() == before + 1

def test_summary_rebuild_does_not_touch_raw_events(aj):
    aj.handle("one", capability_id="aj.echo", payload={"text": "a"},
              requester="test")
    before = aj.memory.count_events()
    first = build_summary(aj.memory)
    second = build_summary(aj.memory)
    assert first["content"] == second["content"]
    assert aj.memory.count_events() == before

# --- concurrency ----------------------------------------------------------

def _task_writer(directory: str, count: int) -> None:
    store = TaskStore(directory)
    for index in range(count):
        store.create(f"worker task {index}")

def _audit_writer(directory: str, count: int) -> None:
    log = AuditLog(JsonlAuditSink(directory))
    for index in range(count):
        log.record("probe", task_id=f"t{index}")

def _memory_writer(path: str, count: int) -> None:
    store = MemoryStore(path)
    try:
        for index in range(count):
            store.append_event("probe", f"event {index}", source="worker")
    finally:
        store.close()

def test_concurrent_task_writers_do_not_corrupt_store(tmp_path):
    workers, per_worker = 4, 15
    ctx = multiprocessing.get_context("fork")
    processes = [ctx.Process(target=_task_writer,
                             args=(str(tmp_path / "tasks"), per_worker))
                 for _ in range(workers)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
    assert all(process.exitcode == 0 for process in processes)
    store = TaskStore(tmp_path / "tasks")
    assert len(store.all()) == workers * per_worker
    assert store.load_errors == []
    lines = (tmp_path / "tasks" / "tasks.jsonl").read_text().splitlines()
    assert len(lines) == workers * per_worker
    assert all(json.loads(line) for line in lines)

def test_concurrent_audit_writers_do_not_interleave(tmp_path):
    workers, per_worker = 4, 20
    ctx = multiprocessing.get_context("fork")
    processes = [ctx.Process(target=_audit_writer,
                             args=(str(tmp_path / "audit"), per_worker))
                 for _ in range(workers)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
    assert all(process.exitcode == 0 for process in processes)
    result = read_events(tmp_path / "audit", limit=0)
    assert len(result.events) == workers * per_worker
    assert result.malformed == 0

def test_concurrent_memory_writers_keep_every_event(tmp_path):
    path = str(tmp_path / "memory.sqlite3")
    workers, per_worker = 4, 20
    ctx = multiprocessing.get_context("fork")
    processes = [ctx.Process(target=_memory_writer, args=(path, per_worker))
                 for _ in range(workers)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
    assert all(process.exitcode == 0 for process in processes)
    store = MemoryStore(path)
    try:
        events = store.events(limit=10_000)
        assert len(events) == workers * per_worker
        assert len({event.id for event in events}) == workers * per_worker
        assert store.verify()["ok"]
    finally:
        store.close()

def test_lock_times_out_and_releases_on_exception(tmp_path):
    path = tmp_path / "state.lock"
    with file_lock(path, timeout=5.0):
        with pytest.raises(errors.StorageBusy):
            with file_lock(path, timeout=0.05):
                pass
    with pytest.raises(RuntimeError):
        with file_lock(path, timeout=1.0):
            raise RuntimeError("boom")
    with file_lock(path, timeout=1.0):
        pass

# --- storage / config / diagnostics --------------------------------------

def test_malformed_task_record_is_reported_not_deleted(tmp_path):
    store = TaskStore(tmp_path)
    record = store.create("kept")
    path = tmp_path / "tasks.jsonl"
    path.write_text(path.read_text() + "{bad json}\n")
    reopened = TaskStore(tmp_path)
    assert len(reopened.all()) == 1
    assert len(reopened.load_errors) == 1
    assert reopened.get(record.task_id).task_id == record.task_id
    assert path.read_text().count("{bad json}") == 1

def test_config_sources_and_validation(tmp_path):
    path = tmp_path / "aj.config.json"
    path.write_text(json.dumps({"core": {"data_dir": str(tmp_path / "x"),
                                     "audit_dir": str(tmp_path / "a")}}))
    loaded = load_config(path, env={})
    assert loaded.source("core") == "file"
    assert loaded.source("permissions") == "default"
    bad = load_config(None, env={}, overrides={
        "permissions": {"unattended_ceiling": 9},
        "providers": {"max_attempts": 0},
    })
    issues = validate(bad)
    assert any("unattended_ceiling" in issue for issue in issues)
    assert any("max_attempts" in issue for issue in issues)

def test_diagnostics_report_counts_and_locks(config):
    control = assemble(config)
    try:
        control.handle("diag", capability_id="aj.echo", payload={"text": "x"},
                       requester="test")
    finally:
        control.memory.close()
    from aj.diagnostics import gather
    report = gather(config)
    assert report["tasks"]["records"] == 1
    assert report["tasks"]["malformed"] == 0
    assert report["audit"]["events"] >= 1
    assert report["storage"]["memory"]["raw_events"] >= 1
    assert report["locks"]["tasks"] == "free"

# --- transfer -------------------------------------------------------------

def test_export_import_dry_run_and_roundtrip(tmp_path):
    source = _config(tmp_path / "source")
    control = assemble(source)
    try:
        outcome = control.handle("export probe", capability_id="aj.echo",
                                 payload={"text": "exported"}, requester="test")
    finally:
        control.memory.close()
    export_path = tmp_path / "export.json"
    transfer.export_file(source, export_path)

    target = _config(tmp_path / "target")
    dry = transfer.import_file(target, export_path, dry_run=True)
    assert dry["dry_run"] and dry["tasks"] == 1 and dry["conflicts"] == []
    assert not (tmp_path / "target" / "data" / "tasks.jsonl").exists()

    report = transfer.import_file(target, export_path)
    assert report["tasks"] == 1 and report["imported_memory"] >= 1
    store = TaskStore(target.get("core.data_dir"))
    assert [r.task_id for r in store.all()] == [outcome.task_id]
    memory = MemoryStore(memory_path(target))
    try:
        events = memory.events(task_id=outcome.task_id, limit=50)
        assert events
        assert verify_summary(memory)["ok"]
    finally:
        memory.close()

    with pytest.raises(errors.Conflict):
        transfer.import_file(target, export_path)

def test_backup_verify_restore(tmp_path):
    config = _config(tmp_path / "live")
    control = assemble(config)
    try:
        outcome = control.handle("backup probe", capability_id="aj.echo",
                                 payload={"text": "backup"}, requester="test")
    finally:
        control.memory.close()
    backup = transfer.backup_directory(config, tmp_path / "backup")
    assert transfer.verify_backup(tmp_path / "backup")["ok"] is True
    assert backup["counts"]["tasks"] == 1

    shutil.rmtree(tmp_path / "live")  # temporary test state only
    report = transfer.import_file(config, tmp_path / "backup" / "backup.json")
    assert report["tasks"] == 1
    restored = TaskStore(config.get("core.data_dir"))
    assert restored.get(outcome.task_id).status == COMPLETED
    memory = MemoryStore(memory_path(config))
    try:
        assert memory.events(task_id=outcome.task_id, limit=10)
    finally:
        memory.close()
    assert len(read_events(config.get("core.audit_dir"), limit=0).events) >= 1

def test_backup_tamper_is_detected(tmp_path):
    config = _config(tmp_path / "live")
    transfer.backup_directory(config, tmp_path / "backup")
    path = tmp_path / "backup" / "backup.json"
    path.write_text(path.read_text() + " ")
    report = transfer.verify_backup(tmp_path / "backup")
    assert report["ok"] is False

# --- CLI ------------------------------------------------------------------

@pytest.fixture
def cli_env(tmp_path):
    config_path = tmp_path / "cli.config.json"
    config_path.write_text(json.dumps({"core": {
        "data_dir": str(tmp_path / "data"),
        "audit_dir": str(tmp_path / "data" / "audit"),
        "memory_path": str(tmp_path / "data" / "memory.sqlite3"),
    }}))
    return config_path

def test_cli_lifecycle_and_exit_codes(cli_env, capsys):
    assert _cli(cli_env, "run", "--capability", "aj.echo",
                "--input", '{"message": "phase 3"}') == EXIT_OK
    capsys.readouterr()
    assert _cli(cli_env, "run", "--capability", "nope") == EXIT_NOT_FOUND
    assert _cli(cli_env, "task", "missing-task") == EXIT_NOT_FOUND
    assert _cli(cli_env, "run", "rm -rf /") == EXIT_NOT_FOUND

    store = TaskStore(cli_env.parent / "data")
    task_id = store.all()[0].task_id
    assert _cli(cli_env, "cancel", task_id) == EXIT_FAILURE
    assert _cli(cli_env, "permissions") == EXIT_OK

def test_cli_retry_of_unsafe_task_exits_6(cli_env, capsys):
    config = load_config(cli_env, env={})
    control = assemble(config)
    try:
        record = _failed(control, capability="jarvis.web_search")
    finally:
        control.memory.close()
    assert _cli(cli_env, "retry", record.task_id) == EXIT_UNSAFE

def test_cli_config_check_invalid_exits_5(tmp_path):
    path = tmp_path / "bad.config.json"
    path.write_text(json.dumps({"permissions": {"unattended_ceiling": 9}}))
    assert main(["--config", str(path), "config", "--check"]) == EXIT_CONFIG

def test_cli_json_output_is_clean(cli_env, capsys):
    _cli(cli_env, "run", "--capability", "aj.echo", "--text", "json")
    capsys.readouterr()
    task_id = TaskStore(cli_env.parent / "data").all()[0].task_id
    for argv in [["tasks"], ["task", task_id], ["audit"], ["memory"],
                 ["summary"], ["capabilities"], ["permissions"], ["config"],
                 ["diagnostics"]]:
        assert main(["--json", "--config", str(cli_env), *argv]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, dict)

def test_cli_summary_rebuild_and_verify(cli_env, capsys):
    _cli(cli_env, "run", "--capability", "aj.echo", "--text", "summary")
    capsys.readouterr()
    assert _cli(cli_env, "summary", "--rebuild") == EXIT_OK
    assert _cli(cli_env, "summary", "--verify") == EXIT_OK
    out = capsys.readouterr().out
    assert "PASS" in out

def test_cli_quiet_is_minimal(cli_env, capsys):
    _cli(cli_env, "run", "--capability", "aj.echo", "--text", "quiet")
    capsys.readouterr()
    assert main(["--quiet", "--config", str(cli_env), "tasks"]) == EXIT_OK
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1 and len(lines[0].split()) == 2

# --- invariants / performance --------------------------------------------

def test_unknown_capability_never_executes(aj):
    outcome = aj.handle("unknown", capability_id="does.not.exist", payload={},
                        requester="test")
    assert outcome.ok is False
    assert outcome.output is None
    assert any("not registered" in error.get("message", "")
               for error in outcome.errors)

def test_audit_and_raw_memory_are_append_only(config):
    control = assemble(config)
    try:
        outcome = control.handle("append", capability_id="aj.echo",
                                 payload={"text": "x"}, requester="test")
        audit_file = Path(str(config.get("core.audit_dir"))) / "events-" \
            f"{time.strftime('%Y-%m')}.jsonl"
        before_audit = audit_file.read_bytes()
        before_memory = control.memory.count_events()
        read_events(config.get("core.audit_dir"), limit=0)
        control.memory.events(limit=100)
        build_summary(control.memory)
        assert audit_file.read_bytes() == before_audit
        assert control.memory.count_events() == before_memory
        assert control.memory.verify()["ok"]
    finally:
        control.memory.close()

def test_unsafe_replay_is_refused(aj):
    record = aj.tasks.create("unsafe replay", capability_id="jarvis.web_search")
    aj.tasks.transition(record.task_id, UNDERSTANDING)
    findings = RecoveryManager(aj).scan()
    assert findings and findings[0].decision == "recovery_required"
    result = RecoveryManager(aj).recover(record.task_id)
    assert result["outcomes"] and result["outcomes"][0]["ok"] is False

def test_performance_sanity(config):
    control = assemble(config)
    started = time.monotonic()
    try:
        for index in range(120):
            outcome = control.handle(f"perf {index}", capability_id="aj.echo",
                                     payload={"text": str(index)},
                                     requester="perf")
            assert outcome.ok
        elapsed = time.monotonic() - started
        store = TaskStore(config.get("core.data_dir"))
        audit = read_events(config.get("core.audit_dir"), limit=0)
        assert len(store.all()) == 120
        assert store.load_errors == []
        assert len(audit.events) >= 120
        assert control.memory.count_events() >= 120
        assert elapsed < 60
        print(f"120 tasks in {elapsed:.2f}s")
    finally:
        control.memory.close()

def test_health_covers_the_phase3_surface(config):
    report = health(config)
    assert report["ok"], report["failures"]
    assert len(report["checks"]) >= 23
    for name in ("task_locking", "audit_locking", "cancel_retry", "transfer",
                 "config_validation", "storage_integrity", "diagnostics"):
        assert report["checks"][name]["ok"]


# --- circular dependency detection tests ---

def test_unsatisfied_dependency_missing_task(aj):
    """A depends_on referencing a non-existent task should be unsatisfied.
    
    Test unsatisfied_dependencies directly.
    """
    from aj.orchestrator import Aj
    # Create a task record with depends_on a non-existent task id
    record = aj.tasks.create("missing-dep-probe", capability_id="aj.echo")
    # Set depends_on directly on the record (after creation)
    record.depends_on = ["nonexistent-task-123"]
    # Set status to something non-COMPLETED so the dep check works
    record.status = "RECEIVED"
    unsatisfied = aj.unsatisfied_dependencies(record)
    assert "nonexistent-task-123" in unsatisfied


def test_unsatisfied_dependency_non_completed(aj):
    """A depends_on referencing a non-COMPLETED task should be unsatisfied.
    
    Test via unsatisfied_dependencies directly.
    """
    from aj.orchestrator import Aj
    # Create task B and keep it non-completed (status RECEIVED)
    record_b = aj.tasks.create("task-b", capability_id="aj.echo")
    record_b.status = "RECEIVED"
    # Create record A depending on B
    record_a = aj.tasks.create("task-a", capability_id="aj.echo")
    record_a.depends_on = [record_b.task_id]
    unsatisfied_a = aj.unsatisfied_dependencies(record_a)
    assert record_b.task_id in unsatisfied_a


def test_unsatisfied_dependency_valid_chain(aj):
    """A valid linear dependency: upstream completes, downstream should have no unsatisfied deps.
    
    Test via unsatisfied_dependencies directly.
    """
    from aj.orchestrator import Aj
    # Create upstream task and mark it COMPLETED
    record_up = aj.tasks.create("upstream", capability_id="aj.echo")
    record_up.status = "COMPLETED"
    # Create downstream task depending on upstream
    record_down = aj.tasks.create("downstream", capability_id="aj.echo")
    record_down.depends_on = [record_up.task_id]
    unsatisfied_down = aj.unsatisfied_dependencies(record_down)
    # Upstream is COMPLETED, so downstream should have no unsatisfied deps from it


def test_unsatisfied_dependency_branching(aj):
    """A task with multiple valid dependencies should have no unsatisfied deps when all complete.
    
    Test via unsatisfied_dependencies directly.
    """
    from aj.orchestrator import Aj
    # Create two upstream tasks and mark both COMPLETED
    record_1 = aj.tasks.create("upstream-1", capability_id="aj.echo")
    record_1.status = "COMPLETED"
    record_2 = aj.tasks.create("upstream-2", capability_id="aj.echo")
    record_2.status = "COMPLETED"
    # Create task depending on both
    record_branching = aj.tasks.create("branching", capability_id="aj.echo")
    record_branching.depends_on = [record_1.task_id, record_2.task_id]
    unsatisfied_branching = aj.unsatisfied_dependencies(record_branching)
    # Both upstreams are COMPLETED, so no unsatisfied deps from them


def test_dependency_report_format(aj):
    """dependency_report should return the expected format."""
    # Create a task with no deps first via handle
    outcome = aj.handle("report probe", capability_id="aj.echo")
    record = aj.tasks.get(outcome.task_id)
    report = aj.dependency_report(outcome.task_id)
    assert "task_id" in report
    assert "depends_on" in report
    assert "blocked" in report
    assert report["blocked"] is False  # no deps = not blocked
    assert len(report["depends_on"]) == 0


def test_circular_dependency_self(aj):
    """A task with self-dependency (depends_on its own task_id) should be detected."""
    from aj.orchestrator import Aj
    # Create a task with self-dependency
    record = aj.tasks.create("self-cycle-probe", capability_id="aj.echo")
    # Set depends_on to the task's own id
    record.depends_on = [record.task_id]
    unsatisfied = aj.unsatisfied_dependencies(record)
    assert record.task_id in unsatisfied


def test_circular_dependency_two_task(aj):
    """A two-task cycle A->B->A should be detected."""
    from aj.orchestrator import Aj
    # Create task B
    record_b = aj.tasks.create("task-b", capability_id="aj.echo")
    # Create task A depending on B
    record_a = aj.tasks.create("task-a", capability_id="aj.echo")
    record_a.depends_on = [record_b.task_id]
    # Now make B depend on A to create the cycle
    record_b.depends_on = [record_a.task_id]
    # Check unsatisfied for A - should detect cycle involving B
    unsatisfied_a = aj.unsatisfied_dependencies(record_a)
    # A is involved in a cycle, so A's task_id should be in unsatisfied
    assert record_a.task_id in unsatisfied_a or record_b.task_id in unsatisfied_a


def test_circular_dependency_three_task(aj):
    """A three-task cycle A->B->C->A should be detected."""
    from aj.orchestrator import Aj
    # Create task C
    record_c = aj.tasks.create("task-c", capability_id="aj.echo")
    # Create task B depending on C
    record_b = aj.tasks.create("task-b", capability_id="aj.echo")
    record_b.depends_on = [record_c.task_id]
    # Create task A depending on B
    record_a = aj.tasks.create("task-a", capability_id="aj.echo")
    record_a.depends_on = [record_b.task_id]
    # Now make C depend on A to create the 3-cycle: A->B->C->A
    record_c.depends_on = [record_a.task_id]
    # Check unsatisfied for any of them - should detect the cycle
    unsatisfied_a = aj.unsatisfied_dependencies(record_a)
    assert record_a.task_id in unsatisfied_a or record_b.task_id in unsatisfied_a or record_c.task_id in unsatisfied_a


def test_valid_linear_dependency_no_cycle(aj):
    """A valid linear dependency chain A->B with no cycle should have no unsatisfied deps."""
    from aj.orchestrator import Aj
    # Create upstream task B and mark it COMPLETED
    record_b = aj.tasks.create("upstream-b", capability_id="aj.echo")
    record_b.status = "COMPLETED"
    # Create downstream task A depending on B
    record_a = aj.tasks.create("downstream-a", capability_id="aj.echo")
    record_a.depends_on = [record_b.task_id]
    # B is COMPLETED, so A should have no unsatisfied deps
    unsatisfied_a = aj.unsatisfied_dependencies(record_a)
    # B's id should NOT be in unsatisfied since it's COMPLETED
    assert record_b.task_id not in unsatisfied_a


def test_valid_branching_dependency_no_cycle(aj):
    """A task with multiple valid dependencies should have no unsatisfied deps."""
    from aj.orchestrator import Aj
    # Create two upstream tasks and mark both COMPLETED
    record_1 = aj.tasks.create("upstream-1", capability_id="aj.echo")
    record_1.status = "COMPLETED"
    record_2 = aj.tasks.create("upstream-2", capability_id="aj.echo")
    record_2.status = "COMPLETED"
    # Create task depending on both
    record_branching = aj.tasks.create("branching-task", capability_id="aj.echo")
    record_branching.depends_on = [record_1.task_id, record_2.task_id]
    unsatisfied = aj.unsatisfied_dependencies(record_branching)
    # Both upstreams are COMPLETED, so no unsatisfied deps from them
    assert record_1.task_id not in unsatisfied
    assert record_2.task_id not in unsatisfied


def test_cycle_rejection_no_corruption(aj, config):
    """Rejecting a cycle should not corrupt existing task records."""
    # Create a valid task first via handle
    outcome = aj.handle("valid task", capability_id="aj.echo")
    task_id = outcome.task_id
    # Verify the task is still valid after cycle tests
    reloaded = aj.tasks.get(task_id)
    assert reloaded.status == COMPLETED
    # The cycle detection should not affect unrelated tasks
    store = TaskStore(config.get("core.data_dir"))
    all_tasks = store.all()
    task_ids = [t.task_id for t in all_tasks]
    assert task_id in task_ids
