# AJ — Reliable Local Orchestration Core

**Owner:** AbuBakar · **Status:** Phase 3, local and provider-independent · **Date:** 10 November 2026

AJ is the ecosystem's control plane: it decides *who* may do *what*, records the outcome, persists it, and can reload it after a restart. It is not a second assistant runtime.

```
AJ
├── JARVIS   general-purpose and major-work sub-agent   (not attached)
├── HELIX    calling and communications sub-agent       (not attached)
└── Hermes   execution/skill runtime                    (NOT ATTACHED)
```

## Quick start

```bash
cd AJ
python3 -m venv .venv
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q          # 119 passed
.venv/bin/python -m aj --check         # 23 local checks, exit 0
.venv/bin/python -m aj --demo          # one complete lifecycle
```

Everything is local: no network, no credentials, no database server, no sub-agent, no LLM.

## Commands

```bash
aj --check
aj --demo
aj run --capability aj.echo --input '{"message":"hello"}'
aj run "echo hello"
aj tasks [--status COMPLETED|FAILED] [--limit 20] [--json]
aj task <task-id> [--json]
aj cancel <task-id> [--json]
aj retry <task-id> [--json]
aj recover [--task <id>] [--json]
aj audit [--limit 50] [--task <id>] [--event authorized] [--agent AJ] [--json]
aj memory [--limit 50] [--task <id>] [--type task.completed] [--json]
aj summary [--task <id>] [--rebuild] [--verify] [--json]
aj capabilities [--json]
aj permissions [--json]
aj config [--check] [--json]
aj diagnostics [--json]
aj export --output <file> [--json]
aj import <file> [--dry-run] [--json]
aj backup --output <dir> | --verify <dir> [--json]
aj --version
```

Run from `AJ/` with `.venv/bin/python -m aj …`, or install the console script:

```bash
.venv/bin/python -m pip install -e ".[dev]"
aj --check
```

`--config <path>` selects a config file; `--log-level` overrides `runtime.log_level`.
`--json`, `--quiet` and `--verbose` are global flags and belong before the
subcommand. `--list-capabilities` remains an alias for `capabilities`.

### What `run` is, and is not

`run` executes **only registered internal actions** (`aj.echo`, `aj.health_check`).
It is not a shell and not an agent: it does not spawn processes, evaluate Python,
read credentials or call a network. A capability with a non-internal adapter is
refused with `capability_unavailable`. `"echo …"` maps deterministically to
`aj.echo`; every other free-text goal is refused.

## Lifecycle

```
RECEIVED → UNDERSTANDING → PLANNED → AUTHORIZED → EXECUTING → VERIFYING → COMPLETED
                                                ↘ FAILED → RECOVERING → RETRYING → EXECUTING
                                                ↘ CANCELLED (before execution)
EXECUTING ↘ CANCEL_REQUESTED (honest request; execution was not killed)
```

`FAILED`, `ESCALATED`, `RECOVERY_REQUIRED` and `CANCEL_REQUESTED` are not
terminal: each is an entry point for a human decision. `COMPLETED`, `CANCELLED`
and `ABORTED` are final.

### Attempts

Every execution attempt appends a record to the task:

```json
{"attempt_id": "att_…", "attempt_number": 2, "operation_id": "op_…",
 "started_at": 1794287008.1, "ended_at": 1794287008.2,
 "status": "COMPLETED", "failure": null}
```

The task id survives retry, so history is one lineage:

```
ONE TASK
   ├── attempt 1 → FAILED (failure retained in attempts[0] and errors[])
   └── attempt 2 → COMPLETED
```

`operation_id` is generated once per task and copied into each attempt, so task,
audit, memory and attempt records correlate. Audit events carry `operation_id`
and (once an attempt exists) `attempt_id`; raw-memory metadata carries both; and
execution logs include task, operation, attempt, capability and status.

### Cancel

```bash
aj cancel <task-id>
```

- Before execution (`RECEIVED`, `UNDERSTANDING`, `PLANNED`, `WAITING_FOR_APPROVAL`,
  `AUTHORIZED`, `FAILED`, `ESCALATED`, `RECOVERY_REQUIRED`) the task becomes
  `CANCELLED`; exit 0.
- While `EXECUTING` the task becomes `CANCEL_REQUESTED`, requires a human decision,
  and the command reports **"the running execution was not interrupted"**; exit 1.
  AJ never claims it can forcibly stop arbitrary execution.
- A final task is never mutated; the command explains why and exits 1.

### Retry

```bash
aj retry <task-id>
```

Only `FAILED` tasks can retry, and only when the capability declares
`retry_safe=True` (`aj.echo`, `aj.health_check`). `retry_safe` defaults to
`False`; nothing is inferred from risk level. Completed and cancelled tasks are
refused; the retry budget (`providers.max_attempts`) is enforced, and an exhausted
task is escalated instead of looping. An unsafe retry is refused without
execution, marks the task as needing a decision, and exits 6. The original task
id, failure and history stay visible.

## Persistence and locking

- Task records append to `<data_dir>/tasks.jsonl`, one full record per change.
  Replay takes the last record per task id.
- `TaskStore` reloads that file on construction; a fresh process sees the same
  task ids, statuses, payloads, attempts and history.
- Appends are serialized with an advisory `flock` on `tasks.jsonl.lock`;
  readers take a shared lock. The lock is released on exceptions and process
  exit, so no stale-lock file can block the store.
- Malformed lines are reported in `load_errors` and skipped — never deleted,
  never treated as success.
- Audit is append-only JSONL under `<audit_dir>/events-YYYY-MM.jsonl` (0600),
  serialized with its own lock. Memory raw events live in
  `<data_dir>/memory.sqlite3` in WAL mode with a busy timeout.
- Defaults: `~/.local/share/aj/`. Tests and `--check` use temporary or in-memory
  stores and never write there.

Locking is POSIX-first (`fcntl`). On platforms without `fcntl`, locks degrade to
a no-op and that limitation is reported by the module, not hidden.

## Recovery

```bash
aj recover                # scan; replay only safely replayable tasks
aj recover --task <id>    # explicit attempt; unsafe tasks are refused and marked
```

A task may be replayed only when its capability is an internal action **and**
declares `replay_safe=True`. Recovery keeps the task id and history, appends
`task.recovery`/`task.completed` memory events and `recovery_started` audit
events, marks unsafe tasks `RECOVERY_REQUIRED` with a reason, and refuses a
second replay of a completed task. `CANCEL_REQUESTED` is never auto-replayed.

## Memory, audit and summaries

- Raw events are canonical, append-only, and have no delete API.
- Summaries are **derived**: a deterministic digest (counts, per-task last kind,
  status, capabilities, cited event ids). Rebuilding the same events produces
  identical content. `summary --verify` compares the stored row with a fresh
  rebuild; `summary --rebuild` stores a new row without touching raw events.
- Audit events are redacted before persistence; key-like fields become
  `[redacted]`.
- `summary --task <id>` computes a task-scoped digest without modifying anything.

## Configuration and diagnostics

```bash
aj config              # effective values + origin: default | file | env | override
aj config --check      # validates types, paths, writability, dangerous values
aj diagnostics         # paths, counts, malformed, last writes, locks, sources
```

`config --check` exits 5 on invalid configuration. `config` redacts key-like
values; it never prints provider credentials. Secrets in free-text fields cannot
be detected by key name, so do not put credentials in task text.

## Export, import and backup

```bash
aj export --output state.json
aj import state.json --dry-run
aj import state.json
aj backup --output backups/2026-11-10
aj backup --verify backups/2026-11-10
```

Export is deterministic JSON (sorted tasks, canonical keys) containing tasks,
audit, raw memory, summaries and metadata. Import validates format/version,
refuses task-id conflicts before writing anything, skips byte-identical memory
duplicates, appends rather than overwrites, and rebuilds summaries from imported
raw events. Backup adds a SHA-256 manifest and is written with a temporary file,
`fsync` and atomic replace. Backup files are plaintext by design; protect them
like the store itself.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | operational failure (task failed, cancel refused, verify mismatch) |
| 2 | invalid CLI usage (argparse) |
| 3 | permission denied |
| 4 | not found (task or capability) |
| 5 | configuration, storage or conflict failure |
| 6 | unsafe operation (unsafe retry, recovery required) |

JSON mode emits exactly one JSON document on stdout; human diagnostics go to
stderr. `--quiet` prints one essential line for `run`, `tasks`, `cancel` and
`retry`.

## Module map

| Path | Purpose |
|---|---|
| `aj/__main__.py` | CLI: lifecycle, inspection, transfer, diagnostics, exit codes |
| `aj/runtime.py` | assembly, logging, 23 health checks, demo |
| `aj/actions.py` | safe in-process actions, replay/retry declarations |
| `aj/orchestrator.py` | routing, policy, execution, attempts, cancel/retry, audit/memory |
| `aj/recovery.py` | conservative scan/classify/replay manager |
| `aj/summary.py` | deterministic digests, build, verify, delete |
| `aj/task.py` | lifecycle, attempts, locked append-only store |
| `aj/locking.py` | POSIX advisory locks with timeouts |
| `aj/memory.py` | canonical raw events (SQLite, WAL) + citing summaries |
| `aj/audit.py` | append-only JSONL audit, redaction, locked reader/writer |
| `aj/diagnostics.py` | read-only storage/lock/count diagnostics |
| `aj/transfer.py` | export, conservative import, backup and verification |
| `aj/config.py` | configuration merge, origins, validation, memory path |
| `tests/` | 119 tests, stdlib + pytest, no network |

## Safety limitations

- No JARVIS/HELIX/Hermes attachment; their adapters report unavailable and
  Hermes is `NOT ATTACHED`.
- No live provider call, no API key handling beyond reading an env var name.
- No Honcho or vector memory adapter; no network server, daemon, scheduler,
  queue, container or database server.
- No UI, voice, desktop/browser automation, calling, or free-form shell/Python.
- No git repository in this directory; no history is implied.
- No automatic replay or retry of external/side-effecting work.
- Cooperative cancellation only: `CANCEL_REQUESTED` is a request, not a kill.
- Import does not preserve memory event ids; it preserves content, provenance,
  timestamps and task correlation, then rebuilds summaries.

## Invariants

1. Raw memory is canonical; summaries are derived and rebuildable.
2. Tasks survive process restart; malformed records are reported, not dropped.
3. Unsafe tasks are never blindly replayed or retried; capability declarations
   are required.
4. Audit history is append-only and redacted before persistence.
5. Task, attempt, audit and memory records share task/operation ids.
6. The CLI cannot become a shell.
7. Multiple local writers serialize instead of corrupting state.
8. Everything is local and deterministic.
