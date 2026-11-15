# 06 — Test Results and Fault Injection

## Baseline (before 4B.1 source changes)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` (AJ/): **exit 0**, `ok: true`, **23/23 checks**, `attached.hermes: "NOT ATTACHED"`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` (AJ/): **433 passed, 13 warnings, 0 failed** (39.63s).

## New tests added (isolated, no live Hermes dependency)

| File | Coverage |
|---|---|
| `tests/test_phase4b1_hermes_adapter.py` | disabled/unavailable behavior, valid `hermes.status.read` success + v0 envelope/ID/correlation mapping, unknown capability + unsupported contract rejection, invalid input/missing authz/wrong trust rejection, non-zero exit => failed, timeout => timeout (partial), spawn failure/missing CLI => failed dependency_unavailable, output bounds + redaction, fixed argv + env allowlist, default-disabled assembly and explicit enablement wiring/registry exposure |
| `tests/test_phase4b1_hermes_security_faults.py` | invalid cli path/arg-smuggling rejection, unknown/disallowed capabilities (shell/tool/fs/messaging), capability-flag-off bypass prevention, malformed/empty/partial outputs handled honestly, timeout bound enforcement, Hermes IDs never invented |

**New targeted result:** `13 passed in 0.34s`.

## Regression and post-change verification
- Targeted existing: `tests/test_hermes_contract.py tests/test_foundation.py` => **29 passed**.
- Regression fix: `tests/test_orchestrator.py::test_hermes_capability_fails_while_no_runtime_is_attached` initially failed due to HERMES path assuming `record.idempotency_key`; fixed with safe `getattr(..., "")`. `tests/test_orchestrator.py` => **13 passed**.
- **Full suite (final):** `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` => **446 passed, 13 warnings, 0 failed** (64.02s).
  - Delta vs baseline: **+13 passed** (new 4B.1 tests), **0 failed**, warnings unchanged class/count.
  - Note: one intermediate full-run attempt hit an environmental `sqlite3.OperationalError: disk I/O error` in forked worker for `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (concurrent stress on local filesystem); the specific test and full suite passed on re-run. Treated as non-deterministic environment flake, not a 4B.1 regression.
- **Health/self-check:** `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` => **exit 0, ok true, 23/23 checks, failures [], attached.hermes "NOT ATTACHED"**.

## Fault/security scenarios exercised (fake-process/unit level)
- CLI unavailable/missing executable, spawn failure, non-zero exit, timeout with partial output, malformed/empty output.
- Disabled adapter/capability flag, unknown capability, unsupported contract version, invalid/missing request fields, missing/invalid authorization/trust context.
- Injection-shaped input attempts (`input` args), unsafe cli_path config rejected, controlled env allowlist (sensitive env not forwarded), output truncation and secret redaction.
- Hermes native IDs not fabricated. Duplicate/retry/unknown-outcome semantics constrained by validation and honest status mapping (read-only, no unsafe replay claims). Live Hermes runtime was **not** manipulated for fault tests.