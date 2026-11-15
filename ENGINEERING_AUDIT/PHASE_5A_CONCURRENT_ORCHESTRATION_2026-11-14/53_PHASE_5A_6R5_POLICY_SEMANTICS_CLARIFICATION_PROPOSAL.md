# 53 — Phase 5A.6R5 Policy Semantics Clarification Proposal

**Date:** 2026-11-14  
**Phase:** 5A.6R5 (audit, policy-definition, compatibility-analysis only)  
**Status:** **PROPOSED — NOT APPROVED.** No implementation authorization granted.  
**Classification key:** [VERIFIED FROM SOURCE/TEST EVIDENCE] [PARTIALLY VERIFIED] [UNVERIFIED] [PROPOSED POLICY] [UNSUPPORTED] [OPEN ISSUE]

## 1. Purpose and authority
- **Purpose:** clarify and propose explicit policy semantics for the narrowed invariant-based acceptance baseline (Option 3) so acceptance criteria can be evaluated against defined, compatible, evidence-backed rules. [PROPOSED POLICY]
- **Authority/scope:** this is a **proposal** for user review/approval; it does **not** approve baseline 52, does **not** authorize implementation, refactoring, integration, cleanup, Phase 5A.7, or modification of protected repositories. [PROPOSED POLICY]
- **Method:** read-only source/test audit and compatibility analysis against current AJ behavior (no code/tests/config/schema/data changes). [VERIFIED FROM SOURCE/TEST EVIDENCE]

## 2. Relationship to proposed baseline document 52
- Baseline 52 recorded: `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/52_PHASE_5A_6R5_PROPOSED_NARROWED_INVARIANT_BASELINE_V1.md` (Option 3, v1.0, PROPOSED/PENDING). [VERIFIED FROM SOURCE/TEST EVIDENCE]
- Doc 53 **does not modify** Doc 52; it proposes clarifications for INV-01/02/03/04/05/06/07/08/09 and evidence/acceptance semantics to support review, approval, or revision. [PROPOSED POLICY]
- Reconstructed 45-scenario matrix and crash windows A–J remain supporting material, not binding original requirements (provenance UNVERIFIED per 5A.6R5). [VERIFIED FROM SOURCE/TEST EVIDENCE]

## 3. Existing AJ behavior versus proposed policy (summary)

| Area | Existing behavior (source/test-evidenced where noted) | Proposed policy direction | Compatibility note |
|---|---|---|---|
| Delegation child requirement semantics | `DelegationRequest.aggregation_policy` supports `all_required/any_sufficient/subset_required` and `required_child_ids` (`aj/delegation.py`). Child specs do not carry an explicit per-child required/optional field; "required" is derived from policy/ids. [PARTIALLY VERIFIED] | Explicit required/optional classification per child (or explicit derivation rule), no silent default to optional on missing/malformed classification. [PROPOSED POLICY] | Current model can partially represent via `required_child_ids`/policy but lacks explicit per-child classification field and strict malformed-classification handling. [PARTIALLY VERIFIED] |
| Parent completion/lifecycle | `aggregate_parent_progress` computes counts/can_complete/manual_review; `Aj._before_task_transition` blocks delegation-parent `COMPLETED` when aggregation unsafe/unverifiable (`aj/orchestrator.py`, `aj/delegation.py`). [PARTIALLY VERIFIED] | Failed/cancelled/unresolved/ambiguous required child outcomes prevent successful parent completion unless explicitly defined policy permits; contradictions never silently yield success. [PROPOSED POLICY] | Largely aligned in guard intent for covered cases; not exhaustively enforced across all paths/policies/outcomes. [PARTIALLY VERIFIED] |
| Partial completion | No dedicated `PARTIAL` task lifecycle state; aggregation exposes counts/waiting/can_complete/manual_review and child statuses. [VERIFIED FROM SOURCE/TEST EVIDENCE] | `PARTIAL` must not be confused with `SUCCESS`; safest default is not a first-class success state without explicit support/policy. [PROPOSED POLICY] | No new status/enum authorized; partiality can only be represented via evidence/aggregation/reporting within existing model. [PARTIALLY VERIFIED] |
| Cancellation | Task states include `CANCELLED`, `CANCEL_REQUESTED`; `Aj.cancel_task/_cancel_locked`, `TaskStore.cancel/transition` exist; scheduler treats active/cancel-requested conservatively; 5A.6R4 added prep/guard blocks for cancelled/unverifiable parent delegation authority. [PARTIALLY VERIFIED] | Durably observed parent cancellation blocks prohibited new delegated prep/dispatch; running work may need cooperative cancel; no instant-stop claim for external side effects; races/late outcomes must not silently invalidate authoritative outcomes; recovery must not resurrect prohibited work; ambiguity remains unresolved. [PROPOSED POLICY] | Partially compatible in covered boundaries; full orchestration, child-cancel verification, all races/recovery paths unproven. [PARTIALLY VERIFIED] |
| Crash/recovery | `RecoveryManager`/`Aj._assess_recovery/recover/recovery_inspection` are conservative/fail-closed in intent; stores append-only with fail-closed persistence behavior; cross-store non-atomicity and NTFS/SQLite-WAL risk documented. [PARTIALLY VERIFIED] | Bounded, honesty-first recovery contract by declared persistence boundary; ambiguous states never become success; unsupported windows classified unresolved/unsupported. [PROPOSED POLICY] | Compatible in intent; demonstrated restart/persistence-boundary evidence incomplete (A–H). [UNVERIFIED]/[OPEN ISSUE] |
| Concurrency/process boundary | In-process locks/guards exist (RLock/thread-local/file locks/lease coordination) in various components; scheduler/dispatch bounded in-process; tests include barrier-based in-process concurrency in covered cases. [PARTIALLY VERIFIED] | Conservative boundary: local AJ, single process, only explicitly demonstrated concurrent operations safe; no multi-process/distributed correctness claims. [PROPOSED POLICY] | Aligned with honest limits; actual support beyond in-process covered cases unproven. [UNVERIFIED] |
| Unknown/ambiguous state | Many paths fail closed (storage errors, invalid transitions, unverifiable auth/delegation/lease states in covered code); aggregation/monitors surface some uncertainties/manual-review. [PARTIALLY VERIFIED] | Unknown/missing/contradictory/unverifiable state must never silently become successful state (cross-cutting). [PROPOSED POLICY] | Generally compatible as intent; exhaustive proof across all records/paths lacking. [PARTIALLY VERIFIED] |

## 4. Policy Area A — Child requirement and failure semantics

### 4.1 Definitions (proposed)
- **Required child:** child whose successful, evidenced completion is necessary for parent completion under the declared aggregation/completion policy. [PROPOSED POLICY]
- **Optional child:** child whose failure/cancellation/non-completion may be tolerated only if all required children satisfy the completion policy and policy explicitly allows it. [PROPOSED POLICY]
- **Missing requirement classification:** no explicit/derivable required-vs-optional classification for a child/spec. [PROPOSED POLICY]
- **Invalid requirement classification:** classification present but malformed, contradictory, or unsupported by policy/schema. [PROPOSED POLICY]
- **Successful child:** child task reached `COMPLETED` with consistent, verifiable evidence (per supported model). [PROPOSED POLICY] / [PARTIALLY VERIFIED] (task status exists)
- **Failed child:** child reached terminal-bad failure outcome (e.g. `FAILED`/`ABORTED`/`DEAD_LETTER` depending on policy mapping) with recorded evidence. [PROPOSED POLICY] / [PARTIALLY VERIFIED]
- **Cancelled child:** child reached `CANCELLED` (or explicitly evidenced cancellation outcome) per supported lifecycle. [PROPOSED POLICY] / [PARTIALLY VERIFIED]
- **Unresolved child:** child not in a final, policy-satisfied outcome (e.g. pending/running/waiting/blocked/non-terminal) or completion evidence incomplete. [PROPOSED POLICY]
- **Ambiguous child outcome:** outcome cannot be determined safely from trusted evidence (conflicting records, unknown/uncertain execution, missing linkage/evidence, unverifiable state). [PROPOSED POLICY]

### 4.2 Evaluation of proposed default
1. Explicit required/optional classification per child: **compatible in intent** but **not explicitly represented** per child spec in current delegation contract (classification currently implicit via `aggregation_policy`/`required_child_ids`). [PROPOSED POLICY] [PARTIALLY VERIFIED]
2. Missing/malformed classification must not silently default to optional: **safer than current implicit behavior**; current request validation/aggregation can fail closed in some malformed cases but explicit per-child classification validation is not implemented as proposed. [PROPOSED POLICY] [UNVERIFIED]
3. Failed required child prevents successful parent completion: **aligned** with aggregation/guard intent (`is_terminal_bad`/manual-review/can_complete logic, completion guard). [PARTIALLY VERIFIED]
4. Cancelled required child prevents successful parent completion unless explicitly approved parent-cancellation policy governs outcome: **partially aligned** (cancelled treated as non-success in aggregation paths; explicit approved parent-cancellation outcome policy not fully defined/enforced). [PROPOSED POLICY] [PARTIALLY VERIFIED]
5. Unresolved required child prevents successful parent completion: **aligned** in covered aggregation/guard behavior. [PARTIALLY VERIFIED]
6. Optional child failure may permit parent completion only when all required children satisfy policy: **partially aligned** for `any_sufficient`/`subset_required`/`all_required` semantics in aggregation, but optional/required semantics not exhaustively specified/certified. [PARTIALLY VERIFIED]
7. Optional failures must remain visible in parent evidence/reporting: **partially supported** (child statuses/counts/details/history/evidence can be exposed) but not guaranteed as a formal requirement in all reports. [PARTIALLY VERIFIED]

### 4.3 Existing model/code paths and limitations
- **Data model:** `TaskRecord.status` lifecycle (`aj/task.py`); `DelegationRequest/DelegationRecord` (policy, `required_child_ids`, child specs/refs), `AssignmentRecord`, aggregation in `aggregate_parent_progress` (`aj/delegation.py`); parent-child linkage via task fields/delegation records. [VERIFIED FROM SOURCE/TEST EVIDENCE]
- **Code paths:** `Aj.delegate`, `_prepare_delegated_child_for_scheduling`, `_reconcile_delegation_parent`, `_before_task_transition`, `delegation_status/monitor`, `aggregate_parent_progress`. [VERIFIED FROM SOURCE/TEST EVIDENCE]
- **Limitations (no implementation):** no explicit per-child required/optional field; no distinct task states for "unresolved/ambiguous/partial/successful-vs-failed-completion" beyond existing statuses; cancelled-required-child outcome under parent cancellation policy not explicitly modeled/enforced; missing/malformed classification semantics not fully specified/validated per proposed rule. [UNVERIFIED]/[UNSUPPORTED] (as proposed)

## 5. Policy Area B — Partial completion

### 5.1 Definitions (proposed)
- **Successful completion:** all policy-required outcomes satisfied with verified, non-ambiguous evidence; parent may reach `COMPLETED` only when allowed. [PROPOSED POLICY]
- **Failed completion:** required completion cannot be satisfied due to failed/invalid outcomes under policy (terminal failure representation per existing lifecycle/policy). [PROPOSED POLICY]
- **Partial outcome:** some work completed but completion policy for the governed scope is not fully satisfied and not cleanly failed/cancelled/unresolved in a way that maps to existing terminal success. [PROPOSED POLICY]
- **Cancelled outcome:** work ended due to cancellation per supported lifecycle/evidence. [PROPOSED POLICY]
- **Unresolved outcome:** no final authoritative outcome yet or evidence insufficient. [PROPOSED POLICY]

### 5.2 Current representation (existing model)
- **Task statuses available:** `RECEIVED, UNDERSTANDING, PLANNED, WAITING_FOR_APPROVAL, AUTHORIZED, EXECUTING, VERIFYING, COMPLETED, FAILED, RECOVERING, RETRYING, ESCALATED, ABORTED, CANCELLED, RECOVERY_REQUIRED, CANCEL_REQUESTED, BLOCKED, DEAD_LETTER`. [VERIFIED FROM SOURCE/TEST EVIDENCE]
- **No `PARTIAL` status/enum** in task lifecycle. [VERIFIED FROM SOURCE/TEST EVIDENCE]
- Aggregation can represent partiality via `counts`, `waiting_for_children`, `can_complete=false`, child detail statuses (`aggregate_parent_progress`). [PARTIALLY VERIFIED]

### 5.3 Recommendation (safest, compatibility-first)
- **`PARTIAL` must not be confused with `SUCCESS`.** [PROPOSED POLICY]
- **Recommended default for current baseline:** **partial completion is NOT supported as a first-class task status** and must not map to `COMPLETED`. Partiality may be represented only as **non-terminal/unresolved/manual-review/failure evidence in aggregation/reporting** according to explicit policy, or treated as not-success until policy-required outcomes are satisfied. [PROPOSED POLICY]
- **Allowed only when explicitly configured/supported:** only if future approved policy defines exact semantics and a compatible representation without inventing unauthorized states in this phase; **not supported in current baseline as a success-equivalent**. [PROPOSED POLICY] [UNSUPPORTED]
- **Compatibility:** avoids introducing new enum/status; relies on existing aggregation/evidence and fail-closed completion guard. [PARTIALLY VERIFIED]

## 6. Policy Area C — Cancellation semantics

### 6.1 Definitions (proposed)
- **Parent cancellation request:** intent to cancel parent/delegated scope initiated (may be represented by transition/request handling depending on supported path). [PROPOSED POLICY]
- **Persisted parent cancellation:** cancellation state durably recorded and observable at authorization/preparation/dispatch boundaries. [PROPOSED POLICY]
- **Child preparation:** progression/authorization-prep of delegated child toward schedulable states (`_prepare_delegated_child_for_scheduling`, related transitions) without dispatch. [VERIFIED FROM SOURCE/TEST EVIDENCE]
- **Child dispatch:** scheduler/admission-selected handoff to execution boundary (`Scheduler` → `Aj.resume(..., leased=True)` → execute paths). [PARTIALLY VERIFIED]
- **Already-running child execution:** child/task/execution in active in-flight states (`EXECUTING/VERIFYING` etc.) or with active execution ownership/lease evidence. [PARTIALLY VERIFIED]
- **Child completion racing with parent cancellation:** concurrent/near-concurrent completion and cancellation transitions/observations. [PROPOSED POLICY]
- **Recovery after cancellation:** recovery/reconciliation actions taken when cancellation and child outcomes may be incomplete/ambiguous. [PROPOSED POLICY]
- **Late child outcome after cancellation:** child result/evidence arriving or observed after cancellation recorded/requested. [PROPOSED POLICY]

### 6.2 Evaluation of proposed policy
1. Once durably observed at authorization/preparation/dispatch boundary, prohibited new delegated prep/dispatch must be rejected: **partially supported** (5A.6R4 prep fail-closed and delegated guard checks for cancelled/unverifiable parent authority in covered paths). [PARTIALLY VERIFIED]
2. Already-running work may require cooperative cancellation: **consistent with honest limits**; AJ has `CANCEL_REQUESTED` semantics and cannot claim forced stop of arbitrary/external execution. [PARTIALLY VERIFIED]
3. Must not claim instant stop of external side effect: **aligned** with no real external transport and evidence-honest posture. [VERIFIED FROM SOURCE/TEST EVIDENCE] (no external transport implemented)
4. Child completing concurrently with cancellation must not silently overwrite/invalidate authoritative parent cancellation outcome: **not proven**; race safety unverified. [UNVERIFIED]
5. Late child results must remain traceable: **partially supported by append-only/evidence/history concepts** but not explicitly guaranteed by tested policy in all cases. [PARTIALLY VERIFIED]
6. Recovery must not resurrect prohibited work without valid explicit policy: **aligned in intent** with conservative recovery/fail-closed behavior; not exhaustively proven. [PARTIALLY VERIFIED]
7. Ambiguous cancellation outcomes must remain unresolved rather than success: **aligned with proposed cross-cutting invariant**; not exhaustively proven. [PROPOSED POLICY] [UNVERIFIED]

### 6.3 Existing support and gaps
- **Supported/observed paths:** `cancel_task/_cancel_locked`, task transitions to `CANCEL_REQUESTED/CANCELLED` where allowed, scheduler eligibility excludes active/cancel-requested/uncertain states in cases, 5A.6R4 `_prepare_delegated_child_for_scheduling` and `_delegated_permission_guard` block under cancelled/revoked/unverifiable parent authority. [PARTIALLY VERIFIED]
- **Gaps/unverified:** end-to-end parent-cancel orchestration (stop all future required child creation/dispatch, request/verify child cancellation), child-completion vs parent-cancel races, recovery-after-cancel resurrection prevention in all paths, late-outcome handling guarantees. [UNVERIFIED]

## 7. Policy Area D — Crash and recovery boundary

### 7.1 Operating boundaries evaluated (separately)
| Boundary | Realistic support (proposed classification) | Notes |
|---|---|---|
| AJ process termination and restart | **PARTIALLY VERIFIED / PROPOSED POLICY (bounded)** | Conservative recovery/scan/inspection exists; restart-proof for all delegation windows not demonstrated. |
| Process interruption during a persisted transition | **UNVERIFIED** | Depends on which store persisted and cross-store ordering; non-atomic. |
| Incomplete operation recovery | **PARTIALLY VERIFIED** | Intent/evidence/incomplete detection concepts exist in broader system; delegation windows A–H not fully certified. |
| Independent-store persistence interruption | **UNVERIFIED / OPEN ISSUE** | Cross-store non-atomicity; ambiguity must fail closed. |
| OS crash | **UNVERIFIED / UNSUPPORTED (unproven)** | No demonstrated restart/persistence-boundary evidence across stores. |
| Power loss | **UNVERIFIED / UNSUPPORTED (unproven)** | Same as OS crash; storage durability unknown. |
| Filesystem I/O failure | **PARTIALLY VERIFIED / OPEN ISSUE** | Fail-closed persistence behavior in stores; NTFS/SQLite-WAL sensitivity OPEN. |
| Database/WAL failure | **OPEN ISSUE / UNVERIFIED** | SQLite/WAL reliability issue unresolved (doc 49). |
| Multi-process recovery | **UNSUPPORTED (unproven)** | No demonstrated multi-process recovery correctness. |

### 7.2 Proposed explicitly bounded recovery contract
- **Supported (only if demonstrated per boundary):** recovery decisions/inspections that can be justified from durable, consistent, available evidence within a single local AJ process and declared store/persistence assumptions; detection of incomplete/ambiguous states; explicit fail-closed/manual-review outcomes. [PROPOSED POLICY]
- **Not promised:** universal recovery across arbitrary process/machine/OS/power/filesystem/db failures or across independent-store atomic boundaries. [PROPOSED POLICY]

For each proposed supported boundary, required elements (to be established before certification): persistence assumptions, required durable evidence, recovery preconditions, ambiguous-state handling (must not become success), relevant tests (incl. restart/boundary), and known limitations. [PROPOSED POLICY] [UNVERIFIED]

### 7.3 Open issues/constraints
- SQLite/WAL reliability **OPEN**; observed **576 passed / 1 failed, 13 warnings** with intermittent `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (`sqlite3.OperationalError: disk I/O error`, NTFS-backed tmp/WAL+fork context) not conclusively diagnosed; **must not be dismissed**, tests not weakened, filesystem not modified. [OPEN ISSUE] [VERIFIED FROM SOURCE/TEST EVIDENCE]
- Cross-store non-atomicity: task/delegation/assignment/execution/lease/receipt/journal/evidence stores not atomically committed. [VERIFIED FROM SOURCE/TEST EVIDENCE]

## 8. Policy Area E — Concurrency and process boundary

### 8.1 Audit of actual support (conservative)
| Mode | Assessment | Evidence/notes |
|---|---|---|
| Sequential execution | **PARTIALLY VERIFIED** | Core flows operate sequentially in many paths; broad correctness still depends on invariants. |
| Concurrent calls within one process | **PARTIALLY VERIFIED** | In-process locks/guards/barrier-tested cases exist (e.g. reconciliation concurrency test); not universal. |
| Thread-level concurrency | **PARTIALLY VERIFIED** | Threading primitives/ThreadPoolExecutor usage in scheduler/components; safety not universally proven. |
| Multiple worker processes | **UNVERIFIED / UNSUPPORTED** | No demonstrated correctness; multiprocessing used in tests/fork contexts but not a certified runtime model. |
| Multiple AJ instances | **UNSUPPORTED** | No multi-instance coordination/correctness demonstrated. |
| Distributed coordination | **UNSUPPORTED** | Explicitly out of scope/not implemented. |

Do not infer support from presence of locks/IDs/tests alone. [VERIFIED FROM SOURCE/TEST EVIDENCE]

### 8.2 Conservative initial acceptance boundary (proposed)
- Local AJ operation, **single AJ process**, and only those concurrent operations whose safety is **explicitly demonstrated** by reproducible evidence within declared bounds. No multi-process or distributed correctness claims. [PROPOSED POLICY]

### 8.3 Race conditions remaining unverified
- Child completion vs parent cancellation, recovery vs scheduler dispatch, concurrent child transitions affecting same parent, mutating reconciliation races beyond covered in-process cases, stale-writer overwrite across all interleavings/stores, duplicate apply under races, concurrent assignment/execution mutations, multi-process access. [UNVERIFIED]

No new locking/synchronization proposed/implemented. [PROPOSED POLICY]

## 9. Policy Area F — Authorization entry-point inventory (read-only source audit)

**Scope note:** "Supported" below means implemented/traceable in current source; **not** a claim of verified correct enforcement. Universal enforcement is **not claimed**. [PARTIALLY VERIFIED]

| # | Path | Exact file and function/method | Entry conditions (summary) | Authorization checks | Current-state revalidation | Permission narrowing | Cancellation enforcement | Evidence produced | Test coverage (observed) | Remaining gaps |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Initial handle/request execution | `aj/orchestrator.py` — `Aj.handle` (L247), `_execute` (L1294), `_capability_blocker` (L1276), `_compute_authorization_context` (L1947), `_delegated_permission_guard` (L3835) | Request routed to capability/spec; task progressed/authorized per flow; executes via `_execute` | Capability/policy/authorizer and state checks in handle/execute path; delegated guard applied in `_execute` when delegation context present | Delegated guard revalidates current parent/delegation linkage/status and recorded snapshots in covered cases (5A.6R4) | Uses recorded delegation permission decision/snapshots; narrowing validated at guard boundaries | Guard blocks delegated exec under cancelled/revoked/unverifiable parent authority; not all cancel semantics enforced globally | Task events/status, attempts, receipts/journal/audit/memory hooks (path-dependent) | Broad general tests exist; delegation-specific handle-path certification limited | Exhaustive delegated-context coverage on all handle variants/entry states unproven |
| 2 | Scheduler dispatch | `aj/scheduler.py` — `Scheduler.evaluate_eligibility`, `_run_one`, `run_once` etc.; dispatches via `Aj.resume(task_id, leased=True)`; `aj/orchestrator.py` — `Aj.resume` (L2036), `_resume_locked` (L2042), `_execute` (L1294) | Task eligible/admitted (AUTHORIZED, deps/capacity/persistence/lease checks conservative) | Resume path performs capability/policy/stale-auth checks; `_resume_locked` and `_execute` apply delegated guard | Guard performs current-state checks (parent/delegation status/linkage) and snapshot consistency | Delegated envelope narrowing/snapshot checks in guard | Cancelled/unverifiable parent authority blocked by guard/prep (prep separate); eligibility excludes some active/cancel states | Scheduler decision/dispatch evidence, lease/execution/task/attempt/receipt/journal (as implemented) | 5A.5 scheduler tests + 5A.6R4 guard tests (indirect/bounded) | Eligibility not fully delegation-parent-cancel aware; all dispatch races unproven |
| 3 | Direct/leased resume | `aj/orchestrator.py` — `Aj.resume` (L2036), `_resume_locked` (L2042), `_execute` (L1294) | Task resumable (e.g. AUTHORIZED) with valid context/lease as applicable | Capability/policy/stale-authorization handling; delegated guard before execute and in execute | Current-state delegation/parent checks in guard | Guard snapshot/narrowing checks | Guard blocks cancelled/revoked/unverifiable authority | Execution/attempt/task/receipt/journal evidence | Covered in scheduler/integration contexts; specific resume+revocation cases limited | Post-assignment revocation across all contexts not exhaustively tested |
| 4 | Retry | `aj/orchestrator.py` — `Aj.retry` (L477), `_retry_locked` (L481), `_execute` (L1294) | Task FAILED, retry budget/capability retry-safety/approval constraints | Retry gating (status, max attempts, `retry_safe`, etc.); executes through `_execute` guard | Execute-boundary guard revalidates at execution time (covered) but not all revocation scenarios certified | Guard checks recorded envelopes/snapshots | Guard may block if authority revoked/cancelled; retry-specific cancellation semantics not fully certified | New attempt/execution/receipt/journal/task updates as applicable | General retry tests exist; delegated-revocation-on-retry not exhaustively certified | Exhaustive authz revocation/revalidation on retry unproven |
| 5 | Recovery (explicit task recovery) | `aj/recovery.py` — `RecoveryManager.recover/scan/_recover_one`, `classify`; `aj/orchestrator.py` — `Aj.recover` (L666), `_recover_locked` (L988), `_assess_recovery` (L782), `recovery_inspection` (L2419) | Non-terminal task; evidence-based assessment/classification | Recovery is conservative/fail-closed by assessment; may resume/execute via guarded paths depending on decision | When routed to resume/execute, guard applies; assessment itself not a delegated-permission revalidation engine | No separate delegated narrowing beyond guarded execution paths | Cancellation/recovery interactions not exhaustively certified for delegated cases | Recovery findings/outcomes, inspection evidence, task/journal/receipt effects when actions taken | Recovery tests exist broadly; delegated recovery-after-revocation/cancel races limited | All recovery-triggered execution outcomes and delegated ambiguity cases unproven |
| 6 | Delegation creation/assignment (logical) | `aj/orchestrator.py` — `Aj.delegate` (L4230), `_ensure_delegation_stores`, `_seed_logical_agents`, `_prepare_delegated_child_for_scheduling` (L3924); `aj/delegation.py` — validation/matching/narrowing/stores | Valid delegation request/config, parent valid/non-terminal, bounds/capability match satisfied | Request/schema/bounds validation, hierarchy checks, capability matching, `narrow_permissions` (intersection fail-closed), idempotency/conflict handling | Parent existence/state checked; prep rechecks parent authority/cancellation before advancing child | `narrow_permissions` computed and recorded in assignment/child delegation context | Prep aborts/fails closed for cancelled/revoked/unverifiable parent; no dispatch performed by delegate | Delegation/assignment/child task records, journal event, status/aggregation | 5A.6/5A.6R/R2/R3/R4 delegation tests (focused) | No real external assignment acceptance; full policy semantics (explicit required/optional) incomplete |
| 7 | Delegated child preparation (scheduling-adjacent) | `aj/orchestrator.py` — `_prepare_delegated_child_for_scheduling` (L3924) | Delegated child task in preparable states; parent/delegation context present | Implicitly relies on task transition validity and existing auth/planning flow; blocked if parent cancelled/revoked/unverifiable | Current parent state rechecked; child aborted/fail-closed when authority invalid | Preserves recorded delegation context (no widening) | Explicit fail-closed on cancelled/revoked/unverifiable parent (5A.6R4) | Task state transitions/persistence, preparation result | 5A.6R4 test covers cancelled-parent block | Not a dispatch path; not exhaustive for all cancellation/creation cases |
| 8 | Reconciliation (parent aggregation/lifecycle) | `aj/orchestrator.py` — `reconcile_delegation_parent` (L3820), `_reconcile_delegation_parent` (L4030), `_on_task_transition` (L3782), `_before_task_transition` (L3733), `delegation_status` (L4183), `delegation_monitor` (L4197); `aj/delegation.py` — `aggregate_parent_progress`, `detect_delegation_anomalies` | Delegation-related parent/child transitions or explicit reconcile call | Completion guard prevents unsafe parent `COMPLETED`; reconciliation computes/stores aggregation evidence; monitor/status read-only | Aggregation computed from current task/record state; guard checks current aggregation; anomaly detection best-effort reads | No permission widening; reconciliation not an execution grant | Parent cancel states influence aggregation/guard; no dispatch performed by reconcile | Delegation evidence/history/provenance, pending markers, monitor/status outputs | 5A.6R2/R3/R4 tests (idempotency, dry-run/apply, detection, guard cases) | Does not enforce all parent policy outcomes; apply/remediation limited; no cross-store atomicity |
| 9 | Cancel (task) | `aj/orchestrator.py` — `Aj.cancel_task` (L607), `_cancel_locked` (L611), `Aj.cancel` (L663); `aj/task.py` — `TaskStore.cancel/transition` | Task in cancellable/valid transition state per lifecycle rules | Lifecycle transition validity; lease/operation coordination as applicable | State-based transition checks | N/A | Moves to `CANCELLED` or `CANCEL_REQUESTED` per rules; cannot forcibly stop running external execution | Task events/status persistence, receipts/journal/audit as applicable | General cancel tests exist; delegated parent-cancel orchestration not fully certified | Full delegated child-cancel propagation/verification and race handling unproven |
| 10 | Dead-letter | `aj/orchestrator.py` — `Aj.dead_letter` (L2244) | Eligible task/state per implementation policy | Lifecycle/transition checks (fail-closed by task rules) | Current task state required | N/A | Terminal/administrative outcome handling; interaction with delegation/cancel policies not exhaustively certified | Task transition/evidence | Limited specific coverage noted | Delegated-policy interactions unverified |
| 11 | Requeue/abandon/operator reconcile (administrative) | `aj/orchestrator.py` — `requeue` (L3408), `abandon` (L3467), `reconcile` (L2864), `consistency_check` (L3371), `storage_diagnostics` (L3391) | Explicit operator/administrative invocation with preconditions | State/evidence/operation-specific checks (conservative intent) | Reads current records/evidence; mutating ops bounded | N/A unless delegated execution triggered (not primary purpose) | Cancellation/lifecycle side effects depend on operation; not delegation-orchestration paths | Evidence/provenance records for reconciliation/ops | Varies; not delegation-exhaustive | May affect task states; interactions with delegated authz/cancel invariants not exhaustively certified |

**Inventory conclusion:** implemented/traceable entry points identified above; **universal authorization/current-state revalidation/cancellation enforcement across every supported or alternative path is UNVERIFIED**. [PARTIALLY VERIFIED]

## 10. Policy Area G — Unknown and ambiguous states

### 10.1 Proposed cross-cutting invariant
**Unknown, missing, contradictory, or unverifiable state must never silently become successful state.** [PROPOSED POLICY]

### 10.2 Analysis against record/state domains
| Domain | Current posture | Observed gaps / cannot yet prove |
|---|---|---|
| Execution records | Execution domain and scheduler/dispatch use conservative/uncertain handling in places; ambiguous/unknown states should block unsafe dispatch/completion. [PARTIALLY VERIFIED] | Not every ambiguous execution outcome in delegated recovery/retry paths certified (e.g. scenario 25 UNTESTED). [UNVERIFIED] |
| Delegation records | Validation and guard checks fail closed on missing/unverifiable delegation in covered paths; anomalies detected read-only. [PARTIALLY VERIFIED] | Full remediation/certification and all linkage inconsistencies not proven. [UNVERIFIED] |
| Parent-child links | Hierarchy validation and orphan/missing-provenance/disagreement detectors exist; guard checks linkage. [PARTIALLY VERIFIED] | Not all linkage/anomaly cases exhaustively certified. [UNVERIFIED] |
| Authorization records | Delegated guard fails closed on missing/invalid/malformed/revoked-unverifiable evidence in covered cases. [PARTIALLY VERIFIED] | Snapshot-only limits, post-assignment revocation and all paths not exhaustively proven. [UNVERIFIED] |
| Reconciliation evidence | Snapshot/hash/history/provenance recorded; pending markers and stale/contradiction detection exist. [PARTIALLY VERIFIED] | Cross-store interruption windows and complete recovery honesty unproven (A–H). [UNVERIFIED] |
| Cancellation records | Lifecycle states/transitions recorded; some fail-closed boundaries added. [PARTIALLY VERIFIED] | Races, late outcomes, resurrection prevention across all recovery paths unproven. [UNVERIFIED] |
| Recovery records | Recovery inspection/classification conservative; fail-closed on assessment errors in places. [PARTIALLY VERIFIED] | Ambiguous recovery outcomes in all delegated contexts not certified. [UNVERIFIED] |
| Terminal lifecycle states | Task FSM blocks illegal transitions; completion guard blocks unsafe delegation-parent COMPLETED in covered cases. [PARTIALLY VERIFIED] | Contradictory terminal regressions/races and all terminal-policy mappings not exhaustively proven. [UNVERIFIED] |

**Current behaviors that cannot yet prove invariant universally:** any path where current-state authorization is not revalidated, where cancellation/race/recovery can race without proof, where cross-store interruption yields ambiguous but unhandled outcomes, or where detection exists without certified safe handling/remediation. [UNVERIFIED]

No fixes implemented. [PROPOSED POLICY]

## 11. Compatibility analysis with existing code
- **Compatible/aligned:** fail-closed posture in many validators/guards/stores; append-only evidence/history patterns; explicit task lifecycle FSM; delegation aggregation/guard concepts; scheduler conservative eligibility; no external transport; reuse of existing stores/scheduler/lease/execution foundations. [PARTIALLY VERIFIED]
- **Partially compatible (needs explicit policy + evidence):** required/optional child semantics, cancelled-required-child handling, partial outcome representation, cancellation orchestration/races/late outcomes, crash-boundary recovery guarantees, concurrency/process support boundaries, universal authz entry-point enforcement, cross-cutting unknown→non-success proof. [PARTIALLY VERIFIED]
- **Incompatible/unsupported as stated in current baseline without further work:** first-class `PARTIAL` success-like status, universal crash recovery, multi-process/distributed correctness, authenticated identity from `local_trust`, exactly-once/cross-store atomicity claims, real remote agent transport/acceptance. [UNSUPPORTED]
- **No new lifecycle states/enums implemented or authorized by this proposal.** [PROPOSED POLICY]

## 12. Missing implementation capabilities (relative to proposed policy, not authorized)
- Explicit per-child required/optional classification and strict validation (no silent default). [UNVERIFIED]
- Explicit, enforced parent outcome policy for failed/cancelled required children and partial outcomes (without new unauthorized states). [UNVERIFIED]
- Complete parent-cancellation orchestration: prevent all prohibited future child creation/prep/dispatch, request/verify child cancellation, race-safe reconciliation. [UNVERIFIED]
- Exhaustive current-state authorization revalidation at every supported delegated execution/recovery/dispatch/administrative path (or explicit blocking of unsupported paths). [UNVERIFIED]
- Demonstrated crash-boundary recovery handling per supported boundary with restart/persistence evidence. [UNVERIFIED]
- Demonstrated concurrency/race/stale-writer safety within declared boundary. [UNVERIFIED]
- Certified anomaly remediation (beyond detection) where safe. [UNVERIFIED]

## 13. Missing test coverage (relative to proposed policy)
- Per-child classification missing/malformed/contradictory cases and policy outcomes. [UNVERIFIED]
- Cancelled-required-child outcome under explicit parent-cancel policy; all cancellation races and late outcomes. [UNVERIFIED]
- Exhaustive authz revocation/reduction/malformed/missing/stale contexts across every identified entry point (retry/recover/scheduler/alt/admin paths). [UNVERIFIED]
- Crash windows A–H with restart/persistence-boundary proofs on isolated storage; multi-process recovery (if ever in scope). [UNVERIFIED]
- Mutating concurrent races (child transitions, completion-vs-cancel, recovery-vs-dispatch, stale overwrite, duplicate apply) and multi-process cases. [UNVERIFIED]
- Ambiguous execution/lease/recovery outcomes and unknown→success prevention across all domains. [UNVERIFIED]
- Stable reproduction/diagnosis and disposition evidence for SQLite/WAL full-suite failure. [OPEN ISSUE]

## 14. Recommended exact policy definitions (proposed, for approval)
1. **Child classification:** every delegated child/spec MUST have explicit required/optional classification (or an explicitly approved deterministic derivation recorded in contract/evidence). Missing, malformed, contradictory, or unsupported classification MUST fail closed and MUST NOT default to optional. [PROPOSED POLICY]
2. **Required-child outcomes:** failed, cancelled (unless explicitly approved parent-cancellation policy states otherwise with evidenced conditions), unresolved, or ambiguous required-child outcomes MUST prevent successful parent completion. [PROPOSED POLICY]
3. **Optional-child outcomes:** optional failures/cancellations MAY allow parent completion only when all required children satisfy the approved completion policy and outcomes remain visible in evidence/reporting. [PROPOSED POLICY]
4. **Partial completion:** no `PARTIAL` task status/success mapping in current baseline. Partial outcomes MUST be represented as non-success (unresolved/manual-review/failed per policy) with explicit evidence; never treated as `COMPLETED`. [PROPOSED POLICY]
5. **Cancellation:** durably observed parent cancellation at any authorization/preparation/dispatch boundary MUST reject prohibited new delegated preparation/dispatch. Running work is cooperative at best; AJ MUST NOT claim instant external side-effect stop. Cancellation-vs-completion races, late outcomes, and recovery MUST be evidence-preserving and fail closed on ambiguity; prohibited work MUST NOT be resurrected without explicit approved policy. [PROPOSED POLICY]
6. **Recovery boundary:** only explicitly demonstrated, bounded boundaries are "supported"; each requires stated persistence assumptions, durable evidence, preconditions, and ambiguous→non-success handling. OS crash/power loss/multi-process/universal recovery NOT claimed. SQLite/WAL remains OPEN. [PROPOSED POLICY] [OPEN ISSUE]
7. **Concurrency boundary:** local, single-AJ-process only; only explicitly demonstrated concurrent operations certified. No multi-process/distributed correctness claims. [PROPOSED POLICY]
8. **Authorization scope:** every supported delegated preparation/assignment/authorization/dispatch/execution/retry/recovery/reconciliation/resume/administrative path MUST enforce fail-closed authorization and current-state revalidation, or be explicitly blocked/unsupported. [PROPOSED POLICY]
9. **Cross-cutting unknown-state rule:** unknown, missing, contradictory, or unverifiable state MUST NEVER silently become successful state in any domain (execution/delegation/linkage/authorization/reconciliation/cancellation/recovery/terminal lifecycle). [PROPOSED POLICY]

## 15. Open decisions requiring user approval
- Approve/revise Doc 52 and these policy definitions (and any versioned baseline update). [PROPOSED POLICY]
- Exact explicit per-child required/optional representation and derivation/validation rules compatible with existing model. [PROPOSED POLICY]
- Explicit policy for cancelled required children under parent cancellation (and partial/optional semantics). [PROPOSED POLICY]
- Authoritative list of "supported" authorization/dispatch/recovery entry points and which must be blocked if not enforceable. [PROPOSED POLICY]
- Declared supported crash/recovery and concurrency boundaries and acceptable evidence standard. [PROPOSED POLICY]
- Disposition/handling plan for OPEN SQLite/WAL full-suite failure (without test weakening/filesystem modification). [OPEN ISSUE]
- Whether/how to ratify reconstructed 45/A–J scenarios as supporting references under this baseline. [PROPOSED POLICY]

## 16. Risks and non-goals
- **Risks:** provenance of original 45/A–J remains unverified; over-claiming safety/certification from partial evidence; hidden bypass paths; cross-store ambiguity; NTFS/SQLite-WAL instability; race conditions under real concurrency/load. [OPEN ISSUE] [UNVERIFIED]
- **Non-goals (unchanged):** universal crash recovery, distributed transactions, exactly-once execution, multi-machine/distributed scheduler correctness, authenticated multi-user identity, real remote-agent transport, external side-effect guarantees, automatic JARVIS/HELIX/Hermes integration, Hermes gateway ensure, production-grade multi-tenant security certification. [UNSUPPORTED]

## 17. Final recommendation
- **Adopt (if approved) a strict, compatibility-first clarification set:** explicit child classification, fail-closed unknown/ambiguous→non-success, no PARTIAL-as-success in current baseline, bounded cancellation/recovery/concurrency claims, and enumerated+enforced-or-blocked authorization paths. [PROPOSED POLICY]
- **Before implementation planning:** obtain explicit user approval of clarified semantics/boundaries and resolve open decisions; treat all non-demonstrated behaviors as UNVERIFIED/UNSUPPORTED and keep SQLite/WAL OPEN. [PROPOSED POLICY]
- **Do not approve baseline or start implementation/5A.7** based on this document alone. [PROPOSED POLICY]
