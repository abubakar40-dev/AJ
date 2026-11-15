# 22 — Delegation Security and Recovery (Stage 5A.6)

**Status:** Evidence-backed description of implemented 5A.6 security/recovery foundations and remaining limitations.

## 1. Security boundaries

- **No privilege escalation:** delegation permission narrowing is computed as intersection-only over provided/derived permission domains (`parent ∩ requested ∩ agent ∩ system` where applicable). Effective permissions cannot include values absent from all sources; narrowing decisions are recorded on assignment evidence. Child tasks/agents are not granted authority by delegation records alone.
- **Fail-closed contexts:** delegation/assignment/matching logic rejects invalid/missing/unverifiable inputs (unknown/unsupported schema, invalid parents/hierarchy, missing required capabilities, unknown/disabled/unavailable capabilities or agents, malformed permission contexts, bound violations, persistence/store unavailability for durable delegation). No fabricated remote acceptance/execution/completion states.
- **Logical identity vs trust:** agent records are AJ-owned logical profiles with `trust_classification=unverified_local_trust` and probe/config provenance only. `local_trust` is **not** authenticated identity. Reachability/configuration/registration does not imply authenticated, authorized, capable, assigned, executing, or verified completion.
- **Contract safety:** delegation requests are strictly validated and conservatively reject obvious arbitrary executable code/shell instruction markers; no arbitrary shell/Python/MCP/skill/browser/messaging/financial/account execution introduced.
- **Boundaries preserved:** Hermes NOT ATTACHED, `gateway.ensure` not implemented/enabled/executed/authorized; no live AJ↔JARVIS/HELIX/Hermes integration; JARVIS/HELIX/Hermes repos untouched.

## 2. Permission inheritance model (implemented foundation)

- `narrow_permissions()` requires well-formed permission sets and returns fail-closed on missing/malformed/unverifiable domains.
- `Aj.delegate()` records a delegation-coordination permission envelope and per-child permission decision/match evidence in assignment and task delegation context. Execution-time authorization/capability/risk/approval enforcement remains the responsibility of existing AJ orchestrator/authorizer/scheduler gates (unchanged, fail-closed behavior preserved).
- **Limitation:** full end-to-end enforcement of inherited narrowed execution permissions for all delegated child execution paths is not comprehensively implemented as a new policy engine in 5A.6; integration relies on existing task/authorization/capability controls plus recorded narrowing evidence.

## 3. Failure isolation and recovery behavior

- **Idempotency/duplicate control:** deterministic delegation ids (idempotency key or contract-spec hash) prevent duplicate delegation record creation for same key/spec; duplicate active assignments per child rejected; bounded creation limits prevent unbounded fan-out.
- **Partial/uncertain outcomes:** delegation creation records intent, then creates child tasks/assignments; on failure, delegation status is marked `FAILED` or `RECOVERY_REQUIRED` conservatively (when partial creation may have occurred) with reason/evidence. Cross-store writes are **not atomic**; uncertain states must be treated as requiring inspection/review per evidence.
- **No unsafe retry claims:** foundation does not blindly retry uncertain external side effects (no real external side effects introduced). Unknown/ambiguous outcomes must not be converted to success/failure without evidence.
- **Assignment/task uncertainty:** assignment lifecycle includes `UNKNOWN` and `RECOVERY_REQUIRED`; aggregation/monitoring surfaces manual-review/waiting/incomplete indicators rather than assuming success.
- **Parent/child semantics:** parent terminal-state delegation rejected; child failure/completion reflected in observational aggregation counts; automatic parent cancellation propagation, automatic aggregation-driven parent transitions, and complete crash-recovery workflows are not fully implemented.

## 4. Observability and anomaly detection

- `delegation_status()` returns delegation record, assignments, and deterministic aggregation/progress for the delegated children.
- `delegation_monitor()` provides observational view (no mutation): delegation/assignment/logical-agent inventories, per-parent progress, and anomaly indicators including orphaned/missing-child observations, missing-parent delegations, incomplete delegations, stuck/recovery-required assignments.
- Existing task lineage/recovery/lease/evidence mechanisms remain available; 5A.5 scheduler monitoring remains observational and unchanged in semantics.

## 5. Storage and durability

- Delegation/assignment/logical-agent records use append-only JSONL stores with fail-closed read/append behavior (durable when `data_dir`/task persistence available). Ephemeral/non-durable store contexts fail closed for durable delegation API usage.
- Workspace remains on NTFS-mounted drive with unresolved historical SQLite/WAL reliability risk; no NTFS repair, storage migration, or mount/config changes performed. No aggressive write/concurrency/resource-exhaustion tests executed.
- **No exactly-once behavior, no cross-store atomicity, no durable distributed transaction claims.** Crash windows include (but are not limited to): delegation intent recorded before/after child creation, child creation vs assignment persistence, and any future dispatch/execution/evidence correlation across stores.

## 6. Known security/recovery gaps

- No real authenticated agent identity, no cryptographic provenance, no remote transport security model (out of scope / not implemented).
- No automatic reconciliation/repair engine for all orphan/stuck/incomplete delegation states; detection is observational and evidence-backed handling remains conservative/manual-review oriented.
- No end-to-end enforcement that all delegated child capability executions run only under fully materialized narrowed execution contexts beyond existing AJ controls and recorded evidence.
- Concurrent multi-process delegation correctness not proven; deterministic single-process/bounded behavior targeted only.
- Delegated children not automatically progressed into authorized/schedulable states by `Aj.delegate()`; operational flow depends on existing/explicit task progression semantics.
