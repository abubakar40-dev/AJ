--- DOC 58 (decisions approved by delegation of the owner, v1) ---
D1 REQUIRED/OPTIONAL
- child_spec gets `required: bool`. Missing => required=true, recorded in child
  evidence as classification_source="default_required".
- Present but not a real bool (string, 0/1, null) => REJECT delegation creation
  with a validation error.
- Legacy persisted records without the field: all children required,
  classification_source="legacy_default_required". Read-time default only; NO
  rewriting of persisted data.
- aggregation_policy interplay: all_required: children with required=true must
  all be COMPLETED, optional ones never block unless unresolved. subset_required:
  if both required_child_ids and per-child `required` are given they must agree
  or creation is rejected; if only required_child_ids is given, listed refs are
  required and the rest optional. any_sufficient: `required` is recorded but not
  used for the completion rule.
D2 PARENT OUTCOME (child state classes)
- completed: COMPLETED. failed: FAILED, ABORTED, DEAD_LETTER, ABANDONED.
  cancelled: CANCELLED. unresolved/ambiguous: every other state, plus missing,
  unloadable or contradictory child records.
- Required child failed or cancelled => parent cannot complete; reconcile moves
  parent to FAILED with evidence "required_child_failed|cancelled".
- Required child unresolved/ambiguous => parent cannot complete, flagged manual
  review (requires_user_decision), status otherwise unchanged.
- Optional child failed or cancelled => parent MAY complete; evidence lists
  "optional_children_not_completed". Optional child unresolved => blocks
  completion until resolved (operator resolves via existing reconcile actions).
- NO partial-success status. Success only if all required COMPLETED and no
  unresolved child remains.
- The parent COMPLETED guard applies REGARDLESS of force=True.
D3 ABANDONED
- Add ABANDONED to aj/task.py constants, TERMINAL and TRANSITIONS. Legal source
  states = exactly the set Aj.abandon accepts today (derive from code and
  tests/test_dead_letter.py, do not widen). EXECUTING and CANCEL_REQUESTED stay
  excluded unless an existing test demands otherwise. Remove force=True from
  abandon once the edge is legal. Reload/import/event validation must accept
  ABANDONED; completed_at is set; legacy persisted ABANDONED records must load.
D4 ADMIN/SCHEDULER
- Aj.requeue on a delegated task: BLOCKED.
- dead_letter/abandon on a delegated child: allowed only through operator
  reconcile, must write delegation evidence and trigger parent reconcile.
- dead_letter/abandon on a parent with non-terminal children: BLOCKED.
- Scheduler (eligibility AND again under lease before dispatch) must verify for
  a delegated child: parent not CANCELLED/CANCEL_REQUESTED/ABORTED/DEAD_LETTER,
  delegation record active and linked, permission snapshot still a subset.
  Otherwise defer with a recorded reason.
- Cancelling a parent cancels non-terminal children through each child's own
  cancel flow (EXECUTING => CANCEL_REQUESTED, cooperative), records delegation
  evidence, and moves open assignments to CANCELLED.
D5 UNSUPPORTED CLAIMS (T-11)
- Anything the system cannot actually do (remote agent transport, exactly-once
  external effects, authenticated identity, Hermes attachment) must be rejected
  or reported as UNSUPPORTED, never silently accepted.
--- END DOC 58 ---


---
## D3 REFINEMENT (S0 round 3, derived from code + tests; not widening)
**Current implementation (observed):** `Aj.abandon` (`aj/orchestrator.py`) refuses only if status is already `ABANDONED`, then performs `self.tasks.transition(task_id, "ABANDONED", ..., force=True, reason="abandoned")` (bypasses `TaskRecord.can_transition`/terminal checks). Therefore in practice it accepts broadly (any non-ABANDONED state), including terminal/active states unless separately prevented — this is broader than policy intent.

**Tests observed (`tests/test_dead_letter.py`):** abandon exercised from FAILED (direct/after flow), from PLANNED (after requeue), and idempotent behavior when already ABANDONED; no test requires abandoning EXECUTING or CANCEL_REQUESTED; no test requires abandoning COMPLETED.

**Doc 58 D3 refinement (approved policy target):**
- Legal source states for `ABANDONED` = **FAILED, DEAD_LETTER, RECOVERY_REQUIRED, ESCALATED**.
- Everything else refused: all other terminal states (COMPLETED, ABORTED, CANCELLED, ABANDONED) and all active/non-listed states (including EXECUTING and CANCEL_REQUESTED).
- `Aj.abandon` must explicitly validate source state and **must no longer rely on `force=True`** once `ABANDONED` edges are legal in FSM/TRANSITIONS.
- `ABANDONED` must be added to `aj/task.py` constants, `TERMINAL`, and `TRANSITIONS` for the legal source states only; reload/import/event validation must accept `ABANDONED`; `completed_at` set; legacy persisted `ABANDONED` records must load (D3). **No aj/ implementation performed in this S0 round except D-001 defect fix below.**

## D-001 DEFECT FIXED: missing import (authorized, S0 round 3)
- **Defect:** `aj/orchestrator.py` imported `AssignmentStore, DelegationStore, LogicalAgentStore, detect_delegation_anomalies` from `.delegation` but omitted `aggregate_parent_progress`. `_before_task_transition` (delegation-parent `COMPLETED` guard, non-force) calls `aggregate_parent_progress(...)`, causing `NameError` caught and wrapped as `Conflict("... delegation state unverifiable (NameError)")`. Effect: every non-force completion of a delegated parent blocked as unverifiable (including legitimate completions); existing Conflict-expecting tests could pass for wrong reason.
- **Fix applied (only authorized source edit):** added `aggregate_parent_progress` to that import in `aj/orchestrator.py` (line ~51). No other source changes; `except Exception` handling unchanged.
- **Evidence before fix:** `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_BEFORE_FIX.txt` — `test_b3_parent_with_all_required_children_completed_completes` failed with `NameError: name 'aggregate_parent_progress' is not defined` -> `aj.errors.Conflict: ... unverifiable (NameError)`.
- **Evidence after fix:** `ENGINEERING_AUDIT/S0_CLOSURE/D001_B3_AFTER_FIX.txt` — same B3 test PASSED. `ENGINEERING_AUDIT/S0_CLOSURE/D001_CONFLICT_MESSAGES_AFTER_FIX.json` shows completion guard now raises real aggregation-based `Conflict` (with `aggregation` detail, no `NameError`/`unverifiable`).
- **Suite impact:** existing suite (`--ignore=tests/s0_proof`) before fix: 576 passed, 1 failed (intermittent NTFS sqlite disk I/O), 13 warnings; after fix: 577 passed, 13 warnings (sqlite test passed in that run). No deterministic regression attributed to D-001. Completion-blocking delegation tests asserting `Conflict` on guarded parent completion previously could pass for wrong reason (NameError-wrapped unverifiable); with fix they pass with real aggregation reasons (see STEP 3 change table in REVIEW_PACK_3 / report).
