"""AJ runtime assembly and self-check.

This is the layer the CLI uses: it loads configuration, configures logging,
builds the registries, attaches local memory, and constructs the orchestrator.
Everything here is local and synchronous. No socket is bound, no daemon is
started, no network call is made.

``health()`` proves the foundation alone is alive: it needs no JARVIS, HELIX,
Hermes, Honcho, internet access or provider credential.
"""

from __future__ import annotations

import importlib
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import __version__, errors, transfer
from .actions import InternalActions, default_actions, specs as internal_specs
from .config import memory_path, validate as validate_config
from .diagnostics import gather as gather_diagnostics
from .agents import AgentRegistry
from .audit import AuditLog, JsonlAuditSink, MemoryAuditSink, read_events
from .capability import CapabilityRegistry
from .config import Config, load as load_config
from .execution import ExecutionPort, SkillRegistry, UnavailableExecutionAdapter
from .locking import file_lock
from .memory import MemoryStore
from .orchestrator import Aj, build
from .permissions import ALLOW, CONFIRM, DENY, ApprovalGate, Authorizer
from .providers import ChatRequest, Gateway, Message, ProviderRegistry
from .recovery import RecoveryManager
from .summary import build as build_summary, verify as verify_summary
from .task import (
    AUTHORIZED, CANCELLED, COMPLETED, EXECUTING, FAILED, PLANNED, RECEIVED,
    UNDERSTANDING, VERIFYING, TaskStore,
)

LOG = logging.getLogger("aj")

_MODULES = (
    "aj", "aj.actions", "aj.agents", "aj.audit", "aj.calling", "aj.capability",
    "aj.config", "aj.contracts", "aj.errors", "aj.execution", "aj.ids",
    "aj.integrations", "aj.integrations.gsconnect", "aj.integrations.jarvis_registry",
    "aj.memory", "aj.orchestrator", "aj.permissions", "aj.providers", "aj.runtime",
    "aj.task", "aj.locking", "aj.diagnostics", "aj.transfer",
)


# --- logging -------------------------------------------------------------
def configure_logging(level: str = "info") -> None:
    """Configure one stderr handler. Never logs configuration values."""
    resolved = getattr(logging, str(level or "info").upper(), logging.INFO)
    root = logging.getLogger("aj")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s event=%(message)s"
        ))
        root.addHandler(handler)
    root.setLevel(resolved)
    root.propagate = False


# --- paths ---------------------------------------------------------------
def build_memory(config: Config, *, ephemeral: bool = False) -> MemoryStore:
    """Open the canonical store. ``ephemeral`` stays entirely in memory."""
    if ephemeral:
        return MemoryStore(":memory:")
    return MemoryStore(memory_path(config))


def _build_execution(config: Config) -> ExecutionPort:
    """Select execution runtime; default is explicitly unattached/disabled."""
    runtime = str(config.get("execution.runtime", "none") or "none").strip().lower()
    ff = bool(config.get("feature_flags.hermes_execution_adapter", False))
    h = config.section("execution").get("hermes", {}) if isinstance(config.section("execution"), Mapping) else {}
    if not isinstance(h, Mapping):
        h = {}
    enabled = ff and runtime == "hermes_cli" and bool(h.get("enabled", False))
    cap_enabled = enabled and bool(h.get("capability_status_read_enabled", False))
    if not enabled:
        return UnavailableExecutionAdapter()
    try:
        from .hermes_adapter import HermesExecutionAdapter
        # Strict validation: fail closed on invalid/unsafe config (no permissive coercion).
        cli_path = h.get("cli_path", "hermes")
        if not isinstance(cli_path, str) or not cli_path.strip():
            raise errors.ConfigError("execution.hermes.cli_path must be a non-empty string")
        if isinstance(h.get("enabled"), bool) is False and "enabled" in h and not isinstance(h.get("enabled"), bool):
            raise errors.ConfigError("execution.hermes.enabled must be boolean")
        if "capability_status_read_enabled" in h and not isinstance(h.get("capability_status_read_enabled"), bool):
            raise errors.ConfigError("execution.hermes.capability_status_read_enabled must be boolean")
        return HermesExecutionAdapter(
            enabled=enabled,
            capability_enabled=cap_enabled,
            cli_path=cli_path,
            default_timeout_ms=h.get("default_timeout_ms", 10000),
            max_timeout_ms=h.get("max_timeout_ms", 30000),
            stdout_max_bytes=h.get("stdout_max_bytes", 8000),
            stderr_max_bytes=h.get("stderr_max_bytes", 4000),
            strict_config=True,
        )
    except Exception:
        # Fail closed: never attach a partially configured adapter.
        return UnavailableExecutionAdapter(reason="hermes execution adapter configuration is invalid or unavailable")


# --- assembly ------------------------------------------------------------
def assemble(
    config: Optional[Config] = None,
    *,
    memory: Optional[MemoryStore] = None,
    ephemeral_memory: bool = False,
    actions: Optional[InternalActions] = None,
    calling=None,
    execution: Optional[ExecutionPort] = None,
) -> Aj:
    """Build a usable control plane from configuration."""
    config = config or load_config()
    if memory is None and config.get("runtime.persist_memory", True):
        memory = build_memory(config, ephemeral=ephemeral_memory)
    port = execution or _build_execution(config)
    return build(config, memory=memory, actions=actions or default_actions(),
                 calling=calling, execution=port)


# --- health --------------------------------------------------------------
def _run_check(name: str, check) -> Dict[str, Any]:
    try:
        detail = check()
    except Exception as exc:  # a check that raises is a failed check
        LOG.debug("health check %s failed: %s", name, type(exc).__name__)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "detail": detail}


def _check_imports() -> Dict[str, Any]:
    for module in _MODULES:
        importlib.import_module(module)
    return {"modules": len(_MODULES)}


def _check_config(config: Config) -> Dict[str, Any]:
    sections = sorted(config.as_dict())
    for required in ("core", "permissions", "capability", "providers", "runtime"):
        if required not in sections:
            raise errors.ConfigError(f"configuration is missing section {required!r}")
    return {
        "sections": sections,
        "data_dir": str(config.get("core.data_dir")),
        "unattended_ceiling": config.get("permissions.unattended_ceiling"),
    }


def _check_tasks() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-lifecheck-") as directory:
        store = TaskStore(directory)
        record = store.create("health check task")
        for status in (UNDERSTANDING, PLANNED, AUTHORIZED, EXECUTING, VERIFYING):
            store.transition(record.task_id, status)
        store.transition(record.task_id, COMPLETED, "health check")
        return {"task_id": record.task_id, "status": record.status,
                "terminal": record.terminal}


def _check_permissions() -> Dict[str, Any]:
    class _Cap:
        def __init__(self, level: int, forbidden: bool = False):
            self.capability_id = "check.capability"
            self.risk_level = level
            self.forbidden = forbidden

    authorizer = Authorizer(gate=ApprovalGate())
    read = authorizer.authorize(_Cap(0))
    consequential = authorizer.authorize(_Cap(3))
    forbidden = authorizer.authorize(_Cap(3, forbidden=True), approval="x")
    if read.outcome != ALLOW or consequential.outcome != CONFIRM or forbidden.outcome != DENY:
        raise errors.AjError("permission model did not answer as designed")
    return {"read": read.outcome, "consequential": consequential.outcome,
            "forbidden": forbidden.outcome}


def _check_capabilities() -> Dict[str, Any]:
    registry = CapabilityRegistry()
    registry.register_many(internal_specs())
    executable = [s.capability_id for s in registry.executable()]
    if "aj.echo" not in executable or "aj.health_check" not in executable:
        raise errors.CapabilityUnavailable("internal capabilities are not executable")
    return {"registered": len(registry.all()), "executable": executable}


def _check_audit() -> Dict[str, Any]:
    sink = MemoryAuditSink()
    log = AuditLog(sink)
    log.record("health_check", task_id="check", params={"api_key": "must-not-appear"})
    event = sink.events[0]
    if event["params"]["api_key"] != "[redacted]":
        raise errors.AjError("audit redaction did not redact a key-like field")
    return {"events": len(sink.events), "redacted": True}


def _check_memory() -> Dict[str, Any]:
    store = MemoryStore(":memory:")
    try:
        first = store.append_event("health_check", "canonical write probe",
                                   source="aj.runtime")
        event = store.events(limit=1)[0]
        if event.id != first or event.content != "canonical write probe":
            raise errors.AjError("memory append/read mismatch")
        report = store.verify()
        if not report["ok"]:
            raise errors.AjError("memory integrity check failed")
        return {"raw_events": store.count_events(), "verify": report["ok"]}
    finally:
        store.close()


def _check_providers(config: Config) -> Dict[str, Any]:
    registry = ProviderRegistry.from_config(config, transport=None)
    status = registry.status()
    try:
        Gateway(registry).complete(ChatRequest(messages=(Message("user", "hi"),)))
    except errors.AjError as exc:
        if exc.code != errors.PROVIDER_UNAVAILABLE:
            raise
    else:
        raise errors.AjError("provider gateway answered without a usable adapter")
    return {"providers": sorted(status), "usable": 0}


def _check_execution() -> Dict[str, Any]:
    port = UnavailableExecutionAdapter()
    if port.available():
        raise errors.AjError("execution port claims a runtime is attached")
    return port.describe()


def _check_task_persistence() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-taskcheck-") as directory:
        store = TaskStore(directory)
        record = store.create("persistence check")
        for status in (UNDERSTANDING, PLANNED, AUTHORIZED, EXECUTING, VERIFYING):
            store.transition(record.task_id, status)
        store.transition(record.task_id, COMPLETED, "persistence check")
        reopened = TaskStore(directory)
        loaded = reopened.get(record.task_id)
        if loaded.status != COMPLETED or not loaded.events:
            raise errors.AjError("reloaded task lost its state or history")
        if reopened.load_errors:
            raise errors.AjError("reload reported malformed records")
        return {"tasks": len(reopened.all()), "status": loaded.status,
                "events": len(loaded.events)}


def _check_audit_reader() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-auditcheck-") as directory:
        log = AuditLog(JsonlAuditSink(directory))
        log.record("one", task_id="t")
        log.record("two", task_id="t", params={"api_key": "must-not-appear"})
        result = read_events(directory, task_id="t")
        if len(result.events) != 2 or result.malformed:
            raise errors.AjError("audit reader returned the wrong records")
        if result.events[1]["params"]["api_key"] != "[redacted]":
            raise errors.AjError("audit reader exposed a redacted field")
        return {"events": len(result.events), "files": len(result.files)}


def _check_memory_reader() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-memcheck-") as directory:
        path = Path(directory) / "memory.sqlite3"
        first = MemoryStore(path)
        first.append_event("task.created", "reader probe", task_id="t")
        first.close()
        reopened = MemoryStore(path)
        try:
            if len(reopened.events(limit=10)) != 1:
                raise errors.AjError("memory reader lost a persisted event")
            return {"raw_events": reopened.count_events()}
        finally:
            reopened.close()


def _check_recovery(config: Config) -> Dict[str, Any]:
    memory = MemoryStore(":memory:")
    with tempfile.TemporaryDirectory(prefix="aj-reccheck-") as directory:
      try:
        aj = Aj(
            registry=CapabilityRegistry(internal_specs()),
            agents=AgentRegistry(),
            authorizer=Authorizer(),
            audit=AuditLog(MemoryAuditSink()),
            tasks=TaskStore(directory),
            execution=UnavailableExecutionAdapter(),
            skills=SkillRegistry(),
            config=config,
            memory=memory,
            actions=default_actions(),
        )
        record = aj.tasks.create("interrupted", capability_id="aj.echo")
        aj.tasks.transition(record.task_id, UNDERSTANDING)
        findings = RecoveryManager(aj).scan()
        if not findings or findings[0].decision != "replay_safe":
            raise errors.AjError("recovery did not classify a replay-safe task")
        return {"non_terminal": len(findings),
                "decision": findings[0].decision}
      finally:
        memory.close()


def _check_summary() -> Dict[str, Any]:
    store = MemoryStore(":memory:")
    try:
        store.append_event("task.created", "a", task_id="t",
                           meta={"status": RECEIVED})
        store.append_event("task.completed", "b", task_id="t",
                           meta={"status": COMPLETED, "capability": "aj.echo"})
        first = build_summary(store)
        second = build_summary(store)
        if first["content"] != second["content"]:
            raise errors.AjError("summary rebuild was not deterministic")
        if not store.verify()["ok"] or store.count_events() != 2:
            raise errors.AjError("summary build disturbed canonical events")
        parity = verify_summary(store)
        if not parity["ok"]:
            raise errors.AjError("stored summary does not match a fresh rebuild")
        return {"summary_id": first["summary_id"],
                "events": len(first["source_event_ids"]),
                "raw_events": store.count_events(), "verified": parity["ok"]}
    finally:
        store.close()


def _check_cli() -> Dict[str, Any]:
    from .__main__ import build_parser

    parser = build_parser()
    commands = [
        "run", "tasks", "task", "cancel", "retry", "audit", "memory",
        "summary", "capabilities", "permissions", "config", "diagnostics",
        "export", "import", "backup", "recover", "orb", "inbox",
    ]
    for command in commands:
        if command in ("task", "cancel", "retry", "import"):
            argv = [command, "x"]
        elif command in ("export", "backup"):
            argv = [command, "--output", "x"]
        else:
            argv = [command]
        args = parser.parse_args(argv)
        if getattr(args, "command", "") != command:
            raise errors.AjError(f"CLI did not register {command!r}")
    return {"commands": commands}


def _check_orchestrator(config: Config) -> Dict[str, Any]:
    memory = build_memory(config, ephemeral=True)
    try:
        aj = assemble(config, memory=memory, ephemeral_memory=True)
        status = aj.status()
        if status["execution"]["integration_status"] != "NOT ATTACHED":
            raise errors.AjError("orchestrator reports an attached execution runtime")
        report = aj.capability_report()
        dispatchable = [row["capability_id"] for row in report if row["dispatchable"]]
        return {"active_tasks": status["active_tasks"],
                "capabilities": status["capabilities"]["total"],
                "metadata_executable": sum(1 for row in report
                                           if row["metadata_executable"]),
                "dispatchable": len(dispatchable),
                "dispatchable_ids": dispatchable}
    finally:
        memory.close()


def _check_task_locking() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-lockcheck-") as directory:
        path = Path(directory) / "tasks.jsonl.lock"
        with file_lock(path, timeout=5.0):
            try:
                with file_lock(path, timeout=0.05):
                    raise errors.AjError("exclusive lock was acquired twice")
            except errors.StorageBusy:
                pass
        with file_lock(path, timeout=1.0):
            pass
        return {"exclusive": True, "released_on_exit": True}


def _check_audit_locking() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-auditlock-") as directory:
        sink = JsonlAuditSink(directory)
        AuditLog(sink).record("lock_probe", task_id="t")
        path = Path(str(sink.path_for_now()))
        with file_lock(str(path) + ".lock", timeout=5.0):
            try:
                with file_lock(str(path) + ".lock", timeout=0.05):
                    raise errors.AjError("audit lock was acquired twice")
            except errors.StorageBusy:
                pass
        return {"events": 1, "exclusive": True}


def _check_cancel_retry(config: Config) -> Dict[str, Any]:
    memory = MemoryStore(":memory:")
    with tempfile.TemporaryDirectory(prefix="aj-retrycheck-") as directory:
      try:
        aj = Aj(
            registry=CapabilityRegistry(internal_specs()),
            agents=AgentRegistry(),
            authorizer=Authorizer(),
            audit=AuditLog(MemoryAuditSink()),
            tasks=TaskStore(directory),
            execution=UnavailableExecutionAdapter(),
            skills=SkillRegistry(),
            config=config,
            memory=memory,
            actions=default_actions(),
        )
        cancel = aj.tasks.create("cancel probe", capability_id="aj.echo")
        cancelled = aj.cancel_task(cancel.task_id)
        if not cancelled.ok or cancelled.status != CANCELLED:
            raise errors.AjError("cancel did not reach CANCELLED")

        failed = aj.tasks.create("retry probe", capability_id="aj.echo")
        for status in (UNDERSTANDING, PLANNED, AUTHORIZED, EXECUTING, FAILED):
            aj.tasks.transition(failed.task_id, status)
        retried = aj.retry(failed.task_id)
        if not retried.ok or retried.status != COMPLETED:
            raise errors.AjError(f"retry did not complete: {retried.summary}")
        attempts = aj.tasks.get(failed.task_id).attempts
        if not attempts or attempts[-1]["status"] != COMPLETED:
            raise errors.AjError("retry did not record a completed attempt")
        return {"cancel": cancelled.status, "retry": retried.status,
                "attempts": len(attempts)}
      finally:
        memory.close()


def _check_transfer(config: Config) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-transfercheck-") as directory:
        root = Path(directory)

        def local(tag: str) -> Config:
            return load_config(None, env={}, overrides={"core": {
                "data_dir": str(root / tag),
                "audit_dir": str(root / tag / "audit"),
                "memory_path": str(root / tag / "memory.sqlite3"),
            }})

        source = local("source")
        aj = assemble(source)
        try:
            outcome = aj.handle("transfer probe", capability_id="aj.echo",
                                payload={"text": "probe"}, requester="check")
            if not outcome.ok:
                raise errors.AjError("source task did not complete")
        finally:
            if aj.memory is not None:
                aj.memory.close()

        export_path = root / "export.json"
        transfer.export_file(source, export_path)
        target = local("target")
        report = transfer.import_file(target, export_path)
        store = TaskStore(root / "target")
        memory = MemoryStore(root / "target" / "memory.sqlite3")
        try:
            if len(store.all()) != 1 or not memory.events(limit=10):
                raise errors.AjError("import did not restore task and memory")
            return {"tasks": len(store.all()), "memory": memory.count_events(),
                    "audit": report["audit"]}
        finally:
            memory.close()


def _check_config_validation(config: Config) -> Dict[str, Any]:
    issues = validate_config(config)
    if issues:
        raise errors.ConfigError("; ".join(issues))
    return {"issues": 0, "sources": getattr(config, "sources", {})}


def _check_storage_integrity() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-integrity-") as directory:
        store = TaskStore(directory)
        record = store.create("integrity probe")
        with (Path(directory) / "tasks.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("{ this is not json }\n")
        reopened = TaskStore(directory)
        if len(reopened.all()) != 1 or len(reopened.load_errors) != 1:
            raise errors.AjError("malformed record handling is not conservative")
        if reopened.get(record.task_id).status != RECEIVED:
            raise errors.AjError("valid record was not readable next to corruption")
        return {"valid": 1, "malformed": 1, "deleted": False}


def _check_diagnostics(config: Config) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aj-diagcheck-") as directory:
        local = load_config(None, env={}, overrides={"core": {
            "data_dir": directory, "audit_dir": str(Path(directory) / "audit"),
            "memory_path": str(Path(directory) / "memory.sqlite3"),
        }})
        aj = assemble(local)
        try:
            aj.handle("diagnostics probe", capability_id="aj.echo",
                      payload={"text": "probe"}, requester="check")
        finally:
            if aj.memory is not None:
                aj.memory.close()
        report = gather_diagnostics(local)
        if report["tasks"]["records"] != 1 or report["tasks"]["malformed"]:
            raise errors.AjError("diagnostics counts disagree with storage")
        return {"tasks": report["tasks"]["records"],
                "audit": report["audit"]["events"],
                "locks": report["locks"]}


def health(config: Optional[Config] = None) -> Dict[str, Any]:
    """Run every local self-check. No network, no credentials, no sub-agents."""
    config = config or load_config()
    checks = {
        "imports": _run_check("imports", _check_imports),
        "configuration": _run_check("configuration", lambda: _check_config(config)),
        "task_lifecycle": _run_check("task_lifecycle", _check_tasks),
        "permissions": _run_check("permissions", _check_permissions),
        "capabilities": _run_check("capabilities", _check_capabilities),
        "audit": _run_check("audit", _check_audit),
        "memory": _run_check("memory", _check_memory),
        "providers": _run_check("providers", lambda: _check_providers(config)),
        "execution": _run_check("execution", _check_execution),
        "task_persistence": _run_check("task_persistence", _check_task_persistence),
        "audit_reader": _run_check("audit_reader", _check_audit_reader),
        "memory_reader": _run_check("memory_reader", _check_memory_reader),
        "recovery": _run_check("recovery", lambda: _check_recovery(config)),
        "summary": _run_check("summary", _check_summary),
        "cli": _run_check("cli", _check_cli),
        "orchestrator": _run_check("orchestrator", lambda: _check_orchestrator(config)),
        "task_locking": _run_check("task_locking", _check_task_locking),
        "audit_locking": _run_check("audit_locking", _check_audit_locking),
        "cancel_retry": _run_check("cancel_retry", lambda: _check_cancel_retry(config)),
        "transfer": _run_check("transfer", lambda: _check_transfer(config)),
        "config_validation": _run_check("config_validation", lambda: _check_config_validation(config)),
        "storage_integrity": _run_check("storage_integrity", _check_storage_integrity),
        "diagnostics": _run_check("diagnostics", lambda: _check_diagnostics(config)),
    }
    failures = sorted(name for name, result in checks.items() if not result["ok"])
    return {
        "ok": not failures,
        "version": __version__,
        "checks": checks,
        "failures": failures,
        "attached": {"jarvis": False, "helix": False, "hermes": "NOT ATTACHED"},
    }


# --- demo ----------------------------------------------------------------
def run_demo(config: Optional[Config] = None) -> Dict[str, Any]:
    """Execute one complete lifecycle with a safe internal capability."""
    config = config or load_config()
    aj = assemble(config)
    try:
        outcome = aj.handle(
            "AJ foundation demo",
            capability_id="aj.echo",
            payload={"text": "hello from AJ"},
            requester="cli",
        )
        memory_events: List[Dict[str, Any]] = []
        if aj.memory is not None:
            memory_events = [
                event.to_dict()
                for event in reversed(aj.memory.events(task_id=outcome.task_id, limit=50))
            ]
        return {
            "outcome": outcome.to_dict(),
            "audit": aj.audit.recent(),
            "memory": aj.memory.stats() if aj.memory is not None else None,
            "memory_events": memory_events,
        }
    finally:
        if aj.memory is not None:
            aj.memory.close()
