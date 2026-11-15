# 57 — Phase 5A.7 Gate B Review and S0 Closure Report

**Date:** 2026-11-14 (audit session) / system date context: 2026-11-15  
**Phase:** 5A.7 planning gate — independent Gate B review of Doc 56 + S0 closure (read-only source audit and planning; single-report creation only)  
**Status:** **AUDIT COMPLETE (planning). No implementation performed.**  
**Primary target reviewed:** `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/56_PHASE_5A7_REVISED_IMPLEMENTATION_PLAN_AND_PROOF_STRATEGY.md`  
**Governing baseline:** Doc 54 (approved acceptance baseline for planning; **not** implementation authorization)

**Evidence classification:** [VERIFIED FROM CURRENT SOURCE] (inspected now), [VERIFIED BY EXECUTABLE TEST] (command executed now with captured result), [PARTIALLY VERIFIED], [REPORT-ONLY / NOT INDEPENDENTLY REPRODUCED], [NOT VERIFIABLE], [CONTRADICTED BY CURRENT EVIDENCE], [OPEN ISSUE], [PROPOSED]. No invariant is claimed implemented/verified by this planning report.

---

## 1. Repository baseline

- **Repository root:** `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ` [VERIFIED FROM CURRENT SOURCE]
- **Branch:** `main` [VERIFIED FROM CURRENT SOURCE]
- **HEAD:** `468fdcebece5b25f02e53add4928d3650ef175f4` [VERIFIED FROM CURRENT SOURCE]
- **`git status --short` (complete, pre-existing/preserved):** 57 entries (17 tracked modified, 40 untracked `??`). [VERIFIED FROM CURRENT SOURCE]
  - **Tracked modified (17):** `aj/__main__.py`, `aj/config.py`, `aj/diagnostics.py`, `aj/ids.py`, `aj/orchestrator.py`, `aj/receipts.py`, `aj/recovery.py`, `aj/runtime.py`, `aj/scheduler.py`, `aj/task.py`, `aj/transfer.py`, `tests/test_foundation.py`, `tests/test_orchestrator.py`, `tests/test_path_config_hardening.py`, `tests/test_phase2.py`, `tests/test_phase3.py`, `tests/test_step_c_gap_closure.py`
  - **Untracked (40, representative):** prior/Phase 5A audit dirs incl. `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/` (Docs 00–56 present), `aj/authorization.py`, `aj/consistency.py`, `aj/delegation.py`, `aj/execution_domain.py`, `aj/hermes_adapter.py`, `aj/hermes_contract.py`, `aj/operation_evidence.py`, `aj/storage_diagnostics.py`, `integrations/`, and Phase 3/4/5A-related tests incl. `tests/test_phase5a4_execution_domain.py`, `tests/test_phase5a5_scheduler_admission.py`, `tests/test_phase5a6_delegation_foundation.py`, `tests/test_phase5a6r_delegation_closure.py`, `tests/test_phase5a6r2_parent_lifecycle.py`, `tests/test_phase5a6r3_scenario_certification.py`, `tests/test_phase5a6r4_gap_closure.py`, `tests/test_dead_letter.py`, `tests/test_audit_reliability_security.py`.
- **Docs 52–56 present/read:** `52_PHASE_5A_6R5_PROPOSED_NARROWED_INVARIANT_BASELINE_V1.md`, `53_PHASE_5A_6R5_POLICY_SEMANTICS_CLARIFICATION_PROPOSAL.md`, `54_PHASE_5A_6R5_CONSOLIDATED_ACCEPTANCE_BASELINE_V1_1_PROPOSAL.md`, `55_PHASE_5A7_IMPLEMENTATION_PLAN_AND_PROOF_STRATEGY.md`, `56_PHASE_5A7_REVISED_IMPLEMENTATION_PLAN_AND_PROOF_STRATEGY.md` in `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/`. [VERIFIED FROM CURRENT SOURCE]
- **No repository mutations performed** except creation of this report file; no staging/commit/push/merge/reset/clean/history rewrite; no source/test/config/schema/DB changes; no fs repair/migration; no `hermes.gateway.ensure`; Hermes remains NOT ATTACHED. [VERIFIED FROM CURRENT SOURCE]
- **Exhaustiveness limitation:** not every caller/wrapper/CLI surface/runtime path was traced to a closed call graph in this pass. Where closure is not established, items are marked `UNKNOWN — REQUIRES INVESTIGATION` / `NOT VERIFIABLE`; no exhaustiveness claim is made.

---

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

---

## 3. Doc 56 claim-by-claim verification (material claims)

| Doc 56 claim (section/subject) | Classification | Evidence (source/tests/executable) | Notes |
|---|---|---|---|
| Repository baseline, docs 52–56 present, no weakening of Doc 54, planning-only (Doc 56 §1–2) | **VERIFIED FROM CURRENT SOURCE** | Repo/branch/HEAD/status and doc listing observed; Doc 56 states preservation/constraints; this pass made no code/test/config/schema/DB changes. | Accurate as planning posture. |
| `Aj.dead_letter` transitions to `DEAD_LETTER` without delegation/lifecycle guards (Doc 56 §3, §4) | **VERIFIED FROM CURRENT SOURCE** | `aj/orchestrator.py::Aj.dead_letter` (method present; inspected earlier): checks transition legality to `DEAD_LETTER`, persists/audits/journals/records memory; no delegation parent/child/assignment checks observed. Callers observed: operator `Aj.reconcile` dead_letter action, `aj/scheduler.py` deadline path `self.aj.dead_letter(...)` (inspected), tests `tests/test_dead_letter.py`. | Confirmed. |
| `Aj.requeue` forces `DEAD_LETTER -> PLANNED` and can resurrect unsafely for delegated contexts (Doc 56 §3, §4) | **VERIFIED FROM CURRENT SOURCE** | `aj/orchestrator.py::Aj.requeue`: enforces source status `DEAD_LETTER`, calls `self.tasks.transition(task_id, taskmod.PLANNED, ..., force=True, reason="requeue")`, appends attempt, clears `requires_user_decision`, audits/journals; no delegation checks. Tests: `tests/test_dead_letter.py`. | Confirmed. |
| `Aj.abandon` forces `"ABANDONED"` and lacks delegation checks (Doc 56 §3, §4, §5) | **VERIFIED FROM CURRENT SOURCE** | `aj/orchestrator.py::Aj.abandon`: idempotent if status `"ABANDONED"`, else `self.tasks.transition(task_id, "ABANDONED", ..., force=True, reason="abandoned")`, records evidence. Tests: `tests/test_dead_letter.py`, `tests/test_audit_reliability_security.py`. Operator reconcile abandon path also present. | Confirmed. |
| `"ABANDONED"` inconsistent with FSM/`TERMINAL`/`TRANSITIONS` in `aj/task.py` (Doc 56 §3, §5, §18) | **VERIFIED FROM CURRENT SOURCE** | `aj/task.py`: `TERMINAL = (COMPLETED, ABORTED, CANCELLED, DEAD_LETTER)`; `TRANSITIONS` defines known states but excludes `"ABANDONED"`; `TaskStore` validation/import/reload logic checks status membership in `TRANSITIONS` and terminal consistency against `TERMINAL` (inspected). Yet runtime code/tests persist and specially handle `"ABANDONED"` (`aj/orchestrator.py`, `aj/consistency.py`, tests). | **Confirmed inconsistency/risk.** Not “everywhere undefined” (special handling exists), but model/persistence consistency is unsafe/unresolved. |
| Operator `Aj.reconcile` has authz/evidence/ownership safeguards but delegation integration unproven (Doc 56 §3, §4) | **PARTIALLY VERIFIED** | `aj/orchestrator.py::Aj.reconcile` (operator): intent/outcome evidence (`_op_record_intent/_op_progress/_op_outcome`), privileged authorization/audit, lease ownership safety, conflict/evidence checks for some actions, actions `abort|dead_letter|abandon|clear_recovery_required` (inspected sections). CLI wrapper `aj/__main__.py::_cmd_reconcile` observed. Tests: `tests/test_audit_reliability_security.py` (grep). No delegation-specific guards observed in inspected logic. | Correctly characterized as partially safe generally, delegation-unproven. |
| `_prepare_delegated_child_for_scheduling` checks parent cancelled/unverifiable but not full delegation revocation/permission/current narrowing (Doc 56 §3, §4, §10) | **VERIFIED FROM CURRENT SOURCE** | `aj/orchestrator.py::Aj._prepare_delegated_child_for_scheduling`: reads delegation ctx, fails/aborts if parent missing or status in `CANCELLED/CANCEL_REQUESTED/ABORTED/DEAD_LETTER`; advances/prepares and authorizes to `AUTHORIZED` via capability blocker/`authorizer.authorize(..., approval="", user_requested=True, actor=...)`; preserves/sets delegation snapshot fields. No check of delegation record status/revocation/assignment linkage/current permission narrowing beyond preserved context observed. | Confirmed. |
| `_delegated_permission_guard` enforces current parent/delegation linkage/status and snapshot envelope checks in covered execute path (Doc 56 §3, §4) | **PARTIALLY VERIFIED** | `aj/orchestrator.py::Aj._delegated_permission_guard`: requires delegation ctx and valid permission decision/effective list; checks parent existence/status, delegation record existence/match/status/child linkage (if stores/id present), effective ⊆ requested/parent snapshots, logical-internal scope restriction. Called from `_execute` when `spec` present. | Stronger than “snapshot-only”, but not proof of universal path coverage or full current-source permission revalidation. |
| `_before_task_transition` guards only `COMPLETED` for delegation parents (Doc 56 §3) | **VERIFIED FROM CURRENT SOURCE** | `aj/orchestrator.py::Aj._before_task_transition`: returns unless non-forced `status == COMPLETED`; blocks if any parent delegation aggregation `!can_complete` or `requires_manual_review` or unverifiable (fail-closed). | Confirmed scope. |
| Completion guard/hook wiring exists (Doc 56 context) | **VERIFIED FROM CURRENT SOURCE** | `aj/orchestrator.py` `Aj.__init__`: sets `self.tasks.after_transition = self._on_task_transition` and monkey-patches `self.tasks.transition` to call `_before_task_transition` then original transition (wrapped in try/except). `TaskStore.transition` fires `after_transition` post-persist. | Wiring observed; robustness/coverage of all transition callers still requires proof. |
| `_reconcile_delegation_parent` apply is mutating (child preparation + evidence persistence); dry-run/apply separated (Doc 56 §3, §9) | **PARTIALLY VERIFIED** | `aj/orchestrator.py::Aj.reconcile_delegation_parent` and `_reconcile_delegation_parent`: dry-run default; apply path may call `_prepare_delegated_child_for_scheduling` for children and persists delegation evidence/history/provenance (inspected). Bounded batch, snapshot-hash/idempotency logic present. | Confirmed mutating apply semantics; safety/idempotency under all races not proven. |
| Scheduler eligibility/admission/dispatch lacks explicit delegated parent-cancellation/authority checks (Doc 56 §3, §4, §6) | **PARTIALLY VERIFIED** | `aj/scheduler.py::Scheduler.evaluate_eligibility`: rejects terminal/waiting-approval/recovery-required/active or uncertain/in-flight, non-dispatchable states, deadline exceeded, unsatisfied deps, capability blocker, untrusted persistence, etc. (inspected sections). `_dispatch_one` records intent, acquires lease, rechecks eligibility, dead-letters on deadline, calls `aj.resume(task_id, leased=True)`, handles evidence failures. **No explicit delegation-parent/delegation-record authority/cancellation checks observed.** | Doc 56 claim directionally correct; scheduler is conservative in other dimensions but delegation-authority-aware enforcement not evidenced. |
| Delegation contract lacks explicit per-child required/optional classification (Doc 56 §3, §7) | **VERIFIED FROM CURRENT SOURCE** | `aj/delegation.py::DelegationRequest` fields include `aggregation_policy`, `required_child_ids`, `child_specs` but no explicit per-child required/optional field (inspected). Aggregation derives required set from policy/ids in orchestrator/delegation usage. | Confirmed core policy/model gap vs Doc 54. |
| SQLite/WAL test exists with stated name; issue environment-sensitive in controlled run (Doc 56 §1, §14 context) | **VERIFIED FROM CURRENT SOURCE** and **VERIFIED BY EXECUTABLE TEST** (limited, controlled) | Test: `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (4 workers × 20 writes, fork, shared SQLite `MemoryStore`, WAL per `aj/memory.py`). Runs: (1) `python3 -m pytest -q tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` → **PASS** (0.70s). (2) `--basetemp /tmp/aj-pytest-basetmp` → **PASS** (0.11s). (3) `--basetemp "/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp"` (approved path, NTFS-backed mount context likely) → **FAIL** `sqlite3.OperationalError: disk I/O error` during forked worker `MemoryStore.__init__ -> executescript(_SCHEMA)` (captured traceback). | Strong controlled evidence of storage/location sensitivity on that basetemp path; not sufficient alone for product-defect vs environment attribution or full-suite disposition. |
| Crash/concurrency/stale-writer claims limited by feasibility/mechanisms (Doc 56 §12–§13) | **PARTIALLY VERIFIED** | No fault-injection seams for specific write/cross-store boundaries identified; reconciliation uses snapshot-hash comparison but no general CAS/version enforcement observed; in-process locks/guards exist. | Correct caution; specific boundaries remain NOT VERIFIABLE/UNSUPPORTED as stated. |
| Exhaustive callable/wrapper closure achieved (Doc 56 §4) | **CONTRADICTED BY CURRENT EVIDENCE** (as a completeness claim) / **VERIFIED as limitation** | Doc 56 itself states non-exhaustiveness; this pass found additional wrappers/callers not fully analyzed (e.g. `aj/__main__.py::_cmd_reconcile`, `aj/__main__.py::_cmd_cancel/_cmd_retry/_cmd_recover`, `aj/inbox_cli.py::requeue_stale` and inbox worker flows) and did not trace all CLI/API/UI/integration surfaces. | Doc 56 appropriately caveated this; S0 remains incomplete for closure. |
| Independent verification operationalized as protocol only (Doc 56 §15–§16) | **VERIFIED FROM CURRENT SOURCE** (documented) | Protocol/manifest defined in Doc 56; no independent reviewer/session executed in this pass. | No implementation/verification claim made. |

---

## 4. Corrected source-enumerated callable inventory (S0, best-effort; not exhaustive)

**Legend:** classifications reflect current evidence for delegated-context safety relative to Doc 54. “Guarded” requires demonstrated enforcement at the relevant boundary; “Supported but not proven” means path exists but delegation-safety proof incomplete.

| Group | Callable (`file::symbol`) | Observed callers (non-exhaustive) | Mutates / affects | Authz checks | Delegation checks | Parent lifecycle checks | Persisted evidence (typical) | Safe for delegated tasks now? | Required disposition |
|---|---|---|---|---|---|---|---|---|---|
| Task create/execute | `aj/orchestrator.py::Aj.handle` | API/runtime/CLI surfaces (not fully enumerated) | task routing/authz/state transitions, lease, execute dispatch | capability/policy/authorizer, mandatory audit in path | via context/execute guard where applicable | limited/indirect | task events, audit, journal/receipt, attempts/execution linkage | **Not proven** | **SUPPORTED BUT NOT PROVEN** (prove per variant or block unsupported variants) |
| Execute boundary | `aj/orchestrator.py::Aj._execute` | handle/resume/retry flows | `EXECUTING`→verify/complete/fail, executions/attempts/receipts/journals | capability blocker/adapter checks; delegated guard when spec+ctx | `_delegated_permission_guard` (partial current-state + snapshots) | indirect via guard/task state | execution/attempt/receipt/journal/audit/task state | **Partially guarded** | **SUPPORTED BUT NOT PROVEN** (complete boundary/path coverage) |
| Scheduler eligibility/queue/admission | `aj/scheduler.py::Scheduler.evaluate_eligibility`, `queue`, `evaluate_admission` (and helpers) | scheduler run flows, inspections (not fully enumerated) | decisions/evidence reads/writes (ledger observational/mgmt) | capability blocker, persistence/capacity checks | **none explicit observed** | **none explicit observed** (parent delegation) | scheduler decision/dispatch ledger (durable mode) | **Not proven** | **SUPPORTED BUT NOT PROVEN** → require delegation-aware checks or **EXPLICITLY BLOCK** delegated scheduling until proven |
| Scheduler dispatch/run | `aj/scheduler.py::Scheduler.run_once`, `_dispatch_one` | CLI/operator/runtime (unknown) | dispatch intents/results, leases, may call `Aj.dead_letter` (deadline), calls `Aj.resume(leased=True)` | eligibility rechecks, lease, evidence fail-closed (durable) | **none explicit observed** | deadline→dead-letter only | scheduler ledger, lease/task/execution effects via resume | **Not proven** | **SUPPORTED BUT NOT PROVEN** (must block unsafe deadline/delegated cases) |
| Leased/direct resume | `aj/orchestrator.py::Aj.resume`, `Aj._resume_locked` | scheduler, direct callers (unknown) | resumes task toward execution | resume preconditions + execute guard | execute-time guard downstream | indirect | task/execution/attempt evidence | **Not proven** | **SUPPORTED BUT NOT PROVEN** |
| Retry | `aj/orchestrator.py::Aj.retry`, `Aj._retry_locked` | `aj/__main__.py::_cmd_retry`, other callers unknown | retry transitions/re-exec/escalation | retry policy/budget/safety checks; execute guard downstream | **not explicitly revalidated pre-exec in inspected slice** | indirect | attempts/events/audit/journal | **Not proven** | **SUPPORTED BUT NOT PROVEN** (block delegated retry when authority ambiguous) |
| Recovery | `aj/orchestrator.py::Aj.recover`, `Aj._recover_locked`, `Aj._assess_recovery`, `Aj.recovery_inspection`; `aj/recovery.py::RecoveryManager.scan/recover/classify` | `aj/__main__.py::_cmd_recover`, internal | inspection/recovery decisions, possible transitions/resume | conservative assessment/ownership/lease handling (partial) | **unproven for delegated ambiguity/authority** | indirect | recovery/inspection evidence, task state | **Not proven** | **SUPPORTED BUT NOT PROVEN** (fail-closed/manual-review for delegated ambiguity) |
| Delegation creation/assignment | `aj/orchestrator.py::Aj.delegate`, `_ensure_delegation_stores`, `_seed_logical_agents`; `aj/delegation.py::DelegationRequest.validate`, `match_agent`, `narrow_permissions`, stores | API/callers unknown | delegation/assignment/child task records, prep may occur | request validation, narrowing, parent checks in flow | partial (structural/narrowing) but **no explicit required/optional classification enforcement** | parent existence/chain checks (per delegation utils) | delegation/assignment/task/journal evidence | **Not proven / unsafe for policy completeness** | **SUPPORTED BUT NOT PROVEN** → fail closed on missing/malformed/contradictory classification (design required) |
| Delegated child preparation | `aj/orchestrator.py::Aj._prepare_delegated_child_for_scheduling` | `Aj.delegate`, `Aj._reconcile_delegation_parent` (apply) | child transitions to planned/authorized/waiting/aborted/failed as applicable, authz context | capability blocker, authorizer | parent-cancel/unverifiable check; **no delegation-record revocation/permission-currentness revalidation** | parent status check (subset) | task transitions/authz context/journal | **Not proven** | **SUPPORTED BUT NOT PROVEN** (must become fully guarded or blocked for unsafe cases) |
| Delegation reconciliation (read/apply) | `aj/orchestrator.py::Aj.reconcile_delegation_parent`, `_reconcile_delegation_parent`, `_on_task_transition`, `_before_task_transition`, `delegation_status`, `delegation_monitor`; `aj/delegation.py::aggregate_parent_progress`, `detect_delegation_anomalies` | hooks, explicit API, status/monitor callers unknown | aggregation/evidence/history; apply may prep children and persist delegation evidence; completion guard blocks COMPLETED | reconcile lock/guards, bounded/idempotent logic | aggregation/record checks partial; apply safety depends on prep/guards | completion guard uses aggregation | delegation evidence/history, task outcomes | **Not proven** (apply mutating) | **SUPPORTED BUT NOT PROVEN** with strict read-only vs mutating contracts; block unsafe apply |
| Task cancellation | `aj/orchestrator.py::Aj.cancel_task`, `_cancel_locked`; `aj/task.py::TaskStore.cancel` | `aj/__main__.py::_cmd_cancel`, others unknown | task `CANCELLED` or `CANCEL_REQUESTED` | FSM/state checks | **no delegation propagation/orchestration** | none for children | task events/audit/memory | **Not proven** for delegated semantics | **SUPPORTED BUT NOT PROVEN** (define semantics; enforce boundaries) |
| Dead-letter | `aj/orchestrator.py::Aj.dead_letter` | operator reconcile, scheduler deadline, tests | task→`DEAD_LETTER` (if legal), evidence | transition legality | **none** | **none** | audit/journal/memory/task | **Unsafe in delegated contexts** | **EXPLICITLY BLOCKED** for delegated parent/child/linked contexts (proposed); review scheduler-deadline interaction |
| Requeue | `aj/orchestrator.py::Aj.requeue` | tests; wrappers unknown | forced `DEAD_LETTER`→`PLANNED`, attempt append, clears decision flag | none relevant to delegation | **none** | **none** | audit/journal/memory/task | **Unsafe in delegated contexts** | **EXPLICITLY BLOCKED** for delegated contexts (proposed) |
| Abandon | `aj/orchestrator.py::Aj.abandon` | operator reconcile, tests | forced→`"ABANDONED"` (non-FSM), evidence | idempotency on string state | **none** | **none** | audit/journal/memory/task/error | **Unsafe in delegated contexts; model inconsistent** | **EXPLICITLY BLOCKED** for delegated contexts (proposed) + resolve `ABANDONED` disposition |
| Operator reconcile (admin) | `aj/orchestrator.py::Aj.reconcile` (operator) | `aj/__main__.py::_cmd_reconcile`, tests | intent/outcome evidence, abort/dead_letter/abandon/clear_recovery_required transitions via guarded logic | privileged authz, ownership/lease, conflict/evidence checks (partial) | **unproven** | action-specific preconditions | operation evidence, audit, task/journal/inspection | **Not proven** for delegated contexts | **SUPPORTED BUT NOT PROVEN** generally; **EXPLICITLY BLOCKED/CONSTRAINED** for delegated-affecting actions until proven |
| CLI wrappers | `aj/__main__.py::_cmd_cancel/_cmd_retry/_cmd_recover/_cmd_reconcile` | CLI | invoke orchestrator APIs | delegate to underlying | delegate to underlying | delegate to underlying | CLI output + underlying records | inherits underlying | classify with underlying; include in S0 closure |
| Inbox/UI worker actions | `aj/inbox_cli.py::requeue_stale` / worker loop | inbox worker CLI | updates inbox item status to queued (observed grep context), not direct `Aj.requeue` call in snippet | inbox-store specific (not inspected) | unknown relation to AJ task delegation | unknown | inbox store (separate) | **Unknown** | **UNKNOWN — REQUIRES INVESTIGATION** (trace effect on AJ tasks/delegation, if any) |
| Diagnostics | `aj/orchestrator.py::Aj.consistency_check`, `Aj.storage_diagnostics` | callers unknown | expected read/inspect | implementation-specific | unknown | unknown | reports | unknown | **UNKNOWN — REQUIRES INVESTIGATION** (must prove read-only and honest) |
| Force/lifecycle hooks | `aj/task.py::TaskStore.transition/save/apply/mutate/import_record/reload`; orchestrator hook wiring in `Aj.__init__` | all task mutations | persistence/lifecycle enforcement, callbacks | structural/FSM/force rules | hook-level delegation guard only for COMPLETED pre-check (via orchestrator patch) | limited | JSONL task records/history | foundational, but forced/admin paths risky | **SUPPORTED BUT NOT PROVEN** for delegated-safe invariants; restrict forced transitions in delegated contexts |

**Remaining callable/wrapper gaps (explicit):** full enumeration/tracing of all CLI subcommands, orb/UI, inbox-to-AJ bridges, integrations (`integrations/`), internal helper callers, and any alternate execution/dispatch APIs was **not completed**. These remain **UNKNOWN — REQUIRES INVESTIGATION** and must be treated as unavailable for safety claims until S0 closes.

---

## 5. Remaining callable and wrapper gaps

- **CLI/API surface:** only selected `aj/__main__.py` commands inspected; other subcommands/wrappers not inventoried.
- **`aj/inbox_cli.py` / inbox store interactions:** `requeue_stale` and worker behavior observed only superficially; relationship to AJ task lifecycle/delegation not traced.
- **UI/orb/integrations:** `integrations/`, `aj/orb*`, and other frontends not traced.
- **Internal call graph:** all callers of `TaskStore.transition(..., force=True)`, `dead_letter/requeue/abandon/reconcile` (operator and delegation), and all resume/execute entry variants not exhaustively enumerated.
- **Scheduler internals:** admission/capacity helpers and all eligibility predicates not fully line-traced for delegation context.
- **Diagnostics/reporting paths:** `consistency_check`, `storage_diagnostics`, monitor/status consumers not proven read-only/honest.
- **Classification gap consequence:** any unclassified path must be treated as **not safe** for delegated invariant claims.

---

## 6. Policy recommendations (conservative defaults)

*Doc 54 is acceptance authority. Defaults below are recommended to minimize ambiguity/risk; semantics-changing or irreversible compatibility choices require explicit user decision where noted.*

| Topic | Recommended default (proposed) | Rationale | Requires user decision? |
|---|---|---|---|
| Required vs optional children | **Explicit per-child classification required** at delegation creation/validation (e.g. `required|optional` in child spec/record), deterministically linked to aggregation policy; `required_child_ids`/policy must be consistent and validated. | Doc 54: no silent default to optional; missing/malformed must fail closed. | **Yes (representation/migration choice)** |
| Missing/malformed/contradictory classification | **Fail closed**: reject request/mutation; do not create or advance unsafe delegation. Existing legacy/ambiguous records treated as unverifiable/manual-review (never auto-optional). | Prevents unsafe weakening (INV-01/03). | No for behavior; **Yes** for legacy-record handling/migration |
| Required child failed | Prevent parent `COMPLETED`; parent enters explicit non-success/manual-review disposition per approved mapping (do **not** mark success). Reconciliation allowed (safe); retry only by explicit approved policy/action. | Doc 54/unknown-state rule. | **Yes (exact parent state mapping)** |
| Required child independently cancelled | Prevent parent `COMPLETED`; treat as required policy not satisfied unless explicit approved exception (default **none**). | Conservative. | **Yes (mapping/exception policy)** |
| Required child unresolved/ambiguous | Prevent parent `COMPLETED`; remain non-complete/unresolved/manual-review with evidence. | Fail closed. | **Yes (mapping)** |
| Optional child failure/cancellation | Tolerated **only** when explicitly classified optional, all required satisfied, and approved tolerance policy permits; failure/cancellation remains visible. Default tolerance policy: **explicit, not implicit**. | Prevents silent success on partials. | **Yes (tolerance policy semantics)** |
| Parent cancellation | Durable cancellation blocks prohibited future prep/dispatch/authorization/execute at enforced boundaries; cooperative handling for in-flight work; no resurrection, no fabricated success; late outcomes traceable. | Doc 54 INV-04. | No for principle; **Yes** for child propagation/orchestration semantics if introduced |
| Late results | Record as traceable evidence; must not change authoritative cancelled/prohibited outcome into success or resurrect work. If ambiguous, unresolved/manual-review. | Doc 54. | No (conservative) |
| Reconciliation dry-run vs apply | **Dry-run:** strictly read-only, no authoritative mutation. **Apply:** explicit mutating operation with authz/cancel/lifecycle/current-state checks, bounded/idempotent behavior, provenance, fail-closed on conflict/ambiguity. | Current apply mutates child prep. | No |
| `ABANDONED` lifecycle semantics | **Recommended disposition (conservative):** (A) formally model `ABANDONED` as an explicit declared terminal lifecycle state in FSM/validation/terminal sets with clear transition/import/consistency semantics and compatibility handling, **or** if not approved, (B) block/replace use with an existing valid terminal state plus explicit evidence — but **do not silently normalize**. Given existing persisted/runtime behavior and tests, (A) with explicit specification is likely the least disruptive **if** approved; until then treat as **model-inconsistent / not certification-safe**. | Resolves confirmed inconsistency while preserving evidence/honesty. | **Yes (explicit disposition/compatibility)** |
| Existing records/migration/backward compatibility | Legacy records lacking explicit classification or using inconsistent states must **not** be auto-interpreted as safe/success; use read-time fail-closed/manual-review markers and an explicitly approved, reversible migration plan before enforcement changes that alter meaning. No destructive rewrite. | Preserves pre-existing data and avoids fabricated correctness. | **Yes** |

---

## 7. Required/optional and parent outcome mapping (proposed, Doc 54-aligned)

*No `PARTIAL` task status. Parent `COMPLETED` forbidden unless all required satisfied per explicit policy with no ambiguity/manual-review. Exact non-success parent state labels require approved mapping (see unresolved decisions).*

| Child condition | Required child → parent outcome (proposed) | Optional child → parent outcome (proposed) | Delegation/assignment/evidence (proposed) | Reconcile | Retry | Admin intervention |
|---|---|---|---|---|---|---|
| Successful | Eligible for completion only when **all required** satisfied and no ambiguity | Compatible with completion if required satisfied and policy allows | Success evidence, aggregation satisfied | Yes (idempotent) | N/A | No |
| Failed | **Not COMPLETED**; explicit non-success/manual-review disposition | Tolerated only under explicit policy and required satisfied; failure visible; else non-success | Failure evidence, aggregation non-completable/manual-review | Yes (safe) | Only if explicitly allowed/safe | Likely |
| Independently cancelled | **Not COMPLETED** (default no exception); explicit non-success/manual-review disposition | Tolerated only under explicit policy; visible | Cancellation evidence, aggregation impact recorded | Yes (safe) | Policy-dependent (default no) | Likely |
| Unresolved | **Not COMPLETED**; remain unresolved/non-complete | Cannot justify success if required unmet/unresolved; policy must be explicit | Pending/non-terminal evidence, waiting counts | Yes | No (as success substitute) | Maybe |
| Ambiguous/unverifiable | **Not COMPLETED**; fail closed/manual-review | **Fail closed** where safety/policy affected | Contradiction/missing-evidence findings, uncertainty surfaced | Diagnostic/read-safe; mutating apply only if proven safe | No blind retry | Yes |
| Missing/malformed classification | **Fail closed** (reject/invalid, never success) | **Fail closed** (never default optional) | Validation rejection or inconsistency evidence | Diagnostic only | No | Yes if persisted |

---

## 8. `ABANDONED` disposition recommendation

- **Current evidence:** `Aj.abandon` and operator reconcile set/preserve `"ABANDONED"`; tests (`tests/test_dead_letter.py`, `tests/test_audit_reliability_security.py`) rely on it; `aj/consistency.py` treats it specially. **But** `aj/task.py` excludes `"ABANDONED"` from `TRANSITIONS`/`TERMINAL`, while store validation/reload/import enforce membership/terminal consistency — creating a **confirmed structural inconsistency**. [VERIFIED FROM CURRENT SOURCE]
- **Recommendation:** **explicitly decide and specify before S1 enforcement**.
  - **Preferred conservative path (proposed):** formalize `ABANDONED` as a declared terminal state with defined allowed transitions/entry rules, import/load compatibility, consistency-check behavior, and delegation-safety constraints (blocked for delegated contexts unless separately proven safe). Document migration/compatibility for existing records.
  - **Alternative:** map abandonment to an existing valid terminal state (e.g. `DEAD_LETTER`/`CANCELLED`/`ABORTED` as policy-appropriate) with unambiguous evidence semantics and compatibility handling.
  - **Interim:** treat `ABANDONED`-affecting paths as **not certification-safe/blocked for delegated contexts** until disposition implemented and proven.
- **Non-negotiable:** no silent normalization; no evidence erasure; no conversion to success.

---

## 9. Executable proof matrix (S0 specification framework)

### 9.1 Per-spec minimum requirements (mandatory)
For every invariant and important callable path: initial persisted state; exact entry point; real execution path; expected state transitions; exact persisted records/fields to inspect; expected audit/evidence records; forbidden transitions/side effects; negative/adversarial scenarios; proof that actual boundary exercised; exact test command; independent rerun procedure. Mocks must not bypass core logic under test.

### 9.2 Matrix (prioritized, minimum set)

| ID | Inv/Req | Entry point (exact callable) | Initial persisted state (key) | Real path/boundary | Expected transitions & persisted fields | Expected evidence/audit | Forbidden outcomes/side effects | Negative/adversarial | Boundary-exercise proof | Command (template) | Independent rerun |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P-INV01-01 | INV-01/02 | `aj/orchestrator.py::Aj.handle`→`_execute` | Valid delegated parent/child/delegation/assignment/authz context | Handle/execute with real guard | Deny or allow only per current valid authority; assert task status/attempt/execution records | Guard/authz/audit/journal/receipt as applicable | Unauthorized execution, widening, success on invalid state | Revoked/missing/malformed/widened/contradictory authz, cancelled parent | Assert guard decision path invoked and persisted outcome; no mocked guard | `python3 -m pytest -q <test>::<name>` (future, authorized) | Clean rerun by independent verifier + record/state inspection |
| P-INV01-02 | INV-01/04 | `aj/scheduler.py::Scheduler._dispatch_one`/`run_once`→`Aj.resume` | Authorized delegated child eligible absent delegation checks; parent cancelled/revoked | Admission/dispatch/resume/execute boundary | Block/defer/fail-closed; no prohibited resume/execute | Scheduler ledger, lease/task/execution evidence | Prohibited dispatch/execution | Deadline+delegated, cancel between claim and resume | Inspect ledger + absence of execution success records | future pytest cmd | independent rerun |
| P-INV01-03 | INV-01/02/04 | `aj/orchestrator.py::Aj._prepare_delegated_child_for_scheduling` | Delegated child with delegation record revoked/permissions reduced/cancelled parent | Prep (and prep-via-apply reconcile) | Refusal/abort/no unsafe AUTHORIZED progression | Prep result, task transitions/events | Unauthorized authorization/prep, resurrection | Missing linkage, malformed context, stale snapshots | Direct callable invocation + store diff | future pytest cmd | independent rerun |
| P-INV01-04 | INV-01/03/04 | `aj/orchestrator.py::Aj.retry`, `Aj.recover` | Failed/recovery-required delegated task with revoked/ambiguous authority | Retry/recovery decision to exec boundary | Fail-closed/manual-review, no blind retry/success | Operation/recovery evidence, attempts unchanged except allowed records | Unsafe retry, duplicate execution, fabricated success | Ambiguous execution/lease/evidence | Inspect attempts/executions/status | future pytest cmd | independent rerun |
| P-INV03-01 | INV-03 | `Aj._before_task_transition`/task completion paths | Parent with required children in failed/cancelled/unresolved/ambiguous states (explicit classification) | Attempt parent `COMPLETED` and reconcile/aggregation | COMPLETED rejected; non-success/manual-review mapping per policy | Aggregation, transition refusal, delegation evidence | False COMPLETED, partial-as-success | Missing/malformed classification, policy contradiction | Direct transition attempt + guard outcome | future pytest cmd | independent rerun |
| P-INV04-01 | INV-04 | `Aj.cancel_task`, prep/dispatch/execute/reconcile boundaries | Parent cancelled durably; child prepared/running/late-completing | Cancel + boundary actions + late outcome hook/reconcile | No prohibited prep/dispatch; late outcome traceable; no resurrection/success | Cancel/transition/reconcile evidence timeline | Resurrection, prohibited work, success fabrication | Race barriers: cancel vs prep/dispatch/complete | Multi-step sequence with store snapshots | future pytest cmd | independent rerun |
| P-INV05-01 | INV-05 | `Aj.reconcile_delegation_parent` (dry-run/apply), `delegation_monitor` | Mixed child states, unchanged/changed/contradictory snapshots | Dry-run, apply, repeat, concurrent apply | Dry-run zero authoritative mutation; apply idempotent/bounded/provenanced or fail-closed | Reconciliation history/provenance, snapshot hashes, monitor findings | Dry-run mutation, duplicate logical outcomes, stale overwrite, unsafe completion | Contradiction/stale/duplicate, concurrent calls | Before/after deep equality for dry-run/monitor; apply evidence checks | future pytest cmd | independent rerun |
| P-INV06-01 | INV-06 | `Aj.recovery_inspection`/`Aj.recover`/`RecoveryManager` | Persisted fixtures representing declared restart/ambiguous boundaries (isolated temp store) | App-level reload/restart from durable fixture | Explicit recovery/unresolved/manual-review; never silent success/duplication | Inspection/recovery records, task/execution state | Success on ambiguity, unsupported durability claim | Missing/contradictory durable evidence | Prove fixture is persisted and reloaded (no in-memory fabrication) | future pytest cmd | independent rerun |
| P-INV07-01 | INV-07 | Competing callables per feasible scenario (reconcile/reconcile, cancel vs prep, etc.) | Shared persisted targets with known pre-state | Single-process barriered concurrent/ordered invocations | Deterministic allowed outcome, consistent authoritative state | Concurrency-relevant evidence/state snapshots | Contradictory terminals, silent overwrite, corruption | Stale snapshot only if mechanism exists | Identify lock/synchronization point and final-state assertions | future pytest cmd | independent rerun |
| P-INV08-01 | INV-08 | `aj/delegation.py::detect_delegation_anomalies`, `Aj.delegation_monitor` | Fixtures for supported anomaly classes and healthy states | Read-only detection/monitor calls | Correct findings with IDs/evidence; healthy no mutation | Findings payloads; before/after equality | Mutation/repair, false healthy | Edge/missing records | Snapshot equality of authoritative stores | future pytest cmd | independent rerun |
| P-INV09-01 | INV-09 | All supported mutating/refusing boundaries above | Per-path cases including rejection/ambiguity | Real calls | Correlatable IDs and required records emitted | Task events/attempts, receipts/journal/audit, delegation/assignment/reconciliation/operation evidence | Missing evidence on key decisions, fabricated success | Failure/ambiguity/interruption fixtures | Assert specific record fields/IDs present | future pytest cmd | independent rerun |
| P-INV10-01 | INV-10 | Admin/operator/unsupported paths (`dead_letter/requeue/abandon/operator reconcile` delegated cases, wrappers) | Delegated contexts and unsupported requests | Invoke path | Explicit block/refusal/unsupported result; no unsafe mutation | Refusal/operation evidence, unchanged state | Bypass, hidden capability, false guarantee | Privilege/capability escalation attempts | State diff + result/output check | future pytest cmd | independent rerun |

*Full per-callable instantiation is required at S0 closure/S1+ planning refinement; this matrix defines the mandatory minimum framework and priorities.*

---

## 10. Crash/concurrency feasibility

### 10.1 Crash/recovery feasibility (inspectable now)
| Boundary | Feasibility | Real seam/mechanism | Allowed claim | Classification |
|---|---|---|---|---|
| Process restart with previously persisted state | **Conditionally feasible (app-level)** | Durable stores reloadable in isolated temp dirs; recovery/inspection APIs exist | Behavior observed from real persisted fixtures only | Potentially verifiable within declared boundary |
| Termination between explicit application operations | **Limited/conditional** | Only if separable operations yield observable durable intermediate state | Case-specific, evidence-backed only | Partially feasible / often NOT VERIFIABLE |
| Failure at specific write boundary | **Not feasible now** | No approved deterministic injection seam (test seam exists in codebase but not an approved/implemented fault-injection mechanism for this plan) | None | NOT VERIFIABLE |
| Cross-store partial persistence | **Not deterministically verifiable now** | Independent stores, no CAS/atomic protocol | Detection/uncertainty if observed | NOT VERIFIABLE / UNSUPPORTED (repair/correctness) |
| Database/WAL failure | **Investigable; guarantees not certifiable** | Observed failures (OPEN) | Evidence-bounded disposition only | OPEN |
| Filesystem I/O failure | **Limited** | Environment-dependent | Observed fail-closed behavior only | NOT VERIFIABLE (general) |
| OS crash / power loss | **No** | None | None | UNSUPPORTED / NOT VERIFIABLE |
| Multi-process recovery | **No** | Out of boundary | None | UNSUPPORTED |

### 10.2 Concurrency/stale-state feasibility
- **Real mechanisms observed:** in-process `RLock`/guards in task store, scheduler, lease/dispatch/reconciliation paths; reconciliation snapshot-hash comparison/idempotency logic; task transition legality checks. [VERIFIED FROM CURRENT SOURCE]
- **Not observed as proven mechanism:** general compare-and-set/versioned stale-writer protection across stores/records. [NOT VERIFIABLE from inspected evidence]
- **Feasible to test (single-process):** barriered races for selected call pairs (e.g. concurrent reconcile apply, cancel vs prep/dispatch boundaries) with authoritative state snapshots. [PARTIALLY VERIFIED]
- **Cannot claim:** general race freedom, multi-process/distributed safety, universal stale-writer protection, or correctness beyond exercised interleavings. [UNSUPPORTED/NOT VERIFIABLE]

---

## 11. SQLite/WAL evidence and disposition

### 11.1 Verified test identity
- **Exact test:** `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` [VERIFIED FROM CURRENT SOURCE]
- **Behavior (inspected):** fork multiprocessing, 4 worker processes × 20 writes to shared SQLite DB via `MemoryStore` (`aj/memory.py`, WAL mode schema/init), asserts all worker exit codes 0 and event count complete.

### 11.2 Controlled, non-destructive runs (executed now)

| Run | Command | Temp/basetemp | Result | Key observations |
|---|---|---|---|---|
| S1 | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` | default | **PASS** (1 passed, ~0.70s) | No failure in this isolated run. |
| S2 | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event --basetemp /tmp/aj-pytest-basetmp` | `/tmp/aj-pytest-basetmp` | **PASS** (1 passed, ~0.11s) | Isolated pass on local `/tmp` path. |
| S3 | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event --basetemp "/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp"` | approved external path on mounted drive | **FAIL** (1 failed, ~0.69s) | Worker fork failed: `sqlite3.OperationalError: disk I/O error` at `aj/memory.py::MemoryStore.__init__ -> self._conn.executescript(_SCHEMA)`; test failed on `assert all(process.exitcode == 0 ...)`. |

### 11.3 Evidence-based disposition
- **Disposition:** **OPEN — environment/storage sensitivity evidenced; product defect not established.** [OPEN ISSUE]
- **Supports:** failure is reproducible in this controlled isolated run on the specific basetemp path/mount context (S3) while same test passes on default and `/tmp` basetemps (S1,S2). This is consistent with filesystem/mount/SQLite-WAL/fork interaction sensitivity in that environment.
- **Does not establish:** root cause, AJ product defect, or full-suite behavior (full suite not rerun). Prior report-derived full-suite result (576 passed, 1 failed, 13 warnings) remains **REPORT-ONLY / NOT INDEPENDENTLY REPRODUCED** in this pass.
- **Certification impact:** blocks/qualifies any claim requiring stable green full-suite results or storage/durability reliability in the affected environment until further controlled evidence and approved disposition. Must not weaken/skip/delete/rewrite the failing test; no fs repair/migration performed.

### 11.4 Additional data to capture in follow-up (non-destructive)
Filesystem type/mount options for basetemp paths (`findmnt`/`mount`/`df -T`), exact DB/WAL/SHM paths, Python/SQLite versions, multiprocessing start method details, repeated-run matrix, and suite-order/load comparisons under controlled basetemps.

---

## 12. Independent verification protocol (operational)

- **Preconditions:** exact source revision + complete working-tree state recorded; test environment and commands documented.
- **Independence:** verification performed by a **separate reviewer agent/session or distinct audit pass** not relying on implementer success narrative; implementer **must not** self-certify independent verification.
- **Procedure per criterion:** (1) map to Doc 54/56/57 requirement & spec; (2) inspect source enforcement point and test body (confirm real boundary, no core-mocking bypass); (3) clean rerun of exact documented commands and capture exit code/output; (4) inspect persisted stores/records/fields and forbidden side effects; (5) review failures/skips/warnings; (6) record verdict.
- **Verdict taxonomy:** `NOT STARTED | IMPLEMENTED — NOT VERIFIED | TESTED — PARTIAL | VERIFIED WITHIN DECLARED BOUNDARY | FAILED | BLOCKED | UNSUPPORTED | NOT VERIFIABLE`.
- **Evidence manifest per criterion:** requirement ID, test ID, source revision, working tree state, exact command/cwd/env, test file/function, actual callable path, persisted evidence inspected, output/log ref, expected vs observed, reviewer identity, verdict, limitations.
- **Prohibitions:** no status inflation from passing tests alone; no claim beyond demonstrated boundary; no hidden/skipped/weakened failures.

---

## 13. S0 exit-criteria assessment

| S0 exit criterion | Status | Evidence / gap |
|---|---|---|
| A. Source-enumerated callable inventory produced (best-effort) | **PARTIAL** | §4 provides corrected inventory for key groups and wrappers inspected; exhaustive closure not achieved (CLI/UI/integrations/inbox bridges/internal callers remain). |
| B. All relevant paths classified and unproven paths not treated as safe | **PARTIAL** | Key paths classified; unknown/untraced paths explicitly flagged as requiring investigation and unsafe for claims. |
| C. Safe blocking strategy for non-provable/unsafe paths | **PARTIAL/COMPLETE (design-level)** | §4–§6 propose narrow block-first dispositions for delegated contexts (dead-letter/requeue/abandon/force/admin/scheduler gaps) pending implementation; enforcement points identified conceptually, not implemented. |
| D. Policy/model decisions closed (required/optional, outcomes, cancellation, reconciliation, ABANDONED, migration) | **PARTIAL** | Conservative recommendations and mappings provided (§6–§8); semantics-changing/compatibility decisions (classification representation/migration, exact outcome-state mapping, ABANDONED disposition, optional tolerance details, delegated child propagation) remain open user decisions. |
| E. Executable proof specifications/matrix for invariants and important paths | **PARTIAL** | §9 defines mandatory framework and prioritized minimum matrix; full per-callable instantiation and command-finalization pending S0 closure of inventory/policy. |
| F. Crash/concurrency feasibility bounded to demonstrable mechanisms | **COMPLETE (planning-level)** | §10 documents feasible/conditional/not-verifiable/unsupported boundaries and mechanism gaps. |
| G. SQLite/WAL evidence gathered and disposition stated | **PARTIAL** | §11 verifies test identity and provides controlled isolated evidence (pass/pass/fail by basetemp) with OPEN disposition; full-suite and deeper env characterization not completed. |
| H. Independent verification protocol defined | **COMPLETE (planning-level)** | §12. |

**S0 overall:** **S0 PARTIALLY COMPLETE** — sufficient to guide a design-closure gate, not sufficient to authorize implementation.

---

## 14. Exact unresolved user decisions (escalate only if safe default insufficient)

| # | Decision | Why safe default cannot fully resolve | Recommended default / smallest choice set |
|---|---|---|---|
| 1 | **Required/optional classification representation & migration/compat** (explicit per-child field/derivation, storage, legacy-record handling) | Changes persisted contract/meaning and may require migration/compat policy affecting existing records and behavior. | **Recommend:** explicit per-child classification + strict validation, fail-closed for legacy/ambiguous records, approved reversible compat/migration plan. **Choices:** (A) explicit per-child field with versioned compat, (B) deterministic derivation rule with explicit validation (only if lossless and proven safe). |
| 2 | **Exact parent outcome-state mapping** for required-failed/cancelled/unresolved/ambiguous (and tolerated optional cases) within existing FSM or approved model change | User-visible lifecycle semantics and audit/operations expectations; FSM adequacy not one-to-one without approved mapping. | **Recommend:** map to existing non-success states with explicit evidence/manual-review semantics (no new PARTIAL, no success). **Need:** approved mapping table per case. |
| 3 | **`ABANDONED` disposition** (formalize in FSM+validation+terminal/import semantics vs remap to existing state vs keep blocked/legacy-limited) | Structural model/compatibility change with persisted behavior/test reliance. | **Recommend:** formalize as declared terminal state with explicit rules and delegated-context blocking, or remap if consistency preferred — but choose explicitly. |
| 4 | **Delegated-context admin/scheduler policy** (block vs guarded support for deadline dead-letter, operator actions, requeue/abandon, delegated dispatch) | Materially affects safety guarantees and allowed operations. | **Recommend:** **block/unsupported** for delegated contexts until individually guarded and proven; allow only narrowly justified non-delegated legacy behavior per evidence. |

*Other items (stale-writer mechanism feasibility, crash seams, SQLite attribution) are technical NOT VERIFIABLE/OPEN constraints to be handled by classification/evidence, not preference decisions.*

---

## 15. Recommended next stage and entry criteria

### Recommended next stage
- **Next:** **S0 Closure / Gate B+ Design-Closure (planning only)** — resolve §14 decisions, complete exhaustive callable/wrapper inventory and per-path dispositions, finalize policy/model/migration design artifacts, and instantiate per-callable executable proof specs. **Do not start S1 implementation.**

### Entry criteria for that next planning/design gate
- Doc 57 reviewed; decisions #1–#4 (and any required tolerances) provided or explicitly accepted as conservative defaults where safe.
- Agreed authoritative inventory scope (CLI/UI/integrations/inbox bridges included) and access/inspection plan.
- Approved direction for `ABANDONED` and legacy-record compatibility.
- Confirmation that Doc 54 remains acceptance authority and Gate C is not granted.

### Entry criteria for future S1 (implementation) — **not now**
- S0 COMPLETE (inventory closed, decisions resolved, designs/proof specs finalized), Gate B accepted for revised plan, **separate explicit Gate C implementation authorization**, and approved migration/compat/safety constraints documented.

**Stage decision:** **GATE B PASS WITH EXPLICIT LIMITATIONS** | **S0 PARTIALLY COMPLETE**. No S1/production changes started. No invariant implemented or verified by this report.