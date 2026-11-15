# S0 CLOSURE REPORT (AJ, round 3 — audit/design scope evidence)

## PHASE
**S0 — Closure & characterization proof (Doc 54/56/57/58 aligned evidence pass, round 3).**
Scope: AJ repo only on `wip/s0-snapshot` (from `468fdce...`). New/updated artifacts under `tests/s0_proof/`, `ENGINEERING_AUDIT/S0_CLOSURE/`, and review context `_context_pack/REVIEW_PACK_3.md`. **Exactly one authorized source edit applied (D-001):** `aj/orchestrator.py` import adds `aggregate_parent_progress` (no other `aj/` changes, no `except Exception` handling changed). No existing tests modified/weakened/deleted. No Hermes/JARVIS/HELIX changes. No `main` changes, no destructive git ops. **S1 not started.**

## STATUS
**PARTIAL** (S0 `PARTIALLY COMPLETE`, audit/design-scope evidence produced but closure not proven).

Rationale: E1–E6 each have evidence files (see table), but characterization gaps remain (**11 xfailed**: A1,A1b,A2a–c,A3–A8), Doc 58 D1–D5 not implemented, Doc 57 §14 decisions unresolved, callable/wrapper/CLI/UI/integration/inbox inventory not exhaustive, crash/recovery/concurrency proofs largely need seams/NOT VERIFIABLE/UNSUPPORTED (original A–H unrecovered), and SQLite/WAL remains **OPEN** with intermittent NTFS `disk I/O error` sensitivity. **No claim of S0 completion/certification is made.**

## E1–E6 TABLE
| Item | Status | Evidence file(s) | Notes |
|---|---|---|---|
| E1 Characterization (A1–A8 xfail gaps, B1–B5 controls after D-001) | PASS (evidence produced) | `tests/s0_proof/test_s0_characterization.py`, `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_BEFORE_FIX.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_AFTER_FIX.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/_step4_new_tests.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/_runxfail_*`, `ENGINEERING_AUDIT/S0_CLOSURE/_full_suite_round3_final.txt` | Final characterization in suite: **11 xfailed** (A1,A1b,A2a,A2b,A2c,A3,A4,A5,A6,A7,A8) expose gaps; **B1–B5 pass** as controls (B3/B5 validate real aggregation guard post D-001). No unexpected XPASS. |
| E2 Callable inventory (AST + grep, dispositions) | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph.py`, `ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph_results.json`, `ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph_results.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/CALLABLE_INVENTORY_S0.md` (v2) | 146 AST call-site entries in `aj/*.py` with dispositions (GUARDED/S2-FIX/BLOCK-PER-D4/UNSUPPORTED/NOT VERIFIABLE). **Not exhaustive**; AST cannot see dynamic dispatch/runtime indirection/callbacks/non-Python/CLI subprocess/UI coupling/tests beyond grep. |
| E3 Proof specs INV-01..10 / T-01..12 | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/PROOF_SPECS.md` | Setup/invocation/authoritative persisted record/expected/forbidden/stage/covering test specified; untestable-now/NOT VERIFIABLE items marked explicitly. No implementation in S0. |
| E4 Policy decisions & D-001/STEP 3 analysis artifacts | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/58_POLICY_DECISIONS.md`, `ENGINEERING_AUDIT/S0_CLOSURE/STEP3_CHANGE_TABLE.md`, `ENGINEERING_AUDIT/S0_CLOSURE/D001_CONFLICT_MESSAGES_AFTER_FIX.json` | Doc 58 D1–D5 captured + D3 refinement (legal ABANDONED sources FAILED/DEAD_LETTER/RECOVERY_REQUIRED/ESCALATED; refuse others; abandon must validate source and not rely on force once legal). D-001 defect fixed and evidenced; wrong-reason Conflict audit documented. |
| E5 Crash feasibility (derived boundaries, A–H unrecovered) | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/CRASH_FEASIBILITY.md` | Original A–H list **UNRECOVERED** (not invented). Boundaries B1–B8 derived from real persistence/write ordering; classified testable-now/needs S4 seam/NOT VERIFIABLE/UNSUPPORTED. No seams invented. |
| E6 SQLite/WAL disposition (facts/hypotheses, targeted runs) | PASS (evidence produced) | `ENGINEERING_AUDIT/S0_CLOSURE/SQLITE_DISPOSITION.md`, `ENGINEERING_AUDIT/S0_CLOSURE/sqlite_wal_matrix_results.json`, `ENGINEERING_AUDIT/S0_CLOSURE/sqlite_wal_matrix_summary.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/E6_ntfs_default_tmpdir.json`, `ENGINEERING_AUDIT/S0_CLOSURE/E6_ntfs_tmpdir_tmp.json` | Facts: `memory.py` connect timeout 30 then `PRAGMA journal_mode=WAL` then `busy_timeout=30000` (no read-first/retry). Default env TMPDIR `/home/abubakargcx/easy-diffusion/tmp`. E6 concurrent writer 10x default: 8 pass/2 fail; 10x `TMPDIR=/tmp`: 10 pass/0 fail (pytest tmp_path FS equivalence not proven). Disposition **OPEN**. |


## REQUIREMENTS
- Read-only closure engineering with only authorized D-001 source edit; preserve `main` (`468fdcebece5b25f02e53add4928d3650ef175f4`), pre-existing work/data; AJ-only; no S1.
- Step 1/2: evidence before/after D-001 (B3 fail with NameError -> PASS). Step 3: wrong-reason audit (suite before/after, change table, Conflict messages in target delegation tests) without editing existing tests. Step 4: edit only `tests/s0_proof/test_s0_characterization.py` (B3 strict reconcile, add B5 pass control, add A1b/A8 xfail). Step 5: append D3 refinement and D-001 evidence to `58_POLICY_DECISIONS.md`. Step 6 (E2,E3,E5,E6): AST callgraph + inventory v2 dispositions, PROOF_SPECS INV-01..10/T-01..12, CRASH_FEASIBILITY from real persistence order (A–H unrecovered, no invented seams), SQLITE_DISPOSITION facts/hypotheses and planned S5 experiments with E6 runs. Step 7/8: report, full suite, separate commits (D-001 vs S0 docs) and plain push of `wip/s0-snapshot`.

## DESIGN
- **D-001:** minimal import-only fix to make delegated-parent completion guard evaluate real aggregation (not NameError) while leaving `except Exception` handling unchanged; wrong-reason masking audited and reported.
- **Characterization:** target invariants asserted with `xfail(strict=True)` for gaps (A1,A1b,A2a-c,A3-A8); positive controls B1-B5 must pass to validate harness/real guard behavior post-fix.
- **Inventory/E3/E5/E6:** AST+grep evidence-based, conservative dispositions; proof specs explicit about untestable-now; crash boundaries derived from observed write order only (no invented A–H, no invented seams); sqlite investigation records facts vs labelled hypotheses (OPEN).

## IMPLEMENTATION

### D-001 (authorized, only `aj/` edit)
- **File:** `aj/orchestrator.py` (line ~51 import)
- **Before:** `from .delegation import AssignmentStore, DelegationStore, LogicalAgentStore, detect_delegation_anomalies`
- **After:** `from .delegation import AssignmentStore, DelegationStore, LogicalAgentStore, aggregate_parent_progress, detect_delegation_anomalies`
- **Evidence:** `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_BEFORE_FIX.txt` (NameError -> `Conflict(... unverifiable (NameError))`), `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_AFTER_FIX.txt` (PASS), `ENGINEERING_AUDIT/S0_CLOSURE/D001_CONFLICT_MESSAGES_AFTER_FIX.json`, `ENGINEERING_AUDIT/S0_CLOSURE/STEP3_CHANGE_TABLE.md`.

### `tests/s0_proof/test_s0_characterization.py` (only edited/new test file)
- B3: removed try/except around `aj.reconcile_delegation_parent` (must fail if raises).
- Added **B5** (PASS): required unresolved child blocks parent completion with `Conflict` containing `detail.aggregation` and message without `NameError`/`unverifiable`.
- Added **A1b** (xfail strict, INV no resurrection / Doc58 D3): abandon DEAD_LETTER, reload, requeue succeeds (resurrection gap).
- Added **A8** (xfail strict, Doc58 D3): abandon on COMPLETED must be refused and task must stay COMPLETED.

### S0 artifacts created/updated (evidence)
- `ENGINEERING_AUDIT/S0_CLOSURE/58_POLICY_DECISIONS.md` (+D3 refinement, D-001 fixed section)
- `ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph.py`, `ast_callgraph_results.json`, `ast_callgraph_results.txt`
- `ENGINEERING_AUDIT/S0_CLOSURE/CALLABLE_INVENTORY_S0.md` (v2, dispositions)
- `ENGINEERING_AUDIT/S0_CLOSURE/PROOF_SPECS.md`
- `ENGINEERING_AUDIT/S0_CLOSURE/CRASH_FEASIBILITY.md`
- `ENGINEERING_AUDIT/S0_CLOSURE/SQLITE_DISPOSITION.md`
- `ENGINEERING_AUDIT/S0_CLOSURE/STEP3_CHANGE_TABLE.md`
- `ENGINEERING_AUDIT/S0_CLOSURE/E6_ntfs_default_tmpdir.json`, `E6_ntfs_tmpdir_tmp.json`
- `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_BEFORE_FIX.txt`, `D001_B3_AFTER_FIX.txt`, `D001_CONFLICT_MESSAGES_AFTER_FIX.json`
- `ENGINEERING_AUDIT/S0_CLOSURE/_step4_new_tests.txt`, `_full_suite_round3_final.txt`, prior sqlite/matrix/runxfail/log artifacts retained
- `_context_pack/REVIEW_PACK_3.md` (to be written as final handoff pack)

## BEHAVIOR

### STEP 3 — wrong-reason audit / change table (D-001)
See `ENGINEERING_AUDIT/S0_CLOSURE/STEP3_CHANGE_TABLE.md` (verbatim required in REVIEW_PACK_3). Summary:
- **Deterministic change:** `tests/s0_proof/test_s0_characterization.py::test_b3_parent_with_all_required_children_completed_completes` FAIL (NameError/unverifiable) -> PASS (D-001).
- **Non-deterministic/env variance:** `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` failed before-fix run on NTFS tmp (`disk I/O error`) but passed in compared after-fix existing-suite run; intermittent OPEN issue, **not attributed to D-001**.
- **No other existing-test result changes observed** in compared runs (`--ignore=tests/s0_proof` before 576 pass/1 fail vs after 577 pass).
- **Wrong-reason (before fix):** guarded delegated-parent COMPLETED transitions that asserted `Conflict` could pass because guard hit `NameError` and wrapped as `Conflict(... unverifiable (NameError))` instead of real aggregation. Notably `test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_when_required_child_unresolved` and `::test_parent_completion_blocked_direct_guard`, and `test_phase5a6r3_scenario_certification.py::test_s16_s31_incorrect_completed_parent_detected` (and equivalent guarded paths). **After fix:** real aggregation-based Conflict with `detail.aggregation` (e.g. unresolved/waiting/failed required child, `can_complete=false`), no `NameError`/`unverifiable`. `test_phase5a6r_delegation_closure.py::test_same_idempotency_key_different_spec_rejected` unchanged/unrelated.
- Target-file `raises Conflict` sites grepped: r2:130, r2:152, r3:258, delegation_closure:126 (all PASS after fix); conflict messages captured in `D001_CONFLICT_MESSAGES_AFTER_FIX.json`.

### A1–A8 / B1–B5 characterization (final)
- **B1–B5: PASS.** B3 passes only after D-001; B5 confirms required-unresolved child blocked with aggregation Conflict (not NameError/unverifiable).
- **A1,A1b,A2a,A2b,A2c,A3,A4,A5,A6,A7,A8: XFAIL (strict).** Gaps remain (ABANDONED loadability/resurrection, delegated child ops/dispatch/cancel propagation/scheduling under cancelled parent, force-complete with unresolved required child, required classification missing/malformed, unsupported remote transport claim accepted, abandon COMPLETED not refused).
- Step 4 spot-check: `test_b5` PASS, `test_a1b`/`test_a8` XFAIL (`_step4_new_tests.txt`).

### Full suite (final, round 3)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`  
Result: **581 passed, 1 failed, 11 xfailed, 13 warnings** (exit 1). Evidence: `ENGINEERING_AUDIT/S0_CLOSURE/_full_suite_round3_final.txt`.
- Failure: `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` — `sqlite3.OperationalError: disk I/O error` at `aj/memory.py:116` (PRAGMA journal_mode=WAL) on NTFS workspace tmp path (`/run/media/.../easy-diffusion/tmp/pytest-of-...`). **Intermittent/environment-sensitive (OPEN), not attributed to D-001** (see E6/SQLITE_DISPOSITION and STEP 3 variance).
- Warnings: 13 total (PyGI deprecation, multiprocessing fork deprecation in test_phase3).

## ADVERSARIAL / E5 & E6 NOTES
- **E5 (CRASH_FEASIBILITY):** original A–H unrecovered; boundaries B1–B8 derived from real persistence/write order (task jsonl persist+hooks, dispatch intent/lease/start/result, multi-store task/execution/receipt/journal, delegation multi-record, reconciliation, append-failure handling, sqlite init, lease vs state). Mostly **needs S4 seams** or **NOT VERIFIABLE/UNSUPPORTED** (OS/power/fs/corruption, cross-store atomicity, exactly-once external, multi-process/host). No seams invented.
- **E6 (SQLITE_DISPOSITION):** `memory.py` does `connect(timeout=30.0)` then `PRAGMA journal_mode=WAL` then `PRAGMA busy_timeout=30000` then schema+commit (no read-first/retry). Matrix shows NTFS concurrent sensitivity (`disk I/O error` at 116 in samples) and some tmpfs lock contention; single-process stable; real AJ default data dir ext4 `~/.local/share/aj`. E6 10x runs: default env 8/10 pass, `TMPDIR=/tmp` 10/10 pass but **pytest tmp_path/basetemp FS equivalence not proven**. Hypotheses labelled, not proven. **OPEN.**

## INDEPENDENT VERIFICATION
- None. Agent-executed evidence/characterization only; **not independent certification**.

## REGRESSION
- No existing tests edited/weakened/deleted. D-001 produced no observed deterministic regression; one intermittent NTFS sqlite failure observed in final full run (env-sensitive). Existing delegation completion-blocking tests now evaluate real aggregation reasons (corrected from prior wrong-reason masking).

## EVIDENCE
- `tests/s0_proof/test_s0_characterization.py`
- `ENGINEERING_AUDIT/S0_CLOSURE/S0_CLOSURE_REPORT.md` (this report)
- `ENGINEERING_AUDIT/S0_CLOSURE/58_POLICY_DECISIONS.md`
- `ENGINEERING_AUDIT/S0_CLOSURE/CALLABLE_INVENTORY_S0.md`, `ast_callgraph.py`, `ast_callgraph_results.json`, `ast_callgraph_results.txt`
- `ENGINEERING_AUDIT/S0_CLOSURE/PROOF_SPECS.md`
- `ENGINEERING_AUDIT/S0_CLOSURE/CRASH_FEASIBILITY.md`
- `ENGINEERING_AUDIT/S0_CLOSURE/SQLITE_DISPOSITION.md`, `sqlite_wal_matrix_results.json`, `sqlite_wal_matrix_summary.txt`, `sqlite_wal_experiment.py`, `E6_ntfs_default_tmpdir.json`, `E6_ntfs_tmpdir_tmp.json`
- `ENGINEERING_AUDIT/S0_CLOSURE/STEP3_CHANGE_TABLE.md`, `D001_B3_BEFORE_FIX.txt`, `D001_B3_AFTER_FIX.txt`, `D001_CONFLICT_MESSAGES_AFTER_FIX.json`
- `ENGINEERING_AUDIT/S0_CLOSURE/_step4_new_tests.txt`, `_full_suite_round3_final.txt`
- `_context_pack/REVIEW_PACK_3.md`

## CRITICAL OPEN ITEMS
1. **S0 not closed/proven:** 11 characterization gaps xfail (A1,A1b,A2a-c,A3-A8). Doc 58 D1–D5 (required classification/validation, outcome mapping/force-guard semantics, ABANDONED FSM/load/import/legal-source enforcement, delegated admin/scheduler/cancel propagation/assignment handling, unsupported-claim rejection across surfaces) **not implemented**.
2. **D2/force-complete semantics unresolved:** A5 xfail — completion guard bypassed when `force=True`; `force=True` still used for requeue/abandon paths in code (policy/implementation alignment pending).
3. **ABANDONED model/load inconsistency:** persisted but not accepted by transitions/load in all cases; resurrection risk after reload (A1/A1b) and completed-task abandon not refused (A8).
4. **Delegated safety gaps:** child admin ops not blocked under cancelled parent without operator reconcile (A2a-c), scheduler dispatch gate insufficient (A3), parent cancel propagation/active-child handling unsafe (A4).
5. **T-11 boundary gap:** remote agent transport/unsupported claims not rejected/reported (A7 xfail).
6. **Inventory/exhaustiveness:** callable/wrapper/CLI/UI/integration/inbox/runtime indirect coupling and all `force`/bypass paths **not exhaustively proven** (AST limitations stated).
7. **Crash/recovery/concurrency:** original A–H unrecovered; most boundaries need S4 seams; cross-store atomicity/exactly-once/multi-process/distributed/OS-failure recovery **UNSUPPORTED/NOT VERIFIABLE**.
8. **SQLite/WAL OPEN (T-12):** intermittent NTFS `disk I/O error` and env-sensitive behavior; no fix/disposition.
9. **Doc 57 §14 decisions still open.** No independent verification/certification.

## FINAL VERDICT
**S0 STATUS: PARTIAL.** E1–E6 each have evidence files and D-001 corrected a real guard-evaluation defect (with wrong-reason masking documented), but S0 closure/proof is **not complete**. Characterization gaps, unimplemented Doc 58 policy/guards, unresolved lifecycle/outcome decisions, non-exhaustive inventories, and open crash/sqlite boundaries prevent claiming S0 COMPLETE. **Do not start S1.**


## ROUND 4 (2026-11-15, evidence pass — facts only, reviewer decides)
**Branch:** `wip/s0-snapshot` (HEAD at start of round 4: `d566840...`). `main` verified: `468fdcebece5b25f02e53add4928d3650ef175f4`.  
**Edits in this round:** NO edits to `aj/`, NO edits to any existing test. New files under `ENGINEERING_AUDIT/S0_CLOSURE/` (+ `CALLABLE_INVENTORY_S0_v2.md` copy) and scratch copies under `/tmp`. Edits to `PROOF_SPECS.md`, `CALLABLE_INVENTORY_S0.md` (replaced with v3), and `S0_CLOSURE_REPORT.md` (this section). No "COMPLETE" written.

### STEP 1 — measured wrong-reason claim (scratch pre-D-001, no guessing)
- Method: `git archive eb2674b | tar -x -C /tmp/aj_prefix` (pre-D-001, real repo unchanged). Instrumented `aj/orchestrator.py::_before_task_transition` `except Exception` in scratch to append `PYTEST_CURRENT_TEST | exc_type` to `/tmp/nameerr_hits.log`. Ran 5 delegation test files one at a time in scratch with `--basetemp=/tmp/aj-pre/<subdir>` (PYTHONDONTWRITEBYTECODE=1): foundation (8 passed), r_closure (7 passed), r2 (11 passed), r3 (12 passed), r4 (6 passed). Logs: `/tmp/step1_foundation.txt`, `/tmp/step1_rclosure.txt`, `/tmp/step1_r2.txt`, `/tmp/step1_r3.txt`, `/tmp/step1_r4.txt`.
- **Measured hits:** 2 log lines, both `NameError`.
  1. `tests/test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_when_required_child_unresolved (call) | NameError` — **PASSED**. Assertion: `with pytest.raises(Conflict): aj.tasks.transition(parent.task_id, taskmod.COMPLETED, "should block")` (satisfied by NameError-wrapped unverifiable Conflict, wrong reason).
  2. `tests/test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_direct_guard (call) | NameError` — **PASSED**. Assertion: `with pytest.raises(Conflict): aj.tasks.transition(parent.task_id, taskmod.COMPLETED, "child unresolved")` (same wrong reason).
- **Measured conclusion:** **2 existing tests (in the 5 measured files) passed for the wrong reason** (NameError path). Other `pytest.raises(Conflict)`/"blocked" sites in those files (e.g. `test_phase5a6r_delegation_closure.py:126` idempotency Conflict, `:157` blocked assertion, `test_phase5a6r3_scenario_certification.py:258` in `test_s16_s31_incorrect_completed_parent_detected`, markers in foundation/r4) did **not** hit the instrumented NameError branch in this measurement; r3:258 was not counted as measured wrong-reason pass. Measurement scope limited to these files/runs.
- Evidence: `ENGINEERING_AUDIT/S0_CLOSURE/WRONG_REASON_MEASURED.md`.

### STEP 2 — callable inventory rebuilt (E2, v3)
- Fresh AST scan over `aj/**/*.py` + `integrations/**/*.py`: **47 files scanned, 146 entries, 0 errors** (`/tmp/ast_round4.json`). Compared to old `ast_callgraph_results.json` (146): **delta added 0, removed 0**. No matching entries under `integrations/**/*.py`.
- `getattr(...)`/target-name scan: no variable target-name dynamic invocation of inventory methods identified; only attribute reads/fixed-name hook (`after_transition`) observed (see v3). Absence of all dynamic dispatch **NOT VERIFIABLE** statically.
- Objects other than `Aj`/`TaskStore` exposing target-like methods identified/classified (CallRecord/CallStore, Assignment/Delegation stores, ExecutionRecord/Store, RecoveryManager, Scheduler).
- Domain filter: all transition call sites classified (Task FSM in-domain; CallRecord/ExecutionRecord sites OUT-OF-TASK-DOMAIN with proof; runtime self-checks DIAGNOSTIC-ONLY with proof of tempfile/temp stores, not real data dir).
- `CALLABLE_INVENTORY_S0.md` replaced with **v3** (grouped by callable, 11-field records for mandatory callables incl Aj.handle/resume/retry/recover/cancel_task/cancel/reconcile+action dispatcher, Aj.dead_letter/requeue/abandon/delegate, Aj.reconcile_delegation_parent/_reconcile_delegation_parent/_prepare_delegated_child_for_scheduling/_delegated_permission_guard/_before_task_transition/_on_task_transition, Scheduler.evaluate_eligibility/evaluate_admission/_dispatch_one/run_once, TaskStore.transition/cancel/mutate/save/import_record, and every task-mutating `_cmd_*` handler; dispositions with target stages; NOT VERIFIABLE entries include exact missing info/seam and what would make verifiable). v2 preserved as `CALLABLE_INVENTORY_S0_v2.md`.
- Scheduler dead-letter near `scheduler.py:720`: trigger predicate and delegated reachability **NOT VERIFIABLE** in this pass (branch-complete trace needed) — documented with required verifiability conditions.
- Honest limits listed (dynamic dispatch, cross-store atomicity/crash/freshness, wrapper coverage, orb/inbox/integration coupling, external boundaries).

### STEP 3 — regression-gate protocol (no test edits)
- Created `ENGINEERING_AUDIT/S0_CLOSURE/TEST_RUN_PROTOCOL.md`. Standard: `python3 -m pytest -q --basetemp=/tmp/aj-pytest-std` (environment/basetemp setting, not a test change; `TMPDIR` points to `/home/abubakargcx/easy-diffusion/tmp` on NTFS/easy-diffusion tmp context, NTFS basetemp previously showed intermittent sqlite sensitivity). Separate T-12 evidence: NTFS basetemp command.
- Standard runs (3, fresh `/tmp/aj-pytest-std` each run, PYTHONDONTWRITEBYTECODE=1): 
  - Run 1: `1 failed, 581 passed, 11 xfailed, 13 warnings in 68.62s` (FAILED `tests/test_crash_safety.py::test_multi_process_recovery_same_operation`).
  - Run 2: `581 passed, 11 xfailed, 16 warnings, 1 error in 68.47s` (ERROR at setup `tests/test_audit_reliability_security.py::test_reconcile_evidence_incomplete_is_reported_not_silent_success`, `FileExistsError` on `/tmp/aj-pytest-std` mkdir/cleanup race with rm_rf warnings).
  - Run 3: `1 failed, 581 passed, 11 xfailed, 13 warnings in 67.30s` (FAILED `tests/test_audit_reliability_security.py::test_clear_recovery_required_fails_closed_on_completion_receipt_conflict`).
  Results not identical across runs (recorded factually; no `aj/` edits in round 4).
- T-12 NTFS basetemp run (1): `582 passed, 11 xfailed, 13 warnings in 60.79s` (`--basetemp="/run/media/abubakargcx/My Drive/easy-diffusion/tmp/aj-pytest-ntfs"`).
- Evidence: `ENGINEERING_AUDIT/S0_CLOSURE/TEST_RUN_PROTOCOL.md`, `/tmp/std_run1.txt`, `/tmp/std_run2.txt`, `/tmp/std_run3.txt`, `/tmp/ntfs_run.txt`.

### STEP 4 — PROOF_SPECS stale statements refreshed
- Refreshed stale "pending approved mapping" / D2-dependent wording to reflect D2 outcome semantics approved in Doc 58 / `58_POLICY_DECISIONS.md` (implementation/proof still incomplete). No "COMPLETE" claim added.
- Evidence of changes: `ENGINEERING_AUDIT/S0_CLOSURE/PROOF_SPECS_ROUND4_DIFF.txt`, `ENGINEERING_AUDIT/S0_CLOSURE/PROOF_SPECS_ROUND4_CHANGED_SENTENCES.md`.
- **Every sentence/statement changed (listed):**
  1. **Round 4 refresh note inserted:** Added section "## Round 4 refresh note (2026-11-15 context)" stating D2 approved in Doc 58 / `58_POLICY_DECISIONS.md` while implementation/proof remains incomplete; no "COMPLETE" claim added.
  2. **INV-03 Untestable now?** BEFORE: `| Untestable now? | **Final approved outcome-state mapping (D2/Doc57 decision #2) dependent** for some cases; cannot claim full conformance until decided/implemented.` AFTER: `| Untestable now? | D2 outcome semantics are approved in Doc 58 / \`58_POLICY_DECISIONS.md\`, but implementation/proof not complete; cannot claim full conformance until implemented and proven across all paths.`
  3. **T-03 stage/untestable note:** BEFORE: `- **Stage:** S1/S3. **Covering test:** A4/A5/B5/A6. **Untestable now:** pending approved mapping for all cases.` AFTER: `- **Stage:** S1/S3. **Covering test:** A4/A5/B5/A6. **Untestable now:** D2 mapping approved (Doc 58), but not implemented/proven for all cases.`

**Status after round 4:** evidence artifacts added/refined (measured wrong-reason audit, inventory v3, test protocol, refreshed specs). S0 closure/certification **not** claimed; underlying Doc58 implementation gaps and unproven boundaries remain as previously reported.

