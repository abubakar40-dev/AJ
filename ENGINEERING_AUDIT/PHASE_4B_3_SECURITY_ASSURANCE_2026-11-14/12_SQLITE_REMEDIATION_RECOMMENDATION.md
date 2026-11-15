# 12 — SQLite Remediation Recommendation

## Decision
- **Application-level fix justified now:** **No** (not with sufficient evidence of a specific AJ defect and not without risk to correctness/semantics).
- **Status:** investigative conclusion `ROOT_CAUSE_PARTIALLY_IDENTIFIED`; remediation **deferred/conditional**.

## Evidence basis
- Intermittent failures strongly correlate with ntfs3-backed temp storage under concurrent forked WAL writers (4/10 and 2/10 failures in ntfs3 samples; 10/10 pass on tmpfs, 9/10 on ext4 in controlled script runs). Failures include `disk I/O error` (workers often exit 0) and occasional `database is locked`.
- `MemoryStore` already uses WAL, `busy_timeout=30000`, per-process connections, and per-event commit; however all workers concurrently initialize WAL/schema on a new DB (potential contention).
- No deterministic reproduction on a known-good local filesystem; no proof of a single AJ logic bug vs filesystem/locking interaction.

## Why no forced fix now
- Changing journal mode globally, adding blind retries, weakening assertions, or redesigning storage could mask data-integrity issues or alter canonical-memory semantics (append-only, no loss).
- `test_concurrent_memory_writers_keep_every_event` is a valid concurrency invariant; making it pass artificially would be unsafe.

## Recommended next steps (safe, evidence-gated)
1. **Reproduce deterministically:** capture SQLite extended error codes and strace/errno on failure; compare WAL init sequence on ntfs3 vs ext4/tmpfs.
2. **Targeted mitigation candidates (evaluate separately):** initialize DB/schema/WAL once in parent before forking workers; add bounded retry only for clearly transient `SQLITE_BUSY`/`SQLITE_LOCKED` during init/commit with strict limits and tests (not for `SQLITE_IOERR` without cause); document/avoid ntfs-backed temp paths for SQLite WAL stress tests in CI/dev if environment-dependent.
3. **Scope:** keep any change minimal, AJ-only, with deterministic regression coverage and no canonical-memory semantic changes. Do not run filesystem repair or remount operations.

## Operational note
In this environment default TMPDIR resolves to ntfs3; placing pytest temp bases on a local POSIX filesystem (e.g. tmpfs/ext4) eliminated observed failures in sampled runs, supporting an environmental/storage-interaction component without proving exclusivity.