"""AJ command line: operate the local control plane.

    python -m aj --check
    python -m aj run --capability aj.echo --input '{"message":"hello"}'
    python -m aj tasks [--status COMPLETED] [--limit 20]
    python -m aj task <task-id>
    python -m aj cancel <task-id>
    python -m aj retry <task-id>
    python -m aj audit [--task <id>] [--event authorized] [--limit 50]
    python -m aj memory [--task <id>] [--type task.completed] [--limit 50]
    python -m aj summary [--task <id>] [--rebuild] [--verify]
    python -m aj capabilities
    python -m aj permissions
    python -m aj config [--check]
    python -m aj diagnostics
    python -m aj export --output <file>
    python -m aj import <file> [--dry-run]
    python -m aj backup --output <dir> | --verify <dir>
    python -m aj recover [--task <id>]
    python -m aj orb [--inbox-root <dir>] [--check-gui] [--system-python] [--debug]
    python -m aj inbox <capture|list|show|process|retry|archive|annotate|summary|orb|view|worker|autostart-install|autostart-remove>

Exit codes: 0 success, 1 operational failure, 2 invalid usage, 3 permission
denied, 4 not found, 5 configuration/storage failure, 6 unsafe operation.

Foreground only. No socket, no daemon, no network, no credential. ``run`` is not
a shell: it can execute only registered internal actions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, errors, transfer
from .audit import read_events
from .config import Config, load as load_config, validate as validate_config
from .diagnostics import gather as gather_diagnostics
from .errors import AjError
from .memory import MemoryStore
from .recovery import RecoveryManager
from .runtime import (
    assemble,
    configure_logging,
    health,
    memory_path,
    run_demo,
)
from .summary import build as build_summary, digest, verify as verify_summary
from .inbox_cli import add_inbox_parser, cmd_inbox
from .task import TaskStore

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_PERMISSION = 3
EXIT_NOT_FOUND = 4
EXIT_CONFIG = 5
EXIT_UNSAFE = 6

_NOT_FOUND_CODES = {errors.CAPABILITY_NOT_FOUND, "task_not_found"}
_PERMISSION_CODES = {
    getattr(errors, name) for name in
    ("POLICY_DENIED", "APPROVAL_REQUIRED", "APPROVAL_INVALID")
    if hasattr(errors, name)
}
_CONFIG_CODES = {
    errors.CONFIG_INVALID, errors.STORAGE_ERROR, errors.STORAGE_BUSY,
    errors.CONFLICT,
}
_UNSAFE_CODES = {errors.RETRY_UNSAFE, errors.RECOVERY_REQUIRED}


def exit_code_for(exc: AjError) -> int:
    if exc.code in _UNSAFE_CODES:
        return EXIT_UNSAFE
    if exc.code in _PERMISSION_CODES:
        return EXIT_PERMISSION
    if exc.code in _NOT_FOUND_CODES:
        return EXIT_NOT_FOUND
    if exc.code in _CONFIG_CODES:
        return EXIT_CONFIG
    return EXIT_FAILURE


# --- output --------------------------------------------------------------
def _emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def _iso(timestamp: Any) -> str:
    if not timestamp:
        return ""
    try:
        return datetime.fromtimestamp(float(timestamp)).astimezone().isoformat(
            timespec="seconds"
        )
    except (TypeError, ValueError, OSError):
        return str(timestamp)


def _print_run(outcome) -> None:
    print(f"Task: {outcome.task_id}")
    print(f"Capability: {outcome.capability_id or '-'}")
    print(f"Status: {outcome.status}")
    print(f"Summary: {outcome.summary}")
    if outcome.output is not None:
        print("Output: " + json.dumps(outcome.output, ensure_ascii=False,
                                      default=str))


def _print_task(record: Dict[str, Any]) -> None:
    print(f"Task: {record['task_id']}")
    print(f"Status: {record['status']}")
    print(f"Goal: {record['goal']}")
    print(f"Requester: {record['requester']}  Owner: {record['owner_agent']}")
    print(f"Capability: {record['capability_id'] or '-'}")
    print(f"Operation: {record.get('operation_id', '') or '-'}  "
          f"Parent: {record.get('parent_task_id') or '-'}  "
          f"Attempt: {record['attempt']}/{record['max_attempts']}")
    print(f"Created: {_iso(record['created_at'])}  Updated: "
          f"{_iso(record['updated_at'])}")
    if record.get("summary"):
        print(f"Summary: {record['summary']}")
    if record.get("requires_user_decision"):
        print("Attention: requires a user decision")
    if record.get("errors"):
        print("Errors:")
        for error in record["errors"]:
            print(f"  - {error.get('code', '?')}: {error.get('message', '')}")
    attempts = record.get("attempts") or []
    if attempts:
        print("Attempts:")
        for attempt in attempts:
            failure = attempt.get("failure") or {}
            detail = f" failure={failure.get('code', '')}" if failure else ""
            print(f"  {attempt.get('attempt_number')}  {attempt.get('status')}"
                  f"  {_iso(attempt.get('started_at'))} -> "
                  f"{_iso(attempt.get('ended_at'))}{detail}")
    if record.get("warnings"):
        print("Notes:")
        for warning in record["warnings"]:
            print(f"  - {warning}")
    print("Transitions:")
    for event in record.get("events", []):
        detail = f"  ({event['detail']})" if event.get("detail") else ""
        print(f"  {_iso(event.get('at'))}  {event.get('status')}{detail}")


def _print_tasks(records: List[Dict[str, Any]]) -> None:
    if not records:
        print("No persisted tasks.")
        return
    print(f"{'TASK ID':<34} {'STATUS':<20} {'CAPABILITY':<24} CREATED")
    for record in records:
        print(f"{record['task_id']:<34} {record['status']:<20} "
              f"{(record['capability_id'] or '-'):<24} "
              f"{_iso(record['created_at'])}")


def _print_audit(events: List[Dict[str, Any]], malformed: int) -> None:
    if not events:
        print("No audit events.")
    for event in events:
        print(f"{event.get('at', '')}  {event.get('action', ''):<18} "
              f"{event.get('agent', ''):<7} {event.get('task_id', '') or '-':<34} "
              f"{event.get('result', '')}")
    if malformed:
        print(f"WARNING: {malformed} malformed audit line(s) were skipped, "
              "not rewritten.", file=sys.stderr)


def _print_memory(events: List[Dict[str, Any]]) -> None:
    if not events:
        print("No raw memory events.")
        return
    print(f"{'ID':>5}  {'WHEN':<25} {'KIND':<20} {'TASK':<34} PREVIEW")
    for event in events:
        preview = str(event.get("content", ""))[:40].replace("\n", " ")
        print(f"{event['id']:>5}  {_iso(event.get('at')):<25} "
              f"{event.get('kind', ''):<20} "
              f"{(event.get('task_id') or '-'):<34} {preview}")


# --- parser --------------------------------------------------------------
def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aj",
        description="AJ local orchestration core (provider-independent).",
    )
    parser.add_argument("--version", action="store_true", help="print the AJ version")
    parser.add_argument("--check", action="store_true",
                        help="run local foundation self-checks (no network)")
    parser.add_argument("--demo", action="store_true",
                        help="run one complete lifecycle with the safe echo capability")
    parser.add_argument("--list-capabilities", action="store_true",
                        help="alias for 'capabilities'")
    parser.add_argument("--config", default="", help="path to an AJ config file")
    parser.add_argument("--log-level", default="",
                        help="override the configured log level")
    parser.add_argument("--json", action="store_true", default=False,
                        help="print machine-readable JSON")
    parser.add_argument("--quiet", action="store_true", default=False,
                        help="print only essential result lines")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="print extra diagnostics to stderr")

    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="execute one registered internal capability")
    run.add_argument("goal", nargs="?", default="",
                     help="goal text; 'echo ...' maps to aj.echo")
    run.add_argument("--capability", default="",
                     help="capability id (must be an internal action)")
    run.add_argument("--input", default="", help="JSON object of arguments")
    run.add_argument("--text", default="", help="shorthand for {\"text\": ...}")
    _add_json(run)

    tasks = sub.add_parser("tasks", help="list persisted tasks")
    tasks.add_argument("--status", default="", help="filter by task status")
    tasks.add_argument("--limit", type=int, default=20, help="max records (0 = all)")
    _add_json(tasks)

    task = sub.add_parser("task", help="show one persisted task in full")
    task.add_argument("task_id")
    _add_json(task)

    cancel = sub.add_parser("cancel", help="cancel a non-final task")
    cancel.add_argument("task_id")
    _add_json(cancel)

    retry = sub.add_parser("retry", help="retry a failed, retry-safe task")
    retry.add_argument("task_id")
    _add_json(retry)

    audit = sub.add_parser("audit", help="read persisted audit events")
    audit.add_argument("--limit", type=int, default=50)
    audit.add_argument("--task", default="", help="filter by task id")
    audit.add_argument("--event", default="", help="filter by action, e.g. authorized")
    audit.add_argument("--agent", default="", help="filter by agent")
    _add_json(audit)

    memory = sub.add_parser("memory", help="read canonical raw memory events")
    memory.add_argument("--limit", type=int, default=50)
    memory.add_argument("--task", default="", help="filter by task id")
    memory.add_argument("--type", default="", dest="event_type",
                        help="filter by event kind, e.g. task.completed")
    _add_json(memory)

    summary = sub.add_parser("summary", help="show, rebuild or verify derived summaries")
    summary.add_argument("--task", default="", help="scope to one task")
    summary.add_argument("--limit", type=int, default=10)
    summary.add_argument("--rebuild", action="store_true",
                         help="deterministically rebuild from raw events")
    summary.add_argument("--verify", action="store_true",
                         help="verify stored summary matches a fresh rebuild")
    _add_json(summary)

    capabilities = sub.add_parser("capabilities", help="list registered capabilities")
    _add_json(capabilities)

    permissions = sub.add_parser("permissions", help="show the permission policy")
    _add_json(permissions)

    config = sub.add_parser("config", help="show effective configuration")
    config.add_argument("--check", action="store_true", dest="check_config",
                        help="validate configuration")
    _add_json(config)

    diagnostics = sub.add_parser("diagnostics", help="local storage and lock diagnostics")
    _add_json(diagnostics)

    export = sub.add_parser("export", help="export local state to a JSON file")
    export.add_argument("--output", required=True)
    _add_json(export)

    importer = sub.add_parser("import", help="import an export conservatively")
    importer.add_argument("source")
    importer.add_argument("--dry-run", action="store_true",
                          help="validate and report without writing")
    _add_json(importer)

    backup = sub.add_parser("backup", help="create or verify a local backup")
    backup.add_argument("--output", default="", help="backup directory")
    backup.add_argument("--verify", default="", help="verify an existing backup dir")
    _add_json(backup)

    recover = sub.add_parser("recover", help="scan persisted tasks and replay safe ones")
    recover.add_argument("--task", default="", help="recover one specific task")
    _add_json(recover)

    orb = sub.add_parser("orb", help="launch the AJ floating capture orb (desktop GUI)")
    orb.add_argument("--inbox-root", dest="inbox_root", default="", help="override canonical inbox root")
    orb.add_argument("--debug", action="store_true", help="verbose orb diagnostics to stderr")
    orb.add_argument("--check-gui", action="store_true", help="check GTK/runtime dependencies and exit")
    orb.add_argument("--system-python", action="store_true",
                     help="launch via system python (/usr/bin/python3) for GTK if current interpreter lacks gi")
    _add_json(orb)

    add_inbox_parser(sub)
    return parser


# --- config helpers ------------------------------------------------------
def _tasks_dir(config: Config) -> Path:
    return Path(str(config.get("core.data_dir"))).expanduser()


def _audit_dir(config: Config) -> Path:
    return Path(str(config.get("core.audit_dir"))).expanduser()


def _memory(config: Config) -> Optional[MemoryStore]:
    path = memory_path(config)
    if not path.is_file():
        return None
    return MemoryStore(path)


# --- commands ------------------------------------------------------------
def _cmd_run(config: Config, args) -> int:
    payload: Dict[str, Any] = {}
    if args.input:
        try:
            parsed = json.loads(args.input)
        except ValueError as exc:
            raise AjError(f"--input must be a JSON object: {exc}",
                          code=errors.CONFIG_INVALID) from exc
        if not isinstance(parsed, dict):
            raise AjError("--input must be a JSON object", code=errors.CONFIG_INVALID)
        payload = parsed

    capability = (args.capability or "").strip()
    goal = (args.goal or "").strip()
    if not capability:
        if goal.lower().startswith("echo "):
            capability = "aj.echo"
            payload.setdefault("text", goal[5:].strip())
        elif goal:
            raise errors.CapabilityNotFound(
                "run needs --capability: only registered internal actions may execute"
            )
        else:
            raise AjError("run needs a goal or --capability",
                          code=errors.CONFIG_INVALID)
    if args.text:
        payload["text"] = args.text

    aj = assemble(config)
    try:
        spec = aj.registry.find(capability)
        if spec is None:
            raise errors.CapabilityNotFound(
                f"capability {capability!r} is not registered")
        if not spec.execution_adapter.startswith("internal:"):
            raise errors.CapabilityUnavailable(
                f"capability {capability!r} is not an internal action; "
                "external capabilities cannot run from this CLI"
            )
        outcome = aj.handle(goal or f"run {capability}", capability_id=capability,
                            payload=payload, requester="cli")
        if getattr(args, "json", False):
            _emit(outcome.to_dict())
        elif getattr(args, "quiet", False):
            print(f"{outcome.task_id} {outcome.status}")
        else:
            _print_run(outcome)
        return EXIT_OK if outcome.ok else EXIT_FAILURE
    finally:
        if aj.memory is not None:
            aj.memory.close()


def _cmd_tasks(config: Config, args) -> int:
    store = TaskStore(_tasks_dir(config))
    records = [record.to_dict() for record in
               store.query(status=args.status, limit=args.limit)]
    if getattr(args, "json", False):
        _emit({"tasks": records, "load_errors": store.load_errors})
    elif getattr(args, "quiet", False):
        for record in records:
            print(f"{record['task_id']} {record['status']}")
    else:
        _print_tasks(records)
        if store.load_errors:
            print(f"WARNING: {len(store.load_errors)} malformed persisted "
                  "record(s) were skipped, not deleted.", file=sys.stderr)
    return EXIT_OK


def _cmd_task(config: Config, args) -> int:
    store = TaskStore(_tasks_dir(config))
    record = store.get(args.task_id).to_dict()
    if getattr(args, "json", False):
        _emit({"task": record, "load_errors": store.load_errors})
    else:
        _print_task(record)
        if store.load_errors:
            print(f"WARNING: {len(store.load_errors)} malformed persisted "
                  "record(s) were skipped, not deleted.", file=sys.stderr)
    return EXIT_OK


def _cmd_cancel(config: Config, args) -> int:
    aj = assemble(config)
    try:
        outcome = aj.cancel_task(args.task_id)
        if getattr(args, "json", False):
            _emit(outcome.to_dict())
        elif getattr(args, "quiet", False):
            print(f"{outcome.task_id} {outcome.status}")
        else:
            print(f"Task: {outcome.task_id}")
            print(f"Status: {outcome.status}")
            print(f"Result: {outcome.summary}")
        return EXIT_OK if outcome.ok else EXIT_FAILURE
    finally:
        if aj.memory is not None:
            aj.memory.close()


def _cmd_retry(config: Config, args) -> int:
    aj = assemble(config)
    try:
        outcome = aj.retry(args.task_id)
        if getattr(args, "json", False):
            _emit(outcome.to_dict())
        elif getattr(args, "quiet", False):
            print(f"{outcome.task_id} {outcome.status}")
        else:
            _print_run(outcome)
        if outcome.ok:
            return EXIT_OK
        return EXIT_UNSAFE if outcome.requires_user_decision and not outcome.ok \
            and "refused" in outcome.summary.lower() else EXIT_FAILURE
    finally:
        if aj.memory is not None:
            aj.memory.close()


def _cmd_audit(config: Config, args) -> int:
    result = read_events(_audit_dir(config), limit=args.limit,
                         task_id=args.task, action=args.event, agent=args.agent)
    if getattr(args, "json", False):
        _emit(result.to_dict())
    else:
        _print_audit(result.events, result.malformed)
    return EXIT_OK


def _cmd_memory(config: Config, args) -> int:
    path = memory_path(config)
    if not path.is_file():
        if getattr(args, "json", False):
            _emit({"events": [], "path": str(path), "exists": False})
        else:
            print(f"No raw memory store at {path}.")
        return EXIT_OK
    store = MemoryStore(path)
    try:
        events = [event.to_dict() for event in store.events(
            kind=args.event_type, task_id=args.task, limit=args.limit
        )]
        if getattr(args, "json", False):
            _emit({"events": events, "path": str(path), "exists": True,
                   "stats": store.stats()})
        else:
            _print_memory(events)
        return EXIT_OK
    finally:
        store.close()


def _cmd_summary(config: Config, args) -> int:
    path = memory_path(config)
    if not path.is_file():
        payload = {"ok": True, "exists": False, "path": str(path),
                   "summaries": []}
        _emit(payload) if getattr(args, "json", False) else print(
            f"No raw memory store at {path}.")
        return EXIT_OK
    store = MemoryStore(path)
    try:
        if args.verify:
            report = verify_summary(store, task_id=args.task)
            if getattr(args, "json", False):
                _emit(report)
            else:
                print(f"kind: {report['kind']}")
                print(f"stored: {report['stored_content'] is not None}")
                print(f"deterministic parity: {'PASS' if report['ok'] else 'FAIL'}")
                if not report["ok"]:
                    print(f"stored:  {report['stored_content']}")
                    print(f"rebuilt: {report['rebuilt_content']}")
            return EXIT_OK if report["ok"] else EXIT_FAILURE
        if args.rebuild:
            built = build_summary(store, task_id=args.task)
            if getattr(args, "json", False):
                _emit(built)
            else:
                print(f"summary_id: {built['summary_id']}")
                print(f"kind: {built['kind']}  source_events: "
                      f"{len(built['source_event_ids'])}")
                print(built["content"])
            return EXIT_OK
        if args.task:
            events = store.events(task_id=args.task, limit=1_000_000)
            payload = {"task_id": args.task, "digest": digest(events),
                       "source_event_ids": sorted(e.id for e in events)}
            if getattr(args, "json", False):
                _emit(payload)
            else:
                _emit(payload)
            return EXIT_OK
        rows = store.summaries(limit=args.limit)
        payload = {"summaries": rows, "stats": store.stats()}
        if getattr(args, "json", False):
            _emit(payload)
        elif getattr(args, "quiet", False):
            for row in rows:
                print(f"{row['id']} {row['kind']}")
        else:
            if not rows:
                print("No stored summaries.")
            for row in rows:
                print(f"#{row['id']}  {_iso(row.get('at'))}  {row.get('kind')}  "
                      f"events={len(row.get('source_event_ids') or [])}")
        return EXIT_OK
    finally:
        store.close()


def _cmd_capabilities(config: Config, args) -> int:
    aj = assemble(config, ephemeral_memory=True)
    dispatch = {spec.capability_id: aj.dispatch_of(spec) for spec in aj.registry.all()}
    payload = {
        "capabilities": [
            {
                "capability_id": spec.capability_id,
                "name": spec.name,
                "description": spec.description,
                "owner_agent": spec.owner_agent,
                "risk_level": spec.risk_level,
                "availability": spec.availability,
                "verification_status": spec.verification_status,
                "execution_adapter": spec.execution_adapter,
                "internal": spec.execution_adapter.startswith("internal:"),
                "dispatchable": dispatch[spec.capability_id][0],
                "dispatch_reason": dispatch[spec.capability_id][1],
                "replay_safe": spec.replay_safe,
                "retry_safe": spec.retry_safe,
                "input_schema": getattr(spec, "input_schema", {}),
            }
            for spec in aj.registry.all()
        ],
        "agents": aj.agents.status(),
        "execution": aj.execution.describe(),
        "internal_actions": aj.actions.names(),
    }
    if getattr(args, "json", False):
        _emit(payload)
    else:
        for spec in payload["capabilities"]:
            print(f"{spec['capability_id']}")
            print(f"  name: {spec['name']}")
            print(f"  owner: {spec['owner_agent']}  risk: {spec['risk_level']}")
            print(f"  internal: {str(spec['internal']).lower()}  "
                  f"replay_safe: {str(spec['replay_safe']).lower()}  "
                  f"retry_safe: {str(spec['retry_safe']).lower()}")
            print(f"  availability: {spec['availability']}")
            if spec["dispatchable"]:
                print(f"  dispatchable: true ({spec['dispatch_reason']})")
            else:
                print(f"  dispatchable: false ({spec['dispatch_reason']})")
    return EXIT_OK


LEVEL_NAMES = {
    0: "read / allow",
    1: "internal write / allow",
    2: "local state change / allow",
    3: "external action / confirm",
    4: "dangerous / deny",
}


def _cmd_permissions(config: Config, args) -> int:
    aj = assemble(config, ephemeral_memory=True)
    payload = {
        "unattended_ceiling": config.get("permissions.unattended_ceiling"),
        "approval_ttl_seconds": config.get("permissions.approval_ttl_seconds"),
        "levels": {str(k): v for k, v in LEVEL_NAMES.items()},
        "capabilities": [
            {"capability_id": spec.capability_id, "risk_level": spec.risk_level,
             "policy": LEVEL_NAMES.get(spec.risk_level, "unknown")}
            for spec in aj.registry.all()
        ],
        "note": "inspection only; this command never grants permissions",
    }
    if getattr(args, "json", False):
        _emit(payload)
    else:
        print(f"unattended_ceiling: {payload['unattended_ceiling']}")
        print(f"approval_ttl_seconds: {payload['approval_ttl_seconds']}")
        for level, name in LEVEL_NAMES.items():
            print(f"  {level}: {name}")
        print(payload["note"])
    return EXIT_OK


def _cmd_config(config: Config, args) -> int:
    if args.check_config:
        issues = validate_config(config)
        payload = {"ok": not issues, "issues": issues,
                   "sources": getattr(config, "sources", {})}
        if getattr(args, "json", False):
            _emit(payload)
        else:
            print("configuration: " + ("VALID" if not issues else "INVALID"))
            for issue in issues:
                print(f"  - {issue}")
        return EXIT_OK if not issues else EXIT_CONFIG
    payload = {
        "config": transfer._redact_object(config.as_dict()),
        "sources": getattr(config, "sources", {}),
    }
    _emit(payload)
    return EXIT_OK


def _cmd_diagnostics(config: Config, args) -> int:
    payload = gather_diagnostics(config)
    if getattr(args, "json", False):
        _emit(payload)
    elif getattr(args, "quiet", False):
        print(f"tasks={payload['tasks']['records']} "
              f"audit={payload['audit']['events']} "
              f"memory={payload['storage']['memory'].get('raw_events', 0)}")
    else:
        _emit(payload)
    return EXIT_OK


def _cmd_export(config: Config, args) -> int:
    result = transfer.export_file(config, args.output)
    if getattr(args, "json", False):
        _emit(result)
    else:
        print(f"exported to {result['path']}")
        print(f"counts: {result['counts']}")
    return EXIT_OK


def _cmd_import(config: Config, args) -> int:
    report = transfer.import_file(config, args.source, dry_run=args.dry_run)
    if getattr(args, "json", False):
        _emit(report)
    else:
        print(f"{'dry run' if report['dry_run'] else 'imported'}: {report['source']}")
        print(f"tasks: {report['tasks']}  audit: {report['audit']}  "
              f"memory: {report['memory']}  "
              f"duplicate memory skipped: {report['memory_duplicates_skipped']}")
        print("conflicts: " + (", ".join(report["conflicts"]) or "none"))
    return EXIT_OK


def _cmd_backup(config: Config, args) -> int:
    if args.verify:
        report = transfer.verify_backup(args.verify)
        if getattr(args, "json", False):
            _emit(report)
        else:
            print("backup: " + ("VALID" if report["ok"] else "INVALID"))
            for problem in report["problems"]:
                print(f"  - {problem}")
        return EXIT_OK if report["ok"] else EXIT_FAILURE
    if not args.output:
        raise AjError("backup needs --output or --verify", code=errors.CONFIG_INVALID)
    result = transfer.backup_directory(config, args.output)
    if getattr(args, "json", False):
        _emit(result)
    else:
        print(f"backup written to {result['directory']}")
        print(f"sha256: {result['sha256']}")
    return EXIT_OK


def _cmd_recover(config: Config, args) -> int:
    aj = assemble(config)
    try:
        manager = RecoveryManager(aj)
        result = manager.recover(args.task or None)
        if getattr(args, "json", False):
            _emit(result)
        else:
            findings = result["findings"]
            if not findings:
                print("No interrupted tasks.")
            for finding in findings:
                print(f"{finding['task_id']}  {finding['status']:<20} "
                      f"{finding['decision']:<20} {finding['reason']}")
            for outcome in result["outcomes"]:
                print(f"recovered {outcome['task_id']}: {outcome['status']} "
                      f"({outcome['summary']})")
        if args.task:
            outcomes = result["outcomes"]
            return EXIT_OK if outcomes and outcomes[0]["ok"] else EXIT_FAILURE
        return EXIT_OK
    finally:
        if aj.memory is not None:
            aj.memory.close()



def _cmd_orb(config: Config, args) -> int:
    from .inbox import resolve_inbox_root
    explicit = getattr(args, "inbox_root", "") or None
    inbox_root = str(resolve_inbox_root(explicit=explicit, config=config))
    debug = bool(getattr(args, "debug", False))
    check_gui = bool(getattr(args, "check_gui", False))
    if check_gui:
        gtk_ok = False
        gtk_err = ""
        try:
            import gi  # noqa: F401
            gi.require_version("Gtk", "3.0")
            gi.require_version("Gdk", "3.0")
            from gi.repository import Gtk, Gdk  # noqa: F401
            gtk_ok = True
        except Exception as e:
            gtk_err = f"{type(e).__name__}: {e}"
        web_ok = False
        web_reason = ""
        try:
            from .orb import web_orb_available
            web_ok, web_reason = web_orb_available()
        except Exception as e:
            web_reason = f"{type(e).__name__}: {e}"
        payload = {
            "ok": bool(gtk_ok or web_ok),
            "gtk": bool(gtk_ok),
            "webkit": bool(web_ok),
            "ui": "web" if web_ok else ("gtk" if gtk_ok else "none"),
            "python": sys.executable,
            "inbox_root": inbox_root,
        }
        if web_ok:
            try:
                from .orb_web import dist_index_path
                payload["dist"] = str(dist_index_path())
            except Exception:
                pass
            payload["message"] = "WebKitGTK orb UI available"
        elif gtk_ok:
            payload["message"] = "GTK3 available in current interpreter (legacy orb fallback)"
        else:
            payload["error"] = gtk_err or web_reason
            payload["hint"] = "Use --system-python or run with an interpreter that has PyGObject/GTK3/WebKit2 and the orb_ui bundle."
        if getattr(args, "json", False):
            _emit(payload)
        else:
            if payload["ok"]:
                print(f"GUI: OK ({payload['python']}, ui={payload.get('ui')})")
                print(f"inbox_root: {inbox_root}")
                if web_reason and not web_ok:
                    print(f"note: web UI unavailable: {web_reason}")
            else:
                print(f"GUI: unavailable in {payload['python']}: {payload.get('error')}", file=sys.stderr)
                print(payload.get("hint", ""), file=sys.stderr)
        return EXIT_OK if payload["ok"] else EXIT_CONFIG

    # Prefer current interpreter if GTK available; otherwise try system python fallback.
    def _gtk_available_here() -> bool:
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            gi.require_version("Gdk", "3.0")
            from gi.repository import Gtk  # noqa: F401
            return True
        except Exception:
            return False

    if not getattr(args, "system_python", False) and _gtk_available_here():
        from .orb import run_orb
        run_orb(inbox_root=inbox_root, config=config, debug=debug)
        return EXIT_OK

    # Fallback: launch canonical AJ source with system python that has GTK bindings.
    import subprocess, os
    aj_root = Path(__file__).resolve().parent.parent
    sys_py = "/usr/bin/python3"
    if not Path(sys_py).exists():
        raise AjError("GTK unavailable in current interpreter and system python3 not found",
                      code=errors.CONFIG_INVALID)
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(aj_root) + (os.pathsep + existing_pp if existing_pp else "")
    cmd = [sys_py, "-m", "aj.orb", "--inbox-root", inbox_root]
    if debug:
        cmd.append("--debug")
    if getattr(args, "json", False):
        _emit({"ok": True, "launching": cmd, "inbox_root": inbox_root, "mode": "system-python"})
    elif not getattr(args, "quiet", False):
        print(f"Launching AJ Orb via system Python: {sys_py}")
        print(f"Inbox root: {inbox_root}")
    proc = subprocess.run(cmd, cwd=str(aj_root), env=env)
    return EXIT_OK if proc.returncode == 0 else EXIT_FAILURE


_COMMANDS = {
    "run": _cmd_run,
    "tasks": _cmd_tasks,
    "task": _cmd_task,
    "cancel": _cmd_cancel,
    "retry": _cmd_retry,
    "audit": _cmd_audit,
    "memory": _cmd_memory,
    "summary": _cmd_summary,
    "capabilities": _cmd_capabilities,
    "permissions": _cmd_permissions,
    "config": _cmd_config,
    "diagnostics": _cmd_diagnostics,
    "export": _cmd_export,
    "import": _cmd_import,
    "backup": _cmd_backup,
    "recover": _cmd_recover,
    "orb": _cmd_orb,
    "inbox": cmd_inbox,
}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        _emit({"version": __version__})
        return EXIT_OK
    if args.check:
        report = health(load_config(args.config or None))
        _emit(report)
        return EXIT_OK if report["ok"] else EXIT_FAILURE
    if args.demo:
        result = run_demo(load_config(args.config or None))
        _emit(result)
        return EXIT_OK if result["outcome"]["ok"] else EXIT_FAILURE
    if args.list_capabilities and not args.command:
        args.command = "capabilities"
    if not args.command:
        build_parser().print_help(sys.stdout)
        return EXIT_USAGE

    config = load_config(args.config or None)
    configure_logging(args.log_level or str(config.get("runtime.log_level", "info")))
    if getattr(args, "verbose", False):
        print(f"aj: data_dir={config.get('core.data_dir')} "
              f"audit_dir={config.get('core.audit_dir')}", file=sys.stderr)
    handler = _COMMANDS.get(args.command)
    if handler is None:  # pragma: no cover - argparse prevents this
        build_parser().print_help(sys.stdout)
        return EXIT_USAGE
    try:
        return handler(config, args)
    except AjError as exc:
        if getattr(args, "json", False):
            _emit({"ok": False, "error": exc.to_dict()})
        else:
            print(f"error [{exc.code}]: {exc}", file=sys.stderr)
        return exit_code_for(exc)
    except (OSError, ValueError) as exc:
        if getattr(args, "json", False):
            _emit({"ok": False, "error": {
                "code": "cli_error", "message": f"{type(exc).__name__}: {exc}"}})
        else:
            print(f"error [cli_error]: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":  # pragma: no cover - exercised through the module
    raise SystemExit(main())
