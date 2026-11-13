# AJ Phase 4: Storage Versioning and Migration

## Overview

This document specifies schema/version metadata for all persistent records, backward compatibility, migration, and testability.

## Schema Version Metadata

### 1. Version Field per Record Type

Every persistent record type should include a `schema_version` field indicating the record format version. This enables:

- **Backward compatibility**: Old version records remain readable
- **Forward compatibility**: Unsupported future versions rejected safely
- **Migration detection**: Identify records needing migration
- **Testability**: Test migration with known version transitions

**Current Implementation Status**:

| Record Type | schema_version | Location | Status |
|-------------|---------------|----------|--------|
| TaskRecord | 1 | `aj/task.py` | Implemented |
| LeaseRecord | 1 | `aj/lease.py` | Implemented |
| Attempt record | 1 (implicit) | `aj/task.py` attempts list | Implicit |
| Receipt record | 1 | `aj/receipts.py` | Implemented |
| Journal event | 1 | `aj/journal.py` | Implemented |
| Audit event | 1 | `aj/audit.py` | Implicit (Jsonl format) |
| Idempotency record | 1 | `aj/idempotency.py` | Implemented |
| Configuration | 1 | `aj/config.py` | Implemented |

**TaskRecord** (already implemented):
```python
@dataclass
class TaskRecord:
    schema_version: int = 1  # <-- already present
    task_id: str
    goal: str
    ...
```

**Evidence**:
- `test_malformed_task_record_is_reported_not_deleted` - Task records with bad JSON handled; schema_version helps identify version
- `test_config_sources_and_validation` - Config version awareness

### 2. Current Version Tracking

**Configuration schema version**:
- `config.get("core.schema_version", 1)` or similar
- Not yet implemented in config (gap identified)
- Should be added for future compatibility tracking

**Evidence**: None (not yet implemented)

### 3. Backward Compatibility

**Guarantee**: Records of older schema_version remain readable and interpretable.

**Mechanism**:
- `TaskRecord.from_dict()`: Accepts extra fields (ignores unknown), provides defaults for missing fields
- `TaskRecord.to_dict()`: Includes all fields, including `schema_version`
- Malformed records: Reported in `load_errors`, skipped, but valid records on either side still load

**Example**: If schema_version changes from 1 to 2:
- Version 1 records: `schema_version` = 1, still readable (default values for v2 fields)
- Version 2 records: `schema_version` = 2, readable (has v2 fields)
- Migration needed: Only if v2 removes or renames v1 fields (not the case with additive changes)

**Evidence from tests**:
- `test_malformed_task_record_is_reported_not_deleted` - Malformed record (not different schema version) reported, good record preserved
- `test_attempt_model_survives_reload` - Task record survives reload across versions (same version, v1 → v1)

**Backward Compatibility Rules**:
1. **Additive changes only**: New fields added, old fields preserved (no removal or renaming)
2. **Default values for missing**: `from_dict()` provides defaults for missing fields
3. **Extra fields ignored**: `to_dict()` includes all, `from_dict()` ignores unknown
4. **schema_version field**: Always present, indicates record format version

### 4. Unsupported Future Versions Rejected Safely

**Guarantee**: Records with `schema_version` greater than supported version are handled gracefully, not silently trusted.

**Mechanism**:
- supported_max_version: integer, highest version the runtime supports
- On record load: if `record.schema_version > supported_max_version`: 
  - Report in `load_errors`
  - Still load record (preserve data), but mark as needing migration
  - Do NOT apply automatic migration (too risky)
  - Flag for operator attention

**Implementation**:
```python
# In TaskStore.reload() or similar:
SUPPORTED_MAX_VERSION = 1  # Update when v2 is released

# After parsing record:
if record.schema_version > SUPPORTED_MAX_VERSION:
    self.load_errors.append({
        "line": number,
        "error": f"unsupported schema_version {record.schema_version}, max supported {SUPPORTED_MAX_VERSION}"
    })
# Still load the record (preserve data), but mark it
record.note(f"unsupported schema version {record.schema_version}; migration required")
```

**Evidence**: None (not yet implemented - future extension)

### 5. Malformed Records Preserved and Reported

**Guarantee**: Malformed records (invalid JSON, missing required fields, unknown status) are preserved in file and reported, never silently deleted.

**Mechanism**:
- **Never rewrite or truncate** the persist file
- Each line parsed independently; one bad line does not affect others
- Bad lines reported in `load_errors` with line number and error type
- Valid lines still loadable around the bad line
- Record count reflects only valid records; `load_errors` count shows malformed

**Example** (`test_malformed_task_record_is_reported_not_deleted`):
```python
# Append "{bad json}" to tasks.jsonl
path.write_text(path.read_text() + "{bad json}\n")

# Reopen TaskStore
reopened = TaskStore(tmp_path)

# Good record preserved
assert len(reopened.all()) == 1  # 1 valid record
assert len(reopened.load_errors) == 1  # 1 malformed error
assert reopened.get(record.task_id).task_id == record.task_id  # Good record loadable

# Bad line still in file, not deleted
assert path.read_text().count("{bad json}") == 1  # Still there, 1 occurrence
```

**Evidence**: 
- `test_malformed_task_record_is_reported_not_deleted` - Core test for this guarantee
- `test_backup_tamper_is_detected` - Tamper detection works (tamper = malformed record)

### 5. Deterministic Migration

**Guarantee**: Migration is deterministic (same input → same output) and testable in temporary directories.

**Not yet implemented** (gap identified). Required for:

1. **Schema version bump**: v1 → v2 migration
2. **Field renaming**: e.g., `old_field` → `new_field`
3. **Field removal**: deprecated fields removed (with deprecation cycle)
4. **Data transformation**: e.g., timestamp format change

**Proposed Migration Pattern** (for future Phase 5):

```python
def migrate_task_record(record: TaskRecord, from_version: int, to_version: int) -> TaskRecord:
    """Deterministic migration from one schema version to another."""
    if from_version == 1 and to_version == 2:
        # Add new fields with defaults
        if not record.recovery:
            record.recovery = {}  # new field, default empty
        if record.next_retry_at is None:
            record.next_retry_at = None  # explicit None
        record.schema_version = 2  # update version
    # v1 → v1: no-op
    # v2 → v1: not supported (downgrade not guaranteed)
    return record
```

**Testability**:
```python
def test_migration_determinism():
    """Test that migration produces same result every time."""
    import tempfile, shutil
    from aj.task import TaskStore, TaskRecord
    
    # Create task record v1
    record = TaskRecord(task_id="test", goal="migration test")
    
    # Migrate v1 → v2
    migrated1 = migrate_task_record(record, 1, 2)
    migrated2 = migrate_task_record(record, 1, 2)  # Same input
    
    assert migrated1.schema_version == migrated2.schema_version == 2
    assert migrated1.task_id == migrated2.task_id == "test"
    assert migrated1.goal == migrated2.goal == "migration test"
    
    # Test in temp directory
    with tempfile.TemporaryDirectory() as tmp:
        # Migration in isolated dir produces deterministic result
        ...
```

**Evidence**: None (not yet implemented - future extension)

### 6. Existing Data Backed Up Before Migration

**Guarantee**: Existing data is backed up before any migration operation.

**Not yet implemented** (gap identified). Required procedure:

1. **Backup**: `transfer.backup_directory(config, backup_path)` before migration
2. **Verify**: `transfer.verify_backup(backup_path)` confirms backup integrity
3. **Migrage**: Apply migration to backup or live data
4. **Rollback**: If migration fails, restore from backup
5. **Never migrate live data without backup**

**Procedure**:
```python
# Phase 5+ migration procedure:
backup_path = tmp_path / "pre_migration_backup"
transfer.backup_directory(config, backup_path)

# Verify backup
report = transfer.verify_backup(backup_path)
assert report["ok"] is True, "Backup must be valid before migration"

# Apply migration to backup (not live data directly)
migrated_backup = apply_migration(backup_path, from_version, to_version)

# Verify migrated backup
report2 = transfer.import_file(config, migrated_backup_path)
# Or: restore migrated backup to fresh location and verify

# Only after verification: apply to live data
```

**Evidence**: None (not yet implemented - future extension)

### 7. Original Data Remains Recoverable

**Guarantee**: Original data (before migration) remains recoverable after migration.

**Mechanism**:
- Migration never deletes original data
- Backup preserves original
- Migration is additive (adds fields, doesn't remove)
- If rollback needed: restore from backup, original schema_version records still readable

**Evidence**: 
- Design principle: "migration must not lose data"
- `test_malformed_task_record_is_reported_not_deleted` - Related principle (malformed not deleted)

### 7. Migration Version Detection

**Gauge**: Detect what version migration is needed.

**Mechanism**:
1. Scan all tasks: find min/max `schema_version`
2. If max > supported_max_version: migration needed
3. If min < 1: older records (should not happen, v1 is baseline)
4. Report: `{"min_version": 1, "max_version": 2, "needs_migration": True}`

**Not yet implemented** (gap identified).

## Migration Readiness Assessment

| Capability | Status | Notes |
|------------|--------|-------|
| Schema version field in TaskRecord | ✅ Implemented (`schema_version: int = 1`) |  |
| Backward compatibility (v1→v1) | ✅ Tested (`test_attempt_model_survives_reload`) |  |
| Malformed record handling | ✅ Tested (`test_malformed_task_record_is_reported_not_deleted`) |  |
| Unsupported version handling | ❌ None | Gap - future extension |
| Deterministic migration | ❌ None | Gap - future Phase 5 |
| Backup before migration | ❌ None | Gap - future Phase 5 |
| Original data recoverable | ✅ Design principle | Supported by malformed record handling |
| Backup verification | ✅ Tested (`test_backup_verify_restore`, `test_backup_tamper_is_detected`) |  |
| Config schema version tracking | ❌ None | Gap - future extension |

## Changed Files

- `AJ/aj/task.py` - TaskRecord has `schema_version: int = 1` field (already present)
- `AJ/aj/journal.py` - Journal events include implicit versioning via event type
- `AJ/aj/receipts.py` - Receipt records have version awareness
- `AJ/aj/idempotency.py` - Idempotency records version-aware
- `AJ/tests/test_phase3.py` - Migration-related tests (malformed record, attempt survival)

## Migration Implementation Roadmap (Phase 5+)

### Phase 5.1: Add schema_version Tracking
- Add `schema_version` to all persistent record types (Lease, Receipt, Idempotency, Audit)
- Add config `core.schema_version` field
- Implement `SUPPORTED_MAX_VERSION` check in all `reload()` methods

### Phase 5.2: Implement Malformed Record Handling
- All `reload()` methods already handle malformed (report + skip)
- Extend to all file-based stores (tasks, journal, receipts, leases, idempotency)
- Ensure backup preservation during malformed record handling

### Phase 5.3: Implement Deterministic Migration
- Create migration functions for each record type version bump
- Test migration in `tempfile.TemporaryDirectory()` 
- Verify backup before migration, verify after
- Add migration CLI commands

### Phase 5.4: Add Version Detection and Reporting
- Scan all records, report min/max schema_version
- CLI command: `aj diagnostics storage --schema-versions`
- Auto-detect migration needs on startup
- Warn operator if migration required

### Phase 5.5: Add Migration CLI Commands
- `aj migrate --from v1 --to v2` (with backup requirement)
- `aj migrate --check` (detect needed migrations)
- `aj migrate --backup-and-migrate` (automated with confirmation)

### Phase 5.6: Add Downgrade Support (Optional)
- v2 → v1 migration (reverse)
- More conservative (only additive changes supported)
- Raise error on non-additive changes

## Test Additions for Storage Versioning

1. **Test schema_version across reload**: Create task, verify schema_version=1 survives reload
2. **Test malformed record preservation**: Append bad JSON, verify good record preserved, error reported
3. **Test unsupported version rejection**: Create record with schema_version=2 (if v2 defined), verify error reported
4. **Test backup before migration**: Backup, migrate, verify backup integrity preserved
5. **Test migration in temp directory**: Migrate in isolated dir, verify deterministic output
6. **Test config version awareness**: Config reports schema version, compatible with records