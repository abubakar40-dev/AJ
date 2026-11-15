# 09 — Observability and Evidence Requirements (future mutating operations)

Principles: append-only where applicable, bounded, redacted best-effort, provenance-tagged, no secret persistence, no fabricated IDs/success, no merge of AJ memory with Hermes state.

## 1. Request metadata (what was asked)
- AJ task/request IDs, capability_id, contract/capability version, requested operation descriptor (fixed argv template), side-effect class, idempotency key (if any), caller/request provenance as known, timestamps.
- Must not include raw secrets; inputs must be schema-validated (prefer empty/fixed for first op).

## 2. Authorization metadata (why allowed)
- Authorizer decision (allow/deny/confirm), policy basis/risk level, trust mode (`local_trust`) and explicit non-authenticated provenance, confirmation/approval evidence binding (capability+scope+fingerprint+time) when required.
- Distinguish “authorized by local policy” from “authenticated principal”.

## 3. Execution metadata (what actually ran)
- Resolved executable (sanitized), exact argv, `shell=false`, cwd/env-allowlist fact (not values of secrets), spawn/start/end times, timeout config, process IDs if useful (non-sensitive), termination/kill signals, exit code, bounded/truncated/redacted stdout/stderr with truncation flags.
- Process-level outcome only.

## 4. External metadata (what Hermes reported)
- Hermes-returned operation/task IDs, status tokens, structured fields **only if actually provided** by interface; otherwise `null/unknown` with note.
- Unstructured CLI text treated as untrusted observation, not authoritative semantic state.

## 5. Outcome metadata (what is known)
- AJ-normalized status (`submitted/accepted/running/completed/failed/rejected/timeout/unknown/requires_manual_review/cancel_requested/cancelled` as truthfully applicable), error classification, acceptance flag, ambiguity/uncertainty markers.
- No semantic success inferred solely from exit 0 unless independently verified.

## 6. Recovery metadata (what remains uncertain)
- Incomplete-intent markers, crash-window ambiguity, whether side effect may have occurred, retry safety (`safe/unsafe/unknown`), manual-review requirement, read-back verification results if performed.

## 7. Provenance
- Each fact tagged by source: `aj_request`, `aj_authorizer`, `aj_adapter`, `hermes_cli_output`, `derived`.
- Preserve correlation across task/audit/journal/receipt/operation evidence; document cross-store non-atomicity boundaries.

## Minimum bar before mutating implementation
- Deterministic capture path for all above (as applicable), tested fail-closed on missing critical fields, and explicit handling for `unknown`/timeout-after-possible-effect cases.
