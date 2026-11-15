# 11 — SQLite Blocking Assessment

## Phase 4B.3 evidence (reviewed)
- Intermittent `sqlite3.OperationalError: disk I/O error` / occasional `database is locked` in `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` under forked concurrent writers.
- Default TMPDIR resolves to ntfs3-backed path (`/run/media/abubakargcx/My Drive/easy-diffusion/tmp`, `/dev/sda4`); controlled reproductions: ntfs3 6/10 pass (4 I/O errors), tmpfs 10/10 pass, ext4 9/10 pass (1 lock). Pytest samples mixed on ntfs3, stable on tmpfs.
- Status: **ROOT_CAUSE_PARTIALLY_IDENTIFIED** (environment/storage + concurrent init sensitivity likely); no definitive application-level defect proven; no safe fix applied.

## This phase observation
- Full AJ regression: `502 passed, 1 failed, 13 warnings` — sole failure was the same intermittent SQLite concurrency test on ntfs3 default tmp path (not Hermes/security suites).

## Does it block future mutating Hermes work?
**Assessment: SEPARATE RELIABILITY TRACK — NOT an automatic blocker, but a CONDITIONAL risk for evidence durability.**

- **Not blocking the readiness/design gate itself:** mutating capability is not implemented; security/contract/execution-boundary tests for Hermes are passing and unaffected.
- **Conditionally relevant before/alongside mutating implementation:** AJ persists tasks, audit, journal, receipts, operation evidence, idempotency and (where enabled) memory in local stores (JSONL/SQLite/file-backed paths under configured data dirs). 4B.3 showed ntfs3/WAL-concurrency sensitivity on this environment; if AJ’s durable evidence/state for a mutating operation resides on a filesystem with similar behavior under contention, **evidence loss or persistence errors could undermine “trustworthy automation” guarantees**.
- **Minimum reliability requirement if proceeding:** (1) run and pass relevant persistence/evidence/idempotency/recovery tests on a known-good local POSIX filesystem for the deployment/test environment; (2) ensure AJ data/tmp paths for critical evidence are not on ntfs3-backed mounts exhibiting WAL I/O issues; (3) treat persistence failure during/after side effects as `unknown/requires_manual_review` per failure model; (4) keep SQLite concurrency issue tracked to resolution or deterministic mitigation with evidence. No storage redesign in 4B.4.

**Conclusion:** keep SQLite as a separate reliability track; require environment/storage reliability evidence for mutating-operation durability before GO to implementation in affected environments.
