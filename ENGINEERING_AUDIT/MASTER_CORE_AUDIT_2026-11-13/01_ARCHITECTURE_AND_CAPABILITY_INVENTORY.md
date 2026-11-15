# 01 — Architecture and Capability Inventory

## 1. Repository/module map (AJ backend scope)
| Area | Modules | Responsibility / notes |
|---|---|---|
| Control plane/orchestration | `orchestrator.py`, `runtime.py`, `__main__.py`, `__init__.py` | Request handling, deterministic routing, execution/retry/recovery/reconciliation, assembly/health/demo, CLI. |
| Task lifecycle & persistence | `task.py`, `ids.py`, `locking.py`, `invariants.py` | Append-only TaskStore, lifecycle transitions/history, snapshots/mutation boundaries, import/restore separation, file locks, invariant checks. |
| Evidence stores | `audit.py`, `journal.py`, `receipts.py`, `lease.py`, `operation_evidence.py`, `idempotency.py` | Append-only audit/journal/receipts, operation/execution leases, privileged reconciliation operation evidence, idempotency keys. |
| Recovery/consistency | `recovery.py`, `consistency.py` | Evidence-based recovery scan/assessment integration, read-only cross-store consistency/incomplete-operation checking. |
| Security/authorization/permissions | `permissions.py`, `authorization.py` | 5-level permission/approval model, fail-closed privileged reconciliation authorization guardrail (local-trust default, extensible). |
| Capability/agent/execution/contracts | `capability.py`, `agents.py`, `execution.py`, `contracts.py`, `actions.py`, `integrations/*` | Capability registry/specs, agent adapters/registry, execution port (unavailable by default), request/result/skill contracts, internal safe actions, JARVIS registry/GSConnect integrations. |
| Providers | `providers.py` | Provider adapter/gateway abstraction, health/cooldown/retry/fallback; no live transport by default. |
| Calling | `calling.py` | Calling state machine/service/ports and policy enforcement; telephony bridge control unverified/unavailable in this environment. |
| Memory/summaries | `memory.py`, `summary.py` | Canonical SQLite raw events (append-only), deterministic derived summaries/verification. |
| Scheduling/retention | `scheduler.py`, `retention.py` | Deterministic local scheduler queue/run helpers and read-only retention assessment (limited integration). |
| Diagnostics/config/transfer | `config.py`, `diagnostics.py`, `storage_diagnostics.py`, `transfer.py`, `errors.py` | Layered config/validation, diagnostics, SQLite/storage diagnostics & error classification, export/import/backup/verify, normalized errors. |
| Knowledge inbox subsystem | `inbox.py`, `inbox_cli.py`, `inbox_view.py` | Local capture-first inbox (SQLite index, originals/extracted artifacts, processing/retry/archive, CLI, localhost inspection UI). Significant subsystem; partly independent of core control-plane execution. |
| Orb/UI | `orb.py`, `orb_web.py`, `orb_autostart.py`, `orb_ui/` | Desktop/web capture orb and autostart helpers (GTK/WebKit/runtime-dependent). |
| Scripts/integrations assets | `scripts/*`, `integrations/*service` | Nautilus send-to-AJ helper, systemd user service template (untracked/preserved). |

## 2. Storage and evidence model (actual)
- **TaskStore:** append-only `tasks.jsonl` (enveloped records), controlled mutations/transitions, deep-copy snapshots, explicit validated import, fail-closed persistence reconciliation.
- **Audit:** append-only monthly JSONL in audit dir, redaction, file locks.
- **Journal:** append-only `journal.jsonl` (execution/recovery/operator events).
- **Receipts:** append-only `receipts.jsonl`.
- **Leases:** file-backed lease records/history in `leases/` (process-local discipline).
- **Operation evidence (3E):** append-only `reconciliation_operations.jsonl` (intent/progress/outcome, incomplete detection).
- **Idempotency:** `idempotency.json` (local claim/lookup).
- **Memory:** SQLite (`memory.sqlite3`, WAL) raw events + summaries tables (derived, rebuildable).
- **Inbox:** separate SQLite index and artifact directories under resolved inbox root.
- **Consistency:** not a single transactional store; multi-store writes are non-atomic but increasingly detectable/honest.

## 3. Execution/routing model (actual)
- Deterministic routing (`Router`) with explicit capability override and default ownership rules.
- Internal safe actions (`aj.echo`, `aj.health_check`) executable in-process.
- Non-internal/external capabilities depend on registered adapter/owner availability and verification evidence; many remain unavailable/unknown/unverified.
- Hermes execution port boundary implemented but **NOT ATTACHED** (`UnavailableExecutionAdapter`).
- Agent delegation adapters probe reachability but lack agreed live AJ task transport by default (reachable != task-executable).
- Provider gateway requires usable adapter+credential+transport; default foundation wires no transport (no live completions).
- Calling service enforces state machine/policy/ambiguity refusal; device telephony control unverified/unavailable.

## 4. Component interaction observations
- Orchestrator coordinates task state, policy, leases, journal, receipts, audit, memory, idempotency, recovery, reconciliation, and 3E operation evidence/authorization.
- Consistency checker and diagnostics/invariants provide read-only observability across stores.
- Scheduler and retention modules exist as local helpers but are not primary CLI-integrated control surfaces in current runtime.
- Inbox/orb are capture/UX subsystems with their own storage flows; integration with core control-plane task semantics is limited/indirect.
- Cross-component correctness relies on append-only evidence, locks, fail-closed checks, and explicit preconditions rather than distributed transactions.
