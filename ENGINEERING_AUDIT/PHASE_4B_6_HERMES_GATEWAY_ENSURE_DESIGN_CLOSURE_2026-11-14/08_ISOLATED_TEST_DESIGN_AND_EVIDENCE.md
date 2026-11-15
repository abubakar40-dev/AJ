# 08 — Isolated Test Design and Evidence (Criterion 7)

## Scope and constraints
- **Implemented (AJ-side, isolated):** `AJ/tests/test_phase4b6_gateway_ensure_design_isolated.py`
- **Execution:** `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_phase4b6_gateway_ensure_design_isolated.py` from `AJ/` → **9 passed in 0.30s** (exit 0).
- **No real lifecycle actions:** tests do **not** invoke real `hermes gateway ensure`, do not start/stop/replace gateways, do not change flags/config/services. Fake executable + synthetic verdicts + pure mapping helpers only.
- **Proof boundary:** proves AJ-side design prototypes/mapping behavior against simulated conditions **only**. Does **not** prove native Hermes behavior, idempotency, concurrency, or real runtime outcomes.

## Comprehensive test design matrix

| Case | Method (isolated) | Expected AJ/design behavior | Status |
|---|---|---|---|
| Ready gateway | Synthetic `ready` verdict (exit 0) + fake JSON executable | Map to `completed/ready`, attach-read-only precondition, no manual review | **Covered** (prototype tests) |
| Stopped/absent gateway | State-gating decision for `stopped/absent` | Classified as mutating start candidate, **not allowed** without explicit start permission; fail closed by default | **Covered** (design assertion) |
| Starting gateway | `starting/deadline` verdict; state `starting` | Timeout/ambiguous -> `unknown`, manual review, no auto-retry; observe/wait decision | **Covered** |
| Unknown state | `unknown`, `unavailable`, `readback_unavailable`, `contradictory`, `None` | Fail closed, no mutation/allow, manual review/unknown | **Covered** |
| Incompatible owner | `incompatible` exit/verdict | Failed/manual review; mutating replace-permission path only | **Covered** |
| Duplicate requests | Identity assertions (independent operation IDs) | Must not assume native idempotency; ambiguous outcomes remain manual-review | **Covered (design-level)** |
| Concurrent requests | (Not executed as real concurrency) design requires per-resource serialization/leases and ambiguity on races | No safe parallel mutation assumption | **Design only; runtime concurrency unproven** |
| Timeout | `process_timed_out` and `starting/deadline` | `timeout` -> `unknown`, manual review, no rollback assumption | **Covered** |
| Partial startup | represented via ambiguous `starting`/`runtime_exited`/failed read-back mappings | `unknown/requires_manual_review` | **Partially covered via verdict classes** |
| Failed read-back | `inaccessible`/conflict/runtime_exited mappings; readback unavailable gating | Fail closed/manual review | **Covered** |
| Secret leakage | argv construction check (no secret in argv) | Secrets never in fixed argv; redaction required for logs/evidence (policy) | **Covered (argv boundary)** |
| Invalid configuration/invocation | `invalid_invocation` exit 2 | `rejected`, not executed/mutated | **Covered** |
| Process interruption | treated as local timeout/unknown outcome class | No rollback, ambiguous -> manual review | **Covered via timeout/unknown mapping** |
| Recovery decision | policy assertions (no auto-retry on ambiguity) | observe/wait/manual-review paths conservative | **Covered (policy-level)** |
| Persistence failure | (No DB mutation performed) documented requirement | must not claim durable evidence or trigger unsafe retries | **Design documented (doc 05/09)** |

## Implemented tests (names)
1. `test_fixed_argv_shape_no_shell`
2. `test_ready_verdict_maps_to_completed_ready_without_mutation_claim`
3. `test_deadline_starting_is_ambiguous_unknown_no_autoretry`
4. `test_inaccessible_incompatible_conflict_require_manual_review`
5. `test_invalid_invocation_is_rejected_not_executed`
6. `test_state_gating_fails_closed_for_unknown_and_mutating_states`
7. `test_fake_hermes_executable_json_contract_isolated`
8. `test_duplicate_requests_require_independent_identity_and_policy_not_native_proof`
9. `test_secret_redaction_boundary_design_note`

## Gaps / follow-up (if later authorized)
- Real Hermes behavior, supervisor/profile/multiplex concurrency, and actual start/replace/read-back under controlled non-production lifecycle experiments (separately authorized).
- Integration tests in safe isolated environment with durable local POSIX storage for evidence persistence semantics.
- Fault-injection for SQLite persistence failures within AJ evidence path (without modifying production behavior in this phase).
