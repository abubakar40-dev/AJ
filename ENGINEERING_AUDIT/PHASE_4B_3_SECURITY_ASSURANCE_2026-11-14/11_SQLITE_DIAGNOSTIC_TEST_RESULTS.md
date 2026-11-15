# 11 — SQLite Diagnostic Test Results

## Environment
- Host: Ubuntu Linux (local workspace), Python 3.14, pytest 9.2.0
- `TMPDIR=/home/abubakargcx/easy-diffusion/tmp` (`tempfile.gettempdir()` same)
- Default tmp FS: `/dev/sda4` **ntfs3** mounted at `/run/media/abubakargcx/My Drive` (`rw,nosuid,nodev,relatime,uid=1000,gid=1000,acl,iocharset=utf8,prealloc`, ~35% used)
- `/tmp`: **tmpfs**; `/home/abubakargcx/.cache`: `/dev/sda2` **ext4**
- Command form: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q ...` from `AJ/`

## Actual test: `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`
Behavior: 4 forked workers × 20 `MemoryStore.append_event` commits into one SQLite DB (WAL, busy_timeout 30000), then verify 80 events/unique IDs/integrity.

### Pytest runs (default TMPDIR, ntfs3)
| Batch | Run | Result | Time | Exit |
|---|---:|---|---:|---:|
| default | 1 | PASS | 0.36s | 0 |
| default | 2 | PASS | 0.51s | 0 |
| default | 3 | PASS | 0.32s | 0 |
| default | 4 | PASS | 0.32s | 0 |
| default | 5 | PASS | 0.32s | 0 |
| controlled | 1 | PASS | 0.29s | 0 |
| controlled | 2 | FAIL | 0.32s | 0* |
| controlled | 3 | PASS | 0.39s | 0 |
| controlled | 4 | PASS | 0.34s | 0 |
| controlled | 5 | PASS | 0.32s | 0 |
| controlled | 6 | PASS | 0.38s | 0 |
| controlled | 7 | PASS | 0.31s | 0 |
| controlled | 8 | PASS | 0.36s | 0 |
| controlled | 9 | FAIL | 0.30s | 0* |
| controlled | 10 | PASS | 0.34s | 0 |

\*pytest reported failure in output; shell loop captured tail/EC per command context as shown in session (`1 failed...`). Aggregate in this sample: **13/15 passed, 2/15 failed** (intermittent).

### Pytest runs (`--basetemp=/tmp/ajpytest43`, tmpfs)
| Run | Result | Time |
|---:|---|---:|
| 1 | PASS | 0.18s |
| 2 | PASS | 0.19s |
| 3 | PASS | 0.18s |
| 4 | PASS | 0.21s |
| 5 | PASS | 0.17s |

**5/5 passed.**

### Controlled script reproductions (disposable `MemoryStore`, same concurrency pattern)
Command pattern: inline Python creating disposable temp dir on base FS, 4 fork workers × 20 appends, verify count/integrity.

| Base FS | Runs | Pass | Fail | Failure evidence |
|---|---:|---:|---:|---|
| ntfs3 (`/home/abubakargcx/easy-diffusion/tmp`) | 10 | 6 | 4 | `('err', 'OperationalError: disk I/O error')`, worker exit codes `[0,0,0,0]` (failures at post-write open/verify in 4 runs) |
| tmpfs (`/tmp`) | 10 | 10 | 0 | — |
| ext4 (`/home/abubakargcx/.cache`) | 10 | 9 | 1 | worker-reported `OperationalError: database is locked` |

## Additional observation
- Earlier session runs also surfaced `sqlite3.OperationalError: disk I/O error` / `database is locked` in forked workers during init/WAL setup on ntfs3-backed temp paths.
- Full AJ regression completed **503 passed, 13 warnings, 0 failed** with this test passing in that run (intermittency remains). No silent rerun-to-green masking; all observed outcomes recorded.