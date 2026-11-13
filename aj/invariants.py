"""Read-only invariant checks over persisted task, lease and receipt state."""

from __future__ import annotations

from typing import Any, Dict, List

from .task import TERMINAL, TRANSITIONS


def check(aj) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    records = aj.tasks.all()

    for record in records:
        if record.status not in TRANSITIONS:
            issues.append({"task_id": record.task_id, "kind": "unknown_state",
                           "detail": record.status})
        if record.terminal and record.completed_at is None:
            issues.append({"task_id": record.task_id, "kind": "terminal_without_time"})
        numbers = [int(a.get("attempt_number", 0)) for a in record.attempts]
        if numbers != list(range(1, len(numbers) + 1)):
            issues.append({"task_id": record.task_id,
                           "kind": "attempt_numbering",
                           "detail": numbers})
        for attempt in record.attempts:
            if attempt.get("status") == "RUNNING" and record.terminal:
                issues.append({"task_id": record.task_id,
                               "kind": "running_attempt_on_terminal",
                               "detail": attempt.get("attempt_id")})
        if record.operation_id and record.attempts:
            if any(a.get("operation_id") != record.operation_id
                   for a in record.attempts):
                issues.append({"task_id": record.task_id,
                               "kind": "operation_id_mismatch"})

    for lease in aj.leases.list():
        record = aj.tasks.find(lease.task_id)
        if record is None:
            issues.append({"task_id": lease.task_id, "kind": "lease_without_task",
                           "detail": lease.lease_id})
        elif lease.status == "ACTIVE" and record.terminal:
            issues.append({"task_id": lease.task_id,
                           "kind": "active_lease_on_terminal_task",
                           "detail": lease.lease_id})

    for receipt in aj.receipts.list(limit=0):
        record = aj.tasks.find(receipt.get("task_id", ""))
        if record is None:
            issues.append({"task_id": receipt.get("task_id", ""),
                           "kind": "receipt_without_task",
                           "detail": receipt.get("receipt_id")})
        elif receipt.get("operation_id") and receipt["operation_id"] != record.operation_id:
            issues.append({"task_id": record.task_id,
                           "kind": "receipt_operation_mismatch",
                           "detail": receipt.get("receipt_id")})

    return {"ok": not issues, "tasks": len(records),
            "leases": len(aj.leases.list()),
            "receipts": aj.receipts.count(), "issues": issues}
