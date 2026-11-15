# 08 Docs Digest (52–57, read-only)

## Files: filename, size, last-modified

| File | Size (bytes) | Last modified (stat) |
|---|---:|---|
| `52_PHASE_5A_6R5_PROPOSED_NARROWED_INVARIANT_BASELINE_V1.md` | 16055 | 2026-11-14 22:35:06.003792800 +0500 |
| `53_PHASE_5A_6R5_POLICY_SEMANTICS_CLARIFICATION_PROPOSAL.md` | 42445 | 2026-11-14 22:40:14.739643700 +0500 |
| `54_PHASE_5A_6R5_CONSOLIDATED_ACCEPTANCE_BASELINE_V1_1_PROPOSAL.md` | 52542 | 2026-11-14 23:15:04.393940100 +0500 |
| `55_PHASE_5A7_IMPLEMENTATION_PLAN_AND_PROOF_STRATEGY.md` | 63180 | 2026-11-14 23:24:52.473370500 +0500 |
| `56_PHASE_5A7_REVISED_IMPLEMENTATION_PLAN_AND_PROOF_STRATEGY.md` | 104634 | 2026-11-14 23:42:27.742115100 +0500 |
| `57_PHASE_5A7_GATE_B_REVIEW_AND_S0_CLOSURE_REPORT.md` | 53838 | 2026-11-15 14:06:57.479802300 +0500 |

## Verbatim: Doc 54 invariants (INV-01..INV-10) and T-01..T-12 matrix

> Source: `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/54_PHASE_5A_6R5_CONSOLIDATED_ACCEPTANCE_BASELINE_V1_1_PROPOSAL.md`, §5 (lines 46–169) and §13 (lines 226–242) as captured.

```markdown
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
```

## Verbatim: Doc 56 S0–S6 stages

> Source: `56_PHASE_5A7_REVISED_IMPLEMENTATION_PLAN_AND_PROOF_STRATEGY.md`, §17 (lines 387–401) as captured.

```markdown
## 17. Revised implementation stages and stage gates

| Stage | Objective | Entry criteria | Work (authorized future only) | Exit criteria (measurable) | Dependencies / gates |
|---|---|---|---|---|---|
| **S0 — Closure & design decisions** | Eliminate planning unknowns required for safe implementation | Doc 56 reviewed; user decisions available for blocking items | Produce authoritative source-enumerated callable inventory + supported/blocked/unsupported decisions; choose `ABANDONED` disposition; finalize delegation classification/model representation and migration/compat design; declare demonstrably feasible crash/concurrency boundaries; identify enforcement points | Signed-off inventory (no unclassified relevant known callable), explicit block list with enforcement points, approved policy/model mapping for §7/§8, boundary feasibility declarations | **Hard gate before S1.** No implementation authorization implied |
| **S1 — Policy/model foundation** | Implement approved classification and lifecycle outcome mapping safely | S0 complete/approved; migration/compat strategy approved | Add/validate explicit classification, enforce fail-closed semantics, align state/outcome mapping and evidence; implement approved `ABANDONED` disposition if in scope | Policy-matrix tests and migration/compat evidence pass per criterion; no silent optional/default; legacy records handled per approved rules | Gate C required for code changes; blocks S2–S3 semantic correctness |
| **S2 — Authorization, scheduler/dispatch, and admin blocking/guarding** | Close enforcement gaps on all supported paths | S1 complete; S0 inventory approved | Enforce current-state authz/narrowing/cancel checks at required boundaries (incl. scheduler/dispatch/resume/execute/prep as applicable); block/guard unsafe admin/operator/CLI paths for delegated contexts | Per-path coverage proven or explicitly blocked; no unauthorized prep/dispatch/execute demonstrated; admin bypasses closed per disposition | Must precede enabling dependent delegated flows |
| **S3 — Lifecycle, cancellation, reconciliation correctness** | Enforce parent/child outcomes and safe reconciliation contracts | S1–S2 complete | Implement cancellation orchestration semantics as approved, completion/transition guards, reconciliation apply safety/idempotency/provenance and read-only guarantees | INV-03/04/05 criteria verified within declared boundary; no false completion/resurrection/unsafe mutation | Requires feasible race evidence where claimed |
| **S4 — Crash/recovery & concurrency (feasible boundaries only)** | Prove only demonstrable boundaries | S1–S3 complete; S0 boundary feasibility fixed | Implement only evidence-backed detection/handling for approved feasible boundaries; add mechanism-backed concurrency protections/tests | Each claimed boundary/operation has VERIFIED evidence or is explicitly UNSUPPORTED/NOT VERIFIABLE/BLOCKED | No overclaims; S5 disposition may constrain claims |
| **S5 — SQLite/WAL investigation & disposition** (parallelizable investigation, gating disposition) | Resolve or bound OPEN storage reliability issue | S0 experiment plan approved | Execute non-destructive matrix (§14), analyze, produce disposition | Root-cause/attribution evidenced or explicit bounded limitation documented | Gates full-suite/environment-dependent certification claims |
| **S6 — Independent verification & acceptance package** | Criterion-level verification and readiness decision | S1–S4 done/blocked per evidence; S5 disposition recorded | Clean re-runs, independent review, evidence manifests, regression analysis | Every mandatory criterion has verdict per taxonomy; no hidden failures; Gate D/E readiness explicitly determined | No VERIFIED without independent evidence (or limitation recorded)

**Stage-gate rules:** no stage proceeds on “looks good”; no general COMPLETE status; each exit requires criterion-level evidence or explicit `BLOCKED`/`UNSUPPORTED`/`NOT VERIFIABLE` with impact.
```

## Verbatim: Doc 57 verdicts and the four user-decision items

> Source: `57_PHASE_5A7_GATE_B_REVIEW_AND_S0_CLOSURE_REPORT.md`, §2 (lines 27–45) and §14 (lines 260–270) as captured.

```markdown
## 2. Gate B verdict

### 2.1 Overall verdicts
- **Gate B (Doc 56 as implementation/proof plan):** **GATE B PASS WITH EXPLICIT LIMITATIONS**.  
  Rationale: Doc 56 materially reverified and corrected key adversarial findings, preserved Doc 54 invariants/policy intent, adopted safer framing (explicit blocking, feasibility limits, no silent optional/partial-success), and defined structured S0–S6/proof protocols. It is suitable as a revised planning basis **only** with the explicit limitations below and S0 closure actions required before implementation authorization.
- **S0 (source and policy closure):** **S0 PARTIALLY COMPLETE**.  
  Rationale: substantial source-grounded inventory, blocking strategy, policy/model recommendations (with conservative defaults), executable proof framework, feasibility/SQLite evidence gathered in this read-only pass; however, exhaustive callable/wrapper closure, final approved policy/model decisions for semantics-changing items, and some feasibility determinations remain unresolved.

### 2.2 Explicit limitations (Gate B pass conditions)
- Callable/wrapper/CLI/UI/integration inventory is **not proven exhaustive**; untraced paths remain `UNKNOWN`.
- Current-state delegated authorization revalidation is **not fully proven dynamic** across all boundaries (snapshot/record checks exist in covered paths).
- Scheduler delegation-cancellation/authority awareness is **not evidenced** in inspected eligibility/dispatch logic; downstream guards exist but race sufficiency unproven.
- `ABANDONED` has a **confirmed FSM/model inconsistency** requiring an explicit disposition decision.
- Required/optional child classification is **not explicitly representable/enforceable** in current contract; outcome-state mapping needs approved, compatibility-safe design.
- Crash cross-store/interruption and stale-writer protections are largely **NOT VERIFIABLE** with current seams/mechanisms.
- SQLite/WAL issue is **OPEN** with strong environment-sensitivity evidence on one controlled storage path, but no full-suite/product-defect attribution.
- Independent verification is a protocol only; implementer self-certification remains prohibited.

## 14. Exact unresolved user decisions (escalate only if safe default insufficient)

| # | Decision | Why safe default cannot fully resolve | Recommended default / smallest choice set |
|---|---|---|---|
| 1 | **Required/optional classification representation & migration/compat** (explicit per-child field/derivation, storage, legacy-record handling) | Changes persisted contract/meaning and may require migration/compat policy affecting existing records and behavior. | **Recommend:** explicit per-child classification + strict validation, fail-closed for legacy/ambiguous records, approved reversible compat/migration plan. **Choices:** (A) explicit per-child field with versioned compat, (B) deterministic derivation rule with explicit validation (only if lossless and proven safe). |
| 2 | **Exact parent outcome-state mapping** for required-failed/cancelled/unresolved/ambiguous (and tolerated optional cases) within existing FSM or approved model change | User-visible lifecycle semantics and audit/operations expectations; FSM adequacy not one-to-one without approved mapping. | **Recommend:** map to existing non-success states with explicit evidence/manual-review semantics (no new PARTIAL, no success). **Need:** approved mapping table per case. |
| 3 | **`ABANDONED` disposition** (formalize in FSM+validation+terminal/import semantics vs remap to existing state vs keep blocked/legacy-limited) | Structural model/compatibility change with persisted behavior/test reliance. | **Recommend:** formalize as declared terminal state with explicit rules and delegated-context blocking, or remap if consistency preferred — but choose explicitly. |
| 4 | **Delegated-context admin/scheduler policy** (block vs guarded support for deadline dead-letter, operator actions, requeue/abandon, delegated dispatch) | Materially affects safety guarantees and allowed operations. | **Recommend:** **block/unsupported** for delegated contexts until individually guarded and proven; allow only narrowly justified non-delegated legacy behavior per evidence. |

*Other items (stale-writer mechanism feasibility, crash seams, SQLite attribution) are technical NOT VERIFIABLE/OPEN constraints to be handled by classification/evidence, not preference decisions.*
```

## Contradictions (docs vs source code), as observed

- **Doc 54 / policy intent vs current model:** Doc 54 requires explicit required/optional child classification with no silent default to optional and no weakening inference (INV-03, §6, T-04). **Source:** `aj/delegation.py::DelegationRequest` has no explicit per-child required/optional field; classification is implicit via `aggregation_policy`/`required_child_ids` (and `aggregate_parent_progress` derivation). **CONTRADICTION/GAP** (not yet implemented as required). [VERIFIED FROM CURRENT SOURCE]
- **Doc 56/57 identify `ABANDONED` FSM inconsistency:** **Source confirms** `"ABANDONED"` used/persisted/forced (`aj/orchestrator.py::Aj.abandon`, operator reconcile, `aj/consistency.py`, tests) but absent from `aj/task.py` `TRANSITIONS`/`TERMINAL` and would fail validation/reload/import assumptions as written. This aligns with (not contradicts) Doc 56/57. [VERIFIED]
- **Exhaustiveness claims:** Any implication of exhaustive closure in planning artifacts would contradict evidence; Doc 56/57 explicitly state non-exhaustiveness and this pass confirms remaining untraced wrappers/surfaces (e.g. inbox CLI "requeue/retry" are separate inbox-domain operations, not task FSM mutations; some CLI/runtime paths not fully enumerated). [VERIFIED]
- **SQLite/WAL:** Doc 54/56 note prior 576/1/13 and OPEN status; this session observed 577/0/13 full-suite pass and controlled intermittent/location-sensitive behavior for the specific test — **environment-dependent variance**, not a doc contradiction but an evidence update requiring honest OPEN disposition. [VERIFIED BY EXECUTABLE TEST]
