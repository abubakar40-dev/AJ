# 07 — Evidence and Outcome Integrity

## Verified properties
- **Authorization/capability boundary:** only `hermes.status.read` allowed through adapter/contract validation; request must carry AJ allow + `local_trust` permission context and empty input; capability registered in runtime only when adapter attached+available and flags/config explicitly enabled (fail-closed). `local_trust` is non-authenticated (rejected if presented as authenticated).
- **Fixed operation:** argv always `[<resolved-hermes>, "gateway", "status"]`, `shell=False`; request/envelope fields cannot change command. Evidence records argv template and sanitized resolved cli.
- **Honest outcomes:** spawn/CLI-unavailable failures → failed, `accepted=false`; timeouts → `timeout`, `accepted=true`, partial bounded output, not ok; non-zero/signal → failed; exit 0 → completed as **process outcome** (`observation=exit_zero`) with explicit note that unstructured output does not prove semantic health. Rejections never recorded as executed.
- **No fabricated metadata:** `hermes_execution_id` always `null` for this probe (never invented).
- **No false success:** timeout/failure/rejection not mapped to completed/ok. Orchestrator-mediated timeout test recorded non-completed task outcome.
- **Output handling:** untrusted, bounded incremental collection, truncation marked, best-effort redaction applied before payload/evidence; raw text preserved as sanitized diagnostics (not executed).
- **Append-only evidence integration:** HERMES path records task action/evidence, transitions, audit, journal, receipts, memory events consistent with existing AJ mechanisms (inspected); correlation/operation/attempt/ids propagated.

## Residual limitations (not fully eliminated)
- **Multi-store non-atomicity:** task, audit, journal, receipt, memory writes are not atomic across stores (existing AJ architecture). Induced persistence-failure consistency not exhaustively fault-injected in 4B.3; no unsafe redesign performed.
- **Semantic ambiguity:** exit 0 cannot prove gateway semantic health; unstructured CLI text remains non-authoritative.
- **Retry/idempotency at external boundary:** read-only probe, no automatic retries added for ambiguous outcomes; broader exactly-once/idempotent guarantees not claimed.
- **Duplication/replay:** orchestrator/lease/idempotency subsystems exist but not comprehensively stress-tested for every Hermes-path race in this phase (out of narrow scope). No evidence of fabricated success/IDs introduced.