# 10 — Security Gate and Acceptance Criteria (before any mutating capability implementation)

A future mutating Hermes capability implementation may proceed only when all applicable controls below are satisfied for that **specific** capability (understood/controlled risk, not zero risk).

## Mandatory controls
1. **No arbitrary shell / no user-controlled command construction**: fixed argv or equivalently strict allowlisted operation template; `shell=False`; input schema rejects unexpected fields.
2. **Capability isolation**: separately registered/enabled/disabled/authorized/audited/tested; default-disabled flags and runtime gating; no unrelated operation exposure.
3. **Explicit permission mapping & fail-closed authz**: AJ authorization required; side-effect class and risk level mapped; deny on missing/invalid context; `local_trust` not represented as authentication.
4. **Confirmation/approval where required**: scope-bound confirmation for sensitive/mutating classes per policy; fail closed if absent/invalid.
5. **Contract/truthful semantics**: versioned contract/profile supporting required fields; unknown/unavailable external IDs/states represented honestly; no fabricated success/IDs.
6. **Evidence requirements**: request/authz/execution/external/outcome/recovery metadata with provenance; bounded and best-effort redacted; secrets excluded.
7. **Failure classification & recovery**: explicit handling for reject/spawn-fail/success/fail/timeout/ambiguity/unknown/cancel-unsupported; no unsafe auto-retry on ambiguous outcomes.
8. **Idempotency analysis**: documented local vs Hermes-native guarantees; no exactly-once claims; duplicate/conflict behavior defined.
9. **Cancellation analysis**: native support known or explicitly unsupported; local kill distinguished from remote cancellation.
10. **Secret handling**: controlled env allowlist, no secret-bearing args/config persistence, redaction limitations documented.
11. **Regression suite**: deterministic unit/contract/fault-injection tests covering allowlist, argv immutability, config fail-closed, authz, timeout/cleanup, redaction, honest evidence/outcomes.
12. **Controlled integration test (if feasible/safe)**: isolated, approved, fixed command only, no persistent enablement, with evidence review.
13. **Rollback/compensation analysis**: reversibility assessed; if unknown/unavailable, classified conservatively and manual-review/confirmation gates applied.
14. **SQLite/storage reliability consideration**: for operations whose evidence durability depends on affected storage paths, environment risk assessed (see doc 11) and minimum reliability posture defined.

## Not required (but must be honest)
- Perfect redaction, impossible zero risk, or authenticated identity when unavailable.

## Explicit non-approvals
- General Hermes execution enablement, arbitrary commands, shell, variable user args without strict schema, messaging/browser/desktop/MCP/skill-agent expansion, or implementation in this phase.
