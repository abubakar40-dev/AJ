# 05 — Operation Evidence and Recovery

## Evidence captured (4B.1 implementation)
- **AJ task/attempt lifecycle:** existing orchestrator flow records task transitions, attempt start/finish, action records, evidence entries, journal events, receipts, audit events, and memory events for HERMES execution path (success/failure/exception) consistent with AJ patterns.
- **Correlation/IDs:** `operation_id`, attempt ID, correlation (`task_id`), idempotency key passed into execution arguments/envelope; echoed in v0 response where applicable. `hermes_execution_id` remains `null` (not exposed/invented).
- **Adapter evidence (bounded, sanitized):** argv template, exit code, timed_out, truncation flags, stdout/stderr char counts, timestamps (started/finished/observed), adapter/provenance, normalized status/error class/code/source/retryable.
- **Result payload:** bounded redacted stdout/stderr diagnostic text and probe metadata (untrusted). No raw secrets/tokens/passwords/API keys intentionally persisted; best-effort redaction applied to captured output/error messages.
- **No historical overwrite:** uses append-oriented task/audit/journal/receipt/memory mechanisms; no claim of cross-store atomicity.

## Timeout/cancellation/retry/unknown handling
- **Timeout:** enforced by adapter subprocess timeout; mapped to `timeout` with `accepted=true` (process started) and partial bounded output marked; never reported as completed.
- **Cancellation:** no cooperative Hermes cancellation claimed for CLI probe. If AJ cancellation semantics apply, they remain AJ-local; adapter does not claim Hermes-side cancellation confirmation beyond process termination evidence if any.
- **Retry/idempotency:** read-only capability; adapter is stateless per call. No blind retry on unknown/ambiguous outcomes. Deduplication beyond existing AJ idempotency/task semantics not generalized.
- **Unknown/manual review:** v0 mapping/vocabulary supports `unknown`/`requires_manual_review`; ambiguous outcomes must not be converted to success. Evidence persistence failures after external execution must preserve ambiguity per existing AJ recovery model (no false "did not happen").

## Recovery/consistency notes
- Phase 3E/3F evidence-consistency and recovery architecture remains authoritative; this spike does not introduce new DB/broker/distributed coordination/recovery engines.
- Because probe is read-only and non-mutating, replay/re-observation risk is low compared to side-effecting operations, but adapter still reports honest outcomes and preserves evidence. Future mutating capabilities require stricter idempotency/unknown handling per 4B.0.