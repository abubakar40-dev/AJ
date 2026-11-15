# 20 — Phase 5A.6 Pre-Implementation Audit (Agent Assignment, Task Delegation & Hierarchical Orchestration Foundation)

**Date:** 2026-11-14  
**Stage:** 5A.6 (audit-before-implementation)  
**Status:** Complete for 5A.6 entry; implementation follows this audit.

## 1. Baseline, Git safety, and health (verified)
- Repo: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`, branch `main`, HEAD `468fdcebece5b25f02e53add4928d3650ef175f4` (unchanged).
- `git status --short` at 5A.6 start: **51 entries** (17 tracked modified, 34 untracked) — identical composition reported at 5A.5 completion. All pre-existing tracked modifications and untracked files/directories preserved; no staging/commit/push/merge/rebase/reset/clean/history rewrite planned.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` → **ok:true, 23/23, failures:[]**, attached `{jarvis:false, helix:false, hermes:"NOT ATTACHED"}`.
- Protected repos (JARVIS, HELIX copies, Hermes) untouched; Hermes NOT ATTACHED, `gateway.ensure` unauthorized/not implemented/not executed.

## 2. Accepted inputs inspected (5A.1–5A.5)
- **5A.1 (domain):** `02_TASK_EXECUTION_DOMAIN_MODEL_AUDIT.md`–`05_STAGE_5A_1_VERIFICATION_REPORT.md` (via 5A.3 references and accepted baseline) — task/operation/execution/attempt distinctions, execution identity gap historically identified.
- **5A.2 (scheduler/admission):** `06`–`09` — eligibility→admission→dispatch separation, bounded capacity/backpressure/fairness, fail-closed, proposed architecture guidance.
- **5A.3 (sub-agent/orchestration design):** `10_SUB_AGENT_AND_EXECUTION_ORCHESTRATION_AUDIT.md`, `11_PROPOSED_SUB_AGENT_ORCHESTRATION_ARCHITECTURE.md`, `12_SUB_AGENT_ORCHESTRATION_DECISION_REGISTER.md`, `13_STAGE_5A_3_VERIFICATION_REPORT.md` read in full. Current state: logical/probe-only agents, no real sub-agent instances/assignment ledger/capacity/heartbeat, execution implicit before 5A.4, `child_of` primitive exists but no orchestrated delegation/aggregation, delegation-specific permission narrowing/provenance missing. Proposed (not implemented/approved): Model C hybrid (child tasks + executions/attempts), explicit `execution_id`/assignment/dispatch intent, narrowing-only permissions, separate lifecycles, evidence-honest aggregation/cancellation/recovery, Option D staged.
- **5A.4 (execution foundation):** `14`–`16` + `aj/execution_domain.py`, task/execution linkage in `aj/task.py`/`aj/orchestrator.py` — AJ-owned `exc_*` `ExecutionRecord`/append-only `ExecutionStore` (fail-closed), task `current_execution_id`/`execution_ids`, additive correlation; execution `assignment_id` field exists but no assignment entity/store/lifecycle implemented.
- **5A.5 (scheduler/admission/dispatch foundation):** `16A`, `17`–`19` + `aj/scheduler.py`, `aj/config.py` — explicit eligibility/admission decisions, deterministic bounded selection/aging/backpressure, durable dispatch intent/evidence (`scheduler_decisions.jsonl`, fail-closed in durable mode), reuse of 5A.4 execution domain and existing `LeaseManager`, observational `inspect()`, strict `scheduler` config. 533 passed, 13 warnings, 0 failures; 23/23 check; Hermes NOT ATTACHED.

**Carried constraints:** AJ-local control plane only; no cross-store atomicity, no exactly-once/external guarantees; NTFS/SQLite-WAL reliability unresolved (fail closed when durable persistence/intent cannot be trusted); `local_trust` is not authenticated identity; reuse 5A.4 execution domain and existing LeaseManager/scheduler/admission (no duplicate systems); Hermes/JARVIS/HELIX boundaries unchanged.

## 3. Current implementation traced (source-backed)

### 3.1 Task hierarchy and persistence
- `aj/task.py` (`TaskRecord`): `task_id`, `operation_id`, `parent_task_id`, `root_task_id`, `depends_on`, `capability_id`, `request_payload`, `permission_level`, `approval_required`, `authorization_context`, `current_execution_id`, `execution_ids`, attempts/evidence/errors/recovery fields, lifecycle states/transitions.
- `TaskStore`: in-memory authoritative snapshots, append-only `tasks.jsonl` persistence, fail-closed writes/reload reconciliation, `create(...)`, `child_of(parent, goal, task_id=ids.new_child_id(...))` primitive sets `parent_task_id` (requester inherited) but does **not** set/propagate `root_task_id`, does **not** validate parent existence/ancestry/cycles, does **not** enforce delegation permissions/idempotency/provenance, does **not** prevent duplicate child creation by contract key.
- `aj/ids.py`: `new_task_id`, `new_child_id(parent_task_id)`; `aj/contracts.py` includes `AgentRequest.parent_task_id` but no delegation/assignment contracts.

### 3.2 Orchestrator and delegation behavior
- `aj/orchestrator.py`: `handle()` creates root task (`root_task_id = task_id`), routes/authorizes/executes; `_execute` dispatches internal/calling/Hermes-adapter or **delegates current task** to logical agent adapter (`AgentRequest/AgentResult`) — records `delegate` action/evidence/receipt but does **not** create child tasks, does **not** perform capability-matching/assignment/aggregation, and does **not** implement parent-child orchestration workflow. `resume`/scheduler integration executes authorized tasks via 5A.5/lease/5A.4 execution paths. `recovery_inspection`/status include `parent_task_id`/`root_task_id`/`child_task_ids` visibility but no aggregation policy engine.

### 3.3 Agents, capabilities, execution domain, leases, scheduler
- `aj/agents.py`: logical `AgentPort`/`HttpAgentAdapter`/`UnconfiguredAgent`/`AgentRegistry` (static config, TCP reachability probe, no agreed task transport by default, honest rejection); no agent instance IDs, capacity/heartbeat/assignment, no capability advertisement/matching engine, no authn. States distinguishable in practice limited (configured/registered/reachable-probe/unavailable); cannot claim authenticated/authorized/capable-beyond-evidence/executing/verified.
- `aj/capability.py` + orchestrator routing/authorizer: capability specs, permissions/risk/availability/verification gates (task-level, fail-closed in scope) but no delegation-specific matching/selection ledger and no parent→child permission narrowing enforcement.
- `aj/execution_domain.py`: `ExecutionRecord` has `agent_id` and `assignment_id` fields (optional) but **no assignment entity/store/lifecycle**; `aj/lease.py` provides operation/execution leases (file-backed/flock/in-memory) — reuse required, no duplicate lease system.
- `aj/scheduler.py` (5A.5): eligibility/admission/dispatch/monitoring foundation; child tasks must flow through same checks/admission/backpressure/dispatch/lease/evidence.
- Evidence/recovery: journal/receipts/operation evidence/consistency/invariants/recovery inspection exist; cross-store non-atomic.

### 3.4 Relevant tests/callers (inspected)
- `tests/test_orchestrator.py` (delegation via fake agents, routing), `tests/test_foundation.py` (`child_of` parent linkage), scheduler/5A.4/5A.5 suites, recovery/evidence/phase3 suites, transfer/import integrity — existing behavior/callers must remain compatible.

## 4. Gaps vs Phase 5A.6 requirements

1. **Delegation contract (validated, versioned, backward-compatible, idempotent):** missing explicit AJ-owned delegation request/record (delegation ID, parent/root, child spec, requested capabilities/constraints/priority/deadline/permission context, correlation/idempotency/provenance); no strict validation or bounded creation.
2. **Controlled child-task orchestration:** `child_of` lacks root propagation, parent-existence/ancestor/cycle validation, duplicate-prevention keyed by delegation/idempotency, delegation provenance/reason recording, and safe handling hooks for parent/child terminal/recovery states.
3. **Logical agent identity model:** registry is minimal; need explicit AJ-owned logical agent records/registry extension (stable agent_id, type, declared capabilities, availability, trust classification `local_trust`/unverified, execution mode, version/compat, optional logical capacity/provenance) without inventing authn or claiming unverified states.
4. **Deterministic capability matching/selection:** missing explicit matcher (exact/declared-verified capability satisfaction, unknown/disabled/unsupported/unavailable reject, explainable selection/rejection, deterministic tie-break) separate from ad-hoc routing.
5. **Assignment lifecycle (distinct durable model):** no assignment record/store/state machine (`proposed/assigned/.../recovery_required/unknown` as supported), no conservative duplicate-active prevention, no stale/race handling, no explicit logical/internal labeling where no real transport.
6. **Permission narrowing (critical):** no enforced child effective-permissions intersection (parent-authorized ∩ delegation-requested ∩ agent-supported ∩ system restrictions), no fail-closed on missing/malformed/unverifiable context, no recorded permission decision/provenance, no prevention of child/agent self-escalation.
7. **Parent progress/result aggregation:** no deterministic aggregation foundation/rules/policy (all/any/subset-required as justified), no parent-wait/completion gating based on required children, no explicit aggregation state/evidence linkage.
8. **Failure isolation/recovery/observability for delegation:** no orphan/missing-parent/incomplete-delegation/stuck-assignment/incomplete-aggregation detection and evidence-backed recovery hooks specific to delegation; need conservative handling for partial creation, crashes, duplicate delegation, agent unavailable, persistence failure.
9. **Scheduler/monitoring integration:** delegated children must pass 5A.5 pipeline without bypass/hidden unlimited queue; monitoring/inspection must expose delegation/assignment/child/parent/agent-match reasons observationally.
10. **Concurrency/idempotency:** deterministic IDs/keys/locking/persistence needed for concurrent duplicate delegation, duplicate child creation, assignment races, crash windows — without distributed/exactly-once/cross-store-atomicity claims.

## 5. Compatibility and safety constraints for implementation

- **Do not redesign core domain:** smallest complete AJ-local foundation; reuse 5A.4 `ExecutionStore`/`ExecutionRecord` and existing `LeaseManager`, 5A.5 scheduler/admission/dispatch, task store/journal/receipts/evidence conventions.
- **Preserve behavior/APIs:** existing `TaskStore` create/child_of/save/import/transition semantics, orchestrator handle/resume/delegation-to-agent (current task) path, scheduler `queue/run_once/inspect` contracts, execution/evidence/receipt formats remain backward-compatible; legacy records loadable.
- **Strict validation & fail-closed:** delegation/assignment/agent/capability/permission inputs validated; unknown/missing/malformed/unverifiable state => fail closed; no privilege escalation, no permission widening, no fabricated remote acceptance/execution/completion, no blind retry of uncertain external side effects.
- **Distinct concepts enforced:** Task ≠ Operation ≠ Execution ≠ Attempt ≠ Agent (logical) ≠ Assignment ≠ Lease ≠ Delegation ≠ Aggregation.
- **Bounded/deterministic:** bounded child creation/dispatch via validated config/limits (logical, not measured host claims), deterministic matching/selection/aggregation, no background daemon, no uncontrolled concurrency/resource tests.
- **Out of scope (enforced):** no live AJ↔JARVIS/HELIX/Hermes integration, no real remote transport/execution, no Hermes gateway ensure, no arbitrary shell/Python/MCP/skills/browser/messaging/financial/account ops, no distributed/multi-machine workers/daemon/unbounded pools/provider-model redesign/paid APIs/Docker/Honcho/local LLMs, no NTFS repair/storage migration, no unrelated refactors. Hermes NOT ATTACHED; JARVIS/HELIX untouched.
- **Storage/durability honesty:** NTFS/SQLite-WAL risk unresolved; append-only evidence where applicable; document non-atomic multi-store ops/crash windows; no exactly-once/cross-store atomicity claims.

## 6. Minimal implementation plan (5A.6, ordered)

1. **Contracts/data foundation:** add versioned, strictly-validated delegation/assignment/logical-agent contracts and append-only durable stores (AJ-local JSONL, fail-closed) for delegation decisions/records and assignment records as needed; deterministic/idempotency keys.
2. **Hierarchy/delegation correctness:** extend/compose task creation helpers to enforce explicit parent/root linkage, parent existence/ancestor-cycle/self checks, controlled bounded child creation with provenance/reason, duplicate-delegation/idempotency prevention, and safe conservative semantics for cancellation/failure/recovery interactions (without mutating legacy tasks).
3. **Logical agents & capability matching:** AJ-owned logical agent identity records/registry extension (declared/unverified states only) + deterministic fail-closed capability matcher with explainable accept/reject.
4. **Assignment lifecycle:** explicit assignment records/states/transitions distinct from execution/lease; prevent duplicate active assignments; reuse existing leases where appropriate; mark logical/internal assignments honestly.
5. **Permission narrowing:** compute/record effective child permission envelope as intersection (fail closed on gaps); reject escalation/missing/unverifiable context.
6. **Scheduler/dispatch integration:** route delegated child tasks through existing 5A.5 eligibility/admission/backpressure/dispatch/lease/execution/evidence paths; no bypass/hidden queue.
7. **Aggregation, isolation, recovery, monitoring:** deterministic parent progress/aggregation foundation (required-children policy, explicit states/counts), failure isolation and evidence-backed recovery/uncertainty handling, observational monitoring extensions for delegation/assignment/orphans/stuck/waiting states.
8. **Tests/docs/verification:** focused deterministic tests for required scenarios + compatibility/regressions, full suite, `aj --check`, Hermes/boundary/Git verification, docs `21`–`24`.

*This audit is evidence-backed and conservative; implementation will follow inspected AJ contracts/behavior and will stop after 5A.6 with evidence-backed verdict.*
