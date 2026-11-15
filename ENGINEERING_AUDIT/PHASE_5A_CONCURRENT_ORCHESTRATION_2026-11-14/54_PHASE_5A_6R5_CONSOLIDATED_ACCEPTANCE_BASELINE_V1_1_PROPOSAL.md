# 54 — Phase 5A.6R5 Consolidated Acceptance Baseline v1.1 (Proposal)

**Date:** 2026-11-14  
**Phase:** 5A.6R5 (documentation, traceability, acceptance-contract only)  
**Status:** **PROPOSED — PENDING USER REVIEW AND APPROVAL**  
**Implementation authorization:** **NOT GRANTED**  
**Next phase:** **NOT AUTHORIZED** (no Phase 5A.7)  

**Classification key:** [VERIFIED] [PARTIALLY VERIFIED] [UNVERIFIED] [UNSAFE] [UNSUPPORTED] [PROPOSED POLICY] [OPEN ISSUE]  
*A proposed policy must not be classified as VERIFIED. Source existence is not demonstrated correctness.*

---

## 1. Executive summary
- **Option 3 selected by the user:** narrowed invariant-based acceptance baseline for AJ internal orchestration and delegation foundation. [PROPOSED POLICY]
- This document consolidates **Doc 52** (Proposed Narrowed Invariant Baseline v1.0) and **Doc 53** (Policy Semantics Clarification Proposal) into one coherent proposed engineering contract with recommended policy defaults, testable acceptance criteria for INV-01–INV-10, authorization entry-point inventory, and explicit gates. [PROPOSED POLICY]
- **No acceptance baseline has final approval. No implementation authorization granted.** Reconstructed scenarios 1–45 and crash windows A–J remain supporting references, not automatically binding original requirements (original provenance UNVERIFIED per 5A.6R5). [VERIFIED]/[PROPOSED POLICY]
- Current evidence (5A.6R4/5A.6R5): focused 5A.4–5A.6R4 suites 65 passed (last verified), `aj --check` 23/23 ok Hermes NOT ATTACHED; full suite latest observed **576 passed, 1 failed, 13 warnings** with SQLite/WAL issue **OPEN** (not conclusively diagnosed). [PARTIALLY VERIFIED]/[OPEN ISSUE]
- Acceptance requires explicit user approval (Gate A), then bounded plan (Gate B), separate implementation authorization (Gate C), reproducible verification (Gate D), and no mandatory invariant remaining PARTIALLY VERIFIED/UNVERIFIED/UNSAFE (Gate E). [PROPOSED POLICY]

## 2. Authority and relationship to Documents 52/53
| Document | Role | Status |
|---|---|---|
| `52_PHASE_5A_6R5_PROPOSED_NARROWED_INVARIANT_BASELINE_V1.md` | Proposed narrowed invariant baseline v1.0 (INV-01–INV-10 framing, boundaries, governance) | **Proposal** (not approved) [VERIFIED] |
| `53_PHASE_5A_6R5_POLICY_SEMANTICS_CLARIFICATION_PROPOSAL.md` | Policy semantics clarification, compatibility analysis, authz entry-point inventory, gaps/risks | **Proposal** (not approved) [VERIFIED] |
| `54_PHASE_5A_6R5_CONSOLIDATED_ACCEPTANCE_BASELINE_V1_1_PROPOSAL.md` (this doc) | Consolidated proposed acceptance contract incorporating recommended defaults and testable criteria | **Consolidated proposal** (not approved) [PROPOSED POLICY] |

- **Authority statements:** Option 3 selected by user. [PROPOSED POLICY] Docs 52/53 are proposals. [VERIFIED] Doc 54 is a consolidated proposal. [PROPOSED POLICY] No acceptance baseline has yet received final approval. [PROPOSED POLICY] No implementation authorization granted. [PROPOSED POLICY]
- **Traceability:** reconstructed scenarios 1–45 and crash windows A–J (`35`/`36` lineage) remain **supporting references** for test-design/failure-mode discovery/regression identification/evidence of uncovered behavior only; **not automatically binding original requirements** (provenance UNVERIFIED, 5A.6R5). [VERIFIED]

## 3. Scope and non-goals

### 3.1 Scope (acceptance target)
Restricted to AJ-internal, local orchestration/delegation foundation: task/execution orchestration, parent-child delegation, assignment and permission boundaries, child execution authorization, parent lifecycle enforcement, cancellation behavior, reconciliation/aggregation, recovery and anomaly detection, evidence/auditability, local AJ regression and operational checks. [PROPOSED POLICY]

### 3.2 Non-goals (explicit exclusions from this baseline)
Universal crash recovery across arbitrary process/machine failures; distributed transactions; exactly-once execution; multi-machine/distributed scheduler correctness; authenticated multi-user identity; real remote-agent transport; external service side-effect guarantees; automatic JARVIS/HELIX/Hermes integration; Hermes gateway ensure; production-grade multi-tenant security certification. These require separately approved scope/architecture decisions. [UNSUPPORTED]/[PROPOSED POLICY]

## 4. System and domain boundaries
- **Domain separation:** Task, Operation, Execution, Attempt, Agent (logical), Assignment, Lease, Delegation, Aggregation are distinct responsibilities; existing AJ execution/scheduling foundations reused, not duplicated. [PARTIALLY VERIFIED]
- **Operating boundary (proposed):** local AJ operation, single AJ process; only explicitly tested/demonstrated concurrent operations certified. No multi-process/distributed correctness guarantees. [PROPOSED POLICY]
- **Trust/identity:** `local_trust` is not authenticated operator identity. [VERIFIED]/[PROPOSED POLICY]
- **Storage:** append-oriented stores, fail-closed persistence behavior in covered code; no cross-store atomicity/exactly-once claims. NTFS/SQLite-WAL reliability OPEN. [PARTIALLY VERIFIED]/[OPEN ISSUE]
- **Integration:** JARVIS/HELIX/Hermes independent/untouched; Hermes NOT ATTACHED; `hermes.gateway.ensure` unimplemented/disabled/unexecuted. No external agent transport. [VERIFIED]

## 5. INV-01 through INV-10 (mandatory within declared supported boundaries)

> For each invariant: (1) description, (2) exact expected behavior, (3) existing implementation evidence, (4) missing implementation, (5) required positive tests, (6) required negative tests, (7) required lifecycle/race tests where applicable, (8) persistence/recovery assumptions, (9) explicit unsupported behavior, (10) acceptance verdict criteria.

### INV-01 — Authorization must fail closed
1. **Description:** Refuse delegated operations when required authorization state is missing, malformed, contradictory, revoked, or unverifiable. [PROPOSED POLICY]
2. **Exact expected behavior:** All supported delegated preparation/assignment/authorization/dispatch/execution/retry/recovery/reconciliation/resume entry points either enforce fail-closed authorization with current-state revalidation or are explicitly blocked/unsupported. Missing/invalid/revoked/malformed permission or delegation authority yields rejection (no unauthorized child execution) with traceable evidence where supported. [PROPOSED POLICY]
3. **Existing implementation evidence:** `_delegated_permission_guard` enforces recorded envelope/snapshot checks and (5A.6R4) current-state parent/delegation linkage/status checks in covered resume/execute paths; `_prepare_delegated_child_for_scheduling` blocks cancelled/revoked/unverifiable parent authority; `narrow_permissions`/request validation fail closed in covered cases; `Aj._capability_blocker`, authz context/stale checks exist. [PARTIALLY VERIFIED]
4. **Missing implementation:** exhaustive enforcement/revalidation across every supported/alternative/administrative path; dynamic revocation/current-trust revalidation beyond recorded/snapshot/local state in all cases; explicit blocking declarations for unsupported paths. [UNVERIFIED]
5. **Required positive tests:** authorized delegated execution succeeds only with valid, current, consistent delegation/permission/parent state on each supported path. [PROPOSED POLICY]
6. **Required negative tests:** missing/invalid/malformed/revoked delegation or permission data, parent-cancelled/revoked authority, missing linkage/record, widened or contradictory envelope rejected on every supported path. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** revocation/reduction after assignment vs dispatch/execute/retry/recover; cancellation observed at boundaries vs prep/dispatch. [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** authorization decisions rely on available durable records/evidence; unverifiable/missing state treated as non-authorized; no cross-store atomicity assumed. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** authenticated operator identity from `local_trust`; universal enforcement claim before all paths protected/blocked; external/dynamic IAM-style revocation proof. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only when every supported entry point is demonstrated fail-closed with current-state revalidation (or explicitly blocked) and negative/race cases pass with traceable evidence; otherwise PARTIALLY VERIFIED/UNVERIFIED/UNSAFE per evidence. [PROPOSED POLICY]

### INV-02 — Delegated permission narrowing
1. **Description:** Child delegation must never receive more authority than parent delegation permits. [PROPOSED POLICY]
2. **Exact expected behavior:** effective permissions are intersection/narrowing-only of permitted sources; expansion, missing/ambiguous permission data, or unverifiable narrowing fails closed; permission changes revalidated at relevant authorization boundaries. Snapshot equality alone insufficient. [PROPOSED POLICY]
3. **Existing implementation evidence:** `narrow_permissions` computes intersection and fails closed on missing/malformed contexts (`aj/delegation.py`); guard checks effective ⊆ requested/parent snapshots and logical-internal scope restrictions in covered cases. [PARTIALLY VERIFIED]
4. **Missing implementation:** explicit revalidation against current authoritative permission sources/changes at all boundaries; exhaustive path coverage; formal per-child classification integration with permission context. [UNVERIFIED]
5. **Required positive tests:** ordinary narrowing combinations produce correct effective subset and allow only permitted operations. [PROPOSED POLICY]
6. **Required negative tests:** permission expansion/widening, missing/ambiguous/malformed contexts, contradictory snapshots, tampered envelopes rejected. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** permission reduction/revocation after assignment before/at dispatch/execute/retry/recover/prep. [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** narrowing decisions/evidence durably recorded where supported; recovered state with unverifiable permissions fails closed. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** privilege escalation, implicit widening, claims of narrowing without boundary revalidation evidence. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only with demonstrated narrowing, boundary revalidation, and adversarial/lifecycle coverage across supported paths. [PROPOSED POLICY]

### INV-03 — Parent lifecycle correctness
1. **Description:** Parent must not be marked successfully complete while required child work is unresolved or violates declared completion policy. [PROPOSED POLICY]
2. **Exact expected behavior:** pending/running/failed/cancelled/unresolved/ambiguous required child outcomes prevent parent `COMPLETED` unless an explicitly approved policy with evidenced conditions permits (none assumed). Contradictory/missing child evidence cannot silently yield success. Optional failure/partial/cancellation semantics must be explicitly defined before certification. [PROPOSED POLICY]
3. **Existing implementation evidence:** `aggregate_parent_progress` computes `can_complete`/`requires_manual_review`/counts across policies; `Aj._before_task_transition` blocks delegation-parent `COMPLETED` when aggregation unsafe/unverifiable in covered cases; reconciliation hook/evidence updates exist. [PARTIALLY VERIFIED]
4. **Missing implementation:** explicit per-child required/optional classification enforcement (no silent optional default), complete policy mapping for failed/cancelled-required/partial outcomes, exhaustive enforcement across all transition/entry paths and policies. [UNVERIFIED]
5. **Required positive tests:** parent completes only when all policy-required children have verified successful outcomes and no manual-review/ambiguity. [PROPOSED POLICY]
6. **Required negative tests:** pending/running/failed/cancelled/unresolved/ambiguous required child, contradictory/missing evidence, malformed classification prevent COMPLETED. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** child completion/failure/cancel vs parent completion/reconciliation/cancellation; terminal regression attempts. [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** lifecycle decisions based on consistent durable task/delegation/evidence state; ambiguity/unverifiable state blocks success. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** PARTIAL mapped to SUCCESS/COMPLETED; silent default to optional on missing/malformed classification; false completion under uncertainty. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only when declared completion/cancellation/optional/partial policies are explicit, implemented, and demonstrated across supported paths/races without false success. [PROPOSED POLICY]

### INV-04 — Cancellation safety
1. **Description:** Cancellation must prevent prohibited future delegated preparation and execution. [PROPOSED POLICY]
2. **Exact expected behavior:** durably observed parent cancellation blocks prohibited new delegated preparation/dispatch at relevant authorization boundaries; running operations may be cooperative only (no instant external side-effect stop claim); races/late outcomes must not silently invalidate authoritative outcomes or create success; recovery must not resurrect prohibited work without explicit approved policy; ambiguous outcomes remain unresolved. Distinguish parent vs independently cancelled children. [PROPOSED POLICY]
3. **Existing implementation evidence:** task states `CANCELLED`/`CANCEL_REQUESTED`; `cancel_task`/store transitions; scheduler excludes active/cancel-requested/uncertain in cases; 5A.6R4 prep/guard fail-closed for cancelled/revoked/unverifiable parent authority in covered paths. [PARTIALLY VERIFIED]
4. **Missing implementation:** complete orchestration to stop all prohibited future child creation/prep/dispatch, request/verify child cancellation, race-safe handling of completion-vs-cancel and late outcomes, resurrection prevention across recovery paths. [UNVERIFIED]
5. **Required positive tests:** cancelled parent authority prevents prohibited new prep/dispatch on supported boundaries; permitted/explicitly approved outcomes behave per defined policy. [PROPOSED POLICY]
6. **Required negative tests:** attempts to prepare/dispatch/authorize after durable cancellation rejected; unverifiable cancellation state fails closed. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** cancel vs child completion/dispatch/recovery/prep; late child outcome traceability and non-overwrite of authoritative state. [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** cancellation must be durably observed at enforced boundaries; ambiguous persisted state treated unresolved/non-success. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** instant forced stop of external side effects; resurrection of prohibited work; silent success from ambiguous cancellation. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only with demonstrated boundary enforcement, race/late-outcome handling, and no prohibited prep/dispatch/resurrection in supported scope. [PROPOSED POLICY]

### INV-05 — Reconciliation correctness and boundedness
1. **Description:** Parent-child reconciliation must be bounded, repeatable, and supported by traceable evidence. [PROPOSED POLICY]
2. **Exact expected behavior:** repeated reconciliation produces no duplicate logical outcomes (idempotent/no-op where unchanged); bounded declared scope; dry-run mutates no authoritative state; apply records available provenance/outcome; invalid/contradictory records fail closed or yield explicit unresolved result; read-only monitoring mutates no authoritative records. Not exactly-once external side effects. [PROPOSED POLICY]
3. **Existing implementation evidence:** snapshot-hash idempotency, dry-run/apply/provenance/history, batch bounds in reconciliation APIs; read-only monitor/status and anomaly detection; pending markers. [PARTIALLY VERIFIED]
4. **Missing implementation:** certified safe remediation for all contradiction classes, monotonic/stale-writer protection across all races/stores, complete cross-store recovery semantics. [UNVERIFIED]
5. **Required positive tests:** unchanged state => idempotent/no-op; dry-run leaves authoritative state unchanged; apply records provenance; bounded batch respected. [PROPOSED POLICY]
6. **Required negative tests:** contradictory/invalid/stale inputs fail closed or explicit unresolved; monitor/status do not mutate on edge states. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** concurrent mutating reconciliations, duplicate apply, stale snapshot vs newer state (within declared boundary). [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** reconciliation evidence/history may be interrupted by non-atomic stores; interrupted/ambiguous cases must be detectable/unresolved, not silently successful. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** exactly-once external side effects, cross-store atomic reconciliation claims, silent auto-repair of unverifiable contradictions. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only for demonstrated bounded/idempotent/evidence-backed behavior within declared boundary and no authoritative mutation in read-only paths. [PROPOSED POLICY]

### INV-06 — Crash and recovery honesty
1. **Description:** AJ must not falsely claim recovery safety for undemonstrated crash windows. [PROPOSED POLICY]
2. **Exact expected behavior:** each supported recovery transition has explicit preconditions; incomplete/ambiguous operations identified where supported; ambiguous state never silently converted to success; repeated recovery does not silently duplicate authoritative transitions; behavior tested at declared persistence boundaries; unsupported cases explicitly classified unsupported/unresolved. No universal crash recovery claim. [PROPOSED POLICY]
3. **Existing implementation evidence:** conservative `RecoveryManager`/assessment/classification/inspection; fail-closed persistence behaviors; reconciliation pending markers and some detection; 5A.6R3 I/J detection evidenced. [PARTIALLY VERIFIED]
4. **Missing implementation/demonstration:** restart/persistence-boundary proofs for A–H and other declared boundaries; complete cross-store interruption handling; stable SQLite/WAL disposition. [UNVERIFIED]/[OPEN ISSUE]
5. **Required positive tests:** supported restart/interruption boundaries recover or explicitly resolve per contract with evidence. [PROPOSED POLICY]
6. **Required negative tests:** ambiguous/incomplete/contradictory states remain unresolved/manual-review, never success; repeated recovery idempotent/non-duplicative for authoritative transitions. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** recovery vs in-flight completion/cancel/dispatch at declared boundaries. [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** explicitly stated per supported boundary (durable evidence availability, store state, single-process restart). Independent-store interruption, OS crash, power loss, filesystem I/O/db/WAL failure, multi-process recovery require separate demonstrated assumptions or remain unsupported. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** universal/complete crash recovery, cross-store atomicity, success on ambiguous recovery. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only for explicitly demonstrated boundaries with reproducible restart evidence; all others classified UNSUPPORTED/UNVERIFIED/OPEN ISSUE. [PROPOSED POLICY]

### INV-07 — Concurrency and stale-state safety
1. **Description:** No mutating concurrency safety claims beyond demonstrated evidence. [PROPOSED POLICY]
2. **Exact expected behavior:** covered concurrent reconciliation/operations produce no silently contradictory authoritative outcomes; stale state cannot silently overwrite newer authoritative state in tested boundary; relevant transitions tested under controlled concurrency; process-boundary limitations documented; unsupported multi-process/distributed concurrency rejected/classified unsupported. Single in-process barrier test is insufficient for universal correctness. [PROPOSED POLICY]
3. **Existing implementation evidence:** in-process locks/guards/file locks/lease coordination; barrier-based in-process concurrent reconciliation test (5A.6R4) showed consistency in covered case. [PARTIALLY VERIFIED]
4. **Missing implementation/demonstration:** proven stale-writer protection, race coverage (cancel-vs-complete, recovery-vs-dispatch, transitions, duplicate apply, assignment/execution mutations), multi-process/distributed support (not in scope). [UNVERIFIED]
5. **Required positive tests:** declared concurrent operations preserve consistency/idempotency and authoritative correctness. [PROPOSED POLICY]
6. **Required negative tests:** conflicting/stale/duplicate concurrent actions fail closed or are safely resolved per evidence with no silent corruption. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** controlled races across listed scenarios within declared single-process boundary. [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** non-atomic multi-store writes and timing can create ambiguity; ambiguity must not become success. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** multi-process/multi-instance/distributed correctness claims; universal concurrency safety from limited tests/locks. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only for explicitly demonstrated concurrent operations within declared boundary; broader claims remain UNVERIFIED/UNSUPPORTED. [PROPOSED POLICY]

### INV-08 — Anomaly visibility
1. **Description:** Supported delegation inconsistencies must be identified/exposed without being presented as healthy state. [PROPOSED POLICY]
2. **Exact expected behavior:** covered missing/inconsistent delegation records, contradictory terminal states, stuck/ambiguous operations detected and surfaced with affected records and available evidence; detection does not silently mutate authoritative state. Detection ≠ remediation. [PROPOSED POLICY]
3. **Existing implementation evidence:** read-only `detect_delegation_anomalies`/`delegation_monitor` surface orphaned/missing parents, incomplete/stuck/recovery-required assignments, stale aggregation, incorrect completed parents, disagreements, missing provenance, active-no-execution; 5A.6R4 extensions for missing assignments, expired/uncertain lease, stuck cancellations, pending reconciliation beyond policy, ambiguous executions, inconsistent terminal states (best-effort). [PARTIALLY VERIFIED]
4. **Missing implementation/demonstration:** complete detector coverage/certification, certified safe remediation for all classes, exhaustive fixtures/tests for each finding. [UNVERIFIED]
5. **Required positive tests:** each supported anomaly class detected with correct identifiers/evidence. [PROPOSED POLICY]
6. **Required negative tests:** healthy/consistent states do not produce false anomaly mutations; monitor/detection remain read-only. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** anomalies arising from cancellation/recovery/concurrency/interruption scenarios within scope. [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** detection best-effort over available records; missing/unreadable evidence may limit detection and must be surfaced as uncertainty where possible. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** claiming remediation from detection; silent healthy presentation of known inconsistencies. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only for supported, tested anomaly classes with read-only detection and accurate surfacing; remediation certified separately if implemented. [PROPOSED POLICY]

### INV-09 — Evidence and auditability
1. **Description:** Important orchestration/delegation decisions must be traceable through existing AJ evidence model. [PROPOSED POLICY]
2. **Exact expected behavior:** relevant operations have correlatable identifiers; available state transitions/reconciliation outcomes recorded; rejected operations have sufficient evidence for diagnosis where supported; missing evidence surfaced as uncertainty; evidence not silently rewritten to manufacture success. No cross-store atomic transaction claim. [PROPOSED POLICY]
3. **Existing implementation evidence:** task events/history, attempts, execution/assignment/delegation records, receipts/journal/audit/operation-evidence/reconciliation provenance mechanisms exist in codebase; correlation fields used in multiple paths. [PARTIALLY VERIFIED]
4. **Missing implementation/demonstration:** complete, consistent evidence coverage across every supported path/decision and all failure/ambiguity cases. [UNVERIFIED]
5. **Required positive tests:** key decisions (authorize/reject/dispatch/cancel/reconcile/recover/transition) produce expected correlatable evidence. [PROPOSED POLICY]
6. **Required negative tests:** failures/rejections/ambiguities produce non-success, diagnosable evidence/uncertainty markers where supported. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** evidence integrity under interruption/races (no fabricated success). [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** append-only/non-atomic stores; evidence may be partial—partial/missing evidence must be surfaced, not treated as success. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** atomic cross-store evidence guarantees, evidence rewriting to claim success. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** only where traceability/evidence is demonstrated for supported decisions and uncertainty is honestly represented. [PROPOSED POLICY]

### INV-10 — Honest system boundaries
1. **Description:** AJ must accurately represent actual operating capabilities. [PROPOSED POLICY]
2. **Exact expected behavior:** no claims of cross-store atomicity, exactly-once external side effects, distributed correctness, authenticated identity from `local_trust`, or real remote-agent execution/acceptance without proof. Capability maturity distinguished (source exists → deps available → service starts → executes → end-to-end works → reliability/security verified). [PROPOSED POLICY]
3. **Existing implementation evidence:** docs/reports and code posture generally avoid those claims; `local_trust` documented as non-authenticated; Hermes NOT ATTACHED; logical-internal delegation only. [PARTIALLY VERIFIED]
4. **Missing implementation/demonstration:** continuous enforcement in all future reporting/behavior; resolution of OPEN issues and unsupported claims in evidence. [UNVERIFIED]
5. **Required positive tests:** N/A as behavioral invariant except checks that unsupported/unsafe capabilities are rejected/blocked and reported honestly. [PROPOSED POLICY]
6. **Required negative tests:** attempts to invoke/claim unsupported external/distributed/authenticated/atomic/exactly-once behavior fail closed or are explicitly reported unsupported. [PROPOSED POLICY]
7. **Required lifecycle/race tests:** N/A (policy/evidence invariant) except where honesty intersects recovery/concurrency claims. [PROPOSED POLICY]
8. **Persistence/recovery assumptions:** reported state/evidence must reflect durable reality, not inferred success. [PROPOSED POLICY]
9. **Explicit unsupported behavior:** all claims listed in §3.2 and §4 boundaries without proof. [UNSUPPORTED]
10. **Acceptance verdict criteria:** **VERIFIED** when documentation, runtime reporting, and evidence consistently reflect demonstrated capabilities/limitations and no prohibited claims are made. [PROPOSED POLICY]

## 6. Required/optional child policy
- **Proposed defaults (incorporated):** (1) child must have deterministically established required/optional classification; (2) required status must never be inferred from missing/malformed data in a way that weakens safety; (3) child must not silently default to optional; (4) required children must satisfy declared completion policy before parent success; (5) optional child failures tolerated only when approved policy explicitly permits; (6) optional failures remain visible in evidence and parent reporting; (7) if existing model cannot safely represent classification, mark capability requiring implementation or UNSUPPORTED. [PROPOSED POLICY]
- **Existing structures inspected:** `DelegationRequest.aggregation_policy` (`all_required|any_sufficient|subset_required`), `required_child_ids`, `child_specs`/`child_refs`, per-delegation `max_children`/bounds; `aggregate_parent_progress` derives required set from `required_child_task_ids or child_task_ids` and policy; no explicit per-child required/optional field in `child_specs` schema. [PARTIALLY VERIFIED]
- **Representation recommendation (compatible, non-implemented):** prefer explicit, validated per-child classification (or deterministic derivation rule) recorded in delegation contract/evidence without inventing unauthorized states; current implicit policy/`required_child_ids` model is **insufficient** to satisfy "no silent default to optional / no weakening inference" without additional explicit rules/validation. Mark as **requiring implementation/clarification** until safely representable. [PROPOSED POLICY] [UNVERIFIED]
- **No implementation invented or assumed.** [PROPOSED POLICY]

## 7. Parent completion and partial outcomes
- **Required-child failure:** failed required child prevents successful parent completion. [PROPOSED POLICY]
- **Independently cancelled required child:** prevents successful parent completion. [PROPOSED POLICY]
- **Unresolved/ambiguous required child:** prevents successful parent completion. [PROPOSED POLICY]
- **Parent-level cancellation:** must be represented according to supported parent cancellation lifecycle, not confused with successful completion; do not automatically invent new lifecycle states. [PROPOSED POLICY]
- **Partial completion:** do not introduce new `PARTIAL` task status. Partial outcomes must never map to `SUCCESS/COMPLETED`. Optional failures may be tolerated only under explicit approved policy. If current model cannot represent a safe non-success partial outcome, report limitation instead of inventing status. [PROPOSED POLICY]
- **Existing model:** task terminal/success states include `COMPLETED` (terminal) and others; aggregation provides non-success indicators (`can_complete=false`, `requires_manual_review`, waiting/failure counts) — usable for non-success representation but policy mapping must be explicit/certified. [PARTIALLY VERIFIED]

## 8. Cancellation policy
- Durably observed parent cancellation must block prohibited new delegated preparation and dispatch at relevant authorization boundaries. [PROPOSED POLICY]
- Already-running operations may only support cooperative cancellation; never claim instant cancellation of external side effect. [PROPOSED POLICY]
- Late child outcomes must remain traceable. Recovery must not resurrect prohibited work without explicit authorization and policy. [PROPOSED POLICY]
- Ambiguous cancellation outcomes must never silently become success. [PROPOSED POLICY]
- Distinguish parent cancellation from independently cancelled children. [PROPOSED POLICY]
- **Existing evidence:** `CANCELLED/CANCEL_REQUESTED` transitions, `cancel_task`, scheduler conservatism, 5A.6R4 prep/guard blocks in covered paths. [PARTIALLY VERIFIED] **Gaps:** full orchestration, child-cancel verification, races/late outcomes/resurrection prevention unproven. [UNVERIFIED]

## 9. Recovery boundary
- Limit supported recovery claims to explicitly demonstrated boundaries. Distinguish: process restart, interrupted transition, independent-store interruption, OS crash, power loss, filesystem I/O failure, database/WAL failure, multi-process recovery. [PROPOSED POLICY]
- Unsupported cases explicitly unsupported; no universal crash recovery promise. [PROPOSED POLICY]
- **SQLite/WAL:** keep **OPEN** until adequately investigated and dispositioned (see §16). [OPEN ISSUE]
- **Evidence posture:** crash windows A–H largely PARTIAL/UNTESTED as reconstructed supporting refs; I/J detection evidenced. [PARTIALLY VERIFIED]

## 10. Concurrency boundary
- **Proposed conservative boundary:** local AJ operation, single AJ process, only explicitly tested concurrent operations certified. No multi-process or distributed correctness guarantees. [PROPOSED POLICY]
- Do not infer concurrency safety from existence of locks or identifiers. [PROPOSED POLICY]
- **Evidence:** in-process guards/locks and limited barrier-tested reconciliation consistency; broader mutating races and multi-process behavior unproven. [PARTIALLY VERIFIED]/[UNVERIFIED]

## 11. Authorization entry-point inventory
*11 path groups identified in Doc 53; retained with source-level detail and proposed acceptance tests. Universal enforcement not claimed until every supported entry point appropriately protected or explicitly blocked.* [PARTIALLY VERIFIED]

| Group | Exact source file | Exact method/function(s) | Authorization boundary | Current-state revalidation | Permission narrowing | Cancellation enforcement | Evidence (existing) | Tests (observed) | Missing coverage | Proposed acceptance test |
|---|---|---|---|---|---|---|---|---|---|---|
| 1. Initial handle/request execution | `aj/orchestrator.py` | `Aj.handle` (L247), `_execute` (L1294), `_capability_blocker` (L1276), `_compute_authorization_context` (L1947), `_delegated_permission_guard` (L3835) | Route/capability/policy/authz decision and execute boundary | Delegated guard checks parent/delegation state/linkage + snapshots (covered) | Guard enforces recorded effective ⊆ snapshots, logical-internal scope | Guard blocks delegated exec under cancelled/revoked/unverifiable parent authority | Task status/events, attempts, receipts/journal/audit hooks (path-dependent) | General + limited delegation-specific | All handle variants/states, post-assignment revocation, all delegated contexts | Positive: valid delegated handle executes only when authorized/current; Negative: revoked/missing/malformed/widened/cancelled authority rejected; Lifecycle: revocation/cancel at boundary |
| 2. Scheduler dispatch | `aj/scheduler.py`, `aj/orchestrator.py` | `Scheduler.evaluate_eligibility`, `_run_one/run_once` (dispatch path), `Aj.resume` (L2036), `_resume_locked` (L2042), `_execute` (L1294) | Eligibility/admission + leased resume/execute boundary | Eligibility conservative; guard revalidates current delegation/parent at resume/execute | Guard snapshot/narrowing checks | Eligibility excludes active/cancel-uncertain in cases; guard/prep block cancelled authority | Scheduler decisions/dispatch evidence, lease/execution/task/attempt evidence | 5A.5 tests, bounded 5A.6R4 guard/prep | Parent-cancel-aware eligibility, dispatch races, revocation cases | Positive: eligible authorized delegated task dispatches safely; Negative: ineligible/cancelled/revoked/unverifiable blocked; Race: cancel/revocation vs dispatch |
| 3. Direct/leased resume | `aj/orchestrator.py` | `Aj.resume` (L2036), `_resume_locked` (L2042), `_execute` (L1294) | Resume capability/policy/stale checks + execute guard | Guard current-state + snapshot checks at boundary | Guard narrowing checks | Guard blocks cancelled/revoked/unverifiable authority | Execution/attempt/task/receipt/journal | Covered indirectly; limited revocation cases | Exhaustive revocation/reduction/recovery-state contexts | Positive: valid resume proceeds; Negative: revoked/cancelled/malformed denied; Lifecycle: post-assignment changes |
| 4. Retry | `aj/orchestrator.py` | `Aj.retry` (L477), `_retry_locked` (L481), `_execute` (L1294) | Retry gating (FAILED, budget, retry_safe) + execute guard | Execute-boundary guard revalidates at runtime | Guard narrowing checks | Guard blocks cancelled/revoked authority if present | New attempt/execution/task evidence | General retry tests; limited delegated revocation | Revocation/cancel during retry across contexts | Positive: authorized retry allowed per policy; Negative: revoked/cancelled/unverifiable denied; Lifecycle: revocation after prior assignment |
| 5. Recovery (explicit) | `aj/recovery.py`, `aj/orchestrator.py` | `RecoveryManager.recover/scan/_recover_one`, `classify`; `Aj.recover` (L666), `_recover_locked` (L988), `_assess_recovery` (L782), `recovery_inspection` (L2419) | Evidence-based assessment; any resumed/executed action passes guarded paths | Guard applies when routed to resume/execute; assessment not full delegated revalidator | Via guarded execution only | Cancellation/recovery interactions partially constrained; not fully certified | Findings/outcomes, inspection, task/journal/receipt when acted | General recovery tests; limited delegated cases | Ambiguous delegated recovery, revocation/cancel/resurrection/races | Positive: safe recoverable case handled per evidence; Negative: ambiguous/unverifiable/revoked/cancel-prohibited blocked or manual-review; Race: recovery vs cancel/dispatch/completion |
| 6. Delegation creation/assignment | `aj/orchestrator.py`, `aj/delegation.py` | `Aj.delegate` (L4230), `_ensure_delegation_stores`, `_seed_logical_agents`, `_prepare_delegated_child_for_scheduling` (L3924); request validation, `match_agent`, `narrow_permissions`, stores | Schema/bounds/hierarchy/idempotency/match/narrowing at creation | Parent existence/state checked; prep rechecks authority/cancel | `narrow_permissions` intersection fail-closed, recorded | Prep fails closed on cancelled/revoked/unverifiable parent; no dispatch | Delegation/assignment/child task records, journal, status/aggregation | 5A.6–5A.6R4 focused tests | Explicit required/optional classification, all cancellation/creation races | Positive: valid delegation creates narrowed/linked records; Negative: invalid/malformed/missing/unmatchable/widening/cancelled-parent rejected; Lifecycle: parent cancel during/after create |
| 7. Delegated child preparation | `aj/orchestrator.py` | `_prepare_delegated_child_for_scheduling` (L3924) | Transition/prep toward schedulable/waiting state (no dispatch) | Rechecks current parent state/authority before advancing | Preserves recorded context (no widening) | Fail-closed abort/block on cancelled/revoked/unverifiable parent (5A.6R4) | Task transitions/persistence, result | 5A.6R4 cancelled-parent test | All preparable states and creation-vs-cancel races | Positive: preparable child advances when authority valid; Negative: cancelled/unverifiable/terminal blocked; Race: cancel vs prep |
| 8. Reconciliation/monitoring | `aj/orchestrator.py`, `aj/delegation.py` | `reconcile_delegation_parent` (L3820), `_reconcile_delegation_parent` (L4030), `_on_task_transition` (L3782), `_before_task_transition` (L3733), `delegation_status` (L4183), `delegation_monitor` (L4197), `aggregate_parent_progress`, `detect_delegation_anomalies` | Aggregation/reconcile/observe boundaries (no dispatch) | Aggregation/guard use current task/delegation state; monitor read-only best-effort | No widening; not a grant path | Completion guard/policy interactions with cancel states in covered cases | Delegation evidence/history/provenance, pending markers, monitor/status outputs | 5A.6R2–R4 tests (idempotency, dry-run/apply, detection, guard) | Full policy enforcement, safe remediation, races/stale overwrite, all cancel semantics | Positive: correct aggregation/evidence/idempotent dry-run-apply; Negative: unsafe completion/contradictions blocked or surfaced; Race: concurrent reconcile/transition/cancel |
| 9. Cancel (task) | `aj/orchestrator.py`, `aj/task.py` | `Aj.cancel_task` (L607), `_cancel_locked` (L611), `Aj.cancel` (L663), `TaskStore.cancel/transition` | Lifecycle-valid cancellation request/transition | State transition validity checks | N/A | Sets `CANCELLED` or `CANCEL_REQUESTED` per FSM; cooperative only | Task events/status persistence and related evidence | General cancel tests; limited delegated orchestration | Child propagation/verification, parent-vs-child semantics, races/late outcomes | Positive: valid cancel transitions recorded; Negative: invalid/terminal transitions rejected; Race: cancel vs completion/dispatch/recovery |
| 10. Dead-letter | `aj/orchestrator.py` | `Aj.dead_letter` (L2244) | Administrative terminal/abandonment per policy | Lifecycle/state checks per implementation | N/A | Affects terminal handling; delegation/cancel interactions limited | Task transition/evidence | Limited | Delegated policy interactions, evidence guarantees | Positive: permitted dead-letter recorded; Negative: invalid state/context rejected; Lifecycle: interaction with unresolved/cancelled children |
| 11. Administrative requeue/abandon/operator reconcile/diagnostics | `aj/orchestrator.py` | `requeue` (L3408), `abandon` (L3467), `reconcile` (L2864), `consistency_check` (L3371), `storage_diagnostics` (L3391) | Explicit admin/operator actions with preconditions | Operation-specific conservative checks | N/A unless triggers guarded execution (not primary) | May affect lifecycle states; cancellation semantics not fully certified | Operation/provenance/evidence outputs | Varies | Interactions with delegated authz/cancel/lifecycle invariants | Positive: valid admin op with evidence; Negative: unsafe/unverifiable op rejected/fails closed; Lifecycle: no resurrection/prohibited dispatch |

## 12. Unknown-state invariant
- **Proposed cross-cutting rule:** "Unknown, missing, contradictory, malformed, or unverifiable state must never silently become successful state." [PROPOSED POLICY]
- **Domains analyzed:** execution records, delegation records, parent-child links, authorization records, reconciliation evidence, cancellation records, recovery records, terminal lifecycle states. [PARTIALLY VERIFIED]
- **Current posture:** many fail-closed behaviors and anomaly surfacing exist, but universal proof is lacking (untraced paths, races, cross-store interruptions, snapshot-limited authz revalidation, ambiguous recovery/cancellation outcomes). [PARTIALLY VERIFIED]/[UNVERIFIED]
- **Acceptance implication:** any demonstrated silent conversion to success is **UNSAFE**; unproven coverage remains **UNVERIFIED/PARTIALLY VERIFIED** until evidenced. [PROPOSED POLICY]

## 13. Acceptance test matrix
*Summary matrix aligned to INV-01–INV-10 and policy areas; to be instantiated as bounded, reproducible tests in a future approved plan (not implemented now).*

| ID | Area / Invariant | Type | Proposed scenario | Expected result | Evidence required | Verdict precondition |
|---|---|---|---|---|---|---|
| T-01 | INV-01/02, Authz paths 1-5,6-7 | Positive/Negative | Valid vs missing/malformed/revoked/widened delegation & permission contexts at each supported path | Authorized only on valid/current; otherwise fail closed/reject | Task/delegation/auth evidence, rejection reason, no unauthorized execution | All supported paths covered or explicitly blocked |
| T-02 | INV-01/04, Authz 1-5,7,9 | Lifecycle/Race | Post-assignment revocation or durable parent cancellation before/at prep/dispatch/execute/retry/recover | Prohibited actions blocked; no success | Boundary decision evidence, state unchanged/protected | Includes revocation + cancel timing cases |
| T-03 | INV-03, Child/Partial policy | Positive/Negative | Required satisfied vs pending/running/failed/cancelled/unresolved/ambiguous; optional failure cases per explicit policy | COMPLETED only when policy satisfied; never on unsafe/partial-as-success | Aggregation, child states, parent transition/evidence | Explicit policy defined/approved |
| T-04 | INV-03, Classification | Negative | Missing/malformed/contradictory required-optional classification | Fail closed, no silent optional default | Validation/rejection evidence | Representation supported or explicitly UNSUPPORTED |
| T-05 | INV-04 | Lifecycle/Race | Cancel vs child completion/dispatch/recovery/prep; late outcome; resurrection attempt | No invalid terminal overwrite/success/resurrection; outcomes traceable or unresolved | Cancellation/child/reconciliation evidence timeline | Declared boundary and cooperative-cancel semantics |
| T-06 | INV-05 | Positive/Negative/Race | Repeated reconcile, dry-run, apply provenance, batch bounds, contradictory/stale/duplicate concurrent actions | Idempotent/no mutation in dry-run/read-only, bounded, fail-closed on contradictions | Reconciliation history/evidence, record snapshots | Single-process declared boundary |
| T-07 | INV-06 | Recovery/Race | Declared restart/persistence-boundary interruptions (supported only) and ambiguous cases | Recover or explicit unresolved/manual-review; never silent success/duplication | Durable pre/post state, restart evidence, recovery outcome | Boundary explicitly demonstrated/supported |
| T-08 | INV-07 | Concurrency/Race | Controlled single-process races (completion-vs-cancel, recovery-vs-dispatch, stale writer, duplicate apply) | No contradictory authoritative outcome/silent overwrite | Deterministic logs/state snapshots/evidence | Only explicitly tested operations certified |
| T-09 | INV-08 | Positive/Negative | Supported anomaly classes present vs healthy states | Detected/surfaced with ids+evidence; no mutation in detection | Monitor findings, unchanged authoritative records | Detection classes enumerated |
| T-10 | INV-09/12 | Positive/Negative | Key decisions and rejections/ambiguities across paths | Correlatable traceable evidence; uncertainty surfaced, no fabricated success | IDs, receipts/journal/task/delegation/reconciliation records | Evidence model coverage per supported path |
| T-11 | INV-10 | Negative/Policy | Unsupported capability/claim attempts (distributed/external/atomic/exactly-once/authenticated identity) | Rejected/blocked or explicitly reported unsupported; no false claim | Runtime/report/evidence behavior | Boundary reporting consistent |
| T-12 | §16 SQLite/WAL | Investigation/Regression | Repro/isolation diagnosis and disposition (not weakening) | Cause/limitation explicitly established or safely bounded; full-suite stability honestly reported | Repro logs, env/fs/WAL/init/concurrency evidence | OPEN until dispositioned |

## 14. Existing implementation compatibility
- **Compatible/aligned (partial):** task FSM and transitions, append-only stores/fail-closed persistence patterns, execution/scheduler/lease foundations, delegation/assignment stores and aggregation, `narrow_permissions` intersection, delegated guard/prep hardening (5A.6R4), reconciliation idempotency/provenance/dry-run/apply, read-only monitoring, conservative recovery intent, no external transport, Hermes NOT ATTACHED. [PARTIALLY VERIFIED]
- **Gaps requiring clarification/implementation evidence:** explicit per-child classification and non-optional-default enforcement, complete parent-cancel/partial/optional policy enforcement, exhaustive authz revalidation/blocking across all paths, crash-boundary restart proofs, mutating race/stale-writer safety, certified remediation, complete unknown→non-success proof. [UNVERIFIED]
- **Incompatible with current baseline claims if asserted now:** PARTIAL-as-success, universal recovery, multi-process/distributed correctness, authenticated `local_trust`, cross-store atomicity/exactly-once, real remote agent transport. [UNSUPPORTED]

## 15. Missing capabilities and risks
- **Missing capabilities:** per-child required/optional representation+validation; full cancellation orchestration/race-safe handling; exhaustive path-level current-state authz enforcement or blocking; demonstrated crash/recovery and concurrency safety per declared boundaries; certified anomaly remediation and complete evidence coverage. [UNVERIFIED]
- **Risks:** original 45/A–J provenance unverified; false safety/certification from partial evidence; hidden bypass paths; cross-store ambiguity and non-atomic interruptions; NTFS/SQLite-WAL instability (OPEN); races under real concurrency/load; policy ambiguity if not explicitly approved. [OPEN ISSUE]/[UNVERIFIED]

## 16. SQLite/WAL issue
- **Preserved known failure:** `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` — `sqlite3.OperationalError: disk I/O error` (forked WAL init, NTFS-backed pytest tmp context observed). [VERIFIED]/[OPEN ISSUE]
- **Latest reported full suite:** **576 passed, 1 failed, 13 warnings**. Cause **not conclusively diagnosed**. [OPEN ISSUE]
- **Investigation requirements (keep OPEN):** reproduce/characterize across isolated runs, full-suite load, tmp locations (`/tmp` vs NTFS-backed), filesystem semantics, WAL/journal behavior, fork/multiprocessing and initialization ordering, test-load sensitivity; record evidence and disposition. [PROPOSED POLICY]
- **Mandatory constraints:** do not weaken/delete test, do not modify filesystem, do not dismiss failure, do not claim isolated pass establishes full-suite stability. [PROPOSED POLICY]

## 17. Protected system boundaries
- JARVIS, HELIX, Hermes remain independent; no protected repository/configuration modified as part of AJ acceptance work. [PROPOSED POLICY]/[VERIFIED]
- Hermes **NOT ATTACHED**; `hermes.gateway.ensure` unimplemented, disabled, unexecuted. [VERIFIED]
- No destructive Git operations; no staging/commits/pushes/merges/tags/history rewriting without explicit approval; no destructive migrations/mass deletion/filesystem repair without explicit approval. Existing uncommitted/untracked work preserved. [PROPOSED POLICY]

## 18. Approval and implementation gates
- **Gate A — Baseline approval:** user explicitly approves Document 54 or requests revisions. [PROPOSED POLICY]
- **Gate B — Implementation plan:** only after Gate A, prepare a bounded implementation and verification plan. [PROPOSED POLICY]
- **Gate C — Implementation authorization:** separate explicit authorization required before any code changes. [PROPOSED POLICY]
- **Gate D — Verification:** all mandatory approved invariants demonstrated with reproducible evidence within declared boundaries. [PROPOSED POLICY]
- **Gate E — Acceptance:** no mandatory invariant may remain PARTIALLY VERIFIED, UNVERIFIED, or UNSAFE; open defects explicitly dispositioned with evidence; unsupported behavior safely rejected/explicit. [PROPOSED POLICY]
- **Gates must not be merged.** [PROPOSED POLICY]

## 19. Final recommendation
- **Approve (after review/revision) a consolidated, narrowed, honesty-first baseline** (this v1.1 proposal) with explicit policy semantics, bounded operating claims, and testable evidence requirements before any implementation. [PROPOSED POLICY]
- **Resolve open decisions first** (§20): required/optional classification representation and policy mappings, supported/blocked path list, supported crash/concurrency boundaries, SQLite/WAL disposition approach, and treatment of reconstructed 45/A–J as supporting refs. [PROPOSED POLICY]
- **Do not start implementation/Phase 5A.7** until Gates A–C satisfied; treat current state as **INCOMPLETE** for 5A.6R–R4 pending approved baseline and verification. [PROPOSED POLICY]

## 20. Explicit pending user decisions
1. Approve, revise, or reject Document 54 (and relationship to 52/53) as the binding proposed baseline. [PROPOSED POLICY]
2. Approve exact required/optional child classification representation/derivation/validation rules and non-optional-default enforcement (compatible with existing model). [PROPOSED POLICY]
3. Approve explicit policy for failed/cancelled-required children, parent-cancellation outcomes, optional failure tolerance, and partial outcome handling (no PARTIAL→SUCCESS). [PROPOSED POLICY]
4. Approve authoritative list of supported vs explicitly blocked authorization/dispatch/recovery/administrative entry points (all 11 groups). [PROPOSED POLICY]
5. Approve declared supported crash/recovery boundaries and concurrency boundary (single-process, demonstrated-only) with evidence standards. [PROPOSED POLICY]
6. Approve investigation/disposition plan for OPEN SQLite/WAL failure (no test weakening/filesystem modification). [OPEN ISSUE]
7. Approve status of reconstructed scenarios 1–45 and crash windows A–J as supporting references only (non-binding) or explicitly ratified checklist under clarified terms. [PROPOSED POLICY]

---
**END OF PROPOSED CONSOLIDATED ACCEPTANCE BASELINE v1.1** (pending user review/approval; no implementation authorized)
