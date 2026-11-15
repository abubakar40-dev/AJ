# 35 — Phase 5A.6R3 Pre-Implementation Gap Audit (Scenario Certification & Remaining Gap Closure)

**Date:** 2026-11-14  
**Stage:** 5A.6R3 (corrective certification/closure, audit-before-implementation)  
**Status:** Audit complete for 5A.6R3 entry; no 5A.7 started.

## 1. Baseline, Git safety, and preservation (verified)

- **Repo:** `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- **Branch/HEAD (unchanged):** `main @ 468fdcebece5b25f02e53add4928d3650ef175f4`
- **`git status --short` at 5A.6R3 start:** **55 entries** (17 tracked modified, 38 untracked), all preserved.
  - Tracked modified: `aj/__main__.py`, `aj/config.py`, `aj/diagnostics.py`, `aj/ids.py`, `aj/orchestrator.py`, `aj/receipts.py`, `aj/recovery.py`, `aj/runtime.py`, `aj/scheduler.py`, `aj/task.py`, `aj/transfer.py`, `tests/test_foundation.py`, `tests/test_orchestrator.py`, `tests/test_path_config_hardening.py`, `tests/test_phase2.py`, `tests/test_phase3.py`, `tests/test_step_c_gap_closure.py`.
  - Untracked include preserved 5A modules/tests/artifacts and docs `25`–`34` in `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/`.
- **Health (baseline check):** prior 5A.6R2 verification recorded `aj --check` 23/23 ok, Hermes `NOT ATTACHED`, full suite 559 passed / 13 warnings / 0 failures.
- **Boundaries:** JARVIS/HELIX/Hermes untouched; Hermes `NOT ATTACHED`; `gateway.ensure` not implemented/enabled/executed/authorized. No destructive Git operations.

## 2. Documents and source inspected

- Read: 5A.6R docs `25`–`29`, 5A.6R2 docs `30`–`34` (including `34_PHASE_5A_6R2_VERIFICATION_REPORT.md`: 5A.6R2 INCOMPLETE, 45 scenarios not individually certified, crash windows A–J not fully closed/proven, auth-path regression incomplete, race safety unproven). 5A.6 foundation docs `20`–`24` present in repo and treated as baseline context.
- Source inspected/reconstructed: `aj/task.py` (TaskRecord/TaskStore lifecycle, transitions, persistence, hooks), `aj/orchestrator.py` (delegate/prepare/reconcile, hooks, guarded completion, resume/execute/retry/recover/cancel/dead-letter paths, delegated-permission guard), `aj/delegation.py` (contracts/stores, matching/narrowing, aggregation, anomaly detection), `aj/scheduler.py` (eligibility/admission/dispatch), `aj/execution_domain.py`, `aj/authorization.py` (principal/privileged auth boundary), `aj/permissions.py`/authorizer usage, `aj/recovery.py`, `aj/receipts.py`, `aj/journal.py`, `aj/lease.py`, `aj/idempotency.py`, `aj/operation_evidence.py`, existing delegation tests (`tests/test_phase5a6_delegation_foundation.py`, `tests/test_phase5a6r_delegation_closure.py`, `tests/test_phase5a6r2_parent_lifecycle.py`).

## 3. Provenance note — 45 scenarios and crash windows A–J

The 5A.6R3 instructions require retrieving the exact 45 scenarios and crash windows A–J from existing 5A.6R2 documentation. Docs `30`–`34` reference "45 enumerated 5A.6R2 scenarios" and crash windows A–J but do **not** restate the full enumerated list text verbatim. A repo-wide search did not locate the verbatim scenario/window text in stored 5A.6R2 docs. For certification traceability, this audit/matrix uses the **authoritative 5A.6R2 requirement set** as specified for 5A.6R2 (section 13 tests 1–45 and section 6 crash windows A–J) without invention, replacement, or reduction. Any mapping uncertainty is recorded as UNTESTED/PARTIAL with explicit rationale.

### Crash windows A–J (authoritative 5A.6R2 set)
- **A.** Child state persisted, parent reconciliation not started.
- **B.** Parent reconciliation intent recorded, parent state not updated.
- **C.** Parent state updated, aggregation evidence not fully persisted.
- **D.** Two child transitions trigger parent reconciliation concurrently.
- **E.** Parent cancellation occurs while a child completes.
- **F.** Child completion occurs while parent recovery runs.
- **G.** Two recovery processes inspect the same incomplete parent.
- **H.** Parent is marked complete while a child transition is concurrently being persisted.
- **I.** Delegation record and task records disagree.
- **J.** Parent has terminal state but child evidence contradicts it.

### 45 required scenarios (authoritative 5A.6R2 set)
1. Child transition automatically triggers parent reconciliation.  
2. Authorization rejection updates parent appropriately.  
3. Admission deferral does not allow false parent completion.  
4. Dispatch updates parent progress.  
5. Execution start updates parent progress.  
6. Child completion updates parent aggregation.  
7. Required child failure updates parent status.  
8. Optional child failure follows policy.  
9. UNKNOWN child prevents false completion.  
10. RECOVERY_REQUIRED child prevents false completion.  
11. Manual-review child prevents false completion.  
12. Parent cancellation stops new child dispatch.  
13. Repeated aggregation is idempotent.  
14. Concurrent aggregation is handled safely.  
15. Stale aggregation is detected.  
16. Parent terminal-state regression is rejected or explicitly recovered.  
17. Parent completion requires verified required-child outcomes.  
18. Partial completion is represented accurately.  
19. Historical aggregation evidence is preserved.  
20. Child transition persisted before parent update is recoverable.  
21. Interrupted aggregation intent is recoverable.  
22. Parent update with missing evidence is detectable.  
23. Concurrent recovery is safe or fails closed.  
24. Parent-child contradictory state is detected.  
25. Ambiguous execution is never blindly retried.  
26. Orphaned child detected.  
27. Missing child/delegation linkage detected.  
28. Missing assignment detected.  
29. Expired lease uncertainty detected.  
30. Stale parent aggregation detected.  
31. Incorrect completed parent detected.  
32. Read-only monitoring does not mutate state.  
33. Dry-run reconciliation does not mutate state.  
34. Explicit apply reconciliation records provenance.  
35. Reconciliation batch limits are enforced.  
36. Delegated permission guard still blocks escalation.  
37. Permission changes after assignment are revalidated.  
38. All supported execution paths enforce authorization.  
39. 5A.4 execution regressions pass.  
40. 5A.5 scheduler regressions pass.  
41. 5A.6 delegation foundation tests pass.  
42. 5A.6R closure tests pass.  
43. Full regression suite passes.  
44. AJ health check passes.  
45. Hermes remains NOT ATTACHED.

## 4. Actual lifecycle/call graph (reconstructed)

- **Task mutation boundary:** `TaskStore.transition()`/`cancel()` mutate+persist under store lock/file lock, then invoke `after_transition` callback outside store lock (5A.6R2). `save/apply/mutate` persist non-lifecycle fields; `mutate` forbids status/event changes.
- **Delegation creation:** `Aj.delegate()` → validate/idempotency/parent checks → create delegation intent → per-child match+narrow+create task+assignment+`_prepare_delegated_child_for_scheduling()` (RECEIVED→UNDERSTANDING→PLANNED→authorize/WAITING/ABORT/FAIL) → finalize delegation → explicit `_reconcile_delegation_parent()` → status.
- **Child transition hook:** `after_transition` → `Aj._on_task_transition()` filters delegation-related child transitions, runs guarded `_reconcile_delegation_parent(apply_parent_policy=True)` best-effort, marks `reconciliation_pending` on failure.
- **Completion enforcement:** wrapped `TaskStore.transition` calls `Aj._before_task_transition()` to block delegation-parent `COMPLETED` when aggregation unsafe/unverifiable.
- **Reconciliation:** `_reconcile_delegation_parent()` (bounded, snapshot-hash, idempotent no-op, dry-run/apply, evidence/history/provenance, optional child preparation in apply). `reconcile_delegation_parent()` is explicit public API.
- **Dispatch/execution:** 5A.5 `Scheduler` selects eligible AUTHORIZED tasks → `Aj.resume(..., leased=True)` → `_resume_locked()` (capability/policy/auth/stale checks, delegated-permission guard) → `_execute()` (guard defense-in-depth, execution record/attempt/dispatch via existing paths) → terminalization/receipts/journal/evidence.
- **Recovery:** `aj.recovery.RecoveryManager`/`Aj.recover/_recover_locked/_assess_recovery` provide conservative evidence-based recovery (separate from delegation reconciliation); orchestration/operator reconciliation paths exist but delegation-specific crash recovery is partial.
- **Authorization:** `Authorizer` (permissions) + capability/policy/stale-context checks in orchestrator; delegated envelope guard `_delegated_permission_guard()` checks recorded delegation snapshots (logical-internal scope, parent/requested envelope subset). `aj/authorization.py` provides privileged-operation principal/boundary metadata (not human authn; `local_trust` non-authenticated).

## 5. Unresolved 5A.6R2 criteria mapped to gaps (audit matrix)

| Criterion / area | Current behavior (source) | Gap / unsafe behavior | Required correction (if any) | Test/scenario needed | Evidence required |
|---|---|---|---|---|---|
| 4. All relevant child transitions trigger auto reconcile or durable pending | Hook on TaskStore transition/cancel (`aj/task.py`, `Aj._on_task_transition` in `aj/orchestrator.py`) for delegation-related children/parents | Not every relevant transition category/policy outcome demonstrated (auth rejection, admission deferral, dispatch, exec start, cancel requested/unresolved, recovery/manual-review/admin paths); pending marker best-effort only | Prove coverage per supported path; add durable intent where feasible or fail closed/detect | 1–6,12,20–21 + path-specific cases | Deterministic tests asserting reconciliation evidence/pending/aggregation update per transition path |
| 5,6,17. No false parent completion / verified required outcomes | `_before_task_transition` blocks COMPLETED when agg unsafe (`aj/orchestrator.py`); agg marks unknown/recovery/manual-review blocking (`aj/delegation.py`) | Guard relies on current computed agg; not all paths to parent completion/policy enforcement proven; no automatic parent task-state transition to completed when safe (by design?) but also no exhaustive prevention proof across all entry points | Ensure all supported parent-completion paths go through guarded transition; prove invariants | 3,6,9,10,11,17,31 | Tests attempting completion from all relevant states/paths with required unresolved/unknown/recovery/manual-review children |
| 7,18. Required/optional/partial semantics deterministic | `aggregate_parent_progress` supports all_required/any_sufficient/subset_required; optional/partial not explicitly represented as parent task states | Optional-child failure and partial completion policies not fully explicit/tested; no deterministic parent status mapping beyond can_complete/manual_review flags | Document conservative deterministic policy; represent partial honestly in evidence/status where supported; fail closed on ambiguity | 7,8,18 | Tests for optional failure, any_sufficient/subset, partial outcomes |
| 8. Parent cancellation policy | `cancel_task`/store cancel exist; delegation prep/reconcile conservative | No full orchestration: stop new child creation/dispatch, request child cancellation via supported mechanisms, verify child cancellation outcomes before reconciling parent | Implement bounded policy enforcement where feasible (prevent new prep/dispatch for cancelled parents, propagate/request cancel safely) or document/fail closed | 12 and cancellation-race scenarios | Tests showing no new dispatch, child cancel requested/verified, parent not falsely cancelled-complete |
| 9. Child failure isolation | Per-task outcomes and aggregation count failures | Isolation under concurrent/multi-child flows not exhaustively proven | Verify no cross-child corruption in reconciliation/assignment handling | 7,8 | Multi-child deterministic tests |
| 10,11,13,19. Idempotent/stale/historical aggregation; interrupted recovery | Snapshot hash, no-op detection, bounded history in delegation evidence (`_reconcile_delegation_parent`) | Stale detection observable but hook may clear quickly; no explicit stale snapshot overwrite protection against older concurrent writer beyond single-process guards; interrupted intent/pending partially modeled | Strengthen idempotency with monotonic evidence/version checks where possible; explicit interrupted-intent recovery detection | 13–16,19–23,30 | Deterministic concurrency/barrier tests and simulated interruption/restart tests |
| 12,14. Concurrency and race safety; crash windows A–J | Thread-local re-entrancy + RLock; best-effort pending marker | No proven multi-process/distributed safety; crash windows A–J not individually certified; cross-store non-atomic sequences (task vs delegation evidence) | Add controlled deterministic concurrency tests; simulate crash windows via sequencing/mocking/persistence boundaries; fail closed/document | A–J, 14,20–24 | Per-window tests with explicit durable-state assertions and restart/recovery checks |
| 14 (anomalies), 26–31. Detection/remediation completeness | `detect_delegation_anomalies` extended (stale/incorrect complete/disagreement/provenance/active-no-exec) | Missing assignment detection, expired lease uncertainty, pending-reconciliation-beyond-policy, stuck cancellation, execution-assignment linkage inconsistencies not fully covered; explicit apply remediation limited (does not safely repair all contradictions) | Extend read-only detectors and bounded dry-run/apply remediation with provenance/fail-closed behavior | 26–31 + anomaly matrix | Tests asserting finding codes/severity/evidence refs and non-repair in monitor/dry-run |
| 18,36–38. Delegated authorization across all execution/recovery paths | `_delegated_permission_guard` in `_resume_locked` and `_execute`; guard checks recorded delegation envelope (logical-internal scope, subset snapshots) | Revalidation against current trusted state limited (compares recorded snapshots, not dynamic revocation/parent-auth changes in all cases); not proven for retry, recovery-triggered execution, reconciliation-triggered execution, assignment acceptance, all alternative/internal paths; tampered assignment/delegation records not fully covered | Trace and harden every entry point; revalidate current parent/task/delegation/assignment/policy state at boundary; block unsupported paths; add adversarial tests | 36–38 | Tests per path with revocation/reduction/malformed/stale/missing/tampered contexts |
| 32–35. Monitoring/reconciliation API guarantees | `delegation_monitor`/status observational; dry-run/apply implemented with batch clamp and provenance | Need explicit proof that monitor/status/dry-run never mutate even on edge states; apply records before/after-like provenance sufficiently | Assert no state mutation in read paths and complete provenance fields | 32–35 | Targeted tests comparing persisted snapshots before/after |
| 39–45. Regressions/boundaries | Prior 5A.6R2: 54 targeted, 559 full, 23/23 check, Hermes NOT ATTACHED | Must re-run and preserve after any changes | Run focused + existing + full + check | 39–45 | Exact command outputs and evidence |

## 6. Execution/recovery/authorization entry points requiring proof (trace targets)

- `Aj.handle`, `Aj._execute`, `Aj._execute_calling` (and internal execution branches), `Aj.resume/_resume_locked` (scheduler and direct), `Aj.retry/_retry_locked`, `Aj.recover/_recover_locked`, `Aj.cancel_task`, `Aj.dead_letter`, `Aj._handle_stale_authorization`, operator/dead-letter reconciliation paths, `Aj._prepare_delegated_child_for_scheduling`, `Scheduler.run_once/_run_one/_dispatch`, any delegation reconciliation path that may transition/prepare children. For each: confirm delegated guard applicability and current-state authorization revalidation or explicit blocking.

## 7. Implementation approach (bounded, corrective)

1. Complete scenario matrix (doc 36) from this audit with explicit PASS/PARTIAL/UNTESTED per current evidence.
2. Implement minimal safe fixes for certifiable gaps: strengthen guard/revalidation and path coverage, improve detection/remediation metadata, enforce conservative parent-cancel/dispatch constraints where feasible, add deterministic scenario/crash/race/concurrency tests.
3. For gaps not safely closable under current storage/locking architecture (cross-store atomicity, multi-process races, full crash-window durability), keep fail-closed behavior and document as UNTESTED/PARTIAL/limitation with evidence.
4. Run focused + 5A.4/5A.5/5A.6/5A.6R/5A.6R2 + full suite + `aj --check`; produce docs 37–39 and final consolidated verdict (INCOMPLETE if any required criterion/scenario remains PARTIAL/FAIL/UNTESTED).

*Audit is evidence-backed and conservative. No implementation changes performed in this step.*