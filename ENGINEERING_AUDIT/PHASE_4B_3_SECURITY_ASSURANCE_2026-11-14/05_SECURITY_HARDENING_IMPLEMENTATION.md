# 05 — Security Hardening Implementation

## Changes (AJ-only, evidence-backed, narrow)

| File | Change | Reason / before→after | Regression coverage |
|---|---|---|---|
| `aj/hermes_contract.py` | Expanded and reordered best-effort redaction patterns; improved replacement logic for Authorization Bearer/Basic, quoted JSON-like secrets, and key/value/env forms | **Before:** `Authorization: Bearer <token>` could be partially redacted leaving token (`Authorization=[REDACTED] <token>`). **After:** scheme+token and common secret forms redacted as `Authorization: Bearer [REDACTED]` / `key=[REDACTED]` / quoted `[REDACTED]`; tail-beyond-limit not exposed by truncation test. Limitation remains best-effort. | `tests/test_phase4b3_security_assurance.py::test_redaction_covers_common_and_edge_formats`, existing `test_phase4b2_reliability_hardening.py::test_redaction_patterns_best_effort`, `test_phase4b1_hermes_adapter.py::test_output_bounds_and_redaction` |
| `aj/hermes_adapter.py` | `__init__` cli_path handling: `None` → default `"hermes"`; explicit string kept stripped (including empty) instead of falling back to default | **Before:** empty/whitespace explicit cli_path silently normalized to `"hermes"` in permissive construction. **After:** explicit empty becomes invalid and `_resolve_cli` fails closed (`dependency_unavailable`, no spawn); runtime explicit-enable strict validation already rejects empty/non-string. | `tests/test_phase4b3_security_assurance.py::test_cli_path_invalid_forms_fail_closed` (incl. empty/whitespace), existing provenance/injection tests |
| `tests/test_phase4b3_security_assurance.py` | Added 47 deterministic security-assurance tests (adversarial contract/config/provenance/argv/env/redaction/lifecycle/evidence cases); adjusted two cases to assert security property (safe symlink outcome, extra fields cannot alter fixed argv) rather than incorrect strict-rejection assumption | New regression suite for threat matrix; no existing tests weakened/removed/skipped | 47 passed; full regression 503 passed |

## Intentionally not changed
- Fixed command `hermes gateway status`, `shell=False`, allowlist deny-by-default, only `hermes.status.read`, contract `aj.hermes.execution.v0`.
- Default-disabled flags/runtime and `local_trust` non-authenticated semantics.
- Orchestrator/evidence/journal/receipt/recovery architecture (no redesign), Hermes/JARVIS/HELIX, unrelated AJ modules/tests.
- No new dependencies added.

## Compatibility
- No public contract semantic changes intended. Stricter fail-closed behavior on explicitly invalid cli_path/config improves safety; legitimate default use (`cli_path` omitted/None or valid path) unaffected. Existing 4B.1/4B.2/contract tests pass.