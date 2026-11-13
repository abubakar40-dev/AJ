"""The AJ control plane.

One entry point — :meth:`Aj.handle` — takes a request, creates an accountable
task record, decides who owns it, enforces permission policy, dispatches through
the owning agent or the execution port, records the outcome, and returns a result
that states plainly what happened.

Routing is deterministic
------------------------
The router is a rule table plus an explicit capability override. It is not an LLM
classifier, so its behaviour is reproducible and testable. An intent classifier can
be added later behind the same interface; today's rules encode the approved split:
calling/communications -> HELIX, general and major work -> JARVIS.

Failure is first-class
----------------------
Every failure produces a task record in ``FAILED`` with the normalized error,
never a success with a warning. Recovery is explicit: :meth:`Aj.retry` moves
``FAILED -> RECOVERING -> RETRYING -> EXECUTING`` with a bounded attempt count,
and escalates instead of looping.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

import logging

from . import errors, ids, invariants, permissions, task as taskmod
from .actions import InternalActions, default_actions, specs as internal_specs
from .calling import CallingService, CallState
from .idempotency import IdempotencyStore
from .journal import Journal
from .lease import LeaseManager
from .receipts import ReceiptStore
from .agents import AgentRegistry, UnconfiguredAgent
from .audit import AuditLog, JsonlAuditSink
from .capability import OWNER_AJ, CapabilityRegistry, CapabilitySpec
from .config import Config, load as load_config
from .contracts import AgentRequest, AgentResult, ExecutionRequest
from .execution import ExecutionPort, SkillRegistry, UnavailableExecutionAdapter, execute
from .memory import MemoryStore
from .permissions import (canonical_fingerprint,
    ALLOW, CONFIRM, LEVEL_CONSEQUENTIAL, Authorizer, PolicyDecision,
)

CALLING_PATTERN = re.compile(
    r"\b(call|phoned?|dial|dialing|ring up|give .{0,20}a call)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Route:
    """Where a request goes and why."""

    owner_agent: str
    capability_id: str
    rule: str

    def to_dict(self) -> Dict[str, str]:
        return {"owner_agent": self.owner_agent, "capability_id": self.capability_id,
                "rule": self.rule}


class Router:
    """Deterministic request routing."""

    def route(self, request_text: str, *, capability_id: str = "",
              registry: Optional[CapabilityRegistry] = None) -> Route:
        if capability_id:
            if registry is not None:
                spec = registry.find(capability_id)
                if spec is None:
                    raise errors.CapabilityNotFound(
                        f"capability {capability_id!r} is not registered"
                    )
                return Route(spec.owner_agent, spec.capability_id, "explicit capability")
            return Route(OWNER_AJ, capability_id, "explicit capability")
        if CALLING_PATTERN.search(request_text or ""):
            return Route("HELIX", "helix.place_call", "calling keyword")
        return Route("JARVIS", "", "default: general and major work")


@dataclass
class TaskOutcome:
    """What AJ returns to the caller."""

    task_id: str
    status: str
    owner_agent: str
    capability_id: str
    ok: bool
    summary: str
    result: Optional[AgentResult] = None
    decision: Optional[PolicyDecision] = None
    requires_user_decision: bool = False
    route_rule: str = ""
    errors: List[Dict[str, Any]] = field(default_factory=list)
    output: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "owner_agent": self.owner_agent,
            "capability_id": self.capability_id,
            "ok": self.ok,
            "summary": self.summary,
            "result": self.result.to_dict() if self.result else None,
            "decision": self.decision.to_dict() if self.decision else None,
            "requires_user_decision": self.requires_user_decision,
            "route_rule": self.route_rule,
            "errors": self.errors,
            "output": self.output,
        }


class Aj:
    """The ecosystem control plane."""

    def __init__(
        self,
        *,
        registry: Optional[CapabilityRegistry] = None,
        agents: Optional[AgentRegistry] = None,
        authorizer: Optional[Authorizer] = None,
        audit: Optional[AuditLog] = None,
        tasks: Optional[taskmod.TaskStore] = None,
        execution: Optional[ExecutionPort] = None,
        skills: Optional[SkillRegistry] = None,
        config: Optional[Config] = None,
        memory: Optional[MemoryStore] = None,
        actions: Optional[InternalActions] = None,
        calling: Optional[CallingService] = None,
        leases: Optional[LeaseManager] = None,
        journal: Optional[Journal] = None,
        receipts: Optional[ReceiptStore] = None,
        idempotency: Optional[IdempotencyStore] = None,
    ):
        self.config = config or load_config()
        self.registry = registry or CapabilityRegistry()
        self.agents = agents or AgentRegistry()
        self.audit = audit or AuditLog(
            JsonlAuditSink(str(self.config.get("core.audit_dir")))
        )
        if authorizer is not None:
            self.authorizer = authorizer
        else:
            self.authorizer = Authorizer(
                unattended_ceiling=int(self.config.get("permissions.unattended_ceiling", 1))
            )
        self.tasks = tasks or taskmod.TaskStore(
            self.config.get("core.data_dir") if self.config.get("runtime.persist_tasks", True)
            else None
        )
        self.execution: ExecutionPort = execution or UnavailableExecutionAdapter()
        self.skills = skills or SkillRegistry()
        self.memory = memory
        self.actions = actions or default_actions()
        self.calling = calling or CallingService()
        self.router = Router()
        data_dir = (self.tasks._path.parent
                    if getattr(self.tasks, "_path", None) is not None else None)
        self.journal = journal or (Journal(data_dir / "journal.jsonl")
                                   if data_dir else None)
        self.receipts = receipts or (ReceiptStore(data_dir / "receipts.jsonl")
                                     if data_dir else None)
        self.idempotency = idempotency or (
            IdempotencyStore(data_dir / "idempotency.json") if data_dir else None)
        self.leases = leases or LeaseManager(
            data_dir, audit=self.audit, journal=self.journal)

    # --- public API ------------------------------------------------------

    def handle(
        self,
        goal: str,
        *,
        capability_id: str = "",
        payload: Optional[Mapping[str, Any]] = None,
        approval: str = "",
        user_requested: bool = True,
        requester: str = "user",
        timeout_seconds: int = 120,
        idempotency_key: str = "",
        depends_on: Optional[List[str]] = None,
        priority: int = 0,
        deadline: Optional[float] = None,
    ) -> TaskOutcome:
        """Accept one request and run it as far as policy allows."""
        goal = (goal or "").strip()
        key = (idempotency_key or "").strip()
        if key and self.idempotency is not None:
            # Check for idempotency key conflict before claiming
            # Look up in capability-scoped namespace first
            existing_task_id = self.idempotency.lookup(capability_id or "auto", key)
            # Also check the full store for cross-capability key reuse
            # (key may have been claimed under a different capability)
            all_entries = self.idempotency.all()
            other_scope_task_id = None
            for scope, data in all_entries.items():
                # scope format is "capability_id:key" or just "key"
                scope_key = scope.split(":", 1) if ":" in scope else [scope, ""]
                scope_id = scope_key[0] if len(scope_key) > 1 else None
                store_key = scope_key[1] if len(scope_key) > 1 else scope
                if store_key == key and scope_id and scope_id != (capability_id or ""):
                    other_scope_task_id = str(data.get("task_id", ""))
                    break
            existing_task_id = existing_task_id or other_scope_task_id
            if existing_task_id:
                # Key already exists - verify it's for the same capability and payload
                existing = self.tasks.get(existing_task_id)
                if existing.capability_id == (capability_id or "") and existing.request_payload == dict(payload or {}):
                    # Same key, same capability, same payload: true idempotent replay
                    return self._idempotent_outcome(existing_task_id)
                # Same key but different capability or payload: conflict
                return self._fail(
                    self.tasks.create(goal or "(no goal text)", requester=requester),
                    "AJ",
                    capability_id or "auto",
                    errors.AjError(
                        f"idempotency key conflict: key {key!r} already used for "
                        f"task {existing_task_id} with different capability/payload",
                        code=errors.CONFIG_INVALID,
                    ),
                    "planning",
                )
            with self.idempotency.claim(capability_id or "auto", key) as claim:
                if claim.get("task_id"):
                    return self._idempotent_outcome(claim["task_id"])
                record = self.tasks.create(goal or "(no goal text)",
                                           requester=requester)
                claim["task_id"] = record.task_id
                claim["claimed"] = True
        else:
            record = self.tasks.create(goal or "(no goal text)",
                                       requester=requester)
        record.request_payload = dict(payload or {})
        record.depends_on = list(depends_on or [])
        record.priority = int(priority)
        record.deadline = deadline
        record.root_task_id = record.task_id
        self.tasks.save(record, "metadata")
        self._journal("TASK_ACCEPTED", record,
                      metadata={"capability": capability_id or "auto"})
        self.audit.record("task_received", task_id=record.task_id,
                          operation_id=record.operation_id, detail=goal[:200])
        self._remember(record, "task.created", record.goal,
                       {"owner_agent": record.owner_agent})

        try:
            route = self.router.route(goal, capability_id=capability_id,
                                      registry=self.registry)
        except errors.AjError as exc:
            return self._fail(record, "AJ", capability_id, exc, "routing")

        record.owner_agent = route.owner_agent
        record.capability_id = route.capability_id
        self.tasks.transition(record.task_id, taskmod.UNDERSTANDING,
                             f"routed to {route.owner_agent} ({route.rule})")

        spec = self.registry.find(route.capability_id) if route.capability_id else None
        if spec is not None:
            record.permission_level = spec.risk_level
        self.tasks.transition(record.task_id, taskmod.PLANNED, route.rule)

        blocked_by = self.unsatisfied_dependencies(record)
        if blocked_by:
            reason = f"waiting for dependencies: {', '.join(blocked_by)}"
            self.tasks.transition(record.task_id, taskmod.BLOCKED, reason)
            self.audit.record("task_blocked", task_id=record.task_id,
                              operation_id=record.operation_id,
                              capability=route.capability_id,
                              result="blocked", detail=reason[:300])
            self._journal("TASK_BLOCKED", record,
                          metadata={"dependencies": blocked_by})
            self._remember(record, "task.blocked", reason,
                           {"dependencies": blocked_by})
            return TaskOutcome(
                task_id=record.task_id, status=record.status,
                owner_agent=route.owner_agent,
                capability_id=route.capability_id, ok=False, summary=reason,
                route_rule=route.rule,
            )

        # Explicit capability requested but unknown to the registry.
        if route.capability_id and spec is None:
            return self._fail(record, route.owner_agent, route.capability_id,
                              errors.CapabilityNotFound(
                                  f"capability {route.capability_id!r} is not registered"),
                              "planning")

        if spec is not None:
            blocker = self._capability_blocker(spec)
            if blocker is not None:
                final = (taskmod.ABORTED if isinstance(blocker, errors.PolicyDenied)
                         else taskmod.FAILED)
                return self._fail(record, route.owner_agent, spec.capability_id,
                                  blocker, "authorization", final=final)

        decision = self.authorizer.authorize(
            spec or self._generic_spec(route),
            payload=payload or {"goal": goal},
            approval=approval,
            user_requested=user_requested,
            actor=requester,
        )
        record.approval_required = decision.requires_approval

        if decision.outcome == CONFIRM:
            self.tasks.transition(record.task_id, taskmod.WAITING_FOR_APPROVAL,
                                 decision.reason)
            record.requires_user_decision = True
            try:
                self.audit.record(
                    "awaiting_approval", task_id=record.task_id,
                    operation_id=record.operation_id,
                    capability=decision.capability_id, permission_level=decision.level,
                    authorization="required", result="awaiting_approval",
                    detail=decision.reason, mandatory=True,
                )
            except Exception as exc:
                err = errors.StorageError(
                    f"mandatory security audit could not be persisted: {exc}")
                return self._fail(record, route.owner_agent, decision.capability_id,
                                  err, "authorization", final=taskmod.FAILED)
            return TaskOutcome(
                task_id=record.task_id, status=record.status,
                owner_agent=route.owner_agent, capability_id=decision.capability_id,
                ok=False, summary=f"Awaiting approval: {decision.reason}",
                decision=decision, requires_user_decision=True,
                route_rule=route.rule,
            )

        if decision.outcome != ALLOW:
            self.tasks.transition(record.task_id, taskmod.ABORTED, decision.reason)
            record.requires_user_decision = False
            try:
                self.audit.record(
                    "policy_denied", task_id=record.task_id,
                    operation_id=record.operation_id,
                    capability=decision.capability_id, permission_level=decision.level,
                    authorization="denied", result="denied", detail=decision.reason,
                    mandatory=True,
                )
            except Exception as exc:
                err = errors.StorageError(
                    f"mandatory security audit could not be persisted: {exc}")
                return self._fail(record, route.owner_agent, decision.capability_id,
                                  err, "authorization", final=taskmod.FAILED)
            return TaskOutcome(
                task_id=record.task_id, status=record.status,
                owner_agent=route.owner_agent, capability_id=decision.capability_id,
                ok=False, summary=f"Blocked by policy: {decision.reason}",
                decision=decision, route_rule=route.rule,
            )

        self.tasks.transition(record.task_id, taskmod.AUTHORIZED, decision.reason)
        if spec is not None:
            record.authorization_context = self._compute_authorization_context(
                record, spec, payload, decision)
            self.tasks.save(record, "authorized")
        lease = self.leases.acquire(record.task_id, "execute",
                                    ttl=timeout_seconds + 30)
        try:
            try:
                self.audit.record(
                    "authorized", task_id=record.task_id,
                    operation_id=record.operation_id, agent=route.owner_agent,
                    capability=decision.capability_id, permission_level=decision.level,
                    authorization=decision.reason, result="authorized",
                    mandatory=True,
                )
            except Exception as exc:
                # Mandatory security audit evidence must be persisted before protected execution.
                err = errors.StorageError(
                    f"mandatory security audit could not be persisted: {exc}")
                return self._fail(record, route.owner_agent, decision.capability_id,
                                  err, "authorization", final=taskmod.FAILED)
            self._journal("TASK_SCHEDULED", record,
                          lease_id=lease.lease_id,
                          metadata={"capability": decision.capability_id})
            self._remember(record, "task.authorized", decision.reason,
                           {"capability": decision.capability_id,
                            "permission_level": decision.level})
            return self._execute(record, route, spec, payload, approval,
                                 timeout_seconds)
        finally:
            try:
                self.leases.release(lease)
            except errors.AjError:
                pass

    def retry(self, task_id: str, *, approval: str = "") -> TaskOutcome:
        with self.leases.hold(task_id, "retry"):
            return self._retry_locked(task_id, approval=approval)

    def _retry_locked(self, task_id: str, *, approval: str = "") -> TaskOutcome:
        """Retry a failed task, bounded and gated by ``retry_safe``."""
        record = self.tasks.get(task_id)
        if record.status != taskmod.FAILED:
            raise errors.AjError(
                f"task {task_id} is {record.status}; only FAILED tasks can be retried",
                code=errors.CALLING_INVALID_STATE,
            )
        if record.attempt >= record.max_attempts:
            self.tasks.transition(task_id, taskmod.RECOVERING,
                                  "attempts exhausted")
            self.tasks.transition(task_id, taskmod.ESCALATED,
                                  "needs a human decision")
            record.requires_user_decision = True
            return TaskOutcome(
                task_id=task_id, status=record.status, owner_agent=record.owner_agent,
                capability_id=record.capability_id, ok=False,
                summary=("Retry budget exhausted; the task is escalated and needs "
                         "a decision"),
                requires_user_decision=True,
            )

        spec = self.registry.find(record.capability_id) if record.capability_id else None
        if spec is None or not spec.retry_safe:
            reason = (f"capability {record.capability_id!r} is not registered"
                      if spec is None else
                      "capability is not declared retry-safe")
            record.requires_user_decision = True
            record.note(f"retry refused: {reason}")
            self.tasks.save(record, "retry_refused")
            self.audit.record(
                "retry_refused", task_id=record.task_id,
                operation_id=record.operation_id, agent="AJ",
                capability=record.capability_id, result="refused",
                authorization="none", detail=reason[:300],
            )
            self._remember(record, "task.retry_refused", reason,
                           {"capability": record.capability_id})
            return TaskOutcome(
                task_id=task_id, status=record.status, owner_agent=record.owner_agent,
                capability_id=record.capability_id, ok=False,
                summary=f"Retry refused: {reason}",
                requires_user_decision=True, route_rule="retry",
            )

        blocker = self._capability_blocker(spec)
        if blocker is not None:
            reason = blocker.message
            record.requires_user_decision = True
            record.note(f"retry refused: {reason}")
            self.tasks.save(record, "retry_refused")
            self.audit.record(
                "retry_refused", task_id=record.task_id,
                operation_id=record.operation_id, agent="AJ",
                capability=record.capability_id, result="refused",
                authorization="policy", detail=reason[:300],
            )
            self._remember(record, "task.retry_refused", reason,
                           {"capability": record.capability_id})
            return TaskOutcome(
                task_id=task_id, status=record.status, owner_agent=record.owner_agent,
                capability_id=record.capability_id, ok=False,
                summary=f"Retry refused: {reason}",
                requires_user_decision=True, route_rule="retry",
            )

        payload = dict(record.request_payload or {})
        decision = self.authorizer.authorize(
            spec,
            payload=payload or {"goal": record.goal},
            approval=approval,
            user_requested=True,
            actor="operator",
        )
        if decision.outcome != ALLOW:
            reason = f"retry authorization {decision.outcome.lower()}: {decision.reason}"
            record.requires_user_decision = True
            record.note(f"retry refused: {reason}")
            self.tasks.save(record, "retry_refused")
            self.audit.record(
                "retry_refused", task_id=record.task_id,
                operation_id=record.operation_id, agent="AJ",
                capability=record.capability_id, result="refused",
                authorization=decision.outcome.lower(),
                permission_level=decision.level,
                detail=reason[:300],
            )
            self._remember(record, "task.retry_refused", reason,
                           {"capability": record.capability_id,
                            "decision": decision.to_dict()})
            return TaskOutcome(
                task_id=task_id, status=record.status, owner_agent=record.owner_agent,
                capability_id=record.capability_id, ok=False,
                summary=f"Retry refused: {reason}",
                decision=decision,
                requires_user_decision=True, route_rule="retry",
            )

        self.tasks.transition(task_id, taskmod.RECOVERING,
                              "operator asked for a retry")
        self.tasks.transition(task_id, taskmod.RETRYING, f"attempt {record.attempt + 1}")
        self.audit.record(
            "retry_started", task_id=record.task_id,
            operation_id=record.operation_id, agent=record.owner_agent,
            capability=record.capability_id, result="retrying",
            authorization="retry_safe", detail=f"attempt {record.attempt + 1}",
        )
        self._remember(record, "task.retry", "retry started",
                       {"capability": record.capability_id,
                        "attempt": record.attempt + 1})
        self._journal("RETRY_STARTED", record,
                      attempt_id=self._attempt_id(record),
                      metadata={"attempt": record.attempt + 1})
        route = Route(record.owner_agent, record.capability_id, "retry")
        return self._execute(
            record, route, spec, payload, approval,
            timeout_seconds=int(self.config.get(
                "agents.jarvis.timeout_seconds", 120)),

        )

    def cancel_task(self, task_id: str) -> TaskOutcome:
        with self.leases.hold(task_id, "cancel"):
            return self._cancel_locked(task_id)

    def _cancel_locked(self, task_id: str) -> TaskOutcome:
        """Cancel a task honestly: no forced termination of running work."""
        record = self.tasks.get(task_id)
        if record.terminal:
            self.audit.record("cancel_refused", task_id=task_id,
                              operation_id=record.operation_id, agent="AJ",
                              capability=record.capability_id, result=record.status,
                              authorization="none",
                              detail="task is already terminal")
            return TaskOutcome(
                task_id=task_id, status=record.status,
                owner_agent=record.owner_agent,
                capability_id=record.capability_id, ok=False,
                summary=f"Task is already {record.status}; nothing was changed",
                route_rule="cancel",
            )
        if record.status == taskmod.EXECUTING:
            self.tasks.transition(record.task_id, taskmod.CANCEL_REQUESTED,
                                 "operator requested cancellation")
            record.requires_user_decision = True
            self.tasks.save(record, "cancel_requested")
            self.audit.record("cancel_requested", task_id=task_id,
                              operation_id=record.operation_id, agent="AJ",
                              capability=record.capability_id, result="requested",
                              authorization="operator",
                              detail="running execution was not interrupted")
            self._remember(record, "task.cancel_requested",
                           "cancellation requested; execution not interrupted",
                           {"status": record.status})
            return TaskOutcome(
                task_id=task_id, status=record.status,
                owner_agent=record.owner_agent,
                capability_id=record.capability_id, ok=False,
                summary=("Cancellation requested; the running execution was not "
                         "interrupted"),
                requires_user_decision=True, route_rule="cancel",
            )
        self.tasks.transition(record.task_id, taskmod.CANCELLED,
                             "cancelled by operator")
        self.audit.record("task_cancelled", task_id=task_id,
                          operation_id=record.operation_id, agent="AJ",
                          capability=record.capability_id, result="cancelled",
                          authorization="operator")
        self._remember(record, "task.cancelled", "cancelled by operator",
                       {"status": record.status})
        return TaskOutcome(
            task_id=task_id, status=record.status, owner_agent=record.owner_agent,
            capability_id=record.capability_id, ok=True, summary="Cancelled",
            route_rule="cancel",
        )

    def cancel(self, task_id: str) -> bool:
        return self.cancel_task(task_id).ok

    def recover(self, task_id: str, *, approval: str = "") -> TaskOutcome:
        with self.leases.hold(task_id, "recover"):
            return self._recover_locked(task_id, approval=approval)

    def _recover_locked(self, task_id: str, *, approval: str = "") -> TaskOutcome:
        """Replay one interrupted task, only when it is declared replay-safe."""
        record = self.tasks.get(task_id)
        if record.terminal:
            raise errors.AjError(
                f"task {task_id} is {record.status}; nothing to recover",
                code=errors.CALLING_INVALID_STATE,
            )
        spec = self.registry.find(record.capability_id) if record.capability_id else None
        reason = ""
        if spec is None:
            reason = (f"capability {record.capability_id!r} is not registered"
                      if record.capability_id else "task has no capability to replay")
        elif not spec.execution_adapter.startswith("internal:"):
            reason = "capability is not an internal action"
        elif not spec.replay_safe:
            reason = "capability is not declared replay-safe"
        if reason:
            return self._require_manual_recovery(record, reason)

        blocker = self._capability_blocker(spec)
        if blocker is not None:
            return self._require_manual_recovery(record, blocker.message)

        payload = dict(record.request_payload or {})
        decision = self.authorizer.authorize(
            spec,
            payload=payload or {"goal": record.goal},
            approval=approval,
            user_requested=True,
            actor="recovery",
        )
        if decision.outcome != ALLOW:
            return self._require_manual_recovery(
                record,
                f"recovery authorization {decision.outcome.lower()}: {decision.reason}",
            )

        if record.status not in (taskmod.AUTHORIZED, taskmod.EXECUTING,
                                 taskmod.RETRYING):
            if not record.can_transition(taskmod.AUTHORIZED):
                return self._require_manual_recovery(
                    record, f"{record.status} cannot move to AUTHORIZED")
            self.tasks.transition(record.task_id, taskmod.AUTHORIZED,
                                 "recovery: replay-safe action")

        record.attempt += 1
        self.audit.record(
            "recovery_started", task_id=record.task_id,
            operation_id=record.operation_id, agent="AJ",
            capability=spec.capability_id, result="replaying",
            authorization=decision.reason, detail=f"attempt {record.attempt}",
        )
        self._remember(record, "task.recovery", "safe replay started",
                       {"capability": spec.capability_id,
                        "attempt": record.attempt})
        self._journal("RECOVERY_STARTED", record,
                      attempt_id=self._attempt_id(record),
                      metadata={"capability": spec.capability_id})
        route = Route(spec.owner_agent, spec.capability_id,
                      "recovery: replay-safe internal action")
        return self._execute(
            record, route, spec, payload, approval,
            int(self.config.get("agents.jarvis.timeout_seconds", 120)),
        )

    def _require_manual_recovery(self, record: taskmod.TaskRecord,
                                 reason: str) -> TaskOutcome:
        if record.can_transition(taskmod.RECOVERY_REQUIRED):
            self.tasks.transition(record.task_id, taskmod.RECOVERY_REQUIRED, reason)
        record.requires_user_decision = True
        record.note(f"recovery required: {reason}")
        self.audit.record(
            "recovery_refused", task_id=record.task_id,
            operation_id=record.operation_id, agent="AJ",
            capability=record.capability_id, result="recovery_required",
            authorization="none", detail=reason[:300],
        )
        self._remember(record, "task.recovery_refused", reason,
                       {"capability": record.capability_id,
                        "status": record.status})
        return TaskOutcome(
            task_id=record.task_id, status=record.status, owner_agent="AJ",
            capability_id=record.capability_id, ok=False,
            summary=f"Recovery required: {reason}",
            requires_user_decision=True, route_rule="recovery",
        )

    def dispatch_of(self, spec: CapabilitySpec) -> Tuple[bool, str]:
        """Whether the executor has an actual handler for *spec*.

        ``CapabilitySpec.executable`` answers a policy question (is this allowed
        and not known-broken). It does not answer whether a code path exists to
        run it. Conflating the two let declarations advertise ``available`` with
        nothing behind them, so the two answers are reported separately.
        """
        adapter = spec.execution_adapter or ""
        if adapter.startswith("internal:"):
            return True, "in-process action"
        if adapter == "helix.calling_service":
            if self.calling is None:
                return False, "no calling service configured"
            resolver = getattr(self.calling, "resolver", None)
            if resolver is None:
                return True, "in-process calling service (no contact resolver configured)"
            return True, "in-process calling service"
        if spec.owner_agent == "HERMES":
            return True, "execution port"
        agent = self.agents.find(spec.owner_agent)
        if agent is None:
            return False, f"no agent adapter for {spec.owner_agent}"
        if getattr(agent, "transport", None) is None:
            return False, f"{spec.owner_agent} adapter has no agreed task transport"
        return True, f"agent transport {spec.owner_agent}"

    def capability_report(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for spec in self.registry.all():
            row = spec.to_dict()
            dispatchable, reason = self.dispatch_of(spec)
            row["metadata_executable"] = spec.executable
            row["dispatchable"] = dispatchable
            row["dispatch_reason"] = reason
            rows.append(row)
        return rows

    def status(self) -> Dict[str, Any]:
        return {
            "ecosystem": self.config.get("core.ecosystem_name", "AJ"),
            "capabilities": self.registry.summary(),
            "agents": self.agents.status(),
            "execution": self.execution.describe(),
            "skills": self.skills.summary(),
            "active_tasks": len(self.tasks.active()),
            "permission_ceiling": self.authorizer.unattended_ceiling,
            "internal_actions": self.actions.names(),
            "memory": self.memory.stats() if self.memory is not None else None,
        }

    # --- internals -------------------------------------------------------

    def _generic_spec(self, route: Route) -> CapabilitySpec:
        return CapabilitySpec(
            capability_id=route.capability_id or f"agent.{route.owner_agent.lower()}.delegate",
            name=f"Delegate to {route.owner_agent}",
            description="General delegation to a sub-agent",
            owner_agent=route.owner_agent if route.owner_agent in
            ("AJ", "JARVIS", "HELIX", "HERMES") else "AJ",
            execution_adapter=f"agent:{route.owner_agent.lower()}",
            risk_level=1,
            availability="available",
            verification_status="implemented_unverified",
        )

    def _capability_blocker(self, spec: CapabilitySpec) -> Optional[errors.AjError]:
        if spec.forbidden:
            return errors.PolicyDenied("this capability is permanently disabled by policy")
        if spec.verification_status in ("broken", "stub", "planned"):
            return errors.CapabilityUnavailable(
                f"{spec.capability_id} is {spec.verification_status}; it is not executable"
            )
        if (spec.verification_status == "unknown"
                and self.config.get("core.require_verification_before_execute", True)):
            return errors.CapabilityUnavailable(
                f"{spec.capability_id} has unknown verification status; verify it first"
            )
        if spec.availability not in ("available", "degraded"):
            return errors.CapabilityUnavailable(
                f"{spec.capability_id} is {spec.availability} in this environment"
            )
        return None

    def _execute(
        self,
        record: taskmod.TaskRecord,
        route: Route,
        spec: Optional[CapabilitySpec],
        payload: Optional[Mapping[str, Any]],
        approval: str,
        timeout_seconds: int,
    ) -> TaskOutcome:
        self.tasks.transition(record.task_id, taskmod.EXECUTING,
                             f"{route.owner_agent}:{route.capability_id or 'delegate'}")
        self._start_attempt(record)
        attempt_id = self._attempt_id(record)
        current_lease = self.leases.get(record.task_id)
        journal_ids = [self._journal(
            "EXECUTION_STARTED", record, attempt_id=attempt_id,
            lease_id=current_lease.lease_id if current_lease else "",
            metadata={"capability": route.capability_id or "delegate"})]
        logging.getLogger("aj.orchestrator").info(
            "task=%s operation=%s attempt=%s capability=%s status=%s",
            record.task_id, record.operation_id, attempt_id,
            route.capability_id or "-", record.status,
        )

        # AJ-owned safe actions run in-process: no agent, no port, no network.
        if spec is not None and spec.execution_adapter.startswith("internal:"):
            action = spec.execution_adapter.split(":", 1)[1]
            arguments = dict(payload or {})
            arguments.setdefault("goal", record.goal)
            try:
                output = self.actions.run(action, arguments)
            except errors.AjError as exc:
                return self._fail(record, "AJ", spec.capability_id, exc, "executing")
            record.record_action("execute",
                                 f"capability={spec.capability_id} action={action}")
            record.evidence.append({"action": action, "verified": True})
            self.tasks.transition(record.task_id, taskmod.VERIFYING,
                                 "internal action returned")
            self.tasks.transition(record.task_id, taskmod.COMPLETED,
                                 f"internal:{action}")
            record.summary = f"{spec.capability_id} completed"
            self._finish_attempt(record, taskmod.COMPLETED)
            self.tasks.save(record, "completed")
            self.audit.record(
                "executed", task_id=record.task_id,
                operation_id=record.operation_id, attempt_id=attempt_id,
                agent="AJ", capability=spec.capability_id,
                permission_level=spec.risk_level,
                authorization="internal", result="completed",
            )
            logging.getLogger("aj.orchestrator").info(
                "task=%s operation=%s attempt=%s capability=%s status=%s",
                record.task_id, record.operation_id, attempt_id,
                spec.capability_id, record.status,
            )
            self._remember(record, "task.completed", record.summary,
                           {"capability": spec.capability_id, "status": record.status})
            journal_ids.append(self._journal(
                "EXECUTION_RESULT_RECORDED", record, attempt_id=attempt_id,
                metadata={"status": record.status}))
            journal_ids.append(self._journal(
                "EXECUTION_VERIFIED", record, attempt_id=attempt_id))
            self._receipt(record, attempt_id, spec.capability_id, "COMPLETED",
                          "verified", output, journal_ids)
            return TaskOutcome(
                task_id=record.task_id, status=record.status, owner_agent="AJ",
                capability_id=spec.capability_id, ok=True, summary=record.summary,
                route_rule=route.rule, output=output,
            )

        # Calling subsystem (in-process adapter). helix.prepare_call resolves a
        # contact and stops before dialing; it does not reach the HELIX HTTP/WS
        # bridge and does not place a real call.
        if spec is not None and spec.execution_adapter == "helix.calling_service":
            return self._execute_calling(record, route, spec, payload, timeout_seconds)

        # Execution through the Hermes boundary, when a skill is named.
        if spec is not None and spec.owner_agent == "HERMES":
            request = ExecutionRequest(
                request_id=f"{record.task_id}/exec",
                capability_id=spec.capability_id,
                arguments=dict(payload or {}),
                task_id=record.task_id,
                permission_level=spec.risk_level,
                approval_token=approval,
                timeout_seconds=timeout_seconds,
            )
            try:
                result = execute(self.execution, request)
            except errors.AjError as exc:
                return self._fail(record, "HERMES", spec.capability_id, exc,
                                  "executing")
            record.record_action("execute", f"capability={spec.capability_id}")
            record.evidence.append({"verified": result.verified,
                                    "status": result.status})
            if not result.ok:
                self.tasks.transition(record.task_id, taskmod.FAILED, result.status)
                record.record_error(result.error or {"message": result.status},
                                    stage="executing")
                self.audit.record("execution_failed", task_id=record.task_id,
                                  operation_id=record.operation_id,
                                  attempt_id=attempt_id, agent="HERMES",
                                  capability=spec.capability_id, result=result.status,
                                  error=str(result.error or ""))
                return TaskOutcome(
                    task_id=record.task_id, status=record.status, owner_agent="HERMES",
                    capability_id=spec.capability_id, ok=False,
                    summary=f"Execution {result.status}", route_rule=route.rule,
                    errors=[result.error] if result.error else [],
                )
            self.tasks.transition(record.task_id, taskmod.VERIFYING,
                                  "execution returned")
            self.tasks.transition(record.task_id, taskmod.COMPLETED,
                                 "verified" if result.verified else "completed unverified")
            record.summary = f"Skill {spec.capability_id} {result.status}"
            self._finish_attempt(record, taskmod.COMPLETED)
            self.tasks.save(record, "completed")
            self._remember(record, "task.completed", record.summary,
                           {"capability": spec.capability_id, "status": record.status})
            return TaskOutcome(
                task_id=record.task_id, status=record.status, owner_agent="HERMES",
                capability_id=spec.capability_id, ok=True, summary=record.summary,
                route_rule=route.rule,
            )

        # Delegation to JARVIS / HELIX through their adapters.
        agent = self.agents.find(route.owner_agent) or UnconfiguredAgent(
            route.owner_agent, "no adapter configured")
        request = AgentRequest(
            task_id=record.task_id,
            goal=record.goal,
            assigned_agent=route.owner_agent,
            requester=record.requester,
            allowed_capabilities=[route.capability_id] if route.capability_id else [],
            timeout_seconds=timeout_seconds,
            idempotency_key=record.task_id,
        )
        try:
            result = agent.execute(request)
        except Exception as exc:
            return self._fail(record, route.owner_agent, route.capability_id,
                              exc, "executing")

        record.record_action("delegate", f"agent={route.owner_agent}")
        record.evidence.extend(result.evidence)
        record.artifacts.extend(result.artifacts)
        record.warnings.extend(result.warnings)
        record.errors.extend(result.errors)

        self.tasks.transition(record.task_id, taskmod.VERIFYING, f"result={result.status}")
        if result.ok:
            self.tasks.transition(record.task_id, taskmod.COMPLETED,
                                result.summary[:200])
            record.summary = result.summary
            self._remember(record, "task.completed", record.summary,
                           {"agent": route.owner_agent,
                            "capability": route.capability_id,
                            "status": record.status})
        else:
            self.tasks.transition(record.task_id, taskmod.FAILED, result.status)
            record.summary = result.summary or f"{route.owner_agent} did not complete the task"
            self._remember(record, "task.failed", record.summary,
                           {"agent": route.owner_agent,
                            "capability": route.capability_id,
                            "status": record.status})
        self._finish_attempt(
            record,
            taskmod.COMPLETED if result.ok else taskmod.FAILED,
            None if result.ok else errors.AjError(
                "; ".join(str(e.get("message", e)) for e in result.errors) or result.status,
                code=errors.EXECUTION_FAILED,
            ),
        )
        self.tasks.save(record, "result")

        self.audit.record(
            "delegated", task_id=record.task_id,
            operation_id=record.operation_id, attempt_id=attempt_id,
            agent=route.owner_agent, capability=route.capability_id,
            result=result.status,
            error="; ".join(str(e.get("message", e)) for e in result.errors)[:300],
            detail=result.summary[:300],
        )
        logging.getLogger("aj.orchestrator").info(
            "task=%s operation=%s attempt=%s capability=%s status=%s",
            record.task_id, record.operation_id, attempt_id,
            route.capability_id or "-", record.status,
        )
        journal_ids.append(self._journal(
            "EXECUTION_RESULT_RECORDED", record, attempt_id=attempt_id,
            metadata={"status": record.status}))
        self._receipt(record, attempt_id, route.capability_id or "delegate",
                      record.status, "verified" if result.ok else "failed",
                      None if result.ok else result.errors, journal_ids)
        return TaskOutcome(
            task_id=record.task_id, status=record.status, owner_agent=route.owner_agent,
            capability_id=route.capability_id, ok=result.ok, summary=record.summary,
            result=result, requires_user_decision=result.requires_user_decision,
            route_rule=route.rule, errors=result.errors,
        )

    def _calling_query(self, record: taskmod.TaskRecord,
                        payload: Optional[Mapping[str, Any]]) -> str:
        data = dict(payload or {})
        for key in ("query", "contact_query", "name", "contact", "recipient"):
            value = data.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return (record.goal or "").strip()

    def _execute_calling(self, record: taskmod.TaskRecord, route: Route,
                         spec: CapabilitySpec,
                         payload: Optional[Mapping[str, Any]],
                         timeout_seconds: int) -> TaskOutcome:
        """Dispatch a calling-subsystem capability through :attr:`calling`.

        This is an in-process adapter family (``helix.calling_service``), not a
        network call to the HELIX bridge. ``helix.prepare_call`` resolves a
        contact and stops before dialing; no external side effect occurs.
        """
        attempt_id = self._attempt_id(record)
        journal_ids = []  # EXECUTION_STARTED was already journaled by _execute

        if self.calling is None:
            return self._fail(record, route.owner_agent, spec.capability_id,
                              errors.CapabilityUnavailable(
                                  "no calling service configured"),
                              "executing")

        query = self._calling_query(record, payload)
        if not query:
            return self._fail(record, route.owner_agent, spec.capability_id,
                              errors.AjError(
                                  "helix.prepare_call requires a contact query",
                                  code=errors.CALLING_CONTACT_NOT_FOUND),
                              "executing")

        try:
            call = self._prepare_with_timeout(
                query, requested_by=record.requester or "user",
                timeout_seconds=timeout_seconds, task_id=record.task_id,
            )
        except errors.AjError as exc:
            return self._fail(record, route.owner_agent, spec.capability_id,
                              exc, "executing")
        except Exception as exc:
            return self._fail(record, route.owner_agent, spec.capability_id,
                              errors.normalize(exc), "executing")

        record.record_action("execute",
                             f"capability={spec.capability_id} call_id={getattr(call, 'call_id', '')}")
        call_state = getattr(getattr(call, "state", None), "value",
                             str(getattr(call, "state", "")))
        output = call.to_dict() if hasattr(call, "to_dict") else {"state": call_state}
        record.evidence.append({
            "capability": spec.capability_id,
            "call_id": getattr(call, "call_id", ""),
            "call_state": call_state,
            "verified": bool(getattr(call, "contact", None)
                             and getattr(call, "state", None) == CallState.AWAITING_CONFIRMATION),
        })

        # A cancellation requested while the resolver was running outranks the
        # result: report CANCELLED rather than claiming a completed preparation.
        if record.status == taskmod.CANCEL_REQUESTED:
            self.tasks.transition(record.task_id, taskmod.CANCELLED,
                                  "cancellation requested before the result was applied")
            record.summary = ("Cancelled before completion; the prepared call "
                              "result was discarded")
            self._finish_attempt(record, taskmod.CANCELLED)
            self.tasks.save(record, "cancelled")
            self.audit.record(
                "cancelled", task_id=record.task_id,
                operation_id=record.operation_id, attempt_id=attempt_id,
                agent=route.owner_agent, capability=spec.capability_id,
                permission_level=spec.risk_level,
                authorization="operator", result="cancelled",
                detail=f"call_state={call_state} discarded",
            )
            self._remember(record, "task.cancelled", record.summary,
                           {"capability": spec.capability_id,
                            "call_state": call_state, "status": record.status})
            journal_ids.append(self._journal(
                "EXECUTION_RESULT_RECORDED", record, attempt_id=attempt_id,
                metadata={"status": record.status, "call_state": call_state}))
            self._receipt(record, attempt_id, spec.capability_id, "CANCELLED",
                          "not_applied", output, journal_ids)
            return TaskOutcome(
                task_id=record.task_id, status=record.status,
                owner_agent=route.owner_agent,
                capability_id=spec.capability_id, ok=False,
                summary=record.summary, route_rule=route.rule,
            )

        if getattr(call, "state", None) == CallState.AWAITING_CONFIRMATION:
            self.tasks.transition(record.task_id, taskmod.VERIFYING,
                                  "calling service prepared contact")
            self.tasks.transition(record.task_id, taskmod.COMPLETED,
                                  "contact resolved; awaiting dial confirmation")
            contact = getattr(call, "contact", None)
            who = getattr(contact, "display_name", "") if contact else ""
            record.summary = (f"Prepared call to {who} (awaiting dial confirmation)"
                              if who else "Prepared call (awaiting dial confirmation)")
            self._finish_attempt(record, taskmod.COMPLETED)
            self.tasks.save(record, "completed")
            self.audit.record(
                "executed", task_id=record.task_id,
                operation_id=record.operation_id, attempt_id=attempt_id,
                agent=route.owner_agent, capability=spec.capability_id,
                permission_level=spec.risk_level,
                authorization="calling_service", result="completed",
                detail=f"call_state={call_state} call_id={getattr(call, 'call_id', '')}"[:300],
            )
            logging.getLogger("aj.orchestrator").info(
                "task=%s operation=%s attempt=%s capability=%s status=%s",
                record.task_id, record.operation_id, attempt_id,
                spec.capability_id, record.status,
            )
            self._remember(record, "task.completed", record.summary,
                           {"capability": spec.capability_id,
                            "call_id": getattr(call, "call_id", ""),
                            "call_state": call_state,
                            "status": record.status})
            journal_ids.append(self._journal(
                "EXECUTION_RESULT_RECORDED", record, attempt_id=attempt_id,
                metadata={"status": record.status, "call_state": call_state}))
            journal_ids.append(self._journal(
                "EXECUTION_VERIFIED", record, attempt_id=attempt_id,
                metadata={"call_state": call_state}))
            self._receipt(record, attempt_id, spec.capability_id, "COMPLETED",
                          "verified", output, journal_ids)
            return TaskOutcome(
                task_id=record.task_id, status=record.status,
                owner_agent=route.owner_agent,
                capability_id=spec.capability_id, ok=True,
                summary=record.summary, route_rule=route.rule, output=output,
            )

        # CallingService reports preparation failure in-band via CallState.FAILED.
        message = getattr(call, "error", "") or f"calling service ended in {call_state}"
        code = errors.CAPABILITY_UNAVAILABLE
        lower = message.lower()
        if "ambiguous" in lower:
            code = errors.CALLING_AMBIGUOUS_CONTACT
        elif "no contact" in lower:
            code = errors.CALLING_UNAVAILABLE
        elif "no contact resolver" in lower or "resolver" in lower:
            code = errors.CAPABILITY_UNAVAILABLE
        elif "no dialing capability" in lower or "bridge" in lower:
            code = errors.CAPABILITY_UNAVAILABLE
        err = errors.AjError(message, code=code,
                             detail={"call_state": call_state,
                                     "call_id": getattr(call, "call_id", "")})
        return self._fail(record, route.owner_agent, spec.capability_id,
                          err, "executing")

    def _prepare_with_timeout(self, query: str, *, requested_by: str,
                              timeout_seconds: int, task_id: str):
        """Run ``CallingService.prepare`` with a wall-clock bound.

        The contact resolver is a blocking external call and Python cannot kill
        a thread, so the worker is a daemon and the caller stops waiting at the
        deadline. That keeps the bound real: an executor's ``with`` block would
        block again on ``shutdown(wait=True)`` until the resolver returned.
        """
        outcome: Dict[str, Any] = {}
        done = threading.Event()

        def _work() -> None:
            try:
                outcome["call"] = self.calling.prepare(
                    query, requested_by=requested_by)
            except BaseException as exc:  # handed to the waiting caller
                outcome["error"] = exc
            finally:
                done.set()

        worker = threading.Thread(target=_work,
                                  name=f"aj-calling-{task_id}", daemon=True)
        worker.start()
        if not timeout_seconds or timeout_seconds <= 0:
            done.wait()
        elif not done.wait(float(timeout_seconds)):
            raise errors.AjError(
                f"calling service timed out after {timeout_seconds}s",
                code=errors.AGENT_TIMEOUT)

        error = outcome.get("error")
        if error is not None:
            raise error
        call = outcome.get("call")
        if call is None:
            raise errors.AjError("calling service returned no result",
                                 code=errors.EXECUTION_FAILED)
        return call

    def _journal(self, event_type: str, record: taskmod.TaskRecord, *,
                 attempt_id: str = "", lease_id: str = "",
                 metadata: Optional[Mapping[str, Any]] = None) -> str:
        if self.journal is None:
            return ""
        try:
            return self.journal.append(
                event_type, task_id=record.task_id,
                operation_id=record.operation_id, attempt_id=attempt_id,
                worker_id=self.leases.worker_id, lease_id=lease_id,
                metadata=metadata or {})
        except Exception:
            return ""

    def _receipt(self, record: taskmod.TaskRecord, attempt_id: str,
                 capability: str, status: str, verification: str,
                 output: Any, journal_ids: List[str]) -> None:
        if self.receipts is None:
            return
        attempt = next((a for a in record.attempts
                        if a.get("attempt_id") == attempt_id), {})
        lease = self.leases.get(record.task_id)
        try:
            self.receipts.record(
                task_id=record.task_id, operation_id=record.operation_id,
                attempt_id=attempt_id, worker_id=self.leases.worker_id,
                lease_id=lease.lease_id if lease else "",
                capability_id=capability, status=status, verification=verification,
                started_at=float(attempt.get("started_at") or time.time()),
                completed_at=float(attempt.get("ended_at") or time.time()),
                output=output,
                error=None if verification != "failed" else
                {"message": str(output)[:300]},
                journal_event_ids=[item for item in journal_ids if item])
        except Exception:
            pass

    def _idempotent_outcome(self, task_id: str) -> TaskOutcome:
        record = self.tasks.get(task_id)
        self.audit.record("idempotent_replay", task_id=task_id,
                          operation_id=record.operation_id, result=record.status,
                          authorization="idempotency_key")
        self._journal("IDEMPOTENT_REPLAY", record,
                      metadata={"status": record.status})
        return TaskOutcome(
            task_id=task_id, status=record.status, owner_agent=record.owner_agent,
            capability_id=record.capability_id,
            ok=record.status == taskmod.COMPLETED,
            summary=f"idempotent replay of existing task ({record.status})",
            route_rule="idempotency")

    def unsatisfied_dependencies(self, record: taskmod.TaskRecord) -> List[str]:
        """Return list of dependency task_ids that are unsatisfied.

        A dependency is unsatisfied when its target task either:
        1. Does not exist, or
        2. Exists but is not in a COMPLETED terminal state, or
        3. Would create a circular dependency if followed.

        Returns unsatisfied dependency task_ids in the order they appear
        in ``record.depends_on``.
        """
        # First, detect cycles in the depends_on graph.
        cycle_entries = self._detect_cycle_in_depends_on(record)

        # Build the unsatisfied list: cycle entries + missing/non-completed deps
        missing: List[str] = []
        for dependency in record.depends_on:
            # If this dependency is part of a cycle, mark it unsatisfied
            if dependency in cycle_entries:
                missing.append(dependency)
                continue
            # Otherwise, check existence and completion status
            other = self.tasks.find(dependency)
            if other is None or other.status != taskmod.COMPLETED:
                missing.append(dependency)
        return missing

    def _detect_cycle_in_depends_on(self, record: taskmod.TaskRecord) -> Set[str]:
        """Detect tasks in cyclic depends_on chains using DFS.

        Returns a set of task_id strings that are part of or lead into a cycle.
        Uses three-state DFS coloring: WHITE (unvisited), GRAY (on current path),
        BLACK (fully processed). If we encounter a GRAY node while traversing,
        a cycle exists.
        """
        # Build adjacency: each task_id -> list of task_ids it depends on
        # that are also in the current depends_on set
        dep_ids = set(record.depends_on)
        # Map each dependency to its own depends_on (if those tasks exist in our set)
        adj: Dict[str, List[str]] = {}
        for dep_id in dep_ids:
            other = self.tasks.find(dep_id)
            if other is not None and other.depends_on:
                # Only include sub-dependencies that are also in our set
                adj[dep_id] = [
                    sd for sd in other.depends_on
                    if sd in dep_ids
                ]
            else:
                adj[dep_id] = []

        # Three-state DFS: 0=WHITE(unvisited), 1=GRAY(on path), 2=BLACK(done)
        color: Dict[str, int] = {node: 0 for node in adj}
        cycle_nodes: Set[str] = set()

        def dfs(node: str) -> bool:
            """Return True if a cycle was found starting from this node."""
            if color[node] == 2:
                # Already fully processed, no cycle from this path
                return False
            if color[node] == 1:
                # We've encountered a GRAY node - cycle detected
                return True
            # Mark as GRAY (on current path)
            color[node] = 1
            for neighbor in adj.get(node, []):
                if dfs(neighbor):
                    # If a cycle was found downstream, add this node to cycle set
                    cycle_nodes.add(node)
                    return True
            # Mark as BLACK (fully processed)
            color[node] = 2
            return False

        # Run DFS from each unvisited node
        for node in adj:
            if color[node] == 0:
                dfs(node)

        # Now expand cycle_nodes to include all nodes that lead INTO the cycle
        # by doing a reverse traversal: find all nodes that can reach a cycle node
        if cycle_nodes:
            # Build reverse adjacency: who points to whom
            reverse_adj: Dict[str, List[str]] = {node: [] for node in adj}
            for node, neighbors in adj.items():
                for neighbor in neighbors:
                    reverse_adj[neighbor].append(node)

            # BFS/DFS from cycle_nodes following reverse edges to find all predecessors
            visited: Set[str] = set(cycle_nodes)
            stack = list(cycle_nodes)
            while stack:
                n = stack.pop()
                for predecessor in reverse_adj.get(n, []):
                    if predecessor not in visited:
                        visited.add(predecessor)
                        cycle_nodes.add(predecessor)
                        stack.append(predecessor)

        return cycle_nodes

    def dependency_report(self, task_id: str) -> Dict[str, Any]:
        record = self.tasks.get(task_id)
        rows = []
        for dependency in record.depends_on:
            other = self.tasks.find(dependency)
            rows.append({"task_id": dependency,
                         "exists": other is not None,
                         "status": other.status if other else "MISSING"})
        return {"task_id": task_id, "depends_on": rows,
                "blocked": bool(self.unsatisfied_dependencies(record))}

    def lineage(self, task_id: str) -> Dict[str, Any]:
        record = self.tasks.get(task_id)
        root = record.root_task_id or record.task_id
        children = [item.task_id for item in self.tasks.all()
                    if item.parent_task_id == task_id]
        return {"task_id": task_id, "parent_task_id": record.parent_task_id,
                "root_task_id": root, "child_task_ids": children,
                "operation_id": record.operation_id,
                "attempts": len(record.attempts)}


    def _authorization_payload(self, record: taskmod.TaskRecord,
                               payload: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        if payload is not None:
            return dict(payload)
        stored = dict(record.request_payload or {})
        return stored or {"goal": record.goal}

    def _compute_authorization_context(
        self, record: taskmod.TaskRecord, spec: CapabilitySpec,
        payload: Optional[Mapping[str, Any]], decision,
    ) -> Dict[str, Any]:
        return {
            "capability_id": spec.capability_id,
            "version": str(getattr(spec, "version", "1")),
            "risk_level": int(getattr(spec, "risk_level", 0)),
            "forbidden": bool(getattr(spec, "forbidden", False)),
            "approval_required": bool(getattr(decision, "requires_approval", False) or getattr(spec, "risk_level", 0) >= LEVEL_CONSEQUENTIAL),
            "payload_fingerprint": canonical_fingerprint(
                spec.capability_id, self._authorization_payload(record, payload)),
            "outcome": str(getattr(decision, "outcome", "")),
            "source": "orchestrator",
        }

    def _is_material_authorization_change(
        self, record: taskmod.TaskRecord, spec: CapabilitySpec,
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        if not isinstance(context, dict) or not context:
            return True, "authorization context missing"
        stored_cap = str(context.get("capability_id", ""))
        if stored_cap and stored_cap != spec.capability_id:
            return True, "capability changed"
        stored_version = context.get("version")
        if stored_version is not None and str(stored_version) != str(getattr(spec, "version", "1")):
            return True, "capability version changed"
        try:
            stored_risk = int(context.get("risk_level", -1))
        except Exception:
            return True, "authorization context malformed"
        current_risk = int(getattr(spec, "risk_level", 0))
        if stored_risk != current_risk:
            return True, "risk classification changed"
        if bool(context.get("forbidden", False)) != bool(getattr(spec, "forbidden", False)):
            return True, "forbidden status changed"
        stored_approval = bool(context.get("approval_required", False))
        current_approval = bool(current_risk >= LEVEL_CONSEQUENTIAL)
        if (not stored_approval) and current_approval:
            return True, "required approval level increased"
        if stored_approval != current_approval and current_approval:
            return True, "required approval level changed"
        stored_fp = str(context.get("payload_fingerprint", ""))
        current_fp = canonical_fingerprint(
            spec.capability_id, self._authorization_payload(record, None))
        if not stored_fp or stored_fp != current_fp:
            return True, "payload changed"
        blocker = self._capability_blocker(spec)
        if blocker is not None:
            return True, f"capability no longer safely executable: {blocker.message}"
        return False, ""

    def _handle_stale_authorization(
        self, record: taskmod.TaskRecord, spec: CapabilitySpec, reason: str,
    ) -> TaskOutcome:
        # Fail closed: consequential/approval-bound continuations must not execute when
        # durable authorization context is stale, missing, malformed, or materially changed.
        # AUTHORIZED cannot transition to WAITING_FOR_APPROVAL; use RECOVERY_REQUIRED as the
        # safe decision point (preserves evidence, no side effect, requires operator action).
        target = taskmod.RECOVERY_REQUIRED if record.can_transition(taskmod.RECOVERY_REQUIRED) else taskmod.ABORTED
        if record.can_transition(target):
            self.tasks.transition(record.task_id, target, f"stale authorization: {reason}")
        record.requires_user_decision = True
        record.note(f"stale authorization on resume: {reason}")
        self.tasks.save(record, "stale_authorization")
        self.audit.record(
            "policy_denied", task_id=record.task_id,
            operation_id=record.operation_id,
            capability=spec.capability_id, permission_level=spec.risk_level,
            authorization="stale", result=record.status.lower(),
            detail=f"resume refused (stale authorization): {reason}"[:300],
        )
        self._journal("TASK_RECOVERY_REQUIRED" if target == taskmod.RECOVERY_REQUIRED else "TASK_ABORTED",
                      record,
                      metadata={"capability": spec.capability_id,
                                "stage": "resume", "reason": reason[:200],
                                "stale_authorization": True})
        self._remember(record, "task.stale_authorization", reason,
                       {"capability": spec.capability_id, "status": record.status})
        return TaskOutcome(
            task_id=record.task_id, status=record.status,
            owner_agent=record.owner_agent or spec.owner_agent,
            capability_id=spec.capability_id, ok=False,
            summary=f"Prior authorization is no longer valid ({reason}); execution refused",
            requires_user_decision=True, route_rule="resume",
            errors=[{"code": errors.POLICY_DENIED, "message": reason, "stage": "authorization"}],
        )

    def resume(self, task_id: str, *, leased: bool = False) -> TaskOutcome:
        if leased:
            return self._resume_locked(task_id)
        with self.leases.hold(task_id, "execute"):
            return self._resume_locked(task_id)

    def _resume_locked(self, task_id: str) -> TaskOutcome:
        record = self.tasks.get(task_id)
        spec = self.registry.find(record.capability_id) if record.capability_id else None
        if spec is None:
            raise errors.CapabilityNotFound(
                f"capability {record.capability_id!r} is not registered")

        # Promote eligible blocked/planned tasks only through explicit authorization.
        if record.status == taskmod.BLOCKED:
            missing = self.unsatisfied_dependencies(record)
            if missing:
                raise errors.AjError(
                    f"task {task_id} is still blocked by {', '.join(missing)}",
                    code=errors.CALLING_INVALID_STATE)
            # BLOCKED cannot transition directly to WAITING_FOR_APPROVAL/ABORTED in all cases;
            # move through PLANNED for authorization decisions that require it.
            self.tasks.transition(record.task_id, taskmod.PLANNED,
                                  "dependencies satisfied; re-evaluating authorization")
            record = self.tasks.get(task_id)
            blocker = self._capability_blocker(spec)
            if blocker is not None:
                final = (taskmod.ABORTED if isinstance(blocker, errors.PolicyDenied)
                         else taskmod.FAILED)
                return self._fail(record, spec.owner_agent, spec.capability_id,
                                  blocker, "authorization", final=final)
            decision = self.authorizer.authorize(
                spec,
                payload=dict(record.request_payload or {}) or {"goal": record.goal},
                approval="",
                user_requested=True,
                actor=record.requester or "scheduler",
            )
            if decision.outcome == CONFIRM:
                self.tasks.transition(record.task_id, taskmod.WAITING_FOR_APPROVAL,
                                      decision.reason)
                record.requires_user_decision = True
                self.audit.record(
                    "awaiting_approval", task_id=record.task_id,
                    operation_id=record.operation_id,
                    capability=spec.capability_id, permission_level=decision.level,
                    authorization="required", result="awaiting_approval",
                    detail=f"resume blocked: {decision.reason}"[:300],
                )
                self._journal("TASK_AWAITING_APPROVAL", record,
                              metadata={"capability": spec.capability_id,
                                        "stage": "resume"})
                return TaskOutcome(
                    task_id=record.task_id, status=record.status,
                    owner_agent=record.owner_agent or spec.owner_agent,
                    capability_id=spec.capability_id, ok=False,
                    summary=f"Awaiting approval: {decision.reason}",
                    decision=decision, requires_user_decision=True,
                    route_rule="scheduler",
                )
            if decision.outcome != ALLOW:
                self.tasks.transition(record.task_id, taskmod.ABORTED, decision.reason)
                record.requires_user_decision = False
                self.audit.record(
                    "policy_denied", task_id=record.task_id,
                    operation_id=record.operation_id,
                    capability=spec.capability_id, permission_level=decision.level,
                    authorization="denied", result="denied",
                    detail=f"resume denied: {decision.reason}"[:300],
                )
                self._journal("TASK_POLICY_DENIED", record,
                              metadata={"capability": spec.capability_id,
                                        "stage": "resume"})
                return TaskOutcome(
                    task_id=record.task_id, status=record.status,
                    owner_agent=record.owner_agent or spec.owner_agent,
                    capability_id=spec.capability_id, ok=False,
                    summary=f"Blocked by policy: {decision.reason}",
                    decision=decision, route_rule="scheduler",
                )
            self.tasks.transition(record.task_id, taskmod.AUTHORIZED,
                                  f"dependencies satisfied; {decision.reason}")
            record.authorization_context = self._compute_authorization_context(
                record, spec, None, decision)
            self.tasks.save(record, "authorized")
            self.audit.record(
                "authorized", task_id=record.task_id,
                operation_id=record.operation_id, agent=record.owner_agent or spec.owner_agent,
                capability=spec.capability_id, permission_level=decision.level,
                authorization=decision.reason, result="authorized",
                detail="scheduler resume authorization",
            )
            self._journal("TASK_AUTHORIZED", record,
                          metadata={"capability": spec.capability_id,
                                    "stage": "resume"})

        elif record.status == taskmod.PLANNED:
            blocker = self._capability_blocker(spec)
            if blocker is not None:
                final = (taskmod.ABORTED if isinstance(blocker, errors.PolicyDenied)
                         else taskmod.FAILED)
                return self._fail(record, spec.owner_agent, spec.capability_id,
                                  blocker, "authorization", final=final)
            decision = self.authorizer.authorize(
                spec,
                payload=dict(record.request_payload or {}) or {"goal": record.goal},
                approval="",
                user_requested=True,
                actor=record.requester or "scheduler",
            )
            if decision.outcome == CONFIRM:
                self.tasks.transition(record.task_id, taskmod.WAITING_FOR_APPROVAL,
                                      decision.reason)
                record.requires_user_decision = True
                self.audit.record(
                    "awaiting_approval", task_id=record.task_id,
                    operation_id=record.operation_id,
                    capability=spec.capability_id, permission_level=decision.level,
                    authorization="required", result="awaiting_approval",
                    detail=f"resume blocked: {decision.reason}"[:300],
                )
                self._journal("TASK_AWAITING_APPROVAL", record,
                              metadata={"capability": spec.capability_id,
                                        "stage": "resume"})
                return TaskOutcome(
                    task_id=record.task_id, status=record.status,
                    owner_agent=record.owner_agent or spec.owner_agent,
                    capability_id=spec.capability_id, ok=False,
                    summary=f"Awaiting approval: {decision.reason}",
                    decision=decision, requires_user_decision=True,
                    route_rule="scheduler",
                )
            if decision.outcome != ALLOW:
                self.tasks.transition(record.task_id, taskmod.ABORTED, decision.reason)
                record.requires_user_decision = False
                self.audit.record(
                    "policy_denied", task_id=record.task_id,
                    operation_id=record.operation_id,
                    capability=spec.capability_id, permission_level=decision.level,
                    authorization="denied", result="denied",
                    detail=f"resume denied: {decision.reason}"[:300],
                )
                self._journal("TASK_POLICY_DENIED", record,
                              metadata={"capability": spec.capability_id,
                                        "stage": "resume"})
                return TaskOutcome(
                    task_id=record.task_id, status=record.status,
                    owner_agent=record.owner_agent or spec.owner_agent,
                    capability_id=spec.capability_id, ok=False,
                    summary=f"Blocked by policy: {decision.reason}",
                    decision=decision, route_rule="scheduler",
                )
            self.tasks.transition(record.task_id, taskmod.AUTHORIZED,
                                  f"scheduler authorization: {decision.reason}")
            record.authorization_context = self._compute_authorization_context(
                record, spec, None, decision)
            self.tasks.save(record, "authorized")
            self.audit.record(
                "authorized", task_id=record.task_id,
                operation_id=record.operation_id, agent=record.owner_agent or spec.owner_agent,
                capability=spec.capability_id, permission_level=decision.level,
                authorization=decision.reason, result="authorized",
                detail="scheduler resume authorization",
            )
            self._journal("TASK_AUTHORIZED", record,
                          metadata={"capability": spec.capability_id,
                                    "stage": "resume"})

        elif record.status == taskmod.AUTHORIZED:
            blocker = self._capability_blocker(spec)
            if blocker is not None:
                return self._fail(record, spec.owner_agent, spec.capability_id,
                                  blocker, "authorization", final=taskmod.ABORTED)
            # Continuation of a previously authorized operation: capability/payload are
            # bound to the durable task record; policy/spec must still be executable.
            # Consequential approvals are single-use at initial authorization and
            # cannot be re-consumed here; resume must not mutate payload/capability.
            if getattr(spec, "capability_id", "") != record.capability_id:
                return self._fail(record, spec.owner_agent, record.capability_id,
                                  errors.PolicyDenied(
                                      "resume refused: capability mismatch"),
                                  "authorization", final=taskmod.ABORTED)
            ctx = getattr(record, "authorization_context", None) or {}
            changed, reason = self._is_material_authorization_change(record, spec, ctx)
            if changed:
                # Legacy/missing or stale context: fail closed for consequential actions.
                if int(getattr(spec, "risk_level", 0)) >= LEVEL_CONSEQUENTIAL or bool(record.approval_required):
                    return self._handle_stale_authorization(record, spec, reason)
                # Non-consequential: require safe executability (already checked) but allow
                # documented legacy/compatible continuation when policy is not stricter.
        else:
            raise errors.AjError(
                f"task {task_id} is {record.status}; scheduler needs AUTHORIZED",
                code=errors.CALLING_INVALID_STATE)

        route = Route(record.owner_agent or spec.owner_agent,
                      record.capability_id, "scheduler")
        self._journal("TASK_RESUMED", record,
                      metadata={"capability": spec.capability_id,
                                "status": record.status})
        return self._execute(record, route, spec,
                             dict(record.request_payload or {}), "",
                             int(self.config.get(
                                 "agents.jarvis.timeout_seconds", 120)))

    def dead_letter(self, task_id: str, reason: str) -> taskmod.TaskRecord:
        record = self.tasks.get(task_id)
        if record.status != taskmod.DEAD_LETTER:
            if not record.can_transition(taskmod.DEAD_LETTER):
                raise errors.AjError(
                    f"task {task_id} cannot be dead-lettered from {record.status}",
                    code=errors.CALLING_INVALID_STATE)
            self.tasks.transition(task_id, taskmod.DEAD_LETTER, reason)
            record = self.tasks.get(task_id)
            record.requires_user_decision = True
            self.tasks.save(record, "dead_letter")
            self.audit.record("task_dead_lettered", task_id=task_id,
                              operation_id=record.operation_id,
                              capability=record.capability_id,
                              result="dead_letter", detail=reason[:300])
            self._journal("TASK_DEAD_LETTERED", record,
                          metadata={"reason": reason[:300]})
            self._remember(record, "task.dead_letter", reason,
                           {"status": record.status})
        return record

    def inspect(self, task_id: str) -> Dict[str, Any]:
        """Inspect a task's complete dead-letter recovery context.

        Returns task context without mutation. Exposure includes:

        - task ID and operation ID
        - current state and transition history
        - attempt history with retry counts
        - failure information and error details
        - dependency state
        - lease state (active/expired/stale)
        - receipt state consistency
        - journal history entries
        - audit continuity and lineage
        - idempotency identity

        Inspection MUST NOT mutate the task state.
        """
        record = self.tasks.get(task_id)
        # Collect attempt history
        attempt_histories = []
        for attempt in record.attempts:
            attempt_histories.append({
                "attempt_id": attempt.get("attempt_id"),
                "attempt_number": attempt.get("attempt_number"),
                "started_at": attempt.get("started_at"),
                "ended_at": attempt.get("ended_at"),
                "status": attempt.get("status"),
                "failure": attempt.get("failure"),
            })
        # Collect journal history (read from journal if available)
        journal_histories = []
        if self.journal is not None:
            try:
                journal_entries = self.journal.events(task_id=task_id, limit=0)
                for entry in journal_entries:
                    journal_histories.append({
                        "event_type": entry.get("event_type"),
                        "at": entry.get("at"),
                        "metadata": entry.get("metadata"),
                    })
            except Exception:
                journal_histories = []
        # Collect audit continuity
        audit_continuity = []
        if self.audit is not None:
            try:
                recent = self.audit.recent(task_id=task_id)
                for entry in recent:
                    audit_continuity.append({
                        "action": entry.get("action"),
                        "actor": entry.get("actor"),
                        "agent": entry.get("agent"),
                        "result": entry.get("result"),
                    })
            except Exception:
                audit_continuity = []
        # Lease state
        lease_info = {"state": "none", "worker_id": None, "lease_id": None}
        try:
            lease = self.leases.get(task_id)
            if lease is not None:
                lease_info = {
                    "state": "active" if (getattr(lease, "status", "") == "ACTIVE" and not lease.expired()) else ("expired" if lease.expired() else str(getattr(lease, "status", "unknown")).lower()),
                    "worker_id": lease.worker_id,
                    "lease_id": lease.lease_id,
                }
        except Exception:
            pass
        # Receipt state
        receipt_info = {"status": record.status, "agrees": True}
        try:
            attempt = next((a for a in record.attempts if a.get("attempt_id")), {})
            receipt_info = {
                "status": record.status,
                "agrees": record.status.value == (attempt.get("status") if attempt else None),
            }
        except Exception:
            pass
        # Idempotency identity
        idempotency_key = ""
        try:
            # Check if there's an idempotency key associated with this task
            idempotency_key = getattr(record, "idempotency_key", "")
        except Exception:
            pass
        return {
            "task_id": record.task_id,
            "operation_id": record.operation_id,
            "status": record.status,
            "capability_id": record.capability_id,
            "requires_user_decision": record.requires_user_decision,
            "attempt_histories": attempt_histories,
            "journal_histories": journal_histories,
            "audit_continuity": audit_continuity,
            "lease_info": lease_info,
            "receipt_info": receipt_info,
            "idempotency_key": idempotency_key,
            "errors": [
                {"message": e.get("message"), "stage": e.get("stage")}
                for e in record.errors
            ],
            "events": [
                {"status": e.get("status")}
                for e in record.events
            ],
            "dependencies": getattr(record, "depends_on", []),
        }

    def requeue(self, task_id: str) -> TaskRecord:
        """Requeue a dead-letter task for re-execution.

        Transitions the task from DEAD_LETTER back to PLANNED state,
        preserving all historical identity, attempts, failure history,
        and audit/journal records. A new execution attempt will be
        created when the task is next executed.

        Requirements:
        - preserve original task identity
        - preserve operation identity
        - preserve historical attempts
        - do not erase failure history
        - do not reset historical audit/journal records
        - create a new execution attempt when execution occurs
        - preserve idempotency semantics
        - respect dependencies
        - respect task state transition rules
        - prevent duplicate logical operations

        Requeue MUST NOT silently create a brand-new logical task.
        """
        record = self.tasks.get(task_id)
        if record.status != taskmod.DEAD_LETTER:
            raise errors.AjError(
                f"task {task_id} is not in DEAD_LETTER state (current: {record.status})",
                code=errors.CALLING_INVALID_STATE)
        # Transition from DEAD_LETTER to PLANNED
        # DEAD_LETTER is normally terminal, but requeue explicitly allows
        # re-planning the work. Uses force=True since DEAD_LETTER is
        # designed to be a terminal state per the existing architecture.
        record.transition(taskmod.PLANNED, "requeue from dead-letter", force=True)
        record = self.tasks.get(task_id)
        record.requires_user_decision = False
        # Preserve the original operation_id and capability_id
        # Create a new execution attempt tracking entry
        number = max(int(record.attempt), len(record.attempts) + 1) if record.attempts else 1
        record.attempt = number
        attempt = {
            "attempt_id": ids.new_task_id("att"),
            "attempt_number": number,
            "operation_id": record.operation_id,
            "started_at": time.time(),
            "ended_at": None,
            "status": "PLANNED",
            "failure": None,
        }
        record.attempts.append(attempt)
        self.tasks.save(record, "requeue")
        self.audit.record("task_requeued", task_id=task_id,
                          operation_id=record.operation_id,
                          capability=record.capability_id,
                          result="planned", detail="requeue from dead-letter")
        self._journal("TASK_REQUEUED", record,
                      metadata={"reason": "requeue from dead-letter",
                                  "original_status": "DEAD_LETTER"})
        self._remember(record, "task.requeued", "requeued from dead-letter",
                       {"original_status": "DEAD_LETTER", "new_status": "PLANNED"})
        return record

    def abandon(self, task_id: str, reason: str = "") -> TaskRecord:
        """Explicitly abandon a dead-letter task.

        Produces a deterministic terminal state consistent with the
        existing architecture. The task and operation history are preserved
        entirely; all attempts are preserved; audit/journal history is
        preserved; future automatic execution is prevented.

        Requirements:
        - preserve the task and operation history
        - preserve all attempts
        - preserve audit/journal history
        - prevent future automatic execution
        - produce a deterministic terminal state consistent with the existing architecture
        - remain inspectable

        Do not delete the task.
        Do not erase evidence.
        Do not silently convert abandonment into success.
        """
        record = self.tasks.get(task_id)
        if record.status == "ABANDONED":
            raise errors.AjError(
                f"task {task_id} is already abandoned",
                code=errors.CALLING_INVALID_STATE)
        # Mark as abandoned while preserving all history
        record.status = "ABANDONED"
        record.requires_user_decision = False
        # Record the abandonment reason
        if reason:
            record.record_error(f"abandoned: {reason}", stage="abandonment")
        else:
            record.record_error("task abandoned", stage="abandonment")
        self.tasks.save(record, "abandoned")
        self.audit.record("task_abandoned", task_id=task_id,
                          operation_id=record.operation_id,
                          capability=record.capability_id,
                          result="abandoned", detail=reason[:300])
        self._journal("TASK_ABANDONED", record,
                      metadata={"reason": reason[:300] if reason else ""})
        self._remember(record, "task.abandoned", "task abandoned",
                       {"reason": reason})
        return record

    def _attempt_id(self, record: taskmod.TaskRecord) -> str:
        for attempt in reversed(record.attempts):
            if attempt.get("attempt_id"):
                return str(attempt["attempt_id"])
        return ""

    def _start_attempt(self, record: taskmod.TaskRecord) -> Dict[str, Any]:
        number = max(int(record.attempt), len(record.attempts) + 1)
        record.attempt = number
        attempt = {
            "attempt_id": ids.new_task_id("att"),
            "attempt_number": number,
            "operation_id": record.operation_id,
            "started_at": time.time(),
            "ended_at": None,
            "status": "RUNNING",
            "failure": None,
        }
        record.attempts.append(attempt)
        self.tasks.save(record, "attempt_started")
        return attempt

    def _finish_attempt(self, record: taskmod.TaskRecord, status: str,
                        error: Optional[errors.AjError] = None) -> Optional[Dict[str, Any]]:
        for attempt in reversed(record.attempts):
            if attempt.get("status") == "RUNNING":
                attempt["status"] = status
                attempt["ended_at"] = time.time()
                if error is not None:
                    attempt["failure"] = error.to_dict()
                return attempt
        return None

    def _remember(self, record: taskmod.TaskRecord, kind: str, content: str,
                  meta: Optional[Mapping[str, Any]] = None) -> Optional[int]:
        """Append one canonical raw event; memory failure never breaks a task."""
        if self.memory is None:
            return None
        payload = dict(meta or {})
        payload.setdefault("operation_id", record.operation_id)
        attempt_id = self._attempt_id(record)
        if attempt_id:
            payload.setdefault("attempt_id", attempt_id)
        try:
            return self.memory.append_event(kind, content, source="aj",
                                            task_id=record.task_id, meta=payload)
        except Exception as exc:  # the task continues; the gap is recorded
            record.note(f"memory write failed: {type(exc).__name__}: {exc}")
            return None

    def _fail(self, record: taskmod.TaskRecord, agent: str, capability_id: str,
              error: errors.AjError, stage: str,
              final: str = taskmod.FAILED) -> TaskOutcome:
        candidates = [final, taskmod.FAILED, taskmod.ABORTED, taskmod.RECOVERY_REQUIRED]
        target = None
        for candidate in candidates:
            if record.can_transition(candidate):
                target = candidate
                break
        try:
            if not record.terminal and target is not None:
                self.tasks.transition(record.task_id, target, error.message)
        except errors.AjError:
            pass  # already final or illegal in edge case; record remains accurate
        record.record_error(error, stage=stage)
        self._finish_attempt(record, taskmod.FAILED, error)
        self.tasks.save(record, "error")
        self.audit.record(
            "failed", task_id=record.task_id,
            operation_id=record.operation_id, attempt_id=self._attempt_id(record),
            agent=agent, capability=capability_id,
            result="failed", error=error.message[:300], detail=stage,
        )
        logging.getLogger("aj.orchestrator").info(
            "task=%s operation=%s attempt=%s capability=%s status=%s",
            record.task_id, record.operation_id, self._attempt_id(record),
            capability_id or "-", record.status,
        )
        self._remember(record, "task.failed", error.message,
                       {"agent": agent, "capability": capability_id,
                        "code": error.code, "stage": stage,
                        "status": record.status})
        self._journal("EXECUTION_FAILED", record,
                      attempt_id=self._attempt_id(record),
                      metadata={"code": error.code, "stage": stage})
        self._receipt(record, self._attempt_id(record), capability_id,
                      "FAILED", "failed", None, [])
        return TaskOutcome(
            task_id=record.task_id, status=record.status, owner_agent=agent,
            capability_id=capability_id, ok=False, summary=error.message,
            errors=[error.to_dict()],
        )


def build(config: Optional[Config] = None, *, memory: Optional[MemoryStore] = None,
          actions: Optional[InternalActions] = None,
          calling: Optional[CallingService] = None) -> Aj:
    """Construct the control plane from configuration.

    AJ's own safe capabilities are always registered. Declarations load from
    ``config/capabilities.json``; the JARVIS tool catalogue is imported from
    JARVIS's own registry so there is one authority for those tiers.
    """
    from pathlib import Path

    from .integrations.jarvis_registry import load_into

    config = config or load_config()
    root = Path(__file__).resolve().parent.parent
    registry = CapabilityRegistry()
    registry.register_many(internal_specs())
    declarations = config.get("capability.declarations", "config/capabilities.json")
    path = root / str(declarations)
    if path.is_file():
        registry.register_many(CapabilityRegistry.load_json(path).all())
    if config.get("capability.load_jarvis_registry", True):
        jarvis_root = config.get("capability.jarvis_root", "") or str(root.parent / "JARVIS")
        load_into(registry, jarvis_root)
    service = calling or CallingService()
    # Availability is about the live environment, not the mere presence of code.
    # helix.prepare_call is dispatchable through the calling service, but without
    # a contact resolver it cannot complete successfully on this host.
    spec = registry.find("helix.prepare_call")
    if spec is not None and getattr(service, "resolver", None) is not None:
        registry.set_availability(spec.capability_id, "available")
    elif spec is not None:
        registry.set_availability(spec.capability_id, "unavailable")
    return Aj(registry=registry, agents=AgentRegistry.from_config(config),
              config=config, memory=memory, actions=actions, calling=service)