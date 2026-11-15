# 07 SQLite/WAL Evidence (read-only, non-destructive)

## Failing test identity (verified)

- **Test:** `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`
- **Behavior (source-inspected):** 4 worker processes × 20 writes into shared `MemoryStore(db)` SQLite file (`store.record(...)`), fork multiprocessing, WAL-related context typical for concurrent writers. (`tests/test_phase3.py`)

## Filesystem / mount / path evidence

Commands:
- `findmnt -T .`
- `findmnt -T /tmp`
- `findmnt -T /home/abubakargcx/easy-diffusion/tmp`
- `findmnt -T "/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp"`
- `stat -f . /tmp /home/abubakargcx/easy-diffusion/tmp "/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp"`
- `df -T . /tmp`
- `python3 -c "import tempfile, sqlite3; print(tempfile.gettempdir()); print(sqlite3.sqlite_version)"`

| Path | Source/FSType | Mount options (observed) | `stat -f` type |
|---|---|---|---|
| AJ root | `/dev/sda4` / `ntfs3` | `rw,nosuid,nodev,relatime,uid=1000,gid=1000,acl,iocharset=utf8,prealloc` | `UNKNOWN (0x7366746e)` |
| Default temp base `tempfile.gettempdir()` = `/home/abubakargcx/easy-diffusion/tmp` | `/dev/sda4` / `ntfs3` (same mount) | same as above | `UNKNOWN (0x7366746e)` |
| NTFS basetemp used | `/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp` | same NTFS mount | `UNKNOWN (0x7366746e)` |
| `/tmp` | `tmpfs` / `tmpfs` | `rw,nosuid,nodev,nr_inodes=1048576,inode64,usrquota` | `tmpfs` |

- **SQLite version (runtime):** `3.46.1`
- **Python:** `3.14.4`, **Kernel:** `Linux 7.0.0-43-generic x86_64 GNU/Linux`

## SQLite PRAGMA / WAL-SHM behavior (probe)

Command (on default tempdir DB, created/closed immediately):
```python
import sqlite3, tempfile, os
db=os.path.join(tempfile.gettempdir(),'_ajctx_pragma.db')
con=sqlite3.connect(db); cur=con.cursor()
for p in ['journal_mode','locking_mode','synchronous','wal_autocheckpoint']:
    cur.execute(f'PRAGMA {p}'); print(p, cur.fetchone())
```
Observed:
- `journal_mode ('delete',)` (default for fresh connection before WAL explicitly enabled by app code, if any)
- `locking_mode ('normal',)`
- `synchronous (2,)` (FULL)
- `wal_autocheckpoint (1000,)`

> Note: `aj/memory.py::MemoryStore` may set pragmas/modes at runtime; exact runtime pragmas during concurrent test were **not** separately traced in this pass (UNVERIFIED). WAL/SHM files may appear transiently during WAL mode use (not directly observed/recorded here).

## Exact failing line / initialization

From captured tracebacks (`_context_pack/_tmp_sqlite_runs.txt`):
- `FAILED tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event - sqlite3.OperationalError: disk I/O error`
- Stack reaches `aj/memory.py", line 162, in __init__` calling `conn.executescript(_SCHEMA)` inside forked worker `MemoryStore` initialization (schema creation/exec path).

`MemoryStore.__init__` path (source, `aj/memory.py:~90-170+`): opens/connects SQLite DB, configures connection, and executes schema script (`executescript(_SCHEMA)`) to initialize tables/indexes (exact pragma/journal setup in code not exhaustively re-documented here).

## Fork vs spawn behavior in test

- Test uses `multiprocessing` with fork-style process creation in this environment (warnings observed in full suite: `popen_fork.py:70 ... multi-threaded, use of fork() may lead to deadlocks in the child`; 12 warnings from `tests/test_phase3.py`).
- Each worker constructs `MemoryStore` against shared DB path and performs writes (per test design). Fork + shared SQLite/WAL state on certain filesystems can be sensitive (**HYPOTHESIS**: NTFS/locking/IO semantics interaction).

## `ntfsfix -n` (non-destructive check)

Command: `ntfsfix -n /dev/sda4 2>&1`  
Result:
```
Refusing to operate on read-write mounted device /dev/sda4.
EXIT:0
```
- **No repair performed.** Read-only probe was refused due to mounted RW state (no sudo/destructive action taken). **SKIPPED** as effective read-only diagnostic beyond refusal message.

## Controlled repeatability runs (this session)

**Commands executed:**
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` ×5 (default)
- `... --basetemp /tmp/aj-pytest-basetmp` ×5
- `... --basetemp "/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp"` ×5

**Results (from `_context_pack/_tmp_sqlite_runs.txt`):**

| Basetemp/location | Total | Pass | Fail | Pattern |
|---|---:|---:|---:|---|
| default (resolved to NTFS-backed `/home/abubakargcx/easy-diffusion/tmp` in this env) | 5 | 2 | 3 | intermittent fails (runs 1,2,4 failed; 3,5 passed) |
| `/tmp/aj-pytest-basetmp` (tmpfs `/tmp`) | 5 | 5 | 0 | all passed in this batch |
| NTFS approved basetemp `/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp` | 5 | 4 | 1 | mostly pass, run 5 failed |

**State:** **repeatable as environment/storage-sensitive/intermittent** in controlled samples (not always failing, not never). Full-suite single run in this session passed (577/577) while isolated targeted run showed intermittent default failures and NTFS-basetemp failure.

## Hypotheses (labeled)

- **HYPOTHESIS:** Failure correlates with storage backend/filesystem semantics and/or temp location (NTFS vs tmpfs) under forked concurrent SQLite initialization/writes (`disk I/O error` at schema init).
- **HYPOTHESIS:** Fork-with-threads + SQLite/WAL/locking behavior may contribute to intermittency; not proven.
- **HYPOTHESIS:** Prior full-suite failure (576 passed, 1 failed, 13 warnings) may reflect load/timing/environment sensitivity rather than deterministic product defect; **not concluded**.

## Disposition (evidence-based, non-conclusive)

- **OPEN ISSUE.** Cause/attribution (product defect vs filesystem/env/test harness interaction) **not conclusively diagnosed**.
- Isolated passes do **not** establish full-suite stability; this session’s full-suite pass does **not** disprove prior/intermittent failures.
- No filesystem repair performed; no test weakened/skipped/edited.
