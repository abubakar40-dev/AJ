"""Conservative, evidence-based recovery for persisted tasks.

Recovery decisions are explicit and fail-closed:
* Automatic replay is allowed only when the control plane can demonstrate a safe
  case from durable evidence (status, attempts, leases, journal, receipts,
  capability replay safety, and idempotency/retry constraints as applicable).
* Ambiguous, conflicting, malformed, or insufficient evidence is never replayed;
  it is reported/reconciled as ``recovery_required``.
* Terminal/completed work is never resurrected.
* Scanning is read-only. Explicit recovery mutates only through controlled,
  auditable store/orchestrator operations and must converge on repeated runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import task as taskmod
from .orchestrator import Aj, TaskOutcome

REPLAY_SAFE = "replay_safe"
RECOVERY_REQUIRED = "recovery_required"
CONVERGED = "converged"
BLOCKED = "blocked"


@dataclass(frozen=True)
class Finding:
    task_id: str
    status: str
    capability_id: str
    decision: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "capability_id": self.capability_id,
            "decision": self.decision,
            "reason": self.reason,
        }


def _map_assessment(assessment: Dict[str, Any], record: taskmod.TaskRecord) -> Finding:
    decision = str(assessment.get("decision") or RECOVERY_REQUIRED)
    reason = str(assessment.get("reason") or "recovery decision unavailable")
    if decision == "replay":
        mapped = REPLAY_SAFE
    elif decision == "converged":
        mapped = CONVERGED
    elif decision == "blocked":
        mapped = BLOCKED
    elif decision == "terminal":
        mapped = CONVERGED
    else:
        mapped = RECOVERY_REQUIRED
    return Finding(record.task_id, record.status, record.capability_id, mapped, reason)


def classify(aj: Aj, record: taskmod.TaskRecord) -> Finding:
    """Assess one persisted task for recovery. Never executes."""
    if record.terminal:
        return Finding(record.task_id, record.status, record.capability_id,
                       CONVERGED, "terminal tasks are not recovered")
    try:
        assessment = aj._assess_recovery(record)
        return _map_assessment(assessment, record)
    except Exception as exc:
        # Fail closed: classification must not claim replay safety on assessment failure.
        return Finding(record.task_id, record.status, record.capability_id,
                       RECOVERY_REQUIRED,
                       f"recovery assessment failed closed: {type(exc).__name__}: {exc}")


class RecoveryManager:
    """Read interrupted tasks and apply explicit, evidence-based recovery."""

    def __init__(self, aj: Aj):
        self.aj = aj

    def scan(self) -> List[Finding]:
        # Read-only scan over non-terminal persisted tasks.
        return [classify(self.aj, record)
                for record in self.aj.tasks.query(newest_first=False)
                if not record.terminal]

    def _recover_one(self, task_id: str, *, finding: Optional[Finding] = None) -> TaskOutcome:
        # Delegate to orchestrator for a single source of truth on evidence,
        # convergence, ownership/lease safety, and fail-closed behavior.
        return self.aj.recover(task_id, approval="")

    def recover(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Recover one task or every interrupted task.

        Explicit single-task recovery always runs through the orchestrator's
        evidence-based decision path and may return converged/blocked/manual
        outcomes without unsafe replay. Batch recovery attempts automatic recovery
        only for tasks assessed replay-safe; other findings are reported honestly.
        """
        if task_id:
            record = self.aj.tasks.get(task_id)
            finding = classify(self.aj, record)
            outcome = self._recover_one(task_id, finding=finding)
            # Re-read status after recovery attempt for honest reporting.
            try:
                current = self.aj.tasks.get(task_id)
                finding = Finding(finding.task_id, current.status, current.capability_id,
                                  finding.decision, finding.reason)
            except Exception:
                pass
            return {"findings": [finding.to_dict()],
                    "outcomes": [outcome.to_dict()]}

        findings = self.scan()
        outcomes: List[Dict[str, Any]] = []
        for finding in findings:
            if finding.decision == REPLAY_SAFE:
                try:
                    outcomes.append(self._recover_one(finding.task_id, finding=finding).to_dict())
                except Exception as exc:
                    outcomes.append({
                        "task_id": finding.task_id,
                        "status": "",
                        "ok": False,
                        "summary": f"Recovery failed closed: {type(exc).__name__}: {exc}",
                        "route_rule": "recovery",
                        "requires_user_decision": False,
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                    })
        return {"findings": [finding.to_dict() for finding in findings],
                "outcomes": outcomes}
