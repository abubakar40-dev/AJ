# WRONG_REASON_MEASURED (Step 1, round 4)

## Method (measured, no guessing)
- Scratch copy: `mkdir /tmp/aj_prefix && git archive eb2674b | tar -x -C /tmp/aj_prefix` (pre-D-001 source; real repo unchanged).
- Instrumentation in scratch only: `aj/orchestrator.py::_before_task_transition` `except Exception as exc:` branch logs `os.environ.get("PYTEST_CURRENT_TEST","?")+" | "+type(exc).__name__+"\n"` to `/tmp/nameerr_hits.log` before raising `Conflict(... unverifiable ...)`.
- Runs (one file at a time, scratch copy, `PYTHONDONTWRITEBYTECODE=1`):
  - `python3 -m pytest -q --basetemp=/tmp/aj-pre/foundation tests/test_phase5a6_delegation_foundation.py` → `8 passed` (`/tmp/step1_foundation.txt`)
  - `python3 -m pytest -q --basetemp=/tmp/aj-pre/rclosure tests/test_phase5a6r_delegation_closure.py` → `7 passed` (`/tmp/step1_rclosure.txt`)
  - `python3 -m pytest -q --basetemp=/tmp/aj-pre/r2 tests/test_phase5a6r2_parent_lifecycle.py` → `11 passed` (`/tmp/step1_r2.txt`)
  - `python3 -m pytest -q --basetemp=/tmp/aj-pre/r3 tests/test_phase5a6r3_scenario_certification.py` → `12 passed` (`/tmp/step1_r3.txt`)
  - `python3 -m pytest -q --basetemp=/tmp/aj-pre/r4 tests/test_phase5a6r4_gap_closure.py` → `6 passed` (`/tmp/step1_r4.txt`)
- Log contents (exact): 2 lines total.

## Tests that wrote to `/tmp/nameerr_hits.log` (hit NameError path)
| Test (PYTEST_CURRENT_TEST) | Exception logged | Test result in scratch run | Exact assertion that let it pass |
|---|---|---|---|
| `tests/test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_when_required_child_unresolved (call)` | `NameError` | **PASSED** (as part of r2: 11 passed) | `with pytest.raises(Conflict): aj.tasks.transition(parent.task_id, taskmod.COMPLETED, "should block")` (line 130-131 in current/r2 file). The guard raised `Conflict(... delegation state unverifiable (NameError))` due to missing `aggregate_parent_progress`, so `pytest.raises(Conflict)` was satisfied for the **wrong reason** (not real aggregation). |
| `tests/test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_direct_guard (call)` | `NameError` | **PASSED** (as part of r2: 11 passed) | `with pytest.raises(Conflict): aj.tasks.transition(parent.task_id, taskmod.COMPLETED, "child unresolved")` (line 152-153). Same wrong reason: NameError-wrapped unverifiable Conflict satisfied `pytest.raises(Conflict)`. |

## Tests with `pytest.raises(Conflict)` / "blocked" assertions that did NOT hit the log
(Within the 5 measured files; searched for `raises(Conflict)` and "blocked"/"Block" markers.)

| Test / site | Assertion/marker | Hit log? | Note (factual) |
|---|---|---:|---|
| `tests/test_phase5a6r_delegation_closure.py:126` `test_same_idempotency_key_different_spec_rejected` | `with pytest.raises(Conflict):` | No | Different code path (delegate idempotency validation), not delegated-parent completion guard `_before_task_transition` NameError path. |
| `tests/test_phase5a6r_delegation_closure.py:157` `test_executor_reads_current_task_and_delegation_state` (approx) | `assert "blocked" in guard.summary.lower() or guard.status in ("ABORTED", "FAILED")` | No | No logged completion-guard NameError. |
| `tests/test_phase5a6r3_scenario_certification.py:258` `test_s16_s31_incorrect_completed_parent_detected` | `with pytest.raises(Conflict): aj.tasks.transition(parent.task_id, taskmod.COMPLETED)` (inside `if cur.can_transition(taskmod.COMPLETED):`) | No | Did not write to log in this pre-D-001 scratch run (12 passed). Not counted as measured wrong-reason pass. |
| `tests/test_phase5a6_delegation_foundation.py:142` (comment/behavior) | "different spec without key blocked by max_delegations_per_parent" | No | No `pytest.raises(Conflict)` guard-hit logged. |
| `tests/test_phase5a6r4_gap_closure.py:137` (section marker) | "Priority A: delegated execution blocked..." | No | No `pytest.raises(Conflict)` guard-hit logged. |

## Measured conclusion
- **Existing tests in the 5 measured files that passed for the wrong reason (NameError path in `_before_task_transition`): 2**
  1. `tests/test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_when_required_child_unresolved`
  2. `tests/test_phase5a6r2_parent_lifecycle.py::test_parent_completion_blocked_direct_guard`
- Both passed because `pytest.raises(Conflict)` caught `Conflict(... unverifiable (NameError))` rather than a real aggregation-based block.
- No other test in these 5 files produced a measured hit to the instrumented NameError branch. This measurement does **not** prove absence of wrong-reason behavior outside these files/runs; it reports only what was measured.
