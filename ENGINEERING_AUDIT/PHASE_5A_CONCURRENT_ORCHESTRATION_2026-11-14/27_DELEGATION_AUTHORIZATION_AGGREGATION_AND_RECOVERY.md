# 27 — Delegation Authorization, Aggregation and Recovery (Stage 5A.6R)

**Status:** Corrective closure notes for security, aggregation, and recovery behavior (partial closure).

## 1. Permission enforcement points

- **Request/contract validation:** `DelegationRequest.validate()` enforces schema/bounds/types and rejects obvious executable markers.
- **Capability matching:** `match_agent()` fail-closed deterministic selection (unknown/disabled/unavailable unsupported).
- **Permission narrowing (creation):** `narrow_permissions()` computes intersection-only envelope; `Aj.delegate()` records `permission_decision`, effective/requested/parent snapshots in task `authorization_context.delegation` and `AssignmentRecord` evidence.
- **Execution authorization boundary (5A.6R):** `_delegated_permission_guard()` in `Aj._resume_locked()` (before dispatch/execute via scheduler resume) and `Aj._execute()` (defense-in-depth) blocks delegated child execution when delegation evidence is missing/invalid/malformed, or when recorded effective permissions exceed captured envelopes / violate logical-internal scope constraints (fail closed, no escalation).
- **Existing gates preserved:** capability blocker/availability/verification, `Authorizer` decisions, stale-authorization handling for consequential resume, lease ownership, 5A.5 eligibility/admission.

**Limitation:** enforcement is evidence/boundary-based and covered by targeted tests/adversarial tamper case; not exhaustively proven across every possible mutation path, legacy record shape, or future context evolution.

## 2. Authorization and lifecycle integration

- Delegated children are created as normal tasks and prepared through existing planning/authorization transitions to reach `AUTHORIZED` (schedulable by 5A.5), `WAITING_FOR_APPROVAL`, or explicit fail/abort states based on existing policy/capability checks.
- Scheduler eligibility/admission/dispatch unchanged in ownership: children pass 5A.5 queue/eligibility/admission/backpressure and dispatch via lease + `Aj.resume(..., leased=True)`; 5A.4 execution/attempt/evidence paths reused.
- Logical assignment remains distinct from authorization/admission/dispatch/execution; no remote acceptance fabricated.

## 3. Parent aggregation semantics

- Deterministic `aggregate_parent_progress()` computes counts/state indicators and required-child completion heuristic for `all_required`, `any_sufficient`, `subset_required` using current task states/evidence.
- `Aj._reconcile_delegation_parent()` recomputes aggregation, stores reconciliation evidence in delegation record, and returns child preparation/aggregation results (explicit mutating reconciliation, bounded to parent delegations).
- **Policy behavior:** required children in incomplete/uncertain/manual-review states prevent `can_complete`; required failures reflected in counts and prevent false completion. Optional/required semantics follow selected aggregation policy and required-child set.
- **Limitation:** aggregation is reconciled explicitly (and after delegation creation) but not automatically enforced as a parent task terminal-state transition on every child state change hook; interrupted aggregation/competing updates remain possible due to non-atomic multi-store writes.

## 4. Failure isolation and recovery

- Delegation creation failures mark records `FAILED` or `RECOVERY_REQUIRED` conservatively when partial/uncertain; idempotent same-spec requests return existing state.
- Child outcomes remain per-task records; aggregation reflects failures/unknown/recovery states without silently discarding them.
- Explicit reconciliation is safe to invoke repeatedly (bounded, evidence-recording); no blind retry of uncertain external work introduced.
- Crash-window handling (demonstrated): intent recorded without children is detectable as incomplete and reconciled explicitly with evidence.

## 5. Observability and anomalies

- `delegation_status()` (observational): delegation record, assignments, current aggregation.
- `delegation_monitor()` (observational, non-mutating): inventories/counts, per-parent progress, anomaly indicators (orphaned/missing children, missing parents, incomplete delegations, stuck/recovery-required assignments).
- Delegation evidence includes last reconciliation snapshots where performed.

## 6. Crash windows and uncertainty (honest)

Defined/handled at foundation level (not fully atomic): intent-only recorded, child created/prepared, assignment persisted, authorization prepared, admission/dispatch via 5A.5 intent/lease, execution/attempt/evidence, aggregation persistence. Multi-store sequences are **not atomic**; evidence may be partial. Reconciliation classifies/re-records observable state and defers/flags uncertainty rather than inventing success. **No exactly-once, no cross-store atomicity, no distributed correctness claimed.**

## 7. Remaining gaps

- No comprehensive automatic repair/state machine for all parent/child/assignment/execution crash permutations.
- Incomplete exhaustive detection for all orphan/stale/incorrect-parent-completion cases and not all proven by dedicated tests.
- No real authenticated identity/provenance; `local_trust` unverified.
- Concurrency/race safety evidenced only by bounded deterministic tests and store guards, not proven under all multi-process timing/crash conditions.
