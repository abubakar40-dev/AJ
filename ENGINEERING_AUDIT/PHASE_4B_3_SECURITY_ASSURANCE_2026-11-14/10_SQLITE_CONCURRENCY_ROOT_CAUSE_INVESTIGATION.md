# 10 — SQLite Concurrency Root-Cause Investigation

## Scope and status
**Investigation status:** `ROOT_CAUSE_PARTIALLY_IDENTIFIED` (strong filesystem/WAL-sensitivity evidence + reproducible intermittency pattern; no single universally proven application defect, and an application-level fix not justified within safety constraints).

Target: `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` (intermittent `sqlite3.OperationalError: disk I/O error` / occasionally `database is locked` observed).

## 1. Actual test behavior (inspected)
- **File:** `AJ/tests/test_phase3.py` (lines ~233–285 in current file)
- **Flow:** creates `tmp_path/memory.sqlite3`; spawns 4 worker processes via `multiprocessing.get_context("fork")`, each running `_memory_writer(path, 20)`; joins (30s); asserts all exit codes 0; reopens `MemoryStore(path)` and asserts 80 events, unique IDs, `verify()["ok"]`.
- **Worker:** `store = MemoryStore(path)`; loop `append_event("probe", f"event {i}", source="worker")` 20×; `store.close()`.
- **MemoryStore (`AJ/aj/memory.py`):** per-process `sqlite3.connect(path, timeout=30.0, check_same_thread=False)`; per-instance `threading.RLock`; on init executes `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=30000`, `executescript(_SCHEMA)`, commit. Each `append_event` inserts and commits under lock. No explicit retry logic; no connection sharing across processes (each worker constructs its own store).
- **Concurrency model:** 4 separate processes, each with independent connection, concurrently initializing/opening (WAL/schema) and writing/committing to same DB file. Fork-based multiprocessing.

## 2. Environment/filesystem evidence (actual)
| Location | Filesystem | Evidence |
|---|---|---|
| `/home/abubakargcx/easy-diffusion/tmp` (default TMPDIR/tempfile; pytest tmp base in this env) | `/dev/sda4` **ntfs3** `rw,nosuid,nodev,relatime,uid=1000,gid=1000,acl,iocharset=utf8,prealloc` (~35% used) | Symlink: `/home/abubakargcx/easy-diffusion -> /run/media/abubakargcx/My Drive/easy-diffusion` |
| `/run/media/abubakargcx/My Drive/easy-diffusion/tmp` | same ntfs3 mount | same device |
| `/tmp` | **tmpfs** | 10/10 controlled script runs passed |
| `/home/abubakargcx/.cache` | `/dev/sda2` **ext4** `rw,relatime` | 9/10 controlled script runs passed (1 lock error) |
| `/home/abubakargcx` | ext4 | host home root |

Disk/inode space adequate on observed mounts during tests (not exhausted).

## 3. Controlled reproduction (disposable DBs, individual results)

### A. Direct script reproductions (4 workers × 20, fork, `MemoryStore`, per-run disposable temp dir)
| Base | FS | Runs | Pass | Fail | Failure modes (observed) |
|---|---|---:|---:|---:|---|
| `/home/abubakargcx/easy-diffusion/tmp` (DEFAULT_TMPDIR) | ntfs3 | 10 | 6 | 4 | post-writer verify/open: `OperationalError: disk I/O error` (all workers exit 0) |
| `/tmp` | tmpfs | 10 | 10 | 0 | — |
| `/home/abubakargcx/.cache` | ext4 | 10 | 9 | 1 | worker-reported `OperationalError: database is locked` |

### B. Actual pytest test `test_concurrent_memory_writers_keep_every_event`
| Context | Base FS | Runs | Pass | Fail | Notes |
|---|---|---:|---:|---:|---|
| Default pytest tmp (TMPDIR on ntfs3) | ntfs3 | 5 | 5 | 0 | batch 1 |
| `--basetemp=/tmp/ajpytest43` | tmpfs | 5 | 5 | 0 | batch 2 |
| Default tmp | ntfs3 | 10 | 8 | 2 | runs 2,9 failed; runs 1,3-8,10 passed (intermittent) |
| Earlier 4B.2/4B.3 session observations | ntfs3/default | multiple batches | mixed | mixed | included `disk I/O error` and `database is locked` in worker/fork contexts |

(Individual timings in doc 11.)

## 4. Execution flow / shared state
- **DB:** one SQLite file per test run (`memory.sqlite3`) plus WAL/SHM sidecars when in WAL mode.
- **Connections:** separate connection per worker process (and separate in parent verify phase); no cross-process connection sharing.
- **Initialization race:** each worker independently sets `journal_mode=WAL` and runs `executescript(_SCHEMA)` on first open; concurrent DDL/WAL setup on a new DB can contend.
- **Transactions:** each append is a single insert+commit (autocommit-like per event pattern in code) under process-local lock; writers serialize via SQLite locks/busy_timeout.
- **Fork:** uses `fork` context (warnings emitted in suite due to multi-threaded test runner environment), which is common in this test suite but can inherit state in general; MemoryStore creates fresh connections in worker function.

## 5. Ranked hypotheses and evidence

| Rank | Hypothesis | Supporting evidence | Contradicting/limits | Confidence |
|---:|---|---|---|---|
| 1 | **NTFS3 + SQLite WAL/shared-memory locking sensitivity** causes intermittent `SQLITE_IOERR` (`disk I/O error`) on default tmp | 4/10 and 2/10 failures on ntfs3; 10/10 passes on tmpfs; ntfs3 mount used for default TMPDIR; workers exit 0 but DB open/verify fails in one reproduction pattern | Not every ntfs3 run fails (intermittent); exact ntfs3 lock opcode not captured | **Medium-High** (environmental/storage-interaction) |
| 2 | **Concurrent initialization/WAL-mode setup contention** under fork+multi-process on new DB can surface as `database is locked` or I/O errors depending on FS | `database is locked` observed on ext4 once and in prior sessions; all writers hit init/schema/WAL concurrently; busy_timeout configured but first-open WAL/DDL contention can be sensitive | Many runs pass on ext4/tmpfs with same code; no deterministic repro | **Medium** |
| 3 | **Fork-in-multithreaded-process test environment effects** (pytest runtime threads) interacting with SQLite/file descriptors | Deprecation warnings present; fork used by design in this suite | Same pattern used elsewhere; failures correlate more with FS in script comparison | **Low–Medium** |
| 4 | Underlying disk/media error or space exhaustion | Disk I/O error string | Space/inodes sufficient; failures intermittent and FS-dependent | **Low** |

## 6. Conclusion
- **Actual DB path in this environment:** pytest temp dirs created under `/home/abubakargcx/easy-diffusion/tmp` → resolves to `/run/media/abubakargcx/My Drive/easy-diffusion/tmp` on **ntfs3** (`/dev/sda4`) when using default TMPDIR.
- **Reproduction:** intermittent failures reproduced in controlled runs on ntfs3 (and occasionally lock errors on ext4); not reproduced on tmpfs in 10/10 runs.
- **Root cause:** **partially identified** — strong evidence that filesystem/WAL locking behavior on ntfs3 (and, secondarily, concurrent init contention) materially contributes to intermittency. No single definitive application-level defect proven; MemoryStore already uses WAL + busy_timeout + per-op commit, but concurrent first-open/schema/WAL setup remains a plausible sensitivity.
- **Application fix justified now?** **No (not narrowly established).** Forcing a global journal-mode change, disabling WAL, adding blind retries, or redesigning storage would risk correctness/semantics and is out of scope. A safe, evidence-backed minimal fix would require first isolating a specific defect (e.g. init serialization strategy) with deterministic reproduction on supported filesystems; not achieved here. Recommended: treat as environment-sensitive for ntfs-backed temp paths and consider targeted follow-up (e.g. init retry on `SQLITE_BUSY`/specific I/O cases, or ensure schema/WAL initialized once before forked writers) only with deterministic regression coverage. See doc 12.