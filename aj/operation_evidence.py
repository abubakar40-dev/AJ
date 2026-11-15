"""Durable, append-only evidence for privileged operations.

Phase 3E: reconciliation (and future privileged operations) record intent before
state-changing work and outcome/progress after. An intent without a terminal
outcome is an incomplete/interrupted operation and must never be fabricated as
success.

This store is append-only evidence. It does not replace TaskStore/audit/journal;
it correlates privileged operation lifecycle for consistency and crash-window
analysis.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from . import errors, ids
from .audit import _redact
from .locking import file_lock

SCHEMA_VERSION = 1

INTENDED = "INTENDED"
IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
REFUSED = "REFUSED"
BLOCKED = "BLOCKED"
FAILED = "FAILED"
INCOMPLETE = "INCOMPLETE"  # derived, not stored as fabrication

_TERMINAL_OUTCOMES = {COMPLETED, REFUSED, BLOCKED, FAILED}


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _redact(str(k), _safe(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value[:30]]
    if isinstance(value, str):
        return value[:1000]
    return value


@dataclass
class OperationEvidenceView:
    operation_id: str
    records: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def intent(self) -> Optional[Dict[str, Any]]:
        for r in self.records:
            if r.get("record_type") == "intent":
                return r
        return None

    @property
    def outcomes(self) -> List[Dict[str, Any]]:
        return [r for r in self.records if r.get("record_type") == "outcome"]

    @property
    def progress(self) -> List[Dict[str, Any]]:
        return [r for r in self.records if r.get("record_type") == "progress"]

    @property
    def terminal_outcome(self) -> Optional[Dict[str, Any]]:
        for r in reversed(self.outcomes):
            st = str(r.get("status") or "")
            if st in _TERMINAL_OUTCOMES:
                return r
        return None

    def derived_status(self) -> str:
        out = self.terminal_outcome
        if out is not None:
            return str(out.get("status") or COMPLETED)
        if self.intent is not None:
            return INTENDED
        return "UNKNOWN"

    def is_incomplete(self) -> bool:
        return self.intent is not None and self.terminal_outcome is None

    def to_dict(self) -> Dict[str, Any]:
        intent = self.intent or {}
        out = self.terminal_outcome
        return {
            "operation_id": self.operation_id,
            "operation_kind": intent.get("operation_kind", ""),
            "task_id": intent.get("task_id", ""),
            "action": intent.get("action", ""),
            "status": self.derived_status(),
            "incomplete": self.is_incomplete(),
            "intent": intent or None,
            "outcome": out,
            "progress_count": len(self.progress),
            "record_count": len(self.records),
        }


class OperationEvidenceStore:
    """Append-only JSONL store for privileged operation evidence."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        line = json.dumps(record, ensure_ascii=False, default=str, sort_keys=True)
        with file_lock(str(self.path) + ".lock", timeout=5.0):
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        return record

    def read_all(self) -> List[Dict[str, Any]]:
        if not self.path.is_file():
            return []
        with file_lock(str(self.path) + ".lock", exclusive=False, timeout=5.0):
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        out: List[Dict[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                out.append({"_parse_error": True, "raw": line[:500]})
                continue
            if not isinstance(rec, dict):
                out.append({"_parse_error": True, "raw": str(rec)[:500]})
                continue
            out.append(rec)
        return out

    def by_operation(self, operation_id: str) -> OperationEvidenceView:
        recs = [r for r in self.read_all()
                if isinstance(r, dict) and r.get("operation_id") == operation_id and not r.get("_parse_error")]
        recs.sort(key=lambda r: float(r.get("ts") or 0.0))
        return OperationEvidenceView(operation_id=operation_id, records=recs)

    def list_operations(self, *, task_id: str = "", operation_kind: str = "") -> List[OperationEvidenceView]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in self.read_all():
            if not isinstance(r, dict) or r.get("_parse_error"):
                continue
            op = str(r.get("operation_id") or "")
            if not op:
                continue
            groups.setdefault(op, []).append(r)
        views: List[OperationEvidenceView] = []
        for op, recs in groups.items():
            recs.sort(key=lambda r: float(r.get("ts") or 0.0))
            view = OperationEvidenceView(operation_id=op, records=recs)
            intent = view.intent or {}
            if task_id and intent.get("task_id") != task_id:
                continue
            if operation_kind and intent.get("operation_kind") != operation_kind:
                continue
            views.append(view)
        views.sort(key=lambda v: float((v.intent or {}).get("ts") or 0.0))
        return views

    def record_intent(self, *, operation_kind: str, operation_id: str, task_id: str,
                      action: str, reason: str = "", evidence_basis: Any = None,
                      operator: str = "", idempotency_key: str = "",
                      correlation: Optional[Mapping[str, Any]] = None,
                      metadata: Optional[Mapping[str, Any]] = None,
                      identity_provenance: Optional[Mapping[str, Any]] = None,
                      requested_operator: str = "") -> Dict[str, Any]:
        req = (requested_operator or operator or "")[:120]
        prov = _safe(dict(identity_provenance or {})) if identity_provenance is not None else {}
        # Never persist secrets; provenance is redacted by _safe/_redact rules.
        if prov and not prov.get("requested_operator"):
            prov["requested_operator"] = req
        rec = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "intent",
            "status": INTENDED,
            "operation_kind": operation_kind,
            "operation_id": operation_id,
            "task_id": task_id,
            "action": action,
            "reason": (reason or "")[:500],
            "evidence_basis": _safe(evidence_basis),
            # Compatibility: operator remains requested/caller metadata label.
            "operator": req,
            "requested_operator": req,
            "identity_provenance": prov,
            "idempotency_key": (idempotency_key or "")[:200],
            "correlation": _safe(dict(correlation or {})),
            "metadata": _safe(dict(metadata or {})),
            "ts": time.time(),
        }
        return self._append(rec)

    def record_progress(self, *, operation_id: str, phase: str,
                        detail: str = "", metadata: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        rec = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "progress",
            "operation_id": operation_id,
            "phase": phase,
            "detail": (detail or "")[:500],
            "metadata": _safe(dict(metadata or {})),
            "ts": time.time(),
        }
        return self._append(rec)

    def record_outcome(self, *, operation_id: str, status: str,
                       task_id: str = "", action: str = "",
                       detail: str = "", result: Optional[Mapping[str, Any]] = None,
                       retry_safe: Optional[bool] = None,
                       disposition: str = "",
                       metadata: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        if status not in _TERMINAL_OUTCOMES:
            raise errors.AjError(f"invalid operation outcome status {status!r}", code=errors.CONFIG_INVALID)
        rec = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "outcome",
            "operation_id": operation_id,
            "task_id": task_id,
            "action": action,
            "status": status,
            "detail": (detail or "")[:500],
            "result": _safe(dict(result or {})),
            "retry_safe": retry_safe,
            "disposition": (disposition or "")[:200],
            "metadata": _safe(dict(metadata or {})),
            "ts": time.time(),
        }
        return self._append(rec)
