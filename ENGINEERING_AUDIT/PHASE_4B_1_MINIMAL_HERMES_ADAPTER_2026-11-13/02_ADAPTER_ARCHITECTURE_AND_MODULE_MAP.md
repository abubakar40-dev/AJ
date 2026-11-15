# 02 — Adapter Architecture and Module Map

## Boundary
- AJ remains orchestration/control/evidence/authorization owner. Hermes accessed only through narrow `ExecutionPort` adapter (`HermesExecutionAdapter`), CLI subprocess boundary, no Hermes imports/internals in AJ core.
- Existing `UnavailableExecutionAdapter` remains default/fallback; Hermes adapter instantiated only when explicitly enabled/configured (feature flag + runtime + hermes.enabled + capability flag) and fails closed on invalid config.

## Files created/modified (4B.1, AJ-only)

| File | Change | Purpose |
|---|---|---|
| `aj/hermes_contract.py` | **Created** | `aj.hermes.execution.v0` constants, request validation (`validate_request`), status normalization, bounded redaction, response envelope helpers (pure, testable). |
| `aj/hermes_adapter.py` | **Created** | `HermesExecutionAdapter` (ExecutionPort) with injectable runner, fixed argv `['<hermes>', 'gateway', 'status']`, controlled env allowlist, bounded timeout/stdout/stderr, redaction, honest status/error mapping, nullable Hermes IDs, CLI resolution/availability handling. |
| `aj/config.py` | Modified (additive) | Defaults: `feature_flags.hermes_execution_adapter=false`, `execution.hermes{enabled:false, capability_status_read_enabled:false, cli_path, timeouts/output bounds}`; runtime remains `none`. |
| `aj/runtime.py` | Modified | `_build_execution(config)` selects `UnavailableExecutionAdapter` by default or `HermesExecutionAdapter` only when explicitly enabled (fail closed on exception); `assemble(...)` passes execution port to build. Added `Mapping` import. |
| `aj/orchestrator.py` | Modified | `build(...)` accepts `execution`; registers `hermes.status.read` (owner HERMES, risk 0, read-only) **only** when adapter is attached/available; enriched HERMES execution path to pass correlation/operation/attempt/idempotency args, persist evidence/audit/journal/receipt, and map outcomes honestly. |
| `tests/test_phase4b1_hermes_adapter.py` | **Created** | Unit/contract/wiring tests (disabled/default, valid mapping, invalid contract/capability/input/authz/trust, timeout/nonzero/spawn/cli-missing, bounds/redaction, fixed argv/env allowlist, assembly enablement). |
| `tests/test_phase4b1_hermes_security_faults.py` | **Created** | Security/fault-injection tests (cli-path injection guard, input smuggling, unknown capabilities, feature bypass, malformed/empty/partial outputs, timeout bound, no invented Hermes IDs). |

## Interfaces and flow
- **Request path (when capability enabled and routed):** AJ authorizes -> orchestrator builds `ExecutionRequest` with correlation args -> `execute(port, request)` -> adapter validates v0 envelope/allowlist/permission context -> runs bounded `hermes gateway status` via injected/default runner -> normalizes to `ExecutionResult` + v0 response envelope (evidence/provenance/timestamps/errors).
- **Runner abstraction:** `Runner(argv, timeout_s, stdout_max, stderr_max, env) -> RunnerResult(started, exit_code, stdout, stderr, timed_out, error)` enables deterministic fake-process tests; default uses `subprocess.run(shell=False, capture_output=True, text=True, timeout=...)`.
- **No-scope additions:** no new orchestration frameworks, no JARVIS/HELIX/Hermes code changes, no generic skill/MCP/agent execution, no services/config/env modifications.