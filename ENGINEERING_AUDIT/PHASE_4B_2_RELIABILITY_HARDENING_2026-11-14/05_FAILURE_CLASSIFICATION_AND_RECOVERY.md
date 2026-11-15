# 05 — Failure Classification and Recovery

## Honest status/error classes (existing read-only capability)
- **Rejected (pre-execution, `accepted=false`):** contract/version/capability/allowlist/validation/authz/trust/input/timeout-bound violations fail closed via v0 validation and adapter checks.
- **Failed, not started (`accepted=false`):** CLI missing/invalid/unresolvable path => `dependency_unavailable`; spawn/start failure => `spawn_failed`.
- **Timeout (`accepted=true`):** process started but exceeded bounded timeout => `status=timeout`, `partial` payload, timeout error, no completion/success claim.
- **Failed after start (`accepted=true`):** non-zero exit or signal termination => `runtime_error` (signal reported when known), `observation=nonzero_exit`.
- **Completed probe (`accepted=true`):** exit code 0 => `status=completed`, verified by `process_exit_zero`, `observation=exit_zero`; raw text still untrusted/non-semantic.
- **Unknown/ambiguous:** vocabulary/helpers support `unknown`/`requires_manual_review`; adapter does not coerce ambiguous outcomes to completed. (No new ambiguous-condition synthesis added beyond honest timeout/failure handling.)

## Evidence and reconciliation behavior (inspected/preserved)
- **No fabricated IDs:** `hermes_execution_id` remains `null`.
- **No false success:** timeout/nonzero/spawn failures/rejections never mapped to completed; verification only on exit 0.
- **Correlation/attempt evidence:** orchestrator HERMES path passes `operation_id/attempt_id/correlation_id/idempotency_key`, records task evidence, audit, journal, receipt, and memory events consistent with existing AJ mechanisms.
- **No unsafe retry/duplication claims:** read-only probe; adapter stateless per call. No automatic retries added for ambiguous outcomes. Repeated controlled probes executed as separate invocations with distinct ids.
- **Preserved constraints:** raw/durable AJ records not overwritten; no cross-store atomicity claim; no exactly-once guarantee claim. Existing AJ recovery/reconciliation subsystems not redesigned.

## Verified
- `test_evidence_honesty_no_false_success_no_fabricated_id`, timeout/failed/rejected unit tests, 4B.1 adapter/security/fault tests, orchestrator HERMES failure test (`test_hermes_capability_fails_while_no_runtime_is_attached`) still passes.
- Live isolated probes: completed only with exit-0 evidence, ids null, consistent results.

## Limitations
- Adapter cannot determine semantic gateway health from unstructured text; `exit_zero` is a process outcome, not a full operational guarantee.
- If evidence persistence fails after a real external probe (AJ-internal concern), existing AJ recovery semantics must handle ambiguity; 4B.2 did not alter multi-store consistency architecture. Read-only probe reduces side-effect reconciliation risk.