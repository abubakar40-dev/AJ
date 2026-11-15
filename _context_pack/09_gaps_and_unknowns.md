# 09 Gaps and Unknowns (read-only, blunt)

## Everything not verified and why

- **Exhaustive callable/wrapper/CLI/UI/integration/inbox inventory:** **NOT VERIFIED.** I performed targeted greps and source inspection for required/core callables (`dead_letter`, `requeue`, `abandon`, `delegate`, `_prepare_delegated_child_for_scheduling`, `_reconcile_delegation_parent`, scheduler `evaluate_eligibility/evaluate_admission/run_once/_dispatch_one`, `Aj.resume/retry/recover/cancel_task/cancel`, `Aj.reconcile`, CLI handlers in `aj/__main__.py`), but did not close the call graph across all wrappers, UI surfaces, background workers, external integrations, or every `aj/inbox*`/`aj/orb*` path. Some related terms appear in inbox domain (e.g. `aj/inbox_cli.py` "retry" failed capture, "requeue_stale" processing items) — **different domain** from task lifecycle mutation; full mapping not exhaustively proven.
- **"Every CLI command handler" exhaustive safety classification:** **PARTIALLY VERIFIED.** `_cmd_*` handlers and parser commands in `aj/__main__.py` were enumerated; mutation/safety implications for delegated contexts beyond inspected handlers (run/cancel/retry/recover/reconcile/tasks/task/audit/memory/summary/etc.) not fully traced end-to-end. `cmd_inbox` dispatches to inbox operations (separate subsystem) — not fully analyzed for interaction with task/delegation invariants.
- **Complete authorization revalidation/current-trust enforcement on all supported paths:** **NOT VERIFIED.** `_delegated_permission_guard` and `_prepare_delegated_child_for_scheduling` provide partial checks in covered paths; exhaustive coverage across handle variants, scheduler dispatch timing, recovery/inspect/admin/operator/alternative entry points, and dynamic permission source revalidation is unproven.
- **Scheduler delegation-awareness:** **NOT VERIFIED as sufficient.** `Scheduler.evaluate_eligibility/_dispatch_one/run_once` show no explicit delegation-parent/delegation-record authority/cancellation checks in inspected code; downstream guarded resume/execute exists but race/pre-dispatch safety for delegated contexts is unproven.
- **`ABANDONED` model consistency:** **CONTRADICTION/UNRESOLVED.** `"ABANDONED"` is used (`Aj.abandon`, operator reconcile flows, consistency logic, tests) but absent from `aj/task.py` `TRANSITIONS`/`TERMINAL`; implications for reload/import/validation/persistence/legacy behavior not fully dispositioned.
- **Explicit required/optional child classification and Doc 54 §6/T-03/T-04 policy enforcement:** **NOT IMPLEMENTED/NOT VERIFIED.** No explicit per-child required/optional field in `DelegationRequest.child_specs`; no proof of "no silent default to optional" / fail-closed on malformed classification as required.
- **Cancellation orchestration completeness (INV-04):** **NOT VERIFIED.** No proof of preventing all prohibited child creation/prep/dispatch, verifying child cancellation, handling cancel-vs-completion/dispatch/recovery/prep races, late outcomes, or resurrection prevention across all paths.
- **Reconciliation stale-writer/contradiction/race safety across stores (INV-05/07):** **NOT VERIFIED.** Snapshot-hash idempotency and locks/guards exist; general monotonic/CAS/versioned stale-writer protection and cross-store interruption safety not demonstrated.
- **Crash/recovery boundaries A–H and declared restart/persistence boundaries (INV-06, T-07):** **NOT VERIFIED.** No restart fault-injection proofs produced in this pass; feasibility/mechanisms largely unproven.
- **Concurrency mutating race coverage (INV-07, T-08):** **NOT VERIFIED** beyond limited evidence (e.g. in-process concurrent reconciliation test exists in 5A.6R4 suite per prior reports/source context; not independently re-executed in isolation here except full suite context). Multi-process/distributed unsupported.
- **Anomaly detection completeness and certified remediation (INV-08):** **PARTIALLY VERIFIED/NOT VERIFIED.** Detectors exist and some cases tested; full class coverage and safe remediation unproven.
- **Evidence/auditability completeness across all supported decisions/failures (INV-09, T-10):** **NOT VERIFIED.**
- **Honest-boundary enforcement as a tested invariant (INV-10, T-11):** **NOT VERIFIED** (no dedicated comprehensive tests identified).
- **SQLite/WAL root cause and disposition (T-12, OPEN):** **NOT VERIFIED.** Controlled runs show environment/storage-sensitive/intermittent behavior (`disk I/O error` in forked `MemoryStore.__init__ -> executescript` on some NTFS/default temp contexts; `/tmp` stable in batch). Full-suite passed in this session (577/0/13) but prior 576/1/13 and intermittency remain unresolved; no product-defect attribution, no `ntfsfix` repair (refused RW-mounted, skipped).
- **PRAGMA/WAL runtime state during failing concurrent test:** **NOT VERIFIED** (only isolated probe shown).
- **Legacy/existing uncommitted-untracked behavior interactions:** **NOT VERIFIED** beyond preserving files; 17 modified tracked files and 40 untracked items (plus newly created `_context_pack/`) not analyzed for semantic impact.

## Claims in handoff/checkpoint that source/tests contradict or cannot support as stated

- **"576 passed, 1 failed, 13 warnings" as current full-suite state:** **CONTRADICTED BY THIS SESSION’S RUN** (observed **577 passed, 13 warnings in 61.68s**), but **cannot be dismissed** because SQLite/WAL failure is intermittent/environment-sensitive and historically evidenced. Treat as **time/environment-dependent evidence**, not a settled contradiction of underlying issue.
- **Implicit assumption of complete task-mutation inventory:** Handoff identified key callables; this pass cannot certify exhaustiveness across all wrappers/surfaces (including inbox CLI "requeue/retry" naming overlap with task APIs but different domain) — **UNVERIFIED**.
- **Any claim that delegated authz/cancel/reconciliation/lifecycle is fully certified across all paths:** **UNSUPPORTED by source/tests evidence** (partial coverage only, known gaps in Doc 56/57 and observed in code).
- **`ABANDONED` as cleanly modeled terminal state:** **CONTRADICTED** by FSM/validation definitions in `aj/task.py` vs runtime usage/tests.
- **Safe-default closure for S0:** Doc 57 and this pass support **S0 PARTIALLY COMPLETE**, not closed.

## Working-tree note (post-baseline artifact)

- `_context_pack/` (including `_tmp_*` helper outputs and 01–09) was created during this read-only analysis and therefore appears as new untracked content relative to the baseline snapshot; no pre-existing files were modified. Re-running `git status --short` now will differ from the captured baseline counts by this directory.

## Bottom line

- Core source facts, baseline/test evidence, and planning docs are partially grounded and preserved in this pack.
- **Not sufficient to claim S0 closed, implementation-ready, or any Doc 54 invariant/T-case fully verified.** Gate B pass (with limitations) and S0 partial completion remain the honest status; unresolved decisions, untraced paths, model/policy gaps, crash/concurrency feasibility limits, and OPEN SQLite/WAL prevent stronger claims.
