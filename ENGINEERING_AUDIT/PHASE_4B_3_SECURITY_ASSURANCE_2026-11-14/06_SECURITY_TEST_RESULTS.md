# 06 — Security Test Results

## Commands and results (AJ root: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`, `PYTHONDONTWRITEBYTECODE=1`)

| Suite | Command | Result | Duration | Exit |
|---|---|---:|---:|---:|
| New Phase 4B.3 security tests | `python -m pytest -q tests/test_phase4b3_security_assurance.py` | **47 passed, 0 failed** | 0.87s (final) | 0 |
| 4B.1 + 4B.2 + 4B.3 + Hermes contract | `python -m pytest -q tests/test_phase4b1_hermes_adapter.py tests/test_phase4b1_hermes_security_faults.py tests/test_phase4b2_reliability_hardening.py tests/test_phase4b3_security_assurance.py tests/test_hermes_contract.py` | **78 passed, 0 failed** | 1.62s | 0 |
| Relevant SQLite (workstream B context) | `python -m pytest -q tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (10 controlled isolated repeats, default tmp/ntfs3) | **8 passed, 2 failed** (intermittent, see doc 11) | ~0.21–0.39s each | per-run |
| Full AJ regression | `python -m pytest -q` | **503 passed, 13 warnings, 0 failed** | 47.10s | 0 |
| AJ self-check | `python -m aj --check` | **ok true, 23/23 checks, failures [], attached.hermes "NOT ATTACHED"** | n/a | 0 |

## Warnings (pre-existing, unchanged)
- `/usr/lib/python3/dist-packages/gi/overrides/__init__.py:159` `PyGIDeprecationWarning` (GLib.unix_signal_add_full)
- `tests/test_phase3.py` 12× `DeprecationWarning` `multiprocessing/popen_fork.py` fork() in multi-threaded process

## Notes
- Initial 4B.3 run: 5 failures investigated — 1 real redaction weakness fixed, 1 fail-closed hardening applied (empty cli_path), 2 test-expectation corrections (safe symlink outcome, extra fields cannot alter fixed argv), 1 redaction pattern improvement; final rerun **47/47 passed**.
- No existing tests weakened, deleted, or skipped. No intermittent failures in 4B.3/4B.2/4B.1/contract suites observed.
- SQLite concurrency test intermittent in this environment (documented separately; not a 4B.3 regression). Full suite completed 503/0.