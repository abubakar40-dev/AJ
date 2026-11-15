# 41 — Phase 5A.6R4 Canonical Scenario Source and Traceability

**Date:** 2026-11-14  
**Phase:** 5A.6R4 (section 2: establish canonical 45-scenario source)  
**Status:** Original-source provenance **UNVERIFIED** (no recoverable original artifact found in repository). 5A.6R3 matrix preserved; traceability added.

## 1. Search and recovery actions performed

Searched the AJ repository (tracked and untracked workspace files, including `ENGINEERING_AUDIT/` phase folders and docs `30–39`) for:
- Exact scenario texts (e.g. "Child transition automatically triggers parent reconciliation", "Permission reduction after assignment", "Admission deferral does not allow false parent completion").
- Crash-window texts (e.g. "Child state persisted, parent reconciliation not started", "crash windows A–J" definitions).
- "45 scenarios", "A–J", 5A.6R2 requirement/section references and related certification lists.

**Findings:**
- Scenario/window definitions appear in 5A.6R3 docs `35` and `36` as a reconstructed "authoritative 5A.6R2 requirement set (section 13 tests 1–45 and section 6 crash windows A–J)" with an explicit provenance note that the verbatim list was not found in stored 5A.6R2 docs `30–34`.
- Docs `33`, `34`, `37`, `38`, `39` reference "45 enumerated 5A.6R2 scenarios" and crash windows A–J but do not restate the full verbatim list.
- No standalone repository document, earlier phase artifact file, implementation-directive file, or other preserved project record in the repo was found containing the exact original 45-scenario list or exact A–J crash-window definitions as a recoverable source artifact.

## 2. Original source identification (required)

| Field | Record |
|---|---|
| **Exact path/name** | **Not recovered** (no repository file/artifact identified) |
| **Version/date** | **Unknown / not recoverable** |
| **Provenance** | **UNVERIFIED.** Likely originated from the 5A.6R2 implementation directive/requirements (external to preserved repo artifacts), but this cannot be confirmed from repository evidence. |
| **Recovered content** | None as original artifact. Reconstructed list exists in `35`/`36` only. |

**Honest determination:** The original 45-scenario source and A–J crash-window source **cannot be established as traceable to a preserved original artifact** from available repository evidence. The reconstructed list in 5A.6R3 docs **must not be labeled the original**.

## 3. Comparison: reconstructed 5A.6R3 list vs "original"

Because the original source artifact is unrecovered, a verbatim comparison against the original is **not possible**.

| Aspect | 5A.6R3 reconstructed list (`35`/`36`) | Original source | Difference |
|---|---|---|---|
| Scenario count | 45 (IDs 1–45) | Unknown/unverified | Cannot confirm |
| Scenario wording | As recorded in `35`/`36` (sourced from 5A.6R2 requirements context) | Unknown/unverified | Cannot confirm verbatim equivalence |
| Crash windows | A–J as recorded in `35`/`36` | Unknown/unverified | Cannot confirm verbatim equivalence |
| Coverage/interpretation | Mapped and certified in `36` with PASS/PARTIAL/UNTESTED outcomes | Unknown/unverified | Cannot confirm intended interpretation |

**Risk:** 5A.6R3 certification may not align perfectly with the unrecovered original wording/intent. Any such misalignment remains **unverifiable** from repo evidence.

## 4. Preservation and traceability actions

- **5A.6R3 matrix preserved:** `36_PHASE_5A_6R3_45_SCENARIO_CERTIFICATION_MATRIX.md` is **not overwritten**. Historical results remain intact.
- **Traceability added:** this document records search actions, non-recovery, UNVERIFIED provenance, and comparison limitations. `42` and subsequent 5A.6R4 artifacts reference scenario IDs 1–45 and windows A–J as defined in `35`/`36` for continuity, while carrying forward this provenance caveat.
- **No silent rewrite:** original definitions were not modified (none recovered to modify). The reconstructed definitions are explicitly identified as reconstructed.

## 5. Acceptance impact

Per 5A.6R4 acceptance criteria: "The original 45-scenario source is identified and traceable, or any inability to establish original provenance is honestly recorded and the phase remains incomplete."  
**Original provenance is not established as traceable to a recoverable artifact; this inability is recorded here.** This condition prevents COMPLETE certification for 5A.6R4 regardless of other outcomes.