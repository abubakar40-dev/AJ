# 03 — Contract and Status Mapping

## Contract: `aj.hermes.execution.v0` (implemented subset)
- **Capability:** `hermes.status.read` only (deny-by-default allowlist). Any other capability => `rejected` (`capability_not_allowed`).
- **Command mapping (fixed, verified):** `<resolved-hermes-cli> gateway status` (no `--deep/--full`, no user-controlled args, no shell).
- **Request validation (fail closed):** required `contract_version == aj.hermes.execution.v0`; non-empty `aj_task_id/operation_id/attempt_id/correlation_id/capability_id`; `input` must be empty `{}`; `timeout_ms` int in (0, max_timeout_ms]; `permission_context` object with `authorizer=="AJ"`, `authorization_decision=="allow"`, `trust_mode=="local_trust"`; `idempotency_key` string if present. Invalid/missing/unsupported => `rejected` with sanitized error.
- **Identity:** explicit `local_trust` (non-authenticated local assumption). Caller-supplied authority not trusted; AJ-derived context required by envelope validation and AJ orchestration authorization.
- **IDs:** AJ IDs echoed; `hermes_execution_id` always `null` for this CLI probe (never fabricated).

## v0 response envelope (adapter output)
Fields: `contract_version, aj_task_id, operation_id, attempt_id, correlation_id, capability_id, hermes_execution_id, accepted, status, result_ref, result_payload, error, timestamps, evidence, provenance`.
- `evidence`: argv template `["<hermes>","gateway","status"]`, `exit_code`, `timed_out`, truncation flags, bounded char counts (no raw secrets).
- `provenance`: `adapter_id=hermes_cli`, `adapter_version=v0`, `hermes_interface=cli`, `trust_mode=local_trust`.
- `result_payload` (on completion/failure/timeout when available): bounded redacted `stdout`, `stderr`, probe metadata/partial flag; treated as untrusted diagnostic text.

## Status mapping (honest)

| Condition | `ExecutionResult.status` | v0 `status` | accepted | notes |
|---|---|---|---:|---|
| Adapter/feature/capability disabled | exception `ExecutionUnavailable` (port unavailable) | n/a | n/a | default path; fail closed |
| Contract/allowlist/authz/input invalid | `rejected` | `rejected` | false | no subprocess spawned |
| CLI missing/unresolvable/invalid path | `failed` | `failed` | false | `dependency_unavailable` |
| Spawn failed (not started) | `failed` | `failed` | false | `spawn_failed` |
| Started but timed out (bounded) | `timeout` | `timeout` | true | partial bounded output preserved; never success |
| Started, exit code 0 | `completed` | `completed` | true | read-only probe completed; `verified=True` (process_exit_zero), output still untrusted text |
| Started, non-zero exit | `failed` | `failed` | true | runtime/command error evidenced |
| Ambiguous/unhandled cases | n/a (mapped conservatively) | `unknown`/`requires_manual_review` supported by vocabulary/helpers | varies | never mapped to `completed` |

## Not claimed
- No native Hermes execution/session/run IDs for this command (null).
- No cooperative Hermes cancellation semantics beyond local process timeout handling.
- No exactly-once/external-effect guarantees; read-only probe only.
- No structured/stable semantic parsing guarantee of Hermes status text.