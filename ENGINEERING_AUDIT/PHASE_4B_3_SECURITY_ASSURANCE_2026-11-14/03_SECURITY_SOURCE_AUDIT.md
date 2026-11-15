# 03 — Security Source Audit

## Sources inspected (actual, current)
- `AJ/aj/hermes_adapter.py` — `HermesExecutionAdapter` (`__init__`, `available/describe`, `_controlled_env`, `_resolve_cli`, `_v0_from_execution_request`, `_reject`, `execute`), `default_runner`, `RunnerResult`, bounds/validation helpers.
- `AJ/aj/hermes_contract.py` — `validate_request`, `redact_text`/patterns, `response_envelope`, constants (`CAPABILITY_STATUS_READ`, `CONTRACT_VERSION`, `TRUST_MODE_LOCAL`).
- `AJ/aj/runtime.py` — `_build_execution` (feature/runtime gates, strict config checks, fail-closed), `assemble`.
- `AJ/aj/config.py` — defaults for `feature_flags` and `execution`/`execution.hermes`.
- `AJ/aj/orchestrator.py` — `build` (conditional `hermes.status.read` registration only when attached+available), `handle`/authorization/`_capability_blocker`, HERMES execution path (correlation args, `execute` via port, evidence/audit/journal/receipt/memory recording), `status`.
- `AJ/aj/execution.py` — `ExecutionPort`, `UnavailableExecutionAdapter`, `execute()` (availability, exception normalization, result-type check).
- `AJ/aj/authorization.py`, `AJ/aj/permissions.py` — privileged/local-trust and 5-level capability authorization models (inspected; general capability auth enforced by `Authorizer` in orchestrator).
- `AJ/aj/journal.py`, `AJ/aj/receipts.py`, `AJ/aj/operation_evidence.py`, `AJ/aj/recovery.py` — evidence/append-only records and recovery semantics (inspected; not redesigned).
- Existing tests: `tests/test_hermes_contract.py`, `tests/test_phase4b1_hermes_adapter.py`, `tests/test_phase4b1_hermes_security_faults.py`, `tests/test_phase4b2_reliability_hardening.py`.

## Findings and actions

| Finding | Location | Evidence | Severity | Action |
|---|---|---|---|---|
| **Fixed (4B.3): redaction token leakage** — `Authorization: Bearer/Basic <token>` could be partially redacted (label redacted, token left behind) due to pattern/replacement order | `aj/hermes_contract.py` `_SENSITIVE_PATTERNS`/`redact_text` | New 4B.3 test initially failed (`Authorization=[REDACTED] abc.def...` leaked token), fixed by specific auth-scheme patterns and quoted JSON-key handling; all 4B.3/4B.2/4B.1 redaction tests pass | High (sanitization correctness) | Implemented narrow fix; regression covered in `tests/test_phase4b3_security_assurance.py::test_redaction_covers_common_and_edge_formats` |
| **Fixed (4B.3): empty cli_path fallback** — adapter init defaulted empty/whitespace `cli_path` to `"hermes"` in permissive construction | `aj/hermes_adapter.py` `__init__` | Adversarial cases showed permissive fallback risk; changed to preserve explicit empty (resolve fails closed) while `None` defaults to `hermes`; runtime strict path already rejects empty/non-string. Tests pass | Medium (provenance/config fail-closed) | Implemented; covered by `test_cli_path_invalid_forms_fail_closed` |
| **Verified:** fixed command/no-shell/allowlist enforced — argv always `[resolved,"gateway","status"]`, `shell=False`, env copied from allowlist keys only | `aj/hermes_adapter.py` `_resolve_cli/execute/default_runner` | Source inspection + 4B.1/4B.2/4B.3 tests (fixed argv, env allowlist, no request-controlled command) | High control (intact) | No change |
| **Verified:** deny-by-default capability/contract/authz/input — only `hermes.status.read`, empty input, AJ allow + `local_trust`, timeout bounds, required IDs; unknown/invalid rejected | `aj/hermes_contract.py` `validate_request`, `aj/hermes_adapter.py.execute`, `aj/runtime.py`/`aj/orchestrator.py` registration | Contract + adversarial matrix tests pass | High control (intact) | No change |
| **Verified:** bounded incremental collection and timeout/cleanup — caps during read, drain-to-EOF, SIGTERM→SIGKILL pgid+pid, bounded waits, honest timeout/partial | `aj/hermes_adapter.py` `default_runner` | 4B.2/4B.3 real-subprocess tests pass (flood, hang, signal, pipe-holder bounded) | High control (intact) | No change |
| **Residual (documented): TOCTOU/path trust** — executable checked then executed; symlink followed if executable; PATH resolution trusted to local context | `_resolve_cli`/`Popen` | Source analysis; symlink test confirms safe fail-or-fixed behavior | Medium | Documented; not safely eliminable without breaking legitimate installs |
| **Residual (documented): descendant pipe holders** — reader threads join with timeout; daemon threads possible if descendant keeps inherited pipe open after group kill (session/group escape edge cases) | `default_runner` threading/join | Pipe-holder test shows bounded return (<8s); best-effort cleanup | Medium | Documented; bounded behavior verified |
| **Residual (documented): best-effort redaction** — regex patterns cannot cover all encodings/formats | `redact_text` | Improved tests pass; limitation explicit | Medium | Documented |
| **Residual (known): multi-store evidence non-atomicity** — task/audit/journal/receipt/memory writes not atomic across stores | `aj/orchestrator.py`, evidence modules | Existing architecture/design docs; not modified | Medium (known) | Documented; no unsafe redesign |

No unauthorized capability, command, shell path, or persistent enablement introduced. `local_trust` remains non-authenticated in code/docs. No Hermes IDs fabricated.