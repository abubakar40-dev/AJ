"""Conservative recovery for persisted tasks.

Rules
-----
* A task is recoverable only when its capability is an AJ internal action **and**
  the capability is explicitly declared ``replay_safe``.
* Everything else is reported as ``recovery_required`` and is never executed.
* Recovery never changes a task id and never deletes existing events; it appends
  new transitions and audit/memory records.
* Scanning is read-only. Only an explicit recover call mutates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import task as taskmod
from .orchestrator import Aj, TaskOutcome

REPLAY_SAFE = "replay_safe"
RECOVERY_REQUIRED = "recovery_required"


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


def classify(aj: Aj, record: taskmod.TaskRecord) -> Finding:
    """Decide whether one persisted task may be replayed. Never executes."""
    spec = aj.registry.find(record.capability_id) if record.capability_id else None
    if record.capability_id == "":
        reason = "task has no capability to replay"
    elif spec is None:
        reason = f"capability {record.capability_id!r} is not registered"
    elif not spec.execution_adapter.startswith("internal:"):
        reason = "capability is not an internal action"
    elif not spec.replay_safe:
        reason = "capability is not declared replay-safe"
    else:
        return Finding(record.task_id, record.status, spec.capability_id,
                       REPLAY_SAFE, "internal action declared replay-safe")
    return Finding(record.task_id, record.status, record.capability_id,
                   RECOVERY_REQUIRED, reason)


class RecoveryManager:
    """Scan persisted tasks and replay only what is provably safe."""

    def __init__(self, aj: Aj):
        self.aj = aj

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        for record in self.aj.tasks.all():
            if record.terminal:
                continue
            findings.append(classify(self.aj, record))
        return findings

    def recover(self, task_id: Optional[str] = None, *,
                safe_only: bool = True,
                approval: str = "") -> Dict[str, Any]:
        """Recover one task, or every safely replayable one.

        With ``safe_only`` (the default), unsafe tasks are reported and left
        untouched. An explicit ``task_id`` still refuses to replay an unsafe
        task; it marks it ``RECOVERY_REQUIRED`` instead.
        """
        if task_id:
            finding = classify(self.aj, self.aj.tasks.get(task_id))
            outcome = self.aj.recover(task_id, approval=approval)
            return {"findings": [finding.to_dict()],
                    "outcomes": [outcome.to_dict()]}

        findings = self.scan()
        outcomes: List[Dict[str, Any]] = []
        for finding in findings:
            if finding.decision != REPLAY_SAFE:
                continue
            if safe_only:
                outcomes.append(self.aj.recover(finding.task_id,
                                                approval=approval).to_dict())
        return {"findings": [f.to_dict() for f in findings],
                "outcomes": outcomes}
