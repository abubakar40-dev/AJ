# 02 — Requirements Coverage and Capability Matrix

## 1. Approved/intended core requirements coverage (evidence-based)
| Requirement area | Coverage status | Evidence | Notes |
|---|---|---|---|
| Local control plane, deterministic routing, no accidental network/daemon behavior | **Implemented & verified (core)** | `README`, `docs/01`, `aj/runtime.py`, `aj/__main__.py`, `aj/orchestrator.py`, `aj.providers.py`, health checks, CLI behavior | No live provider transport by default; execution port not attached. |
| Task lifecycle, accountability, attempt/history lineage | **Implemented & substantially verified** | `aj/task.py`, `aj/orchestrator.py`, `tests/test_phase2.py`, `test_phase3*`, crash/recovery suites | Terminal/fail-closed semantics enforced; legacy `ABANDONED` compatibility preserved. |
| Persistence, restart visibility, conservative malformed handling | **Implemented & verified** | TaskStore append-only JSONL, reload/lock behavior, `tests/test_task_persistence_fail_closed.py`, `test_phase3.py`, diagnostics | Malformed records reported/skipped, not deleted. |
| Permissions/approval boundaries (5-level model) | **Implemented & verified** | `aj/permissions.py`, orchestrator authorization paths, runtime/CLI tests | Ecosystem-level gate; not a substitute for external authenticated operator identity. |
| Auditability and redaction | **Implemented & substantially verified** | `aj/audit.py`, `tests/test_audit_reliability_security.py`, 3D/3E tests | Append-only, redacted; multi-store atomicity not guaranteed. |
| Canonical memory + derived summaries | **Implemented & verified** | `aj/memory.py`, `aj/summary.py`, memory/summary tests, health checks | Append-only raw events; summaries rebuildable/deterministic. |
| Evidence-based recovery, no blind replay, fail-closed ambiguity | **Implemented & verified** | `aj/orchestrator.py`, `aj/recovery.py`, 3C/3D/3E suites, crash/idempotency tests | Bounded, convergent, ownership-safe in process-local model. |
| Read-only inspection and explicit operator reconciliation | **Implemented & verified** | `recovery_inspection`/`inspect`, `reconcile`, CLI, 3D/3E tests | Incomplete evidence and conflicts surfaced honestly. |
| 3E operation evidence, consistency checking, authz guardrail, storage diagnostics | **Implemented & verified** | `aj/operation_evidence.py`, `aj/authorization.py`, `aj/consistency.py`, `aj/storage_diagnostics.py`, CLI/runtime integration, `tests/test_phase3e_evidence_consistency.py` | Fail-closed, read-only checks, no fabricated success/repair. |
| Idempotency/concurrency (local) | **Implemented & partially verified** | `aj/idempotency.py`, locks/leases, concurrency tests, stress checks | Process-local/file-lock discipline; external-fs SQLite WAL sensitivity observed. |
| Transfer/backup/restore diagnostics | **Implemented & verified** | `aj/transfer.py`, diagnostics/config validation, phase3/runtime/CLI tests | Conservative import/export/backup verification. |
| Provider abstraction with fallback/health controls | **Partially implemented & partially verified** | `aj/providers.py`, provider tests | No live transport/real credentials/model verification in this cycle; placeholder/default catalog behavior. |
| Agent/execution/calling contracts and boundaries | **Partially implemented & partially verified** | `aj/agents.py`, `aj/execution.py`, `aj/contracts.py`, `aj/calling.py`, capability declarations | Hermes NOT ATTACHED; agent task endpoints/telephony control unverified/unavailable. |
| Scheduling/background execution/resumption workflows | **Partially implemented & partially verified** | `aj/scheduler.py`, `Aj.resume`, scheduler-related tests | Helper exists; not fully integrated as primary CLI/runtime control surface. |
| Retention/archival workflow | **Partially implemented & partially verified** | `aj/retention.py` (read-only assessment) | No destructive archival/compaction automation (intentional). |
| Knowledge inbox capture/processing subsystem | **Implemented & partially verified** | `aj/inbox.py`, `aj/inbox_cli.py`, `aj/inbox_view.py`, inbox tests | Substantial local subsystem; extractor/platform coverage and operational guarantees vary by dependency/environment. |
| Orb/desktop capture UI | **Partially implemented & partially verified (environment-dependent)** | `aj/orb.py`, `aj/orb_web.py`, `aj/orb_autostart.py`, docs | Depends on GTK/WebKit/system runtime; not core headless backend correctness path. |

## 2. Backend capability matrix (classification)
| Capability | Classification | Evidence | Key gaps/notes |
|---|---|---|---|
| Core architecture & module boundaries | **Implemented & verified** | module layout, contracts, runtime assembly, health | Boundaries documented; not all external adapters wired. |
| Task lifecycle & orchestration | **Implemented & verified** | orchestrator/task/CLI/tests (194 preflight subset, full 424) | Complex cross-store windows remain non-atomic. |
| Scheduling & background execution | **Partially implemented** | `scheduler.py`, `resume`, limited tests/usage | Not a fully integrated/operated scheduler service/CLI workflow. |
| Persistence & database integrity | **Implemented & substantially verified** | TaskStore/inbox/memory implementations, fail-closed/reload tests | Multi-store integrity is detectable, not transactional; inbox/memory DBs have separate semantics. |
| Crash recovery & resumability | **Implemented & substantially verified** | recovery engine, leases, crash/idempotency/scheduler-resume tests, 3E incomplete-op detection | Process-local; external side effects not exactly-once; environment-dependent SQLite edge. |
| Error detection, diagnosis & remediation | **Implemented & substantially verified** | normalized errors, fail-closed paths, diagnostics/storage/consistency checks | No automatic unsafe repair; remediation mostly operator-guided. |
| Memory capture, retrieval & continuity | **Implemented & verified** | `memory.py`, `summary.py`, memory tests, health | Retrieval is simple (SQLite/LIKE semantics in implementation), not semantic/vector. |
| Audit trails & event journals | **Implemented & substantially verified** | audit/journal/receipts/operation evidence stores, correlation/consistency checks | No cross-file atomic commit. |
| Permissions, authorization & security | **Implemented & substantially verified** | permissions model, approvals, 3E privileged guardrail, redaction, tests | No authenticated operator identity; local trust assumptions documented. |
| Provider registry, adapters, routing & fallback | **Partially implemented** | `providers.py`, provider tests, config | Live provider operation unverified here (no transport/credentials exercised). |
| API quotas, rate limits, retries & budget controls | **Partially implemented** | provider health/cooldown/retry, task retry budgets/attempts | Real quota/rate-limit behavior not validated against live APIs. |
| Capability & plugin registry | **Implemented & substantially verified** | capability registry/integrations/config declarations, CLI/runtime checks | Many declared capabilities unavailable/unverified by environment/integration state. |
| Connector integrations | **Partially implemented / blocked by external dependency** | GSConnect/jarvis registry/inbox extractors/orb integrations | Telephony control, live JARVIS/HELIX task endpoints, Hermes runtime not attached/verified. |
| Monitoring, health checks & diagnostics | **Implemented & verified** | `diagnostics.py`, `storage_diagnostics.py`, `--check`, `diagnostics`, `consistency` CLI | Observability strong for local stores; no centralized/remote monitoring. |
| Configuration & environment handling | **Implemented & verified** | `config.py`, validation, path hardening, CLI config checks | Some advanced schema/versioning evolution concerns remain low/medium backlog. |
| Logging & observability | **Implemented & partially verified** | audit/journal/CLI diagnostics/runtime logging paths | Human/operator observability improved; not a full telemetry stack. |
| Backup, restore & data retention | **Partially implemented** | `transfer.py` backup/export/import/verify, `retention.py` assessment | Retention is assessment-only; no automated safe archival lifecycle. |
| Idempotency & concurrency | **Implemented & substantially verified (local)** | idempotency stores/keys, locks, leases, concurrency/stress tests | Distributed/idempotent external side-effect guarantees out of scope/not claimed. |
| CLI & runtime integration | **Implemented & verified** | `__main__.py`, runtime assembly, CLI smokes, 424 tests | Some modules/features (scheduler/retention) lack first-class CLI workflows. |
| External integration contracts | **Partially implemented / blocked** | contracts, ports/adapters, docs | Actual runtime/protocol verification pending external components/owner decisions. |
| Dependency management & portability | **Implemented & partially verified** | stdlib-first, pyproject, POSIX flock behavior, env isolation | POSIX-first assumptions; GUI deps optional/environment-specific. |
| Test architecture & regression coverage | **Implemented & substantially verified** | 35+ test files, 424 tests, crash/concurrency/recovery/3E suites | Not proof of total correctness; external/live integration coverage limited by design. |

## 3. Capability status legend (requested)
| Status | Meaning in this audit |
|---|---|
| Implemented & verified | Present, exercised by code inspection and passing tests/runtime checks in scope. |
| Implemented but partially verified | Present and exercised, but important conditions/environments/integrations not fully proven. |
| Partially implemented | Core scaffolding/helper exists, but incomplete integration/workflow/coverage. |
| Missing | Not found as an implemented capability for approved core scope. |
| Broken | Reproducible defect in current scope. (None confirmed open in core after fixes.) |
| Not required yet | Intentionally deferred (e.g. Hermes attachment, live external integrations). |
| Blocked by external dependency | Requires external runtime/service/device/credential/protocol not available or not authorized. |
