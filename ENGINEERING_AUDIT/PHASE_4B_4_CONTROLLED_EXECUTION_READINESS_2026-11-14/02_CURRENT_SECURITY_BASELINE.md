# 02 — Current Security Baseline (4B.3, verified)

## Invariants verified against current source and tests
| Invariant | Evidence |
|---|---|
| Only approved capability `hermes.status.read` (`aj.hermes.execution.v0`) | `aj/hermes_contract.py` `CAPABILITY_STATUS_READ`, `validate_request` rejects other capabilities/versions/inputs; `aj/runtime.py` registers capability only when adapter attached+available; `aj/orchestrator.py` build gates on `execution.available()` |
| Fixed command `hermes gateway status`, `shell=False` | `aj/hermes_adapter.py` resolves cli then executes fixed argv `[resolved,"gateway","status"]`; `default_runner` uses `subprocess.Popen(..., shell=False, ...)` |
| Controlled environment allowlist | `_controlled_env` copies only allowlisted keys from `os.environ` (PATH/HOME/USER/LOGNAME/LANG/LC_*/TERM/XDG_RUNTIME_DIR/DBUS_SESSION_BUS_ADDRESS/HERMES_HOME/HERMES_PROFILE) |
| Bounded output and timeout | Incremental capped stdout/stderr collection, truncation markers, `default/max` timeout bounds, timeout termination (SIGTERM→SIGKILL best-effort), bounded waits/reap |
| Fail-closed authorization/config/request validation | Contract requires AJ allow + `local_trust` + empty input + bounded timeout + required IDs; runtime `_build_execution` strict validation and fail-closed to `UnavailableExecutionAdapter`; adapter rejects invalid/unavailable cases |
| Default-disabled, no persistent enablement | `aj/config.py` defaults: `feature_flags.hermes_execution_adapter=false`, `execution.runtime="none"`, `execution.hermes.enabled=false`, `capability_status_read_enabled=false`; runtime gates require explicit enablement |
| `local_trust` is not authentication | Contract/trust model and adapter provenance use `local_trust_non_authenticated`; authenticated trust mode rejected by validation |
| No fabricated Hermes execution IDs | `hermes_execution_id` set to `null` in envelopes/evidence paths |
| Honest timeout/failure/rejection outcomes; no semantic health inference | Adapter maps spawn failure/timeout/signal/nonzero/exit0 conservatively (`observation=exit_zero` with non-semantic-health note); timeout/reject not completed |
| Redaction best-effort (not guaranteed) | `redact_text` patterns improved in 4B.3 (Bearer/Basic, quoted JSON-like, key/value/env/URLs), bounds/truncation applied; limitation documented |
| No JARVIS/HELIX/Hermes source modification | AJ-only scope; protected repos/Hermes source untouched (doc 01) |

## 4B.3 regression verification (this phase)
- `tests/test_phase4b3_security_assurance.py tests/test_phase4b2_reliability_hardening.py tests/test_phase4b1_hermes_adapter.py tests/test_phase4b1_hermes_security_faults.py tests/test_hermes_contract.py` → **78 passed, 0 failed** (1.43s/1.67s runs recorded)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` → **23/23 ok, failures [], Hermes NOT ATTACHED**
- Full regression: **502 passed, 1 failed, 13 warnings** (51.42s) — sole failure `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` intermittent on ntfs3-backed default tmp (known, separate SQLite track)

No working 4B.3 security code rewritten for style.
