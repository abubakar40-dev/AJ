# 01 — Existing AJ Capability Inventory (Stage 5A.0)

**Scope:** AJ repository as inspected at `main@468fdcebece5b25f02e53add4928d3650ef175f4` (2026-11-14). Classifications follow required labels: *Fully implemented and tested; Implemented but not adequately verified; Partially implemented; Interface only; Mock/test only; Missing; Deprecated or unused; Unknown.*

**Evidence types:** VERIFIED FACT (repo/git/check output), SOURCE-CODE OBSERVATION (paths/symbols), TEST EVIDENCE (test file presence/execution context noted), RUNTIME OBSERVATION (`aj --check`).

---

## 1. Domain, lifecycle, and identity primitives

| Capability | Classification | Evidence | Limitations / notes |
|---|---|---|---|
| Task record model (`TaskRecord`) with goal/request/owner/capability/payload/priority/deadline/deps/root/parent/attempt counters/history/evidence fields | **Implemented but not adequately verified** | `aj/task.py`: dataclass fields incl. `task_id`, `operation_id` (default `ids.new_task_id("op")`), `parent_task_id`, `root_task_id`, `requester`, `owner_agent`, `capability_id`, `request_payload`, `status`, `attempt`, `max_attempts`, `attempts`, `depends_on`, `priority`, `deadline`, `events`, `authorization_context`, etc.; `to_dict/from_dict` | Semantics for concurrent sub-agent execution (distinct operation/attempt ownership per parallel execution, subtask aggregation) not fully designed/verified for 5A target. |
| Task state machine & transition enforcement | **Implemented and tested** (core paths) | `aj/task.py`: `TRANSITIONS`, `TERMINAL`, `can_transition`, `transition`, terminal guards; states incl. `RECEIVED/UNDERSTANDING/PLANNED/WAITING_FOR_APPROVAL/AUTHORIZED/EXECUTING/VERIFYING/COMPLETED/FAILED/RECOVERING/RETRYING/ESCALATED/ABORTED/CANCELLED/RECOVERY_REQUIRED/CANCEL_REQUESTED/BLOCKED/DEAD_LETTER`; tests across lifecycle suites (`test_foundation.py`, `test_orchestrator.py`, phase tests) | Designed for single-task progression/recovery semantics; concurrent multi-execution state ownership needs explicit extension (Stage 5A.1). |
| Task persistence store (append-only JSONL, thread-safe snapshots) | **Implemented but not adequately verified** | `aj/task.py`: `TaskStore` (`RLock`, `_tasks`, deep-copy `_snapshot`, `create/child_of/save/update/query/import_record`, append-only persistence, fail-closed reconciliation hooks) | Durability/consistency under NTFS/WAL-adjacent conditions and multi-process concurrent orchestration not proven; `import_record`/update contracts must be preserved. |
| Operation/attempt identifiers on tasks/receipts/journal | **Partially implemented** | `aj/task.py` (`operation_id`, `attempt`, `attempts`), `aj/receipts.py` (`operation_id`, `attempt_id`), `aj/journal.py` (`operation_id`, `attempt_id`, `worker_id`, `lease_id`, `correlation_id`), `aj/ids.py` | Present but model conflates/under-specifies independent concurrent operations/attempts per task; no verified sub-agent execution graph. |
| Dependency metadata (`depends_on`) and blocking | **Partially implemented** | `aj/task.py` field + transitions allow `BLOCKED`; `aj/orchestrator.py` checks `unsatisfied_dependencies` in `handle/resume` paths and sets `BLOCKED`; `aj/scheduler.py` queue annotates waiting deps | Dependency resolution/satisfaction semantics exist in parts but no full DAG scheduler/admission engine or concurrent unblocking workflow verified. |

## 2. Control plane, routing, and dispatch

| Capability | Classification | Evidence | Limitations / notes |
|---|---|---|---|
| Deterministic request routing | **Implemented and tested** | `aj/orchestrator.py`: `Router.route` (explicit capability -> registry/owner, calling keyword `CALLING_PATTERN` -> `HELIX/helix.place_call`, default -> `JARVIS`), `Route` | Rule-based only; no intent classifier. |
| Orchestrated task handling (`Aj.handle`) with idempotency, authz, audit/journal/memory | **Implemented but not adequately verified** | `aj/orchestrator.py`: `Aj.handle` (idempotency conflict checks, task create/transition, dependency block, permission/approval flow, dispatch, outcome), integration with `AuditLog`, `Journal`, `ReceiptStore`, `MemoryStore`, `LeaseManager` | Correctness under concurrent submissions/executions and multi-agent delegation unverified. |
| Resume/retry/cancel/recover control APIs | **Implemented but not adequately verified** | `aj/orchestrator.py`: `resume`, `retry`/recovery paths, `cancel`, `recover`, `_assess_recovery`; `aj/__main__.py` CLI commands; `tests/test_f2_scheduler_resume.py` | Authorization/lease/evidence rules exist; concurrency/race behavior beyond covered cases not fully proven. |
| CLI foreground control surface | **Implemented and tested** (scope-limited) | `aj/__main__.py`, runtime/health commands, `--check` exit 0 / 23 checks (RUNTIME OBSERVATION) | Local/foreground, no daemon; `run` limited to registered internal actions. |

## 3. Execution, capabilities, and adapters

| Capability | Classification | Evidence | Limitations / notes |
|---|---|---|---|
| Execution port abstraction & honest unavailable runtime | **Implemented and tested** | `aj/execution.py`: `ExecutionPort`, `UnavailableExecutionAdapter`, `SkillRegistry`, `execute`; `aj/runtime.py::_check_execution` | Default no runtime attached. |
| Internal (in-process) capabilities/actions | **Implemented and tested** | `aj/actions.py`: `InternalActions`, `echo`, `health_check`, specs `aj.echo`, `aj.health_check`; capability registration in runtime/registry paths | Safe, local-only, no external side effects. |
| Capability registry (ownership/risk/availability/verification/replay-retry flags) | **Implemented and tested** | `aj/capability.py`: `CapabilitySpec`, `CapabilityRegistry`, load/register/query/summary; `aj/runtime.py` checks | Metadata integrity strong; live adapter availability often unavailable/unattached. |
| Hermes execution adapter — `hermes.status.read` (read-only CLI subprocess) | **Implemented but not adequately verified** (disabled/unattached) | `aj/hermes_adapter.py`, `aj/hermes_contract.py` (`aj.hermes.execution.v0`), `aj/runtime.py::_build_execution` (strict, fail-closed, feature/config gated), `tests/test_phase4b1_*`, `test_phase4b2_*`, `test_phase4b3_security_assurance.py`, 4B.3–4B.6 docs | Only implemented AJ↔Hermes capability; fixed argv/no-shell, bounded I/O, redaction, `local_trust` non-auth, default-disabled; `aj --check` reports Hermes NOT ATTACHED. |
| Hermes lifecycle capability `hermes.gateway.ensure` | **Missing** (production) / **Mock/test only** (design evidence) | `tests/test_phase4b6_gateway_ensure_design_isolated.py`, 4B.5/4B.6 audit docs | Explicitly NOT implemented/authorized; any use would be lifecycle-mutating and out of scope. |
| Agent ports/adapters for JARVIS & HELIX | **Interface only / partially implemented (honest stubbed transport)** | `aj/agents.py`: `AgentPort`, `HttpAgentAdapter` (TCP probe, injected transport required, rejects when no agreed task transport), `UnconfiguredAgent`, `AgentRegistry.from_config` | No verified AJ task endpoint/protocol; reachable!=accepted; not a working delegation integration. |
| Provider/calling/orb/inbox execution contexts | **Partially implemented** | `aj/providers.py`, `aj/calling.py`, `aj/orb*.py`, `aj/inbox*.py`, related tests | Present but peripheral/mixed maturity; not an orchestration engine. |

## 4. Scheduling, concurrency, and coordination

| Capability | Classification | Evidence | Limitations / notes |
|---|---|---|---|
| Local deterministic scheduler (queue + leased `run_once`) | **Partially implemented** | `aj/scheduler.py`: `Scheduler.queue` (AUTHORIZED/BLOCKED view, deadline/dep annotation, priority sort), `_run_one` (acquire execution lease, deadline dead-letter check, `aj.resume(..., leased=True)`), `run_once(limit, workers)` uses `ThreadPoolExecutor` when `workers>1`; `tests/test_f2_scheduler_resume.py` | No daemon/continuous loop, no admission control, no resource-aware scheduling, no backpressure/fairness guarantees, no distributed/cross-process coordination, no sub-agent orchestration. |
| Operation/execution lease management | **Implemented but not adequately verified** | `aj/lease.py`: `LeaseManager` (file-backed + flock / in-memory RLock), operation leases (`cancel/retry/recover`), execution leases (`execute`, heartbeat/renew/release), expiry/ownership/stale-break semantics, history hooks | Solid primitives; correctness under high parallelism/multi-process and complex recovery races not fully verified. |
| Idempotency (local, capability-scoped) | **Implemented but not adequately verified** | `aj/idempotency.py`: `IdempotencyStore`; `aj/orchestrator.py` conflict detection/replay in `handle` | At-most-once within local store only; no external exactly-once. |
| Thread-safety primitives in stores/runtime components | **Partially implemented** | `aj/task.py` (`RLock`), `aj/memory.py` (`RLock`, SQLite WAL), `aj/lease.py`, orb/inbox threading/queues | Not equivalent to a verified concurrent orchestration architecture. |
| Worker pool / agent pool / sub-agent manager / admission controller / resource manager | **Missing** | Repository-wide inspection: no dedicated orchestration manager modules beyond `Scheduler` helper; `agents.py` is adapter registry, not active worker pool | Core gap for Phase 5A target. |
| Concurrent multi-task execution engine with independent managed sub-agents | **Missing** | Absence of dispatcher/supervisor/graph-execution components; scheduler limited to optional in-process threads over `resume` | Must be designed (not assumed) in 5A. |

## 5. Recovery, evidence, observability, and storage

| Capability | Classification | Evidence | Limitations / notes |
|---|---|---|---|
| Recovery classification and controlled recovery | **Implemented but not adequately verified** | `aj/recovery.py` (`RecoveryManager`, `classify/_map_assessment`), `aj/orchestrator.py` (`_assess_recovery`, `recover`, `recovery_inspection`) | Conservative/fail-closed intent; concurrent/interrupted multi-execution scenarios need design/verification. |
| Privileged operation evidence (intent/progress/outcome) | **Implemented but not adequately verified** | `aj/operation_evidence.py` (`OperationEvidenceStore`, append-only, incomplete detection) | Used for reconciliation/privileged flows; broader orchestration coverage TBD. |
| Journal & receipts (durable attempt/execution evidence) | **Implemented and tested** | `aj/journal.py`, `aj/receipts.py`, runtime/orchestrator wiring, diagnostics counts | Append-only; schema/correlation adequate for current scope, extension likely for sub-agents. |
| Audit logging & readback | **Implemented and tested** | `aj/audit.py` (sinks/read events/redaction patterns in use), CLI `audit`, diagnostics | Must remain redaction-safe under new orchestration events. |
| Read-only consistency/invariant/storage diagnostics | **Implemented and tested** (read-only) | `aj/consistency.py`, `aj/invariants.py`, `aj/storage_diagnostics.py`, `aj/diagnostics.py`, `aj --check` (23/23) | Diagnostic, not self-healing; storage issues surfaced not auto-fixed. |
| Canonical memory store (raw events + cited summaries) | **Implemented but not adequately verified** | `aj/memory.py` (`MemoryStore`, SQLite WAL, append-only events/summaries/search/verify), `aj/runtime.py` checks | **Known reliability caveat:** intermittent `sqlite3.OperationalError: disk I/O error` on NTFS-backed workspace in concurrent writer test (`tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`, 4B.3/4B.5 evidence). |

## 6. Security, authorization, and configuration

| Capability | Classification | Evidence | Limitations / notes |
|---|---|---|---|
| Permission/approval enforcement | **Implemented and tested** | `aj/permissions.py` (levels 0–4, forbidden, `Authorizer`, `ApprovalGate`, payload-bound single-use tokens) | Correct delegation/child-permission inheritance for future sub-agents not yet defined. |
| Privileged operation authorization guardrails | **Implemented but not adequately verified** | `aj/authorization.py` (`LocalTrustPrivilegedAuthorizer`, provenance separation requested vs authenticated principal, fail-closed modes) | `local_trust` is **not** authenticated identity; no verified identity provider in default path. |
| Centralized config, feature flags, fail-closed validation | **Implemented and tested** | `aj/config.py` (defaults/merge/env/overrides, `require_path`, validation, `feature_flags.hermes_execution_adapter` default false), `aj/runtime.py` | Hermes/experimental integrations remain gated. |

## 7. External integration status (ecosystem boundaries)

| Capability | Classification | Evidence | Limitations / notes |
|---|---|---|---|
| JARVIS integration as live delegated executor | **Missing** (verified working integration) | `aj/agents.py` adapter honest/unconfigured transport; JARVIS repo present separately (`d93c702`) | Identity preserved; AJ must not modify JARVIS. |
| HELIX integration as live delegated executor | **Missing** (verified working integration) | Same as above; HELIX copies present | Identity preserved; AJ must not modify HELIX. |
| Hermes runtime as attached execution provider | **Missing/Not attached** | `aj/runtime.py` default unavailable; `aj --check` `hermes:"NOT ATTACHED"`; 4B.6 status | Read-only status adapter implemented-but-disabled; lifecycle ensure unauthorized. |

## 8. Summary gaps relevant to Phase 5A
- **Missing:** concurrent multi-task/sub-agent orchestration engine (admission, resource-aware scheduling, worker/agent manager, supervised parallel executions, dependency/DAG progression under concurrency, stuck/orphan supervision at orchestration scale).
- **Partially implemented:** scheduler, dependencies, agent adapters, operation/attempt modeling for parallelism.
- **Constraints to carry forward:** 8 GB / 2C4T host, NTFS+SQLite WAL reliability caveat (no storage changes), Hermes NOT ATTACHED & `gateway.ensure` unauthorized, JARVIS/HELIX/Hermes identities and repos untouched, no unbounded concurrency.
