# 43 — Phase 5A.6R4 Authorization, Cancellation, and Recovery Fixes

**Date:** 2026-11-14  
**Scope:** Targeted corrective closure on preserved 5A.4–5A.6R3 foundations. No redesign, no duplicate systems, no 5A.7.

## 1. Authorization and permission revocation (Priority A)

### Fixes implemented (`aj/orchestrator.py`)
- **`_delegated_permission_guard` strengthened (execution boundary):** now fail-closed revalidates delegated child execution against current local state/evidence where available:
  - requires parent linkage and verifies parent task is loadable/unverifiable-safe;
  - blocks execution when parent status is `CANCELLED`, `CANCEL_REQUESTED`, `ABORTED`, or `DEAD_LETTER` (conservative revocation/cancellation of delegation authority);
  - when delegation record is available: requires delegation exists, parent/delegation linkage matches, delegation status not `FAILED/CANCELLED/REVOKED`, and child linked to delegation;
  - enforces recorded effective permissions ⊆ requested/parent snapshots when present; malformed snapshot types now fail closed;
  - preserves logical-internal scope restriction (`delegation.coordinate` only unless explicitly verifiably authorized, not implemented).
- Guard remains enforced at **`_resume_locked`** (scheduler dispatch/resume boundary) and **`_execute`** (dispatch/execution boundary), providing defense-in-depth for covered paths.

### Bounded evidence (deterministic tests: `tests/test_phase5a6r4_gap_closure.py`)
- `test_delegated_guard_blocks_missing_or_revoked_delegation`: revoked/missing delegation record blocks execution guard.
- `test_delegated_guard_blocks_malformed_permission_snapshots`: malformed snapshot fails closed.
- Existing 5A.6/5A.6R/5A.6R2/5A.6R3 suites preserved and passing (38 tests) including delegation narrowing/idempotency/lifecycle invariants.

### Limitations (not fully closed)
- Guard revalidation is based on **local recorded snapshots/store state**; it does not provide authenticated identity, dynamic external authorization service revalidation, or cryptographic proof that an off-record permission revocation occurred. `local_trust` remains a non-authenticated assumption.
- Not every theoretical alternative/internal execution path outside traced resume/execute boundaries is exhaustively proven; unsupported/unverifiable paths must remain blocked/fail closed by design.
- Post-assignment permission reduction/revocation scenarios beyond covered store-state/snapshot cases (e.g. all recovery-triggered mutations, external auth revocation, every authorizer path) remain **PARTIAL/UNTESTED** per matrix.

## 2. Parent cancellation and dispatch prevention (Priority B)

### Fixes implemented (`aj/orchestrator.py`)
- **`_prepare_delegated_child_for_scheduling`** now enforces conservative cancellation/authority checks for delegated children before advancing/preparing:
  - if parent is missing/unverifiable or in `CANCELLED/CANCEL_REQUESTED/ABORTED/DEAD_LETTER`, preparation fails closed (`reason=parent_cancelled_or_unverifiable`) and attempts to abort preparable child (no new delegated authorization/preparation for dispatch).
- Execution guard also blocks delegated child execution when parent authority is cancelled/revoked/unverifiable.

### Bounded evidence
- `test_parent_cancellation_blocks_child_preparation`: parent cancellation prevents delegated child preparation/authorization under cancelled authority and/or requires guard block.

### Limitations (not fully closed)
- Full parent-cancellation orchestration (explicit request/verification of child cancellation across all active children, required vs optional policy application in every case, prevention of every future required-child creation/dispatch race under all schedulers/paths, cancellation-vs-completion race safety under true concurrency) is **not exhaustively implemented/proven**.
- Scheduler eligibility does not independently encode every delegation-parent cancellation policy; enforcement relies on preparation/guard fail-closed boundaries and lifecycle constraints where covered. Any path that cannot be proven safe must be treated as blocked/uncertain (no fabricated success).

## 3. Crash/recovery boundaries (Priority C - partial)

- No cross-store atomic durability mechanism added (by design/constraint). Existing explicit reconciliation/recovery hooks, pending markers, and non-fabricating recovery semantics preserved.
- NTFS/SQLite-WAL reliability and cross-store non-atomicity remain unresolved; crash windows A–H cannot be claimed fully recoverable/safe. Uncertainty must remain explicit/manual-review where not durably evidenced.
- 5A.6R4 added limited deterministic tests for anomaly/concurrency surfaces but did not produce exhaustive A–H restart/process-crash proofs on isolated storage for all boundaries.

## 4. Safety/constraint compliance
- No production/storage relocation, no deps, no Docker/Honcho/paid APIs/local LLMs, no real agent transport/fan-out/heartbeat/distributed workers/daemon, no Hermes/JARVIS/HELIX changes, Hermes NOT ATTACHED.
- Reused existing 5A.4 ExecutionStore, 5A.5 scheduler/dispatch, LeaseManager, delegation/assignment stores, receipts/journal/recovery/reconciliation. No duplicate orchestration systems. Fail-closed posture preserved. No cross-store atomicity/exactly-once/authenticated/distributed guarantees claimed.
