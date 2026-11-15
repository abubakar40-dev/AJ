# 10 — Sub-Agent & Execution Orchestration Audit (Stage 5A.3)

**Status:** Source-backed audit of **current** AJ implementation (not proposed design). Stage 5A.3 is audit/design/verification only.  
**Baseline:** `main@468fdcebece5b25f02e53add4928d3650ef175f4`, 45 pre-existing git status entries preserved (14 tracked M, 31 untracked incl. prior phase/5A artifacts and 5A.0–5A.2 docs). 5A.0–5A.2 docs (`00`–`09`) read. 4B.3/4B.4 (`00_PHASE_4B_4_MASTER_READINESS_REPORT.md`)/4B.5/4B.6 master decisions reviewed. Protected repositories untouched.  
**Evidence basis (inspected):** `aj/agents.py`, `aj/execution.py`, `aj/runtime.py`, `aj/orchestrator.py` (routing/handle/resume/_execute/dispatch paths, attempts, cancel, recovery, evidence correlation), `aj/task.py`, `aj/scheduler.py`, `aj/lease.py`, `aj/recovery.py`, `aj/idempotency.py`, `aj/journal.py`, `aj/receipts.py`, `aj/operation_evidence.py`, `aj/consistency.py`, `aj/invariants.py`, `aj/permissions.py`, `aj/authorization.py`, `aj/capability.py`, `aj/contracts.py`, `aj/ids.py`, `aj/memory.py`, `aj/storage_diagnostics.py`, `aj/__main__.py`; tests `tests/test_orchestrator.py`, `tests/test_f2_scheduler_resume.py`, `tests/test_foundation.py`, `tests/test_phase3_lifecycle_reliability.py`, `tests/test_phase3c_recovery_integrity.py`, `tests/test_phase3d_recovery_observability.py`, `tests/test_phase3e_evidence_consistency.py`, `tests/test_phase3f_identity_trust_boundary.py`, `tests/test_task_persistence_fail_closed.py`, `tests/test_phase3.py` (grep evidence).

**Classification labels:** *Fully implemented and verified; Partially implemented; Interface-only; Probe-only; Mock/test-only; Process-local; Missing; Unverified.*

---

## 1. Current agent architecture (source-inspected)

### 1.1 What AJ currently means by “agent”

| Mechanism | Current reality (evidence) | Classification |
|---|---|---|
| Agent boundary/port | `AgentPort` protocol: `name`, `available()`, `describe()`, `execute(request: AgentRequest) -> AgentResult` (`aj/agents.py`). | **Interface-only** (contract shape). |
| Agent adapters | `HttpAgentAdapter` for loopback endpoint: TCP reachability probe `_probe(host,port)`, `describe()` reports `reachable`/`protocol_verified`; `execute()` rejects if wrong assignee, unreachable, or `transport is None` (“no agreed task transport…”). Injected `transport` can POST JSON and parse `AgentResult`, but default is `None`. (`aj/agents.py`) | **Partially implemented / Probe-only** (reachability + honest rejection). Real task transport **not agreed/configured/verified**. |
| Unconfigured agent | `UnconfiguredAgent`: always unavailable, rejects execution with `AGENT_UNAVAILABLE`. | **Implemented (honest placeholder)**. |
| Agent registry/discovery | `AgentRegistry`: in-memory map by uppercase name, `register/get/find/names/status`, `from_config` builds JARVIS/HELIX adapters from `agents.*` config (endpoint/timeout/notes, enabled flag). No dynamic discovery, no remote registry. (`aj/agents.py`) | **Partially implemented (static, process-local)**. |
| Agent IDs/instances | Agents identified by logical name string (`JARVIS`, `HELIX`, etc.). No persisted agent instance IDs, no runtime worker-instance identity, no per-execution agent handle. (`aj/agents.py`, `aj/orchestrator.py` routes) | **Missing** (instance identity). |
| Agent capabilities/capacity/health/heartbeat | `describe()` exposes endpoint/reachable/protocol_verified notes only. No capability advertisement model, no capacity slots, no heartbeat/liveness monitoring, no load/concurrency tracking. | **Missing / Probe-only (TCP only)**. |
| Agent registration & ownership | Registry assembled in runtime/config (`AgentRegistry.from_config`); ownership of capabilities modeled in `CapabilitySpec.owner_agent` (`AJ/JARVIS/HELIX/HERMES`). Logical ownership, not execution-instance ownership. | **Partially implemented**. |
| Agent execution assignment | `Aj._execute` (delegation branch) finds adapter by `route.owner_agent` or `UnconfiguredAgent`, builds `AgentRequest` (task_id/goal/assigned_agent/requester/allowed_capabilities/timeout/idempotency_key), calls `agent.execute(request)`, records evidence/actions/receipt/journal and transitions task based on `AgentResult`. No assignment ledger, no agent selection/matching engine. (`aj/orchestrator.py`) | **Partially implemented (direct call path)**, **Mock/test-only proven** in unit tests with fake agents; live sub-agent transport **unverified/unavailable**. |
| Agent lifecycle/cancellation/failure/result reporting | No agent lifecycle state machine. Cancellation is task-level (`Aj.cancel_task/_cancel_locked`: terminal refused; `EXECUTING` → `CANCEL_REQUESTED` without interrupting running work; others → `CANCELLED`). Agent execution not interruptible/observable as separate lifecycle. Failures surfaced as `AgentResult`/errors recorded on task; retry is task-level bounded recovery path. (`aj/orchestrator.py`, `aj/task.py`) | **Missing** (agent lifecycle) / **Partially implemented** (task-level handling). |
| Agent authorization/provenance | Task-level permission/authorization gates in orchestrator (`Authorizer`, `authorization_context`, stale checks). `AgentRequest` carries requester/allowed_capabilities/timeout/idempotency context but no verified delegated-permission envelope or signed provenance. `local_trust` is not authenticated identity (4B/`aj/authorization.py`). | **Partially implemented (task-level)**, **Missing** (delegation-specific provenance/narrowing enforcement). |

### 1.2 Explicit answers (evidence-based)

| # | Question | Answer | Evidence / classification |
|---|---|---|---|
| 1 | Can AJ currently create a real sub-agent? | **No.** AJ can instantiate in-memory logical adapters/placeholders from config; it cannot spawn/manage real sub-agent processes/runtimes/instances. | `aj/agents.py`, `aj/runtime.py`; **Missing**. |
| 2 | Can AJ assign a task to a sub-agent? | **Only as a direct in-process delegation call path** when routed to JARVIS/HELIX and adapter exists; default adapters have no agreed transport and reject. No durable assignment/claim model. | `aj/orchestrator.py::_execute` delegation branch, `aj/agents.py` `transport is None` rejection, `tests/test_orchestrator.py` fake agents (**Mock/test-only**). |
| 3 | Can AJ distinguish two simultaneous sub-agents? | **No.** No agent instance identities/capacity/assignment tracking; logical name only. | **Missing**. |
| 4 | Can AJ monitor an individual sub-agent? | **No.** Only TCP reachability probe in `describe()/available()`; no per-agent/per-execution monitoring/heartbeat/progress. | `aj/agents.py::_probe`; **Probe-only/Missing**. |
| 5 | Can AJ cancel one sub-agent without cancelling unrelated work? | **No.** Cancellation is task-level and cooperative/non-interrupting for executing work; no sub-agent/execution-scoped cancellation control. | `Aj.cancel_task/_cancel_locked`; **Missing**. |
| 6 | Can AJ detect a failed sub-agent? | **Limited.** Can observe delegation result failure or TCP unreachable; cannot detect runtime/instance health beyond probe or in-flight execution failure semantics. | `AgentResult` handling, `_probe`; **Partially implemented/Probe-only**. |
| 7 | Can AJ retry a failed sub-agent safely? | **Task-level retry only**, bounded by task retry/capability/policy/lease rules; not a sub-agent-instance retry with external side-effect guarantees. | `Aj.retry`, task transitions, receipts/attempts; **Partially implemented, Unverified for external safety**. |
| 8 | Can AJ associate a sub-agent result with a parent task? | **Not as a verified parent-child orchestration model.** Results are recorded on the delegated task record; `TaskStore.child_of`/`parent_task_id` exist but no orchestrated child-creation/aggregation flow observed. | `aj/task.py:child_of`, no orchestrator usage; `aj/orchestrator.py` records on current task; **Missing/Unverified**. |
| 9 | Can AJ enforce the parent's permissions on delegated work? | **No proven delegation inheritance/narrowing.** Task authorization is enforced per handled/resumed task; no explicit parent→child permission envelope propagation or narrowing verification in inspected paths. | `Authorizer`/`authorization_context` per task, `AgentRequest.allowed_capabilities` informational; **Missing/Unverified**. |
| 10 | Can AJ prove that a reported result came from the intended execution? | **No strong proof.** Correlation relies on task/operation/attempt/receipt/journal/lease fields and caller-reported adapter results; no first-class `execution_id`, no cryptographic/remote provenance, cross-store not atomic. | `journal/receipts/invariants/consistency`, lack of execution entity; **Partially implemented correlation, Unverified provenance**. |

---

## 2. Current execution architecture (Task → Orchestrator → Scheduler → Execution → Runtime/Adapter → Evidence)

| Aspect | Current reality (evidence) | Classification |
|---|---|---|
| Where execution begins | Synchronous dispatch inside `Aj._execute(...)` called from `Aj.handle` (after routing/authz) and `Aj.resume/_resume_locked` (scheduler or direct). `Scheduler._run_one` acquires execution lease then `aj.resume(task_id, leased=True)`. | **Implemented (in-process), Process-local**. |
| Execution as persisted object | **No first-class `Execution` entity/record/id.** Execution is implicit: task state transitions (`AUTHORIZED→EXECUTING→VERIFYING→…`), `attempts[]` entries, receipts, journal events, lease ownership. | **Missing** (execution entity). |
| Execution/attempt identity | Task has `operation_id` (single per task). Attempts created by `_start_attempt` (`att-*`, attempt_number, status RUNNING) and finished by `_finish_attempt`; `_attempt_id` returns latest attempt id. Receipts/journal carry `task_id/operation_id/attempt_id/worker_id/lease_id`. HERMES `ExecutionRequest.request_id` composed as `"{task_id}/exec/{attempt_id or '0'}"`; correlation/operation/attempt passed in args for v0 adapter. | **Partially implemented** (attempt ids/evidence), **no execution_id**. |
| Scheduler→execution association | Scheduler selects `AUTHORIZED` tasks and calls `resume(task_id, leased=True)`; resume executes current task record. Association is task-level lease + current attempt, not a distinct execution object. | **Partially implemented, ambiguous for multi-execution**. |
| Execution ownership | Per-task execution lease (`LeaseManager`, `operation="execute"`, worker_id/heartbeat/expiry) acquired by scheduler/resume/hold paths. Not an execution-instance ownership record. | **Partially implemented**. |
| Completion/failure/cancellation/unknown recording | Completion/failure via task transitions, attempt finish, receipts (`ReceiptStore.record`), journal events, audit/memory notes. Cancellation: task-level states/requests (`CANCEL_REQUESTED` cooperative for executing). Unknown/ambiguous outcomes represented indirectly via recovery-required/fail-closed paths and evidence gaps, not a uniform execution outcome entity. | **Partially implemented**. |
| Retry representation | Task-level retry (`FAILED→RECOVERING→RETRYING→EXECUTING`), bounded escalation; new attempts recorded over same task/operation context. No independent execution retry object/lineage model. | **Partially implemented**. |
| Evidence correlation | Journal/receipts/operation-evidence/invariants/consistency correlate by task/operation/attempt/lease/worker/event IDs; `recovery_inspection` correlates evidence and reports gaps. Cross-store non-atomic. | **Partially implemented, Unverified completeness**. |
| Runtime/adapter paths | `_execute`: (1) `internal:` actions → in-process, verified; (2) `helix.calling_service` → in-process calling prepare with timeout; (3) HERMES owner → `ExecutionPort.execute` via `execute()` wrapper (`UnavailableExecutionAdapter` or conditionally built `HermesExecutionAdapter` when gated, but Hermes NOT ATTACHED by config/check); (4) delegation to agent adapter → `AgentRequest/AgentResult`. | **Implemented routing paths (local), Hermes/agents not attached as live external execution**. |

**Consequences of missing first-class `execution_id`/execution entity (critical for concurrent sub-agent orchestration):** cannot uniquely model multiple concurrent executions per task; cannot scope leases/ownership/cancellation/progress/retries per execution instance; cannot disambiguate results from parallel attempts/delegations; cannot represent admitted-but-not-dispatched or dispatch-intent per execution; cannot safely aggregate child execution outcomes under one parent; restart/recovery/duplicate-detection remain coarse and ambiguity-prone.

---

## 3. Parent/child delegation and current delegation capability

| Aspect | Current reality | Classification |
|---|---|---|
| Child task creation primitive | `TaskStore.child_of(parent, goal, ...)` creates child with `ids.new_child_id(parent.task_id)` and `parent_task_id`; task has `root_task_id`, `depends_on`, `parent_task_id`. | **Partially implemented (data primitive)**. |
| Orchestrated delegation/child spawning | No evidence of orchestrator creating child tasks, dispatching children, or aggregating child results. `_execute` delegates the **current task** to an agent adapter (not spawning child tasks). | **Missing** (orchestration workflow). |
| Parent/child visibility | Task lineage fields present; `recovery_inspection`/dependency reports/consistency checks exist at task level, but no parent aggregation engine. | **Partially implemented**. |
| Inherited permissions/context | No explicit inheritance/narrowing mechanism observed for delegated/child work. | **Missing**. |

**Overall delegation capability:** **Interface/probe/data-primitive level only; real concurrent sub-agent delegation, assignment, supervision, aggregation, and cancellation are not implemented.**

---

## 4. Capability matching and permission behavior (current)

| Aspect | Current reality | Classification |
|---|---|---|
| Capability registry/matching | `CapabilityRegistry` + `CapabilitySpec` (owner, adapter, availability, verification, risk, replay/retry safety, permissions/forbidden). Router resolves explicit capability or default/calling rules; dispatch checks blockers/availability/verification. No agent-capability matching/selection engine. | **Partially implemented** (metadata/routing gates). |
| Permissions/authorization | 5-level permission model, `Authorizer`/`ApprovalGate`, payload-bound approvals, unattended ceiling, stale-authorization fail-closed on consequential resume, `authorization_context` persisted. | **Implemented and tested (core paths), Unverified for delegation inheritance**. |
| Identity/trust | `local_trust`/operator provenance is **not authenticated identity** (4B.3–4B.6). No verified principal for remote/delegated actors. | **Known limitation (by design/evidence)**. |
| Fail-closed semantics | Missing/unknown/unavailable/forbidden/stale cases generally fail closed or block in inspected paths. | **Partially implemented/verified in scope**. |

---

## 5. Required 20 concurrent orchestration scenario assessments

Classification per scenario: **Clearly representable / Representable with limitations / Ambiguous / Not representable**.

| # | Scenario | Classification | Missing/limiting domain capability & evidence |
|---|---|---|---|
| 1 | One parent delegates two children concurrently | **Not representable** | No orchestrated child-task spawning/dispatch, no first-class execution/agent-instance identities, no multi-execution-per-parent model, no aggregation. `child_of` primitive unused. |
| 2 | One parent delegates ten children but admission allows only three | **Not representable** | No admission controller, no child/delegation fan-out management, no per-parent/per-agent capacity admission for executions. |
| 3 | Two different parents use the same agent concurrently | **Not representable** | No agent instances/capacity/concurrency control/assignment ledger; logical adapter only (probe/unconfigured transport). |
| 4 | One agent reaches capacity while another is idle | **Not representable** | No agent capacity, health/load metrics, or capability-aware assignment/placement. |
| 5 | One child fails while siblings continue | **Not representable** (as orchestrated siblings) / **Representable with limitations** (independent tasks only) | No child-execution supervision/aggregation; independent tasks have separate lifecycles but no parent-sibling orchestration contract. |
| 6 | One child succeeds and produces a result while another becomes unknown | **Not representable** (orchestrated) | No aggregation over child executions, no per-execution unknown outcome entity; task-level recovery is coarse. |
| 7 | Parent is cancelled while children are running | **Not representable** | No descendant cancellation propagation/scope, no running execution/sub-agent interrupt control; task cancel is local/non-interrupting for executing. |
| 8 | One child is cancelled while siblings continue | **Not representable** (orchestrated) | No scoped child/execution cancellation isolated from siblings/parent. |
| 9 | Parent deadline expires while children remain active | **Ambiguous / Not representable** | Task deadlines checked in scheduler/resume paths with `dead_letter` attempt (coherence unverified); no parent-child deadline propagation or active-child control. |
| 10 | Child retries after failure | **Representable with limitations** (task-level) | Retries/attempts exist per task with bounded escalation; no child-execution/agent-scoped retry model or external side-effect safety proof. |
| 11 | Two children accidentally receive the same logical work | **Ambiguous** | Idempotency is capability-scoped submission dedupe; no execution/assignment-level dedupe for delegated work, no `execution_id`. |
| 12 | Two AJ processes attempt to assign the same execution | **Ambiguous / Representable with limitations** | Per-task execution leases/locks provide some mutual exclusion, but no execution assignment entity, cross-process store consistency/NTFS locking reliability unproven. |
| 13 | Agent disappears while work is active | **Ambiguous** | No agent instance monitoring/heartbeat; only coarse task/lease/recovery handling; external/in-flight outcome may be unknown. |
| 14 | Agent reports completion but evidence persistence fails | **Representable with limitations** | Task/evidence writes can fail; fail-closed reconciliation in some paths but cross-store partial writes possible (no atomicity), risk of ambiguous state. |
| 15 | Execution starts but AJ crashes before recording the running state | **Ambiguous** | Durable intent-before-dispatch not guaranteed; recovery conservative but outcome/evidence may be missing/unknown. |
| 16 | AJ records an execution as admitted but never dispatches it | **Not representable** | No admission entity/ledger/dispatch-intent state; no `execution_id`. |
| 17 | External runtime completes after AJ has marked local execution unknown | **Ambiguous** | No external correlation/outcome reconciliation protocol; recovery must remain honest/unknown without evidence. |
| 18 | A child task creates its own child task | **Representable with limitations** (data only) | `child_of` allows hierarchy data; no orchestration/scheduling/aggregation/capacity controls for nested delegation. |
| 19 | Parent dependency is unresolved while children are ready | **Not representable** (orchestrated) | No parent-child readiness/aggregation semantics; dependency checks are task-level (`depends_on`). |
| 20 | Parent has partially successful children and requires aggregation | **Not representable** | No aggregation policy/engine, no child result set model, no first-class executions/children linkage for orchestration. |

---

## 6. Audit conclusions (Stage 5A.3, current state)

- **Agent model today:** logical, static, probe-only adapters (JARVIS/HELIX) with honest rejection when no agreed transport; no real sub-agent creation/instances, no assignment/ownership/capacity/health/cancellation lifecycle, no verified live delegation runtime.
- **Execution model today:** in-process orchestrated dispatch over task lifecycle with implicit execution, single `operation_id` per task, attempt records/receipts/journal correlation, per-task execution leases; **no first-class `execution_id`/execution entity**, no concurrent multi-execution-per-task support.
- **Delegation today:** `child_of` and hierarchy fields exist as primitives but no orchestrated parent-child delegation, supervision, permission inheritance/narrowing, or result aggregation.
- **Boundary posture preserved:** AJ remains control plane only; Hermes read-only `status.read` boundary NOT ATTACHED, `gateway.ensure` unauthorized; JARVIS/HELIX identities and repos untouched; `local_trust` not authenticated; no exactly-once/external-cancellation guarantees.

**Stage 5A.3 audit evidence is sufficient to inform proposed orchestration architecture (`11`/`12`) without implying implementation or capability existence.**
MARKDOWN
