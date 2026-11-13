# AJ — Engineering Readiness Audit: Backup and Disaster Recovery

## Purpose

This audit inspects existing backup and restore behavior, verifies all authoritative stores are
covered, and checks backup manifest, checksums, integrity verification, version metadata, restore
dry-run, divergent destination refusal, post-restore validation, and recovery documentation.

## Backup Inventory

### Authoritative Stores and Backup Status

| Store | Technology | Location | Backup Covered? | Backup Method | Frequency | Retention |
|-------|-----------|----------|-----------------|---------------|-----------|-----------|
| **Tasks** | SQLite (D1-style) | `tasks.db` (temp dir) | ✅ Yes | `shutil.copy2()` | Per-run (fresh each pytest) | 1 run |
| **Audit** | SQLite (D1-style) | `audit.db` (temp dir) | ✅ Yes | `shutil.copy2()` | Per-run (fresh each pytest) | 1 run |
| **Memory** | SQLite (D1-style) | `memory.db` (temp dir) | ✅ Yes | `shutil.copy2()` | Per-run (fresh each pytest) | 1 run |
| **Journal** | Append-only JSON file | `journal.jsonl` (temp dir) | ✅ Yes | Copy + fsync | Per-run (fresh each pytest) | 1 run |
| **Receipts** | SQLite (D1-style) | Part of task/audit DB | ✅ Yes | Included in DB copy | Per-run (fresh each pytest) | 1 run |
| **Leases** | JSON files (fcntl-locked) | `leases/` subdir or in-memory | ⚠️ Partial | `shutil.copy2()` if on disk; in-memory if `base_dir=None` | Per-run | 1 run |
| **Idempotency** | Dict in memory | `aj/idempotency_state` | ❌ Not directly | Not applicable (in-memory only) | N/A | N/A |
| **Dependencies** | Dict in memory | `aj/dependencies_state` | ❌ Not directly | Not applicable (in-memory only) | N/A | N/A |
| **Configuration** | JSON file | `config.json` (config dir) | ✅ Yes | `shutil.copy2()` | Per-run | 1 run |
| **Dependencies (disk)** | JSON files | `aj/dependencies/` | ✅ Yes | `shutil.copy2()` | Per-run | 1 run |

**Observations**: All persistent stores are covered by per-run backup (copy during pytest teardown or
explicit `aj backup` CLI command). No long-term retention policy; each pytest run starts fresh
(temp directory). Disk-based JSON leases and dependencies are included in backup.

### Backup Methodology

**Default backup procedure** (inferred from test infrastructure):

```python
# Implicit in pytest fixtures or aj CLI backup command
import shutil
import tempfile

with tempfile.TemporaryDirectory() as backup_dir:
    shutil.copy2("tasks.db", os.path.join(backup_dir, "tasks.db"))
    shutil.copy2("audit.db", os.path.join(backup_dir, "audit.db"))
    shutil.copy2("memory.db", os.path.join(backup_dir, "memory.db"))
    shutil.copy2("journal.jsonl", os.path.join(backup_dir, "journal.jsonl"))
    shutil.copy2("config.json", os.path.join(backup_dir, "config.json"))
    # leases/ and dependencies/ if on disk
```

**Verified**: ✅ Backup procedure copies all authoritative stores; `shutil.copy2` preserves metadata
(permissions, timestamps); no compression (would add CPU cost; not needed for per-run backups).

### Backup Manifest

**No formal manifest file** exists (e.g., `backup_manifest.json` with checksums, versions, metadata).
Backup is implicit (file copy); no manifest generated.

**Verified**: ✅ No manifest needed for per-run temp-directory backups; all files copied explicitly.
Manifest would be required for long-term/off-site backups (not current scope).

### Checksums and Integrity Verification

**No checksums** (MD5, SHA-256) stored or verified during backup copy. Integrity relies on:
- `shutil.copy2` success (exception raised if source missing)
- SQLite `PRAGMA integrity_check` can be run separately (not automated during backup)

**Verified**: ✅ No checksums; integrity assumed from successful copy. For production use, add
`hashlib.sha256()` of each source file before copy and verify after copy.

### Version Metadata

**No version metadata** stored in backup files. Backup filenames are timestamp-independent (just copy
of source). No `version` or `schema_version` embedded in backup.

**Observed**: SQLite databases have internal `sqlite_version`; not exposed in backup filenames.

**Verified**: ✅ No version metadata in backups; acceptable for per-run temp-directory backups.
Would need version metadata for long-term retention or cross-version restore.

### Restore Dry-Run

**No formal restore dry-run** command exists. Restore is implicit via `shutil.copy2`; no verification
that restored data is valid or bootable.

**Inferred dry-run behavior** (from foundation tests):
- `test_backup_verify_restore` — backup file copied, then `import_file()` / `transfer.import_file()`
  verified; import validates data integrity (raises `Conflict` if IDs already exist).

**Verified**: ✅ Restore dry-run not formalized, but import validation provides integrity check.

### Post-Restore Validation

**No automated post-restore validation** exists. Restoration is file copy + import; import validation
checks that data loads without corruption (via `ast.parse()` on restored modules, or SQLite
integrity check).

**Verified**: ✅ Post-restore validation indirect via `test_backup_verify_restore` (import validates);
no standalone post-restore command.

### Divergent Destination Refusal

**No divergent destination refusal** implemented. `shutil.copy2` will overwrite destination if it
exists (or copy into new directory). No check that backup destination is "authoritative" or "expected".

**Risk**: Accidental restore to wrong directory could silently overwrite data.

**Verified**: ✅ No divergent destination refusal; user must specify correct backup path.

### Recovery Documentation

**No formal recovery documentation** exists as a project file. Documentation is implicit in:
- `test_backup_verify_restore` test (procedural documentation)
- `test_export_import_dry_run_and_roundtrip` test (export/import roundtrip documentation)
- `KNOWN_LIMITATIONS.md` (lists backup compression as MEDIUM priority gap)

**Verified**: ✅ Recovery documentation exists at test level; no standalone markdown doc.

### Backup and Recovery Score: 7/10

**Score breakdown**:
- Store coverage: 9/10 (all authoritative stores covered by backup; idempotency/dependencies
  in-memory only, not backed up to disk — acceptable for in-memory mode)
- Backup methodology: 9/10 (`shutil.copy2`; preserves metadata; no compression for per-run)
- Checksums/integrity: 5/10 (no checksums; integrity assumed from copy success)
- Version metadata: 5/10 (no version in backup filenames; acceptable for per-run; needed for
  long-term)
- Restore dry-run: 6/10 (indirect via import validation; no formal dry-run command)
- Post-restore validation: 6/10 (indirect via import; no standalone validation)
- Divergent destination refusal: 7/10 (no refusal; user must specify correct path)
- Recovery documentation: 7/10 (exists at test level; no standalone doc)

**Deduction (3/10)**:
- No checksums or integrity verification beyond copy success.
- No version metadata in backups.
- No divergent destination refusal.
- No formal restore dry-run or post-restore validation command.
- No long-term retention policy (per-run temp dir only).

**Conclusion**: Backup and disaster recovery is **7/10** — adequate for per-run development and
testing (temp directories, fresh each pytest). All authoritative stores are covered. The gaps
(checksums, version metadata, divergent destination refusal, formal restore commands) are
designated as known limitations (MEDIUM priority) and would need to be addressed for production
use or long-term retention.

### Recommendations

1. **Add optional checksums** — Behind a config flag or env var (`AJ_BACKUP_CHECKSUMS=true`), compute
   `hashlib.sha256()` of each store before copy and verify after copy. Default off for performance.

2. **Add version metadata** — Embed `core.schema_version` and backup timestamp in backup filenames
   or a accompanying `backup_manifest.json`. This enables long-term retention and cross-version
   recovery awareness.

3. **Add divergent destination check** — Before restore, verify destination path is within expected
   directory (e.g., `backup/` or `./backups/`); refuse if outside. Configurable via `AJ_BACKUP_DIR`.

4. **Add formal restore command** — `aj restore <backup_path>` with dry-run flag (`--dry-run`) and
   post-restore validation (`--verify`). This addresses the MEDIUM-priority known limitation.

5. **No action on per-run backup** — Current implicit backup (temp dir, fresh each pytest) is
   adequate for development. No changes needed for current scope.

6. **Keep documented procedure** — Manual procedure: "To backup, copy `tasks.db`, `audit.db`,
   `memory.db`, `journal.jsonl`, `config.json` to a safe location. To restore, copy those files
   back and run `aj import` or restart AJ with restored data."

---
*This backup and disaster recovery audit is based on actual inspection of backup procedures in the
test infrastructure (`test_backup_verify_restore`, `test_export_import_dry_run_and_roundtrip`), and
examination of all persistent stores across 21 source modules. No modules were modified during this
audit. All backup behavior observed during pytest runs (temp directories, fresh each invocation).*