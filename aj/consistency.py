"""Read-only task/audit/journal/operation-evidence consistency checking.

Phase 3E: detects and classifies inconsistencies and partial operations without
mutating canonical stores or fabricating evidence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .audit import read_events
from .operation_evidence import OperationEvidenceStore


def _safe_read_jsonl(path: Path) -> Tuple[List[Dict[str, Any]], int]:
    if not path.is_file():
        return [], 0
    rows: List[Dict[str, Any]] = []
    malformed = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return [{"_read_error": True, "path": str(path)}], 0
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            malformed += 1
            rows.append({"_parse_error": True})
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            malformed += 1
            rows.append({"_parse_error": True})
    return rows, malformed


def _finding(severity: str, category: str, message: str, *, confidence: str = "confirmed",
             task_id: str = "", operation_id: str = "", evidence: Any = None,
             operator_action: str = "") -> Dict[str, Any]:
    return {
        "severity": severity,
        "category": category,
        "confidence": confidence,  # confirmed | uncertain | missing_information
        "message": message,
        "task_id": task_id,
        "operation_id": operation_id,
        "evidence": evidence,
        "operator_action": operator_action,
    }


def check_consistency(data_dir: str | Path, audit_dir: str | Path, *, task_id: str = "") -> Dict[str, Any]:
    """Read-only consistency inspection across task/audit/journal/reconciliation evidence.

    Never mutates stores. Distinguishes confirmed inconsistency from uncertainty.
    """
    data_dir = Path(data_dir)
    audit_dir = Path(audit_dir)
    findings: List[Dict[str, Any]] = []
    summary = {"confirmed": 0, "uncertain": 0, "missing_information": 0,
               "critical": 0, "high": 0, "medium": 0, "low": 0}

    def add(f: Dict[str, Any]) -> None:
        findings.append(f)
        summary[f.get("confidence", "confirmed")] = summary.get(f.get("confidence", "confirmed"), 0) + 1
        sev = str(f.get("severity", "low")).lower()
        if sev in summary:
            summary[sev] += 1

    # Load stores (read-only)
    tasks_path = data_dir / "tasks.jsonl"
    journal_path = data_dir / "journal.jsonl"
    receipts_path = data_dir / "receipts.jsonl"
    ops_path = data_dir / "reconciliation_operations.jsonl"
    leases_dir = data_dir / "leases"

    task_rows, task_malformed = _safe_read_jsonl(tasks_path)
    task_records = []
    for r in task_rows:
        if not isinstance(r, dict) or r.get("_parse_error") or r.get("_read_error"):
            continue
        # TaskStore appends envelopes {"reason": ..., "task": {...}}; tolerate direct records too.
        if isinstance(r.get("task"), dict):
            task_records.append(r.get("task") or {})
        else:
            task_records.append(r)
    if task_malformed:
        add(_finding("medium", "task_store_malformed", f"{task_malformed} malformed task record line(s) detected",
                     confidence="confirmed", evidence={"path": str(tasks_path)}))
    if any(r.get("_read_error") for r in task_rows):
        add(_finding("high", "task_store_unreadable", "task store could not be read completely",
                     confidence="uncertain", evidence={"path": str(tasks_path)},
                     operator_action="inspect filesystem/storage health; do not assume task state"))

    journal_rows, journal_malformed = _safe_read_jsonl(journal_path)
    journal_events = [r for r in journal_rows if isinstance(r, dict) and not r.get("_parse_error") and not r.get("_read_error")]
    if journal_malformed:
        add(_finding("medium", "journal_malformed", f"{journal_malformed} malformed journal event line(s) detected",
                     confidence="confirmed", evidence={"path": str(journal_path)}))

    receipt_rows, receipt_malformed = _safe_read_jsonl(receipts_path)
    receipts = [r for r in receipt_rows if isinstance(r, dict) and not r.get("_parse_error") and not r.get("_read_error")]
    if receipt_malformed:
        add(_finding("medium", "receipt_malformed", f"{receipt_malformed} malformed receipt line(s) detected",
                     confidence="confirmed", evidence={"path": str(receipts_path)}))

    audit = read_events(audit_dir, limit=0)
    audit_events = list(audit.events or [])
    if getattr(audit, "malformed", 0):
        add(_finding("medium", "audit_malformed", f"{audit.malformed} malformed audit line(s) detected",
                     confidence="confirmed", evidence={"audit_dir": str(audit_dir)}))

    # Task index (latest-by-task snapshot approximation from append-only records)
    task_latest: Dict[str, Dict[str, Any]] = {}
    for r in task_records:
        tid = str(r.get("task_id") or "")
        if not tid:
            continue
        prev = task_latest.get(tid)
        if prev is None or float(r.get("updated_at") or 0) >= float(prev.get("updated_at") or 0):
            task_latest[tid] = r
    if task_id:
        task_latest = {k: v for k, v in task_latest.items() if k == task_id}

    # Index evidence by task
    journal_by_task: Dict[str, List[Dict[str, Any]]] = {}
    for e in journal_events:
        tid = str(e.get("task_id") or "")
        if tid:
            journal_by_task.setdefault(tid, []).append(e)
    receipts_by_task: Dict[str, List[Dict[str, Any]]] = {}
    for r in receipts:
        tid = str(r.get("task_id") or "")
        if tid:
            receipts_by_task.setdefault(tid, []).append(r)
    audit_by_task: Dict[str, List[Dict[str, Any]]] = {}
    for e in audit_events:
        tid = str(e.get("task_id") or "")
        if tid:
            audit_by_task.setdefault(tid, []).append(e)

    # Reconciliation operation evidence
    op_store = OperationEvidenceStore(ops_path)
    op_views = op_store.list_operations(task_id=task_id)
    op_by_id: Dict[str, Dict[str, Any]] = {}
    for v in op_views:
        d = v.to_dict()
        op_by_id[v.operation_id] = d
        if v.is_incomplete():
            add(_finding("high", "incomplete_privileged_operation",
                         f"reconciliation operation {v.operation_id} has intent without terminal outcome",
                         confidence="confirmed", task_id=str((v.intent or {}).get('task_id') or ""),
                         operation_id=v.operation_id,
                         evidence={"intent": v.intent, "progress_count": len(v.progress)},
                         operator_action="inspect task/audit/journal and operation evidence; do not auto-retry or mark success; determine actual state before any manual disposition"))
    # Duplicate/parse issues in op store
    for r in op_store.read_all():
        if isinstance(r, dict) and r.get("_parse_error"):
            add(_finding("medium", "operation_evidence_malformed", "malformed operation-evidence record detected",
                         confidence="confirmed", evidence={"path": str(ops_path)}))

    # Leases (best-effort read-only snapshot)
    lease_states: Dict[str, Any] = {}
    if leases_dir.is_dir():
        for p in sorted(leases_dir.glob("*.json")):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                add(_finding("medium", "lease_malformed", f"could not parse lease file {p.name}",
                             confidence="confirmed", evidence={"path": str(p)}))
                continue
            if isinstance(obj, dict):
                tid = str(obj.get("task_id") or p.stem)
                lease_states[tid] = obj

    # Cross-store checks per known task
    now = time.time()
    for tid, task in task_latest.items():
        status = str(task.get("status") or "")
        op_id = str(task.get("operation_id") or "")
        attempts = task.get("attempts") or []
        if not isinstance(attempts, list):
            attempts = []
        attempt_ids = {str(a.get("attempt_id")) for a in attempts if isinstance(a, dict) and a.get("attempt_id")}
        j = journal_by_task.get(tid, [])
        rcs = receipts_by_task.get(tid, [])
        aev = audit_by_task.get(tid, [])

        # Orphan/correlation gaps: receipts/journal referencing unknown attempts
        for rc in rcs:
            aid = str(rc.get("attempt_id") or "")
            if aid:
                if attempt_ids and aid not in attempt_ids:
                    add(_finding("high", "orphan_receipt_attempt",
                                 f"receipt {rc.get('receipt_id')} references unknown attempt_id {aid}",
                                 confidence="confirmed", task_id=tid,
                                 evidence={"receipt_id": rc.get("receipt_id"), "attempt_id": aid}))
                elif not attempt_ids:
                    add(_finding("medium", "receipt_attempt_unlinked",
                                 f"receipt {rc.get('receipt_id')} references attempt_id {aid} but task has no attempt history",
                                 confidence="uncertain", task_id=tid,
                                 evidence={"receipt_id": rc.get("receipt_id"), "attempt_id": aid}))
            if op_id and rc.get("operation_id") not in (None, "", op_id):
                add(_finding("high", "receipt_operation_mismatch",
                             f"receipt {rc.get('receipt_id')} operation_id does not match task operation",
                             confidence="confirmed", task_id=tid,
                             evidence={"receipt": rc.get("receipt_id"), "task_operation_id": op_id, "receipt_operation_id": rc.get("operation_id")}))
        for ev in j:
            aid = str(ev.get("attempt_id") or "")
            if aid:
                if attempt_ids and aid not in attempt_ids:
                    add(_finding("high", "orphan_journal_attempt",
                                 f"journal event {ev.get('event_id')} references unknown attempt_id {aid}",
                                 confidence="confirmed", task_id=tid,
                                 evidence={"event_id": ev.get("event_id"), "attempt_id": aid}))
                elif not attempt_ids:
                    add(_finding("medium", "journal_attempt_unlinked",
                                 f"journal event {ev.get('event_id')} references attempt_id {aid} but task has no attempt history",
                                 confidence="uncertain", task_id=tid,
                                 evidence={"event_id": ev.get("event_id"), "attempt_id": aid}))
            if op_id and ev.get("operation_id") not in (None, "", op_id):
                add(_finding("medium", "journal_operation_mismatch",
                             f"journal event {ev.get('event_id')} operation_id does not match task operation",
                             confidence="confirmed", task_id=tid,
                             evidence={"event_id": ev.get("event_id"), "task_operation_id": op_id, "event_operation_id": ev.get("operation_id")}))

        # Completion/conflict signals
        success_receipts = [r for r in rcs if str(r.get("execution_status") or r.get("status") or "") == "COMPLETED"]
        if success_receipts and status not in ("COMPLETED", "ABANDONED"):
            add(_finding("high", "completion_evidence_conflict",
                         "completion receipt exists but canonical task is not terminal/completed",
                         confidence="confirmed", task_id=tid,
                         evidence={"receipt_ids": [r.get("receipt_id") for r in success_receipts], "status": status},
                         operator_action="manual reconciliation/inspection required; do not auto-retry or auto-complete"))

        # Operator reconciliation state changed but evidence trail markers missing (best-effort)
        rec_meta = ((task.get("recovery") or {}).get("operator_reconciliation") or {}) if isinstance(task.get("recovery"), dict) else {}
        if isinstance(rec_meta, dict) and rec_meta.get("outcome") == "ok" and rec_meta.get("evidence_recording") == "incomplete":
            add(_finding("high", "reconciliation_evidence_incomplete",
                         "operator reconciliation changed or reported state but evidence trail marked incomplete",
                         confidence="confirmed", task_id=tid,
                         evidence={"operator_reconciliation": rec_meta},
                         operator_action="inspect audit/journal/task metadata; treat reconciliation outcome as not fully auditable"))

        # Expected evidence presence (uncertain/missing info, not always inconsistency)
        if status in ("RECOVERY_REQUIRED", "FAILED", "ABORTED", "DEAD_LETTER", "CANCELLED", "COMPLETED") and not j and not aev and not rcs:
            add(_finding("low", "limited_evidence",
                         f"task in state {status} has no associated journal/audit/receipt records in scanned stores",
                         confidence="missing_information", task_id=tid,
                         evidence={"status": status},
                         operator_action="verify store paths and historical context before concluding"))

    # Reconciliation audit/journal correlation for op evidence
    audit_op_actions = [e for e in audit_events if e.get("action") == "operator_reconciliation"]
    for v in op_views:
        d = op_by_id.get(v.operation_id, {})
        tid = str(d.get("task_id") or "")
        if v.terminal_outcome and str(v.terminal_outcome.get("status")) == "COMPLETED":
            # best-effort: expect an audit event for this task/action around time (not strictly required by id, but useful signal)
            related = [e for e in audit_op_actions if e.get("task_id") == tid]
            if not related:
                add(_finding("medium", "operation_outcome_without_audit_correlation",
                             f"completed reconciliation operation {v.operation_id} has no correlated operator_reconciliation audit event in scan window",
                             confidence="uncertain", task_id=tid, operation_id=v.operation_id,
                             evidence={"task_id": tid, "action": d.get("action")},
                             operator_action="inspect audit logs and operation evidence for partial trail"))

    # Summaries for operator-readable use
    counts = {
        "tasks_scanned": len(task_latest),
        "journal_events_scanned": len(journal_events),
        "audit_events_scanned": len(audit_events),
        "receipts_scanned": len(receipts),
        "reconciliation_operations_scanned": len(op_views),
        "incomplete_reconciliation_operations": sum(1 for v in op_views if v.is_incomplete()),
        "findings": len(findings),
    }
    status = "consistent" if not findings else ("inconsistent" if any(f.get("confidence") == "confirmed" for f in findings) else "uncertain")
    operator_summary = []
    operator_summary.append(f"consistency status: {status}; findings={counts['findings']} (confirmed={summary['confirmed']}, uncertain={summary['uncertain']}, missing={summary['missing_information']})")
    if counts["incomplete_reconciliation_operations"]:
        operator_summary.append(f"incomplete privileged reconciliation operations: {counts['incomplete_reconciliation_operations']} (manual inspection required)")
    for f in findings[:10]:
        operator_summary.append(f"[{f.get('severity')}/{f.get('confidence')}] {f.get('category')}: {f.get('message')}")

    return {
        "ok": len(findings) == 0,
        "status": status,
        "scanned": {
            "data_dir": str(data_dir),
            "audit_dir": str(audit_dir),
            "task_filter": task_id or None,
        },
        "counts": counts,
        "summary": summary,
        "findings": findings,
        "incomplete_operations": [v.to_dict() for v in op_views if v.is_incomplete()],
        "operator_summary": "\n".join(operator_summary),
    }
