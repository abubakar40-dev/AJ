# 06 — Execution Lifecycle, Failure, and Recovery

**Workstream F (Phase 4B.0).** Provisional design for AJ↔Hermes governed execution lifecycle. Must respect AJ limits: no cross-store atomicity guarantee, no exactly-once external side-effect guarantee, process-local locking/lease assumptions, no authenticated identity by default.

## 1. End-to-end lifecycle (AJ↔Hermes, v0)

| Step | Actor (owner) | Action | Durable evidence (AJ unless noted) | Correlation/IDs | Failure/uncertainty handling |
|---:|---|---|---|---|---|
| 1 | AJ (orchestrator/dispatcher) | Receive execution request for AJ-governed capability | Request intake record, normalized contract payload ref (redacted) | `aj_task_id`, `operation_id`, `attempt_id`, `correlation_id` | Invalid/missing context → `rejected` before mutation of external state |
| 2 | AJ (capability/permission/allowlist) | Validate contract, capability allowlist, input/bounds, authorization decision (AJ-computed) | Validation result, allowlist entry ref, authorization decision/provenance (`local_trust`, non-auth), deny reasons | Same + `capability_id` | Deny/invalid → `rejected` (fail closed), audited; no Hermes call |
| 3 | AJ (operation evidence/journal/task) | Create durable operation intent/dispatch-attempt record **before external invocation** | Intent event, planned command template ref, timeout/retry/idempotency policy snapshot | Operation/attempt/correlation | If intent persistence uncertain, stop (do not dispatch blindly) and surface inconsistency per AJ recovery rules |
| 4 | AJ adapter (Hermes boundary) | Submit bounded CLI invocation to Hermes | Submission/start evidence (argv template id/hash, start time, process handle metadata, bounded env policy ref) | All AJ IDs; `hermes_execution_id=null` unless evidenced | Start failure → `failed/rejected` with transport classification |
| 5 | Hermes/runtime (ack) | Accept/reject/start (process spawn/command acceptance semantics) | Observed acceptance/start evidence; Hermes-native ID only if exposed | Map Hermes ID if any | No Hermes ID for CLI v0 is acceptable; **must not invent** |
| 6 | AJ adapter | Record execution identifier mapping and current status (`submitted/accepted/running`) | Status transition evidence, mapping record | AJ↔Hermes mapping (nullable Hermes IDs) | Mapping write issues handled honestly (AJ non-atomic limits) |
| 7 | Hermes/runtime | Execute bounded read-only capability | Hermes-side runtime behavior (not AJ-canonical) | Native IDs if any | Unobservable internals treated as unknown beyond evidence |
| 8 | AJ adapter | Receive/retrieve progress or completion signal (stdout/stderr/exit/timeout) | Stream/output refs/digests (bounded, redacted), progress snapshots if available | Correlation/attempt | Lost stream/partial capture → `unknown`/`requires_manual_review` as warranted |
| 9 | Hermes/runtime + AJ adapter | Reach terminal or uncertain outcome | Raw outcome evidence (exit code, timeout, cancellation observation) | Same | Ambiguity preserved (no forced mapping to completed/cancelled) |
| 10 | AJ | Normalize and record final outcome/evidence; update AJ task/operation state per rules | `HermesExecutionResponseV0` mapping, final status, error classification, evidence bundle refs | Full ID map | Conflicting/incomplete evidence → `unknown` or `requires_manual_review` |
| 11 | AJ (recovery/reconciliation) | Reconcile uncertain outcomes only when safe/read-only evidence allows | Reconciliation attempt/result records, disposition | Correlation/operation IDs | No unsafe replay; v0 read-only probe may allow safe re-observation, but must not fabricate prior outcome |
| 12 | JARVIS/HELIX (consumers, future/approved) | Consume results via own approved contracts/views | Consumer-side read/reference records (out of 4B.1 scope) | Correlation/refs | Must honor AJ status honesty and domain ownership; not implemented now |

## 2. Ownership at transitions
- **AJ owns:** request validation, authorization decision, dispatch intent, AJ task/operation/attempt/correlation records, outcome normalization, reconciliation decisions for AJ-governed flow.
- **Adapter owns (within AJ trust boundary):** deterministic command mapping, bounded invocation, observation/capture, redaction, evidence packaging.
- **Hermes owns:** runtime process/session/tool execution internals and any native runtime state; Hermes-reported data is untrusted input until validated/mapped.
- **JARVIS/HELIX own:** their own user-facing delivery and delegated-work contexts when later integrated (no ownership transfer in v0).

## 3. Retry, idempotency, duplicate prevention
- **Pre-submission dedup:** AJ checks idempotency key / attempt uniqueness before dispatch where applicable.
- **v0 policy:** `hermes.status.read` is read-only/no intended side effects; retries allowed only for definitively non-dispatched/non-started failures or explicitly safe re-observation paths defined in implementation policy. **No retry on `unknown` submission outcome.**
- **Duplicate prevention:** stable `operation_id`+`attempt_id`+`idempotency_key` mapping persisted; adapter must not reuse attempt IDs for distinct dispatches.
- **External exactly-once:** not guaranteed (and not required for read-only v0); never claimed.

## 4. Timeout and cancellation semantics
- **Timeout:** adapter enforces `timeout_ms` bound; on expiry emits `timeout` with evidence (elapsed, process state/kill attempt result). Post-timeout state may become `cancelled`, `failed`, or `unknown`.
- **Cancellation:** AJ may issue cancel request (`cancel_requested`) translated to bounded process termination/interrupt where possible; **`cancelled` only when evidenced** (process exit/confirmed stop). If effect/state unclear → `unknown`/`requires_manual_review`.
- **No forced success mapping:** timeout/cancel ambiguity never becomes `completed`.

## 5. Recovery and manual disposition
- **Automatic recovery:** limited to evidence-based, safe reconciliation (e.g. confirm process exited, re-read read-only status only if policy allows and cannot create side effects). Must not mutate external state to "fix" unknowns.
- **Manual disposition required:** `requires_manual_review`, unresolved `unknown` with possible side effects (future capabilities), or conflicting evidence. Record operator-visible reason and pending disposition state.
- **Crash/restart:** adapter/AJ process restart leaves attempt in last durable honest state; reconciliation reads evidence and runtime observability without assuming completion.

## 6. Partial-result handling
- Capture and bound partial stdout/stderr/progress evidence with truncation markers.
- Mark outcome non-completed (`timeout|failed|unknown|requires_manual_review`) unless completion criteria fully satisfied.
- Never present partial output as successful final result.

## 7. AJ limitation alignment (must hold)
- **No cross-store atomicity:** intent/evidence/state updates may be partially persisted; design favors durable intent before dispatch and honest detection/reconciliation over assumed atomicity.
- **No exactly-once external side effects:** v0 avoids side effects; future capabilities must classify side effects and constrain retries accordingly.
- **Process-local locking/leases:** guarantees are local/process-scoped; adapter must not imply distributed coordination.
- **No authenticated identity by default:** provenance recorded as `local_trust` non-auth; no identity elevation.

## 8. Observable state taxonomy (operational)
Terminal: `completed`, `failed`, `rejected`, `cancelled` (evidenced). Non-terminal/transitional: `submitted`, `accepted`, `running`, `cancel_requested`. Uncertain: `timeout` (may require resolution), `unknown`, `requires_manual_review`. Consumers must render uncertainty explicitly.

## 9. Labels
- **Provisional design:** lifecycle steps, transition ownership, recovery policy.
- **Existing approved direction / evidence-based:** AJ honest-state, fail-closed, evidence-before-dispatch intent where possible, no fake auth/atomicity/exactly-once.
- **Decision requiring user approval:** enabling retries/cancellation behavior specifics for approved command, operational exposure scope.
