# 03 — AJ↔Hermes Versioned Contract (Specification)

**Workstream C (Phase 4B.0).** Provisional design specification for future adapter implementation. No live adapter implemented. All fields/behaviors are contract targets; adapter must not claim values Hermes/AJ cannot evidence.

## 1. Contract identity and versioning
- **Contract name:** `aj.hermes.execution`
- **`contract_version`:** `aj.hermes.execution.v0` (string, required in all requests/responses crossing the AJ↔Hermes adapter boundary)
- **Compatibility rule:** adapter rejects unknown/unsupported major contract versions with `rejected`/`failed` classification `contract_version_unsupported` (fail closed). Minor additive evolution must be backward-compatible and explicitly versioned in future revisions.
- **Transport (preferred, per `02`):** bounded Hermes CLI subprocess invocation mediated by AJ `ExecutionPort` implementation; this contract defines logical payload/evidence mapping, not a claim that Hermes natively speaks this schema.

## 2. Submission request schema (`HermesExecutionRequestV0`)

| Field | Required | Source/validation | Description |
|---|---:|---|---|
| `contract_version` | Yes | Caller/adapter must equal `aj.hermes.execution.v0` | Contract version guard |
| `aj_task_id` | Yes | AJ-controlled, non-empty stable ID | Owning AJ task |
| `operation_id` | Yes | AJ-controlled, non-empty (idempotency/audit scope) | AJ operation/evidence chain |
| `attempt_id` | Yes | AJ-controlled, non-empty unique per attempt | Dispatch attempt under operation |
| `correlation_id` | Yes | AJ-controlled, globally traceable string | Cross-component correlation key |
| `capability_id` | Yes | Must match AJ allowlist entry and capability policy | AJ-facing bounded capability (v0: `hermes.status.read`) |
| `input` | Yes | Strict schema per capability; size/shape bounded; no secrets in cleartext fields beyond necessity | Capability input payload (v0: `{}` or tightly defined read-only params) |
| `timeout_ms` | Yes | Integer > 0 and <= configured max (v0 cap defined in config/policy) | End-to-end adapter timeout |
| `permission_context` | Yes | AJ-derived, validated object (see §2.1); **never trusted as caller authority grant** | AJ authorization/evidence context snapshot |
| `idempotency_key` | Conditional | Required when capability/retry policy allows retry or dedup; must be deterministic for same logical request scope as defined | Duplicate-submission prevention key |
| `dry_run` | No | Default `false`; if true must be explicitly supported by capability/adapter else reject | Non-executing validation where supported |
| `requested_at` | No | Adapter may set if absent (AJ clock) | Submission intent timestamp |
| `metadata` | No | Strict allowlisted keys only, redacted | Non-authoritative trace metadata |

### 2.1 `permission_context` (AJ-derived, fail-closed)
Required subfields (AJ-generated): `authorizer` (`"AJ"`), `authorization_decision` (`allow|deny|unknown` + reason code), `decision_scope` (capability/operation/attempt), `trust_mode` (`local_trust` for v0), `principal_provenance` (provenance labels; may be non-authenticated), `policy_snapshot_id/hash` (if available), `allowlist_entry_id`.
**Rules:** caller-supplied authorization decisions/roles/tokens are **not trusted facts**; AJ recomputes/validates authorization before submission. Missing/invalid context => `rejected`.

### 2.2 Validation (reject before side effects)
- Schema/type/range/required fields, contract version, capability allowlist, permission decision `allow`, input schema/size, timeout bounds, idempotency key format when required.
- Redact secrets from any persisted/logged request representation.

## 3. Execution response schema (`HermesExecutionResponseV0`)

| Field | Required | Description |
|---|---:|---|
| `contract_version` | Yes | `aj.hermes.execution.v0` |
| `aj_task_id`, `operation_id`, `attempt_id`, `correlation_id` | Yes | Echoed correlation mapping |
| `capability_id` | Yes | Echoed capability |
| `hermes_execution_id` | Conditional | Hermes-native execution/session/run/task/admission ID **only if evidenced**; else `null` with reason |
| `accepted` | Yes | Whether Hermes/runtime boundary accepted the invocation request |
| `status` | Yes | One of status model (§4) |
| `result_ref` | Conditional | Reference to bounded stored artifact/evidence payload if not inline (preferred for large outputs) |
| `result_payload` | Conditional | Bounded, sanitized inline payload (v0 status probe: small structured/normalized text fields) |
| `error` | Conditional | Structured error object when not completed: `class`, `code`, `message` (sanitized), `retryable` (bool/`unknown`), `source` (`aj|adapter|hermes|transport|timeout`) |
| `timestamps` | Yes | `requested_at`, `accepted_at?`, `started_at?`, `finished_at?`, `observed_at` (known values only) |
| `evidence` | Yes | Provenance/evidence bundle (argv template id/hash, exit code, stdout/stderr refs or bounded digests, runtime identity hints, non-secret) |
| `provenance` | Yes | `adapter_id`, `adapter_version`, `hermes_interface` (`cli`), `hermes_home`/profile labels if known, `trust_mode` |

**Rule:** unavailable/ambiguous outcomes must never be represented as `completed`.

## 4. Status model and honest mapping

| Status | Meaning | Allowed evidence conditions |
|---|---|---|
| `submitted` | AJ prepared and handed request to adapter boundary | Intent recorded; outbound attempt started |
| `accepted` | Hermes/runtime acknowledged invocation accepted | Explicit acceptance signal or process successfully started as defined for capability |
| `running` | Execution in progress | Observed active process/stream/session |
| `completed` | Bounded capability completed successfully with required evidence | Exit/success criteria satisfied and result/evidence captured |
| `failed` | Execution attempted and definitively failed | Evidenced non-success (exit/error/validation of response) |
| `rejected` | Rejected before/at acceptance (policy/validation/contract/permission/capability) | Precondition or explicit rejection evidenced |
| `cancel_requested` | AJ requested cancellation | Request sent/kill issued as applicable; **not terminal success** |
| `cancelled` | Cancellation confirmed/evidenced | Runtime/process confirmed terminated/cancelled per boundary semantics |
| `timeout` | Adapter/operation timeout reached | Timeout condition evidenced; terminality only if stop/unknown handling resolved per policy |
| `unknown` | Outcome cannot be determined honestly | Lost ack/response, ambiguous termination, crash boundary, or insufficient evidence |
| `requires_manual_review` | Ambiguous/partial state needing operator disposition | Conflicting evidence, possible side effects, or reconciliation cannot prove outcome |

**Prohibitions:** do not map unavailable/ambiguous Hermes result to `completed`; do not claim `cancelled` merely because AJ sent cancellation request.

## 5. Identifier mapping

| ID | Owner | Required | Notes |
|---|---|---:|---|
| `aj_task_id` | AJ | Yes | Task lifecycle correlation |
| `operation_id` | AJ | Yes | Privileged/controlled operation evidence scope |
| `attempt_id` | AJ | Yes | Per-dispatch attempt |
| `correlation_id` | AJ | Yes | Global trace key across components |
| `idempotency_key` | AJ caller/adapter policy | Conditional | Dedup key; scope defined per capability |
| `hermes_execution_id` | Hermes (if available) | Conditional | CLI may not expose a stable ID for read-only status commands; **null allowed** |
| `hermes_session_id` | Hermes | Conditional | Only if session-based interface/command used and evidenced |
| `hermes_run_id` / task/admission IDs | Hermes | Conditional | Not assumed for CLI v0; populate only when verified |

**Rule:** never invent Hermes identifiers. Missing IDs must be represented as `null`/absent with `unknown`/`not_exposed` evidence note.

## 6. Failure semantics

| Condition | Expected status | Retry/idempotency | Notes |
|---|---|---|---|
| Hermes unavailable / command not found / gateway dependency unmet for command | `failed` or `rejected` (classified `dependency_unavailable`) | Retryable only if read-only and explicitly safe; default conservative | No success claim |
| Connection/IPC/transport timeout (if applicable) or process start failure | `failed`/`timeout`/`unknown` as evidenced | No blind retry if submission state ambiguous | Preserve attempt evidence |
| Execution timeout | `timeout` (then `cancelled`/`unknown`/`requires_manual_review` as resolved) | No automatic retry unless idempotent-safe and approved | Capture partial output bounds |
| Malformed/unexpected response or nonconforming output | `failed` (`response_invalid`) | No retry unless idempotent-safe; may need manual review | Treat output as untrusted data |
| Lost response after successful submission/start | `unknown` or `requires_manual_review` | **No unsafe retry**; reconcile/read-only probe if safe | Never assume completion |
| Duplicate submission (same idempotency/correlation scope) | Return prior mapped result or `rejected`/`failed` duplicate per policy | Must not create duplicate logical execution for idempotent-scoped requests | AJ-side dedup required; Hermes-side not assumed in CLI v0 |
| Partial execution/output | `failed`/`timeout`/`unknown`/`requires_manual_review` | No unsafe retry | Evidence must mark partiality |
| Cancellation race | `cancel_requested` → `cancelled`/`completed`/`failed`/`unknown` based on evidence | N/A | Terminal state must be evidenced |
| Result retrieval failure (artifact/ref missing) | `unknown` or `failed` (`result_unavailable`) | Read-only retrieval retry may be allowed if safe | Keep execution evidence |
| Process restart / adapter crash boundary | `unknown`/`requires_manual_review` unless durable evidence proves terminal state | No blind retry | Reconciliation required |
| Unknown final state | `unknown` | No automatic completion or destructive retry | Manual disposition when side effects possible |

## 7. Retry, idempotency, and side-effect policy
- **Default:** retries disabled unless capability is explicitly marked idempotent and side-effect-free in allowlist/policy.
- **v0 first capability (`hermes.status.read`):** read-only, no external side effects; bounded retries may be permitted **only** when prior outcome is definitively non-submitted/non-started or safely re-observable without mutation (policy-defined). Never retry on `unknown` in a way that can duplicate untracked effects (none expected for v0, but rule preserved).
- **Idempotency key scope:** `(capability_id, normalized_input, operation_id or explicit dedup scope)` as defined by AJ; adapter must persist/consult mapping.

## 8. Evidence and audit requirements (contract-level)
- Persist submission intent, validation/authorization decision, argv/template identifier (not raw secrets), start/finish timestamps, exit/transport outcome, bounded output refs/digests, redaction actions, correlation/ID mapping, and final status rationale.
- Treat all Hermes output/log text as untrusted data; sanitize before persistence/display.

## 9. Labels
- **Provisional design:** schema/status/id/failure mapping for `aj.hermes.execution.v0`.
- **Evidence-based constraints:** no invented Hermes IDs, no completed-on-ambiguous, no trusted caller-supplied authz, AJ multi-store non-atomic/no exactly-once external effects.
- **Decision requiring user approval:** adoption of contract, first capability mapping, any retry enablement beyond conservative read-only policy.
