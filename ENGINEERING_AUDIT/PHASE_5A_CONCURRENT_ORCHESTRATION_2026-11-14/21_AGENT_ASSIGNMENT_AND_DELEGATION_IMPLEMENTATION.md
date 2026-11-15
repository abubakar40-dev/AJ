# 21 — Agent Assignment & Delegation Implementation (Stage 5A.6)

**Status:** Minimal AJ-local logical/internal delegation foundation implemented (partial 5A.6 scope). **No 5A.7 work performed.**  
**Baseline:** `main@468fdcebece5b25f02e53add4928d3650ef175f4`, 51 pre-existing git status entries preserved at 5A.6 start (17 tracked M, 34 untracked). 5A.1–5A.5 docs/decisions inspected; 5A.5 scheduler/admission/dispatch and 5A.4 execution domain reused.

## 1. Actual delegation architecture (implemented)

- **New module:** `aj/delegation.py` — versioned contracts/records/stores and deterministic helpers for delegation, logical agent identity, capability matching, permission narrowing, assignment lifecycle, aggregation/progress, and anomaly detection.
- **Orchestrator integration (`aj/orchestrator.py`):** durable `DelegationStore`/`AssignmentStore`/`LogicalAgentStore` (append-only JSONL in data dir when task persistence enabled), `Aj.delegate()` (controlled logical/internal delegation foundation), `Aj.delegation_status()`, `Aj.delegation_monitor()` (observational, no mutation).
- **Task hierarchy support:** `TaskStore.child_of()` now propagates `root_task_id` from parent lineage (safe compatibility improvement); delegation-created children are linked with explicit `parent_task_id`/`root_task_id` and delegation provenance in task context.
- **IDs/config/runtime:** `aj/ids.py` adds delegation/assignment ids; `aj/config.py` adds strict validated `delegation` bounds (`enabled`, `max_children_per_delegation`, `max_delegations_per_parent`, `max_active_assignments_per_child`); logical defaults conservative. Runtime/health/checks remain compatible (delegation config surfaced).

**Concept separation maintained:** Task, Operation, Execution, Attempt, Agent (logical), Assignment, Lease, Delegation, and Aggregation are distinct entities/concerns. No duplicate execution/lease/scheduler systems introduced.

## 2. Delegation contract

- **`DelegationRequest` (schema v1):** validated, versionable, backward-compatible contract with `parent_task_id`, `requested_work`, `child_specs`, `required_capabilities`, `constraints`, `priority`, `deadline`, `permission_context`, `correlation_id`, `idempotency_key`, `provenance`, `aggregation_policy` (`all_required|any_sufficient|subset_required`), `required_child_ids`, `max_children`. Strict validation rejects malformed types/unsupported schema/bounds and conservatively rejects obvious arbitrary executable code/shell markers.
- **`DelegationRecord`:** durable append-only record of validated request, deterministic `delegation_id`, root linkage, created child ids/refs, status, reason, evidence/provenance.
- **Idempotency/duplicate prevention:** stable delegation id derived from idempotency key or `(parent_task_id, spec_hash, delegation.v1)`; existing idempotent/same-contract delegations return prior status; per-parent and per-delegation bounds enforced (fail closed when exceeded).

## 3. Task hierarchy

- Controlled child creation via `Aj.delegate()` (not ad-hoc): validates parent existence/loadability and hierarchy (`validate_parent_chain`), rejects invalid parent references, self-parent/ancestor cycles, and unsafe hierarchy conditions (fail closed).
- Children created as AJ-owned task records with stable ids, explicit `parent_task_id`, propagated `root_task_id`, bounded count, and delegation provenance/reason/context; child history preserved in existing task store/evidence model.
- Delegation disallowed from terminal/failed-final parent states (conservative). Parent/child cancellation/failure/recovery/aggregation semantics are represented at foundation level (progress/aggregation helpers, anomaly detection) but not fully enforced as an automatic orchestrator state machine.

## 4. Logical agent identity

- **`LogicalAgentRecord` (AJ-owned):** `agent_id`, `logical_name`, `agent_type`, declared `supported_capabilities`, `availability_state`, `trust_classification=unverified_local_trust`, `execution_mode` (`logical_internal`/adapter profile), version/compatibility, logical `capacity` (configured/declared only), provenance, enabled flag.
- `Aj._seed_logical_agents()` materializes logical profiles from current agent registry/config as probe/config evidence only (no authn, no execution proof). Internal logical worker profile provided for logical/internal assignment foundation.
- Explicit non-claims: `local_trust` is **not** authenticated identity; configured/registered/reachable-probe states do not imply authenticated/authorized/capable/executing/verified.

## 5. Capability matching and selection

- Deterministic, fail-closed `match_agent()`: exact declared capability satisfaction required for all requested capabilities; unknown capability => no match; disabled/unavailable agents and disabled capabilities rejected; no wildcard privilege inference from names; explainable rejection reasons and deterministic selection (logical_internal preference, then least-broad supported set, then `agent_id`).

## 6. Assignment lifecycle

- **`AssignmentRecord` (distinct from Task/Execution/Attempt/Lease):** AJ-owned `assignment_id`, delegation/parent/child/execution/attempt links, `agent_id`, capability, status, `logical_internal=true` marker, match/permission decision evidence, lease ref, events/timestamps.
- States/transitions implemented: `PROPOSED, ASSIGNED, ACCEPTED, RUNNING, COMPLETED, FAILED, REJECTED, CANCEL_REQUESTED, CANCELLED, UNKNOWN, RECOVERY_REQUIRED` with conservative transition validation.
- Assignments created as logical/internal `ASSIGNED` records with recorded match and permission decision; duplicate active assignment per child prevented at store/create time; no fabricated remote acceptance/execution. Existing `LeaseManager` and 5A.4 execution domain remain separate/reusable (execution `assignment_id` linkage available).

## 7. Scheduler/execution integration (foundation level)

- Delegated children are created as normal AJ task records with delegation provenance and must follow existing task lifecycle/authorization/capability/policy semantics; 5A.5 scheduler/admission/dispatch, 5A.4 execution domain, and existing leases/evidence stores are reused (no bypass, no parallel scheduler/lease/execution systems).
- **Limitation:** `Aj.delegate()` currently creates children in `RECEIVED` state and records logical assignment/progress foundations; it does **not** implement full end-to-end orchestration that automatically advances/authorizes/admission-dispatches children or drives parent completion transitions. Children become schedulable/dispatchable only when progressed/authorized through existing AJ paths and then pass 5A.5 eligibility/admission/dispatch.

## 8. Parent progress and aggregation

- `aggregate_parent_progress()` provides deterministic observational aggregation (counts by state, waiting/manual-review indicators, required-child policy handling for `all_required`/`any_sufficient`/`subset_required`, `can_complete` heuristic based on required completed children and no manual-review signals).
- `delegation_status()` / `delegation_monitor()` expose delegation records, assignments, per-parent progress, and anomaly indicators (orphaned/missing/incomplete/stuck/recovery-required observations).

## 9. Limitations (explicit)

- AJ-local logical/internal foundation only; **no real remote agent execution transport**, no real agent acceptance/progress/completion proofs, no live JARVIS/HELIX/Hermes integration, Hermes NOT ATTACHED, `gateway.ensure` not implemented/enabled/executed/authorized.
- No automatic child orchestration/dispatch pipeline, no automatic parent aggregation state transitions/completion enforcement, and no full crash-safe multi-store delegation workflow; cross-store operations remain non-atomic.
- **No exactly-once, no cross-store atomicity, no distributed correctness claims.** NTFS/SQLite-WAL reliability risk remains unresolved (fail closed on durable persistence failures where applicable). `local_trust` is not authenticated identity.
- Permission narrowing implemented as explicit intersection-only computation/recording for delegation-coordination context; execution-time capability/authorization enforcement remains governed by existing AJ policy/authorizer/scheduler paths.
- Test coverage is focused/deterministic but not an exhaustive 1:1 proof of every enumerated scenario; see `23` and `24`.
