# 47 — Phase 5A.6R5 Requirement Traceability and Gap Analysis

**Date:** 2026-11-14  
**Scope:** Traceability audit of reconstructed 45-scenario matrix (`36`, preserved, not overwritten) and crash windows A–J against recoverable evidence. No scenario meanings or acceptance standards silently changed.

## 1. Method and constraints

- **Preserved artifact:** `36_PHASE_5A_6R3_45_SCENARIO_CERTIFICATION_MATRIX.md` unchanged.
- **Compared against:** 5A.6R2–5A.6R4 docs (`30`–`45`), 5A.6R5 recovery search (Doc `46`), current implementation/test evidence cited in `36`/`39`/`45`.
- **Original source status:** not recovered (UNVERIFIED, `46`). Therefore "original intent" and "original acceptance criterion" cannot be authoritatively verified from a recoverable original artifact.

## 2. Scenario traceability (1–45)

Legend: **Orig. evidence** = recoverable original-source evidence found. **Intent verified** = verified against original source (not reconstructed). **Reconstructed** = interpretation/listing derived from `35`/`36`/later docs rather than recovered original. **Criterion unambiguous** = text in `36` is reasonably specific, but authority/unambiguous original meaning may remain unresolved.

| ID | Reconstructed description (`36`) | Available original-source evidence | Original intent verified | Reconstructed interpretation | Acceptance criterion unambiguous | Current PASS/PARTIAL/UNTESTED remains valid (as reconstructed certification) | Missing evidence | Clarification required |
|---|---|---|---|---|---|---|---|---|
| 1 | Child transition automatically triggers parent reconciliation. | None recovered | No (UNVERIFIED) | Yes | Partially (scope of "relevant durable child transition"/"every relevant transition category" ambiguous without original) | Yes (5A.6R3: PARTIAL; 5A.6R4 no full closure) | Original text; per-transition-category/path proof | Yes |
| 2 | Authorization rejection updates parent appropriately. | None recovered | No | Yes | Partially ("appropriately"/parent-status policy not fully specified) | Yes (PARTIAL) | Original intent; exhaustive auth-rejection paths | Yes |
| 3 | Admission deferral does not allow false parent completion. | None recovered | No | Yes | Mostly (no-false-completion clear; deferral representation/path ambiguous) | Yes (PARTIAL) | Original wording; admission-deferral-specific certification | Yes |
| 4 | Dispatch updates parent progress. | None recovered | No | Yes | Partially (what constitutes "progress"/evidence) | Yes (PARTIAL) | Dispatch-specific evidence/isolation | Yes |
| 5 | Execution start updates parent progress. | None recovered | No | Yes | Partially | Yes (PARTIAL) | Execution-start-specific assertion | Yes |
| 6 | Child completion updates parent aggregation. | None recovered | No | Yes | Mostly | Yes (PARTIAL) | All completion paths | Yes |
| 7 | Required child failure updates parent status. | None recovered | No | Yes | Partially (parent status mapping beyond guard/evidence) | Yes (PARTIAL) | Deterministic parent-status policy intent | Yes |
| 8 | Optional child failure follows policy. | None recovered | No | Yes | No (policy details depend on original intent) | Yes (PARTIAL) | Original policy/intent; exhaustive matrix | Yes |
| 9 | UNKNOWN child prevents false completion. | None recovered | No | Yes | Mostly | Yes (PARTIAL) | Explicit UNKNOWN-state path certification | Yes |
| 10 | RECOVERY_REQUIRED child prevents false completion. | None recovered | No | Yes | Yes | Yes (PASS in `36`, preserved) | Original-source confirmation only | Yes (provenance) |
| 11 | Manual-review child prevents false completion. | None recovered | No | Yes | Mostly | Yes (PARTIAL) | All manual-review sources | Yes |
| 12 | Parent cancellation stops new child dispatch. | None recovered | No | Yes | Mostly (orchestration details ambiguous) | Yes (5A.6R3 UNTESTED; 5A.6R4 bounded fix/test → PARTIAL per `45`) | Full child-cancel verification, all dispatch/creation/race paths | Yes |
| 13 | Repeated aggregation is idempotent. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 14 | Concurrent aggregation is handled safely. | None recovered | No | Yes | No ("safely" scope: in-process vs multi-process/distributed) | Yes (PARTIAL) | Mutating/multi-process/race proof, stale-writer proof | Yes |
| 15 | Stale aggregation is detected. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 16 | Parent terminal-state regression is rejected or explicitly recovered. | None recovered | No | Yes | Partially ("explicitly recovered" conditions) | Yes (PARTIAL) | Explicit recovery/regression policy proof | Yes |
| 17 | Parent completion requires verified required-child outcomes. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 18 | Partial completion is represented accurately. | None recovered | No | Yes | No (representation/policy intent unclear) | Yes (PARTIAL) | Original intent; state semantics certification | Yes |
| 19 | Historical aggregation evidence is preserved. | None recovered | No | Yes | Partially (extent/append-only guarantees) | Yes (PARTIAL) | Multi-distinct-entry/append-only proof | Yes |
| 20 | Child transition persisted before parent update is recoverable. | None recovered | No | Yes | Mostly | Yes (PARTIAL) | Exact crash-boundary/restart proof, cross-store limits | Yes |
| 21 | Interrupted aggregation intent is recoverable. | None recovered | No | Yes | Mostly | Yes (UNTESTED per `45`) | Deterministic intent interruption/restart proof | Yes |
| 22 | Parent update with missing evidence is detectable. | None recovered | No | Yes | Mostly | Yes (PARTIAL) | Specific missing-evidence fixtures/cases | Yes |
| 23 | Concurrent recovery is safe or fails closed. | None recovered | No | Yes | Partially ("safe" scope) | Yes (UNTESTED) | Deterministic concurrent recovery tests/proof | Yes |
| 24 | Parent-child contradictory state is detected. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 25 | Ambiguous execution is never blindly retried. | None recovered | No | Yes | Yes | Yes (UNTESTED) | Delegation-relevant ambiguous-execution recovery tests | Yes |
| 26 | Orphaned child detected. | None recovered | No | Yes | Yes | Yes (PARTIAL) | Deterministic orphan fixture | Yes |
| 27 | Missing child/delegation linkage detected. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 28 | Missing assignment detected. | None recovered | No | Yes | Yes | Yes (5A.6R4 PARTIAL, detection+test added) | Safe apply remediation certification | Yes |
| 29 | Expired lease uncertainty detected. | None recovered | No | Yes | Mostly | Yes (5A.6R4 PARTIAL, best-effort detection) | Dedicated lease-expiry fixture/certification | Yes |
| 30 | Stale parent aggregation detected. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 31 | Incorrect completed parent detected. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 32 | Read-only monitoring does not mutate state. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 33 | Dry-run reconciliation does not mutate state. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 34 | Explicit apply reconciliation records provenance. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 35 | Reconciliation batch limits are enforced. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 36 | Delegated permission guard still blocks escalation. | None recovered | No | Yes | Mostly | Yes (PASS for covered case) | Broader escalation-path certification | Yes |
| 37 | Permission changes after assignment are revalidated. | None recovered | No | Yes | Mostly ("revalidated" mechanism/scope) | Yes (5A.6R4 PARTIAL) | Exhaustive revocation/reduction/current-state revalidation across paths | Yes |
| 38 | All supported execution paths enforce authorization. | None recovered | No | Yes | No ("all supported" set not originally enumerated in recoverable form) | Yes (5A.6R4 PARTIAL) | Authoritative path list; exhaustive proof/blocking evidence | Yes |
| 39 | 5A.4 execution regressions pass. | None recovered | No | Yes | Yes | Yes (PASS, focused suites) | Original-source confirmation | Yes (provenance) |
| 40 | 5A.5 scheduler regressions pass. | None recovered | No | Yes | Yes | Yes (PASS, focused suites) | Original-source confirmation | Yes (provenance) |
| 41 | 5A.6 delegation foundation tests pass. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 42 | 5A.6R closure tests pass. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |
| 43 | Full regression suite passes. | None recovered | No | Yes | Yes | **Conditionally weakened:** 5A.6R5 observed 576 passed/1 failed (env-related) in full run; focused 5A.4–5A.6R4 regressions PASS (65). Reconstructed criterion "full regression suite passes" not fully satisfied by latest full run. | Green full-suite evidence in this environment or authoritative disposition of failure | Yes |
| 44 | AJ health check passes. | None recovered | No | Yes | Yes | Yes (PASS, 23/23, RC 0 in 5A.6R5) | Original-source confirmation | Yes (provenance) |
| 45 | Hermes remains NOT ATTACHED. | None recovered | No | Yes | Yes | Yes (PASS) | Original-source confirmation | Yes (provenance) |

## 3. Crash windows A–J traceability (independent)

Definitions per reconstructed set (`35`/`36`); original source UNVERIFIED.

| Window | Reconstructed definition | Original-source evidence | Intent verified | Reconstructed interpretation | Criterion unambiguous | Current result validity (reconstructed) | Missing evidence | Clarification required |
|---|---|---|---|---|---|---|---|---|
| A | Child state persisted, parent reconciliation not started. | None recovered | No | Yes | Mostly | PARTIAL (`38`/`36`/`45`) | Exact durable-boundary/restart proof | Yes |
| B | Parent reconciliation intent recorded, parent state not updated. | None recovered | No | Yes | Mostly | UNTESTED | Intent-persist/interruption simulation + recovery proof | Yes |
| C | Parent state updated, aggregation evidence not fully persisted. | None recovered | No | Yes | Mostly | UNTESTED | Boundary simulation under non-atomic stores | Yes |
| D | Two child transitions trigger parent reconciliation concurrently. | None recovered | No | Yes | Mostly | PARTIAL | True mutating concurrent/race proof | Yes |
| E | Parent cancellation occurs while a child completes. | None recovered | No | Yes | Mostly | UNTESTED | Deterministic race/cancel-vs-complete proof | Yes |
| F | Child completion occurs while parent recovery runs. | None recovered | No | Yes | Mostly | UNTESTED | Recovery-vs-completion race proof | Yes |
| G | Two recovery processes inspect the same incomplete parent. | None recovered | No | Yes | Partially (multi-process scope) | UNTESTED | Concurrent/multi-process recovery proof | Yes |
| H | Parent marked complete while child transition concurrently being persisted. | None recovered | No | Yes | Mostly | PARTIAL | Race-proof preventing contradictory terminal state | Yes |
| I | Delegation record and task records disagree. | None recovered | No | Yes | Yes | PASS (detection, per `38`) | Repair/recovery completeness if required by original | Yes |
| J | Parent has terminal state but child evidence contradicts it. | None recovered | No | Yes | Yes | PASS (detection, per `38`) | Repair/recovery completeness if required by original | Yes |

## 4. Key findings

- **Provenance:** no scenario/window has recoverable original-source evidence in repo/workspace/git history searched; all 45 and A–J are **reconstructed interpretations** traceable to `35`/`36` lineage.
- **Validity of current results:** PASS/PARTIAL/UNTESTED classifications remain valid **only as reconstructed-certification status**; they cannot be claimed as certification against a verified original requirement set.
- **Ambiguity hotspots:** policy/semantics-dependent scenarios (2,7,8,12,14,16,18,23,37,38), crash/concurrency safety scope (14,20,21,23,A–H), and "full regression suite passes" (43) given latest full-suite environment failure.
- **Action:** clarify/approve authoritative requirement baseline before treating any reconstructed item as acceptance gate (Doc `50`).
