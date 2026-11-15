# 50 — Phase 5A.6R5 Revised Acceptance Baseline Proposal

**Date:** 2026-11-14  
**Status:** **Proposal requiring explicit user decision** (original acceptance source not recovered; reconstructed requirements must not be silently elevated).

## A. Original verified requirements (supported by recoverable authoritative sources)

Requirements directly supported by recoverable, in-repo authoritative artifacts (earlier 5A/4B/core docs, code contracts, verified stage reports) — **excluding** unrecovered 5A.6R2 "45 scenarios / A–J" original text:

1. **Preservation and safety boundaries:** no destructive Git ops; preserve pre-existing tracked/untracked work; JARVIS/HELIX/Hermes protected/untouched; Hermes NOT ATTACHED; `hermes.gateway.ensure` not implemented/enabled/executed/authorized unless explicitly approved.
2. **AJ-local, bounded, fail-closed foundations:** reuse existing task/execution/lease/receipt/journal/evidence/recovery/scheduler/delegation stores where applicable; no duplicate orchestration systems; no cross-store atomicity/exactly-once/distributed-correctness claims; fail closed on unknown/unhealthy/untrusted/ambiguous state.
3. **5A.4/5A.5 accepted baselines (as previously reported/verified in stage docs):** AJ-owned execution domain (`exc_*`, `ExecutionStore`, task↔execution linkage) and explicit eligibility/admission/dispatch with bounded scheduling, durable dispatch intent/evidence, lease-guarded dispatch, observational monitoring.
4. **Delegation foundation invariants (design-verified in code/docs, partially certified):** Task≠Operation≠Execution≠Attempt≠Agent(logical)≠Assignment≠Lease≠Delegation≠Aggregation distinctions; deterministic ids/idempotency intent; capability matching and intersection-only permission narrowing; no fabricated remote acceptance/execution/completion; no real agent transport/fan-out/heartbeat/distributed workers.
5. **Evidence-honest health/regression gates (when achieved):** `aj --check` passing with Hermes NOT ATTACHED; relevant regression suites passing; full-suite green is desirable but currently environment-sensitive (see D/E, `49`).
6. **Storage/identity honesty:** NTFS/SQLite-WAL reliability risk acknowledged; `local_trust` not authenticated human identity.

> Note: These are baseline engineering constraints/invariants evidenced in repo; they do **not** substitute for the unrecovered 45/A–J acceptance specification.

## B. Reconstructed requirements (inferred from 5A.6R3 matrix or later phase docs — NOT original)

All items below derive from reconstructed artifacts (`35`, `36`, `41`, `42`) and must be treated as **provisional** until an authoritative source or explicit user approval is provided:

1. **Scenarios 1–45** as enumerated in `36_PHASE_5A_6R3_45_SCENARIO_CERTIFICATION_MATRIX.md` (reconstructed from "5A.6R2 section 13 tests 1–45").
2. **Crash windows A–J** as enumerated in `35`/`36`/`38` (reconstructed from "5A.6R2 section 6 crash windows A–J").
3. **Certification bar implied by 5A.6R3–5A.6R4:** every scenario/window requires evidence-backed PASS with traceable original provenance; PARTIAL/UNTESTED/FAIL or unverified provenance implies INCOMPLETE.
4. **Dispositions and priority closures (A–E)** defined in `42` for 28 gaps (auth revocation, cancellation/dispatch prevention, crash A–H, mutating concurrency/stale-writer, anomaly detection/remediation).

**Policy:** do not elevate any B item to "original approved requirement" without explicit user confirmation or recovery of an authoritative artifact.

## C. Confirmed engineering invariants (justified from existing architecture and approved project direction)

Invariants that should hold for continued AJ work regardless of 45/A–J provenance resolution:

1. **Fail closed:** on unverifiable/malformed/ambiguous authorization, delegation, lifecycle, persistence, or recovery state; never fabricate success/completion/acceptance.
2. **No false parent completion:** delegation parent must not transition to successful completion when required child outcomes are unresolved/unknown/recovery-required/manual-review/unsafe (guarded in covered paths; exhaustive proof pending).
3. **Boundary enforcement over recorded snapshots alone is insufficient:** execution boundaries must revalidate against current trusted state where feasible; unsupported paths must be blocked.
4. **Idempotent, evidence-backed reconciliation:** explicit dry-run/apply, bounded scope, provenance/history, non-mutating monitoring/reads.
5. **Honest uncertainty representation:** cross-store non-atomic operations and storage unreliability require detectable pending/manual-review/uncertain states, not silent success.
6. **Resource/scope bounds:** manual launch, bounded concurrency/queues/work, no unreviewed deps/daemons/external transport.

## D. Unresolved decisions (meaning, authority, or acceptance standard cannot currently be established)

1. **Authoritative source/provenance** for 45 scenarios and A–J windows (and exact acceptance intent/wording).
2. **Acceptance authority of reconstructed matrix:** treat `36` as binding gate, advisory checklist, or superseded by newly approved baseline?
3. **Policy semantics where original intent unverified:** optional-child failure handling, partial-completion representation, "appropriate" parent updates on auth rejection/deferral, full parent-cancellation orchestration semantics, "all supported execution paths" enumeration.
4. **Crash/concurrency certification standard:** required proof level given cross-store non-atomicity and no multi-process/distributed implementation (detection/fail-closed vs recoverability guarantees).
5. **Full-suite criterion (scenario 43):** whether environment-intermittent NTFS/SQLite-sensitive failure blocks acceptance if unrelated to changed code and focused regressions are green.
6. **Whether to pursue original-source recovery outside repo** (user-held prompts/chats/exports) as a prerequisite gate.

## E. Known technical limitations (must remain explicit)

- **NTFS/SQLite-WAL reliability:** unresolved sensitivity/intermittency risk (see `49`); no repair/migration performed.
- **Cross-store non-atomicity:** task/delegation/assignment/execution/lease/receipt/journal/evidence stores are not atomically committed together.
- **No exactly-once guarantee:** duplicates/ambiguous outcomes possible at boundaries; must be detected/fail-closed where not provably safe.
- **`local_trust` is not authenticated identity:** local runtime/provenance metadata is not human/cryptographic authentication.
- **No distributed or multi-process correctness guarantees unless proven:** current evidence is in-process/bounded/deterministic in covered cases only.
- **No real external agent transport:** logical/internal AJ-only delegation foundations; no real remote acceptance/progress/completion proofs.
- **Hermes/JARVIS/HELIX:** unattached/untouched per constraints; no gateway ensure.

## F. Recommended gating decision for user

Before further corrective implementation, explicitly decide one of:
1. **Provide/recover authoritative original 45/A–J source** (external artifact) and certify against it; or
2. **Adopt a ratified reconstructed baseline** (approve `35`/`36`/A–J definitions and explicit policy clarifications as the new acceptance contract); or
3. **Adopt an invariant-based baseline** (A+C+E above, with a narrowed, approved scenario/checklist set and explicit non-goals).

Until decided, 5A.6R/5A.6R2/5A.6R3/5A.6R4 remain INCOMPLETE and 5A.7 remains BLOCKED.
