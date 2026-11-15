# 00 — Baseline and Scope (Stage 5A.0)

**Project:** AJ (Agent Junction) — Phase 5A: Concurrent Task & Sub-Agent Orchestration (Architecture Audit, Design & Verification)  
**Phase type:** Audit/design/validation only. **No production implementation authorized.**  
**Date:** 2026-11-14  
**Stage result:** **COMPLETE** (acceptance criteria satisfied by evidence below)

---

## A. Repository identity (VERIFIED FACT)

| Item | Value |
|---|---|
| Actual AJ repository (absolute path) | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ` |
| Branch | `main` |
| HEAD | `468fdcebece5b25f02e53add4928d3650ef175f4` |
| `git status --short` count (captured 5A.0 baseline) | **44 entries** |
| Tracked modifications (14) | `M aj/__main__.py`, `M aj/config.py`, `M aj/diagnostics.py`, `M aj/orchestrator.py`, `M aj/recovery.py`, `M aj/runtime.py`, `M aj/task.py`, `M aj/transfer.py`, `M tests/test_foundation.py`, `M tests/test_orchestrator.py`, `M tests/test_path_config_hardening.py`, `M tests/test_phase2.py`, `M tests/test_phase3.py`, `M tests/test_step_c_gap_closure.py` |
| Untracked files/dirs (30) | `?? ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/`, `?? ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/`, `?? ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/`, `?? ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/`, `?? ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/`, `?? ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/`, `?? ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/`, `?? ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/`, `?? ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/`, `?? ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/`, `?? aj/authorization.py`, `?? aj/consistency.py`, `?? aj/hermes_adapter.py`, `?? aj/hermes_contract.py`, `?? aj/operation_evidence.py`, `?? aj/storage_diagnostics.py`, `?? integrations/`, `?? tests/test_audit_reliability_security.py`, `?? tests/test_phase3_lifecycle_reliability.py`, `?? tests/test_phase3c_recovery_integrity.py`, `?? tests/test_phase3d_recovery_observability.py`, `?? tests/test_phase3e_evidence_consistency.py`, `?? tests/test_phase3f_identity_trust_boundary.py`, `?? tests/test_phase4b1_hermes_adapter.py`, `?? tests/test_phase4b1_hermes_security_faults.py`, `?? tests/test_phase4b2_reliability_hardening.py`, `?? tests/test_phase4b3_security_assurance.py`, `?? tests/test_phase4b6_gateway_ensure_design_isolated.py`, `?? tests/test_task_creation_import_integrity.py`, `?? tests/test_task_persistence_fail_closed.py` |
| Existing audit artifacts (present, untracked) | Prior phase dirs under `AJ/ENGINEERING_AUDIT/` including MASTER_CORE_AUDIT, 3F, 4A, 4B.0–4B.6 (see list above). |
| Existing tests (inventory) | `AJ/tests/` contains 38 test modules incl. `conftest.py`, lifecycle/recovery/permissions/capability/runtime/orchestrator/foundation, scheduler-related `test_f2_scheduler_resume.py`, `test_f2_authorization_context.py`, phase 3/4b suites, inbox/orb/calling/provider suites, etc. (full listing captured via `ls tests`). |

**Preservation:** All pre-existing tracked modifications and untracked files treated as user/existing work; none modified or removed in 5A.0. No Git staging/commits/destructive operations.

---

## B. Protected project repositories (VERIFIED FACT, read-only inspection)

| Repository | Absolute path | HEAD (short) | `git status --short` (observed) | Notes |
|---|---|---|---|---|
| JARVIS | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/JARVIS` | `d93c702` | `?? chat_history/2026-11-04.md`, `?? chat_history/2026-11-05.md` | Untouched by Phase 5A |
| HELIX workspace copy | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/helix` | `99c7a38` | (clean) | Untouched |
| Other known HELIX copy (Drive) | `/run/media/abubakargcx/My Drive/hermes/helix` | `e8a64cf` | Pre-existing dirty/diverged (`M .gitignore`, `M bridge/README.md`, `M docs/PROGRESS.md`, `M docs/VOICE_AUDIO_DIAGNOSTIC.md`, `M tools/selfcheck.py`, multiple `D` bridge/deploy/tools/ui files) | Present, pre-existing state; untouched |
| Hermes source repository | `/home/abubakargcx/.hermes/hermes-agent` | `2bd378ed1b` (`2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`) | (clean, detached) | Untouched |

**Governing project context document:** `Complete-Project-context-till-now.txt` located and read (actual file) at `/home/abubakargcx/Downloads/Complete-Project-context-till-now.txt` (not present inside `AI_WORKSPACE` by name). Treated as authoritative governing context per Part 1; decisions in this phase must preserve finalized vs proposal status. (NOTE: document is long; relevant Parts 1–4+ reviewed for vision, AJ/JARVIS/HELIX/Hermes roles, GREEN SIGNAL/no-destructive rules, modular-monolith/ports-adapters/feature-flag/capability/permission/evidence constraints.)

**Latest accepted phase docs inspected (actual masters):** 4B.3 `00_PHASE_4B_3_MASTER_REPORT.md` (PARTIALLY COMPLETE; security fixes/regression 503 passed at time, SQLite root cause partially identified; readiness conditional), 4B.5 `00_PHASE_4B_5_MASTER_REPORT.md` (COMPLETE, CONDITIONAL GO, `hermes.gateway.ensure` not authorized/executed, Hermes NOT ATTACHED), 4B.6 `00_PHASE_4B_6_MASTER_REPORT.md` (COMPLETE, CONDITIONAL GO, design closure, 9 isolated tests, no lifecycle action). 4B.4 master report file `PHASE_4B_4.../00_PHASE_4B_4_MASTER_REPORT.md` **not found** at expected path during inspection (gap recorded); 4B.4 outcomes referenced from 4B.5/4B.6 summaries and prior context where needed.

---

## C. AJ source inventory (SOURCE-CODE OBSERVATION, inspected)

### C.1 Modules (actual `aj/`)
Core: `__init__.py`, `__main__.py`, `ids.py`, `errors.py`, `contracts.py`, `config.py`, `task.py`, `orchestrator.py`, `runtime.py`, `execution.py`, `scheduler.py`, `agents.py`, `actions.py`, `capability.py`, `permissions.py`, `authorization.py`, `journal.py`, `receipts.py`, `idempotency.py`, `lease.py`, `locking.py`, `recovery.py`, `operation_evidence.py`, `memory.py`, `audit.py`, `diagnostics.py`, `consistency.py`, `storage_diagnostics.py`, `invariants.py`, `providers.py`, `calling.py`, `orb*.py`, `inbox*.py`, `summary.py`, `transfer.py`, `retention.py`, `integrations/*`, `hermes_adapter.py`, `hermes_contract.py`.

### C.2 Task models & lifecycle (`aj/task.py`)
- **`TaskRecord` (dataclass):** identities/fields include `task_id`, `operation_id` (default generated), `parent_task_id`, `root_task_id`, `requester`, `owner_agent`, `capability_id`, `request_payload`, `permission_level`, `approval_required`, `status` (default `RECEIVED`), timestamps, `attempt`/`max_attempts`, `actions_taken/actions_not_taken/artifacts/evidence/errors/warnings`, `recovery`, `attempts` (list), `depends_on`, `priority`, `deadline`, `requires_user_decision`, `summary`, `events`, `authorization_context`.
- **States/constants:** `RECEIVED, UNDERSTANDING, PLANNED, WAITING_FOR_APPROVAL, AUTHORIZED, EXECUTING, VERIFYING, COMPLETED, FAILED, RECOVERING, RETRYING, ESCALATED, ABORTED, CANCELLED, RECOVERY_REQUIRED, CANCEL_REQUESTED, BLOCKED, DEAD_LETTER`. **Terminal:** `COMPLETED, ABORTED, CANCELLED, DEAD_LETTER` (`FAILED` non-terminal/recoverable path). `TRANSITIONS` map enforces allowed moves (`can_transition`, `transition`; `force` override exists in API but controlled).
- **Persistence:** `TaskStore` (thread-safe, `RLock`), append-only JSONL (`tasks.jsonl`) under `persist_dir`; deep-copied snapshots returned; `create/child_of`, `save/update` (preserve store-controlled identity/lifecycle/history fields, reject unknown IDs for normal update), `import_record` (explicit, validated, no overwrite of existing canonical history), `query`, dependency-aware usage via orchestrator/scheduler. Fail-closed on persist failure with reconciliation semantics.

### C.3 Orchestrator / control plane (`aj/orchestrator.py`)
- **`Aj.handle(...)`:** deterministic routing (`Router`: explicit capability or calling keyword -> HELIX `helix.place_call`, default -> JARVIS), task creation, idempotency claim/check, lifecycle progression (RECEIVED→UNDERSTANDING→PLANNED), dependency blocking (`unsatisfied_dependencies` → `BLOCKED`), capability lookup/permission evaluation (`Authorizer`), dispatch via internal actions/agents/execution port/calling paths, audit/journal/memory/receipt recording, bounded outcomes.
- **Other APIs (observed):** `resume`, `retry`, `cancel/cancel_task`, `recover`, `_assess_recovery`, `dispatch_of`, capability/status/introspection helpers, `recovery_inspection`, child/delegation-related structures (e.g. `child_of` in task store, request fields) — **actual concurrent multi-task execution engine not present** (see scheduler).
- **Ownership/routing:** `Route(owner_agent, capability_id, rule)`, `OWNER_AJ/JARVIS/HELIX/HERMES` in capabilities; agent delegation through `AgentRegistry`/adapters (availability-honest).

### C.4 Runtime & execution boundary (`aj/runtime.py`, `aj/execution.py`)
- **Runtime assembly:** `assemble/build`, config loading/validation, logging, memory, internal actions, registries, audit/journal/receipts/idempotency/leases wiring, `_build_execution` selects `HermesExecutionAdapter` only when feature flag + runtime `hermes_cli` + strict config enabled/capability flags satisfied, else `UnavailableExecutionAdapter` (fail-closed). `health()`/checks prove local foundation without external deps.
- **Execution port:** `ExecutionPort` protocol, `UnavailableExecutionAdapter` (inert, explicit NOT ATTACHED), `SkillRegistry` with approval/verification gating; `execute()` normalizes failures. Hermes remains boundary-gated/read-only status capability context per prior phases.

### C.5 Scheduler (`aj/scheduler.py`) — **critical 5A finding**
- Deterministic local scheduler over durable task store: selects eligible `AUTHORIZED` (and considers `BLOCKED`/deadline metadata in queue view) tasks, claims **execution lease** per task before resume, runs via `aj.resume(task_id, leased=True)`.
- `run_once(*, limit=10, workers=1)`: when `workers > 1` and multiple selected, uses `concurrent.futures.ThreadPoolExecutor` to run `_run_one` calls in-process threads; default/typical path effectively single-worker. No persistent daemon loop, no admission/resource manager, no priority queue service, no cross-process scheduler coordination, no backpressure/objective concurrency control beyond simple selection/leases, no sub-agent pool abstraction.
- **Interpretation:** basic bounded local dispatch helper exists; **not** a verified concurrent multi-task/sub-agent orchestration engine.

### C.6 Leases, idempotency, journal, receipts (`aj/lease.py`, `aj/idempotency.py`, `aj/journal.py`, `aj/receipts.py`)
- **Leases:** file-backed/in-memory; separates **operation leases** (`cancel/retry/recover`, mutation serialization, expired -> must be broken stale explicitly) and **execution leases** (`execute`, worker identity/heartbeat/expiry, ownership checks). Guarded by flock/RLock; history/audit/journal hooks.
- **Idempotency:** persistent store scoped to capability key (`IdempotencyStore.claim/lookup`), at-most-once within local store for same scope/key; orchestrator checks conflicts (same key different capability/payload rejected).
- **Journal:** append-only JSONL execution events (task/operation/attempt/worker/lease/correlation metadata). **Receipts:** durable per finished attempt records (status, times, verification/output/error refs).

### C.7 Recovery, evidence, consistency (`aj/recovery.py`, `aj/operation_evidence.py`, `aj/consistency.py`, `aj/storage_diagnostics.py`, `aj/invariants.py`)
- **Recovery:** `RecoveryManager` classifies non-terminal tasks via orchestrator assessment (`replay_safe/converged/blocked/recovery_required` mapped findings), delegates recovery to `aj.recover` (single source of truth), conservative/fail-closed on assessment errors; batch auto-recovers only replay-safe.
- **Operation evidence:** append-only privileged-operation intent/progress/outcome evidence (incomplete = intent without terminal outcome), correlation support.
- **Consistency/invariants/diagnostics:** read-only cross-store checks (task/journal/receipt/audit/op-evidence/leases), storage/SQLite diagnostics and error classification, invariant validation.

### C.8 Permissions, capabilities, agents, memory, config (`aj/permissions.py`, `aj/capability.py`, `aj/authorization.py`, `aj/agents.py`, `aj/memory.py`, `aj/config.py`)
- **Permissions:** 5-level model + forbidden, `Authorizer`/`ApprovalGate` (single-use, capability+payload-bound approvals, unattended ceiling), `PolicyDecision` allow/confirm/deny.
- **Capabilities:** `CapabilitySpec`/`CapabilityRegistry` with owner, risk, availability, verification status, replay/retry safety flags, adapter binding, executable semantics; honest verification/availability states.
- **Authorization (privileged):** local-trust/non-authenticated-by-default guardrails, explicit separation of requested operator metadata vs verified principal (only via trusted provider), fail-closed modes.
- **Agents:** `AgentPort`/`HttpAgentAdapter` (probe-only honesty, no agreed transport by default -> rejected/unavailable), `UnconfiguredAgent`, `AgentRegistry.from_config` for JARVIS/HELIX endpoints (not verified as live task transport).
- **Memory:** SQLite-backed canonical store (`MemoryStore`, WAL/busy timeout), append-only raw events + cited summaries, provider-independent; known ntfs3/WAL reliability caveat per prior investigations.
- **Config:** defaults/merge/env/overrides, known sections, feature flags (incl. `hermes_execution_adapter` false), runtime/provider/agent/inbox/permissions sections.

### C.9 CLI & integrations (`aj/__main__.py`)
- Foreground CLI (`--check`, run/capabilities/tasks/task/cancel/retry/audit/memory/summary/config/diagnostics/export/import/backup/recover/orb/inbox), local/no daemon by design; `run` limited to registered internal actions.

---

## D. Existing capability matrix (VERIFIED FACT / SOURCE-CODE OBSERVATION; classification per 5A.0)

| Capability / area | Classification | Evidence (paths/symbols) | Notes / limitations |
|---|---|---|---|
| Task domain model & lifecycle transitions | **Implemented but not adequately verified** (for future multi-task/sub-agent semantics) | `aj/task.py` (`TaskRecord`, `TRANSITIONS`, `TaskStore`, ids/parent/root/deps/attempts/events fields) | Rich single-task lifecycle exists; `operation_id` generated per task record, `attempts` list present but full operation-vs-attempt separation for concurrent sub-agents not yet modeled/verified as required by 5A. |
| Deterministic routing & request handling | **Implemented but not adequately verified** | `aj/orchestrator.py` (`Router`, `Aj.handle`, `Route`, `TaskOutcome`) | Deterministic rules; agent/exec paths constrained by availability/authz. |
| Capability registry & honest availability/verification metadata | **Implemented and tested** (core) | `aj/capability.py`; runtime/health checks; registry usage throughout | Registry present; live environment attachment still limited. |
| Permission model & approval gate | **Implemented and tested** (core) | `aj/permissions.py` (`Authorizer`, `ApprovalGate`, levels/fingerprints) | Strong local model; `local_trust` not authentication (see authz). |
| Internal actions execution (local) | **Implemented and tested** | `aj/actions.py` (`InternalActions`, `echo`, `health_check`), `aj/runtime.py` checks, CLI `run` | Safe/no side-effect local path. |
| Execution port abstraction & unavailable runtime boundary | **Implemented and tested** | `aj/execution.py` (`ExecutionPort`, `UnavailableExecutionAdapter`, `SkillRegistry`) | Honest unattached default. |
| Hermes read-only status adapter boundary (`hermes.status.read`) | **Implemented but not adequately verified** (integration remains disabled/unattached) | `aj/hermes_adapter.py`, `aj/hermes_contract.py`, `aj/runtime.py::_build_execution`, phase 4B.1–4B.3 tests/docs | **Only implemented AJ↔Hermes capability**; default-disabled, fail-closed, fixed argv/no-shell; `aj --check` reports Hermes NOT ATTACHED. |
| `hermes.gateway.ensure` | **Missing / not authorized** (design-only) | 4B.5/4B.6 docs, `tests/test_phase4b6_gateway_ensure_design_isolated.py` (mock design evidence) | No production implementation; lifecycle actions prohibited. |
| Agent adapters & registry (JARVIS/HELIX) | **Partially implemented / interface-honest** | `aj/agents.py` (`AgentPort`, `HttpAgentAdapter` probe-only, `UnconfiguredAgent`, `AgentRegistry.from_config`) | Reachability probe exists but **no agreed task transport** configured/verified; execution returns rejected/unavailable honestly. Not a working delegation integration. |
| Local scheduler (queue + leased resume) | **Partially implemented** | `aj/scheduler.py` (`Scheduler.queue`, `_run_one`, `run_once` with optional `ThreadPoolExecutor`), `tests/test_f2_scheduler_resume.py` | Basic authorized-task dispatch helper; **not** admission control, not resource-aware, no persistent service, no dependency-aware execution graph engine, no multi-agent orchestration. |
| Concurrency controls (leases/locks/idempotency) | **Implemented but not adequately verified** (for high-concurrency orchestration) | `aj/lease.py` (op vs execution leases, heartbeat/ownership), `aj/locking.py`, `aj/idempotency.py`, `aj/task.py` RLock | Foundations exist; scheduler can use threads when `workers>1`, but end-to-end concurrent orchestration safety unproven. |
| Recovery & restart assessment | **Implemented but not adequately verified** | `aj/recovery.py`, `aj/orchestrator.py` recovery/assessment paths, `aj/operation_evidence.py`, phase tests | Conservative/fail-closed design; complex concurrent/interrupted multi-execution recovery not yet designed/verified. |
| Journal, receipts, audit, evidence | **Implemented and tested** (substantial) | `aj/journal.py`, `aj/receipts.py`, `aj/audit.py`, `aj/operation_evidence.py`, diagnostics/consistency | Append-only evidence primitives present; coverage varies by scenario. |
| Memory (canonical SQLite store) | **Implemented but not adequately verified** (storage-reliability caveat) | `aj/memory.py`, `aj/storage_diagnostics.py`, 4B.3/4B.5 findings | WAL/concurrency on ntfs3-backed paths shows intermittent I/O issues (known, unresolved). |
| Diagnostics, invariants, consistency checks | **Implemented and tested/read-only** | `aj/diagnostics.py`, `aj/invariants.py`, `aj/consistency.py`, CLI commands | Operator visibility primitives exist. |
| Providers/calling/orb/inbox subsystems | **Partially implemented / mixed** | `aj/providers.py`, `aj/calling.py`, `aj/orb*.py`, `aj/inbox*.py`, related tests | Present in tree/tests; not core focus of 5A orchestration except as future execution/resource contexts. |
| Persistent background workers / multi-agent manager / concurrent orchestration engine | **Missing** | (no dedicated manager/worker-pool/admission/resource subsystems found beyond basic scheduler helper) | Required target for Phase 5A design; must not be assumed to exist. |

---

## E. Existing concurrency-related code (VERIFIED FACT / SOURCE-CODE OBSERVATION)
- `aj/scheduler.py`: `ThreadPoolExecutor` for `run_once(workers>1)` over selected leased task resumes.
- `aj/task.py`: `threading.RLock`, deep-copy snapshots, append-only persistence with locking.
- `aj/lease.py`: per-task flock/RLock guards, operation vs execution leases, TTL/heartbeat semantics.
- `aj/memory.py`: `threading.RLock`, SQLite WAL + busy timeout.
- `aj/permissions.py`, `aj/orb.py`, `aj/orb_web.py`: threading/queues/events for UI/capture workers (non-orchestration subsystems).
- Tests: `tests/test_f2_scheduler_resume.py`, `tests/test_f2_authorization_context.py`, `tests/test_phase3.py` (concurrent memory writers, known intermittent NTFS issue), other concurrency/resilience suites.
- **Not found as implemented orchestration capability:** distributed scheduler, durable queue service, worker supervisor/registry for sub-agents, admission controller, resource manager/backpressure engine, DAG/dependency execution engine with concurrent dispatch semantics beyond current blocking/queue metadata.

---

## F. Runtime/baseline observations (RUNTIME OBSERVATION)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` (from `AJ/`, 2026-11-14): **exit 0, `ok:true`, 23/23 checks, `failures:[]`, `attached:{jarvis:false, helix:false, hermes:"NOT ATTACHED"}`**.
- Hermes integration flags remain disabled by configuration/design (default `feature_flags.hermes_execution_adapter=false`, runtime not attached); `hermes.gateway.ensure` not implemented/authorized.
- Known reliability issue (not re-run in 5A.0): `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` intermittently fails on NTFS-backed workspace with SQLite `disk I/O error` (4B.3/4B.5 evidence). No storage/mount/config changes made.

---

## G. Stage 5A.0 acceptance criteria check
1. Actual repository identity verified: **YES** (path/branch/HEAD).  
2. Baseline Git status captured: **YES** (44 entries, tracked/untracked enumerated).  
3. Existing task and execution architecture mapped: **YES** (task/orchestrator/runtime/execution/scheduler/agents/leases/journal/receipts/recovery/memory).  
4. Existing concurrency-related code identified: **YES**.  
5. Protected repositories identified: **YES** (JARVIS, helix workspace, helix Drive copy, Hermes source).  
6. Existing functionality and limitations documented: **YES** (matrix + findings).  
7. No project modifications have occurred: **YES** (only creation of Phase 5A audit docs under `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/`).

**Gaps recorded (do not block 5A.0 evidence capture, but noted):** `Complete-Project-context-till-now.txt` absent from workspace (found/read from Downloads path); 4B.4 master report file missing at expected path. These are documentation-location gaps, not evidence that 5A.0 baseline mapping is unperformed.

**Stage 5A.0 status:** **COMPLETE — proceed to Stage 5A.1 only after this document is treated as verified baseline for subsequent stages.**
