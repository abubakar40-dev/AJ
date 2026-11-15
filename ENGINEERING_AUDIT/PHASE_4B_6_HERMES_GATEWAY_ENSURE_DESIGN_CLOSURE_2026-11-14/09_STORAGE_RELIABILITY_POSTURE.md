# 09 — Storage Reliability Posture (Criterion 8)

## Current evidence (verified/known)
- AJ workspace on **NTFS-mounted** partition (My Drive). 4B.3/4B.5 recorded intermittent `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` failure on NTFS-backed default tmp: `sqlite3.OperationalError: disk I/O error`; repeated successes observed when using `/tmp` on tmpfs in prior investigation. **Root cause not conclusively established** (correlation with ntfs3+WAL/concurrent forked init noted; no deterministic app defect proven). User chose to leave filesystem/config **unchanged**.
- **No filesystem repair, auto-mount, fstab modification, migration, formatting, swap/boot changes, or data moves performed in 4B.6.** A single passing test does **not** establish storage reliability.

## Posture (design, mandatory for any future mutating lifecycle capability)

| Area | Posture / requirement | Current status |
|---|---|---|
| SQLite DB location | Durable AJ lifecycle evidence for mutating ops (e.g. `gateway.ensure`) must reside on **reliable local POSIX storage** with correct locking/WAL/`fsync` semantics (prefer native Linux fs, e.g. tmpfs/ext4 as appropriate for durability needs), not assumed-safe NTFS-backed paths for critical write patterns. | **Not satisfied as demonstrated guarantee** on current workspace/tmp context for WAL-heavy concurrent cases; no migration performed. |
| WAL and shared-memory | Account for `-wal`/`-shm` behavior, directory/fsync semantics, and concurrent writer constraints; avoid relying on NTFS/WAL behavior known to be flaky here. | Risk remains on NTFS-backed paths. |
| Durable evidence writes | Lifecycle side-effect decisions/outcomes must be persisted with clear success/failure of persistence; if persistence fails/uncertain, report `unknown`/persistence-failure condition and **do not** claim durable record or perform unsafe compensating retries. | Design requirement; not validated under faulted storage in this phase. |
| Crash recovery | Evidence/state must support restart reconciliation: detect incomplete ops, re-readback, mark ambiguous outcomes conservatively. | Compatible with AJ invariants; depends on reliable storage. |
| Atomic file replacement | Use atomic rename/replace patterns on filesystems that support them correctly; verify target fs semantics before relying on them for critical evidence. | Must be validated on chosen storage. |
| Backup and restore | Define backup/restore/export for critical evidence/config on reliable media; no silent loss acceptance. | Operational requirement; not implemented/moved. |
| Persistence uncertainty | Explicit first-class outcome: "evidence persistence uncertain/failed" distinct from execution outcome. | Required for mutating lifecycle ops. |
| Recovery after AJ interruption | Reconcile in-flight/ambiguous operations via read-back; never assume commit durability if write errors occurred. | Required; storage-dependent. |

## Implementation condition (blocking for production lifecycle capability)
- **Reliable durable operation cannot be demonstrated in the current NTFS-backed environment for mutating lifecycle evidence** given known intermittent SQLite/WAL I/O errors. Before authorizing production implementation of `hermes.gateway.ensure` (or any mutating lifecycle capability requiring durable AJ evidence), provide:
  1. a storage strategy/location on reliable POSIX storage for required DB/WAL/evidence (without unauthorized destructive moves of existing user data), and
  2. evidence (tests/runs) that persistence and recovery behave reliably under relevant concurrency/write patterns, or explicitly accepted residual risk with compensating controls.
- This is a **separate reliability track**; no unsafe redesign/retries/semantic changes made here.

## Prohibited in this phase (respected)
- No move/copy of existing DBs/data, no mount/fstab/repair/format, no config changes, no claim of reliability from isolated passes.
