# 06 — Test Results and Fault Injection

## Baseline (rerun before 4B.2 code edits)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check`: **exit 0, ok true, 23/23, failures [], attached.hermes "NOT ATTACHED"**
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`: **446 passed, 13 warnings, 0 failed** (51.07s)

## New 4B.2 deterministic tests (no live Hermes required)
`AJ/tests/test_phase4b2_reliability_hardening.py` — **10 passed**:
- strict adapter config fail-closed (negative/zero/excessive/invalid-type/bounds inversion)
- runtime fail-closed on invalid explicit hermes config (no attachment)
- CLI provenance rejects argument-like/invalid path
- default runner bounds output **during collection** with truncation (real subprocess flood)
- default runner timeout terminates/reaps and returns partial bounded output within bounded time (real subprocess sleep)
- non-zero exit and signal termination classification (real + injected)
- malformed encoding/empty output handled honestly
- redaction best-effort patterns (Bearer/Basic, keys/tokens/passwords, credential URL, env-style secrets)
- repeated bounded probes consistent (injected runner)
- evidence honesty: no false success, no fabricated Hermes ID on timeout

## Existing relevant suites (post-hardening)
- `tests/test_phase4b1_hermes_adapter.py tests/test_phase4b1_hermes_security_faults.py tests/test_hermes_contract.py tests/test_phase4b2_reliability_hardening.py`: **31 passed** (1.04s)
- `tests/test_orchestrator.py` and other existing suites included in full regression: passed.

## Full regression and health (post-4B.2)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`: **456 passed, 13 warnings, 0 failed** (60.79s)
  - Delta vs pre-4B.2 rerun baseline: **+10 passed** (new 4B.2 tests), warnings unchanged/pre-existing.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check`: **exit 0, ok true, 23/23, failures [], attached.hermes "NOT ATTACHED"**

## Fault/security observations covered
Fixed argv/no-shell preserved, executable-path/config validation tightened (fail-closed when explicitly enabled), spawn/missing CLI/nonzero/signal/timeout/partial/malformed/empty/oversized/encoding cases covered, env allowlist and redaction tested, disabled-adapter/feature/capability/allowlist/authz bypass cases covered by existing+new tests, no fabricated metadata.

## SQLite/concurrency observation (Stage E4, unrelated to 4B.2)
`tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (forked concurrent writers) run independently 5 times in current environment:
- Run 1: **PASS** (0.50s)
- Run 2: **FAIL** `sqlite3.OperationalError: disk I/O error` (0.24s)
- Run 3: **FAIL** `sqlite3.OperationalError: disk I/O error` (0.39s)
- Run 4: **FAIL** `sqlite3.OperationalError: disk I/O error` (0.29s)
- Run 5: **PASS** (0.29s)

**Assessment:** intermittent/environment-sensitive in this environment (2/5 passed in isolated repeats; also observed as transient in 4B.1/full-suite history). Failures are SQLite/storage concurrency behavior in a stress test using fork on this filesystem/runtime, **not caused by 4B.2 adapter/runtime changes** (4B.2 touched only hermes adapter/contract/runtime selection/tests/docs). No unrelated DB architecture changes made; full suite completed **456 passed, 0 failed** in final run. Documented for follow-up outside 4B.2 scope if reproducible remediation is desired.