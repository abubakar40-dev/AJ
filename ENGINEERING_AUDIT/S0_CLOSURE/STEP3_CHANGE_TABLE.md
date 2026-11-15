# STEP 3 — D-001 impact: before/after fix evidence

## Commands / artifacts
- Before-fix B3 (NameError): `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_BEFORE_FIX.txt`
- After-fix B3 (PASS): `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_AFTER_FIX.txt`
- Before-fix existing suite (`pytest -q`, clean committed snapshot, no `tests/s0_proof`): `/tmp/s0_round3_suite_before_d001.txt` → **576 passed, 1 failed, 13 warnings** (`tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` failed with `sqlite3.OperationalError: disk I/O error` on NTFS workspace tmp path; known intermittent/environment-sensitive OPEN issue)
- After-fix existing suite (`pytest -q --ignore=tests/s0_proof`): `/tmp/s0_round3_suite_after_d001_existing.txt` → **577 passed, 13 warnings** (sqlite test passed in this run)
- After-fix all suite including `tests/s0_proof`: `/tmp/s0_round3_suite_after_d001_all.txt` → **581 passed, 9 xfailed, 13 warnings**
- Conflict message capture (with fix): `ENGINEERING_AUDIT/S0_CLOSURE/D001_CONFLICT_MESSAGES_AFTER_FIX.json`

## Test result changes (every observed change)
| Test / scope | Before D-001 fix | After D-001 fix | Attribution |
|---|---|---|---|
| `tests/s0_proof/test_s0_characterization.py::test_b3_parent_with_all_required_children_completed_completes` | FAIL (`NameError: aggregate_parent_progress` -> `Conflict ... unverifiable (NameError)`) | PASS | **D-001 fix** (intended) |
| `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` | FAIL (`sqlite3.OperationalError: disk I/O error`, NTFS workspace tmp) | PASS (in compared after-fix run) | **Intermittent/environment-sensitive variance (OPEN, not attributed to D-001)** |
| All other existing tests (`--ignore=tests/s0_proof`, excluding above) | PASS (576) | PASS (576) | No change observed |

**Conclusion:** no deterministic regression in existing tests attributed to D-001. The only deterministic behavior change observed is correction of delegated-parent completion guard evaluation (from NameError/unverifiable to real aggregation).

## Conflict messages for delegation completion-blocking cases (with fix applied)
Source: `D001_CONFLICT_MESSAGES_AFTER_FIX.json` (reproduced via real Aj/delegation flows) and verified passing tests.

| Scenario / representative test(s) | `raises Conflict` site(s) | Message with fix (real reason) | Previously passed only because of NameError? | Notes |
|---|---|---|---|---|
| Required child unresolved, parent completion attempted | `tests/test_phase5a6r2_parent_lifecycle.py:130` (`test_parent_completion_blocked_when_required_child_unresolved`), `:152` (`test_parent_completion_blocked_direct_guard`) | `parent task ... cannot complete: required child work unresolved/uncertain/manual-review` with `detail.aggregation` (e.g. waiting/unresolved, `can_complete=false`) | **YES (wrong reason).** Guard called undefined `aggregate_parent_progress` -> caught -> `Conflict(... delegation state unverifiable (NameError))`; tests asserted only `Conflict`, so they passed but for wrong reason. | With fix, correct aggregation-based block. |
| Required child failed, parent completion attempted | `tests/test_phase5a6r2_parent_lifecycle.py::test_required_child_failure_prevents_false_completion` (asserts aggregation/cannot-complete; may also block transition if attempted) / reproduced case | same Conflict class/message family with aggregation showing failed required child, `can_complete=false` | **YES if it reached guarded COMPLETED transition and asserted only Conflict.** Guard path would have thrown NameError-wrapped unverifiable Conflict before fix. | Reproduced case shows real aggregation reason after fix. |
| Unknown/recovery-required/manual-review child blocks completion | `tests/test_phase5a6r2_parent_lifecycle.py::test_unknown_or_recovery_required_child_blocks_completion`, `tests/test_phase5a6r3_scenario_certification.py::test_s7_s11_required_failure_and_manual_review_prevent_completion` | aggregation-based cannot-complete/manual-review when evaluated | **Potentially YES for wrong reason** in any path that attempted guarded non-force parent COMPLETED and only checked Conflict/blocked outcome; before fix such guard evaluation was NameError -> unverifiable Conflict. | Tests primarily assert aggregation flags; completion-guard wrong-reason exposure depends on whether guarded transition was invoked. |
| Incorrect completed parent detection scenario (guard blocks proper completion attempt) | `tests/test_phase5a6r3_scenario_certification.py:258` (`test_s16_s31_incorrect_completed_parent_detected`) | aggregation-based cannot-complete Conflict when transition attempted | **YES (wrong reason)** for the `pytest.raises(Conflict)` on `aj.tasks.transition(..., COMPLETED)` at ~258 (guarded path). | Test later simulates contradictory persisted state for detection; the guarded transition assertion would have passed for wrong reason before fix. |
| Same idempotency key, different spec (delegate) | `tests/test_phase5a6r_delegation_closure.py:126` (`test_same_idempotency_key_different_spec_rejected`) | `same delegation idempotency key with different specification` | **NO.** Different code path (`delegate` idempotency validation), unaffected by D-001. | Included for completeness of `raises(Conflict)` sites in target files. |

## Wrong-reason summary (as required)
- **Previously passed only because of NameError (`unverifiable (NameError)`), not real aggregation reason:** completion-guarding assertions that expected `Conflict` when transitioning a delegated parent to `COMPLETED` (non-force) while children unresolved/failed/manual-review — notably `test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_when_required_child_unresolved` (~130), `::test_parent_completion_blocked_direct_guard` (~152), and `test_phase5a6r3_scenario_certification.py::test_s16_s31_incorrect_completed_parent_detected` (~258). Any equivalent guarded path in `test_required_child_failure_prevents_false_completion`, `test_unknown_or_recovery_required_child_blocks_completion`, or `test_s7_s11_required_failure_and_manual_review_prevent_completion` would also have been masked if it relied on the guard raising Conflict.
- **Real aggregation reason (after fix):** `Conflict` with message `cannot complete: required child work unresolved/uncertain/manual-review` and `detail.aggregation` populated (e.g. `waiting_for_children`, failed counts, `can_complete=false`, `requires_manual_review` as applicable).
- **Unrelated to D-001:** `test_same_idempotency_key_different_spec_rejected` (idempotency Conflict) — not due to NameError before or after.
- No existing tests in target files were edited; this is a reporting-only audit.
