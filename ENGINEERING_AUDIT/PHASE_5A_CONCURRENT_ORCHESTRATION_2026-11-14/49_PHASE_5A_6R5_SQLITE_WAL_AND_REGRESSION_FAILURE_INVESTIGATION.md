# 49 — Phase 5A.6R5 SQLite/WAL and Regression Failure Investigation

**Date:** 2026-11-14  
**Scope:** Independent investigation of 5A.6R4 full-suite failure. No user data modified/repaired/migrated; isolated test data only. No test changed to force pass.

## 1. Failure under investigation

- **Reported (5A.6R4):** `576 passed, 1 failed, 13 warnings`
- **Test:** `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`
- **Error:** `sqlite3.OperationalError: disk I/O error` (raised in forked worker during `MemoryStore` init: `PRAGMA journal_mode=WAL`), leading to child `exitcode != 0` and `assert all(process.exitcode == 0 ...)` failure.

## 2. Code/test characteristics (inspected)

- **Test (`tests/test_phase3.py`):** uses `multiprocessing.get_context("fork")`, 4 workers × 20 events each writing to a shared SQLite DB at `tmp_path / "memory.sqlite3"` via `_memory_writer` (creates `MemoryStore(path)` per worker, appends events, closes).
- **Store (`aj/memory.py`):** `sqlite3.connect(path, timeout=30.0, check_same_thread=False)`, sets `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=30000`, executes schema; RLock around operations. Design intends WAL + busy timeout for concurrent appends.

## 3. Locations and filesystem context

| Context | Path(s) observed | Filesystem backing (observed/inferred) | Notes |
|---|---|---|---|
| AJ repo/data dir (config default in `--check`) | `/home/abubakargcx/.local/share/aj` (per `aj --check`) | Linux local path (not NTFS mount path shown) | Not the pytest tmp DB |
| Pytest temp base (environment) | `/run/media/abubakargcx/My Drive/easy-diffusion/tmp` exists; `/home/abubakargcx/easy-diffusion/tmp` exists; `/tmp` exists | `/run/media/.../My Drive/...` indicates mounted external/NTFS-backed path in this environment; `/tmp` is system temp (separate fs) | Full-suite failure stacktrace showed tmp under `/run/media/abubakargcx/My Drive/easy-diffusion/tmp/pytest-of-...` (NTFS-backed) |
| Isolated test DB | `<pytest_tmp>/memory.sqlite3` (+ WAL/SHM side files when WAL active) | Depends on basetemp/tmp location | Test creates DB under provided `tmp_path` |

## 4. SQLite journal/WAL mode

- **Configured by application/store:** `PRAGMA journal_mode=WAL` on `MemoryStore` initialization (`aj/memory.py`).
- **Actual mode during failures:** failure occurred at WAL pragma/init in forked process; exact resulting mode at failure instant not separately instrumented, but WAL is the intended/requested mode and NTFS/WAL interactions are a known sensitivity.

## 5. Reproduction results (isolated, no original data touched)

| Invocation/context | Command | Result | Observation |
|---|---|---|---|
| Test alone (default pytest tmp, repo cwd) | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` | **PASS** (1 passed, ~0.28s) | No failure reproduced in isolation |
| Test alone under `/tmp` basetemp | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --basetemp /tmp/aj_r5_pytest tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` | **PASS** (1 passed, ~0.09s) | No failure reproduced on `/tmp` |
| Full suite (5A.6R4/5A.6R5 context) | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` | **FAIL observed once**: 576 passed, 1 failed, 13 warnings (`disk I/O error` in forked worker, NTFS-backed pytest tmp path in traceback) | Intermittent/environment-sensitive in full-suite load/context |
| Under existing NTFS-backed path (targeted) | Default env pytest tmp resolves to NTFS-backed `/run/media/.../easy-diffusion/tmp` in observed runs; isolated targeted run passed but prior full-suite run on same fs class failed | **Inconclusive / intermittent** | Sensitivity appears load/timing/context-dependent rather than deterministic per single run |

## 6. Assessment

- **Reproduces when run alone:** not reproduced in 5A.6R5 isolated runs (passed).
- **Reproduces in full suite:** observed in full-suite run (5A.6R4/5A.6R5 record) but not deterministically isolated.
- **Under `/tmp`:** passed (isolated).
- **Under NTFS-backed path:** failure previously manifested on NTFS-backed pytest tmp during full suite; isolated run on similar context passed → inconclusive/intermittent.
- **Likely contributing factors (evidence-consistent, not conclusively proven):** filesystem semantics/behavior of NTFS-backed storage for SQLite WAL with concurrent multiprocessing (`fork`) writers under suite load/contention, potential initialization/race sensitivity in WAL setup across forked processes, and/or environment/test-isolation pressure during full suite. Application-level logic change from 5A.6R4 (delegation/orchestrator/anomaly/docs/tests) is **not indicated** by traced modifications.
- **Cannot conclusively attribute to:** a specific AJ application bug vs filesystem/concurrency/runtime interaction from available evidence.

## 7. Disposition

- **Status:** **OPEN** (not conclusively diagnosed). Failure is real in observed full-suite context but intermittent and environment/storage-sensitive.
- **Actions taken:** read-only investigation and isolated reproductions only. No filesystem repair/remount/reformat/migration, no user DB/app data modification, no test alteration.
- **Implication:** full-suite "green" cannot be claimed as stable in this environment without further controlled diagnosis/remediation decision; does not invalidate focused 5A.4–5A.6R4 regression results (65 passed) but remains a release/acceptance risk signal consistent with known NTFS/SQLite-WAL concerns.
