"""Scheduler, eligibility, admission, dispatch, and monitoring foundation (5A.5).

Responsibilities are explicit and separated:
- Eligibility: is a task schedulable in principle now? (decision, no reservation)
- Admission: may an eligible task enter dispatch now under bounded capacity/policy?
- Scheduler/selection: deterministic ordering, fairness/aging, bounded backpressure
- Dispatch: durable intent/evidence + lease claim + orchestrator resume boundary
- Monitoring: observational counts/reasons (no mutation)

This is a conservative, single-process, non-daemon foundation. It reuses the 5A.4
execution domain and existing LeaseManager. No cross-store atomicity or
exactly-once behavior is claimed.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from . import errors, task as taskmod
from .locking import file_lock

# Reason codes (machine-readable, stable within 5A.5 scope)
ELIGIBLE = "ELIGIBLE"
NOT_SCHEDULABLE_STATE = "NOT_SCHEDULABLE_STATE"
TERMINAL = "TERMINAL"
DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
ALREADY_ACTIVE_OR_UNCERTAIN = "ALREADY_ACTIVE_OR_UNCERTAIN"
RECOVERY_OR_REVIEW_REQUIRED = "RECOVERY_OR_REVIEW_REQUIRED"
PERSISTENCE_UNAVAILABLE = "PERSISTENCE_UNAVAILABLE"
CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
UNRESOLVED_DISPATCH_INTENT = "UNRESOLVED_DISPATCH_INTENT"

ADMITTED = "ADMITTED"
DEFERRED_CAPACITY_ACTIVE = "DEFERRED_CAPACITY_ACTIVE"
DEFERRED_CAPACITY_WAITING = "DEFERRED_CAPACITY_WAITING"
DEFERRED_UNKNOWN_CAPACITY = "DEFERRED_UNKNOWN_CAPACITY"
DEFERRED_PERSISTENCE_UNHEALTHY = "DEFERRED_PERSISTENCE_UNHEALTHY"
DEFERRED_DUPLICATE_OR_LEASE_CONFLICT = "DEFERRED_DUPLICATE_OR_LEASE_CONFLICT"
DEFERRED_NOT_ELIGIBLE = "DEFERRED_NOT_ELIGIBLE"
DEFERRED_SCHEDULER_DISABLED = "DEFERRED_SCHEDULER_DISABLED"


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    reason_code: str
    explanation: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    deferred: bool
    reason_code: str
    explanation: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "admitted": self.admitted,
            "deferred": self.deferred,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "details": dict(self.details),
        }


@dataclass
class SchedulerResult:
    task_id: str
    status: str
    ok: bool
    detail: str = ""
    eligibility: Optional[Dict[str, Any]] = None
    admission: Optional[Dict[str, Any]] = None
    dispatch: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {"task_id": self.task_id, "status": self.status,
               "ok": self.ok, "detail": self.detail}
        if self.eligibility is not None:
            out["eligibility"] = self.eligibility
        if self.admission is not None:
            out["admission"] = self.admission
        if self.dispatch is not None:
            out["dispatch"] = self.dispatch
        return out


class DispatchLedger:
    """Append-only scheduler/dispatch decision evidence (best-effort, fail-closed on use)."""

    def __init__(self, path: Optional[str | Path]):
        self.path = Path(path) if path else None
        self._mem: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def lock_path(self) -> Optional[str]:
        return str(self.path) + ".lock" if self.path else None

    def append(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        rec = dict(record)
        rec.setdefault("ts", time.time())
        line = json.dumps(rec, ensure_ascii=False, default=str, sort_keys=True)
        with self._lock:
            if self.path is None:
                self._mem.append(rec)
                return rec
            try:
                with file_lock(self.lock_path, timeout=5.0):
                    with self.path.open("a", encoding="utf-8") as h:
                        h.write(line + "\n")
                        h.flush()
            except Exception as exc:
                raise errors.AjError(
                    f"scheduler dispatch evidence persistence failed: {exc}",
                    code=errors.STORAGE_ERROR,
                ) from exc
            self._mem.append(rec)
            return rec

    def read_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            if self.path is None:
                return list(self._mem)
            if not self.path.is_file():
                return []
            try:
                with file_lock(self.lock_path, exclusive=False, timeout=5.0):
                    lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                # observational read; caller may treat as unknown/unhealthy
                raise
            out: List[Dict[str, Any]] = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
            return out

    def latest_by_task(self) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        try:
            rows = self.read_all()
        except Exception:
            return {}
        for r in rows:
            tid = str(r.get("task_id") or "")
            if not tid:
                continue
            prev = latest.get(tid)
            if prev is None or float(r.get("ts") or 0) >= float(prev.get("ts") or 0):
                latest[tid] = r
        return latest


class Scheduler:
    def __init__(self, aj, *, worker_id: str = ""):
        self.aj = aj
        self.worker_id = worker_id or f"scheduler-{time.time_ns()}"
        self._ledger: Optional[DispatchLedger] = None
        self._ledger_init = False

    # --- config / persistence -------------------------------------------------
    def _cfg(self, key: str, default: Any = None) -> Any:
        try:
            return self.aj.config.get(f"scheduler.{key}", default)
        except Exception:
            return default

    def _data_dir(self) -> Optional[Path]:
        tasks = getattr(self.aj, "tasks", None)
        path = getattr(tasks, "_path", None)
        if path is None:
            return None
        try:
            return Path(path).parent
        except Exception:
            return None

    def _ledger_store(self) -> Optional[DispatchLedger]:
        if self._ledger_init:
            return self._ledger
        self._ledger_init = True
        d = self._data_dir()
        self._ledger = DispatchLedger(d / "scheduler_decisions.jsonl") if d else DispatchLedger(None)
        return self._ledger

    def _durable_mode(self) -> bool:
        tasks = getattr(self.aj, "tasks", None)
        return bool(tasks is not None and getattr(tasks, "_path", None) is not None)

    def _persistence_healthy_for_dispatch(self) -> (bool, str):
        # In-memory/non-durable task store: durable dispatch intent ledger is not
        # applicable (legacy/ephemeral mode). Preserve in-process dispatch behavior.
        if not self._durable_mode():
            return True, "ephemeral in-memory mode (durable intent not applicable)"
        # Conservative: durable task storage path and required stores must be present/trustable.
        d = self._data_dir()
        if d is None:
            return False, "no durable task/data directory available"
        if getattr(self.aj, "tasks", None) is None:
            return False, "task store unavailable"
        try:
            # Basic writability signal for append-only decision evidence path parent.
            if not d.exists():
                return False, "data directory does not exist"
            test_path = d / ".scheduler_health_probe"
            test_path.write_text("", encoding="utf-8")
            try:
                test_path.unlink()
            except Exception:
                pass
        except Exception as exc:
            return False, f"persistence health probe failed: {type(exc).__name__}"
        return True, "ok"

    # --- eligibility ----------------------------------------------------------
    def _active_or_uncertain(self, record: taskmod.TaskRecord, *, allow_lease_worker: str = "") -> (bool, str, Dict[str, Any]):
        details: Dict[str, Any] = {"task_status": record.status}
        # Task lifecycle states that indicate active/in-flight or explicit review/uncertainty.
        if record.status in (taskmod.EXECUTING, taskmod.VERIFYING, taskmod.CANCEL_REQUESTED):
            return True, "task is in an active/in-flight state", details
        if record.status in (taskmod.RECOVERY_REQUIRED,):
            return True, "task requires recovery/manual review", details
        # Existing active execution lease => another worker/run may own execution.
        try:
            lease = self.aj.leases.get(record.task_id)
        except Exception as exc:
            details["lease_error"] = f"{type(exc).__name__}: {exc}"
            return True, "execution lease state cannot be trusted", details
        if lease is not None:
            try:
                op = str(getattr(lease, "operation", "") or "")
                raw = str(getattr(lease, "status", "") or "")
                expired = bool(lease.expired()) if raw == "ACTIVE" else False
                details["lease"] = {"operation": op, "status": raw, "expired": expired,
                                    "lease_id": getattr(lease, "lease_id", None),
                                    "worker_id": getattr(lease, "worker_id", None)}
                if op == "execute" and raw == "ACTIVE":
                    if allow_lease_worker and str(getattr(lease, "worker_id", "") or "") == allow_lease_worker:
                        pass  # lease held by current dispatch context
                    else:
                        return True, "active execution lease exists", details
                if raw == "EXPIRED":
                    # Uncertain ownership/outcome window; fail closed for redispatch.
                    return True, "expired/stale lease indicates uncertain ownership", details
            except Exception as exc:
                details["lease_error"] = f"{type(exc).__name__}: {exc}"
                return True, "execution lease state cannot be interpreted", details
        # Current execution record in active/uncertain state.
        try:
            xid = str(getattr(record, "current_execution_id", "") or "")
            if xid and getattr(self.aj, "executions", None) is not None:
                ex = self.aj.executions.get(xid)
                if ex is not None:
                    details["execution"] = {"execution_id": ex.execution_id, "status": ex.status}
                    if ex.status in ("CREATED", "READY", "RUNNING", "UNKNOWN", "RECOVERY_REQUIRED"):
                        # During dispatch we may have just created/marked execution intent; caller can decide.
                        # Treat as uncertain for general eligibility; dispatch recheck can be more specific if needed.
                        if not allow_lease_worker:
                            return True, "current execution is active or uncertain", details
        except Exception as exc:
            details["execution_error"] = f"{type(exc).__name__}: {exc}"
            return True, "execution state cannot be trusted", details
        return False, "no active/uncertain execution detected", details

    def evaluate_eligibility(self, task_id: str, *, now: Optional[float] = None,
                             allow_lease_worker: str = "") -> EligibilityDecision:
        now = time.time() if now is None else float(now)
        try:
            record = self.aj.tasks.get(task_id)
        except Exception as exc:
            return EligibilityDecision(False, PERSISTENCE_UNAVAILABLE,
                                       f"Task cannot be loaded safely: {type(exc).__name__}: {exc}",
                                       {"task_id": task_id})

        if record.terminal or record.status in taskmod.TERMINAL:
            return EligibilityDecision(False, TERMINAL,
                                       f"Task is terminal ({record.status}) and not schedulable.",
                                       {"status": record.status})

        if record.status == taskmod.WAITING_FOR_APPROVAL:
            return EligibilityDecision(False, AUTHORIZATION_REQUIRED,
                                       "Task requires authorization/approval before dispatch.",
                                       {"status": record.status})

        if record.status == taskmod.RECOVERY_REQUIRED:
            return EligibilityDecision(False, RECOVERY_OR_REVIEW_REQUIRED,
                                       "Task requires recovery/manual review before dispatch.",
                                       {"status": record.status})

        if record.status == taskmod.BLOCKED:
            try:
                deps = self.aj.unsatisfied_dependencies(record)
            except Exception as exc:
                return EligibilityDecision(False, DEPENDENCY_BLOCKED,
                                           f"Dependency state cannot be evaluated safely: {type(exc).__name__}: {exc}",
                                           {"status": record.status})
            if deps:
                return EligibilityDecision(False, DEPENDENCY_BLOCKED,
                                           f"Task is blocked by unsatisfied dependencies: {', '.join(deps)}.",
                                           {"status": record.status, "dependencies": deps})
            # BLOCKED but deps satisfied: current scheduler dispatch path requires
            # explicit resume/reauthorization promotion; do not claim dispatch-eligible.
            return EligibilityDecision(False, NOT_SCHEDULABLE_STATE,
                                       "Blocked task has no unsatisfied dependencies but is not in a dispatchable state; resume/reauthorization is required.",
                                       {"status": record.status, "dependencies": []})

        # Deadline gate (explicit)
        if record.deadline and float(record.deadline) <= now:
            return EligibilityDecision(False, DEADLINE_EXCEEDED,
                                       "Task deadline has been exceeded.",
                                       {"deadline": record.deadline, "now": now})

        # Explicit active/uncertain/recovery states are never dispatchable.
        if record.status in (taskmod.EXECUTING, taskmod.VERIFYING, taskmod.CANCEL_REQUESTED):
            return EligibilityDecision(False, ALREADY_ACTIVE_OR_UNCERTAIN,
                                       f"Task is already active/in-flight ({record.status}) and cannot be dispatched again.",
                                       {"status": record.status})

        # Dispatchable states for this conservative foundation: AUTHORIZED only.
        # (Other states may become eligible via orchestrator transitions, not by silent dispatch.)
        if record.status != taskmod.AUTHORIZED:
            return EligibilityDecision(False, NOT_SCHEDULABLE_STATE,
                                       f"Task status {record.status} is not directly dispatchable by scheduler.",
                                       {"status": record.status})

        active, why, details = self._active_or_uncertain(record, allow_lease_worker=allow_lease_worker)
        if active:
            code = UNRESOLVED_DISPATCH_INTENT if "dispatch" in why.lower() else ALREADY_ACTIVE_OR_UNCERTAIN
            if "recovery" in why.lower() or "uncertain" in why.lower():
                code = RECOVERY_OR_REVIEW_REQUIRED if record.status == taskmod.RECOVERY_REQUIRED else ALREADY_ACTIVE_OR_UNCERTAIN
            return EligibilityDecision(False, code, why, details)

        # Capability availability gate (policy-level, existing registry behavior)
        cap_id = str(getattr(record, "capability_id", "") or "")
        if cap_id:
            try:
                spec = self.aj.registry.find(cap_id) if getattr(self.aj, "registry", None) else None
            except Exception as exc:
                return EligibilityDecision(False, CAPABILITY_UNAVAILABLE,
                                           f"Capability state cannot be evaluated safely: {type(exc).__name__}: {exc}",
                                           {"capability_id": cap_id})
            if spec is not None:
                try:
                    from .orchestrator import Aj as _Aj  # local import to avoid cycle surprises
                except Exception:
                    _Aj = None
                # Prefer orchestrator's blocker logic if available.
                try:
                    blocker = self.aj._capability_blocker(spec) if hasattr(self.aj, "_capability_blocker") else None
                except Exception as exc:
                    return EligibilityDecision(False, CAPABILITY_UNAVAILABLE,
                                               f"Capability blocker evaluation failed closed: {type(exc).__name__}: {exc}",
                                               {"capability_id": cap_id})
                if blocker is not None:
                    msg = str(getattr(blocker, "message", "") or "capability unavailable or blocked")
                    return EligibilityDecision(False, CAPABILITY_UNAVAILABLE, msg,
                                               {"capability_id": cap_id, "code": getattr(blocker, "code", "")})

        # Persistence trust for dispatch decisions.
        ok_persist, persist_msg = self._persistence_healthy_for_dispatch()
        # Eligibility focuses on task readiness; persistence/capacity unknowns are still
        # surfaced as non-dispatchable here for conservative scheduling decisions.
        if not ok_persist:
            return EligibilityDecision(False, PERSISTENCE_UNAVAILABLE,
                                       f"Persistence not trusted for dispatch: {persist_msg}",
                                       {"persistence": persist_msg})

        return EligibilityDecision(True, ELIGIBLE, "Task is eligible for admission/dispatch consideration.",
                                   {"status": record.status, "capability_id": cap_id})

    # --- admission ------------------------------------------------------------
    def _active_execution_count(self) -> (Optional[int], str):
        """Count active executions conservatively from trusted durable state."""
        try:
            tasks = list(self.aj.tasks.all())
        except Exception as exc:
            return None, f"task scan failed: {type(exc).__name__}: {exc}"
        count = 0
        try:
            for t in tasks:
                if getattr(t, "status", "") in (taskmod.EXECUTING, taskmod.VERIFYING, taskmod.CANCEL_REQUESTED):
                    count += 1
                    continue
                try:
                    lease = self.aj.leases.get(t.task_id)
                except Exception as exc:
                    return None, f"lease read failed: {type(exc).__name__}: {exc}"
                if lease is not None and str(getattr(lease, "operation", "")) == "execute":
                    st = str(getattr(lease, "status", ""))
                    if st == "ACTIVE":
                        count += 1
        except Exception as exc:
            return None, f"active count failed: {type(exc).__name__}: {exc}"
        return count, "ok"

    def evaluate_admission(self, task_id: str, *, eligibility: Optional[EligibilityDecision] = None,
                           now: Optional[float] = None,
                           selected_active: int = 0,
                           selected_waiting: int = 0) -> AdmissionDecision:
        now = time.time() if now is None else float(now)
        elig = eligibility or self.evaluate_eligibility(task_id, now=now)
        if not elig.eligible:
            return AdmissionDecision(False, True, DEFERRED_NOT_ELIGIBLE,
                                     f"Not admitted because task is not eligible: {elig.explanation}",
                                     {"eligibility": elig.to_dict()})

        if not bool(self._cfg("enabled", True)):
            return AdmissionDecision(False, True, DEFERRED_SCHEDULER_DISABLED,
                                     "Scheduler admission is disabled by configuration.",
                                     {})

        ok_persist, persist_msg = self._persistence_healthy_for_dispatch()
        if not ok_persist:
            return AdmissionDecision(False, True, DEFERRED_PERSISTENCE_UNHEALTHY,
                                     f"Deferred: persistence/state not trusted ({persist_msg}).",
                                     {"persistence": persist_msg})

        try:
            max_active = int(self._cfg("global_max_active_executions", 1))
            max_waiting = int(self._cfg("global_max_admitted_waiting", 10))
            max_dispatch = int(self._cfg("max_dispatch_per_run", 5))
            max_workers = int(self._cfg("max_workers", 1))
        except Exception:
            return AdmissionDecision(False, True, DEFERRED_UNKNOWN_CAPACITY,
                                     "Deferred: scheduler capacity configuration is invalid/untrusted.",
                                     {})
        # Defensive bounds (config validation should enforce, but fail closed).
        if min(max_active, max_waiting, max_dispatch, max_workers) < 1 and max_waiting < 0:
            return AdmissionDecision(False, True, DEFERRED_UNKNOWN_CAPACITY,
                                     "Deferred: scheduler capacity bounds are not usable.",
                                     {})
        if max_active < 1 or max_dispatch < 1 or max_workers < 1 or max_waiting < 0:
            return AdmissionDecision(False, True, DEFERRED_UNKNOWN_CAPACITY,
                                     "Deferred: scheduler capacity bounds are not usable.",
                                     {"global_max_active_executions": max_active,
                                      "global_max_admitted_waiting": max_waiting,
                                      "max_dispatch_per_run": max_dispatch,
                                      "max_workers": max_workers})

        active_count, active_msg = self._active_execution_count()
        if active_count is None:
            return AdmissionDecision(False, True, DEFERRED_UNKNOWN_CAPACITY,
                                     f"Deferred: active capacity cannot be determined ({active_msg}).",
                                     {"reason": active_msg})

        # Conservative: account for admissions already selected in this run.
        projected_active = active_count + max(0, int(selected_active))
        if projected_active >= max_active:
            return AdmissionDecision(False, True, DEFERRED_CAPACITY_ACTIVE,
                                     "Deferred: active execution capacity limit reached.",
                                     {"active_count": active_count, "selected_active": selected_active,
                                      "limit": max_active, "limit_kind": "global_max_active_executions"})
        if selected_waiting >= max_waiting:
            return AdmissionDecision(False, True, DEFERRED_CAPACITY_WAITING,
                                     "Deferred: admitted/waiting dispatch capacity limit reached.",
                                     {"selected_waiting": selected_waiting,
                                      "limit": max_waiting, "limit_kind": "global_max_admitted_waiting"})

        # Duplicate/lease conflict check just before admission decision.
        try:
            lease = self.aj.leases.get(task_id)
            if lease is not None and str(getattr(lease, "operation", "")) == "execute":
                st = str(getattr(lease, "status", ""))
                if st in ("ACTIVE", "EXPIRED"):
                    return AdmissionDecision(False, True, DEFERRED_DUPLICATE_OR_LEASE_CONFLICT,
                                             "Deferred: execution lease conflict or uncertain lease state.",
                                             {"lease_status": st, "lease_id": getattr(lease, "lease_id", None)})
        except Exception as exc:
            return AdmissionDecision(False, True, DEFERRED_DUPLICATE_OR_LEASE_CONFLICT,
                                     f"Deferred: lease state cannot be trusted ({type(exc).__name__}).",
                                     {"error": f"{type(exc).__name__}: {exc}"})

        return AdmissionDecision(True, False, ADMITTED,
                                 "Admitted for dispatch under current bounded capacity policy.",
                                 {"active_count": active_count, "selected_active": selected_active,
                                  "limits": {"global_max_active_executions": max_active,
                                             "global_max_admitted_waiting": max_waiting,
                                             "max_dispatch_per_run": max_dispatch,
                                             "max_workers": max_workers}})

    # --- ordering / selection -------------------------------------------------
    def _effective_priority(self, record: taskmod.TaskRecord, now: float) -> int:
        base = int(getattr(record, "priority", 0) or 0)
        aging = int(self._cfg("aging_seconds", 300) or 0)
        if aging <= 0:
            return base
        created = float(getattr(record, "created_at", now) or now)
        waited = max(0.0, now - created)
        # Deterministic, bounded starvation protection: +1 band per aging window.
        boost = int(waited // aging)
        # Cap boost to avoid runaway distortion while still preventing indefinite starvation.
        return base + min(boost, 1000)

    def queue(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        """Compatibility view: task scheduling candidates with explicit decisions/reasons."""
        now = time.time()
        rows: List[Dict[str, Any]] = []
        try:
            records = list(self.aj.tasks.all())
        except Exception:
            return []
        for record in records:
            if record.status not in (taskmod.AUTHORIZED, taskmod.BLOCKED):
                # keep legacy queue scope focused; monitoring API can expose broader view
                continue
            elig = self.evaluate_eligibility(record.task_id, now=now)
            reason = elig.explanation if not elig.eligible else ""
            # legacy fields preserved
            rows.append({
                "task_id": record.task_id,
                "status": record.status,
                "capability": getattr(record, "capability_id", ""),
                "priority": getattr(record, "priority", 0),
                "effective_priority": self._effective_priority(record, now),
                "deadline": getattr(record, "deadline", None),
                "reason": reason,
                "eligible": bool(elig.eligible),
                "eligibility": elig.to_dict(),
            })
        created_by_id = {x.task_id: float(getattr(x, "created_at", 0.0) or 0.0) for x in records}
        for r in rows:
            r["created_at"] = created_by_id.get(r["task_id"], 0.0)
        rows.sort(key=lambda r: (
            -int(r.get("effective_priority", r.get("priority", 0)) or 0),
            -int(r.get("priority", 0) or 0),
            float(r.get("created_at", 0.0) or 0.0),
            str(r.get("task_id", "")),
        ))
        return rows[:limit] if limit and limit > 0 else rows

    def inspect(self) -> Dict[str, Any]:
        """Observational monitoring view (no mutation)."""
        now = time.time()
        out = {
            "ts": now,
            "worker_id": self.worker_id,
            "config": {
                "enabled": bool(self._cfg("enabled", True)),
                "global_max_active_executions": self._cfg("global_max_active_executions", 1),
                "global_max_admitted_waiting": self._cfg("global_max_admitted_waiting", 10),
                "max_dispatch_per_run": self._cfg("max_dispatch_per_run", 5),
                "max_workers": self._cfg("max_workers", 1),
                "aging_seconds": self._cfg("aging_seconds", 300),
            },
            "counts": {},
            "reasons": {"ineligible": {}, "deferred": {}},
            "eligible": [],
            "ineligible": [],
            "admitted": [],
            "deferred": [],
            "active_executions": [],
            "uncertain_or_recovery": [],
            "expired_leases": [],
            "persistence": {},
        }
        try:
            records = list(self.aj.tasks.all())
        except Exception as exc:
            out["error"] = f"task scan failed: {type(exc).__name__}: {exc}"
            return out
        ok_persist, persist_msg = self._persistence_healthy_for_dispatch()
        out["persistence"] = {"trusted_for_dispatch": ok_persist, "detail": persist_msg}

        active_count, active_msg = self._active_execution_count()
        out["counts"]["active_executions_estimate"] = active_count
        out["counts"]["active_executions_estimate_detail"] = active_msg

        # lease observations
        try:
            for l in self.aj.leases.list():
                st = str(getattr(l, "status", ""))
                if st in ("EXPIRED",):
                    out["expired_leases"].append({
                        "task_id": l.task_id, "lease_id": getattr(l, "lease_id", None),
                        "operation": getattr(l, "operation", None), "status": st,
                    })
                if st == "ACTIVE" and str(getattr(l, "operation", "")) == "execute":
                    out["active_executions"].append({
                        "task_id": l.task_id, "lease_id": getattr(l, "lease_id", None),
                        "worker_id": getattr(l, "worker_id", None),
                    })
        except Exception:
            pass

        # decisions over schedulable-scope records
        for r in records:
            elig = self.evaluate_eligibility(r.task_id, now=now)
            item = {"task_id": r.task_id, "status": r.status, "capability": r.capability_id,
                    "priority": r.priority, "effective_priority": self._effective_priority(r, now),
                    "eligibility": elig.to_dict()}
            if elig.eligible:
                adm = self.evaluate_admission(r.task_id, eligibility=elig, now=now)
                item["admission"] = adm.to_dict()
                out["eligible"].append(item)
                if adm.admitted:
                    out["admitted"].append(item)
                else:
                    out["deferred"].append(item)
                    out["reasons"]["deferred"][adm.reason_code] = out["reasons"]["deferred"].get(adm.reason_code, 0) + 1
            else:
                out["ineligible"].append(item)
                out["reasons"]["ineligible"][elig.reason_code] = out["reasons"]["ineligible"].get(elig.reason_code, 0) + 1
            if r.status in (taskmod.RECOVERY_REQUIRED, taskmod.CANCEL_REQUESTED) or elig.reason_code in (RECOVERY_OR_REVIEW_REQUIRED, ALREADY_ACTIVE_OR_UNCERTAIN, UNRESOLVED_DISPATCH_INTENT):
                out["uncertain_or_recovery"].append(item)

        out["counts"].update({
            "tasks_total": len(records),
            "eligible": len(out["eligible"]),
            "ineligible": len(out["ineligible"]),
            "admitted": len(out["admitted"]),
            "deferred": len(out["deferred"]),
            "expired_leases": len(out["expired_leases"]),
            "uncertain_or_recovery": len(out["uncertain_or_recovery"]),
        })
        # dispatch evidence summary (observational)
        try:
            led = self._ledger_store()
            out["dispatch_evidence"] = {"available": led is not None, "records": len(led.read_all()) if led else 0}
        except Exception:
            out["dispatch_evidence"] = {"available": False, "records": None, "error": "unreadable"}
        return out

    # --- dispatch -------------------------------------------------------------
    def _record_decision(self, kind: str, task_id: str, payload: Mapping[str, Any],
                         *, required: bool = False) -> Optional[Dict[str, Any]]:
        led = self._ledger_store()
        if led is None:
            return None
        rec = {"kind": kind, "task_id": task_id, "worker_id": self.worker_id}
        rec.update(dict(payload))
        try:
            return led.append(rec)
        except Exception:
            # In durable mode, dispatch-intent/evidence persistence failures must fail closed.
            # In ephemeral mode, inability to persist durable evidence is non-applicable.
            if required and self._durable_mode():
                raise
            return None

    def _dispatch_one(self, task_id: str, *, eligibility: EligibilityDecision,
                      admission: AdmissionDecision) -> SchedulerResult:
        # Persist dispatch intent before lease/dispatch attempt (fail closed in durable mode).
        intent: Dict[str, Any] = {
            "task_id": task_id,
            "eligibility": eligibility.to_dict(),
            "admission": admission.to_dict(),
            "state": "DISPATCH_INTENT_RECORDED",
        }
        try:
            rec = self.aj.tasks.get(task_id)
            intent["task_status"] = rec.status
            intent["operation_id"] = getattr(rec, "operation_id", "")
            intent["current_execution_id"] = getattr(rec, "current_execution_id", "")
        except Exception:
            pass
        try:
            self._record_decision("dispatch_intent", task_id, intent, required=True)
        except Exception as exc:
            return SchedulerResult(task_id, "DEFERRED", False,
                                   f"Dispatch deferred: durable intent/evidence could not be recorded ({exc})",
                                   eligibility=eligibility.to_dict(), admission=admission.to_dict(),
                                   dispatch={"state": "intent_persist_failed", "error": str(exc)})

        lease = None
        try:
            lease = self.aj.leases.acquire(task_id, "execute", worker_id=self.worker_id)
        except errors.AjError as exc:
            try:
                self._record_decision("dispatch_deferred", task_id, {
                    "reason_code": DEFERRED_DUPLICATE_OR_LEASE_CONFLICT,
                    "explanation": str(exc), "state": "LEASE_NOT_ACQUIRED"})
            except Exception:
                pass
            return SchedulerResult(task_id, "SKIPPED", False, str(exc),
                                   eligibility=eligibility.to_dict(), admission=admission.to_dict(),
                                   dispatch={"state": "lease_not_acquired", "error": str(exc)})
        try:
            # Conservative recheck under lease held by this scheduler worker.
            elig2 = self.evaluate_eligibility(task_id, allow_lease_worker=self.worker_id)
            if not elig2.eligible:
                try:
                    self._record_decision("dispatch_aborted", task_id, {
                        "state": "RECHECK_NOT_ELIGIBLE", "eligibility": elig2.to_dict()})
                except Exception:
                    pass
                return SchedulerResult(task_id, "DEFERRED", False,
                                       f"Dispatch aborted after claim: {elig2.explanation}",
                                       eligibility=elig2.to_dict(), admission=admission.to_dict(),
                                       dispatch={"state": "recheck_not_eligible"})
            record = self.aj.tasks.get(task_id)
            if record.deadline and record.deadline <= time.time():
                self.aj.dead_letter(task_id, "deadline exceeded before execution")
                try:
                    self._record_decision("dispatch_deadline", task_id, {
                        "state": "DEADLINE_EXCEEDED"})
                except Exception:
                    pass
                return SchedulerResult(task_id, getattr(record, "status", "DEAD_LETTER"), False,
                                       "deadline exceeded; dead-lettered",
                                       eligibility=elig2.to_dict(), admission=admission.to_dict(),
                                       dispatch={"state": "deadline_exceeded"})
            try:
                self._record_decision("dispatch_started", task_id, {
                    "state": "DISPATCHED", "lease_id": getattr(lease, "lease_id", None)}, required=True)
            except Exception as exc:
                # If we cannot record dispatch start after claiming lease in durable mode, fail closed:
                # do not proceed to resume uncertainly; release lease and mark deferred/uncertain.
                return SchedulerResult(task_id, "DEFERRED", False,
                                       f"Dispatch deferred: dispatch-start evidence could not be recorded ({exc})",
                                       eligibility=elig2.to_dict(), admission=admission.to_dict(),
                                       dispatch={"state": "dispatch_evidence_failed", "error": str(exc)})
            outcome = self.aj.resume(task_id, leased=True)
            try:
                self._record_decision("dispatch_result", task_id, {
                    "state": "RESULT_RECORDED", "status": outcome.status,
                    "ok": bool(getattr(outcome, "ok", False)),
                    "summary": str(getattr(outcome, "summary", ""))[:300]})
            except Exception:
                pass
            return SchedulerResult(task_id, outcome.status, bool(getattr(outcome, "ok", False)),
                                   str(getattr(outcome, "summary", "")),
                                   eligibility=elig2.to_dict(), admission=admission.to_dict(),
                                   dispatch={"state": "completed_dispatch_call",
                                             "lease_id": getattr(lease, "lease_id", None)})
        except errors.AjError as exc:
            try:
                self._record_decision("dispatch_error", task_id, {
                    "state": "ERROR", "error": str(exc), "code": getattr(exc, "code", "")})
            except Exception:
                pass
            return SchedulerResult(task_id, "FAILED", False, str(exc),
                                   eligibility=eligibility.to_dict(), admission=admission.to_dict(),
                                   dispatch={"state": "error", "error": str(exc)})
        except Exception as exc:
            # Fail closed: do not claim success; preserve evidence best-effort.
            try:
                self._record_decision("dispatch_error", task_id, {
                    "state": "UNEXPECTED_ERROR", "error": f"{type(exc).__name__}: {exc}"})
            except Exception:
                pass
            return SchedulerResult(task_id, "FAILED", False, f"{type(exc).__name__}: {exc}",
                                   eligibility=eligibility.to_dict(), admission=admission.to_dict(),
                                   dispatch={"state": "unexpected_error", "error": f"{type(exc).__name__}: {exc}"})
        finally:
            if lease is not None:
                try:
                    self.aj.leases.release(lease)
                except Exception:
                    pass

    def run_once(self, *, limit: int = 10, workers: int = 1) -> Dict[str, Any]:
        now = time.time()
        try:
            max_dispatch = int(self._cfg("max_dispatch_per_run", 5))
            cfg_workers = int(self._cfg("max_workers", 1))
            max_waiting = int(self._cfg("global_max_admitted_waiting", 10))
        except Exception:
            max_dispatch, cfg_workers, max_waiting = 5, 1, 10
        # Explicit bounds (no unbounded submission): respect configured caps and caller args.
        effective_limit = max(1, min(int(limit or 1), max_dispatch))
        effective_workers = max(1, min(int(workers or 1), cfg_workers))

        # Evaluate queue candidates in deterministic order.
        try:
            all_rows = self.queue(limit=0)
        except Exception:
            all_rows = []

        decisions: List[Dict[str, Any]] = []
        selected: List[str] = []
        selected_active = 0
        selected_waiting = 0
        admitted_plan: List[Dict[str, Any]] = []

        # Admission is separate from eligibility; defer with reasons.
        for row in all_rows:
            tid = row["task_id"]
            elig = EligibilityDecision(**row["eligibility"]) if isinstance(row.get("eligibility"), dict) else self.evaluate_eligibility(tid, now=now)
            if not elig.eligible:
                decisions.append({"task_id": tid, "eligibility": elig.to_dict(), "admission": None, "selected": False})
                continue
            adm = self.evaluate_admission(tid, eligibility=elig, now=now,
                                          selected_active=selected_active,
                                          selected_waiting=selected_waiting)
            decisions.append({"task_id": tid, "eligibility": elig.to_dict(), "admission": adm.to_dict(),
                              "selected": bool(adm.admitted and len(selected) < effective_limit and selected_waiting < max_waiting)})
            if adm.admitted:
                if len(selected) >= effective_limit or selected_waiting >= max_waiting:
                    # backpressure: capacity to admit more in this run exhausted
                    decisions[-1]["admission"] = AdmissionDecision(
                        False, True, DEFERRED_CAPACITY_WAITING,
                        "Deferred: dispatch/admission run capacity reached (backpressure).",
                        {"limit": effective_limit, "max_waiting": max_waiting},
                    ).to_dict()
                    decisions[-1]["selected"] = False
                    continue
                selected.append(tid)
                admitted_plan.append({"task_id": tid, "eligibility": elig, "admission": adm})
                selected_active += 1
                selected_waiting += 1

        # Bounded dispatch: no unbounded submission, only selected plan.
        results: List[SchedulerResult] = []
        if admitted_plan:
            if effective_workers > 1 and len(admitted_plan) > 1:
                # Bounded pool; each item independently lease-guarded and evidence-recorded.
                with ThreadPoolExecutor(max_workers=effective_workers) as pool:
                    results = list(pool.map(lambda item: self._dispatch_one(item["task_id"], eligibility=item["eligibility"], admission=item["admission"]), admitted_plan))
            else:
                for item in admitted_plan:
                    results.append(self._dispatch_one(item["task_id"], eligibility=item["eligibility"], admission=item["admission"]))

        return {
            "worker_id": self.worker_id,
            "selected": selected,
            "results": [r.to_dict() for r in results],
            "completed": sum(1 for r in results if r.ok),
            "failed": sum(1 for r in results if not r.ok),
            "decisions": decisions,
            "limits": {
                "requested_limit": int(limit or 1),
                "requested_workers": int(workers or 1),
                "effective_limit": effective_limit,
                "effective_workers": effective_workers,
                "max_dispatch_per_run": max_dispatch,
                "global_max_admitted_waiting": max_waiting,
            },
        }
