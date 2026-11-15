# SQLITE_DISPOSITION (S0 E6, read-only investigation)

## 1) Facts (observed)

### `aj/memory.py` (lines 95–130, verbatim context recorded)
- `sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)` then `row_factory` set.
- Under `_lock`: executes `PRAGMA journal_mode=WAL` (line 116), then `PRAGMA busy_timeout=30000` (117), then `executescript(_SCHEMA)` (118), then `commit()`.
- **Order:** Python `sqlite3.connect(..., timeout=30.0)` is set at connection creation; **`PRAGMA journal_mode=WAL` is executed before `PRAGMA busy_timeout=30000`** is set in this sequence (busy_timeout PRAGMA comes after WAL pragma). No read-first/check of existing journal_mode before setting WAL; no retry/backoff on locked/disk I/O.

### Environment
- `env | grep -i tmp` (this session): `TMPDIR=/home/abubakargcx/easy-diffusion/tmp` (also other tmp-related vars present, e.g. GNOME_SETUP_DISPLAY path). `TMPDIR` was set in environment.

### Prior controlled matrix (round 2, `sqlite_wal_matrix_results.json`/summary, `sqlite3 3.46.1`)
- Path types: `/tmp` tempdir on tmpfs, ext4 under `~` (`/dev/sda2`), `/dev/shm` tmpfs, NTFS workspace (`/dev/sda4 ntfs3`). Variants: fork×4 no-precreate, fork×4 precreate WAL in parent, 1 process, spawn×4; 20 runs/cell.
- **Single-process (`v3`)**: 20/20 pass on all path types.
- **NTFS workspace (concurrent)**: v1 9/20, v2 17/20, v4 15/20. First failures sampled: `sqlite3.OperationalError: disk I/O error` at `aj/memory.py:116` (`PRAGMA journal_mode=WAL`), journal_mode readback `wal`, integrity `ok` in sampled record.
- **tmpfs/dev_shm (concurrent, some variants):** intermittent `database is locked` at/around WAL init in sampled failures.
- **Real AJ memory config:** `core.memory_path=""`, `core.data_dir="/home/abubakargcx/.local/share/aj"` on ext4 home (not NTFS workspace).

### E6 targeted runs (this round, no edits) — `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`, 10 runs each
| Condition | Pass | Fail | Evidence |
|---|---:|---:|---|
| Default env TMPDIR (`/home/abubakargcx/easy-diffusion/tmp` in shell env) | 8 | 2 | `E6_ntfs_default_tmpdir.json` (failures at runs 4,6; rc=1) |
| `TMPDIR=/tmp` | 10 | 0 | `E6_ntfs_tmpdir_tmp.json` |

**Caveat (fact):** pytest `tmp_path` location is controlled by pytest basetemp/config and may differ from `TMPDIR`; these results are recorded as-run under the specified env vars without asserting tmp_path filesystem equivalence. Earlier full-suite failures showed NTFS workspace basetemp paths (`/run/media/.../easy-diffusion/tmp/pytest-of-*`) producing `disk I/O error` at `memory.py:116`.

### Full-suite observations (this environment)
- Baseline context: 577 passed / 13 warnings (intermittent history for the concurrent memory writer test noted).
- Round 3 before D-001 (clean snapshot): 576 passed, 1 failed (`test_concurrent_memory_writers_keep_every_event`, `disk I/O error` at `memory.py:116`, NTFS tmp), 13 warnings.
- Round 3 after D-001 (existing tests): 577 passed, 13 warnings (same test passed in that run).

## 2) Labelled hypotheses (not proven)
- **H1 (storage/FS sensitivity):** NTFS `ntfs3` + SQLite WAL/shared-memory/locking semantics under multi-process concurrent init/writes is a likely contributor to `disk I/O error` seen at WAL pragma/init on workspace paths. **Hypothesis, not attributed to AJ logic defect.**
- **H2 (init ordering/contention):** `PRAGMA journal_mode=WAL` executes before `PRAGMA busy_timeout=30000` is set (connect timeout exists but busy handler/timeout PRAGMA ordering differs), which may increase sensitivity to lock contention at WAL setup under concurrency. **Hypothesis.**
- **H3 (TMPDIR/tmp location correlation):** improved pass rate with `TMPDIR=/tmp` in targeted runs may correlate with different temp placement or reduced contention; because pytest tmp_path/basetemp behavior not proven identical to `TMPDIR`, causality is **unproven**.
- **H4 (fork/multi-process semantics):** concurrent forked access patterns can interact with sqlite connections/file locks differently across filesystems; pre-creating WAL reduced but did not eliminate NTFS failures in matrix (sample). **Hypothesis.**

## 3) Planned S5 experiments (no fix in S0)
- **Read-before-set WAL:** check current `journal_mode` first; set `PRAGMA journal_mode=WAL` only if not already `wal` (idempotent/reduced contention on reopen).
- **Ordering/hardening:** ensure effective busy timeout/handler is in place for initialization path as appropriate (evaluate `connect timeout`, `busy_timeout` PRAGMA timing, and `sqlite3_busy_timeout` API) — **design only, not implemented**.
- **Retry with backoff:** bounded retry on transient `database is locked` / `disk I/O error` during WAL init/open with jittered backoff and explicit failure classification; must not mask persistent corruption or broaden claims.
- **Controlled reruns:** repeat matrix on NTFS, ext4, tmpfs with/without precreated WAL, fork vs spawn, and with pytest basetemp pinned per filesystem to remove TMPDIR ambiguity; capture first-failure traceback, errno where available, and journal_mode.
- **Disposition goal:** evidence-backed attribution or explicit bounded limitation (e.g. NTFS workspace not a supported path for concurrent WAL-backed memory store) — to be decided in S5 with proof.

## 4) Disposition (S0)
**OPEN (T-12 / Doc 54 §16).** Facts recorded; hypotheses labelled; no `aj/memory.py` changes made. Not sufficient to claim product defect fix or universal reliability; real AJ default data dir observed on ext4 home.
