# 12 — Test Results

All runs from `AJ/` with `PYTHONDONTWRITEBYTECODE=1` (2026-11-14 environment, default TMPDIR on ntfs3-backed path unless noted).

| # | Suite | Command | Pass | Fail | Warnings | Duration | Exit |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | New Phase 4B.4 tests | *(none added — no gate assumptions required new speculative infra; isolation/authz/evidence behaviors covered by existing suites and source-verified analysis)* | 0 | 0 | 0 | n/a | n/a |
| 2 | Phase 4B.3 security tests | `python -m pytest -q tests/test_phase4b3_security_assurance.py` (included in targeted run) | 47 | 0 | 0 | incl. | 0 |
| 3 | Phase 4B.2 tests | `tests/test_phase4b2_reliability_hardening.py` (targeted) | incl. | 0 | 0 | incl. | 0 |
| 4 | Phase 4B.1 tests | `tests/test_phase4b1_hermes_adapter.py tests/test_phase4b1_hermes_security_faults.py` (targeted) | incl. | 0 | 0 | incl. | 0 |
| 5 | Hermes contract tests | `tests/test_hermes_contract.py` (targeted) | incl. | 0 | 0 | incl. | 0 |
| 6 | Relevant execution/authorization/evidence (security/contract boundary targeted set) | `python -m pytest -q tests/test_phase4b3_security_assurance.py tests/test_phase4b2_reliability_hardening.py tests/test_phase4b1_hermes_adapter.py tests/test_phase4b1_hermes_security_faults.py tests/test_hermes_contract.py` | **78** | **0** | 0 | 1.43s / 1.67s | 0 |
| 7 | Full AJ regression | `python -m pytest -q` | **502** | **1** | **13** | 51.42s | 1 |
| 8 | AJ self-check | `python -m aj --check` | 23 checks ok | 0 | 0 | n/a | 0 (`ok:true`, `failures:[]`, `attached.hermes:"NOT ATTACHED"`) |

## Exact failure (reported honestly, no retry-to-green)
- **FAILED:** `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`
  - Assertion: `assert all(process.exitcode == 0 for process in processes)` → `False`
  - Captured stderr (workers): `sqlite3.OperationalError: disk I/O error` during `MemoryStore` init `PRAGMA journal_mode=WAL` (forked workers, ntfs3-backed tmp: `/run/media/abubakargcx/My Drive/easy-diffusion/tmp/pytest-of-abubakargcx/pytest-189/...`)
  - Context: known intermittent/environment-sensitive (Phase 4B.3 SQLite track, ntfs3+WAL/concurrent init). Not a Hermes/4B.4 regression; no code changes made to storage.

## Warnings (pre-existing)
- `/usr/lib/python3/dist-packages/gi/overrides/__init__.py:159` `PyGIDeprecationWarning: GLib.unix_signal_add_full...`
- `tests/test_phase3.py`: 12× `DeprecationWarning` `multiprocessing/popen_fork.py` fork() in multi-threaded process

## Environment notes
- Targeted Hermes/security suites passed consistently in this phase.
- SQLite concurrency stress behavior remains intermittent on default ntfs3 tmp (see docs 02, 11); individual prior controlled runs documented in Phase 4B.3 docs `10`/`11`.
