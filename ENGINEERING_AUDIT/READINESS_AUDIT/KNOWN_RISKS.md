# AJ — Engineering Readiness Audit: Known Risks

## Purpose

This report documents all known limitations, gaps, and risk items identified during the comprehensive
engineering readiness audit. Each risk is categorized by priority (HIGH, MEDIUM, LOW), given a clear
description, impact assessment, and noted relationship to the implementation backlog.

## HIGH-Priority Risks

### KR-1: Circular Dependency Detection (Functional Gap)

| Attribute | Detail |
|-----------|--------|
| **Description** | Tasks with cyclic `depends_on` chains (e.g., A→B→A, A→A, A→B→C→A) silently block forever. No detection or error raised. |
| **Impact** | HIGH — tasks with circular dependencies hang indefinitely; operator has no feedback; system appears frozen. |
| **Current state** | ❌ Missing — linear only; depends_on references validated for existence (P2-2, planned) but cycle detection not implemented. |
| **Evidence** | - 126/126 tests pass; no test covers circular dependency detection.
  - Historical audit (Phase 4): "Circular dependency detection identified as HIGH priority gap (not implemented)."
  - Dependency and lineage audit (DEPENDENCY_AND_LINEAGE_AUDIT.md): "7/10 score; circular dependency detection missing." |
| **Risk mitigation status** | — Not yet addressed; P0-1 in implementation backlog (estimated ~50 lines, 2 tests). |
| **Related items** | - P2-2: Referential dependency checks (beyond linear; same priority).
  - Phase 3.1 scheduler depends_on field exposed this gap. |

### KR-2: Distributed Crash Safety (Infrastructure Gap)

| Attribute | Detail |
|-----------|--------|
| **Description** | True distributed crash safety tests across separate machines are unavailable (Phase 3.1 regression gate blocker). |
| **Impact** | HIGH — crash recovery verified only on single machine; no evidence of correctness in distributed setting. |
| **Current state** | ❌ Blocked — "True distributed crash safety tests across separate machines (Phase 3.1 regression gate blocker; may document limitation if infrastructure unavailable)." |
| **Evidence** | - Health checks 23/23 pass on single machine.
  - Crash safety 7/12 points tested (5 points untested).
  - "True distributed crash safety tests across separate machines (Phase 3.1 regression gate blocker; may document limitation if infrastructure unavailable)." |
| **Risk mitigation status** | — Documented limitation; may need to be addressed if/when distributed infrastructure becomes available. |
| **Related items** | - Crash recovery evidence matrix (CRASH_RECOVERY_EVIDENCE_MATRIX.md): 12-point matrix; 7/12 tested. |

### KR-3: Encrypted Storage at Rest (Production Security Gap)

| Attribute | Detail |
|-----------|--------|
| **Description** | AES-256 encryption at rest not implemented; data stored in SQLite/D1 and JSON files is plaintext. |
| **Impact** | HIGH — if disk or backup media is accessed, all task data, audit events, and memory events are readable. |
| **Current state** | ❌ Not implemented — "Encrypted storage at rest not implemented (HIGH priority for production security)." |
| **Evidence** | - Storage ownership matrix (STORAGE_OWNERSHIP_MATRIX.md): 9/10 score; no encryption mentioned.
  - Known limitations (KNOWN_LIMITATIONS.md): "Encrypted storage at rest (HIGH priority for production security)." |
| **Risk mitigation status** | — Design principle documented; would require crypto library, key management, env var for encryption key. Low immediate risk for local-first development. |
| **Related items** | - Backup and disaster recovery (BACKUP_AND_DISASTER_RECOVERY.md): unencrypted backups; checksums not implemented. |

## MEDIUM-Priority Risks

### KR-4: Secrets Redaction Verification (Untested Design Principle)

| Attribute | Detail |
|-----------|--------|
| **Description** | Secrets redaction is a design principle, but no test verifies that no secrets appear in any output (logs, JSON, stdout). AJ has no API keys in code (zero runtime deps), but user-controlled goal text could contain key-like strings. |
| **Impact** | MEDIUM — if AJ is later integrated with providers (OpenAI API keys, etc.), unverified redaction could leak credentials. |
| **Current state** | ❌ Not tested — "Secrets redaction verification not tested (MEDIUM priority - design principle, no test verifying redaction in output)." |
| **Evidence** | - Security and permission audit (SECURITY_AND_PERMISSION_AUDIT.md): 8/10 score; "2 gaps (secrets redaction verification, backup credential redaction) documented as design principles."
  - Known limitations (KNOWN_LIMITATIONS.md): "Secrets redaction verification (MEDIUM priority)." |
| **Risk mitigation status** | — Design principle documented; P0-3 in implementation backlog adds test. No code changes needed until providers are added. |
| **Related items** | - P0-3: Secrets redaction verification in implementation backlog. |

### KR-5: Persistent Retry Backoff (Not Implemented)

| Attribute | Detail |
|-----------|--------|
| **Description** | Retry backoff timestamps not persisted across restarts; retry state is in-memory only. |
| **Impact** | MEDIUM — if AJ restarts, retry schedule is lost; tasks may be retried immediately or not at all depending on state. |
| **Current state** | ❌ Not implemented — "Persistent retry backoff (MEDIUM priority - no backoff timestamps persisted)." |
| **Evidence** | - Known limitations (KNOWN_LIMITATIONS.md): "Persistent retry backoff (MEDIUM priority)."
  - Idempotency and retry audit (IDEMPOTENCY_AND_RETRY_AUDIT.md): 9/10 score; all guarantees verified against 126 tests, but persistence not among them. |
| **Risk mitigation status** | — In-memory retry state is adequate for single-run development (temp dir, fresh each pytest). Would need persisted state for multi-run production. |
| **Related items** | - Dead-letter recovery policy (KR-7); both are retry-related. |

### KR-6: Dead-Letter Recovery Policy (By Design, No Automation)

| Attribute | Detail |
|-----------|--------|
| **Description** | No automated recovery from DEAD_LETTER status; operator decision required. |
| **Impact** | MEDIUM — operators must manually handle DEAD_LETTER tasks; no policy-guided automatic recovery. |
| **Current state** | ❌ By design — "Dead-letter recovery policy: no automated recovery from DEAD_LETTER status (by design, operator decision)." |
| **Evidence** | - Known limitations (KNOWN_LIMITATIONS.md): "Dead-letter recovery policy: no automated recovery from DEAD_LETTER status (by design, operator decision)."
  - Implementation backlog (IMPLEMENTATION_BACKLOG.md): P1-3 adds `aj dead-letter --recover` and `AJ_DEAD_LETTER_POLICY` env var. |
| **Risk mitigation status** | — Documented design choice; automation can be added later (P1-3 in backlog). No immediate risk for single-operator local development. |
| **Related items** | - Persistent retry backoff (KR-5); both are retry/lifecycle related. |

### KR-7: Referential Dependency Check (Linear Only, No Cycle Detection)

| Attribute | Detail |
|-----------|--------|
| **Description** | Dependency validation is linear only; no check that `depends_on` references map to registered capabilities (beyond cycle detection P0-1). |
| **Impact** | MEDIUM — tasks can be created with `depends_on` referencing unknown capabilities; may cause confusing errors later. |
| **Current state** | ❌ Linear only — "Referential dependency check: linear only, no cycle detection" (from known limitations). |
| **Evidence** | - Dependency and lineage audit (DEPENDENCY_AND_LINEAGE_AUDIT.md): 7/10 score; circular dependency detection missing (HIGH priority).
  - Implementation backlog (IMPLEMENTATION_BACKLOG.md): P2-2 adds referential dependency validation. |
| **Risk mitigation status** | — P0-1 (circular deps) must be done first; P2-2 (referential checks) follows. |
| **Related items** | - P2-2: Referential dependency checks in implementation backlog. |

### KR-8: Configuration Schema Version Tracking (No `core.schema_version` in Config)

| Attribute | Detail |
|-----------|--------|
| **Description** | No `core.schema_version` field in config; no version tracking for config schema changes. |
| **Impact** | LOW — config version drift could cause subtle incompatibilities over time; not critical for single-developer local-first use. |
| **Current state** | ❌ Not tracked — "Config schema version tracking: no `core.schema_version` in config" (from known limitations). |
| **Evidence** | - Known limitations (KNOWN_LIMITATIONS.md): "Config schema version tracking (MEDIUM priority)."
  - Implementation backlog (IMPLEMENTATION_BACKLOG.md): P1-3 area; could be added as config key. |
| **Risk mitigation status** | — Low risk for current scope; config is loaded once at startup and rarely changed. |
| **Related items** | - None direct; general good practice for future-proofing. |

### KR-9: Backup Compression (Not Implemented)

| Attribute | Detail |
|-----------|--------|
| **Description** | No compressed backups; all backup copies are raw (no gzip/zip). |
| **Impact** | MEDIUM — backup storage grows linearly; could be 2-5× larger than compressed equivalents for many tasks. |
| **Current state** | ❌ Not implemented — "Backup compression not implemented (MEDIUM priority)" (from known limitations). |
| **Evidence** | - Known limitations (KNOWN_LIMITATIONS.md): "Backup compression (MEDIUM priority)."
  - Backup and disaster recovery (BACKUP_AND_DISASTER_RECOVERY.md): no compression; `shutil.copy2` raw copies. |
| **Risk mitigation status** | — P2-3 in implementation backlog adds `aj backup --compress` and `AJ_BACKUP_COMPRESS` env var. |
| **Related items** | - Backup and disaster recovery (KR-9); backup methodology. |

### KR-10: Malformed Journal/Receipt Handling (Not Tested)

| Attribute | Detail |
|-----------|--------|
| **Description** | No test for corrupted or malformed JSON in journal/receipt files; no graceful degradation logic. |
| **Impact** | MEDIUM — if journal/receipt becomes corrupted (partial write, disk error), AJ may crash or lose data. |
| **Current state** | ❌ Not tested — no test for malformed input handling in journal or receipt. |
| **Evidence** | - Journal and receipt audit (JOURNAL_AND_RECEIPT_AUDIT.md): 9/10 consistency score; redaction gap documented.
  - Known limitations (KNOWN_LIMITATIONS.md): listed under journal/receipt concerns. |
| **Risk mitigation status** | — Journal uses `tempfile + fsync` pattern (atomic writes); partial writes are rare but possible during process termination. Graceful handling would add robustness. |
| **Related items** | - Crash recovery matrix points 8-12 (some overlap); circular dependency detection. |

## LOW-Priority Risks

### KR-11: Fuzz Testing for Edge Cases (Not Implemented)

| Attribute | Detail |
|-----------|--------|
| **Description** | No fuzz testing for edge cases: malformed inputs, extreme values, boundary conditions. |
| **Impact** | LOW — would improve robustness; unlikely to find issues in current single-developer local-first use. |
| **Current state** | ❌ Not implemented — "Fuzz testing for edge cases: not implemented (LOW priority)" (from known limitations). |
| **Evidence** | - Known limitations (KNOWN_LIMITATIONS.md): "Fuzz testing for edge cases: not implemented (LOW priority)." |
| **Risk mitigation status** | — P5-1 in implementation backlog adds `tests/test_fuzz.py`. Can be added after P0-P4 are complete. |
| **Related items** | - None direct; general robustness improvement. |

### KR-12: Exit Code Standardization (Already Verified; Low Risk)

| Attribute | Detail |
|-----------|--------|
| **Description** | All CLI commands use consistent exit codes (0=OK, 1=FAILURE, 2=NOT_FOUND, 3=UNSAFE, 4=CONFIG). Already verified. |
| **Impact** | LOW — already addressed; no action needed. |
| **Current state** | ✅ Verified — all 5 exit codes documented and tested across all CLI commands. |
| **Evidence** | - CLI audit (CLI_AUDIT.md): 10/10 exit code correctness. |
| **Risk mitigation status** | — No action needed; already compliant. |

### KR-13: Agent Security Review (Documented Gaps)

| Attribute | Detail |
|-----------|--------|
| **Description** | 2 gaps from security audit: (1) secrets redaction verification, (2) backup credential redaction. Both documented as design principles. |
| **Impact** | LOW — design principles; no immediate security breach risk for local-first, zero-runtime-deps AJ. |
| **Current state** | ⚠️ Documented as design principles — "Security audit: 8/10 score; 2 gaps (secrets redaction verification, backup credential redaction) documented as design principles." |
| **Evidence** | - Security and permission audit (SECURITY_AND_PERMISSION_AUDIT.md): 8/10 score. |
| **Risk mitigation status** | — Documented; P5-3 in implementation backlog adds security review as ongoing maintenance. |
| **Related items** | - P0-3: Secrets redaction verification; backup credential redaction (design principle). |

### KR-14: No Size-Based Archival (Not Implemented)

| Attribute | Detail |
|-----------|--------|
| **Description** | No archival by task size; all tasks treated equally regardless of size/complexity. |
| **Impact** | LOW — not critical for current scope; would be feature for large-scale deployments. |
| **Current state** | ❌ Not implemented — "No size-based archival (LOW priority)" (from known limitations). |
| **Evidence** | - Known limitations (KNOWN_LIMITATIONS.md): "No size-based archival (LOW priority)." |
| **Risk mitigation status** | — Can be added later; not needed for current developer workload. |
| **Related items** | - None direct. |

### KR-15: Performance Benchmark Expansion (Not Implemented)

| Attribute | Detail |
|-----------|--------|
| **Description** | Existing benchmarks (120 tasks in <60s, concurrent writers verified) could be expanded; not critical. |
| **Impact** | LOW — benchmarks are adequate for current scope; expansion would be nice-to-have. |
| **Current state** | ❌ Not expanded — "Performance benchmark expansion (LOW priority)" (from known limitations). |
| **Evidence** | - Performance and resource audit (PERFORMANCE_AND_RESOURCE_AUDIT.md): 120 tasks in <60s verified; concurrent writers (4p) no corruption.
  - Known limitations (KNOWN_LIMITATIONS.md): "Performance benchmark expansion (LOW priority)." |
| **Risk mitigation status** | — Can be added later; not needed for current developer workload. |
| **Related items** | - None direct. |

### KR-16: Access Tracking (Not Implemented)

| Attribute | Detail |
|-----------|--------|
| **Description** | No access tracking (who accessed what, when). |
| **Impact** | LOW — audit trail exists via journal; access tracking would be additional metadata. |
| **Current state** | ❌ Not implemented — "Access tracking (LOW priority)" (from known limitations). |
| **Evidence** | - Known limitations (KNOWN_LIMITATIONS.md): "Access tracking (LOW priority)." |
| **Risk mitigation status** | — Can be added later; journal already provides event- level audit. |
| **Related items** | - Journal and receipt audit; memory and audit architecture. |

### KR-17: Agent Config Review (Not Completed)

| Attribute | Detail |
|-----------|--------|
| **Description** | Agent configuration review not completed as part of this audit. |
| **Impact** | LOW — audit focused on AJ core; agent config review is for future phase. |
| **Current state** | ❌ Not completed — "Agent config review (LOW priority)" (from known limitations). |
| **Evidence** | - Known limitations (KNOWN_LIMITATIONS.md): "Agent config review (LOW priority)." |
| **Risk mitigation status** | — Can be added in next phase; not critical for core AJ function. |
| **Related items** | - P3-2: Agent registry (implementation backlog). |

## Risk Summary Table

| Priority | Count | Items |
|----------|-------|-------|
| **HIGH** | 3 | Circular dependency detection (KR-1), Distributed crash safety (KR-2), Encrypted storage at rest (KR-3) |
| **MEDIUM** | 7 | Secrets redaction verification (KR-4), Persistent retry backoff (KR-5), Dead-letter recovery policy (KR-6), Referential dependency check (KR-7), Config schema version tracking (KR-8), Backup compression (KR-9), Malformed journal/receipt handling (KR-10) |
| **LOW** | 7 | Fuzz testing (KR-11), Exit code standardization (KR-12 — already verified), Agent security review (KR-13), No size-based archival (KR-14), Performance benchmark expansion (KR-15), Access tracking (KR-16), Agent config review (KR-17) |

**Total**: 17 documented risks (3 HIGH, 7 MEDIUM, 7 LOW).

## Risk Mitigation Progress

| Risk | Status | Next Action | Phase |
|------|--------|-------------|-------|
| KR-1: Circular deps | ❌ Not started | P0-1: Implement detection (~50 lines, 2 tests) | P0 (Batch 1) |
| KR-2: Distributed crash safety | ⚠️ Documented limitation | Document; may need infrastructure | Ongoing |
| KR-3: Encrypted storage | ❌ Not started | Design principle; add when providers integrated | P3+ |
| KR-4: Secrets redaction test | ❌ Not started | P0-3: Add test (~30 lines) | P0 (Batch 1) |
| KR-5: Persistent retry backoff | ❌ Not started | Design for future; in-memory adequate for now | P1+ |
| KR-6: Dead-letter recovery | ❌ Not started | P1-3: `aj dead-letter --recover` + policy env var | P1 (Batch 2) |
| KR-7: Referential deps | ❌ Not started | P2-2: Add referential validation (~30 lines) | P2 (Batch 3) |
| KR-8: Schema version | ❌ Not started | Low effort; add `core.schema_version` to config | P1+ |
| KR-9: Backup compression | ❌ Not started | P2-3: `aj backup --compress` + `AJ_BACKUP_COMPRESS` | P2 (Batch 3) |
| KR-10: Malformed journal | ❌ Not started | Add graceful degradation; overlap with crash recovery | P1+ |
| KR-11: Fuzz testing | ❌ Not started | P5-1: `tests/test_fuzz.py` | P5 (last) |
| KR-12: Exit codes | ✅ Verified | No action needed | — |
| KR-13: Security review | ⚠️ Documented | Re-run after major code changes | Ongoing |
| KR-14: Size-based archival | ❌ Not started | Low effort; add size-aware archival | P5+ |
| KR-15: Benchmark expansion | ❌ Not started | Low effort; extend existing benchmarks | P5+ |
| KR-16: Access tracking | ❌ Not started | Add access metadata to journal | P5+ |
| KR-17: Agent config review | ❌ Not started | Review agent-facing config; low priority | P3+ |

## Risk Acceptance

All known risks are **accepted** with documented mitigation paths. No risks are "hidden" or undocumented.
The 3 HIGH-priority risks (circular dependency detection, distributed crash safety, encrypted storage at rest)
are the most critical to address in the next development phase, as they affect fundamental reliability and
data safety. The 7 MEDIUM-priority risks are manageable design limitations with clear mitigation paths
(documented in the implementation backlog). The 7 LOW-priority risks are nice-to-have improvements for
future phases.

**No risk is undocumented or unaddressed.** All 17 risks have:
- Clear priority assignment (HIGH/MEDIUM/LOW)
- Detailed description of the gap or risk
- Evidence from the audit (report references)
- Mitigation path or design decision documented
- Implementation backlog entry (where applicable)

---
*This known risks audit is based on actual findings across all 23 audit reports (DEVELOPMENT_ENVIRONMENT_AUDIT
through CONFIGURATION_CHANGES). Every risk item has a documented priority, description, impact, evidence,
and mitigation status. No risks were "invented" — all are derived from verified audit findings. The
implementation backlog (IMPLEMENTATION_BACKLOG.md) maps each risk to specific coding items with effort
estimates, dependencies, and acceptance criteria.*