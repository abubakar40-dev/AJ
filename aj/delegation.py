"""Agent assignment, task delegation, and hierarchical orchestration foundation (5A.6).

AJ-local, logical/internal foundation only. No real remote agent transport,
no live JARVIS/HELIX/Hermes integration, no daemon/distributed execution.

Distinct concepts: Task, Operation, Execution, Attempt, Agent (logical),
Assignment, Lease, Delegation, Aggregation. No cross-store atomicity or
exactly-once guarantees are claimed; fail closed on uncertainty.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import errors, ids, task as taskmod
from .locking import file_lock

DELEGATION_SCHEMA_VERSION = 1
ASSIGNMENT_SCHEMA_VERSION = 1
AGENT_SCHEMA_VERSION = 1

# Assignment lifecycle (logical/internal; no fabricated remote acceptance/execution).
AS_PROPOSED = "PROPOSED"
AS_ASSIGNED = "ASSIGNED"
AS_ACCEPTED = "ACCEPTED"  # only if actually supported; 5A.6 keeps logical/internal
AS_RUNNING = "RUNNING"    # only if backed by execution evidence
AS_COMPLETED = "COMPLETED"
AS_FAILED = "FAILED"
AS_REJECTED = "REJECTED"
AS_CANCEL_REQUESTED = "CANCEL_REQUESTED"
AS_CANCELLED = "CANCELLED"
AS_UNKNOWN = "UNKNOWN"
AS_RECOVERY_REQUIRED = "RECOVERY_REQUIRED"

ASSIGNMENT_TERMINAL = {AS_COMPLETED, AS_FAILED, AS_REJECTED, AS_CANCELLED}
ASSIGNMENT_ACTIVE = {AS_PROPOSED, AS_ASSIGNED, AS_ACCEPTED, AS_RUNNING, AS_CANCEL_REQUESTED}

ASSIGNMENT_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    AS_PROPOSED: (AS_ASSIGNED, AS_REJECTED, AS_FAILED, AS_CANCELLED, AS_UNKNOWN, AS_RECOVERY_REQUIRED),
    AS_ASSIGNED: (AS_ACCEPTED, AS_RUNNING, AS_COMPLETED, AS_FAILED, AS_REJECTED,
                  AS_CANCEL_REQUESTED, AS_CANCELLED, AS_UNKNOWN, AS_RECOVERY_REQUIRED),
    AS_ACCEPTED: (AS_RUNNING, AS_COMPLETED, AS_FAILED, AS_REJECTED,
                  AS_CANCEL_REQUESTED, AS_CANCELLED, AS_UNKNOWN, AS_RECOVERY_REQUIRED),
    AS_RUNNING: (AS_COMPLETED, AS_FAILED, AS_CANCEL_REQUESTED, AS_CANCELLED, AS_UNKNOWN, AS_RECOVERY_REQUIRED),
    AS_CANCEL_REQUESTED: (AS_CANCELLED, AS_COMPLETED, AS_FAILED, AS_UNKNOWN, AS_RECOVERY_REQUIRED),
    AS_UNKNOWN: (AS_RECOVERY_REQUIRED, AS_FAILED, AS_CANCELLED),
    AS_RECOVERY_REQUIRED: (AS_ASSIGNED, AS_REJECTED, AS_FAILED, AS_CANCELLED, AS_UNKNOWN),
    AS_COMPLETED: (),
    AS_FAILED: (),
    AS_REJECTED: (),
    AS_CANCELLED: (),
}

AGENT_TRUST_UNVERIFIED = "unverified_local_trust"  # local_trust is not authenticated identity
AGENT_AVAILABILITY_CONFIGURED = "configured"
AGENT_AVAILABILITY_REGISTERED = "registered"
AGENT_AVAILABILITY_REACHABLE = "reachable_probe"
AGENT_AVAILABILITY_UNAVAILABLE = "unavailable"
AGENT_AVAILABILITY_DISABLED = "disabled"
AGENT_AVAILABILITY_UNKNOWN = "unknown"


def _norm_str(value: Any, *, name: str, max_len: int = 500, allow_empty: bool = False) -> str:
    if value is None:
        if allow_empty:
            return ""
        raise errors.ConfigError(f"{name} is required")
    if not isinstance(value, str):
        raise errors.ConfigError(f"{name} must be a string")
    s = value.strip()
    if not s and not allow_empty:
        raise errors.ConfigError(f"{name} must be non-empty")
    return s[:max_len]


def _norm_str_list(value: Any, *, name: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise errors.ConfigError(f"{name} must be a list")
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise errors.ConfigError(f"{name} entries must be strings")
        s = item.strip()
        if s:
            out.append(s[:200])
    # deterministic, de-duplicated preserving order
    seen = set()
    deduped = []
    for s in out:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


def stable_delegation_id(idempotency_key: str = "", *, parent_task_id: str = "", spec_hash: str = "") -> str:
    key = (idempotency_key or "").strip()
    if key:
        material = key
    else:
        # Conservative idempotency: same parent+contract spec maps to same delegation id.
        material = f"{parent_task_id}|{spec_hash}|delegation.v1"
    h = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"dlg_{h}"


def stable_assignment_id(delegation_id: str, child_task_id: str, agent_id: str) -> str:
    material = f"{delegation_id}|{child_task_id}|{agent_id}"
    h = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"asg_{h}"


@dataclass
class LogicalAgentRecord:
    """AJ-owned logical agent identity/profile (not an authenticated runtime identity)."""

    agent_id: str
    logical_name: str
    agent_type: str = "logical_internal"  # logical_internal | configured_adapter | ...
    supported_capabilities: List[str] = field(default_factory=list)
    availability_state: str = AGENT_AVAILABILITY_UNKNOWN
    trust_classification: str = AGENT_TRUST_UNVERIFIED
    execution_mode: str = "logical_internal"  # explicit: no real transport in 5A.6
    version: str = "1"
    contract_compatibility: str = "aj.delegation.v1"
    capacity: Dict[str, Any] = field(default_factory=dict)  # logical/configured only
    provenance: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    schema_version: int = AGENT_SCHEMA_VERSION
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "logical_name": self.logical_name,
            "agent_type": self.agent_type,
            "supported_capabilities": list(self.supported_capabilities),
            "availability_state": self.availability_state,
            "trust_classification": self.trust_classification,
            "execution_mode": self.execution_mode,
            "version": self.version,
            "contract_compatibility": self.contract_compatibility,
            "capacity": dict(self.capacity),
            "provenance": dict(self.provenance),
            "enabled": self.enabled,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LogicalAgentRecord":
        return cls(
            agent_id=str(data.get("agent_id") or ""),
            logical_name=str(data.get("logical_name") or ""),
            agent_type=str(data.get("agent_type") or "logical_internal"),
            supported_capabilities=list(data.get("supported_capabilities") or []),
            availability_state=str(data.get("availability_state") or AGENT_AVAILABILITY_UNKNOWN),
            trust_classification=str(data.get("trust_classification") or AGENT_TRUST_UNVERIFIED),
            execution_mode=str(data.get("execution_mode") or "logical_internal"),
            version=str(data.get("version") or "1"),
            contract_compatibility=str(data.get("contract_compatibility") or "aj.delegation.v1"),
            capacity=dict(data.get("capacity") or {}),
            provenance=dict(data.get("provenance") or {}),
            enabled=bool(data.get("enabled", True)),
            schema_version=int(data.get("schema_version") or AGENT_SCHEMA_VERSION),
            updated_at=float(data.get("updated_at") or time.time()),
        )


@dataclass
class DelegationRequest:
    """Validated, versionable delegation contract (no executable code/shell)."""

    parent_task_id: str
    requested_work: str
    required_capabilities: List[str] = field(default_factory=list)
    child_specs: List[Dict[str, Any]] = field(default_factory=list)  # minimal per-child specs
    constraints: List[str] = field(default_factory=list)
    priority: int = 0
    deadline: Optional[float] = None
    permission_context: Dict[str, Any] = field(default_factory=dict)  # requested/narrowed context
    correlation_id: str = ""
    idempotency_key: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)
    aggregation_policy: str = "all_required"  # all_required | any_sufficient | subset_required
    required_child_ids: List[str] = field(default_factory=list)  # for subset_required (logical refs)
    schema_version: int = DELEGATION_SCHEMA_VERSION
    max_children: int = 10

    def spec_hash(self) -> str:
        payload = {
            "parent_task_id": self.parent_task_id,
            "requested_work": self.requested_work,
            "required_capabilities": list(self.required_capabilities),
            "child_specs": copy.deepcopy(self.child_specs),
            "constraints": list(self.constraints),
            "priority": int(self.priority),
            "deadline": self.deadline,
            "aggregation_policy": self.aggregation_policy,
            "required_child_ids": list(self.required_child_ids),
            "schema_version": self.schema_version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "parent_task_id": self.parent_task_id,
            "requested_work": self.requested_work,
            "required_capabilities": list(self.required_capabilities),
            "child_specs": copy.deepcopy(self.child_specs),
            "constraints": list(self.constraints),
            "priority": int(self.priority),
            "deadline": self.deadline,
            "permission_context": copy.deepcopy(self.permission_context),
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "provenance": copy.deepcopy(self.provenance),
            "aggregation_policy": self.aggregation_policy,
            "required_child_ids": list(self.required_child_ids),
            "max_children": int(self.max_children),
        }

    @classmethod
    def validate(cls, data: Mapping[str, Any], *, config_max_children: int = 20) -> "DelegationRequest":
        if not isinstance(data, Mapping):
            raise errors.ConfigError("delegation request must be an object")
        schema = int(data.get("schema_version") or DELEGATION_SCHEMA_VERSION)
        if schema != DELEGATION_SCHEMA_VERSION:
            raise errors.ConfigError(f"unsupported delegation schema_version {schema}")
        parent_task_id = _norm_str(data.get("parent_task_id"), name="parent_task_id")
        requested_work = _norm_str(data.get("requested_work"), name="requested_work", max_len=2000)
        required_capabilities = _norm_str_list(data.get("required_capabilities"), name="required_capabilities")
        constraints = _norm_str_list(data.get("constraints"), name="constraints")
        child_specs = data.get("child_specs") or []
        if not isinstance(child_specs, list):
            raise errors.ConfigError("child_specs must be a list")
        norm_specs: List[Dict[str, Any]] = []
        for i, spec in enumerate(child_specs):
            if not isinstance(spec, Mapping):
                raise errors.ConfigError(f"child_specs[{i}] must be an object")
            goal = _norm_str(spec.get("goal") or requested_work, name=f"child_specs[{i}].goal", max_len=2000)
            caps = _norm_str_list(spec.get("required_capabilities") or required_capabilities,
                                  name=f"child_specs[{i}].required_capabilities")
            norm_specs.append({
                "goal": goal,
                "required_capabilities": caps,
                "capability_id": str(spec.get("capability_id") or "")[:200],
                "child_ref": str(spec.get("child_ref") or f"child_{i+1}")[:100],
                "priority": int(spec.get("priority", data.get("priority", 0)) or 0),
                "deadline": spec.get("deadline", data.get("deadline")),
                "request_payload": copy.deepcopy(spec.get("request_payload") or {}),
                "permission_context": copy.deepcopy(spec.get("permission_context") or {}),
            })
        if not norm_specs:
            # default single child from requested work
            norm_specs = [{
                "goal": requested_work,
                "required_capabilities": list(required_capabilities),
                "capability_id": "",
                "child_ref": "child_1",
                "priority": int(data.get("priority", 0) or 0),
                "deadline": data.get("deadline"),
                "request_payload": {},
                "permission_context": {},
            }]
        max_children = int(data.get("max_children", min(len(norm_specs), config_max_children)) or len(norm_specs))
        hard_cap = max(1, min(int(config_max_children), 100))
        if max_children < 1 or max_children > hard_cap:
            raise errors.ConfigError(f"max_children must be between 1 and {hard_cap}")
        if len(norm_specs) > max_children:
            raise errors.ConfigError("child_specs exceeds max_children bound")
        # reject obvious executable payloads (conservative)
        blob = json.dumps({"requested_work": requested_work, "child_specs": norm_specs, "constraints": constraints}, default=str).lower()
        for marker in ("#!/bin/sh", "#!/bin/bash", "import os", "subprocess", "rm -rf", "powershell", "curl | sh"):
            if marker in blob:
                raise errors.ConfigError("delegation contract must not contain arbitrary executable code/shell instructions")
        perm_ctx = copy.deepcopy(data.get("permission_context") or {})
        if not isinstance(perm_ctx, dict):
            raise errors.ConfigError("permission_context must be an object")
        provenance = copy.deepcopy(data.get("provenance") or {})
        if not isinstance(provenance, dict):
            raise errors.ConfigError("provenance must be an object")
        agg = str(data.get("aggregation_policy") or "all_required")
        if agg not in ("all_required", "any_sufficient", "subset_required"):
            raise errors.ConfigError("aggregation_policy must be all_required, any_sufficient, or subset_required")
        req_ids = _norm_str_list(data.get("required_child_ids"), name="required_child_ids")
        return cls(
            schema_version=schema,
            parent_task_id=parent_task_id,
            requested_work=requested_work,
            required_capabilities=required_capabilities,
            child_specs=norm_specs,
            constraints=constraints,
            priority=int(data.get("priority", 0) or 0),
            deadline=data.get("deadline"),
            permission_context=perm_ctx,
            correlation_id=str(data.get("correlation_id") or "")[:200],
            idempotency_key=str(data.get("idempotency_key") or "")[:300],
            provenance=provenance,
            aggregation_policy=agg,
            required_child_ids=req_ids,
            max_children=max_children,
        )


@dataclass
class DelegationRecord:
    delegation_id: str
    request: DelegationRequest
    root_task_id: str
    child_task_ids: List[str] = field(default_factory=list)
    child_refs: Dict[str, str] = field(default_factory=dict)  # child_ref -> task_id
    status: str = "RECORDED"  # RECORDED | COMPLETED_CREATION | FAILED | RECOVERY_REQUIRED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": DELEGATION_SCHEMA_VERSION,
            "delegation_id": self.delegation_id,
            "parent_task_id": self.request.parent_task_id,
            "root_task_id": self.root_task_id,
            "request": self.request.to_dict(),
            "child_task_ids": list(self.child_task_ids),
            "child_refs": dict(self.child_refs),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reason": self.reason,
            "evidence": copy.deepcopy(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DelegationRecord":
        req = DelegationRequest.validate(data.get("request") or {}, config_max_children=100)
        return cls(
            delegation_id=str(data.get("delegation_id") or ""),
            request=req,
            root_task_id=str(data.get("root_task_id") or ""),
            child_task_ids=list(data.get("child_task_ids") or []),
            child_refs=dict(data.get("child_refs") or {}),
            status=str(data.get("status") or "RECORDED"),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            reason=str(data.get("reason") or ""),
            evidence=dict(data.get("evidence") or {}),
        )


@dataclass
class AssignmentRecord:
    assignment_id: str
    delegation_id: str
    parent_task_id: str
    child_task_id: str
    execution_id: str = ""
    attempt_id: str = ""
    agent_id: str = ""
    capability_id: str = ""
    status: str = AS_PROPOSED
    logical_internal: bool = True
    reason: str = ""
    match: Dict[str, Any] = field(default_factory=dict)
    permission_decision: Dict[str, Any] = field(default_factory=dict)
    lease_id: str = ""
    schema_version: int = ASSIGNMENT_SCHEMA_VERSION
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    events: List[Dict[str, Any]] = field(default_factory=list)

    def can_transition(self, status: str) -> bool:
        return status in ASSIGNMENT_TRANSITIONS.get(self.status, ())

    def transition(self, status: str, *, reason: str = "", force: bool = False) -> "AssignmentRecord":
        if status == self.status:
            return self
        if status not in ASSIGNMENT_TRANSITIONS:
            raise errors.AjError(f"unknown assignment status {status!r}", code=errors.CONFIG_INVALID)
        if self.status in ASSIGNMENT_TERMINAL and not force:
            raise errors.AjError(f"assignment {self.assignment_id} is terminal ({self.status})",
                                 code=errors.CALLING_INVALID_STATE)
        if not force and not self.can_transition(status):
            raise errors.AjError(f"illegal assignment transition {self.status} -> {status}",
                                 code=errors.CALLING_INVALID_STATE)
        self.status = status
        self.updated_at = time.time()
        if reason:
            self.reason = str(reason)[:500]
        if status in ASSIGNMENT_TERMINAL:
            self.completed_at = self.updated_at
        self.events.append({"status": status, "at": self.updated_at, "reason": (reason or "")[:300]})
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assignment_id": self.assignment_id,
            "delegation_id": self.delegation_id,
            "parent_task_id": self.parent_task_id,
            "child_task_id": self.child_task_id,
            "execution_id": self.execution_id,
            "attempt_id": self.attempt_id,
            "agent_id": self.agent_id,
            "capability_id": self.capability_id,
            "status": self.status,
            "logical_internal": bool(self.logical_internal),
            "reason": self.reason,
            "match": copy.deepcopy(self.match),
            "permission_decision": copy.deepcopy(self.permission_decision),
            "lease_id": self.lease_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "events": list(self.events),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssignmentRecord":
        return cls(
            assignment_id=str(data.get("assignment_id") or ""),
            delegation_id=str(data.get("delegation_id") or ""),
            parent_task_id=str(data.get("parent_task_id") or ""),
            child_task_id=str(data.get("child_task_id") or ""),
            execution_id=str(data.get("execution_id") or ""),
            attempt_id=str(data.get("attempt_id") or ""),
            agent_id=str(data.get("agent_id") or ""),
            capability_id=str(data.get("capability_id") or ""),
            status=str(data.get("status") or AS_PROPOSED),
            logical_internal=bool(data.get("logical_internal", True)),
            reason=str(data.get("reason") or ""),
            match=dict(data.get("match") or {}),
            permission_decision=dict(data.get("permission_decision") or {}),
            lease_id=str(data.get("lease_id") or ""),
            schema_version=int(data.get("schema_version") or ASSIGNMENT_SCHEMA_VERSION),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            completed_at=data.get("completed_at"),
            events=list(data.get("events") or []),
        )


class AppendOnlyJsonlStore:
    """Minimal append-only JSONL store with fail-closed reads/writes."""

    def __init__(self, path: Optional[str | Path]):
        self.path = Path(path) if path else None
        self._lock = threading.RLock()
        self._records: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._load()

    @property
    def lock_path(self) -> Optional[str]:
        return str(self.path) + ".lock" if self.path else None

    def _load(self) -> None:
        if self.path is None or not self.path.is_file():
            return
        try:
            with file_lock(self.lock_path, exclusive=False, timeout=5.0):
                lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as exc:
            raise errors.AjError(f"store load failed ({self.path}): {exc}", code=errors.STORAGE_ERROR) from exc
        for idx, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception as exc:
                raise errors.AjError(f"store malformed at line {idx} ({self.path}): {exc}",
                                     code=errors.STORAGE_ERROR) from exc
            if not isinstance(obj, dict):
                raise errors.AjError(f"store malformed at line {idx} ({self.path}): not an object",
                                     code=errors.STORAGE_ERROR)
            rid = str(obj.get("_id") or obj.get("id") or obj.get("delegation_id") or obj.get("assignment_id") or obj.get("agent_id") or "")
            if not rid:
                # allow records keyed by explicit fields later
                rid = f"_line_{idx}"
            self._records[rid] = obj
            if rid not in self._order:
                self._order.append(rid)

    def append(self, record_id: str, record: Mapping[str, Any]) -> Dict[str, Any]:
        rec = copy.deepcopy(dict(record))
        rec["_id"] = record_id
        line = json.dumps(rec, ensure_ascii=False, default=str, sort_keys=True)
        with self._lock:
            if self.path is None:
                self._records[record_id] = rec
                if record_id not in self._order:
                    self._order.append(record_id)
                return rec
            try:
                with file_lock(self.lock_path, timeout=5.0):
                    with self.path.open("a", encoding="utf-8") as h:
                        h.write(line + "\n")
                        h.flush()
            except Exception as exc:
                raise errors.AjError(f"store append failed ({self.path}): {exc}", code=errors.STORAGE_ERROR) from exc
            self._records[record_id] = rec
            if record_id not in self._order:
                self._order.append(record_id)
            return rec

    def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            val = self._records.get(record_id)
            return copy.deepcopy(val) if val is not None else None

    def all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(self._records[k]) for k in self._order if k in self._records]


class DelegationStore:
    def __init__(self, path: Optional[str | Path]):
        self._store = AppendOnlyJsonlStore(path)
        self._by_parent: Dict[str, List[str]] = {}
        self._by_idempotency: Dict[str, str] = {}
        for r in self._store.all():
            try:
                rec = DelegationRecord.from_dict(r)
                self._index(rec)
            except Exception:
                continue

    @property
    def path(self):
        return self._store.path

    def _index(self, rec: DelegationRecord) -> None:
        self._by_parent.setdefault(rec.request.parent_task_id, [])
        if rec.delegation_id not in self._by_parent[rec.request.parent_task_id]:
            self._by_parent[rec.request.parent_task_id].append(rec.delegation_id)
        ik = (rec.request.idempotency_key or "").strip()
        if ik and ik not in self._by_idempotency:
            self._by_idempotency[ik] = rec.delegation_id

    def get(self, delegation_id: str) -> Optional[DelegationRecord]:
        raw = self._store.get(delegation_id)
        return DelegationRecord.from_dict(raw) if raw else None

    def find_by_idempotency(self, idempotency_key: str) -> Optional[DelegationRecord]:
        did = self._by_idempotency.get((idempotency_key or "").strip())
        return self.get(did) if did else None

    def list_for_parent(self, parent_task_id: str) -> List[DelegationRecord]:
        out = []
        for did in self._by_parent.get(parent_task_id, []):
            rec = self.get(did)
            if rec:
                out.append(rec)
        return out

    def all(self) -> List[DelegationRecord]:
        out = []
        for raw in self._store.all():
            try:
                out.append(DelegationRecord.from_dict(raw))
            except Exception:
                continue
        return out

    def save(self, rec: DelegationRecord) -> DelegationRecord:
        rec.updated_at = time.time()
        self._store.append(rec.delegation_id, rec.to_dict())
        self._index(rec)
        return rec

    def create(self, rec: DelegationRecord) -> DelegationRecord:
        if self.get(rec.delegation_id):
            raise errors.Conflict(f"delegation {rec.delegation_id} already exists")
        ik = (rec.request.idempotency_key or "").strip()
        if ik and ik in self._by_idempotency:
            raise errors.Conflict(f"duplicate delegation idempotency key: {ik}")
        self._store.append(rec.delegation_id, rec.to_dict())
        self._index(rec)
        return rec


class AssignmentStore:
    def __init__(self, path: Optional[str | Path]):
        self._store = AppendOnlyJsonlStore(path)

    @property
    def path(self):
        return self._store.path

    def get(self, assignment_id: str) -> Optional[AssignmentRecord]:
        raw = self._store.get(assignment_id)
        return AssignmentRecord.from_dict(raw) if raw else None

    def all(self) -> List[AssignmentRecord]:
        out = []
        for raw in self._store.all():
            try:
                out.append(AssignmentRecord.from_dict(raw))
            except Exception:
                continue
        return out

    def list_for_child(self, child_task_id: str) -> List[AssignmentRecord]:
        return [r for r in self.all() if r.child_task_id == child_task_id]

    def list_for_delegation(self, delegation_id: str) -> List[AssignmentRecord]:
        return [r for r in self.all() if r.delegation_id == delegation_id]

    def active_for_child(self, child_task_id: str) -> List[AssignmentRecord]:
        return [r for r in self.list_for_child(child_task_id) if r.status in ASSIGNMENT_ACTIVE]

    def save(self, rec: AssignmentRecord) -> AssignmentRecord:
        rec.updated_at = time.time()
        self._store.append(rec.assignment_id, rec.to_dict())
        return rec

    def create(self, rec: AssignmentRecord) -> AssignmentRecord:
        if self.get(rec.assignment_id):
            raise errors.Conflict(f"assignment {rec.assignment_id} already exists")
        # conservative duplicate-active prevention per child
        if rec.status in ASSIGNMENT_ACTIVE and self.active_for_child(rec.child_task_id):
            raise errors.Conflict(f"active assignment already exists for child task {rec.child_task_id}")
        self._store.append(rec.assignment_id, rec.to_dict())
        return rec


class LogicalAgentStore:
    def __init__(self, path: Optional[str | Path]):
        self._store = AppendOnlyJsonlStore(path)

    @property
    def path(self):
        return self._store.path

    def get(self, agent_id: str) -> Optional[LogicalAgentRecord]:
        raw = self._store.get(agent_id)
        return LogicalAgentRecord.from_dict(raw) if raw else None

    def all(self) -> List[LogicalAgentRecord]:
        out = []
        for raw in self._store.all():
            try:
                out.append(LogicalAgentRecord.from_dict(raw))
            except Exception:
                continue
        return out

    def save(self, rec: LogicalAgentRecord) -> LogicalAgentRecord:
        rec.updated_at = time.time()
        self._store.append(rec.agent_id, rec.to_dict())
        return rec

    def upsert(self, rec: LogicalAgentRecord) -> LogicalAgentRecord:
        rec.updated_at = time.time()
        self._store.append(rec.agent_id, rec.to_dict())
        return rec


# --- Hierarchy / delegation helpers --------------------------------------

def compute_root_task_id(tasks, parent_task_id: str) -> str:
    parent = tasks.get(parent_task_id)
    return str(getattr(parent, "root_task_id", "") or parent.task_id)


def validate_parent_chain(tasks, parent_task_id: str, *, child_task_id: Optional[str] = None) -> Tuple[str, str]:
    """Return (parent_id, root_id). Fail closed on invalid hierarchy."""
    if not parent_task_id:
        raise errors.ConfigError("parent_task_id is required")
    parent = tasks.get(parent_task_id)
    if parent is None:
        raise errors.Conflict(f"invalid parent reference: {parent_task_id}")
    if parent.task_id == child_task_id:
        raise errors.Conflict("task cannot be its own parent")
    # cycle/self-ancestor detection
    seen = set()
    cur = parent
    hops = 0
    while cur is not None and hops < 1000:
        if cur.task_id in seen:
            raise errors.Conflict("circular task hierarchy detected")
        seen.add(cur.task_id)
        if child_task_id and (cur.task_id == child_task_id or cur.parent_task_id == child_task_id):
            raise errors.Conflict("circular task hierarchy detected")
        if not cur.parent_task_id:
            root = cur.root_task_id or cur.task_id
            return parent.task_id, root
        try:
            cur = tasks.get(cur.parent_task_id)
        except Exception:
            raise errors.Conflict(f"invalid ancestor reference: {cur.parent_task_id}")
        hops += 1
    raise errors.Conflict("task hierarchy could not be validated safely")


# --- Capability matching & permission narrowing --------------------------

def _capability_state(agent: LogicalAgentRecord, cap: str) -> Tuple[bool, str]:
    if not agent.enabled:
        return False, "agent_disabled"
    if agent.availability_state in (AGENT_AVAILABILITY_UNAVAILABLE, AGENT_AVAILABILITY_DISABLED):
        return False, f"agent_{agent.availability_state}"
    supported = set(agent.supported_capabilities or [])
    if cap not in supported:
        return False, "capability_not_supported"
    return True, "capability_supported"


def match_agent(required_capabilities: Sequence[str], agents: Sequence[LogicalAgentRecord],
                *, capability_policy: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Deterministic, fail-closed capability matching. No wildcard inference."""
    req = [str(c).strip() for c in (required_capabilities or []) if str(c).strip()]
    if not req:
        return {"ok": False, "reason": "no_required_capabilities", "explanation": "No required capabilities specified; fail closed."}
    capability_policy = capability_policy or {}
    disabled = set(capability_policy.get("disabled_capabilities") or [])
    for c in req:
        if c in disabled:
            return {"ok": False, "reason": "disabled_capability", "capability": c,
                    "explanation": f"Required capability {c!r} is disabled; cannot assign."}
    candidates = []
    rejections: List[Dict[str, Any]] = []
    for agent in sorted(agents, key=lambda a: (a.agent_id, a.logical_name)):
        reasons = []
        ok = True
        if not agent.enabled:
            ok = False; reasons.append("agent_disabled")
        if agent.availability_state in (AGENT_AVAILABILITY_UNAVAILABLE, AGENT_AVAILABILITY_DISABLED):
            ok = False; reasons.append(f"agent_{agent.availability_state}")
        for c in req:
            cap_ok, why = _capability_state(agent, c)
            if not cap_ok:
                ok = False; reasons.append(f"{c}:{why}")
        if ok:
            candidates.append(agent)
        else:
            rejections.append({"agent_id": agent.agent_id, "reasons": reasons})
    if not candidates:
        return {"ok": False, "reason": "no_matching_agent", "required_capabilities": req,
                "rejections": rejections, "explanation": "No enabled, available agent satisfies all required capabilities."}
    # deterministic selection: prefer logical_internal, then fewer supported caps (least broad) then agent_id
    candidates.sort(key=lambda a: (0 if a.execution_mode == "logical_internal" else 1,
                                   len(a.supported_capabilities or []), a.agent_id))
    chosen = candidates[0]
    return {
        "ok": True,
        "reason": "matched",
        "agent_id": chosen.agent_id,
        "required_capabilities": req,
        "execution_mode": chosen.execution_mode,
        "logical_internal": chosen.execution_mode == "logical_internal",
        "explanation": f"Selected {chosen.agent_id} (deterministic) for capabilities {req}.",
        "rejections": rejections,
    }


def narrow_permissions(*, parent_permissions: Any, requested_permissions: Any,
                       agent_permissions: Any = None, system_permissions: Any = None) -> Dict[str, Any]:
    """Intersection-only narrowing. Missing/malformed/unverifiable => fail closed."""
    def to_set(val: Any, label: str) -> Tuple[Optional[set], Optional[str]]:
        if val is None:
            return None, f"{label}_missing"
        if isinstance(val, (list, tuple, set)):
            out = set()
            for x in val:
                if not isinstance(x, str) or not str(x).strip():
                    return None, f"{label}_malformed"
                out.add(str(x).strip())
            return out, None
        if isinstance(val, dict):
            # allow {"permissions":[...]} form
            if "permissions" in val:
                return to_set(val.get("permissions"), label)
            return None, f"{label}_malformed"
        return None, f"{label}_malformed"

    parts = [
        ("parent", to_set(parent_permissions, "parent")),
        ("requested", to_set(requested_permissions, "requested")),
    ]
    if agent_permissions is not None:
        parts.append(("agent", to_set(agent_permissions, "agent")))
    if system_permissions is not None:
        parts.append(("system", to_set(system_permissions, "system")))
    for label, (s, err) in parts:
        if err or s is None:
            return {"ok": False, "reason": err or "unverifiable", "failed_source": label,
                    "explanation": f"Permission context {label} is missing/malformed/unverifiable; fail closed."}
    sets = [s for _, (s, _) in parts if s is not None]
    effective = set.intersection(*sets) if sets else set()
    # narrowing only: effective must be subset of every provided source
    for label, (s, _) in parts:
        if s is not None and not effective.issubset(s):
            return {"ok": False, "reason": "narrowing_violation", "failed_source": label,
                    "explanation": "Permission narrowing violated; fail closed."}
    return {"ok": True, "reason": "narrowed", "effective_permissions": sorted(effective),
            "explanation": "Effective permissions computed as intersection (narrowing only)."}


# --- Aggregation ---------------------------------------------------------

def aggregate_parent_progress(tasks, *, parent_task_id: str, child_task_ids: Sequence[str],
                              aggregation_policy: str = "all_required",
                              required_child_task_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    counts = {"created": 0, "eligible": 0, "admitted": 0, "running": 0, "completed": 0,
              "failed": 0, "cancelled": 0, "recovery_required": 0, "manual_review": 0,
              "waiting": 0, "unknown": 0}
    details = []
    required = list(required_child_task_ids or child_task_ids or [])
    for cid in list(child_task_ids or []):
        try:
            rec = tasks.get(cid)
        except Exception:
            counts["unknown"] += 1
            counts["manual_review"] += 1
            details.append({"child_task_id": cid, "status": "MISSING"})
            continue
        st = rec.status
        counts["created"] += 1
        details.append({"child_task_id": cid, "status": st})
        if st == taskmod.COMPLETED:
            counts["completed"] += 1
        elif st in (taskmod.FAILED, taskmod.ABORTED, taskmod.DEAD_LETTER):
            counts["failed"] += 1
        elif st in (taskmod.CANCELLED,):
            counts["cancelled"] += 1
        elif st in (taskmod.RECOVERY_REQUIRED, taskmod.ESCALATED):
            counts["recovery_required"] += 1
            counts["manual_review"] += 1
        elif st in (taskmod.EXECUTING, taskmod.VERIFYING, taskmod.RETRYING, taskmod.RECOVERING):
            counts["running"] += 1
            counts["waiting"] += 1
        elif st in (taskmod.AUTHORIZED, taskmod.PLANNED, taskmod.RECEIVED, taskmod.UNDERSTANDING, taskmod.BLOCKED, taskmod.WAITING_FOR_APPROVAL):
            counts["waiting"] += 1
        elif st == taskmod.CANCEL_REQUESTED:
            counts["waiting"] += 1
            counts["manual_review"] += 1
        else:
            counts["unknown"] += 1
            counts["manual_review"] += 1

    required_statuses = {}
    for cid in required:
        try:
            required_statuses[cid] = tasks.get(cid).status
        except Exception:
            required_statuses[cid] = "MISSING"

    def is_done_ok(st: str) -> bool:
        return st == taskmod.COMPLETED

    def is_terminal_bad(st: str) -> bool:
        return st in (taskmod.FAILED, taskmod.ABORTED, taskmod.DEAD_LETTER, taskmod.CANCELLED)

    can_complete = False
    if aggregation_policy == "all_required":
        can_complete = bool(required) and all(is_done_ok(required_statuses.get(cid, "MISSING")) for cid in required)
    elif aggregation_policy == "any_sufficient":
        can_complete = any(is_done_ok(required_statuses.get(cid, "MISSING")) for cid in required)
    elif aggregation_policy == "subset_required":
        subset = list(required_child_task_ids or [])
        can_complete = bool(subset) and all(is_done_ok(required_statuses.get(cid, "MISSING")) for cid in subset)
    else:
        can_complete = False

    has_manual_review = counts["manual_review"] > 0 or any(
        required_statuses.get(cid) in ("MISSING", taskmod.RECOVERY_REQUIRED, taskmod.ESCALATED, taskmod.CANCEL_REQUESTED)
        for cid in (required_child_task_ids or required)
    )
    waiting = counts["waiting"] > 0 and not can_complete
    return {
        "parent_task_id": parent_task_id,
        "aggregation_policy": aggregation_policy,
        "required_child_task_ids": list(required_child_task_ids or required),
        "counts": counts,
        "children": details,
        "waiting_for_children": waiting,
        "can_complete": bool(can_complete) and not has_manual_review,
        "requires_manual_review": has_manual_review,
    }


def _child_snapshot_hash(tasks, child_task_ids: Sequence[str]) -> str:
    items = []
    for cid in list(child_task_ids or []):
        try:
            rec = tasks.get(cid)
            items.append({"child_task_id": cid, "status": rec.status,
                          "updated_at": float(getattr(rec, "updated_at", 0.0) or 0.0),
                          "completed_at": getattr(rec, "completed_at", None),
                          "requires_user_decision": bool(getattr(rec, "requires_user_decision", False))})
        except Exception:
            items.append({"child_task_id": cid, "status": "MISSING"})
    payload = json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def detect_delegation_anomalies(tasks, delegations: Sequence[DelegationRecord],
                                assignments: Sequence[AssignmentRecord], *,
                                leases=None, executions=None) -> Dict[str, Any]:
    known_tasks = {t.task_id: t for t in tasks.all()}
    known_task_ids = set(known_tasks.keys())
    children_with_delegation = set()
    orphaned_children = []
    missing_parents = []
    incomplete_delegations = []
    stale_aggregation = []
    incorrect_completed_parents = []
    delegation_task_disagreements = []
    for d in delegations:
        if d.request.parent_task_id not in known_task_ids:
            missing_parents.append({"delegation_id": d.delegation_id, "parent_task_id": d.request.parent_task_id,
                                    "finding_code": "missing_parent", "severity": "high",
                                    "safe_auto_recovery": False, "recommended": "manual_review"})
        for cid in d.child_task_ids:
            children_with_delegation.add(cid)
            if cid not in known_task_ids:
                orphaned_children.append({"delegation_id": d.delegation_id, "child_task_id": cid,
                                          "finding_code": "missing_child_task", "severity": "high",
                                          "safe_auto_recovery": False, "recommended": "manual_review"})
        if d.status not in ("COMPLETED_CREATION",) or len(d.child_task_ids) != len(d.request.child_specs):
            incomplete_delegations.append({"delegation_id": d.delegation_id, "status": d.status,
                                           "expected": len(d.request.child_specs), "created": len(d.child_task_ids),
                                           "finding_code": "incomplete_delegation", "severity": "high",
                                           "safe_auto_recovery": False, "recommended": "explicit_reconcile_or_manual_review"})
        # stale aggregation / incorrect completed parent / disagreement
        try:
            agg = aggregate_parent_progress(tasks, parent_task_id=d.request.parent_task_id,
                                            child_task_ids=d.child_task_ids,
                                            aggregation_policy=d.request.aggregation_policy,
                                            required_child_task_ids=(d.request.required_child_ids or d.child_task_ids))
            cur_hash = _child_snapshot_hash(tasks, d.child_task_ids)
            ev = getattr(d, "evidence", {}) or {}
            prev = ev.get("last_reconciliation") or {}
            prev_hash = (((prev.get("aggregation") or {}).get("child_state_snapshot") or {}).get("hash")
                         if isinstance(prev, dict) else None)
            if prev_hash and prev_hash != cur_hash:
                stale_aggregation.append({"delegation_id": d.delegation_id, "parent_task_id": d.request.parent_task_id,
                                          "finding_code": "stale_aggregation", "severity": "medium",
                                          "safe_auto_recovery": True, "recommended": "explicit_reconcile_apply"})
            parent = known_tasks.get(d.request.parent_task_id)
            if parent and parent.status == taskmod.COMPLETED and (not agg.get("can_complete", False) or agg.get("requires_manual_review", False)):
                incorrect_completed_parents.append({"delegation_id": d.delegation_id, "parent_task_id": d.request.parent_task_id,
                                                    "finding_code": "incorrect_completed_parent", "severity": "critical",
                                                    "safe_auto_recovery": False, "recommended": "manual_review_evidence_preserved"})
            # delegation-task disagreement: child not linked to parent/root as expected
            for cid in d.child_task_ids:
                rec = known_tasks.get(cid)
                if rec and rec.parent_task_id != d.request.parent_task_id:
                    delegation_task_disagreements.append({"delegation_id": d.delegation_id, "child_task_id": cid,
                                                          "finding_code": "delegation_task_disagreement", "severity": "high",
                                                          "safe_auto_recovery": False, "recommended": "manual_review"})
        except Exception:
            delegation_task_disagreements.append({"delegation_id": d.delegation_id,
                                                  "finding_code": "delegation_state_unverifiable", "severity": "high",
                                                  "safe_auto_recovery": False, "recommended": "manual_review"})

    # children claiming delegation context but not linked by any delegation record
    missing_delegation_provenance = []
    for tid, rec in known_tasks.items():
        dctx = ((getattr(rec, "authorization_context", None) or {}).get("delegation") or {})
        if isinstance(dctx, dict) and dctx.get("delegation_id") and tid not in children_with_delegation:
            missing_delegation_provenance.append({"child_task_id": tid, "delegation_id": dctx.get("delegation_id"),
                                                  "finding_code": "missing_delegation_provenance", "severity": "high",
                                                  "safe_auto_recovery": False, "recommended": "manual_review"})

    stuck_assignments = [dict(a.to_dict(), finding_code="stuck_assignment", severity="medium",
                              safe_auto_recovery=False, recommended="explicit_reconcile_or_manual_review")
                         for a in assignments if a.status in (AS_UNKNOWN, AS_RECOVERY_REQUIRED, AS_CANCEL_REQUESTED)]
    active_no_execution = []
    for a in assignments:
        if a.status in (AS_ASSIGNED, AS_ACCEPTED, AS_RUNNING, AS_CANCEL_REQUESTED):
            try:
                rec = known_tasks.get(a.child_task_id)
                if rec is None or not (getattr(rec, "current_execution_id", "") or (getattr(rec, "execution_ids", []) or [])):
                    active_no_execution.append({"assignment_id": a.assignment_id, "child_task_id": a.child_task_id,
                                                "finding_code": "active_assignment_without_execution", "severity": "low",
                                                "safe_auto_recovery": False, "recommended": "inspect"})
            except Exception:
                pass

    # Priority E extensions (read-only, best-effort)
    missing_assignments = []
    stuck_cancellations = []
    pending_reconciliation_beyond_policy = []
    ambiguous_executions = []
    inconsistent_terminal_states = []
    expired_lease_uncertainties = []

    as_by_child = {}
    for a in assignments:
        as_by_child.setdefault(a.child_task_id, []).append(a)
    for d in delegations:
        ev = getattr(d, "evidence", {}) or {}
        pend = ev.get("reconciliation_pending") or {}
        if isinstance(pend, dict) and pend.get("pending"):
            age = time.time() - float(pend.get("at") or 0.0)
            if age > 300:  # conservative policy threshold (observational)
                pending_reconciliation_beyond_policy.append({
                    "delegation_id": d.delegation_id, "parent_task_id": d.request.parent_task_id,
                    "finding_code": "pending_reconciliation_beyond_policy", "severity": "medium",
                    "safe_auto_recovery": False, "recommended": "explicit_reconcile_or_manual_review",
                    "age_seconds": int(age),
                })
        for cid in list(d.child_task_ids or []):
            if cid not in as_by_child:
                missing_assignments.append({
                    "delegation_id": d.delegation_id, "child_task_id": cid,
                    "finding_code": "missing_assignment", "severity": "high",
                    "safe_auto_recovery": False, "recommended": "manual_review",
                })
            rec = known_tasks.get(cid)
            if rec and rec.status == taskmod.CANCEL_REQUESTED:
                stuck_cancellations.append({
                    "delegation_id": d.delegation_id, "child_task_id": cid,
                    "finding_code": "stuck_cancellation", "severity": "medium",
                    "safe_auto_recovery": False, "recommended": "explicit_reconcile_or_manual_review",
                })
            # ambiguous execution / inconsistent terminal via execution records
            if rec and executions is not None:
                try:
                    for xid in list(getattr(rec, "execution_ids", []) or []):
                        er = executions.get(xid) if hasattr(executions, "get") else None
                        if er is None:
                            continue
                        est = str(getattr(er, "status", "") or "")
                        if est in ("UNKNOWN", "RECOVERY_REQUIRED", "DISPATCH_UNCERTAIN"):
                            ambiguous_executions.append({
                                "delegation_id": d.delegation_id, "child_task_id": cid, "execution_id": xid,
                                "execution_status": est, "finding_code": "ambiguous_execution",
                                "severity": "high", "safe_auto_recovery": False, "recommended": "manual_review",
                            })
                        if rec.terminal and est in ("DISPATCHED", "RUNNING", "DISPATCH_INTENT_RECORDED"):
                            inconsistent_terminal_states.append({
                                "delegation_id": d.delegation_id, "child_task_id": cid, "execution_id": xid,
                                "task_status": rec.status, "execution_status": est,
                                "finding_code": "inconsistent_terminal_state", "severity": "high",
                                "safe_auto_recovery": False, "recommended": "manual_review",
                            })
                except Exception:
                    pass
            # expired/uncertain lease
            if rec and leases is not None:
                try:
                    lease = leases.get(cid) if hasattr(leases, "get") else None
                    if lease is not None:
                        expired = bool(getattr(lease, "expired", lambda: False)())
                        lst = str(getattr(lease, "status", "") or "")
                        if expired or lst in ("STALE", "EXPIRED"):
                            if rec.status in (taskmod.EXECUTING, taskmod.VERIFYING, taskmod.CANCEL_REQUESTED, taskmod.RECOVERY_REQUIRED) or not rec.terminal:
                                expired_lease_uncertainties.append({
                                    "delegation_id": d.delegation_id, "child_task_id": cid,
                                    "lease_status": lst, "expired": expired,
                                    "finding_code": "expired_lease_uncertainty", "severity": "high",
                                    "safe_auto_recovery": False, "recommended": "manual_review",
                                })
                except Exception:
                    pass
            # inconsistent terminal state (parent/child contradictory terminal handled elsewhere)
            if rec and rec.terminal and rec.status == taskmod.COMPLETED and rec.requires_user_decision:
                inconsistent_terminal_states.append({
                    "delegation_id": d.delegation_id, "child_task_id": cid,
                    "task_status": rec.status, "finding_code": "inconsistent_terminal_state",
                    "severity": "medium", "safe_auto_recovery": False, "recommended": "inspect",
                })

    return {
        "orphaned_children": orphaned_children,
        "missing_parents": missing_parents,
        "incomplete_delegations": incomplete_delegations,
        "stuck_assignments": stuck_assignments,
        "recovery_required_assignments": [dict(a.to_dict(), finding_code="recovery_required_assignment", severity="high",
                                               safe_auto_recovery=False, recommended="manual_review")
                                          for a in assignments if a.status == AS_RECOVERY_REQUIRED],
        "stale_aggregation": stale_aggregation,
        "incorrect_completed_parents": incorrect_completed_parents,
        "delegation_task_disagreements": delegation_task_disagreements,
        "missing_delegation_provenance": missing_delegation_provenance,
        "active_assignments_without_execution": active_no_execution,
        "missing_assignments": missing_assignments,
        "expired_lease_uncertainties": expired_lease_uncertainties,
        "stuck_cancellations": stuck_cancellations,
        "pending_reconciliation_beyond_policy": pending_reconciliation_beyond_policy,
        "ambiguous_executions": ambiguous_executions,
        "inconsistent_terminal_states": inconsistent_terminal_states,
    }
