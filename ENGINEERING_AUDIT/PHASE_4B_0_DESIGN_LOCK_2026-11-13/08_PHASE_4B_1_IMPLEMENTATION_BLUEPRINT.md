# 08 — Phase 4B.1 Implementation Blueprint (Future, Not Implemented)

**Workstream H (Phase 4B.0).** Exact, bounded implementation plan for the future minimal Hermes adapter. **No live adapter implemented in 4B.0.**

## 1. Scope and objective
- **Objective:** implement a minimal, feature-flagged, default-disabled, deny-by-default `HermesExecutionAdapter` (CLI boundary) supporting **one** narrow read-only capability `hermes.status.read`, with full correlation/evidence mapping, timeout/error handling, and honest status semantics.
- **In scope:** AJ-side adapter, config/allowlist wiring, validation/authorization integration, evidence/audit recording, unit/contract/fault/security/regression tests, docs/runbook notes.
- **Out of scope:** mutating/side-effecting capabilities, tool/skill/MCP execution, messaging/browser/account actions, JARVIS/HELIX wiring, memory migration, service/runtime reconfiguration, repo consolidation, remote exposure, authenticated identity provider.

## 2. Selected interface and first capability
| Item | Value | Status |
|---|---|---|
| Interface | Hermes CLI subprocess (argv-array, no shell), mediated by AJ `ExecutionPort` | **Evidence-based recommendation; requires user approval** |
| Contract | `aj.hermes.execution.v0` (`03`) | Provisional spec |
| First capability | `hermes.status.read` (read-only runtime/gateway status probe) | **Evidence-based recommendation; requires user approval + command verification** |
| Exact command mapping | **TBD at 4B.1 preflight:** select verified read-only Hermes CLI command/args with no mutation, bounded output, stable exit semantics (candidate class: status/introspection; must be proven safe) | **Blocked until verified** |

## 3. Exact AJ modules to modify / create (proposed)

| Path | Change | Purpose |
|---|---|---|
| `aj/execution.py` | Modify | Add/compose `HermesExecutionAdapter` implementing `ExecutionPort` (CLI runner injection, availability/describe, execute mapping to `ExecutionResult`/v0 response evidence); keep `UnavailableExecutionAdapter` as default/fallback |
| `aj/contracts.py` | Modify (additive-compatible) | Add/align fields/helpers for `contract_version`, `operation_id/attempt_id/correlation_id/idempotency_key`, Hermes execution ID mapping, extended honest statuses if required (`accepted/cancel_requested/cancelled/unknown/requires_manual_review` mapping strategy) while preserving existing contract behavior |
| `aj/runtime.py` | Modify | Assemble Hermes adapter only when explicitly enabled/configured and safe; default remains unavailable/not attached; feature-flag gating |
| `aj/config.py` and/or config loading path (exact hook to confirm at implementation) | Modify | Typed config for `execution.runtime`, `execution.hermes.*`, allowlist path/inline policy, timeout/output bounds, CLI path/profile/home overrides (sanitized) |
| `config/aj.config.json` (or documented local override mechanism; prefer non-secret local override) | Modify/additive | Default-disabled settings (`runtime: "none"` or explicit `hermes_cli` disabled), feature flag remains false until approved enablement |
| `aj/capability.py` / capability declarations (`config/capabilities.json` and/or loader) | Modify/additive | Register `hermes.status.read` as declared capability with risk/availability/verification metadata, disabled/unavailable by default |
| `aj/diagnostics.py` / status surfaces (if applicable) | Modify (minimal) | Expose adapter attachment/availability/allowlist state truthfully (no "attached" unless real) |
| `aj/hermes_adapter.py` (or `aj/execution_hermes.py`) | **Create** | CLI runner abstraction, argv template validation, subprocess execution with timeout/capture, output normalization/redaction, ID/evidence mapping, error classification |
| `aj/hermes_contract.py` (optional) | **Create** | v0 request/response schema validation and status mapping helpers (pure, testable) |
| `tests/test_hermes_execution_adapter.py` (new, isolated) | **Create** | Unit tests with mocked runner |
| `tests/test_hermes_execution_contract_v0.py` (new, isolated) | **Create** | Contract/schema/status mapping tests |
| `tests/test_hermes_execution_security.py` (new, isolated) | **Create** | Allowlist/permission/redaction/untrusted-output tests |
| `tests/test_hermes_execution_faults.py` (new, isolated) | **Create** | Timeout/cancel/lost/partial/malformed/unknown/restart-reconcile simulations |
| `tests/fixtures/hermes_cli/*` (new, isolated) | **Create** | Deterministic fake command outputs/exit cases |
| `docs/*` (AJ integration doc) | Create/update (additive) | Operator/runbook: enablement prerequisites, boundaries, disabled capabilities, rollback |

**Constraint:** do not modify existing tests; do not alter JARVIS/HELIX/Hermes app code.

## 4. Module boundaries
- **AJ orchestrator/task/authorization layers:** remain owners of validation, authz, intent/evidence/task state; call `ExecutionPort` only.
- **`HermesExecutionAdapter`:** sole Hermes-specific integration point (command mapping, process invocation, normalization). No Hermes imports/internals leakage.
- **CLI runner interface:** injectable for tests (`run(argv, env, cwd, timeout)->result`).
- **Contract validators/mappers:** pure functions/dataclasses, no side effects.

## 5. Configuration and feature flag
- `feature_flags.hermes_skills` (or dedicated `feature_flags.hermes_execution_adapter`) default **false**.
- `execution.runtime`: default `"none"`; `"hermes_cli"` only when explicitly configured + flag enabled + preflight checks pass.
- `execution.hermes.cli_path` (optional, validated), `execution.hermes.profile/home` (if needed), `execution.hermes.default_timeout_ms`, `execution.hermes.output_max_bytes`, `execution.hermes.allowlist` (capability->template mapping) with **only `hermes.status.read` eligible**.
- **Default-disabled behavior:** if not fully enabled/approved/configured, `UnavailableExecutionAdapter` semantics preserved and status reported as not attached/disabled.

## 6. Permission/allowlist implementation
- Pre-dispatch checks (all required): contract version valid, capability in allowlist and enabled, AJ authorization `allow`, input schema valid, bounds valid, idempotency/retry policy satisfied.
- Fixed argv templates only; reject non-allowlisted args/env/cwd overrides from request.
- Deny with audited reason on any failure (fail closed).

## 7. Correlation mapping and durable evidence flow
- Generate/persist AJ `operation_id`, `attempt_id`, `correlation_id` (and link `aj_task_id`) in intent record before invocation.
- Persist submission, start/ack observation, outcome, and normalized response with nullable Hermes IDs.
- Store bounded stdout/stderr refs/digests (redacted), exit/timeout/cancel evidence, classification, and status rationale.
- On ambiguity, persist `unknown`/`requires_manual_review` with reconciliation-needed marker.

## 8. Timeout, cancellation, retry/idempotency
- **Timeout:** enforce adapter timeout via process kill/termination handling; map to `timeout` then evidenced terminal/uncertain state.
- **Cancellation:** cooperative only at process boundary (terminate/kill); record `cancel_requested`; set `cancelled` only when evidenced, else `unknown`.
- **Retry/idempotency:** default no retry. For `hermes.status.read`, allow only policy-defined safe re-observation when no ambiguous prior submission exists; dedup by idempotency key/scope; never retry `unknown`.
- **No blind replay / no unsafe side-effect duplication.**

## 9. Error classification and logging/redaction
- Classes (proposed): `validation_error`, `contract_version_unsupported`, `permission_denied`, `capability_not_allowed`, `dependency_unavailable`, `spawn_failed`, `timeout`, `cancelled`, `response_invalid`, `result_unavailable`, `runtime_error`, `unknown_outcome`.
- Structured errors with sanitized messages/codes; `retryable` set conservatively (`false` or `unknown`).
- Redact secrets in argv/env/stdout/stderr/evidence; treat outputs as untrusted data.

## 10. Test plan (4B.1 execution)

| Suite | Focus | Key cases |
|---|---|---|
| Unit | Adapter/validator/mapper logic | schema validation, allowlist/denial, argv templating, normalization, ID mapping, redaction |
| Contract | `aj.hermes.execution.v0` compliance | version/id requirements, status mapping, honest unknown/null Hermes IDs |
| Integration (mocked runner) | `ExecutionPort` wiring in AJ runtime path | enabled/disabled behavior, evidence flow, correlation persistence hooks |
| Fault-injection | Failures and ambiguity | unavailable, timeout, kill/cancel race, lost ack, partial/truncated output, malformed output, restart/reconcile simulation |
| Security | Boundary enforcement | bypass attempts, non-allowlisted capability, secret leakage, untrusted/injection-shaped output handling |
| Regression | Existing AJ suites relevant to execution/tasks/authz/evidence | no regressions; `tests/test_hermes_contract.py` and 3F/3E/3D baselines preserved |

**Gated optional smoke (requires approval):** one manual/CI-gated local run of approved read-only `hermes.status.read` command in controlled environment to confirm real CLI behavior; must be non-mutating and skippable by default.

## 11. Rollback procedure
- Immediate: set feature flag false / `execution.runtime="none"` → revert to `UnavailableExecutionAdapter` (no code rollback required).
- Code rollback: remove `HermesExecutionAdapter` wiring and keep port unavailable; preserve additive evidence records (append-only) for auditability.
- No data migration; no irreversible state changes expected for read-only v0.

## 12. Acceptance criteria (4B.1)
1. Adapter is **default-disabled** and fail-closed; enabling requires explicit config/flag and preflight pass.
2. Only `hermes.status.read` (verified read-only command) is allowlisted/executable.
3. Valid request produces evidenced, correlated, bounded result with honest status; Hermes IDs null when not exposed.
4. Invalid/denied/unavailable/timeout/malformed/ambiguous cases produce correct non-success statuses and evidence (no false completion/cancellation).
5. No duplicate logical execution for deduped idempotent-safe cases per policy; no unsafe retries.
6. Secrets redacted; outputs treated as untrusted; no privilege escalation.
7. Existing AJ tests unmodified and regression suites pass (results recorded).
8. Exact command mapping and live behavior verified and documented before enablement.

## 13. Labels
- **Evidence-based recommendation:** CLI boundary, read-only first capability, `ExecutionPort` adapter pattern.
- **Provisional design:** module names, config keys, error classes (to be finalized against current codebase conventions at implementation).
- **Decision requiring user approval:** interface/capability/command approval, identity scope, enablement.
- **Deferred idea:** ACP/gateway RPC adapter, broader capabilities, JARIS/HELIX integration.
