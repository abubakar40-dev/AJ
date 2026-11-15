# 02 — Multi-Store Consistency Investigation (Secondary, evidence-based)

**Scope:** non-atomic writes across task, audit, journal, receipt, and operation-evidence stores in privileged reconciliation and related flows. No storage redesign implemented.

## 1. Stores and write sequences observed

### Stores involved
- **TaskStore** (`tasks.jsonl`, append-only envelopes): transitions/saves/mutations (`self.tasks.transition`, `self.tasks.save`, `self.tasks.apply`, `self.tasks.mutate`).
- **Operation evidence** (`reconciliation_operations.jsonl`, append-only): intent, progress, outcome records.
- **Audit** (`audit/events-*.jsonl`, append-only): `privileged_authorization`, `operator_reconciliation`, and other task/audit events.
- **Journal** (`journal.jsonl`, append-only): `OPERATOR_RECONCILIATION` and execution/recovery events.
- **Receipts** (`receipts.jsonl`, append-only): execution/attempt receipts (primarily execution paths; reconcile does not create execution receipts but interacts with inspection/evidence).
- **Leases** (lease files): acquire/release/break operations for serialization/ownership.
- **Idempotency/memory**: separate stores in broader flows (not the primary reconcile mutation set).

### Reconcile sequence (current, simplified)
1. Validate inputs and handle known operation-id cases (terminal duplicate -> idempotent return; intent-only incomplete -> refused/manual, no reapply).
2. Compute authorization decision (no task mutation).
3. **Append operation-evidence intent** (durable). Fail closed if intent cannot be recorded.
4. **Append audit `privileged_authorization`** (best-effort in implementation; decision itself fail-closed). If denied/unavailable/invalid -> append progress/outcome `REFUSED`, record operator reconciliation evidence best-effort, return no state change.
5. Acquire reconciliation/operation lease and perform guarded state change path (transition/save/apply/mutate as applicable, calling `dead_letter`/`abandon` helpers in some actions).
6. Record operator reconciliation evidence: task metadata mutation, **audit `operator_reconciliation`**, **journal `OPERATOR_RECONCILIATION`**, completeness flags.
7. Append operation-evidence progress/outcome (best-effort in `finally`/path; completeness/incomplete-evidence surfaced when state changed but evidence trail incomplete).

**Key property:** each append/write targets an independent file/store with independent locking/fsync behavior; there is no cross-store atomic commit/transaction.

## 2. Partial-success windows and detectability

| Window | Possible partial state | Detectable? | Evidence/mechanism |
|---|---|---|---|
| Intent appended, crash before outcome/state change | Intent exists, no terminal outcome | **Yes** | Operation-evidence `is_incomplete`; consistency checker `incomplete_privileged_operation`; reconcile refuses reapply for same op ID as incomplete/manual disposition. |
| State changed, outcome/audit/journal/evidence incomplete | Canonical task moved but evidence trail partial | **Partially/yes in intended cases** | Reconcile tracks `evidence_recording`/`incomplete_evidence`; task metadata flags; consistency findings (e.g. reconciliation evidence incomplete, operation outcome without audit correlation as uncertain); inspection surfaces warnings. Not guaranteed perfect classification for every crash point. |
| Authorization audited but intent append failed | Should fail closed before mutation | **Yes (prevented)** | Intent append failure raises storage error and blocks proceed. |
| Audit/journal append fails around reconciliation record | State/op outcome may exist but audit trail incomplete | **Yes/uncertain** | `_record_operator_reconciliation` returns/persists completeness flags/errors; consistency reports uncertain/confirmed gaps depending on correlation. |
| Lease acquired/released around crash | Ownership ambiguity/expiry handling | **Yes by design** | Lease state/expiry model and recovery/inspection logic; fail-closed ownership checks. |
| Receipt/journal/task divergence (general) | Cross-store mismatch/conflict | **Yes (best-effort)** | Consistency checker detects orphan/mismatch/completion conflicts/malformed records with confidence levels. |

## 3. Recovery safety and idempotent retries

- **Completed vs incomplete privileged op:** distinguished by presence of terminal operation-evidence outcome for the operation ID. Terminal duplicate -> idempotent no-reapply. Intent-only/incomplete -> no auto-retry, no auto-success, manual disposition required.
- **State-changing reconcile actions:** guarded by preconditions (status/transition legality), lease serialization, ownership/conflict checks, and fail-closed evidence/ambiguity checks (especially `clear_recovery_required`).
- **Idempotent retries:** safe when caller reuses same operation ID for a known terminal outcome (returns recorded/idempotent result). Unsafe automatic retry is intentionally avoided for incomplete/ambiguous cases.
- **Limit:** a crash exactly between dependent non-atomic writes can leave a window where canonical state and some evidence disagree; current design prioritizes detectability, honesty, and fail-closed/manual resolution over silent repair.

## 4. Alternatives considered (recommendation only, not implemented)

| Option | Expected benefit | Cost/risk/fit | Recommendation |
|---|---|---|---|
| **Deterministic correlation protocol hardening** (stronger shared operation/correlation IDs across task/audit/journal/receipt/op-evidence, stricter completeness checks) | Better detectability/classification and operator triage with minimal architectural change | Low-medium; must preserve append-only semantics and compatibility | **High priority (next)**. Evidence shows gaps are mostly diagnosable but correlation can be stronger. |
| **Transactional outbox / single append-only operation log (WAL-intent)** for privileged ops | Material improvement: intent + state-change intent + side-record intents can be atomically committed before/with effects | Medium-high; requires careful migration/design, fsync ordering, replay/idempotency semantics, and compatibility with existing stores | **Medium priority / design spike** if stronger guarantees needed; best path to reduce partial-trail windows without external DB. |
| **Move to embedded transactional DB (SQLite) for all stores** | Strong atomicity/transactions possible | **Large redesign**, migration risk, locking/performance/operational changes, conflicts with append-only JSONL evidence model and constraints (no new DB/recovery engines in 3F) | **Not recommended in this phase**; only with explicit architectural approval. |
| **Two-phase markers with mandatory fsync/ordered appends** | Marginally stronger durability ordering | Filesystem-dependent; cannot make multi-file updates atomic | **Low-medium**, consider alongside correlation hardening. |

## 5. Sufficiency for controlled local use
**Assessment:** current architecture provides **sufficient safety for controlled local/internal use** *with documented limitations*: partial states are generally detectable, incomplete privileged operations are not auto-completed/replayed unsafely, and idempotent duplicate handling is in place. It does **not** provide multi-store atomicity, exactly-once semantics, or guaranteed perfect classification for every crash boundary. This matches and refines AJ-AUD-001.

## 6. Backlog impact
- Keep **AJ-AUD-001** open (Medium, architectural weakness), reprioritize around correlation/WAL-intent evaluation and evidence completeness.
- Add/track 3F-specific documentation/residual items in Phase 3F backlog delta (identity boundary now hardened; atomicity remains a separate reliability concern).