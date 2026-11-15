# 10 — Phase 4B Implementation Plan (proposal, not implemented)

## 0. Planning basis and constraints
- **Approved existing architecture (evidence):** AJ is control plane (task lifecycle, authz decisions for AJ ops, evidence/recovery/inspection), not a replacement assistant/runtime; JARVIS and HELIX retain separate identities; Hermes is execution runtime/skills (not unrestricted authority). AJ 3F trust boundary is local-trust/non-auth by default and fail-closed where required.
- **Evidence-based recommendation:** start with **AJ↔Hermes minimal execution adapter spike** (contract-first, feature-flagged, local/controlled) before AJ↔JARVIS or AJ↔HELIX task-network integration.
- **Open architectural decisions:** canonical HELIX target (`AI_WORKSPACE/helix` vs Drive/`~/helix` vs redefined), cross-component trusted identity mechanism, JARVIS↔HELIX ownership model (internal module vs separate service), chosen Hermes interface (CLI vs gateway/ACP vs MCP-mediated path).
- **Deferred future ideas:** full multi-agent mesh, automatic cross-system memory unification, Obsidian-as-canonical-store, broad platform/channel expansion, paid/provider scaling work, Honcho installation.

**Hard constraints:** no fake auth/atomicity/exactly-once claims; preserve separate identities/ownership; no secrets exposure; free-first; incremental, testable, auditable changes; explicit approval required for destructive/architectural decisions.

## 1. Why AJ↔Hermes first (smallest safe, highest value)
| Option | Value | Risk/complexity | Readiness now | Recommendation |
|---|---|---|---|---|
| **AJ↔Hermes (execution adapter)** | High: exercises AJ core mission (governed execution + evidence) against an active runtime | Medium, containable if scoped to one interface and allowlisted skills/tools | Hermes running, AJ ports/contracts exist | **Do first** |
| AJ↔JARVIS (task submission/status) | High for user workflow, but depends on identity/UX/memory boundaries | High (ambiguous contracts, personal context coupling) | JARVIS internal APIs exist, no external contract | After 4B.1 contracts/decisions |
| AJ↔HELIX | Medium/uncertain value until canonicalized | High (target ambiguity, duplicate orchestrators) | Canonical HELIX unclear | After INT4A-001/010 decisions |
| JARVIS↔HELIX externalization | Medium | High overlap/refactor risk | Internal manager exists but ecosystem unclear | Later |

## 2. Phased plan

### Phase 4B.0 — Preconditions and design lock (no runtime integration)
**Goal:** remove ambiguity before code.
- **Scope:** confirm canonical HELIX target (INT4A-001), select Hermes integration interface (INT4A-006), define correlation schema (INT4A-004), define trust/permission envelope and fail-closed behavior (INT4A-003/011), define task semantics mapping (INT4A-005), ratify memory/data ownership boundaries (INT4A-008).
- **Deliverables:** design notes/ADR-style doc in AJ audit/docs (additive), approved interface choice, correlation schema, allowlist policy draft.
- **Acceptance criteria:** no "TBD" on chosen Hermes interface, IDs/correlation fields, timeout/cancel/idempotency semantics, or authz fail-closed rules for the spike.
- **Tests:** spec/contract test skeletons (mocked).
- **Risk gate:** if trusted identity cannot be provided, scope limited to explicit local-trust single-user mode with prominent non-authenticated labeling and no remote exposure.

### Phase 4B.1 — AJ HermesExecutionAdapter spike (feature-flagged, bounded)
**Goal:** one governed execution path from AJ to Hermes with honest evidence.
- **Prerequisites:** 4B.0 complete; Hermes runtime available; selected interface stable.
- **Scope boundaries:** implement `HermesExecutionAdapter` for AJ `ExecutionPort` behind config/feature flag; support **one narrow, low-risk capability/skill/tool class** (read-only or explicitly safe, allowlisted); map `ExecutionRequest` → Hermes invocation; capture stdout/stderr/status/artifacts/IDs as available; map to `ExecutionResult` + AJ evidence/audit records.
- **Must include:** correlation IDs (`aj_task_id`, `aj_operation_id`, `aj_attempt_id`, `hermes_session/task/run_id`), timeout, cooperative cancellation where supported (else explicit unsupported/unknown state), idempotent submission key, no secret logging, deny-by-default tool/skill allowlist.
- **Must not include:** broad skill enablement, autonomous multi-step external side effects, provider/model changes, JARVIS/HELIX wiring, memory merging, service exposure.
- **Acceptance criteria:** successful bounded execution produces verifiable evidence-linked result; unavailable/denied/timeout/failure paths fail closed and honestly; duplicate submission with same idempotency key does not create duplicate logical execution/result (within defined scope).
- **Tests:** unit tests for adapter mapping/error handling; integration tests with Hermes stub/mock and, if safe, controlled local Hermes test invocation in isolated temp context; regression of AJ execution/task suites.

### Phase 4B.2 — Reliability and safety hardening for the spike
**Goal:** prove behavior under failure, not just happy path.
- **Scope:** timeout handling, cancellation propagation semantics, process/connection failure, malformed/unexpected responses, partial output, retry policy (only if idempotent-safe), evidence completeness checks, structured error classification.
- **Acceptance criteria:** no false-complete on partial/ambiguous outcomes; retries never duplicate unsafe effects; stuck/unknown states surfaced to inspection; consistency/correlation checks pass.
- **Tests:** fault-injection/mocked failure tests, timeout/cancel tests, duplicate/idempotency tests, evidence-gap tests.

### Phase 4B.3 — Security boundary validation
**Goal:** ensure mediation is real, not nominal.
- **Scope:** enforce AJ-side allowlist and permission checks before dispatch; validate Hermes response provenance fields as untrusted input; block disallowed tools/skills; verify no bypass path from AJ integrated flow; document residual direct-Hermes-access risk (independent runtime) and mitigations.
- **Acceptance criteria:** disallowed/forged/overscoped requests denied and audited; prompt-injection-shaped outputs cannot escalate privileges; security review checklist completed.
- **Tests:** negative authorization tests, allowlist bypass tests, malformed payload tests, redaction checks.

### Phase 4B.4 — Controlled pilot and observability
**Goal:** limited real use with traceability.
- **Scope:** enable for a single operator/workflow in local trusted mode; add correlation trace/reporting (read-only) across AJ and Hermes IDs/evidence refs; runbook for unknown/stuck/partial outcomes.
- **Acceptance criteria:** operator can trace request→dispatch→execution→result/failure with evidence or explicit gaps; rollback/disable flag works instantly.
- **Tests:** end-to-end pilot checklist, rollback test, trace completeness sampling.

### Phase 4B.5 — Next integration candidates (only after 4B.4 success)
- **Option A:** AJ↔JARVIS contract adapter (task submission/status/result) using lessons from correlation/evidence/authz.
- **Option B:** Canonical HELIX integration (only after INT4A-001/010 resolved) as execution/delegation target via same contract principles.
- **Selection rule:** choose by approved ownership model, verified interface, and lowest combined security+duplication risk.

## 3. Interface/contract requirements (must hold in all 4B work)
- Versioned request/response schemas with strict validation at boundaries.
- Stable correlation: global correlation ID + mapped component-native IDs persisted in AJ evidence.
- Explicit status taxonomy: accepted/running/completed/failed/cancelled/rejected/timeout/unknown (mapped, never guessed).
- Idempotent submission keys for retryable requests; dedup before side effects.
- Timeouts at every hop; cancellation best-effort with truthful terminal/unknown states.
- Evidence-gated completion (no success without required evidence/result mapping).
- Append-only audit of authorization, dispatch, progress checkpoints, and outcomes.
- Feature flags and kill switches for every new integration path.

## 4. Security and trust requirements
- Fail closed on missing/invalid authz, unknown tool/skill, schema mismatch, or ambiguous outcome.
- Do not treat caller-supplied identity, local-trust assumptions, or shared host access as strong authentication.
- Minimize privileges: smallest Hermes profile/tool/skill allowlist, no credential broadening.
- Redact secrets/PII from logs/evidence/prompts per policy; preserve provenance.
- Treat runtime outputs (including Hermes/tool results) as untrusted data, not instructions.

## 5. Test and acceptance matrix (Phase 4B.1–4B.4)

| Category | Minimum tests | Pass criteria |
|---|---|---|
| Contract/schema | Request/response validation, version mismatch, unknown fields/status mapping | Invalid inputs rejected; no silent coercion to success |
| Happy path | Bounded allowlisted execution end-to-end through AJ adapter | Completed with correlated evidence and correct AJ state |
| Idempotency/duplicates | Same submission key retried/replayed | Single logical execution/result |
| Timeout/cancel | Runtime hang, cancel request at each stage | Honest timeout/cancel/unknown; no orphan untracked success |
| Failure handling | Hermes unavailable, tool denied, runtime error, malformed output | Fail closed, classified error, evidence recorded |
| Security | Disallowed tool/skill, permission escalation attempt, injection-shaped result, secret redaction | All blocked/redacted/audited as required |
| Regression | Existing AJ task/recovery/evidence/3F suites | No regressions (exact results recorded) |

## 6. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Choosing unstable Hermes interface | 4B.0 evaluation with evidence; thin adapter layer; pin/version assumptions |
| Direct Hermes bypass outside AJ | Scope pilot, document residual risk, long-term mediation controls/host policy (decision) |
| Duplicate/unsafe side effects | Idempotency keys, effect classification, read-only/low-risk first scope |
| Canonical HELIX confusion | Block HELIX integration until INT4A-001 resolved |
| False confidence from green tests | Include fault-injection, negative security, and evidence-completeness checks; honest status taxonomy |

## 7. Proposed first implementation scope (recommended)
**"AJ HermesExecutionAdapter v0 (read-only/low-risk, local, feature-flagged)"**
- One adapter, one Hermes interface, one allowlisted capability class, full correlation/evidence mapping, timeout/cancel/idempotency, fail-closed authz/validation, and comprehensive tests.
- Success metric: a single AJ-orchestrated bounded task executed via Hermes with **end-to-end verified evidence and honest failure semantics** — nothing more.

**Implementation status:** **Not started in Phase 4A (read-only audit).** Requires explicit go-ahead and completion of 4B.0 decisions/prerequisites.