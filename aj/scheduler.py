"""Deterministic local scheduler over the durable task store.

Only already-authorized (or dependency-blocked) tasks are eligible. Each task is
claimed with an execution lease before the orchestrator resumes it, so two
scheduler processes cannot execute the same task.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import errors, task as taskmod


@dataclass
class SchedulerResult:
    task_id: str
    status: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"task_id": self.task_id, "status": self.status,
                "ok": self.ok, "detail": self.detail}


class Scheduler:
    def __init__(self, aj, *, worker_id: str = ""):
        self.aj = aj
        self.worker_id = worker_id or f"scheduler-{time.time_ns()}"

    def queue(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        rows = []
        now = time.time()
        for record in self.aj.tasks.all():
            if record.status not in (taskmod.AUTHORIZED, taskmod.BLOCKED):
                continue
            reason = ""
            if record.status == taskmod.BLOCKED:
                deps = self.aj.unsatisfied_dependencies(record)
                if deps:
                    reason = f"waiting for {', '.join(deps)}"
            overdue = bool(record.deadline and record.deadline <= now)
            if overdue:
                reason = reason or "deadline exceeded"
            rows.append({"task_id": record.task_id, "status": record.status,
                         "capability": record.capability_id,
                         "priority": record.priority,
                         "deadline": record.deadline, "reason": reason,
                         "eligible": not reason or reason.startswith("waiting") is False})
        rows.sort(key=lambda row: (-int(row["priority"]), row["task_id"]))
        return rows[:limit] if limit and limit > 0 else rows

    def _run_one(self, task_id: str) -> SchedulerResult:
        lease = None
        try:
            lease = self.aj.leases.acquire(task_id, "execute",
                                           worker_id=self.worker_id)
        except errors.AjError as exc:
            return SchedulerResult(task_id, "SKIPPED", False, str(exc))
        try:
            record = self.aj.tasks.get(task_id)
            if record.deadline and record.deadline <= time.time():
                self.aj.dead_letter(task_id, "deadline exceeded before execution")
                return SchedulerResult(task_id, record.status, False,
                                       "deadline exceeded; dead-lettered")
            outcome = self.aj.resume(task_id, leased=True)
            return SchedulerResult(task_id, outcome.status, outcome.ok,
                                   outcome.summary)
        except errors.AjError as exc:
            return SchedulerResult(task_id, "FAILED", False, str(exc))
        finally:
            if lease is not None:
                try:
                    self.aj.leases.release(lease)
                except errors.AjError:
                    pass

    def run_once(self, *, limit: int = 10, workers: int = 1) -> Dict[str, Any]:
        candidates = [row for row in self.queue(limit=0)
                      if row["status"] == taskmod.AUTHORIZED
                      and not (row["deadline"] and row["deadline"] <= time.time())]
        selected = [row["task_id"] for row in candidates[:limit]]
        if workers > 1 and len(selected) > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(self._run_one, selected))
        else:
            results = [self._run_one(task_id) for task_id in selected]
        return {
            "worker_id": self.worker_id,
            "selected": selected,
            "results": [result.to_dict() for result in results],
            "completed": sum(1 for result in results if result.ok),
            "failed": sum(1 for result in results if not result.ok),
        }
