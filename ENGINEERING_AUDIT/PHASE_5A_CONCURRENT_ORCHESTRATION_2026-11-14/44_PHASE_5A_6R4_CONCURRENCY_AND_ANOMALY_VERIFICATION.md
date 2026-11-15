# 44 — Phase 5A.6R4 Concurrency and Anomaly Verification

**Date:** 2026-11-14  
**Scope:** Bounded deterministic verification and extensions for Priority D (mutating concurrency/stale-writer) and Priority E (anomaly detection/remediation surfaces). Read-only monitoring preserved.

## 1. Anomaly detection extensions (Priority E) — `aj/delegation.py`, `aj/orchestrator.py`

`detect_delegation_anomalies(...)` extended (best-effort, observational, read-only) with:
- `missing_assignments`: delegated child linked in delegation record with no corresponding assignment record.
- `stuck_cancellations`: child in `CANCEL_REQUESTED` under delegation (conservative).
- `pending_reconciliation_beyond_policy`: delegation `reconciliation_pending` older than conservative threshold (300s) flagged for explicit reconcile/manual review.
- `ambiguous_executions`: execution records in `UNKNOWN`/`RECOVERY_REQUIRED`/`DISPATCH_UNCERTAIN` linked to delegated child.
- `inconsistent_terminal_states`: terminal task states inconsistent with active dispatch/running execution states (and specific contradictory terminal flags where detected).
- `expired_lease_uncertainties`: expired/stale lease observations on non-safely-terminal delegated children (best-effort via leases/executions inputs).
- Existing findings preserved: orphaned children, missing parents, incomplete delegations, stuck/recovery-required assignments, active assignment without execution, stale aggregation, incorrect completed parents, delegation-task disagreements, missing delegation provenance.

`delegation_monitor()` now passes `leases` and `executions` stores (when available) into anomaly detection. Monitoring remains **read-only/non-mutating**.

## 2. Bounded deterministic tests (`tests/test_phase5a6r4_gap_closure.py`)
- `test_missing_assignment_detected`: missing assignment surfaced.
- `test_stuck_cancellation_and_pending_reconciliation_detected`: stuck cancellation and aged pending-reconciliation surfaced.
- `test_mutating_concurrent_reconciliation_deterministic`: concurrent mutating `reconcile_delegation_parent(..., apply=True)` calls (barrier-coordinated, in-process) complete without uncaught errors/corruption; delegation evidence remains readable/consistent with stable aggregation snapshot hash for same state.

## 3. Mutating concurrency and stale-writer (Priority D) — status
- **Evidence added:** deterministic in-process concurrent mutating reconciliation calls behaved consistently in covered case; existing idempotent snapshot/hash and guarded reconciliation logic preserved.
- **Not proven/closed:** true race safety for all cases (concurrent child transitions, recovery racing scheduler dispatch, child completion racing parent cancellation, stale aggregation/evidence overwriting newer state under all interleavings, duplicate apply in all stores/paths, concurrent assignment/execution mutations, multi-process/distributed locking). Sequential/barrier tests do **not** prove race safety. Unsupported concurrency claims are not made; behavior must fail closed where coordination/safety cannot be guaranteed.

## 4. Crash windows A–H (Priority C) — status
- I,J previously evidenced as detection-covered in 5A.6R3; 5A.6R4 did not add exhaustive restart/process-crash proofs for A–H.
- A–H remain **PARTIAL/UNTESTED** relative to full recoverability/certification due to cross-store non-atomic persistence boundaries and unresolved NTFS/SQLite-WAL durability. No destructive experiments on real project data; no durability guarantees claimed.

## 5. Remediation posture
- Existing explicit, bounded, dry-run/apply-gated, evidence-backed, fail-closed reconciliation/remediation paths preserved (`reconcile_delegation_parent` dry-run/apply, non-fabricating). New anomaly findings are surfaced for explicit operator/remediation action; monitoring does not silently mutate records.
- Not all anomaly classes have fully automated safe apply remediation certified; unverifiable/ambiguous states must require manual review.
