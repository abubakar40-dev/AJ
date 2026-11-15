# 42 — Phase 5A.6R4 Remaining Gap Closure Matrix

**Date:** 2026-11-14  
**Starting point:** 5A.6R3 matrix (`36`, preserved). 28 scenarios previously PARTIAL (20) or UNTESTED (8).  
**Scenario definitions:** per `35`/`36` reconstructed set (original source provenance UNVERIFIED per `41`; traceability caveat applies).  
**Disposition legend:** FIX REQUIRED | TEST REQUIRED | SOURCE/REQUIREMENT CLARIFICATION REQUIRED | UNSUPPORTED PATH — MUST BE BLOCKED | SAFE LIMITATION — DOCUMENTED AND ACCEPTED ONLY IF THE ORIGINAL REQUIREMENT ALLOWS IT

## 1. Disposition summary

| ID | Prior (5A.6R3) | Disposition | Priority | Rationale / planned closure in 5A.6R4 |
|---|---|---|---|---|
| 1 | PARTIAL | TEST REQUIRED (+ minor FIX if gap found) | Lifecycle | Hook/reconcile exists and covered for some transitions; need deterministic assertions across additional relevant child transition categories/paths (auth rejection, cancel states, recovery/manual-review) where supported. |
| 2 | PARTIAL | TEST REQUIRED | Lifecycle/Authz | Aggregation reflects terminal/aborted outcomes; certify parent-appropriate update/no-false-completion on authorization rejection path with explicit assertions. |
| 3 | PARTIAL | TEST REQUIRED | Lifecycle/Admission | Waiting/deferred children block completion by aggregation/guard; certify specific admission-deferral representation where feasible in current scheduler semantics. |
| 4 | PARTIAL | TEST REQUIRED | Lifecycle | Dispatch progress reflected via state/aggregation in covered flows; add isolated dispatch-progress assertion if feasible. |
| 5 | PARTIAL | TEST REQUIRED | Lifecycle | Execution start reflected via EXECUTING/running counts; add isolated assertion if feasible. |
| 6 | PARTIAL | TEST REQUIRED | Lifecycle | Completion reflected in aggregation/evidence in covered flows; strengthen end-to-end completion-update assertion. |
| 7 | PARTIAL | TEST REQUIRED (+ FIX if policy gap) | Lifecycle | Required failure blocks completion; certify deterministic parent-status/evidence policy behavior beyond guard. |
| 8 | PARTIAL | TEST REQUIRED (+ SOURCE/REQUIREMENT CLARIFICATION REQUIRED) | Lifecycle | Optional/required semantics partially demonstrated; exact optional-failure parent policy may depend on original requirement intent (UNVERIFIED source) — apply conservative deterministic fail-closed policy and test it. |
| 9 | PARTIAL | TEST REQUIRED | Lifecycle | UNKNOWN/missing treated manual-review/non-completing; add explicit UNKNOWN-state fixture/assertion where representable. |
| 11 | PARTIAL | TEST REQUIRED | Lifecycle | Manual-review sources (e.g. CANCEL_REQUESTED, recovery/unknown) block completion in logic; certify per-source cases. |
| 12 | UNTESTED | FIX REQUIRED + TEST REQUIRED | **B (Cancellation)** | No proven prevention of new child dispatch/preparation after parent cancellation and no verified child-cancellation orchestration; must enforce conservative dispatch/prep blocking and evidence-backed handling (unsupported orchestration steps must be blocked/fail closed). |
| 14 | PARTIAL | FIX/TEST REQUIRED (bounded) + SAFE LIMITATION — DOCUMENTED AND ACCEPTED ONLY IF THE ORIGINAL REQUIREMENT ALLOWS IT | **D (Concurrency)** | In-process guards insufficient for mutating race proof; add deterministic mutating concurrency/barrier tests and stale-writer protection checks; multi-process/distributed safety not claimable (limitation). |
| 16 | PARTIAL | TEST REQUIRED (+ FIX if needed) | Lifecycle/Recovery | Guard prevents false completion and contradictions detectable; certify rejection/explicit recovery handling for terminal-regression/contradiction cases within safe bounds. |
| 18 | PARTIAL | TEST REQUIRED (+ SOURCE/REQUIREMENT CLARIFICATION REQUIRED) | Lifecycle | Partial completion represented in counts but policy/state semantics depend on original intent; certify deterministic honest representation conservatively. |
| 19 | PARTIAL | TEST REQUIRED | Aggregation | History/evidence present; certify multi-entry preservation across distinct state changes. |
| 20 | PARTIAL | FIX/TEST REQUIRED (bounded) + SAFE LIMITATION — DOCUMENTED AND ACCEPTED ONLY IF THE ORIGINAL REQUIREMENT ALLOWS IT | **C (Crash)** | Pending/explicit recovery exists; simulate child-persisted/parent-update-not-started boundary on isolated temp storage where feasible; cross-store atomicity/NTFS durability limits remain. |
| 21 | UNTESTED | FIX/TEST REQUIRED (bounded) + SAFE LIMITATION — DOCUMENTED AND ACCEPTED ONLY IF THE ORIGINAL REQUIREMENT ALLOWS IT | **C (Crash)** | Interrupted intent not proven; add deterministic interruption simulation and detection/recovery where feasible, else fail closed/manual-review. |
| 22 | PARTIAL | TEST REQUIRED (+ FIX if detector gap) | Detection | Detectors exist; certify missing/inconsistent evidence detection with fixtures. |
| 23 | UNTESTED | TEST REQUIRED (bounded) + SAFE LIMITATION — DOCUMENTED AND ACCEPTED ONLY IF THE ORIGINAL REQUIREMENT ALLOWS IT | **C/D** | Concurrent recovery safety not proven; add deterministic controlled test or fail-closed evidence; multi-process guarantee not claimable. |
| 25 | UNTESTED | TEST REQUIRED (+ FIX if needed) | Recovery | Ambiguous execution must not be blindly retried; certify fail-closed behavior in delegation-relevant recovery paths. |
| 26 | PARTIAL | TEST REQUIRED (+ FIX if detector gap) | **E (Anomaly)** | Detector exists; add deterministic orphan-child fixture/assertion. |
| 28 | UNTESTED | FIX REQUIRED + TEST REQUIRED | **E (Anomaly)** | Missing assignment detection/remediation gap; extend read-only detector and bounded explicit remediation. |
| 29 | UNTESTED | FIX REQUIRED + TEST REQUIRED | **E (Anomaly)** | Expired/uncertain lease detection not delegation-surfaced; extend detector/remediation (observational, fail-closed). |
| 37 | UNTESTED | FIX REQUIRED + TEST REQUIRED | **A (Authz)** | Guard revalidates recorded envelopes but not certified for post-assignment revocation/reduction/current-state revalidation across paths; strengthen checks and add deterministic adversarial tests. |
| 38 | UNTESTED | FIX REQUIRED + TEST REQUIRED / UNSUPPORTED PATH — MUST BE BLOCKED | **A (Authz)** | Not all execution/recovery/alternative paths certified; trace and enforce guard/current-state authz on all supported paths or explicitly block unsupported paths with tests. |

## 2. Priority focus mapping

- **Priority A (Authorization/revocation):** 37, 38 (and related security assertions affecting 36/paths).  
- **Priority B (Parent cancellation/dispatch prevention):** 12 (and race/dispatch implications for 1,3,4,5,20).  
- **Priority C (Crash windows A–H):** 20,21,23 and matrix crash windows A–H (`38`): A PARTIAL, B UNTESTED, C UNTESTED, D PARTIAL, E UNTESTED, F UNTESTED, G UNTESTED, H PARTIAL.  
- **Priority D (Mutating concurrency/stale-writer):** 14,23 and races (duplicate apply, stale overwrite, child-completion vs parent-cancel vs reconcile vs recovery/dispatch).  
- **Priority E (Anomaly detection/remediation):** 26,28,29 plus stuck cancellation, pending reconciliation beyond policy, ambiguous execution/linkage, inconsistent terminal states.

## 3. Scenarios already PASS in 5A.6R3 (unchanged target: preserve)

10,13,15,17,24,27,30,31,32,33,34,35,36,39,40,41,42,43,44,45 — must remain PASS with regressions intact.

## 4. Non-code dispositions and constraints

- **SOURCE/REQUIREMENT CLARIFICATION REQUIRED:** original scenario source provenance UNVERIFIED (`41`); where policy intent (optional failure, partial completion semantics) cannot be confirmed from recoverable original artifact, apply conservative deterministic fail-closed behavior, document explicitly, and test that behavior (cannot claim original-requirement equivalence).
- **SAFE LIMITATION — DOCUMENTED AND ACCEPTED ONLY IF THE ORIGINAL REQUIREMENT ALLOWS IT:** cross-store non-atomicity, NTFS/SQLite-WAL durability uncertainty, and lack of multi-process/distributed locking prevent provable guarantees for some crash/concurrency cases; such cases must fail closed, be explicitly represented (pending/manual-review/uncertainty), and be documented. Acceptance cannot be assumed because original requirement allowance is unverified.
- **UNSUPPORTED PATH — MUST BE BLOCKED:** any execution/dispatch path that cannot be proven to enforce delegated authorization and current-state checks must be blocked (not merely documented).

## 5. 5A.6R4 execution intent (bounded)

1. Implement/fix Priority A and B in code with deterministic tests.  
2. Extend anomaly detection/remediation (Priority E) and add deterministic tests.  
3. Add deterministic mutating-concurrency and feasible crash-boundary simulations (Priority D/C) with fail-closed limitations.  
4. Certify/update dispositions with evidence; rerun targeted 5A.4–5A.6R3 regressions, full suite, `aj --check`.  
5. Produce docs `43–45` and consolidated report. Verdict remains INCOMPLETE if any previously PARTIAL/UNTESTED scenario lacks evidence-backed closure or if original provenance remains unverified (per acceptance criteria).