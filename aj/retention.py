"""Non-destructive retention assessment.

Nothing here deletes or compacts. It reports what exists, what is referenced and
what cannot safely be removed until a verified archive story exists.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict

from .config import Config, memory_path, require_path
from .diagnostics import gather


def assess(config: Config) -> Dict[str, Any]:
    report = gather(config)
    data_dir = require_path(config, "core.data_dir")
    paths = {
        "tasks": data_dir / "tasks.jsonl",
        "audit": require_path(config, "core.audit_dir"),
        "journal": data_dir / "journal.jsonl",
        "receipts": data_dir / "receipts.jsonl",
        "memory": memory_path(config),
    }

    def size(path: Path) -> int:
        if path.is_dir():
            return sum(p.stat().st_size for p in path.glob("*") if p.is_file())
        return path.stat().st_size if path.is_file() else 0

    journal_lines = 0
    journal_path = paths["journal"]
    if journal_path.is_file():
        journal_lines = len([line for line in journal_path.read_text(
            encoding="utf-8", errors="replace").splitlines() if line.strip()])
    receipt_lines = 0
    receipt_path = paths["receipts"]
    if receipt_path.is_file():
        receipt_lines = len([line for line in receipt_path.read_text(
            encoding="utf-8", errors="replace").splitlines() if line.strip()])

    return {
        "read_only": True,
        "destructive_actions": "none",
        "counts": {
            "tasks": report["tasks"]["records"],
            "audit": report["audit"]["events"],
            "journal": journal_lines,
            "receipts": receipt_lines,
            "raw_memory": report["storage"]["memory"].get("raw_events", 0),
            "summaries": report["summaries"].get("count", 0),
        },
        "sizes_bytes": {name: size(path) for name, path in paths.items()},
        "oldest_newest": {
            "tasks_updated": report["tasks"]["last"],
            "audit_last": report["audit"]["last"],
        },
        "candidates": {
            "audit": "archive only after a verified external copy",
            "journal": "archive only after receipts/tasks reference audit is verified",
            "receipts": "retain while their task exists",
        },
        "not_removable": [
            "raw memory events (canonical)",
            "audit events (append-only history)",
            "task transition history required by attempts/receipts",
        ],
        "backup_coverage": "not assessed automatically; run `aj backup --output <dir>`",
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
