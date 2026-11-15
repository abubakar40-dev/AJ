# 07 — Contract Test Strategy

**Workstream G (Phase 4B.0).** Strategy for future adapter testing. No existing AJ tests modified. Isolated additive contract fixtures/tests may be added later (4B.1) when justified and non-mutating; **none added in 4B.0** beyond this specification (design-lock scope).

## 1. Baseline (existing, inspected)
- `AJ/tests/test_hermes_contract.py` (read-only inspected): validates `UnavailableExecutionAdapter` behavior ("NOT ATTACHED", requires GREEN SIGNAL), `execute()` refusal for unavailable ports, `ExecutionRequest` round-trip/token non-serialization, normalization of bad port returns/exceptions, unverified-result preservation, and `SkillRegistry` withholding/approval/permission-ceiling semantics with test doubles (`RecordingPort`) — **no Hermes runtime/import/start**.
- This baseline covers current execution port/contract primitives; future `HermesExecutionAdapter` requires additional boundary-specific tests.

## 2. Test design principles
- **No fake coverage:** tests must assert observable behavior against defined contracts/mocks, not self-fulfilling assumptions.
- **No live Hermes dependency for unit/contract tests:** use test doubles/fakes/fixtures for CLI runner, process results, and Hermes responses.
- **Isolation:** additive tests in dedicated files/fixtures (e.g. `tests/test_hermes_execution_adapter_contract.py`, `tests/fixtures/hermes_cli/*`) without altering existing tests.
- **Fail-closed expectations:** invalid/ambiguous inputs and outcomes must not map to success.
- **Security assertions:** redaction, allowlist denial, and untrusted-output handling verified.
- **Regression safety:** full existing AJ suites must remain green.

## 3. Required coverage matrix (future 4B.1)

| Category | Scenario | Expected behavior | Test type |
|---|---|---|---|
| Valid submission | Allowlisted `hermes.status.read`, valid v0 request, successful bounded command result | `accepted/completed` as evidenced, correlation/IDs mapped, evidence recorded, sanitized output bounded | Unit/contract integration (mocked runner) |
| Invalid contract version | Unsupported `contract_version` | `rejected` `contract_version_unsupported`, no Hermes invocation | Unit |
| Missing mandatory identifiers | Missing/empty `aj_task_id|operation_id|attempt_id|correlation_id|capability_id` | `rejected` validation failure, no invocation | Unit (parametrized) |
| Invalid capability | Unknown or not-allowlisted capability | `rejected`/denied fail-closed | Unit |
| Denied permission | AJ authorization denies / allowlist disabled | `rejected` with audited reason, no invocation | Unit |
| Malformed response/output | Non-UTF8/oversize/unexpected output, parse failure | `failed` (`response_invalid`) or `unknown` per policy, no crash, bounded evidence | Unit/fault |
| Hermes unavailable | CLI missing, nonzero dependency/start failure, command absent | `failed/rejected` (`dependency_unavailable`) honestly | Unit/integration-mocked |
| Duplicate submission | Same idempotency key / duplicate attempt scope | Deduped result or explicit rejection per policy; no duplicate logical execution | Unit |
| Lost acknowledgement/start ambiguity | Process started but result channel lost / adapter crash boundary simulated | `unknown` or `requires_manual_review`, no success claim | Fault-injection |
| Execution timeout | Command exceeds `timeout_ms` | `timeout` with evidence; resolved terminal state only if evidenced | Fault-injection (fake slow process) |
| Cancellation requested but unconfirmed | Cancel issued, termination not confirmed | `cancel_requested`/`unknown` (not `cancelled`) | Fault-injection |
| Unknown result | Ambiguous/insufficient evidence after execution | `unknown`, preserved for reconciliation/manual disposition | Unit/fault |
| Partial execution/output | Truncated/interrupted output or partial completion signal | Non-completed honest status, partiality marked | Fault-injection |
| Result retrieval failure | Evidence/result ref unavailable/corrupt | `unknown`/`failed` (`result_unavailable`) with evidence | Unit |
| Correlation mismatch | Response/mapping IDs inconsistent with request | `failed`/`requires_manual_review`, no misattribution | Unit |
| Secret redaction | Inputs/env/output containing secret-like values | Redacted in logs/evidence/returned payloads | Unit/security |
| Untrusted output handling | Output containing control/injection-like text, oversized content | Treated as data, sanitized/bounded, no privilege/escalation effect | Security |
| Restart/reconciliation behavior | Simulated restart between intent/dispatch/outcome | Durable intent/evidence consulted; honest state recovery, no invented completion | Integration/fault |

## 4. Fixtures and test doubles (additive, isolated)
- **CLI runner double:** injectable interface returning `(exit_code, stdout, stderr, started_at, finished_at, pid/handle metadata, timeout/killed flags)` deterministically.
- **Clock/ID fixtures:** deterministic `operation_id/attempt_id/correlation_id` and timestamps for assertions.
- **Allowlist/policy fixtures:** minimal enabled `hermes.status.read` entry and disabled-by-default variants.
- **Golden/snapshot payloads:** sanitized expected `HermesExecutionResponseV0` mappings for key scenarios.
- **No external dependencies:** no real Hermes process required for unit/contract suite; optional gated local smoke test only if read-only, explicitly safe, and approved.

## 5. Additive tests in 4B.0?
**None added.** Rationale: meaningful adapter tests depend on 4B.1 module boundaries, selected/verified command template, and approved interface/capability; adding speculative tests now risks false coverage or coupling to unapproved decisions. Existing `tests/test_hermes_contract.py` already provides contract-baseline coverage for current ports/specs. **Additive isolated tests are justified and planned for 4B.1** once blueprint is approved.

## 6. Limitations (honest)
- CLI-native Hermes execution/session IDs and cooperative cancellation semantics may be unavailable for v0 command; tests must assert `null/unknown` handling, not fabricated values.
- End-to-end proof against real Hermes runtime is environment-dependent and mutability-risky for many commands; v0 E2E must be restricted to approved read-only command in controlled local context.
- Cross-store atomicity and exactly-once guarantees cannot be tested as properties that do not exist; tests must verify honest detection/reporting instead.

## 7. Exit criteria for test strategy (4B.0)
- Future coverage scenarios, fixtures, isolation, and fail-closed/security expectations defined.
- No existing tests weakened/altered; no fake live tests introduced.
- Limitation documented where interface/command approval is prerequisite.

## 8. Labels
- **Evidence-based:** existing hermes contract test baseline and AJ port behavior.
- **Provisional design:** 4B.1 test matrix and fixtures.
- **Decision requiring user approval:** any optional gated live read-only smoke test in 4B.1.
