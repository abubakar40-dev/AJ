# 32 — Parent Reconciliation and Recovery (Stage 5A.6R2)

**Status:** Bounded, evidence-backed reconciliation and detection improvements (partial closure).

## 1. Reconciliation model

- **Automatic trigger:** durable child task lifecycle transitions (via `TaskStore` hook) trigger bounded delegation-parent reconciliation attempts with re-entrancy/concurrency guards; failures mark delegation reconciliation pending in evidence when possible.
- **Explicit operations:** `Aj.reconcile_delegation_parent(...)`
  - **Dry-run/inspection:** read-only (no delegation/task mutation, no child preparation side effects), returns computed aggregation/snapshot/idempotency/contradiction observations.
  - **Apply:** mutating and explicit; performs bounded safe child preparation where applicable, recomputes aggregation, persists reconciliation provenance/evidence and bounded history on delegation records, records incorrect-completion observations. Bounded by validated `batch_size` (clamped).
- **Idempotency:** aggregation includes `child_state_snapshot` hash; repeated runs detect unchanged snapshots (`idempotent_noop`) and avoid contradictory logical outcomes. Historical evidence retained (bounded).

## 2. Crash/race handling (honest, bounded)

- **A–C (child persisted / intent or evidence gaps):** addressed partially via post-persist hook + pending marker + explicit reconciliation/detection of stale aggregation and incomplete evidence; not a complete transactional recovery engine.
- **D–H (concurrent child/parent/recovery transitions):** guarded by thread-local re-entrancy + RLock around reconciliation and by idempotent snapshot comparison; not proven safe under all multi-process/thread timing or cross-store races. Before-transition guard blocks false parent completion conservatively.
- **I–J (delegation-task disagreement / contradictory terminal state):** detected by monitoring/anomaly findings and reconciliation observations; terminal task-state regression not automatically forced by illegal transitions (manual-review/evidence-preserved posture).
- **Persistence uncertainty:** fail closed where state unverifiable (e.g. completion guard blocks on delegation read/compute failure). No cross-store atomicity, no exactly-once, no distributed locking/correctness claimed.

## 3. Monitoring and detection (read-only)

`delegation_monitor()` / `detect_delegation_anomalies()` remain non-mutating and now report extended findings with codes/severity/auto-recovery guidance where applicable:
- orphaned/missing child tasks, missing parents, incomplete delegations
- stuck/recovery-required assignments, active assignments without execution linkage (observational)
- stale aggregation, incorrect completed parent
- delegation-task disagreement / unverifiable delegation state
- missing delegation provenance for delegation-context child tasks

Monitoring does not repair state; explicit reconciliation is separate.

## 4. Cancellation and child failure isolation

- Delegation creation still rejects non-delegable/terminal parent states; reconciliation/guard logic treats cancelled/failed/unknown/recovery-required/manual-review outcomes conservatively in aggregation and completion blocking.
- Full parent-cancellation orchestration (stop creation, prevent unsafe dispatch, request child cancellation through all supported mechanisms, reconcile only after evidenced outcomes) is **not fully implemented/enforced end-to-end**; existing cancel/recovery paths and scheduler controls remain authoritative. Unknown is not fabricated as success/failure.

## 5. Unresolved risks

- Incomplete crash-window automation for all stated scenarios (A–J) and incomplete detection/remediation for every orphan/stuck/inconsistency case.
- Multi-process/concurrent race safety unproven beyond deterministic single-process tests/guards.
- NTFS/SQLite-WAL durability unresolved; temporary storage used for deterministic tests where appropriate.
- `local_trust` remains non-authenticated; no real remote agent acceptance/transport.
