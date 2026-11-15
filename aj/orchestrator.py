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

import copy
import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import logging

from . import errors, ids, invariants, permissions, task as taskmod
from .actions import InternalActions, default_actions, specs as internal_specs
from .calling import CallingService, CallState
from .execution_domain import (
    CANCELLED as EXEC_CANCELLED,
    COMPLETED as EXEC_COMPLETED,
    CREATED as EXEC_CREATED,
    FAILED as EXEC_FAILED,
    READY as EXEC_READY,
    RECOVERY_REQUIRED as EXEC_RECOVERY_REQUIRED,
    RUNNING as EXEC_RUNNING,
    UNKNOWN as EXEC_UNKNOWN,
    ExecutionRecord,
    ExecutionStore,
)
from .delegation import AssignmentStore, DelegationStore, LogicalAgentStore, detect_delegation_anomalies
from .idempotency import IdempotencyStore
from .journal import Journal
from .lease import LeaseManager
from .receipts import ReceiptStore
from .agents import AgentRegistry, UnconfiguredAgent
from .audit import AuditLog, JsonlAuditSink
from .capability import OWNER_AJ, CapabilityRegistry, CapabilitySpec
from .config import Config, load as load_config, require_path
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
        executions: Optional[ExecutionStore] = None,
        delegations: Optional[DelegationStore] = None,
        assignments: Optional[AssignmentStore] = None,
        logical_agents: Optional[LogicalAgentStore] = None,
    ):
        self.config = config or load_config()
        self.registry = registry or CapabilityRegistry()
        self.agents = agents or AgentRegistry()
        self.audit = audit or AuditLog(
            JsonlAuditSink(require_path(self.config, "core.audit_dir"))
        )
        if authorizer is not None:
            self.authorizer = authorizer
        else:
            self.authorizer = Authorizer(
                unattended_ceiling=int(self.config.get("permissions.unattended_ceiling", 1))
            )
        persist_dir = (require_path(self.config, "core.data_dir")
                       if self.config.get("runtime.persist_tasks", True)
                       else None)
        self.tasks = tasks or taskmod.TaskStore(persist_dir)
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
        self.executions = executions or (ExecutionStore(data_dir / "executions.jsonl")
                                        if data_dir else None)
        self.delegations = delegations or (DelegationStore(data_dir / "delegations.jsonl")
                                           if data_dir else None)
        self.assignments = assignments or (AssignmentStore(data_dir / "assignments.jsonl")
                                           if data_dir else None)
        self.logical_agents = logical_agents or (LogicalAgentStore(data_dir / "logical_agents.jsonl")
                                                 if data_dir else None)
        self.leases = leases or LeaseManager(
            data_dir, audit=self.audit, journal=self.journal)
        # Phase 3E: durable evidence for privileged operations and authorization guardrail
        self.operation_evidence = None
        try:
            from .operation_evidence import OperationEvidenceStore
            if data_dir:
                self.operation_evidence = OperationEvidenceStore(data_dir / "reconciliation_operations.jsonl")
        except Exception:
            self.operation_evidence = None
        self.privileged_authorizer = None
        try:
            from .authorization import build_privileged_authorizer, UnavailablePrivilegedAuthorizer
            auth_cfg = {}
            try:
                perms = self.config.section("permissions") if hasattr(self.config, "section") else {}
                if isinstance(perms, dict):
                    auth_cfg = perms.get("privileged_reconciliation") or perms.get("privileged_operations") or {}
                    if not isinstance(auth_cfg, dict):
                        auth_cfg = {}
            except Exception:
                auth_cfg = {}
            self.privileged_authorizer = build_privileged_authorizer(auth_cfg)
        except Exception:
            try:
                from .authorization import UnavailablePrivilegedAuthorizer
                self.privileged_authorizer = UnavailablePrivilegedAuthorizer()
            except Exception:
                self.privileged_authorizer = None
        # 5A.6R2: central lifecycle hooks for delegation parent enforcement/reconciliation.
        self._delegation_reconcile_guard = threading.RLock()
        self._delegation_reconcile_local = threading.local()
        try:
            self.tasks.after_transition = self._on_task_transition
            _orig_transition = self.tasks.transition
            def _guarded_transition(task_id, status, detail="", *, force=False, reason="transition"):
                self._before_task_transition(task_id, status, detail, force=force, reason=reason)
                return _orig_transition(task_id, status, detail, force=force, reason=reason)
            self.tasks.transition = _guarded_transition
        except Exception:
            pass

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
            self.tasks.save(record, "metadata")
        self.tasks.transition(record.task_id, taskmod.PLANNED, route.rule)
        record = self.tasks.get(record.task_id)

        blocked_by = self.unsatisfied_dependencies(record)
        if blocked_by:
            reason = f"waiting for dependencies: {', '.join(blocked_by)}"
            self.tasks.transition(record.task_id, taskmod.BLOCKED, reason)
            record = self.tasks.get(record.task_id)
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
            record = self.tasks.get(record.task_id)
            record.requires_user_decision = True
            record.approval_required = decision.requires_approval
            self.tasks.save(record, "awaiting_approval")
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
            record = self.tasks.get(record.task_id)
            record.requires_user_decision = False
            record.approval_required = decision.requires_approval
            self.tasks.save(record, "policy_denied")
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
        record = self.tasks.get(record.task_id)
        if spec is not None:
            record.authorization_context = self._compute_authorization_context(
                record, spec, payload, decision)
        record.approval_required = decision.requires_approval
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
            record = self.tasks.transition(task_id, taskmod.ESCALATED,
                                           "needs a human decision")
            record.requires_user_decision = True
            record = self.tasks.save(record, "retry_escalated")
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
            record = self.tasks.get(record.task_id)
            record.requires_user_decision = True
            record.note(f"retry refused: {reason}")
            record = self.tasks.save(record, "retry_refused")
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
            record = self.tasks.get(record.task_id)
            record.requires_user_decision = True
            record.note(f"retry refused: {reason}")
            record = self.tasks.save(record, "retry_refused")
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
            record = self.tasks.get(record.task_id)
            record.requires_user_decision = True
            record.note(f"retry refused: {reason}")
            record = self.tasks.save(record, "retry_refused")
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
        record = self.tasks.get(task_id)
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
            record = self.tasks.get(record.task_id)
            record.requires_user_decision = True
            record = self.tasks.save(record, "cancel_requested")
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
        record = self.tasks.transition(record.task_id, taskmod.CANCELLED,
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
        try:
            with self.leases.hold(task_id, "recover"):
                return self._recover_locked(task_id, approval=approval)
        except (errors.LeaseHeld, errors.LeaseExpired) as exc:
            # Another active operation/execution owner serializes this task; recovery
            # must not steal ownership or replay. Report blocked/convergent refusal.
            try:
                record = self.tasks.get(task_id)
                self.audit.record(
                    "recovery_blocked", task_id=task_id,
                    operation_id=getattr(record, "operation_id", ""), agent="AJ",
                    capability=getattr(record, "capability_id", ""),
                    result="blocked", authorization="none",
                    detail=str(exc)[:300],
                )
                return TaskOutcome(
                    task_id=task_id, status=record.status, owner_agent="AJ",
                    capability_id=getattr(record, "capability_id", ""), ok=False,
                    summary=f"Recovery blocked: {exc}",
                    requires_user_decision=False, route_rule="recovery",
                )
            except Exception:
                raise

    # --- recovery evidence & decisions ------------------------------------

    def _recovery_evidence(self, record: taskmod.TaskRecord) -> Dict[str, Any]:
        """Collect best-effort durable evidence for recovery decisions.

        Evidence is observational and never implies success by absence. Journal/
        receipt reads are fail-closed on malformed or newer-schema data so recovery
        cannot infer a safe outcome from corrupted/incompatible evidence.
        """
        task_id = record.task_id
        evidence: Dict[str, Any] = {
            "task_id": task_id,
            "status": record.status,
            "attempt_count": len(record.attempts or []),
            "current_attempt": int(getattr(record, "attempt", 0) or 0),
            "receipts": [],
            "journal_events": [],
            "journal_malformed": 0,
            "execution_lease": None,
            "errors": [],
        }
        # Receipts (task-scoped). ReceiptStore validates schema on read.
        if self.receipts is not None:
            try:
                evidence["receipts"] = list(self.receipts.list(task_id=task_id, limit=0))
            except Exception as exc:
                evidence["errors"].append(f"receipt_read_failed:{type(exc).__name__}:{exc}")
        # Journal (task-scoped). Treat malformed/newer-schema as unsafe evidence.
        if self.journal is not None:
            try:
                evidence["journal_malformed"] = int(self.journal.malformed() or 0)
                if evidence["journal_malformed"] > 0:
                    evidence["errors"].append("journal_contains_malformed_entries")
                evidence["journal_events"] = list(self.journal.events(task_id=task_id, limit=0))
            except Exception as exc:
                evidence["errors"].append(f"journal_read_failed:{type(exc).__name__}:{exc}")
        # Execution lease visibility (ownership/liveness hint, not an authority).
        try:
            lease = self.leases.get(task_id)
            if lease is not None and getattr(lease, "operation", "") == "execute":
                evidence["execution_lease"] = {
                    "lease_id": lease.lease_id,
                    "status": lease.status,
                    "worker_id": lease.worker_id,
                    "holder": lease.holder,
                    "issued_at": lease.issued_at,
                    "expires_at": lease.expires_at,
                    "last_heartbeat_at": lease.last_heartbeat_at,
                    "expired": bool(lease.expired()),
                }
        except Exception as exc:
            evidence["errors"].append(f"lease_read_failed:{type(exc).__name__}:{exc}")
        return evidence

    @staticmethod
    def _recovery_attempt_evidence(record: taskmod.TaskRecord,
                                   evidence: Dict[str, Any]) -> Dict[str, Any]:
        attempts = list(getattr(record, "attempts", []) or [])
        latest = attempts[-1] if attempts else None
        latest_id = str((latest or {}).get("attempt_id") or "")
        running = [a for a in attempts if a.get("status") == "RUNNING"]
        receipts = [r for r in (evidence.get("receipts") or [])
                    if isinstance(r, dict)]
        latest_receipts = [r for r in receipts if latest_id and r.get("attempt_id") == latest_id]
        events = [e for e in (evidence.get("journal_events") or [])
                  if isinstance(e, dict)]
        latest_events = [e for e in events if latest_id and e.get("attempt_id") == latest_id]
        started = [e for e in latest_events if e.get("event_type") == "EXECUTION_STARTED"]
        completed = [e for e in latest_events if e.get("event_type") in (
            "EXECUTION_COMPLETED", "EXECUTION_RESULT_RECORDED")]
        failed = [e for e in latest_events if e.get("event_type") == "EXECUTION_FAILED"]
        def _rstate(r: Dict[str, Any]) -> str:
            return str(r.get("execution_status") or r.get("result_state") or r.get("status") or "")
        terminal_receipts = [r for r in latest_receipts if _rstate(r) in (
            "COMPLETED", "FAILED", "CANCELLED", "ABORTED")]
        success_receipts = [r for r in latest_receipts if _rstate(r) == "COMPLETED"]
        # Also consider any task-level completion receipt as convergence evidence.
        any_success_receipt = [r for r in receipts if _rstate(r) == "COMPLETED"]
        return {
            "latest_attempt": latest,
            "latest_attempt_id": latest_id,
            "running_attempts": running,
            "latest_receipts": latest_receipts,
            "latest_terminal_receipts": terminal_receipts,
            "latest_success_receipts": success_receipts,
            "any_success_receipts": any_success_receipt,
            "latest_started_events": started,
            "latest_completed_events": completed,
            "latest_failed_events": failed,
        }

    def _assess_recovery(self, record: taskmod.TaskRecord) -> Dict[str, Any]:
        """Return an evidence-based recovery assessment.

        Decisions:
          - terminal: no recovery
          - converged: canonical state/evidence already settled; no replay
          - replay: automatic replay is demonstrably safe now
          - reconcile: ambiguous or unsafe to replay automatically
          - blocked: cannot decide safely now (e.g. active owner lease) but not a
                     canonical failure; repeated attempts must converge
        """
        spec = self.registry.find(record.capability_id) if record.capability_id else None
        assessment: Dict[str, Any] = {
            "task_id": record.task_id,
            "status": record.status,
            "decision": "reconcile",
            "reason": "insufficient recovery evidence",
            "spec": spec,
            "evidence": {},
        }
        if record.terminal:
            assessment.update({"decision": "terminal",
                               "reason": f"task is terminal ({record.status})"})
            return assessment

        try:
            evidence = self._recovery_evidence(record)
        except Exception as exc:
            assessment.update({
                "decision": "reconcile",
                "reason": f"evidence collection failed closed: {type(exc).__name__}: {exc}",
                "evidence": {"errors": [f"collection_failed:{exc}"]},
            })
            return assessment
        assessment["evidence"] = evidence
        if evidence.get("errors"):
            assessment.update({
                "decision": "reconcile",
                "reason": "recovery evidence is missing/malformed/conflicting: "
                          + "; ".join(str(e) for e in evidence["errors"])[:300],
            })
            return assessment

        ae = self._recovery_attempt_evidence(record, evidence)
        latest = ae["latest_attempt"]
        latest_id = ae["latest_attempt_id"]
        latest_receipts = ae["latest_terminal_receipts"]
        success_receipts = ae["latest_success_receipts"] or ae["any_success_receipts"]
        started = ae["latest_started_events"]
        completed_events = ae["latest_completed_events"]
        failed_events = ae["latest_failed_events"]

        # Active execution owner: do not steal/replay; fail closed for this call.
        ex = evidence.get("execution_lease") or {}
        if ex and ex.get("status") == "ACTIVE" and not ex.get("expired", False):
            assessment.update({
                "decision": "blocked",
                "reason": "active execution lease present; another worker may own the task",
            })
            return assessment

        # Already-converged / no-work states.
        if record.status == taskmod.RECOVERY_REQUIRED:
            assessment.update({
                "decision": "converged",
                "reason": "task is already waiting for explicit recovery/reconciliation",
            })
            return assessment
        if record.status in (taskmod.WAITING_FOR_APPROVAL, taskmod.ESCALATED,
                             taskmod.CANCEL_REQUESTED):
            assessment.update({
                "decision": "converged",
                "reason": f"task is {record.status}; no automatic execution replay",
            })
            return assessment
        if record.status == taskmod.BLOCKED:
            assessment.update({
                "decision": "converged",
                "reason": "task is blocked on dependencies; scheduler/resume owns progression",
            })
            return assessment
        if record.status == taskmod.COMPLETED:
            assessment.update({"decision": "terminal",
                               "reason": "task is already completed"})
            return assessment

        # Completion evidence present: converge without replay. Prefer explicit
        # persisted terminal state; if a completion receipt exists but task is still
        # non-terminal due interruption, require reconciliation rather than guessing
        # a transition not supported by current state machine/evidence.
        if success_receipts and record.status == taskmod.COMPLETED:
            assessment.update({"decision": "terminal",
                               "reason": "completed receipt and terminal task state"})
            return assessment
        if success_receipts and record.status in taskmod.TERMINAL:
            assessment.update({"decision": "terminal",
                               "reason": "terminal task state with completion evidence"})
            return assessment
        if success_receipts and record.status != taskmod.COMPLETED:
            assessment.update({
                "decision": "reconcile",
                "reason": "completion receipt exists but canonical task state is not terminal; "
                          "automatic replay/resurrection is unsafe",
            })
            return assessment

        # Capability/safety preconditions for any replay.
        if spec is None:
            assessment.update({
                "decision": "reconcile",
                "reason": (f"capability {record.capability_id!r} is not registered"
                           if record.capability_id else "task has no capability to replay"),
            })
            return assessment
        if not spec.execution_adapter.startswith("internal:"):
            assessment.update({
                "decision": "reconcile",
                "reason": "capability is not an internal action; external side effects cannot be ruled out",
            })
            return assessment
        if not spec.replay_safe:
            assessment.update({
                "decision": "reconcile",
                "reason": "capability is not declared replay-safe",
            })
            return assessment

        # Internal replay-safe actions have no external side effects by contract, so
        # a started-but-unfinished in-process attempt is safe to replay/reconcile;
        # but existing terminal attempt evidence for the latest attempt must not be
        # ignored (converge or require reconciliation on conflict).
        if latest is not None and latest.get("status") == "RUNNING" and latest_receipts:
            assessment.update({
                "decision": "reconcile",
                "reason": "running attempt has conflicting terminal receipt evidence",
            })
            return assessment
        if failed_events and not started and not completed_events and not latest_receipts:
            # journal-only failure evidence without attempt/receipt state is odd; fail closed
            assessment.update({
                "decision": "reconcile",
                "reason": "conflicting/incomplete failure evidence for latest attempt",
            })
            return assessment
        if completed_events and latest_receipts and not success_receipts:
            # terminal non-success evidence exists for latest attempt
            if record.status == taskmod.FAILED:
                assessment.update({
                    "decision": "replay",
                    "reason": "failed replay-safe internal action may be retried within policy/budget",
                })
                return assessment
            assessment.update({
                "decision": "reconcile",
                "reason": "latest attempt has terminal non-success evidence; manual reconciliation required",
            })
            return assessment

        # At this point: replay-safe internal capability, no completion evidence, no
        # active owner. Determine if automatic replay is appropriate for state/budget.
        if record.status in (taskmod.AUTHORIZED, taskmod.EXECUTING, taskmod.RETRYING,
                             taskmod.RECEIVED, taskmod.UNDERSTANDING, taskmod.PLANNED,
                             taskmod.FAILED, taskmod.RECOVERING, taskmod.VERIFYING):
            # Respect retry/attempt budget for states that represent prior failures.
            if record.status in (taskmod.FAILED, taskmod.RECOVERING, taskmod.RETRYING):
                try:
                    attempt_count = int(getattr(record, "attempt", 0) or 0)
                    max_attempts = int(getattr(record, "max_attempts", 1) or 1)
                except Exception:
                    assessment.update({"decision": "reconcile",
                                       "reason": "attempt budget metadata is invalid"})
                    return assessment
                if attempt_count >= max_attempts and record.status != taskmod.RECOVERING:
                    # FAILED/RETRYING at budget: do not auto-replay; preserve/escalate path exists.
                    assessment.update({
                        "decision": "reconcile",
                        "reason": "retry budget exhausted for automatic replay",
                    })
                    return assessment
            assessment.update({
                "decision": "replay",
                "reason": "replay-safe internal action with no completion/ownership conflict evidence",
            })
            return assessment

        assessment.update({
            "decision": "reconcile",
            "reason": f"state {record.status} is not automatically replayable from available evidence",
        })
        return assessment

    def _recovery_blocked_outcome(self, record: taskmod.TaskRecord,
                                  reason: str) -> TaskOutcome:
        self.audit.record(
            "recovery_blocked", task_id=record.task_id,
            operation_id=record.operation_id, agent="AJ",
            capability=record.capability_id, result="blocked",
            authorization="none", detail=reason[:300],
        )
        return TaskOutcome(
            task_id=record.task_id, status=record.status, owner_agent="AJ",
            capability_id=record.capability_id, ok=False,
            summary=f"Recovery blocked: {reason}",
            requires_user_decision=False, route_rule="recovery",
        )

    def _recover_locked(self, task_id: str, *, approval: str = "") -> TaskOutcome:
        """Recover one interrupted task using explicit evidence.

        Never blindly replays based on status alone. Automatic replay is allowed only
        for demonstrably safe cases; ambiguous/malformed/conflicting cases fail closed
        to reconciliation/manual handling. Repeated calls must converge.
        """
        record = self.tasks.get(task_id)
        if record.terminal:
            # Convergent no-op: terminal tasks must never be resurrected or mutated.
            self.audit.record(
                "recovery_converged", task_id=record.task_id,
                operation_id=getattr(record, "operation_id", ""), agent="AJ",
                capability=getattr(record, "capability_id", ""), result="terminal",
                authorization="none", detail=f"task is terminal ({record.status})"[:300],
            )
            return TaskOutcome(
                task_id=record.task_id, status=record.status, owner_agent="AJ",
                capability_id=getattr(record, "capability_id", ""), ok=True,
                summary=f"Recovery converged: task is terminal ({record.status})",
                requires_user_decision=False, route_rule="recovery",
            )

        assessment = self._assess_recovery(record)
        decision = assessment.get("decision")
        reason = str(assessment.get("reason") or "recovery decision unavailable")
        evidence = assessment.get("evidence") or {}

        # Persist recovery assessment evidence for auditability/debuggability.
        try:
            self.tasks.mutate(task_id, "recovery_assessment", lambda r: (
                r.recovery.update({
                    "last_assessed_at": time.time(),
                    "last_decision": decision,
                    "last_reason": reason[:500],
                    "evidence_summary": {
                        "status": evidence.get("status"),
                        "attempt_count": evidence.get("attempt_count"),
                        "current_attempt": evidence.get("current_attempt"),
                        "receipt_count": len(evidence.get("receipts") or []),
                        "journal_event_count": len(evidence.get("journal_events") or []),
                        "journal_malformed": evidence.get("journal_malformed", 0),
                        "execution_lease": evidence.get("execution_lease"),
                    },
                })
            ))
            record = self.tasks.get(task_id)
        except Exception:
            # assessment persistence must not mask a safe/convergent decision
            record = self.tasks.get(task_id)

        if decision == "converged":
            self.audit.record(
                "recovery_converged", task_id=record.task_id,
                operation_id=record.operation_id, agent="AJ",
                capability=record.capability_id, result="converged",
                authorization="none", detail=reason[:300],
            )
            self._remember(record, "task.recovery_converged", reason,
                           {"status": record.status, "capability": record.capability_id})
            return TaskOutcome(
                task_id=record.task_id, status=record.status, owner_agent="AJ",
                capability_id=record.capability_id, ok=True,
                summary=f"Recovery converged: {reason}",
                requires_user_decision=bool(record.requires_user_decision),
                route_rule="recovery",
            )
        if decision == "blocked":
            return self._recovery_blocked_outcome(record, reason)
        if decision != "replay":
            return self._require_manual_recovery(record, reason)

        spec = assessment.get("spec") or self.registry.find(record.capability_id)
        if spec is None:
            return self._require_manual_recovery(record, reason)

        blocker = self._capability_blocker(spec)
        if blocker is not None:
            return self._require_manual_recovery(record, blocker.message)

        payload = dict(record.request_payload or {})
        try:
            decision_auth = self.authorizer.authorize(
                spec,
                payload=payload or {"goal": record.goal},
                approval=approval,
                user_requested=True,
                actor="recovery",
            )
        except Exception as exc:
            return self._require_manual_recovery(
                record, f"recovery authorization failed closed: {exc}")
        if decision_auth.outcome != ALLOW:
            return self._require_manual_recovery(
                record,
                f"recovery authorization {decision_auth.outcome.lower()}: {decision_auth.reason}",
            )

        # Move to an executable replay state only through legal transitions.
        if record.status not in (taskmod.AUTHORIZED, taskmod.EXECUTING,
                                 taskmod.RETRYING):
            # FAILED uses the normal retry/recovery path semantics when budget allows.
            if record.status == taskmod.FAILED:
                if int(record.attempt) < int(record.max_attempts):
                    record = self.tasks.transition(record.task_id, taskmod.RECOVERING,
                                                   f"recovery: {reason[:200]}")
                    record = self.tasks.transition(record.task_id, taskmod.RETRYING,
                                                   f"recovery attempt {record.attempt + 1}")
                else:
                    return self._require_manual_recovery(
                        record, "retry budget exhausted for automatic replay")
            elif record.can_transition(taskmod.AUTHORIZED):
                record = self.tasks.transition(record.task_id, taskmod.AUTHORIZED,
                                               f"recovery: replay-safe action ({reason[:160]})")
            else:
                return self._require_manual_recovery(
                    record, f"{record.status} cannot move to an executable replay state")

        # Convergence guard: do not create unbounded replay attempts on repeated recovery.
        # _execute/_start_attempt will advance attempt for the new execution.
        if record.status in (taskmod.EXECUTING, taskmod.AUTHORIZED, taskmod.RETRYING):
            ae = self._recovery_attempt_evidence(record, evidence)
            latest = ae.get("latest_attempt") or {}
            # If latest attempt is still RUNNING with no terminal evidence and we are
            # replaying same interrupted execution context, require reconciliation once
            # ambiguity cannot be disproven except by declared replay safety + absence
            # of external effects (internal replay-safe). We still replay, but bound
            # by attempt budget.
            if int(record.attempt) >= int(record.max_attempts) and record.status == taskmod.RETRYING:
                return self._require_manual_recovery(
                    record, "retry budget exhausted for automatic replay")

        self.audit.record(
            "recovery_started", task_id=record.task_id,
            operation_id=record.operation_id, agent="AJ",
            capability=spec.capability_id, result="replaying",
            authorization=decision_auth.reason, detail=reason[:300],
        )
        self._remember(record, "task.recovery", "safe replay started",
                       {"capability": spec.capability_id,
                        "attempt": int(record.attempt) + 1,
                        "decision_reason": reason[:200]})
        self._journal("RECOVERY_STARTED", record,
                      attempt_id=self._attempt_id(record),
                      metadata={"capability": spec.capability_id,
                                "reason": reason[:200],
                                "evidence_decision": "replay"})
        route = Route(spec.owner_agent, spec.capability_id,
                      "recovery: replay-safe internal action")
        try:
            outcome = self._execute(
                record, route, spec, payload, approval,
                int(self.config.get("agents.jarvis.timeout_seconds", 120)),
            )
            return outcome
        except Exception as exc:
            # Recovery execution/persistence failures must fail closed and remain
            # retryable/convergent without claiming success.
            try:
                current = self.tasks.get(task_id)
                self.audit.record(
                    "recovery_failed", task_id=task_id,
                    operation_id=getattr(current, "operation_id", ""),
                    agent="AJ", capability=getattr(current, "capability_id", ""),
                    result="failed", detail=f"{type(exc).__name__}: {exc}"[:300],
                )
            except Exception:
                pass
            raise

    def _require_manual_recovery(self, record: taskmod.TaskRecord,
                                 reason: str) -> TaskOutcome:
        # Idempotent/convergent: repeated calls keep the task in RECOVERY_REQUIRED
        # (or preserve an already-safe non-executable state) without mutating
        # canonical execution history beyond explicit recovery bookkeeping.
        reason = (reason or "manual recovery required")[:500]
        if record.terminal:
            return TaskOutcome(
                task_id=record.task_id, status=record.status, owner_agent="AJ",
                capability_id=record.capability_id, ok=False,
                summary=f"Recovery required: {reason}",
                requires_user_decision=False, route_rule="recovery",
            )
        if record.can_transition(taskmod.RECOVERY_REQUIRED):
            try:
                record = self.tasks.transition(record.task_id, taskmod.RECOVERY_REQUIRED, reason)
            except Exception:
                record = self.tasks.get(record.task_id)
        else:
            record = self.tasks.get(record.task_id)
        needs_save = (not bool(getattr(record, "requires_user_decision", False))
                      or reason not in "\n".join(getattr(record, "warnings", []) or []))
        if needs_save:
            record.requires_user_decision = True
            record.note(f"recovery required: {reason}")
            try:
                self.tasks.save(record, "recovery_required")
            except Exception:
                # Fail closed: do not claim recovery classification if persistence fails.
                raise
            record = self.tasks.get(record.task_id)
        else:
            record = self.tasks.get(record.task_id)
        self.audit.record(
            "recovery_refused", task_id=record.task_id,
            operation_id=record.operation_id, agent="AJ",
            capability=record.capability_id, result="recovery_required",
            authorization="none", detail=reason[:300],
        )
        try:
            self._remember(record, "task.recovery_refused", reason,
                           {"capability": record.capability_id,
                            "status": record.status})
        except Exception:
            pass
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
        # Defense-in-depth: delegated child execution must satisfy recorded narrowing envelope.
        if spec is not None:
            guard = self._delegated_permission_guard(record, spec)
            if guard is not None:
                return guard
        self.tasks.transition(record.task_id, taskmod.EXECUTING,
                             f"{route.owner_agent}:{route.capability_id or 'delegate'}")
        record = self.tasks.get(record.task_id)
        # First-class execution domain: create/persist AJ-owned execution before attempt dispatch.
        exec_rec = self._ensure_execution(
            record,
            agent_id=route.owner_agent or str(getattr(record, "owner_agent", "") or ""),
            reason=f"{route.owner_agent}:{route.capability_id or 'delegate'}",
        )
        if exec_rec is not None and exec_rec.status == EXEC_CREATED:
            self._transition_execution(record, EXEC_READY, detail="dispatch ready")
        self._start_attempt(record)
        record = self.tasks.get(record.task_id)
        attempt_id = self._attempt_id(record)
        current_lease = self.leases.get(record.task_id)
        xid = self._current_execution_id(record)
        journal_ids = [self._journal(
            "EXECUTION_STARTED", record, attempt_id=attempt_id,
            lease_id=current_lease.lease_id if current_lease else "",
            execution_id=xid,
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
            record = self.tasks.get(record.task_id)
            record.record_action("execute",
                                 f"capability={spec.capability_id} action={action}")
            record.evidence.append({"action": action, "verified": True})
            record = self.tasks.save(record, "executing_update")
            self.tasks.transition(record.task_id, taskmod.VERIFYING,
                                 "internal action returned")
            self.tasks.transition(record.task_id, taskmod.COMPLETED,
                                 f"internal:{action}")
            record = self.tasks.get(record.task_id)
            record.summary = f"{spec.capability_id} completed"
            self._finish_attempt(record, taskmod.COMPLETED)
            record = self.tasks.save(record, "completed")
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

        # Execution through the Hermes boundary, when a skill/capability is named.
        if spec is not None and spec.owner_agent == "HERMES":
            # Pass AJ correlation/operation/attempt context in arguments for v0 adapters.
            exec_args = dict(payload or {})
            exec_args.setdefault("operation_id", record.operation_id)
            exec_args.setdefault("attempt_id", attempt_id)
            exec_args.setdefault("correlation_id", record.task_id)
            exec_args.setdefault("idempotency_key", getattr(record, "idempotency_key", "") or "")
            request = ExecutionRequest(
                request_id=f"{record.task_id}/exec/{attempt_id or '0'}",
                capability_id=spec.capability_id,
                arguments=exec_args,
                task_id=record.task_id,
                permission_level=spec.risk_level,
                approval_token=approval,
                timeout_seconds=timeout_seconds,
            )
            try:
                result = execute(self.execution, request)
            except errors.AjError as exc:
                self._journal("EXECUTION_FAILED", record, attempt_id=attempt_id,
                              metadata={"code": exc.code})
                self._receipt(record, attempt_id, spec.capability_id, "FAILED",
                              "failed", {"error": exc.to_dict()}, journal_ids)
                return self._fail(record, "HERMES", spec.capability_id, exc, "executing")
            record = self.tasks.get(record.task_id)
            record.record_action("execute", f"capability={spec.capability_id}")
            out = result.output if isinstance(result.output, dict) else {"result": result.output}
            record.evidence.append({
                "verified": result.verified,
                "status": result.status,
                "adapter_output": out,
            })
            record = self.tasks.save(record, "executing_update")
            if not result.ok:
                self.tasks.transition(record.task_id, taskmod.FAILED, result.status)
                record = self.tasks.get(record.task_id)
                record.record_error(result.error or {"message": result.status}, stage="executing")
                self._finish_attempt(record, taskmod.FAILED,
                                     errors.ExecutionFailed(str((result.error or {}).get("message", result.status))
                                                            if isinstance(result.error, dict) else str(result.status)))
                record = self.tasks.save(record, "failed")
                self.audit.record("execution_failed", task_id=record.task_id,
                                  operation_id=record.operation_id,
                                  attempt_id=attempt_id, agent="HERMES",
                                  capability=spec.capability_id, result=result.status,
                                  error=str(result.error or ""))
                self._remember(record, "task.failed", f"Execution {result.status}",
                               {"capability": spec.capability_id, "status": record.status})
                journal_ids.append(self._journal("EXECUTION_RESULT_RECORDED", record, attempt_id=attempt_id,
                                                 metadata={"status": record.status}))
                self._receipt(record, attempt_id, spec.capability_id, "FAILED",
                              "failed", out, journal_ids)
                return TaskOutcome(
                    task_id=record.task_id, status=record.status, owner_agent="HERMES",
                    capability_id=spec.capability_id, ok=False,
                    summary=f"Execution {result.status}", route_rule=route.rule,
                    errors=[result.error] if result.error else [], output=out,
                )
            self.tasks.transition(record.task_id, taskmod.VERIFYING, "execution returned")
            self.tasks.transition(record.task_id, taskmod.COMPLETED,
                                  "verified" if result.verified else "completed unverified")
            record = self.tasks.get(record.task_id)
            record.summary = f"Capability {spec.capability_id} {result.status}"
            self._finish_attempt(record, taskmod.COMPLETED)
            record = self.tasks.save(record, "completed")
            self._remember(record, "task.completed", record.summary,
                           {"capability": spec.capability_id, "status": record.status})
            self.audit.record("executed", task_id=record.task_id,
                              operation_id=record.operation_id, attempt_id=attempt_id,
                              agent="HERMES", capability=spec.capability_id,
                              permission_level=spec.risk_level,
                              authorization="local_trust", result=record.status)
            journal_ids.append(self._journal("EXECUTION_RESULT_RECORDED", record, attempt_id=attempt_id,
                                             metadata={"status": record.status}))
            if result.verified:
                journal_ids.append(self._journal("EXECUTION_VERIFIED", record, attempt_id=attempt_id))
            self._receipt(record, attempt_id, spec.capability_id, "COMPLETED",
                          "verified" if result.verified else "recorded", out, journal_ids)
            return TaskOutcome(
                task_id=record.task_id, status=record.status, owner_agent="HERMES",
                capability_id=spec.capability_id, ok=True, summary=record.summary,
                route_rule=route.rule, output=out,
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

        record = self.tasks.get(record.task_id)
        record.record_action("delegate", f"agent={route.owner_agent}")
        record.evidence.extend(result.evidence)
        record.artifacts.extend(result.artifacts)
        record.warnings.extend(result.warnings)
        record.errors.extend(result.errors)
        record = self.tasks.save(record, "delegated")

        self.tasks.transition(record.task_id, taskmod.VERIFYING, f"result={result.status}")
        if result.ok:
            self.tasks.transition(record.task_id, taskmod.COMPLETED,
                                result.summary[:200])
            record = self.tasks.get(record.task_id)
            record.summary = result.summary
            self._remember(record, "task.completed", record.summary,
                           {"agent": route.owner_agent,
                            "capability": route.capability_id,
                            "status": record.status})
        else:
            self.tasks.transition(record.task_id, taskmod.FAILED, result.status)
            record = self.tasks.get(record.task_id)
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
        record = self.tasks.save(record, "result")

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

        record = self.tasks.get(record.task_id)
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
        record = self.tasks.save(record, "calling_result")

        # A cancellation requested while the resolver was running outranks the
        # result: report CANCELLED rather than claiming a completed preparation.
        record = self.tasks.get(record.task_id)
        if record.status == taskmod.CANCEL_REQUESTED:
            self.tasks.transition(record.task_id, taskmod.CANCELLED,
                                  "cancellation requested before the result was applied")
            record = self.tasks.get(record.task_id)
            record.summary = ("Cancelled before completion; the prepared call "
                              "result was discarded")
            self._finish_attempt(record, taskmod.CANCELLED)
            record = self.tasks.save(record, "cancelled")
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
            record = self.tasks.get(record.task_id)
            contact = getattr(call, "contact", None)
            who = getattr(contact, "display_name", "") if contact else ""
            record.summary = (f"Prepared call to {who} (awaiting dial confirmation)"
                              if who else "Prepared call (awaiting dial confirmation)")
            self._finish_attempt(record, taskmod.COMPLETED)
            record = self.tasks.save(record, "completed")
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
                 execution_id: str = "",
                 metadata: Optional[Mapping[str, Any]] = None) -> str:
        if self.journal is None:
            return ""
        try:
            meta = dict(metadata or {})
            xid = execution_id or str(getattr(record, "current_execution_id", "") or "")
            if xid:
                meta.setdefault("execution_id", xid)
            return self.journal.append(
                event_type, task_id=record.task_id,
                operation_id=record.operation_id, attempt_id=attempt_id,
                worker_id=self.leases.worker_id, lease_id=lease_id,
                metadata=meta)
        except Exception:
            return ""

    def _receipt(self, record: taskmod.TaskRecord, attempt_id: str,
                 capability: str, status: str, verification: str,
                 output: Any, journal_ids: List[str],
                 *, execution_id: str = "") -> None:
        if self.receipts is None:
            return
        attempt = next((a for a in record.attempts
                        if a.get("attempt_id") == attempt_id), {})
        lease = self.leases.get(record.task_id)
        xid = execution_id or str(attempt.get("execution_id") or getattr(record, "current_execution_id", "") or "")
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
                journal_event_ids=[item for item in journal_ids if item],
                metadata={"execution_id": xid} if xid else None)
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
        guard = self._delegated_permission_guard(record, spec)
        if guard is not None:
            return guard
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

    # --- Phase 3D: recovery observability & operator reconciliation ------

    def _safe_status_str(self, status: Any) -> str:
        if hasattr(status, "value"):
            try:
                return str(status.value)
            except Exception:
                return str(status)
        return str(status)

    def _read_task_receipts(self, task_id: str) -> List[Dict[str, Any]]:
        if self.receipts is None:
            return []
        try:
            rows = list(self.receipts.list(task_id=task_id, limit=0))
            return [r for r in rows if isinstance(r, dict)]
        except Exception as exc:
            # fail-closed visibility: expose evidence-read failure, never fabricate
            return [{"_evidence_error": f"{type(exc).__name__}: {exc}"}]

    def _read_task_journal(self, task_id: str) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        if self.journal is None:
            return [], 0, None
        try:
            malformed = int(self.journal.malformed() or 0)
            events = list(self.journal.events(task_id=task_id, limit=0))
            return [e for e in events if isinstance(e, dict)], malformed, None
        except Exception as exc:
            return [], 0, f"{type(exc).__name__}: {exc}"

    def _read_task_audit(self, task_id: str, limit: int = 0) -> List[Dict[str, Any]]:
        """Read-only audit continuity view (persisted + recent in-memory best effort)."""
        out: List[Dict[str, Any]] = []
        seen = set()
        try:
            audit_dir = self.config.get("core.audit_dir", "") if self.config else ""
            if audit_dir:
                from .audit import read_events as _read_events
                result = _read_events(audit_dir, limit=0, task_id=task_id)
                for ev in (result.events or []):
                    if not isinstance(ev, dict):
                        continue
                    key = (ev.get("at"), ev.get("action"), ev.get("task_id"), ev.get("attempt_id"), ev.get("result"), ev.get("detail"))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(ev)
        except Exception:
            pass
        try:
            if self.audit is not None and hasattr(self.audit, "recent"):
                for ev in (self.audit.recent() or []):
                    if not isinstance(ev, dict) or ev.get("task_id") != task_id:
                        continue
                    key = (ev.get("at"), ev.get("action"), ev.get("task_id"), ev.get("attempt_id"), ev.get("result"), ev.get("detail"))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(ev)
        except Exception:
            pass
        # stable chronological best-effort
        try:
            out.sort(key=lambda e: str(e.get("at") or ""))
        except Exception:
            pass
        if limit and limit > 0:
            out = out[-limit:]
        return out

    def _lease_snapshot(self, task_id: str) -> Dict[str, Any]:
        try:
            lease = self.leases.get(task_id)
        except Exception as exc:
            return {"present": False, "state": "unknown", "error": f"{type(exc).__name__}: {exc}"}
        if lease is None:
            return {"present": False, "state": "none", "worker_id": None, "lease_id": None,
                    "operation": None, "status": None, "expired": None}
        try:
            expired = bool(lease.expired())
        except Exception:
            expired = None
        raw_status = str(getattr(lease, "status", ""))
        if raw_status == "ACTIVE" and expired is True:
            state = "expired"
        elif raw_status == "ACTIVE":
            state = "active"
        elif raw_status:
            state = raw_status.lower()
        else:
            state = "unknown"
        return {
            "present": True,
            "state": state,
            "lease_id": getattr(lease, "lease_id", None),
            "worker_id": getattr(lease, "worker_id", None),
            "holder": getattr(lease, "holder", None),
            "operation": getattr(lease, "operation", None),
            "status": raw_status or None,
            "pid": getattr(lease, "pid", None),
            "host": getattr(lease, "host", None),
            "acquired_at": getattr(lease, "acquired_at", None),
            "expires_at": getattr(lease, "expires_at", None),
            "last_heartbeat_at": getattr(lease, "last_heartbeat_at", None),
            "released_at": getattr(lease, "released_at", None),
            "expired": expired,
        }

    @staticmethod
    def _correlate_evidence(record: taskmod.TaskRecord, receipts: List[Dict[str, Any]],
                            journal_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        attempts = [a for a in (getattr(record, "attempts", []) or []) if isinstance(a, dict)]
        attempt_ids = [str(a.get("attempt_id") or "") for a in attempts if a.get("attempt_id")]
        receipt_attempt_ids = [str(r.get("attempt_id") or "") for r in receipts if isinstance(r, dict) and r.get("attempt_id")]
        journal_attempt_ids = [str(e.get("attempt_id") or "") for e in journal_events if isinstance(e, dict) and e.get("attempt_id")]
        task_id = record.task_id
        op_id = getattr(record, "operation_id", "")
        mismatched_task = [r.get("receipt_id") for r in receipts if isinstance(r, dict) and r.get("task_id") not in (None, "", task_id)]
        mismatched_op = [r.get("receipt_id") for r in receipts if isinstance(r, dict) and op_id and r.get("operation_id") not in (None, "", op_id)]
        mismatched_journal_task = [e.get("event_id") for e in journal_events if isinstance(e, dict) and e.get("task_id") not in (None, "", task_id)]
        orphan_receipt_attempts = sorted({aid for aid in receipt_attempt_ids if aid and aid not in attempt_ids})
        orphan_journal_attempts = sorted({aid for aid in journal_attempt_ids if aid and aid not in attempt_ids})
        linked = []
        for aid in attempt_ids:
            linked.append({
                "attempt_id": aid,
                "receipts": [r.get("receipt_id") for r in receipts if isinstance(r, dict) and r.get("attempt_id") == aid],
                "journal_event_ids": [e.get("event_id") for e in journal_events if isinstance(e, dict) and e.get("attempt_id") == aid],
            })
        gaps = []
        if mismatched_task:
            gaps.append("receipt task_id mismatch")
        if mismatched_op:
            gaps.append("receipt operation_id mismatch")
        if mismatched_journal_task:
            gaps.append("journal task_id mismatch")
        if orphan_receipt_attempts:
            gaps.append("receipts reference unknown attempt_id")
        if orphan_journal_attempts:
            gaps.append("journal events reference unknown attempt_id")
        return {
            "task_id": task_id,
            "operation_id": op_id,
            "attempt_ids": attempt_ids,
            "by_attempt": linked,
            "orphan_receipt_attempt_ids": orphan_receipt_attempts,
            "orphan_journal_attempt_ids": orphan_journal_attempts,
            "mismatched_receipt_task_ids": mismatched_task,
            "mismatched_receipt_operation_ids": mismatched_op,
            "mismatched_journal_task_ids": mismatched_journal_task,
            "gaps": gaps,
            "coherent": len(gaps) == 0,
        }

    def recovery_inspection(self, task_id: str) -> Dict[str, Any]:
        """Structured, read-only recovery inspection (Phase 3D).

        No mutation, no recovery lease acquisition, no replay/repair side effects.
        Derived from the same evidence/assessment model used by recovery.
        """
        record = self.tasks.get(task_id)
        spec = self.registry.find(record.capability_id) if record.capability_id else None
        receipts = self._read_task_receipts(task_id)
        journal_events, journal_malformed, journal_error = self._read_task_journal(task_id)
        audit_events = self._read_task_audit(task_id)
        lease = self._lease_snapshot(task_id)
        correlation = self._correlate_evidence(record, [r for r in receipts if isinstance(r, dict) and "_evidence_error" not in r],
                                               journal_events)

        # Evidence/assessment (read-only; do not persist assessment side effects)
        assessment: Dict[str, Any]
        try:
            assessment = dict(self._assess_recovery(record) or {})
        except Exception as exc:
            assessment = {"decision": "reconcile", "reason": f"assessment failed closed: {type(exc).__name__}: {exc}",
                          "evidence": {"errors": [str(exc)]}}
        evidence = dict(assessment.get("evidence") or {})
        if journal_error:
            evidence.setdefault("errors", []).append(f"journal_read_failed:{journal_error}")
        receipt_read_errors = [r for r in receipts if isinstance(r, dict) and "_evidence_error" in r]
        if receipt_read_errors:
            evidence.setdefault("errors", []).append("receipt_read_failed")
        decision = str(assessment.get("decision") or "reconcile")
        reason = str(assessment.get("reason") or "recovery decision unavailable")

        # Normalize decision semantics for operators
        if record.terminal and decision not in ("terminal", "converged"):
            decision = "terminal"
        replay_permitted = (decision == "replay")
        if decision == "terminal":
            classification = "converged"
        elif decision == "blocked":
            classification = "blocked"
        elif decision == "replay":
            classification = "replay_safe"
        elif decision == "converged":
            # Assessment 'converged' for RECOVERY_REQUIRED means no automatic recovery action,
            # but operator reconciliation may still be required.
            if record.status == taskmod.RECOVERY_REQUIRED:
                classification = "recovery_required"
            else:
                classification = "converged"
        else:
            classification = "recovery_required"

        # What is known / unknown / conflicts
        latest_attempt = (record.attempts or [{}])[-1] if record.attempts else {}
        latest_id = str((latest_attempt or {}).get("attempt_id") or "")
        known = [
            f"task status: {record.status}",
            f"capability: {record.capability_id or '(none)'}",
            f"attempts recorded: {len(record.attempts or [])}",
            f"receipts recorded: {len([r for r in receipts if isinstance(r, dict) and '_evidence_error' not in r])}",
            f"journal events recorded: {len(journal_events)}",
            f"execution lease state: {lease.get('state')}",
            f"assessment: {classification} ({reason})",
        ]
        unknown = []
        conflicts = list(evidence.get("errors") or [])
        conflicts.extend(correlation.get("gaps") or [])
        if not record.attempts:
            unknown.append("no attempt history recorded")
        if self.receipts is None:
            unknown.append("receipt store unavailable")
        elif not any(isinstance(r, dict) and "_evidence_error" not in r for r in receipts):
            unknown.append("no durable receipts found for this task")
        if self.journal is None:
            unknown.append("journal store unavailable")
        if not journal_events:
            unknown.append("no journal events found for this task")
        if spec is None and record.capability_id:
            unknown.append(f"capability {record.capability_id!r} is not registered in this runtime")
        if lease.get("state") == "unknown":
            unknown.append("lease/ownership state could not be determined")
        # detect expected markers
        latest_events = [e for e in journal_events if not latest_id or e.get("attempt_id") == latest_id]
        if latest_id and latest_attempt.get("status") == "RUNNING":
            if not any(e.get("event_type") == "EXECUTION_STARTED" for e in latest_events):
                unknown.append("latest running attempt has no EXECUTION_STARTED journal marker")
        # conflicts: completion receipt but non-terminal task
        def _rstate(r):
            return str((r or {}).get("execution_status") or (r or {}).get("result_state") or (r or {}).get("status") or "")
        success_receipts = [r for r in receipts if isinstance(r, dict) and _rstate(r) == "COMPLETED"]
        if success_receipts and record.status != taskmod.COMPLETED:
            conflicts.append("completion receipt exists but canonical task state is not terminal/completed")
        if journal_malformed:
            conflicts.append(f"journal contains malformed entries ({journal_malformed})")
        if record.status == taskmod.EXECUTING and lease.get("state") == "active" and lease.get("operation") == "execute":
            conflicts.append("active execution lease present (another worker may own execution)")

        # replay safety explanation
        replay_safety = {
            "capability_registered": spec is not None,
            "capability_id": record.capability_id,
            "execution_adapter": getattr(spec, "execution_adapter", None) if spec else None,
            "internal_action": bool(getattr(spec, "execution_adapter", "").startswith("internal:")) if spec else False,
            "replay_safe_declared": bool(getattr(spec, "replay_safe", False)) if spec else False,
            "retry_safe_declared": bool(getattr(spec, "retry_safe", False)) if spec else False,
            "automatic_replay_permitted": bool(replay_permitted),
            "reason": reason,
        }

        # safe actions (explicit, non-binding suggestions based on assessment/state)
        safe_actions = []
        if classification == "replay_safe":
            safe_actions.append({"action": "recover", "safe_now": True, "reason": "evidence indicates demonstrably safe automatic replay"})
        elif classification == "blocked":
            safe_actions.append({"action": "wait_or_release_stale_owner", "safe_now": False, "reason": "active ownership/lease conflict blocks recovery"})
        elif classification == "converged":
            safe_actions.append({"action": "none", "safe_now": True, "reason": "task is already settled/converged"})
        else:
            if not record.terminal:
                safe_actions.append({"action": "inspect_and_reconcile", "safe_now": False, "reason": "automatic replay unsafe or unproven; operator review required"})
                if record.status == taskmod.RECOVERY_REQUIRED and record.can_transition(taskmod.DEAD_LETTER):
                    safe_actions.append({"action": "reconcile.dead_letter", "safe_now": "if_operator_confirms_no_safe_replay", "reason": "explicitly abandon unrecoverable work with audit trail"})
                if record.status == taskmod.RECOVERY_REQUIRED and record.can_transition(taskmod.ABORTED):
                    safe_actions.append({"action": "reconcile.abort", "safe_now": "if_operator_confirms_resolution", "reason": "record explicit operator resolution/abort"})
            else:
                safe_actions.append({"action": "none", "safe_now": True, "reason": "terminal tasks must not be replayed or mutated"})

        return {
            "task": {
                "task_id": record.task_id,
                "operation_id": record.operation_id,
                "capability_id": record.capability_id,
                "status": record.status,
                "goal": record.goal,
                "requester": record.requester,
                "owner_agent": record.owner_agent,
                "parent_task_id": record.parent_task_id,
                "root_task_id": record.root_task_id,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "completed_at": record.completed_at,
                "attempt": record.attempt,
                "max_attempts": record.max_attempts,
                "requires_user_decision": bool(record.requires_user_decision),
                "summary": record.summary,
                "recovery_metadata": dict(getattr(record, "recovery", {}) or {}),
            },
            "recovery": {
                "classification": classification,
                "decision": decision,
                "reason": reason,
                "recovery_executable": bool(classification == "replay_safe"),
                "automatic_replay_permitted": bool(replay_permitted),
                "reconciliation_required": bool(classification == "recovery_required"),
                "blocked": bool(classification == "blocked"),
                "converged": bool(classification == "converged"),
                "requires_operator_action": bool(classification in ("recovery_required", "blocked") and not record.terminal),
            },
            "explanation": {
                "known": known,
                "unknown": sorted(set(unknown)),
                "conflicts": sorted(set([c for c in conflicts if c])),
                "prevents_automatic_recovery": [] if replay_permitted else [reason] + sorted(set([c for c in conflicts if c and c != reason])),
                "safe_actions": safe_actions,
            },
            "evidence": {
                "assessment": {
                    "decision": decision,
                    "reason": reason,
                    "evidence_summary": {
                        "status": evidence.get("status"),
                        "attempt_count": evidence.get("attempt_count"),
                        "current_attempt": evidence.get("current_attempt"),
                        "receipt_count": len([r for r in receipts if isinstance(r, dict) and "_evidence_error" not in r]),
                        "journal_event_count": len(journal_events),
                        "journal_malformed": journal_malformed or evidence.get("journal_malformed", 0),
                        "execution_lease": evidence.get("execution_lease") or lease,
                        "errors": evidence.get("errors") or [],
                    },
                },
                "attempts": list(record.attempts or []),
                "receipts": [r for r in receipts if isinstance(r, dict)],
                "journal": {"events": journal_events, "malformed": journal_malformed, "read_error": journal_error},
                "lease": lease,
                "replay_safety": replay_safety,
                "correlation": correlation,
                "audit": audit_events,
            },
            "lifecycle": {
                "events": list(record.events or []),
                "errors": list(record.errors or []),
                "warnings": list(record.warnings or []),
                "dependencies": list(getattr(record, "depends_on", []) or []),
            },
            "read_only": True,
        }

    def inspect(self, task_id: str) -> Dict[str, Any]:
        """Inspect task context without mutation (read-only, Phase 3D compatible).

        Preserves legacy keys used by existing callers/tests and adds enriched
        recovery observability under ``recovery_inspection``.
        """
        record = self.tasks.get(task_id)
        recovery = self.recovery_inspection(task_id)
        ev = recovery.get("evidence") or {}

        attempt_histories = []
        for attempt in (record.attempts or []):
            if not isinstance(attempt, dict):
                continue
            attempt_histories.append({
                "attempt_id": attempt.get("attempt_id"),
                "attempt_number": attempt.get("attempt_number"),
                "started_at": attempt.get("started_at"),
                "ended_at": attempt.get("ended_at"),
                "status": attempt.get("status"),
                "failure": attempt.get("failure"),
            })

        journal_events = ((ev.get("journal") or {}).get("events") or [])
        journal_histories = []
        for entry in journal_events:
            if not isinstance(entry, dict):
                continue
            journal_histories.append({
                "event_type": entry.get("event_type"),
                "at": entry.get("at") or entry.get("timestamp"),
                "metadata": entry.get("metadata"),
            })

        audit_events = ev.get("audit") or []
        audit_continuity = []
        for entry in audit_events:
            if not isinstance(entry, dict):
                continue
            audit_continuity.append({
                "action": entry.get("action"),
                "actor": entry.get("actor"),
                "agent": entry.get("agent"),
                "result": entry.get("result"),
            })

        lease = ev.get("lease") or {}
        lease_info = {
            "state": lease.get("state") or "none",
            "worker_id": lease.get("worker_id"),
            "lease_id": lease.get("lease_id"),
        }

        status_str = self._safe_status_str(record.status)
        # legacy receipt_info shape: best-effort consistency indicator, never mutating
        latest_attempt_status = None
        if attempt_histories:
            latest_attempt_status = attempt_histories[-1].get("status")
        receipt_info = {
            "status": status_str,
            "agrees": (status_str == str(latest_attempt_status)) if latest_attempt_status is not None else True,
        }

        # idempotency identity: best-effort from persisted submission store
        idempotency_key = ""
        try:
            if self.idempotency is not None and hasattr(self.idempotency, "all"):
                cap = record.capability_id or "auto"
                for key, val in (self.idempotency.all() or {}).items():
                    if not isinstance(val, dict):
                        continue
                    if str(val.get("task_id")) == record.task_id:
                        prefix = f"{cap}:"
                        if isinstance(key, str) and key.startswith(prefix):
                            idempotency_key = key[len(prefix):]
                        elif isinstance(key, str):
                            idempotency_key = key
                        break
            if not idempotency_key:
                idempotency_key = str(getattr(record, "idempotency_key", "") or "")
        except Exception:
            idempotency_key = str(getattr(record, "idempotency_key", "") or "")

        out = {
            "task_id": record.task_id,
            "operation_id": record.operation_id,
            "status": status_str,
            "capability_id": record.capability_id,
            "requires_user_decision": bool(record.requires_user_decision),
            "attempt_histories": attempt_histories,
            "journal_histories": journal_histories,
            "audit_continuity": audit_continuity,
            "lease_info": lease_info,
            "receipt_info": receipt_info,
            "idempotency_key": idempotency_key,
            "errors": [
                {"message": e.get("message"), "stage": e.get("stage")}
                for e in (record.errors or []) if isinstance(e, dict)
            ],
            "events": [
                {"status": e.get("status")}
                for e in (record.events or []) if isinstance(e, dict)
            ],
            "dependencies": list(getattr(record, "depends_on", []) or []),
            # Phase 3D additive, read-only observability
            "recovery_inspection": recovery,
        }
        return out

    def _record_operator_reconciliation(self, task_id: str, *, action: str, previous: Dict[str, Any],
                                        resulting: Dict[str, Any], reason: str,
                                        evidence_basis: Any = None, operator: str = "",
                                        outcome: str = "ok", detail: str = "",
                                        authorization_decision: Any = None,
                                        operation_id: str = "") -> Dict[str, Any]:
        # Preserve caller/requested metadata as supplied (may be empty); do not invent identity.
        requested_operator = "" if operator is None else str(operator)
        authz = {}
        prov = {}
        principal = None
        principal_source = "none"
        authenticated = False
        identity_provider = ""
        trust_assumption = ""
        try:
            if authorization_decision is not None and hasattr(authorization_decision, "to_dict"):
                authz = authorization_decision.to_dict() or {}
                prov = authz.get("provenance") or {}
                principal = authz.get("principal") if authz.get("principal") is not None else authz.get("identity")
                principal_source = str(authz.get("principal_source") or prov.get("principal_source") or "none")
                authenticated = bool(authz.get("authenticated") and principal)
                identity_provider = str(authz.get("identity_provider") or prov.get("identity_provider") or "")
                trust_assumption = str(authz.get("trust_assumption") or prov.get("trust_assumption") or "")
        except Exception:
            authz = {}
        payload = {
            "action": action,
            "previous": previous,
            "resulting": resulting,
            "reason": (reason or "")[:500],
            "evidence_basis": evidence_basis,
            "operator": requested_operator[:120],
            "requested_operator": requested_operator[:120],
            "operation_id": str(operation_id or ""),
            "principal_identity": principal,
            "principal_source": principal_source,
            "authenticated": authenticated,
            "identity_provider": identity_provider,
            "trust_assumption": trust_assumption,
            "authorization": authz,
            "timestamp": time.time(),
        }
        status = {"task_metadata_persisted": False, "audit_persisted": False, "journal_persisted": False, "errors": []}
        try:
            record = self.tasks.get(task_id)
        except Exception as exc:
            record = None
            status["errors"].append(f"task_read_failed:{type(exc).__name__}:{exc}")
        if record is not None:
            try:
                self.tasks.mutate(task_id, "operator_reconciliation", lambda r: r.recovery.update({
                    "operator_reconciliation": {
                        "action": action,
                        "previous_status": previous.get("status"),
                        "previous_classification": previous.get("classification"),
                        "resulting_status": resulting.get("status"),
                        "resulting_classification": resulting.get("classification"),
                        "reason": (reason or "")[:500],
                        "operator": requested_operator[:120],
                        "requested_operator": requested_operator[:120],
                        "operation_id": str(operation_id or ""),
                        "principal_identity": principal,
                        "principal_source": principal_source,
                        "authenticated": authenticated,
                        "identity_provider": identity_provider,
                        "trust_assumption": trust_assumption,
                        "authorization_decision": (authz.get("outcome") if isinstance(authz, dict) else ""),
                        "timestamp": payload["timestamp"],
                        "outcome": outcome,
                        "evidence_basis": evidence_basis,
                        "evidence_recording": "pending",
                    }
                }))
                status["task_metadata_persisted"] = True
            except Exception as exc:
                status["errors"].append(f"task_metadata_failed:{type(exc).__name__}:{exc}")
        try:
            opid = str(operation_id or resulting.get("operation_id") or previous.get("operation_id") or (record.operation_id if record else ""))
            self.audit.record(
                "operator_reconciliation", task_id=task_id,
                operation_id=opid,
                agent="AJ", capability=(resulting.get("capability_id") or previous.get("capability_id") or (record.capability_id if record else "")),
                actor=requested_operator[:120],
                authorization=str((authz.get("outcome") if isinstance(authz, dict) else "") or "operator_explicit_action"),
                result=outcome,
                detail=(detail or reason or action)[:300],
                params={
                    "action": action,
                    "previous_status": previous.get("status"),
                    "resulting_status": resulting.get("status"),
                    "operation_id": opid,
                    "requested_operator": requested_operator[:120],
                    "principal_identity": principal,
                    "principal_source": principal_source,
                    "authenticated": authenticated,
                    "identity_provider": identity_provider,
                    "trust_assumption": trust_assumption,
                    "authorization_decision": (authz.get("outcome") if isinstance(authz, dict) else ""),
                    "authorization_provenance": prov,
                },
            )
            status["audit_persisted"] = True
        except Exception as exc:
            status["errors"].append(f"audit_failed:{type(exc).__name__}:{exc}")
        try:
            if record is not None:
                jid = self._journal("OPERATOR_RECONCILIATION", record,
                              metadata={"action": action, "outcome": outcome,
                                        "operation_id": str(operation_id or ""),
                                        "previous_status": previous.get("status"),
                                        "resulting_status": resulting.get("status"),
                                        "reason": (reason or "")[:200],
                                        "operator": requested_operator[:120],
                                        "requested_operator": requested_operator[:120],
                                        "principal_identity": principal,
                                        "principal_source": principal_source,
                                        "authenticated": authenticated})
                status["journal_persisted"] = bool(jid) or self.journal is None
            else:
                status["journal_persisted"] = self.journal is None
        except Exception as exc:
            status["errors"].append(f"journal_failed:{type(exc).__name__}:{exc}")
        # best-effort: mark evidence recording completeness on task if possible
        try:
            if status.get("task_metadata_persisted"):
                complete = bool(status.get("audit_persisted")) and bool(status.get("journal_persisted")) and not status.get("errors")
                self.tasks.mutate(task_id, "operator_reconciliation_evidence", lambda r: (
                    r.recovery.setdefault("operator_reconciliation", {}).update({
                        "evidence_recording": "complete" if complete else "incomplete",
                        "audit_persisted": bool(status.get("audit_persisted")),
                        "journal_persisted": bool(status.get("journal_persisted")),
                    })
                ))
                status["task_metadata_persisted"] = True
        except Exception as exc:
            status["errors"].append(f"task_metadata_finalize_failed:{type(exc).__name__}:{exc}")
        status["complete"] = bool(status.get("audit_persisted")) and bool(status.get("journal_persisted")) and not status.get("errors")
        return status

    def reconcile(self, task_id: str, action: str, *, reason: str,
                  evidence_basis: Any = None, operator: str = "operator",
                  target_status: str = "", operation_id: str = "",
                  idempotency_key: str = "") -> Dict[str, Any]:
        """Explicit, narrowly-scoped operator reconciliation (Phase 3D/3E).

        Supported actions (validated, fail-closed):
          - abort: RECOVERY_REQUIRED -> ABORTED (operator confirms no safe replay / resolved as aborted)
          - dead_letter: RECOVERY_REQUIRED -> DEAD_LETTER (explicit unrecoverable disposition)
          - abandon: mark task as ABANDONED via existing controlled semantics (legacy-compatible terminal operator disposition)
          - clear_recovery_required: RECOVERY_REQUIRED -> FAILED only when no active execution ownership and
            evidence is not malformed/conflicting for this operator decision; allows subsequent explicit retry
            flow under existing retry authorization/budget rules (no automatic execution, no ownership theft).

        Phase 3E: durable operation evidence (intent/outcome), idempotent duplicate prevention for known
        operation IDs, and fail-closed privileged-operation authorization guardrail. Never fabricates success.
        """
        action = (action or "").strip().lower()
        reason = (reason or "").strip()
        # Caller-supplied label is metadata only; never authenticated identity.
        requested_operator = "" if operator is None else str(operator)
        idempotency_key = (idempotency_key or "").strip()
        # Stable operation identity for this reconciliation attempt
        op_id = (operation_id or "").strip() or ids.new_task_id("rop")

        def _authz_audit_params(decision):
            d = getattr(decision, "to_dict", lambda: {})() or {}
            prov = d.get("provenance") or {}
            principal = d.get("principal") if d.get("principal") is not None else d.get("identity")
            authenticated = bool(d.get("authenticated") and principal)
            return {
                "operation_kind": "reconciliation",
                "action": action,
                "operation_id": op_id,
                "decision": d.get("outcome") or ("allow" if d.get("allowed") else "deny"),
                "authenticated": authenticated,
                "principal_identity": principal,
                "principal_source": d.get("principal_source") or prov.get("principal_source") or "none",
                "identity_provider": d.get("identity_provider") or prov.get("identity_provider") or "",
                "requested_operator": d.get("requested_operator") or prov.get("requested_operator") or requested_operator,
                "requested_operator_provided": bool(requested_operator),
                "trust_assumption": d.get("trust_assumption") or prov.get("trust_assumption") or "",
                "scope": d.get("scope") or {},
                "provenance": prov,
            }

        def _audit_authz(decision, opid, outcome="denied"):
            try:
                params = _authz_audit_params(decision)
                self.audit.record(
                    "privileged_authorization", task_id=task_id,
                    operation_id=opid, agent="AJ", actor=requested_operator or "operator",
                    capability="", authorization=str(getattr(decision, "outcome", outcome) or outcome),
                    result=str(getattr(decision, "outcome", outcome) or outcome),
                    detail=str(getattr(decision, "reason", "") or "")[:300],
                    params=params,
                )
            except Exception:
                pass

        def _op_record_intent(authz_decision=None):
            if self.operation_evidence is None:
                return
            prov = {}
            try:
                if authz_decision is not None:
                    prov = (_authz_audit_params(authz_decision).get("provenance") or {})
            except Exception:
                prov = {}
            try:
                self.operation_evidence.record_intent(
                    operation_kind="reconciliation", operation_id=op_id, task_id=task_id,
                    action=action, reason=reason, evidence_basis=evidence_basis,
                    operator=requested_operator, requested_operator=requested_operator,
                    idempotency_key=idempotency_key,
                    correlation={"task_operation_id": ""},
                    identity_provenance=prov,
                    metadata={"phase": "intent", "authorization_recorded": authz_decision is not None},
                )
            except Exception:
                # fail closed for durable evidence of privileged op: cannot safely proceed without intent durability
                raise

        def _op_progress(phase, detail="", metadata=None):
            if self.operation_evidence is None:
                return
            try:
                self.operation_evidence.record_progress(operation_id=op_id, phase=phase, detail=detail, metadata=metadata or {})
            except Exception:
                pass

        def _op_outcome(status, detail="", result=None, disposition="", retry_safe=None):
            if self.operation_evidence is None:
                return
            try:
                self.operation_evidence.record_outcome(
                    operation_id=op_id, status=status, task_id=task_id, action=action,
                    detail=detail, result=result or {}, disposition=disposition, retry_safe=retry_safe,
                    metadata={"idempotency_key": idempotency_key},
                )
            except Exception:
                pass

        # Basic input validation (preserve existing behavior)
        if not action:
            raise errors.AjError("reconciliation action is required", code=errors.CONFIG_INVALID)
        if not reason:
            raise errors.AjError("reconciliation reason is required", code=errors.CONFIG_INVALID)

        # Duplicate/known operation handling (idempotent, no duplicate application)
        if self.operation_evidence is not None and (operation_id or "").strip():
            try:
                view = self.operation_evidence.by_operation(op_id)
                if view.terminal_outcome is not None:
                    out = view.terminal_outcome or {}
                    stored = dict(out.get("result") or {})
                    if not stored:
                        stored = {
                            "ok": str(out.get("status")) == "COMPLETED",
                            "task_id": task_id,
                            "action": action,
                            "detail": out.get("detail") or "idempotent duplicate: operation already has terminal outcome",
                            "idempotent_duplicate": True,
                        }
                    stored["operation_id"] = op_id
                    stored["idempotent_duplicate"] = True
                    stored.setdefault("ok", str(out.get("status")) == "COMPLETED")
                    stored.setdefault("task_id", task_id)
                    stored.setdefault("action", action)
                    return stored
                if view.intent is not None and view.terminal_outcome is None:
                    # Intent recorded but no outcome: incomplete/interrupted. Never reapply.
                    res = {
                        "ok": False,
                        "task_id": task_id,
                        "action": action,
                        "previous": None,
                        "resulting": None,
                        "reason": reason,
                        "evidence_basis": evidence_basis,
                        "operator": operator,
                        "detail": "incomplete/interrupted reconciliation operation detected for this operation_id; manual disposition required (no duplicate application)",
                        "state_changed": False,
                        "incomplete_operation": True,
                        "operation_id": op_id,
                        "inspection": None,
                    }
                    try:
                        res["inspection"] = self.recovery_inspection(task_id)
                    except Exception:
                        pass
                    return res
            except errors.AjError:
                raise
            except Exception:
                # fail closed on evidence lookup errors for explicit operation IDs
                raise errors.AjError("could not verify reconciliation operation evidence; refusing to proceed",
                                     code=errors.STORAGE_ERROR)

        # Authorization (internally constructed context; caller cannot inject decision/principal), then durable intent.
        # Intent is recorded after computing the authorization decision but before any state-changing work,
        # so attempted privileged operations are durably evidenced with authorization/provenance.
        try:
            from .authorization import AuthorizationContext, UnavailablePrivilegedAuthorizer
            authz = self.privileged_authorizer
            if authz is None:
                authz = UnavailablePrivilegedAuthorizer()
            ctx = AuthorizationContext(
                operation_kind="reconciliation", action=action, task_id=task_id,
                operation_id=op_id,
                operator_label=requested_operator, requested_operator=requested_operator,
                # Never accept caller-supplied authenticated identity.
                authenticated_identity=None, principal=None, principal_source="none",
                identity_provider="", authenticated=False,
                trust_domain="local_runtime", source="reconcile_api",
                metadata={"idempotency_key": idempotency_key},
            )
            decision = authz.authorize(ctx)
        except Exception as exc:
            # fail closed on authorization errors
            _req = requested_operator
            _scope = {"operation_kind": "reconciliation", "action": action, "task_id": task_id, "operation_id": op_id}
            _prov = {"principal_identity": None, "principal_source": "none", "requested_operator": _req, "authenticated": False, "identity_provider": "none", "trust_assumption": "authorization_error"}
            class _D:
                allowed = False
                outcome = "unavailable"
                reason = f"authorization error: {exc}"
                authenticated = False
                principal = None
                identity = None
                principal_source = "none"
                identity_provider = "none"
                requested_operator = _req
                operator_label = _req
                trust_assumption = "authorization_error"
                scope = _scope
                provenance = _prov
                details = {}
                def to_dict(self_inner):
                    return {
                        "allowed": False, "outcome": "unavailable", "reason": self_inner.reason,
                        "authenticated": False, "principal": None, "identity": None,
                        "principal_source": "none", "identity_provider": "none",
                        "requested_operator": _req, "operator_label": _req,
                        "trust_assumption": "authorization_error",
                        "scope": dict(_scope),
                        "provenance": dict(_prov),
                    }
            decision = _D()
        intent_recorded = False
        try:
            _op_record_intent(decision)
            intent_recorded = True
            _op_progress("intent_recorded", "reconciliation intent durably recorded", metadata={"authorization_outcome": getattr(decision, "outcome", "")})
        except Exception as exc:
            # cannot durably evidence privileged operation intent -> fail closed
            raise errors.AjError(f"failed to record reconciliation operation intent: {exc}", code=errors.STORAGE_ERROR) from exc
        _audit_authz(decision, op_id, outcome=getattr(decision, "outcome", "denied"))
        if not bool(getattr(decision, "allowed", False)):
            detail = f"privileged reconciliation authorization {getattr(decision,'outcome','denied')}: {getattr(decision,'reason','denied')}"
            _op_progress("authorization_denied", detail)
            # No state change; record refused outcome for this operation evidence
            try:
                prev = None
                inspection = None
                try:
                    record = self.tasks.get(task_id)
                    inspection = self.recovery_inspection(task_id)
                    prev = {"task_id": record.task_id, "operation_id": record.operation_id,
                            "capability_id": record.capability_id, "status": self._safe_status_str(record.status),
                            "classification": ((inspection.get("recovery") or {}).get("classification"))}
                except Exception:
                    prev = {"task_id": task_id, "status": None}
                self._record_operator_reconciliation(task_id, action=action, previous=prev or {}, resulting=prev or {},
                                                     reason=reason, evidence_basis=evidence_basis, operator=requested_operator,
                                                     outcome="denied", detail=detail,
                                                     authorization_decision=decision, operation_id=op_id)
            except Exception:
                pass
            res = {
                "ok": False,
                "task_id": task_id,
                "action": action,
                "previous": None,
                "resulting": None,
                "reason": reason,
                "evidence_basis": evidence_basis,
                "operator": requested_operator,
                "requested_operator": requested_operator,
                "detail": detail,
                "state_changed": False,
                "authorization": getattr(decision, "to_dict", lambda: {"allowed": False})(),
                "operation_id": op_id,
                "inspection": None,
            }
            try:
                res["inspection"] = self.recovery_inspection(task_id)
            except Exception:
                pass
            _op_outcome("REFUSED", detail=detail, result=res, disposition="authorization_denied", retry_safe=False)
            return res

        _op_progress("authorized", "authorization allowed under explicit guardrail")

        final_result = None
        outcome_status = "FAILED"
        try:
            # Serialize with recovery operation lease (and fail closed on active conflicts).
            try:
                with self.leases.hold(task_id, "recover"):
                    record = self.tasks.get(task_id)
                    inspection = self.recovery_inspection(task_id)
                    prev = {
                        "task_id": record.task_id,
                        "operation_id": record.operation_id,
                        "capability_id": record.capability_id,
                        "status": self._safe_status_str(record.status),
                        "classification": ((inspection.get("recovery") or {}).get("classification")),
                    }
                    lease = ((inspection.get("evidence") or {}).get("lease") or {})
                    assessment = ((inspection.get("evidence") or {}).get("assessment") or {})
                    evidence_errors = ((assessment.get("evidence_summary") or {}).get("errors") or [])
                    if not isinstance(evidence_errors, list):
                        evidence_errors = [evidence_errors] if evidence_errors else []
                    malformed = int(((assessment.get("evidence_summary") or {}).get("journal_malformed") or 0) or 0)

                    def _result(outcome: str, detail: str, ok: bool, resulting_status: Optional[str] = None,
                                resulting_classification: Optional[str] = None, state_changed: bool = False):
                        status = resulting_status or prev["status"]
                        resulting = dict(prev)
                        resulting["status"] = status
                        if resulting_classification is not None:
                            resulting["classification"] = resulting_classification
                        rec_evidence = self._record_operator_reconciliation(
                            task_id, action=action, previous=prev, resulting=resulting,
                            reason=reason, evidence_basis=evidence_basis, operator=requested_operator,
                            outcome=outcome, detail=detail,
                            authorization_decision=decision, operation_id=op_id,
                        ) or {}
                        try:
                            post = self.recovery_inspection(task_id)
                        except Exception:
                            post = None
                        warnings = []
                        evidence_complete = bool(rec_evidence.get("complete", False))
                        if not evidence_complete:
                            warnings.append("operator reconciliation evidence trail is incomplete; inspect task/audit/journal for details")
                        result = {
                            "ok": ok,
                            "task_id": task_id,
                            "action": action,
                            "previous": prev,
                            "resulting": {"status": status, "classification": resulting.get("classification")},
                            "reason": reason,
                            "evidence_basis": evidence_basis,
                            "operator": requested_operator,
                            "requested_operator": requested_operator,
                            "detail": detail,
                            "state_changed": bool(state_changed),
                            "evidence_recording": rec_evidence,
                            "evidence_complete": evidence_complete,
                            "warnings": warnings if warnings else [],
                            "inspection": post,
                            "operation_id": op_id,
                            "authorization": getattr(decision, "to_dict", lambda: {})(),
                        }
                        # If canonical state was changed but audit/journal evidence is incomplete,
                        # do not claim a fully successful auditable reconciliation.
                        if state_changed and ok and not evidence_complete:
                            result["ok"] = False
                            result["detail"] = (detail + "; state changed but reconciliation evidence trail incomplete").strip("; ")
                            result["incomplete_evidence"] = True
                        return result

                    _op_progress("lease_acquired", "reconciliation lease acquired")

                    # Ownership safety: no stealing active execution owner.
                    if lease.get("operation") == "execute" and lease.get("state") == "active":
                        final_result = _result("blocked", "active execution lease present; operator reconciliation cannot steal ownership", False)
                        outcome_status = "BLOCKED"
                        return final_result

                    # Terminal immutability
                    if record.terminal or self._safe_status_str(record.status) == "ABANDONED":
                        # idempotent no-op for explicit abandon on ABANDONED handled below in action
                        if action == "abandon" and self._safe_status_str(record.status) == "ABANDONED":
                            final_result = _result("idempotent", "task is already abandoned", True, resulting_status="ABANDONED", resulting_classification="converged")
                            outcome_status = "COMPLETED"
                            return final_result
                        final_result = _result("refused", "terminal task cannot be reconciled into an executable or mutated state", False)
                        outcome_status = "REFUSED"
                        return final_result

                    # Fail closed on malformed/conflicting/ambiguous evidence for actions that would change recovery posture
                    inspection_conflicts = ((inspection.get("explanation") or {}).get("conflicts") or [])
                    if not isinstance(inspection_conflicts, list):
                        inspection_conflicts = [inspection_conflicts] if inspection_conflicts else []
                    if action in ("clear_recovery_required",):
                        if malformed or evidence_errors or inspection_conflicts:
                            final_result = _result("refused", "evidence is malformed/conflicting/missing/ambiguous; cannot safely clear recovery-required state", False)
                            outcome_status = "REFUSED"
                            return final_result
                        rec_assess = ((inspection.get("evidence") or {}).get("assessment") or {})
                        if str(rec_assess.get("decision") or "") == "reconcile" and str(rec_assess.get("reason") or ""):
                            # only allow clear when not blocked by unsafe ambiguity evidence; assessment 'reconcile' with no conflicts
                            # can be operator-reviewed, but conflicts/unsafe markers must have been absent above
                            pass
                        # completion evidence ambiguity must not be cleared into retry path
                        if any("completion receipt" in str(c).lower() and "not terminal" in str(c).lower() for c in inspection_conflicts):
                            final_result = _result("refused", "completion evidence conflicts with non-terminal state; cannot safely clear to retry", False)
                            outcome_status = "REFUSED"
                            return final_result

                    if action == "abort":
                        if record.status != taskmod.RECOVERY_REQUIRED:
                            final_result = _result("refused", f"abort reconciliation requires RECOVERY_REQUIRED (current {record.status})", False)
                            outcome_status = "REFUSED"
                            return final_result
                        if not record.can_transition(taskmod.ABORTED):
                            final_result = _result("refused", f"illegal transition {record.status} -> ABORTED", False)
                            outcome_status = "REFUSED"
                            return final_result
                        _op_progress("state_change_begin", "transition RECOVERY_REQUIRED->ABORTED")
                        self.tasks.transition(task_id, taskmod.ABORTED, f"operator reconciliation(abort): {reason}"[:300])
                        rec = self.tasks.get(task_id)
                        try:
                            self.tasks.apply(task_id, "operator_reconcile_meta", requires_user_decision=False)
                            rec = self.tasks.get(task_id)
                        except Exception:
                            rec = self.tasks.get(task_id)
                        final_result = _result("ok", "task aborted by explicit operator reconciliation", True,
                                       resulting_status=rec.status, resulting_classification="converged", state_changed=True)
                        outcome_status = "COMPLETED" if final_result.get("ok") or final_result.get("state_changed") else "FAILED"
                        return final_result

                    if action == "dead_letter":
                        if record.status != taskmod.RECOVERY_REQUIRED:
                            final_result = _result("refused", f"dead_letter reconciliation requires RECOVERY_REQUIRED (current {record.status})", False)
                            outcome_status = "REFUSED"
                            return final_result
                        if not record.can_transition(taskmod.DEAD_LETTER):
                            final_result = _result("refused", f"illegal transition {record.status} -> DEAD_LETTER", False)
                            outcome_status = "REFUSED"
                            return final_result
                        _op_progress("state_change_begin", "transition RECOVERY_REQUIRED->DEAD_LETTER")
                        rec = self.dead_letter(task_id, f"operator reconciliation: {reason}")
                        final_result = _result("ok", "task dead-lettered by explicit operator reconciliation", True,
                                       resulting_status=rec.status, resulting_classification="converged", state_changed=True)
                        outcome_status = "COMPLETED" if final_result.get("ok") or final_result.get("state_changed") else "FAILED"
                        return final_result

                    if action == "abandon":
                        # Preserve existing abandon semantics (including forced ABANDONED state/idempotency behavior)
                        try:
                            _op_progress("state_change_begin", "abandon")
                            rec = self.abandon(task_id, f"operator reconciliation: {reason}")
                        except errors.AjError as exc:
                            # existing abandon may raise for already-abandoned in some paths; treat as idempotent if state confirms
                            cur = self.tasks.get(task_id)
                            if self._safe_status_str(cur.status) == "ABANDONED":
                                final_result = _result("idempotent", "task is already abandoned", True,
                                               resulting_status="ABANDONED", resulting_classification="converged")
                                outcome_status = "COMPLETED"
                                return final_result
                            final_result = _result("refused", str(exc), False)
                            outcome_status = "REFUSED"
                            return final_result
                        status = self._safe_status_str(rec.status)
                        final_result = _result("ok" if status == "ABANDONED" else "ok", "task abandoned by explicit operator reconciliation", True,
                                       resulting_status=status, resulting_classification="converged", state_changed=True)
                        outcome_status = "COMPLETED" if final_result.get("ok") or final_result.get("state_changed") else "FAILED"
                        return final_result

                    if action == "clear_recovery_required":
                        if record.status != taskmod.RECOVERY_REQUIRED:
                            final_result = _result("refused", f"clear_recovery_required requires RECOVERY_REQUIRED (current {record.status})", False)
                            outcome_status = "REFUSED"
                            return final_result
                        if not record.can_transition(taskmod.FAILED):
                            final_result = _result("refused", f"illegal transition {record.status} -> FAILED", False)
                            outcome_status = "REFUSED"
                            return final_result
                        _op_progress("state_change_begin", "transition RECOVERY_REQUIRED->FAILED (operator clear)")
                        self.tasks.transition(task_id, taskmod.FAILED, f"operator reconciliation(clear_recovery_required): {reason}"[:300])
                        rec = self.tasks.get(task_id)
                        try:
                            self.tasks.apply(task_id, "operator_reconcile_meta", requires_user_decision=True)
                            rec = self.tasks.get(task_id)
                        except Exception:
                            rec = self.tasks.get(task_id)
                        final_result = _result("ok", "recovery-required cleared to FAILED for explicit operator retry flow (no automatic execution)", True,
                                       resulting_status=rec.status, resulting_classification="recovery_required", state_changed=True)
                        outcome_status = "COMPLETED" if final_result.get("ok") or final_result.get("state_changed") else "FAILED"
                        return final_result

                    final_result = _result("refused", f"unsupported reconciliation action: {action}", False)
                    outcome_status = "REFUSED"
                    return final_result

            except (errors.LeaseHeld, errors.LeaseExpired) as exc:
                # cannot safely obtain reconciliation serialization; fail closed, no mutation
                try:
                    record = self.tasks.get(task_id)
                    prev = {"task_id": record.task_id, "operation_id": record.operation_id,
                            "capability_id": record.capability_id, "status": self._safe_status_str(record.status),
                            "classification": None}
                except Exception:
                    prev = {"task_id": task_id, "status": None}
                self._record_operator_reconciliation(task_id, action=action, previous=prev, resulting=prev,
                                                     reason=reason, evidence_basis=evidence_basis, operator=requested_operator,
                                                     outcome="blocked", detail=str(exc),
                                                     authorization_decision=decision, operation_id=op_id)
                _op_progress("blocked", str(exc))
                blocked_res = {
                    "ok": False, "task_id": task_id, "action": action, "detail": str(exc),
                    "state_changed": False, "operation_id": op_id,
                    "requested_operator": requested_operator,
                    "authorization": getattr(decision, "to_dict", lambda: {})(),
                }
                _op_outcome("BLOCKED", detail=str(exc), result=blocked_res, disposition="lease_blocked", retry_safe=True)
                raise errors.AjError(
                    f"reconciliation blocked: {exc}", code=errors.LEASE_HELD,
                ) from exc
        finally:
            # Record terminal outcome for operation evidence if not already recorded in lease-blocked path
            if final_result is not None and self.operation_evidence is not None:
                try:
                    view = self.operation_evidence.by_operation(op_id)
                    if view.terminal_outcome is None:
                        # map outcome
                        st = outcome_status
                        if final_result.get("incomplete_evidence") or (final_result.get("state_changed") and not final_result.get("ok")):
                            st = "COMPLETED" if final_result.get("state_changed") else "FAILED"
                        elif final_result.get("ok"):
                            st = "COMPLETED"
                        elif str(final_result.get("detail") or "").lower().find("blocked") >= 0:
                            st = "BLOCKED"
                        elif not final_result.get("state_changed"):
                            st = "REFUSED"
                        _op_outcome(st, detail=str(final_result.get("detail") or ""), result=final_result,
                                    disposition=("state_changed_incomplete_evidence" if final_result.get("incomplete_evidence") else ""),
                                    retry_safe=False)
                except Exception:
                    pass
        return final_result


    def consistency_check(self, *, task_id: str = "") -> Dict[str, Any]:
        """Read-only consistency inspection (Phase 3E). Never mutates stores."""
        from .consistency import check_consistency
        data_dir = (self.tasks._path.parent if getattr(self.tasks, "_path", None) is not None else None)
        audit_dir = None
        try:
            audit_dir = self.config.get("core.audit_dir")
        except Exception:
            audit_dir = None
        if audit_dir is None and data_dir is not None:
            audit_dir = data_dir / "audit"
        if data_dir is None or audit_dir is None:
            return {"ok": False, "status": "unavailable", "error": "data_dir or audit_dir unavailable",
                    "counts": {}, "findings": [], "summary": {}, "operator_summary": "consistency check unavailable"}
        try:
            return check_consistency(data_dir, audit_dir, task_id=task_id)
        except Exception as exc:
            return {"ok": False, "status": "error", "error": f"{type(exc).__name__}: {exc}",
                    "counts": {}, "findings": [], "summary": {}, "operator_summary": "consistency check failed"}

    def storage_diagnostics(self) -> Dict[str, Any]:
        """Read-only storage/SQLite diagnostics (Phase 3E)."""
        from .storage_diagnostics import inspect_storage, classify_sqlite_error
        data_dir = (self.tasks._path.parent if getattr(self.tasks, "_path", None) is not None else None)
        mem_path = ""
        try:
            mem_path = self.config.get("core.memory_path") or ""
        except Exception:
            mem_path = ""
        if not mem_path and data_dir is not None:
            mem_path = str(data_dir / "memory.sqlite3")
        cfg = self.config.as_dict() if hasattr(self.config, "as_dict") else {}
        try:
            return inspect_storage(cfg, data_dir=str(data_dir) if data_dir else "", memory_path=str(mem_path))
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}", "classification": classify_sqlite_error(exc)}

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
        # Transition from DEAD_LETTER to PLANNED through store-controlled forced transition.
        self.tasks.transition(task_id, taskmod.PLANNED, "requeue from dead-letter",
                              force=True, reason="requeue")
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
        record = self.tasks.save(record, "requeue")
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
        # Mark as abandoned through store-controlled mutation (ABANDONED is a
        # special terminal state outside normal transitions).
        record = self.tasks.transition(task_id, "ABANDONED",
                                       reason or "task abandoned",
                                       force=True, reason="abandoned")
        record.requires_user_decision = False
        if reason:
            record.record_error(f"abandoned: {reason}", stage="abandonment")
        else:
            record.record_error("task abandoned", stage="abandonment")
        record = self.tasks.save(record, "abandoned")
        self.audit.record("task_abandoned", task_id=task_id,
                          operation_id=record.operation_id,
                          capability=record.capability_id,
                          result="abandoned", detail=reason[:300])
        self._journal("TASK_ABANDONED", record,
                      metadata={"reason": reason[:300] if reason else ""})
        self._remember(record, "task.abandoned", "task abandoned",
                       {"reason": reason})
        return record

    def _current_execution_id(self, record: taskmod.TaskRecord) -> str:
        return str(getattr(record, "current_execution_id", "") or "")

    def _ensure_execution(self, record: taskmod.TaskRecord, *,
                          agent_id: str = "", reason: str = "") -> Optional[ExecutionRecord]:
        """Ensure the task has a current AJ-owned execution record (fail-closed on persistence errors)."""
        if self.executions is None:
            return None
        xid = self._current_execution_id(record)
        if xid:
            rec = self.executions.get(xid)
            if rec is not None:
                return rec
        lease = self.leases.get(record.task_id)
        now = time.time()
        rec = ExecutionRecord(
            execution_id=ids.new_execution_id(),
            task_id=record.task_id,
            operation_id=getattr(record, "operation_id", "") or "",
            status=EXEC_CREATED,
            correlation_id=record.task_id,
            agent_id=agent_id or str(getattr(record, "owner_agent", "") or ""),
            lease_id=lease.lease_id if lease else "",
            reason=reason[:500] if reason else "",
            created_at=now,
            updated_at=now,
            events=[{"status": EXEC_CREATED, "at": now, "detail": (reason or "created")[:500]}],
        )
        self.executions.create(rec)
        record.current_execution_id = rec.execution_id
        ids_list = list(getattr(record, "execution_ids", []) or [])
        if rec.execution_id not in ids_list:
            ids_list.append(rec.execution_id)
        record.execution_ids = ids_list
        return rec

    def _transition_execution(self, record: taskmod.TaskRecord, status: str, *,
                              detail: str = "", force: bool = False) -> Optional[ExecutionRecord]:
        if self.executions is None:
            return None
        xid = self._current_execution_id(record)
        if not xid:
            return None
        rec = self.executions.get(xid)
        if rec is None:
            return None
        lease = self.leases.get(record.task_id)
        if lease and not rec.lease_id:
            rec.lease_id = lease.lease_id
        rec.transition(status, detail=detail, force=force)
        return self.executions.save(rec)

    def _attempt_id(self, record: taskmod.TaskRecord) -> str:
        for attempt in reversed(record.attempts):
            if attempt.get("attempt_id"):
                return str(attempt["attempt_id"])
        return ""

    def _start_attempt(self, record: taskmod.TaskRecord) -> Dict[str, Any]:
        exec_rec = self._ensure_execution(record, reason="attempt started")
        if exec_rec is not None and exec_rec.status in (EXEC_CREATED, EXEC_READY):
            self._transition_execution(record, EXEC_RUNNING, detail="attempt started")
        number = max(int(record.attempt), len(record.attempts) + 1)
        record.attempt = number
        attempt = {
            "attempt_id": ids.new_task_id("att"),
            "attempt_number": number,
            "operation_id": record.operation_id,
            "execution_id": self._current_execution_id(record),
            "started_at": time.time(),
            "ended_at": None,
            "status": "RUNNING",
            "failure": None,
        }
        record.attempts.append(attempt)
        # link attempt to execution record (best-effort correlation persisted with execution)
        xid = self._current_execution_id(record)
        if xid and self.executions is not None:
            erec = self.executions.get(xid)
            if erec is not None:
                erec.current_attempt_id = attempt["attempt_id"]
                if attempt["attempt_id"] not in erec.attempt_ids:
                    erec.attempt_ids.append(attempt["attempt_id"])
                if erec.status == EXEC_CREATED:
                    erec.transition(EXEC_RUNNING, detail="attempt started")
                self.executions.save(erec)
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
                # best-effort execution state update aligned to attempt outcome
                xid = attempt.get("execution_id") or self._current_execution_id(record)
                if xid and self.executions is not None:
                    erec = self.executions.get(xid)
                    if erec is not None:
                        try:
                            if status == taskmod.COMPLETED:
                                if erec.can_transition(EXEC_COMPLETED):
                                    erec.transition(EXEC_COMPLETED, detail="attempt completed")
                                    self.executions.save(erec)
                            elif status in (taskmod.FAILED, taskmod.CANCELLED):
                                # task-level terminal attempt status; map conservatively
                                target = EXEC_FAILED if status == taskmod.FAILED else EXEC_CANCELLED
                                if erec.can_transition(target):
                                    erec.transition(target, detail=f"attempt {status.lower()}")
                                    self.executions.save(erec)
                        except Exception:
                            # execution evidence must not corrupt attempt/task terminalization paths
                            pass
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
        record = self.tasks.get(record.task_id)
        record.record_error(error, stage=stage)
        self._finish_attempt(record, taskmod.FAILED, error)
        record = self.tasks.save(record, "error")
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


    # --- delegation / assignment foundation (5A.6R2 closure) ----------------
    @staticmethod
    def _delegation_child_snapshot(child_task_ids: Sequence[str], tasks) -> Dict[str, Any]:
        items = []
        for cid in list(child_task_ids or []):
            try:
                rec = tasks.get(cid)
                items.append({
                    "child_task_id": cid,
                    "status": rec.status,
                    "updated_at": float(getattr(rec, "updated_at", 0.0) or 0.0),
                    "completed_at": getattr(rec, "completed_at", None),
                    "requires_user_decision": bool(getattr(rec, "requires_user_decision", False)),
                })
            except Exception:
                items.append({"child_task_id": cid, "status": "MISSING"})
        payload = json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return {"items": items, "hash": hashlib.sha256(payload.encode("utf-8")).hexdigest()}

    def _delegations_for_parent(self, parent_task_id: str) -> List[Any]:
        if not self.delegations:
            return []
        try:
            return list(self.delegations.list_for_parent(parent_task_id) or [])
        except Exception:
            return []

    def _delegations_for_child(self, child_task_id: str) -> List[Any]:
        if not self.delegations:
            return []
        try:
            found = []
            for d in self.delegations.all():
                if child_task_id in list(getattr(d, "child_task_ids", []) or []):
                    found.append(d)
            return found
        except Exception:
            return []

    def _before_task_transition(self, task_id: str, status: str, detail: str = "",
                                *, force: bool = False, reason: str = "transition") -> None:
        """Fail closed on invalid delegation-parent completion transitions."""
        if force or status != taskmod.COMPLETED:
            return
        dels = self._delegations_for_parent(task_id)
        if not dels:
            return
        try:
            # Conservative: if any delegation for parent cannot be safely completed, block completion.
            for d in dels:
                agg = aggregate_parent_progress(
                    self.tasks, parent_task_id=d.request.parent_task_id,
                    child_task_ids=d.child_task_ids,
                    aggregation_policy=d.request.aggregation_policy,
                    required_child_task_ids=(d.request.required_child_ids or d.child_task_ids),
                )
                if not agg.get("can_complete", False) or agg.get("requires_manual_review", False):
                    raise errors.Conflict(
                        f"parent task {task_id} cannot complete: required child work unresolved/uncertain/manual-review",
                        detail={"delegation_id": getattr(d, "delegation_id", ""), "aggregation": agg},
                    )
        except errors.Conflict:
            raise
        except Exception as exc:
            raise errors.Conflict(
                f"parent task {task_id} completion blocked: delegation state unverifiable ({type(exc).__name__})"
            ) from exc

    def _mark_delegation_reconciliation_pending(self, parent_task_id: str, *, trigger: str,
                                                child_task_id: str = "", error: str = "") -> None:
        """Best-effort durable pending marker (append-only delegation evidence)."""
        dels = self._delegations_for_parent(parent_task_id)
        for d in dels:
            try:
                ev = dict(getattr(d, "evidence", {}) or {})
                ev["reconciliation_pending"] = {
                    "pending": True,
                    "at": time.time(),
                    "trigger": trigger,
                    "child_task_id": child_task_id,
                    "error": error[:300],
                }
                d.evidence = ev
                d.reason = "reconciliation pending"
                self.delegations.save(d)
            except Exception:
                pass

    def _on_task_transition(self, record: taskmod.TaskRecord, previous_status: str,
                            new_status: str, reason: str) -> None:
        """After durable child transition, reconcile parent delegation state (bounded/idempotent)."""
        if previous_status == new_status:
            return
        parent_id = getattr(record, "parent_task_id", None)
        if not parent_id:
            return
        if not self.delegations:
            return
        # avoid re-entrant reconciliation loops from transitions caused by reconciliation itself
        active = getattr(self._delegation_reconcile_local, "active", None)
        if not active:
            active = set()
            self._delegation_reconcile_local.active = active
        if parent_id in active:
            return
        try:
            # only reconcile when task appears delegation-related (child in delegation or has delegation context)
            dctx = ((getattr(record, "authorization_context", None) or {}).get("delegation") or {})
            if not dctx and not self._delegations_for_child(record.task_id):
                # cheap conservative check: still may be child of delegated parent
                if not self._delegations_for_parent(parent_id):
                    return
            active.add(parent_id)
            with self._delegation_reconcile_guard:
                self._reconcile_delegation_parent(parent_id, trigger=f"child_transition:{record.task_id}:{previous_status}->{new_status}",
                                                   source_child_task_id=record.task_id, apply_parent_policy=True)
        except Exception as exc:
            self._mark_delegation_reconciliation_pending(parent_id, trigger="child_transition",
                                                         child_task_id=record.task_id,
                                                         error=f"{type(exc).__name__}:{exc}")
        finally:
            try:
                active.discard(parent_id)
            except Exception:
                pass

    def reconcile_delegation_parent(self, parent_task_id: str, *, dry_run: bool = False,
                                    apply: bool = False, batch_size: int = 50,
                                    actor: str = "operator") -> Dict[str, Any]:
        """Explicit delegation reconciliation. Read-only dry-run by default; apply requires explicit flag."""
        if dry_run and apply:
            raise errors.Conflict("reconciliation cannot be both dry_run and apply")
        # default to dry-run/inspection when neither specified
        if not dry_run and not apply:
            dry_run = True
        batch = max(1, min(int(batch_size or 50), 100))
        with self._delegation_reconcile_guard:
            return self._reconcile_delegation_parent(parent_task_id, trigger=f"explicit:{'dry_run' if dry_run else 'apply'}",
                                                     dry_run=dry_run, apply_parent_policy=bool(apply),
                                                     bounded_batch=batch, actor=actor)

    def _delegated_permission_guard(self, record: taskmod.TaskRecord, spec: CapabilitySpec) -> Optional[TaskOutcome]:
        """Fail-closed execution-boundary enforcement for delegated child permissions.

        Revalidates recorded delegation evidence against current local trusted state
        where available (parent/delegation/task consistency). Does not claim
        authenticated identity or cross-store atomicity.
        """
        dctx = ((getattr(record, "authorization_context", None) or {}).get("delegation") or {})
        if not dctx:
            return None
        perm = dctx.get("permission_decision") or {}
        if not isinstance(perm, dict) or not perm.get("ok"):
            return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                              errors.PolicyDenied("delegated execution blocked: permission narrowing evidence missing/invalid"),
                              "authorization", final=taskmod.ABORTED)
        effective = perm.get("effective_permissions")
        if not isinstance(effective, list) or any(not isinstance(x, str) for x in effective):
            return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                              errors.PolicyDenied("delegated execution blocked: malformed effective permission envelope"),
                              "authorization", final=taskmod.ABORTED)
        # Current-state consistency checks (fail closed on unverifiable revocation/cancellation indicators).
        parent_id = str(dctx.get("parent_task_id") or getattr(record, "parent_task_id", "") or "")
        delegation_id = str(dctx.get("delegation_id") or "")
        if not parent_id:
            return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                              errors.PolicyDenied("delegated execution blocked: missing parent linkage"),
                              "authorization", final=taskmod.ABORTED)
        try:
            parent = self.tasks.get(parent_id)
        except Exception:
            return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                              errors.PolicyDenied("delegated execution blocked: parent task unverifiable"),
                              "authorization", final=taskmod.ABORTED)
        # Conservative revocation/cancellation handling: if parent delegation authority is no longer valid,
        # delegated child execution must not proceed (no fabricated continuation).
        if getattr(parent, "status", "") in (taskmod.CANCELLED, taskmod.CANCEL_REQUESTED, taskmod.ABORTED, taskmod.DEAD_LETTER):
            return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                              errors.PolicyDenied("delegated execution blocked: parent delegation authority revoked/cancelled"),
                              "authorization", final=taskmod.ABORTED)
        if self.delegations and delegation_id:
            try:
                drec = self.delegations.get(delegation_id)
            except Exception:
                drec = None
            if drec is None:
                return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                                  errors.PolicyDenied("delegated execution blocked: delegation record unverifiable"),
                                  "authorization", final=taskmod.ABORTED)
            if str(getattr(drec.request, "parent_task_id", "") or "") != parent_id:
                return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                                  errors.PolicyDenied("delegated execution blocked: delegation-parent mismatch"),
                                  "authorization", final=taskmod.ABORTED)
            if getattr(drec, "status", "") in ("FAILED", "CANCELLED", "REVOKED"):
                return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                                  errors.PolicyDenied("delegated execution blocked: delegation no longer active"),
                                  "authorization", final=taskmod.ABORTED)
            if record.task_id not in list(getattr(drec, "child_task_ids", []) or []):
                return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                                  errors.PolicyDenied("delegated execution blocked: child not linked to delegation"),
                                  "authorization", final=taskmod.ABORTED)
        # Conservative envelope checks against recorded snapshots (narrowing only).
        req_snapshot = dctx.get("requested_permissions_snapshot")
        if isinstance(req_snapshot, list):
            if not set(effective).issubset({str(x) for x in req_snapshot if isinstance(x, str)}):
                return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                                  errors.PolicyDenied("delegated execution blocked: effective permissions exceed requested envelope"),
                                  "authorization", final=taskmod.ABORTED)
        elif req_snapshot is not None:
            return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                              errors.PolicyDenied("delegated execution blocked: malformed requested permission snapshot"),
                              "authorization", final=taskmod.ABORTED)
        parent_snapshot = dctx.get("parent_permissions_snapshot")
        if isinstance(parent_snapshot, list):
            if not set(effective).issubset({str(x) for x in parent_snapshot if isinstance(x, str)}):
                return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                                  errors.PolicyDenied("delegated execution blocked: effective permissions exceed parent envelope"),
                                  "authorization", final=taskmod.ABORTED)
        elif parent_snapshot is not None:
            return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                              errors.PolicyDenied("delegated execution blocked: malformed parent permission snapshot"),
                              "authorization", final=taskmod.ABORTED)
        # Logical-internal delegated children must remain within delegation-coordination scope
        # unless an explicit broader execution envelope is verifiably authorized (not implemented).
        if dctx.get("logical_internal") and effective and set(effective) - {"delegation.coordinate"}:
            return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
                              errors.PolicyDenied("delegated execution blocked: unverifiable permission scope for logical-internal delegation"),
                              "authorization", final=taskmod.ABORTED)
        return None

    def _prepare_delegated_child_for_scheduling(self, task_id: str) -> Dict[str, Any]:
        """Progress a delegated child through existing planning/authorization paths to a schedulable
        or explicit waiting/deferred state. Does not dispatch/execute (scheduler owns dispatch)."""
        record = self.tasks.get(task_id)
        # Conservative parent-cancellation/delegation-authority enforcement (Priority B/A).
        dctx = ((getattr(record, "authorization_context", None) or {}).get("delegation") or {})
        if dctx:
            parent_id = str(dctx.get("parent_task_id") or getattr(record, "parent_task_id", "") or "")
            try:
                parent = self.tasks.get(parent_id) if parent_id else None
            except Exception:
                parent = None
            if parent is None or getattr(parent, "status", "") in (
                taskmod.CANCELLED, taskmod.CANCEL_REQUESTED, taskmod.ABORTED, taskmod.DEAD_LETTER
            ):
                # Fail closed: do not prepare/authorize new delegated work under cancelled/revoked/unverifiable parent.
                if not record.terminal and record.can_transition(taskmod.ABORTED):
                    try:
                        self.tasks.transition(task_id, taskmod.ABORTED, "delegated parent cancelled/revoked/unverifiable")
                    except Exception:
                        pass
                return {"task_id": task_id, "status": self.tasks.get(task_id).status, "ok": False,
                        "reason": "parent_cancelled_or_unverifiable"}
        if record.terminal:
            return {"task_id": task_id, "status": record.status, "ok": False, "reason": "terminal"}
        if record.status == taskmod.AUTHORIZED:
            return {"task_id": task_id, "status": record.status, "ok": True, "reason": "already_authorized"}
        if record.status not in (taskmod.RECEIVED, taskmod.UNDERSTANDING, taskmod.PLANNED,
                                 taskmod.WAITING_FOR_APPROVAL, taskmod.BLOCKED):
            return {"task_id": task_id, "status": record.status, "ok": False, "reason": "not_prepareable"}
        # advance to PLANNED
        try:
            if record.status == taskmod.RECEIVED:
                self.tasks.transition(task_id, taskmod.UNDERSTANDING, "delegated child preparation")
            record = self.tasks.get(task_id)
            if record.status == taskmod.UNDERSTANDING:
                self.tasks.transition(task_id, taskmod.PLANNED, "delegated child preparation")
            record = self.tasks.get(task_id)
        except Exception as exc:
            return {"task_id": task_id, "status": self.tasks.get(task_id).status, "ok": False,
                    "reason": f"transition_failed:{type(exc).__name__}"}
        if record.status == taskmod.WAITING_FOR_APPROVAL:
            return {"task_id": task_id, "status": record.status, "ok": False, "reason": "awaiting_approval"}
        if record.status == taskmod.BLOCKED:
            return {"task_id": task_id, "status": record.status, "ok": False, "reason": "blocked"}
        if record.status != taskmod.PLANNED:
            return {"task_id": task_id, "status": record.status, "ok": False, "reason": "not_planned"}
        # resolve capability and apply existing authorization policy (no execution)
        cap_id = str(getattr(record, "capability_id", "") or "")
        spec = self.registry.find(cap_id) if cap_id else None
        if spec is None:
            try:
                self.tasks.transition(task_id, taskmod.FAILED, "capability not found")
            except Exception:
                pass
            return {"task_id": task_id, "status": self.tasks.get(task_id).status, "ok": False,
                    "reason": "capability_not_found"}
        blocker = self._capability_blocker(spec)
        if blocker is not None:
            final = taskmod.ABORTED if isinstance(blocker, errors.PolicyDenied) else taskmod.FAILED
            try:
                self.tasks.transition(task_id, final, str(getattr(blocker, "message", "blocked")))
            except Exception:
                pass
            return {"task_id": task_id, "status": self.tasks.get(task_id).status, "ok": False,
                    "reason": "capability_blocked"}
        payload = dict(getattr(record, "request_payload", {}) or {}) or {"goal": record.goal}
        try:
            decision = self.authorizer.authorize(spec, payload=payload, approval="",
                                                  user_requested=True, actor=record.requester or "delegation")
        except Exception as exc:
            try:
                self.tasks.transition(task_id, taskmod.ABORTED, f"authorization error: {exc}")
            except Exception:
                pass
            return {"task_id": task_id, "status": self.tasks.get(task_id).status, "ok": False,
                    "reason": "authorization_error"}
        if decision.outcome == CONFIRM:
            self.tasks.transition(task_id, taskmod.WAITING_FOR_APPROVAL, decision.reason)
            rec = self.tasks.get(task_id)
            rec.requires_user_decision = True
            self.tasks.save(rec, "delegated_awaiting_approval")
            return {"task_id": task_id, "status": "WAITING_FOR_APPROVAL", "ok": False, "reason": "awaiting_approval"}
        if decision.outcome != ALLOW:
            self.tasks.transition(task_id, taskmod.ABORTED, decision.reason)
            return {"task_id": task_id, "status": "ABORTED", "ok": False, "reason": "denied"}
        # ALLOW -> AUTHORIZED (schedulable by 5A.5; dispatch remains scheduler-owned)
        self.tasks.transition(task_id, taskmod.AUTHORIZED, f"delegated authorization: {decision.reason}")
        rec = self.tasks.get(task_id)
        rec.authorization_context = self._compute_authorization_context(rec, spec, payload, decision)
        # preserve delegation evidence/narrowing context
        dctx_old = ((getattr(record, "authorization_context", None) or {}).get("delegation") or {})
        if dctx_old:
            merged = dict(rec.authorization_context or {})
            dctx = dict(dctx_old)
            # snapshot envelopes for execution-boundary checks
            dctx.setdefault("parent_permissions_snapshot", dctx.get("permission_decision", {}).get("parent_permissions"))
            dctx.setdefault("requested_permissions_snapshot", dctx.get("permission_decision", {}).get("requested_permissions"))
            if "effective_permissions" in (dctx.get("permission_decision") or {}):
                dctx["effective_permissions_snapshot"] = list(dctx["permission_decision"].get("effective_permissions") or [])
            merged["delegation"] = dctx
            rec.authorization_context = merged
        self.tasks.save(rec, "delegated_authorized")
        self._journal("TASK_AUTHORIZED", rec, metadata={"capability": spec.capability_id, "stage": "delegation"})
        return {"task_id": task_id, "status": "AUTHORIZED", "ok": True, "reason": "authorized"}

    def _reconcile_delegation_parent(self, parent_task_id: str, *, trigger: str = "explicit",
                                     source_child_task_id: str = "", dry_run: bool = False,
                                     apply_parent_policy: bool = False, bounded_batch: int = 50,
                                     actor: str = "system") -> Dict[str, Any]:
        """Delegation reconciliation (dry-run read-only or explicit apply, bounded/idempotent)."""
        if not self.delegations:
            return {"ok": False, "reason": "delegation_stores_unavailable", "dry_run": dry_run}
        try:
            dels = list(self.delegations.list_for_parent(parent_task_id) or [])
        except Exception as exc:
            return {"ok": False, "reason": f"delegation_read_failed:{type(exc).__name__}", "dry_run": dry_run}
        batch = max(1, min(int(bounded_batch or 50), 100))
        dels = dels[:batch]
        from .delegation import aggregate_parent_progress
        results = []
        for d in dels:
            child_ids = list(getattr(d, "child_task_ids", []) or [])
            child_results = []
            # In apply mode, attempt safe child preparation (bounded). Dry-run must not mutate.
            if not dry_run and apply_parent_policy:
                for cid in child_ids:
                    try:
                        child_results.append(self._prepare_delegated_child_for_scheduling(cid))
                    except Exception as exc:
                        child_results.append({"task_id": cid, "ok": False, "reason": f"prepare_error:{type(exc).__name__}"})
            snapshot = self._delegation_child_snapshot(child_ids, self.tasks)
            agg = aggregate_parent_progress(self.tasks, parent_task_id=d.request.parent_task_id,
                                            child_task_ids=child_ids,
                                            aggregation_policy=d.request.aggregation_policy,
                                            required_child_task_ids=(d.request.required_child_ids or child_ids))
            agg = dict(agg)
            agg["child_state_snapshot"] = snapshot
            # stale/contradiction detection vs previous evidence
            ev = dict(getattr(d, "evidence", {}) or {})
            prev = ev.get("last_reconciliation") or {}
            prev_hash = (((prev.get("aggregation") or {}).get("child_state_snapshot") or {}).get("hash")
                         if isinstance(prev, dict) else None)
            unchanged = bool(prev_hash and prev_hash == snapshot.get("hash"))
            # parent policy observations
            try:
                parent = self.tasks.get(parent_task_id)
                parent_status = parent.status
            except Exception:
                parent = None
                parent_status = "MISSING"
            incorrect_complete = bool(parent_status == taskmod.COMPLETED and (not agg.get("can_complete", False) or agg.get("requires_manual_review", False)))
            pending_cleared = not dry_run and apply_parent_policy
            entry = {
                "delegation_id": getattr(d, "delegation_id", ""),
                "aggregation": agg,
                "children": child_results,
                "idempotent_noop": unchanged,
                "incorrect_parent_completion": incorrect_complete,
                "parent_status": parent_status,
                "dry_run": dry_run,
            }
            if not dry_run:
                rec_ev = {
                    "at": time.time(),
                    "trigger": trigger,
                    "actor": actor,
                    "source_child_task_id": source_child_task_id,
                    "aggregation": agg,
                    "children": child_results,
                    "incorrect_parent_completion": incorrect_complete,
                }
                ev["last_reconciliation"] = rec_ev
                ev.setdefault("reconciliation_history", [])
                if isinstance(ev["reconciliation_history"], list):
                    ev["reconciliation_history"].append({"at": rec_ev["at"], "hash": snapshot.get("hash"),
                                                         "can_complete": agg.get("can_complete"),
                                                         "manual_review": agg.get("requires_manual_review"),
                                                         "trigger": trigger})
                    # bounded history
                    ev["reconciliation_history"] = ev["reconciliation_history"][-20:]
                if pending_cleared and isinstance(ev.get("reconciliation_pending"), dict):
                    ev["reconciliation_pending"] = {**ev.get("reconciliation_pending", {}), "pending": False, "cleared_at": time.time()}
                elif not apply_parent_policy:
                    # record that reconciliation was observed/requested without apply
                    pass
                d.evidence = ev
                d.reason = f"reconciled: can_complete={agg.get('can_complete')} manual_review={agg.get('requires_manual_review')} incorrect_complete={incorrect_complete}"
                try:
                    self.delegations.save(d)
                except Exception as exc:
                    entry["persist_error"] = f"{type(exc).__name__}"
            results.append(entry)
        return {"ok": True, "parent_task_id": parent_task_id, "dry_run": dry_run, "delegations": results,
                "bounded_batch": batch, "total_considered": len(dels)}

    def _ensure_delegation_stores(self) -> None:
        if self.delegations is None or self.assignments is None or self.logical_agents is None:
            raise errors.AjError(
                "delegation stores are unavailable; durable delegation requires task persistence/data dir",
                code=errors.STORAGE_ERROR,
            )

    def _delegation_config(self) -> Dict[str, Any]:
        try:
            sec = self.config.section("delegation") if hasattr(self.config, "section") else {}
            return sec if isinstance(sec, dict) else {}
        except Exception:
            return {}

    def _seed_logical_agents(self) -> None:
        """Best-effort AJ-owned logical agent records from current registry (no authn/provenance claims)."""
        if self.logical_agents is None:
            return
        try:
            from .delegation import LogicalAgentRecord, AGENT_TRUST_UNVERIFIED, AGENT_AVAILABILITY_REGISTERED, AGENT_AVAILABILITY_UNAVAILABLE, AGENT_AVAILABILITY_DISABLED
            # AJ internal logical worker (always available for logical/internal assignment in this foundation)
            internal = LogicalAgentRecord(
                agent_id="agent.aj.internal",
                logical_name="AJ_INTERNAL",
                agent_type="logical_internal",
                supported_capabilities=["*"],  # capability satisfaction still gated by AJ registry/policy/capability checks
                availability_state="available",
                trust_classification=AGENT_TRUST_UNVERIFIED,
                execution_mode="logical_internal",
                provenance={"source": "aj.core", "note": "logical/internal only; not a real runtime worker"},
                enabled=True,
            )
            if self.logical_agents.get(internal.agent_id) is None:
                self.logical_agents.upsert(internal)
            # Mirror configured adapters as logical profiles (reachability/config only; no execution proof)
            for name in (self.agents.names() if self.agents else []):
                try:
                    desc = self.agents.get(name).describe() if self.agents else {}
                except Exception:
                    desc = {}
                reachable = bool(desc.get("reachable"))
                available = bool(desc.get("available", reachable))
                state = AGENT_AVAILABILITY_REGISTERED
                if desc.get("reason") == "disabled in configuration":
                    state = AGENT_AVAILABILITY_DISABLED
                elif not available:
                    state = AGENT_AVAILABILITY_UNAVAILABLE
                rec = LogicalAgentRecord(
                    agent_id=f"agent.{name.lower()}",
                    logical_name=name.upper(),
                    agent_type="configured_adapter",
                    supported_capabilities=[],  # unknown unless explicitly declared; fail closed in matching
                    availability_state=state,
                    trust_classification=AGENT_TRUST_UNVERIFIED,
                    execution_mode="logical_adapter_profile",
                    provenance={"source": "agents.registry", "probe_only": True, "description": desc},
                    enabled=state != AGENT_AVAILABILITY_DISABLED,
                )
                if self.logical_agents.get(rec.agent_id) is None:
                    self.logical_agents.upsert(rec)
        except Exception:
            return

    def delegation_status(self, delegation_id: str) -> Dict[str, Any]:
        if self.delegations is None:
            raise errors.AjError("delegation stores unavailable", code=errors.STORAGE_ERROR)
        rec = self.delegations.get(delegation_id)
        if rec is None:
            raise errors.AjError(f"unknown delegation {delegation_id}", code="task_not_found")
        assignments = self.assignments.list_for_delegation(delegation_id) if self.assignments else []
        from .delegation import aggregate_parent_progress
        agg = aggregate_parent_progress(self.tasks, parent_task_id=rec.request.parent_task_id,
                                        child_task_ids=rec.child_task_ids,
                                        aggregation_policy=rec.request.aggregation_policy,
                                        required_child_task_ids=(rec.request.required_child_ids or rec.child_task_ids))
        return {"delegation": rec.to_dict(), "assignments": [a.to_dict() for a in assignments], "aggregation": agg}

    def delegation_monitor(self) -> Dict[str, Any]:
        """Observational delegation/assignment/agent view (no mutation)."""
        from .delegation import detect_delegation_anomalies
        delegations = self.delegations.all() if self.delegations else []
        assignments = self.assignments.all() if self.assignments else []
        agents = self.logical_agents.all() if self.logical_agents else []
        anomalies = detect_delegation_anomalies(
            self.tasks, delegations, assignments,
            leases=getattr(self, "leases", None),
            executions=getattr(self, "executions", None),
        ) if (self.delegations and self.assignments) else {}
        parents = {}
        for d in delegations:
            from .delegation import aggregate_parent_progress
            parents[d.request.parent_task_id] = aggregate_parent_progress(
                self.tasks, parent_task_id=d.request.parent_task_id,
                child_task_ids=d.child_task_ids,
                aggregation_policy=d.request.aggregation_policy,
                required_child_task_ids=(d.request.required_child_ids or d.child_task_ids),
            )
        return {
            "counts": {
                "delegations": len(delegations),
                "assignments": len(assignments),
                "logical_agents": len(agents),
            },
            "delegations": [d.to_dict() for d in delegations],
            "assignments": [a.to_dict() for a in assignments],
            "logical_agents": [a.to_dict() for a in agents],
            "parent_progress": parents,
            "anomalies": anomalies,
        }

    def delegate(self, request: Mapping[str, Any], *, actor: str = "aj") -> Dict[str, Any]:
        """Controlled logical/internal delegation foundation (5A.6). No real remote transport."""
        from .delegation import (
            DelegationRequest, DelegationRecord, AssignmentRecord, LogicalAgentRecord,
            stable_delegation_id, stable_assignment_id, match_agent, narrow_permissions,
            validate_parent_chain, compute_root_task_id,
            AS_PROPOSED, AS_ASSIGNED, AS_REJECTED, AGENT_TRUST_UNVERIFIED,
        )
        cfg = self._delegation_config()
        if not bool(cfg.get("enabled", True)):
            raise errors.PolicyDenied("delegation is disabled by configuration")
        self._ensure_delegation_stores()
        self._seed_logical_agents()
        req = DelegationRequest.validate(request, config_max_children=int(cfg.get("max_children_per_delegation", 10)))
        # idempotency: same key with different specification must be rejected.
        if req.idempotency_key:
            existing = self.delegations.find_by_idempotency(req.idempotency_key)
            if existing:
                if existing.request.spec_hash() != req.spec_hash() or existing.request.parent_task_id != req.parent_task_id:
                    raise errors.Conflict("same delegation idempotency key with different specification")
                return self.delegation_status(existing.delegation_id)

        parent = self.tasks.get(req.parent_task_id)
        # parent must be allowed to delegate (conservative: not terminal/aborted/failed-final-only states for delegation intent)
        if parent.terminal or parent.status in (taskmod.ABORTED, taskmod.CANCELLED, taskmod.DEAD_LETTER, taskmod.FAILED):
            raise errors.Conflict(f"parent task {parent.task_id} is not allowed to delegate in state {parent.status}")

        # bounded per-parent delegations
        existing_for_parent = self.delegations.list_for_parent(parent.task_id)
        if len(existing_for_parent) >= int(cfg.get("max_delegations_per_parent", 20)):
            raise errors.PolicyDenied("delegation bound exceeded: max_delegations_per_parent")
        if len(req.child_specs) > int(cfg.get("max_children_per_delegation", 10)):
            raise errors.PolicyDenied("delegation bound exceeded: max_children_per_delegation")

        # deterministic delegation id (stable for same idempotency key or same contract spec)
        delegation_id = stable_delegation_id(req.idempotency_key, parent_task_id=parent.task_id, spec_hash=req.spec_hash())
        existing_d = self.delegations.get(delegation_id)
        if existing_d:
            return self.delegation_status(delegation_id)

        # validate hierarchy/root
        _, root_id = validate_parent_chain(self.tasks, parent.task_id)
        root_id = root_id or (parent.root_task_id or parent.task_id)

        # pre-validate all child refs and hierarchy targets (no partial writes before record intent)
        child_task_ids: List[str] = []
        child_refs: Dict[str, str] = {}
        created_children: List[taskmod.TaskRecord] = []
        assignment_records: List[AssignmentRecord] = []
        agents = self.logical_agents.all() if self.logical_agents else []
        cap_policy = {"disabled_capabilities": []}  # conservative: rely on registry/availability checks below

        # derive parent-authorized permission context conservatively.
        # Permission narrowing is explicit and fail-closed; for logical/internal
        # delegation foundation we accept a minimal delegation-coordination envelope
        # when not explicitly provided (no execution capability escalation implied).
        parent_auth = dict(getattr(parent, "authorization_context", {}) or {})
        default_coord = ["delegation.coordinate"]
        req_parent_perms = req.permission_context.get("parent_permissions",
                                                       parent_auth.get("effective_permissions") or parent_auth.get("permissions") or default_coord)
        req_requested_perms = req.permission_context.get("requested_permissions", default_coord)
        system_for_narrow = req.permission_context.get("system_permissions", default_coord)

        try:
            # record delegation intent first (durable where stores are file-backed)
            drec = DelegationRecord(
                delegation_id=delegation_id,
                request=req,
                root_task_id=root_id,
                child_task_ids=[],
                child_refs={},
                status="RECORDED",
                reason=f"delegation requested by {actor}",
                evidence={"actor": actor, "provenance": copy.deepcopy(req.provenance)},
            )
            self.delegations.create(drec)

            for spec in req.child_specs:
                child_ref = str(spec.get("child_ref") or "")
                goal = str(spec.get("goal") or req.requested_work)
                req_caps = list(spec.get("required_capabilities") or req.required_capabilities or [])
                if not req_caps and spec.get("capability_id"):
                    req_caps = [str(spec.get("capability_id"))]
                if not req_caps:
                    raise errors.ConfigError(f"child {child_ref}: required_capabilities must be explicit")
                # capability matching (deterministic, fail-closed)
                match = match_agent(req_caps, agents, capability_policy=cap_policy)
                if not match.get("ok"):
                    # record rejection as assignment evidence is not possible without child; fail delegation conservatively
                    drec.status = "FAILED"
                    drec.reason = f"capability matching failed for {child_ref}: {match.get('reason')}"
                    self.delegations.save(drec)
                    raise errors.PolicyDenied(drec.reason)

                # permission narrowing (intersection only, fail closed)
                agent_rec = self.logical_agents.get(str(match.get("agent_id"))) if self.logical_agents else None
                agent_perms = req.permission_context.get("agent_permissions")
                if agent_perms is None and agent_rec is not None:
                    agent_perms = (agent_rec.capacity or {}).get("permissions") if isinstance(agent_rec.capacity, dict) else None
                child_req_perms = spec.get("permission_context", {}).get("requested_permissions", req_requested_perms)
                child_agent_perms = spec.get("permission_context", {}).get("agent_permissions", agent_perms)
                child_system_perms = spec.get("permission_context", {}).get("system_permissions", system_for_narrow)
                if child_system_perms is None:
                    perm_decision = {"ok": False, "reason": "system_permissions_missing",
                                     "explanation": "system_permissions missing/unverifiable; fail closed."}
                else:
                    perm_decision = narrow_permissions(
                        parent_permissions=req_parent_perms,
                        requested_permissions=child_req_perms,
                        agent_permissions=child_agent_perms,
                        system_permissions=child_system_perms,
                    )
                # capture envelopes for boundary enforcement evidence
                if isinstance(perm_decision, dict):
                    perm_decision = dict(perm_decision)
                    perm_decision.setdefault("parent_permissions", list(req_parent_perms) if isinstance(req_parent_perms, list) else req_parent_perms)
                    perm_decision.setdefault("requested_permissions", list(child_req_perms) if isinstance(child_req_perms, list) else child_req_perms)
                    perm_decision.setdefault("agent_permissions", list(child_agent_perms) if isinstance(child_agent_perms, list) else child_agent_perms)
                    perm_decision.setdefault("system_permissions", list(child_system_perms) if isinstance(child_system_perms, list) else child_system_perms)
                if not perm_decision.get("ok"):
                    drec.status = "FAILED"
                    drec.reason = f"permission narrowing failed for {child_ref}: {perm_decision.get('reason')}"
                    self.delegations.save(drec)
                    raise errors.PolicyDenied(drec.reason)

                # create child task (controlled)
                child = self.tasks.create(
                    goal,
                    requester=parent.requester,
                    owner_agent=parent.owner_agent,
                    parent_task_id=parent.task_id,
                    capability_id=str(spec.get("capability_id") or (req_caps[0] if len(req_caps) == 1 else "")),
                    permission_level=int(getattr(parent, "permission_level", 0) or 0),
                )
                # set lineage/root and delegation provenance (store-controlled updates via canonical in-lock mutation)
                with self.tasks._lock:
                    cur = self.tasks._tasks.get(child.task_id)
                    if cur is not None:
                        cur.root_task_id = root_id
                        cur.priority = int(spec.get("priority", req.priority) or 0)
                        cur.deadline = spec.get("deadline", req.deadline)
                        cur.request_payload = copy.deepcopy(spec.get("request_payload") or {"goal": goal, "delegation_id": delegation_id, "child_ref": child_ref})
                        # persist narrowed effective permissions in authorization/delegation context (evidence, not escalation)
                        dctx = dict(cur.authorization_context or {})
                        dctx["delegation"] = {
                            "delegation_id": delegation_id,
                            "parent_task_id": parent.task_id,
                            "root_task_id": root_id,
                            "child_ref": child_ref,
                            "permission_decision": copy.deepcopy(perm_decision),
                            "match": copy.deepcopy(match),
                            "logical_internal": bool(match.get("logical_internal", True)),
                            "provenance": copy.deepcopy(req.provenance),
                            "parent_permissions_snapshot": list(req_parent_perms) if isinstance(req_parent_perms, list) else req_parent_perms,
                            "requested_permissions_snapshot": list(child_req_perms) if isinstance(child_req_perms, list) else child_req_perms,
                            "effective_permissions_snapshot": list(perm_decision.get("effective_permissions") or []),
                        }
                        cur.authorization_context = dctx
                        self.tasks._persist_locked(cur, "delegated_child_created")
                        child = self.tasks._snapshot(cur)
                # progress child through existing planning/authorization paths for scheduling (no dispatch here)
                try:
                    prep = self._prepare_delegated_child_for_scheduling(child.task_id)
                except Exception as exc:
                    prep = {"task_id": child.task_id, "ok": False, "reason": f"prepare_error:{type(exc).__name__}"}
                child_task_ids.append(child.task_id)
                child_refs[child_ref] = child.task_id
                created_children.append({"task_id": child.task_id, "preparation": prep})

                # assignment record (logical/internal)
                aid = stable_assignment_id(delegation_id, child.task_id, str(match.get("agent_id") or ""))
                asg = AssignmentRecord(
                    assignment_id=aid,
                    delegation_id=delegation_id,
                    parent_task_id=parent.task_id,
                    child_task_id=child.task_id,
                    agent_id=str(match.get("agent_id") or ""),
                    capability_id=str(child.capability_id or ""),
                    status=AS_ASSIGNED if match.get("ok") else AS_REJECTED,
                    logical_internal=bool(match.get("logical_internal", True)),
                    reason=str(match.get("explanation") or ""),
                    match=copy.deepcopy(match),
                    permission_decision=copy.deepcopy(perm_decision),
                )
                self.assignments.create(asg)
                assignment_records.append(asg)

            # finalize delegation record
            drec.child_task_ids = list(child_task_ids)
            drec.child_refs = dict(child_refs)
            drec.status = "COMPLETED_CREATION"
            drec.reason = f"created {len(child_task_ids)} child task(s) (logical/internal delegation)"
            self.delegations.save(drec)
            # observational event
            if self.journal is not None:
                try:
                    self.journal.append("DELEGATION_RECORDED", task_id=parent.task_id, detail=delegation_id,
                                        metadata={"delegation_id": delegation_id, "child_task_ids": child_task_ids})
                except Exception:
                    pass
            # explicit reconciliation/aggregation evidence (non-completing)
            try:
                self._reconcile_delegation_parent(parent.task_id)
            except Exception:
                pass
            return self.delegation_status(delegation_id)
        except Exception as exc:
            # fail closed: do not silently orphan partial intent; record evidence conservatively
            try:
                drec = self.delegations.get(delegation_id)
                if drec and drec.status == "RECORDED":
                    drec.status = "RECOVERY_REQUIRED" if drec.child_task_ids else "FAILED"
                    drec.reason = f"delegation failed/partial: {exc}"
                    self.delegations.save(drec)
            except Exception:
                pass
            raise


def build(config: Optional[Config] = None, *, memory: Optional[MemoryStore] = None,
          actions: Optional[InternalActions] = None,
          calling: Optional[CallingService] = None,
          execution: Optional[ExecutionPort] = None) -> Aj:
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
    # Hermes read-only status capability: registered only when explicitly enabled
    # (adapter + capability flag). Default-deny/unregistered otherwise.
    if execution is not None and getattr(execution, "name", "") == "hermes_cli" and execution.available():
        try:
            from .hermes_contract import CAPABILITY_STATUS_READ
            registry.register(CapabilitySpec(
                capability_id=CAPABILITY_STATUS_READ,
                name="Hermes runtime status (read-only)",
                description="Read Hermes gateway/runtime status via bounded CLI probe (local_trust).",
                owner_agent="HERMES",
                execution_adapter="hermes_cli:gateway.status",
                required_permissions=("read",),
                risk_level=0,
                availability="available",
                verification_status="experimental",
                supported_inputs=[],
                supported_outputs=["status", "diagnostics"],
                side_effects=[],
                failure_modes=["unavailable", "timeout", "invalid_response"],
                notes="Phase 4B.1 minimal read-only adapter; default-disabled, deny-by-default.",
            ))
        except Exception:
            pass
    return Aj(registry=registry, agents=AgentRegistry.from_config(config),
              config=config, memory=memory, actions=actions, calling=service,
              execution=execution)