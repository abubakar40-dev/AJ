# CALLABLE_INVENTORY_S0.md v3 (E2, round 4)

**Status:** NOT exhaustive. Rebuilt from fresh AST scan + targeted manual/code inspection. Facts only; reviewer decides closure. v2 preserved as `ENGINEERING_AUDIT/S0_CLOSURE/CALLABLE_INVENTORY_S0_v2.md`.

## Tools / commands (exact)
```bash
cd "/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ" && git branch --show-current && git rev-parse main
# fresh AST scan (aj/**/*.py + integrations/**/*.py) -> /tmp/ast_round4.json
# compare vs ENGINEERING_AUDIT/S0_CLOSURE/ast_callgraph_results.json
# getattr/dynamic target-name scan
grep -rn "def transition\b" aj integrations
grep -rn "def (dead_letter|requeue|abandon|delegate|resume|retry|recover|cancel_task|cancel|run_once|_dispatch_one|reconcile|import_record|save|mutate|evaluate_eligibility|evaluate_admission|_prepare_delegated_child_for_scheduling|_reconcile_delegation_parent|handle)\b" aj integrations
grep -n "_cmd_" aj/__main__.py
# sed -n inspections: aj/orchestrator.py, aj/scheduler.py, aj/task.py, aj/recovery.py, aj/runtime.py, aj/__main__.py
```

## Step 2a — fresh scan results and delta vs old 146-entry result
- Files scanned (fresh): **47** (`aj/**/*.py` + `integrations/**/*.py`). AST parse errors: **0**.
- Fresh AST call-site entries: **146**. Old `ast_callgraph_results.json` entries: **146**.
- **Delta:** added **0**, removed **0** (identical entry set by file/line/call/target key). No matching entries under `integrations/**/*.py`.

### getattr(...) / dynamic-call scan (target-name strings)
| Location / expression | Classification / proof |
|---|---|
| `aj/inbox_cli.py:332` `getattr(args, "requeue_stale_seconds", 300)` | Attribute read only; no dynamic target-method invocation. |
| `aj/orchestrator.py:1178` `getattr(record, "requires_user_decision", False)` | Attribute read only. |
| `aj/orchestrator.py:2522` `getattr(spec, "retry_safe", False)` | Attribute read only. |
| `aj/orchestrator.py:2563` `getattr(record, "recovery", {})` | Attribute read only. |
| `aj/orchestrator.py:3793` `getattr(self._delegation_reconcile_local, "active", None)` | Attribute read only. |
| `aj/orchestrator.py:3985` `getattr(blocker, "message", "blocked")` | Attribute read only. |
| `aj/task.py:633` `cb = getattr(self, "after_transition", None)` | Fixed-name hook lookup/invocation (Aj after_transition). Not variable target-name dispatch. |

No `getattr`-based dynamic invocation of inventory target methods by variable target-name string identified in this scan. Absence of all dynamic dispatch is **NOT VERIFIABLE** statically (see end).

### Objects other than `Aj`/`TaskStore` exposing methods named like targets
| Object/class (file:line/methods) | Domain / note |
|---|---|
| `aj/task.py:146 TaskRecord.transition; :642 TaskStore.transition; :455 save; :599 import_record; :658 cancel; :694 mutate` | Task domain (in-scope). |
| `aj/calling.py:202 CallRecord.transition; :379 cancel` | Calling domain. |
| `aj/delegation.py:387 AssignmentRecord.transition; :579/:626/:662 save` | Delegation/assignment domain. |
| `aj/execution_domain.py:78 ExecutionRecord.transition; :231 save; :252 transition` | Execution domain. |
| `aj/recovery.py:94 RecoveryManager.recover` | Recovery manager (distinct from Aj.recover). |
| `aj/scheduler.py evaluate_eligibility/evaluate_admission/_dispatch_one/run_once` | Scheduler (in-scope). |

## Step 2b — domain filter for `.transition(...)` call sites
| File:Line | Caller | Call | Class/object of record | Disposition | Proof |
|---|---|---|---|---|---|
| `aj/calling.py:264` | `prepare` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:266` | `prepare` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:269` | `prepare` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:273` | `prepare` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:277` | `prepare` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:281` | `prepare` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:285` | `prepare` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:304` | `confirm_and_dial` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:333` | `confirm_and_dial` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:334` | `confirm_and_dial` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:338` | `confirm_and_dial` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:344` | `confirm_and_dial` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:347` | `confirm_and_dial` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:376` | `hang_up` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/calling.py:383` | `cancel` | `record.transition` | CallRecord (aj.calling.CallRecord.transition) | **OUT-OF-TASK-DOMAIN** | CallRecord in calling subsystem |
| `aj/execution_domain.py:256` | `transition` | `rec.transition` | ExecutionRecord (aj.execution_domain.ExecutionRecord.transition) | **OUT-OF-TASK-DOMAIN** | Execution domain FSM |
| `aj/orchestrator.py:331` | `handle` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:338` | `handle` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:344` | `handle` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:386` | `handle` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:414` | `handle` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:439` | `handle` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:490` | `_retry_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:492` | `_retry_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:583` | `_retry_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:585` | `_retry_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:628` | `_cancel_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:649` | `_cancel_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1092` | `_recover_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1094` | `_recover_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1100` | `_recover_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1173` | `_require_manual_recovery` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1308` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1349` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1351` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1425` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1449` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1450` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1501` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1503` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1512` | `_execute` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1625` | `_execute_calling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1656` | `_execute_calling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:1658` | `_execute_calling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2009` | `_handle_stale_authorization` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2058` | `_resume_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2075` | `_resume_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2097` | `_resume_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2116` | `_resume_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2147` | `_resume_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2169` | `_resume_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2188` | `_resume_locked` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:2251` | `dead_letter` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3247` | `reconcile` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3307` | `reconcile` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3437` | `requeue` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3494` | `abandon` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3562` | `_transition_execution` | `rec.transition` | ExecutionRecord (execution attempt) | **OUT-OF-TASK-DOMAIN** | ExecutionRecord.transition, not TaskRecord |
| `aj/orchestrator.py:3597` | `_start_attempt` | `erec.transition` | ExecutionRecord (execution attempt) | **OUT-OF-TASK-DOMAIN** | ExecutionRecord.transition, not TaskRecord |
| `aj/orchestrator.py:3618` | `_finish_attempt` | `erec.transition` | ExecutionRecord (execution attempt) | **OUT-OF-TASK-DOMAIN** | ExecutionRecord.transition, not TaskRecord |
| `aj/orchestrator.py:3624` | `_finish_attempt` | `erec.transition` | ExecutionRecord (execution attempt) | **OUT-OF-TASK-DOMAIN** | ExecutionRecord.transition, not TaskRecord |
| `aj/orchestrator.py:3660` | `_fail` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3942` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3957` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3960` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3976` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3985` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:3996` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:4002` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:4008` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/orchestrator.py:4011` | `_prepare_delegated_child_for_scheduling` | `self.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/runtime.py:163` | `_check_tasks` | `store.transition` | TaskRecord via temporary TaskStore (self-check) | **DIAGNOSTIC-ONLY (temp)** | tempfile.TemporaryDirectory + local TaskStore |
| `aj/runtime.py:164` | `_check_tasks` | `store.transition` | TaskRecord via temporary TaskStore (self-check) | **DIAGNOSTIC-ONLY (temp)** | tempfile.TemporaryDirectory + local TaskStore |
| `aj/runtime.py:246` | `_check_task_persistence` | `store.transition` | TaskRecord via temporary TaskStore (self-check) | **DIAGNOSTIC-ONLY (temp)** | tempfile.TemporaryDirectory + local TaskStore |
| `aj/runtime.py:247` | `_check_task_persistence` | `store.transition` | TaskRecord via temporary TaskStore (self-check) | **DIAGNOSTIC-ONLY (temp)** | tempfile.TemporaryDirectory + local TaskStore |
| `aj/runtime.py:303` | `_check_recovery` | `aj.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/runtime.py:428` | `_check_cancel_retry` | `aj.tasks.transition` | TaskStore/TaskRecord task FSM | **IN-TASK-DOMAIN** | Aj/TaskStore tasks.transition call site |
| `aj/task.py:650` | `transition` | `record.transition` | TaskRecord (aj.task.TaskRecord) | **IN-TASK-DOMAIN** | TaskStore method delegates to TaskRecord.transition/persist |
| `aj/task.py:665` | `cancel` | `record.transition` | TaskRecord (aj.task.TaskRecord) | **IN-TASK-DOMAIN** | TaskStore method delegates to TaskRecord.transition/persist |

### `aj/runtime.py` self-checks — DIAGNOSTIC-ONLY proof
- `_check_tasks` (`aj/runtime.py:163-164`): `tempfile.TemporaryDirectory(...)` + `TaskStore(directory.name)` (temp). **Proof:** not real configured data dir.
- `_check_task_persistence` (`aj/runtime.py:246-247`): `with tempfile.TemporaryDirectory(...)` + `TaskStore(directory)`. **Proof:** temp context.
- `_check_recovery` (`aj/runtime.py:303+`): Aj with `TaskStore(directory)`, `MemoryStore(":memory:")`, `MemoryAuditSink()` inside `tempfile.TemporaryDirectory(prefix="aj-reccheck-")`. **Proof:** isolated temp stores.
- `_check_cancel_retry` (`aj/runtime.py:428+`): isolated temp pattern with `tempfile.TemporaryDirectory(prefix="aj-retrycheck-")`. **Proof:** isolated temp stores.
- Runtime self-check transition sites are **DIAGNOSTIC-ONLY (temporary stores/dirs)**.

## Step 2c — callable-grouped inventory (mandatory callables)
### Common guard wiring (Aj, D-001 applied)
Aj monkeypatches `self.tasks.transition` -> `_guarded_transition` calling `_before_task_transition` then original transition; `tasks.after_transition = _on_task_transition`. `force=True` bypasses completion-guard branch in `_before_task_transition`.
```python
236:             self.tasks.after_transition = self._on_task_transition
237:             _orig_transition = self.tasks.transition
238:             def _guarded_transition(task_id, status, detail="", *, force=False, reason="transition"):
239:                 self._before_task_transition(task_id, status, detail, force=force, reason=reason)
240:                 return _orig_transition(task_id, status, detail, force=force, reason=reason)
241:             self.tasks.transition = _guarded_transition
242:         except Exception:
243:             pass
244: 

3733:     def _before_task_transition(self, task_id: str, status: str, detail: str = "",
3734:                                 *, force: bool = False, reason: str = "transition") -> None:
3735:         """Fail closed on invalid delegation-parent completion transitions."""
3736:         if force or status != taskmod.COMPLETED:
3737:             return
3738:         dels = self._delegations_for_parent(task_id)
3739:         if not dels:
3740:             return
3741:         try:
3742:             # Conservative: if any delegation for parent cannot be safely completed, block completion.
3743:             for d in dels:
3744:                 agg = aggregate_parent_progress(
3745:                     self.tasks, parent_task_id=d.request.parent_task_id,
3746:                     child_task_ids=d.child_task_ids,
3747:                     aggregation_policy=d.request.aggregation_policy,
3748:                     required_child_task_ids=(d.request.required_child_ids or d.child_task_ids),
3749:                 )
3750:                 if not agg.get("can_complete", False) or agg.get("requires_manual_review", False):
3751:                     raise errors.Conflict(
3752:                         f"parent task {task_id} cannot complete: required child work unresolved/uncertain/manual-review",
3753:                         detail={"delegation_id": getattr(d, "delegation_id", ""), "aggregation": agg},
3754:                     )
3755:         except errors.Conflict:
3756:             raise
3757:         except Exception as exc:
3758:             raise errors.Conflict(
3759:                 f"parent task {task_id} completion blocked: delegation state unverifiable ({type(exc).__name__})"
3760:             ) from exc
3761: 
3762:     def _mark_delegation_reconciliation_pending(self, parent_task_id: str, *, trigger: str,
3763:                                                 child_task_id: str = "", error: str = "") -> None:
3764:         """Best-effort durable pending marker (append-only delegation evidence)."""
3765:         dels = self._delegations_for_parent(parent_task_id)
3766:         for d in dels:
3767:             try:
3768:                 ev = dict(getattr(d, "evidence", {}) or {})
3769:                 ev["reconciliation_pending"] = {
3770:                     "pending": True,
3771:                     "at": time.time(),
```
`_delegated_permission_guard` excerpt:
```python
3860:                               errors.PolicyDenied("delegated execution blocked: missing parent linkage"),
3861:                               "authorization", final=taskmod.ABORTED)
3862:         try:
3863:             parent = self.tasks.get(parent_id)
3864:         except Exception:
3865:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3866:                               errors.PolicyDenied("delegated execution blocked: parent task unverifiable"),
3867:                               "authorization", final=taskmod.ABORTED)
3868:         # Conservative revocation/cancellation handling: if parent delegation authority is no longer valid,
3869:         # delegated child execution must not proceed (no fabricated continuation).
3870:         if getattr(parent, "status", "") in (taskmod.CANCELLED, taskmod.CANCEL_REQUESTED, taskmod.ABORTED, taskmod.DEAD_LETTER):
3871:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3872:                               errors.PolicyDenied("delegated execution blocked: parent delegation authority revoked/cancelled"),
3873:                               "authorization", final=taskmod.ABORTED)
3874:         if self.delegations and delegation_id:
3875:             try:
3876:                 drec = self.delegations.get(delegation_id)
3877:             except Exception:
3878:                 drec = None
3879:             if drec is None:
3880:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3881:                                   errors.PolicyDenied("delegated execution blocked: delegation record unverifiable"),
3882:                                   "authorization", final=taskmod.ABORTED)
3883:             if str(getattr(drec.request, "parent_task_id", "") or "") != parent_id:
3884:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3885:                                   errors.PolicyDenied("delegated execution blocked: delegation-parent mismatch"),
3886:                                   "authorization", final=taskmod.ABORTED)
3887:             if getattr(drec, "status", "") in ("FAILED", "CANCELLED", "REVOKED"):
3888:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3889:                                   errors.PolicyDenied("delegated execution blocked: delegation no longer active"),
3890:                                   "authorization", final=taskmod.ABORTED)
3891:             if record.task_id not in list(getattr(drec, "child_task_ids", []) or []):
3892:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3893:                                   errors.PolicyDenied("delegated execution blocked: child not linked to delegation"),
3894:                                   "authorization", final=taskmod.ABORTED)
3895:         # Conservative envelope checks against recorded snapshots (narrowing only).
3896:         req_snapshot = dctx.get("requested_permissions_snapshot")
3897:         if isinstance(req_snapshot, list):
3898:             if not set(effective).issubset({str(x) for x in req_snapshot if isinstance(x, str)}):
3899:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3900:                                   errors.PolicyDenied("delegated execution blocked: effective permissions exceed requested envelope"),
3901:                                   "authorization", final=taskmod.ABORTED)
3902:         elif req_snapshot is not None:
3903:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3904:                               errors.PolicyDenied("delegated execution blocked: malformed requested permission snapshot"),
3905:                               "authorization", final=taskmod.ABORTED)
3906:         parent_snapshot = dctx.get("parent_permissions_snapshot")
3907:         if isinstance(parent_snapshot, list):
3908:             if not set(effective).issubset({str(x) for x in parent_snapshot if isinstance(x, str)}):
3909:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3910:                                   errors.PolicyDenied("delegated execution blocked: effective permissions exceed parent envelope"),
3911:                                   "authorization", final=taskmod.ABORTED)
3912:         elif parent_snapshot is not None:
3913:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3914:                               errors.PolicyDenied("delegated execution blocked: malformed parent permission snapshot"),
3915:                               "authorization", final=taskmod.ABORTED)
3916:         # Logical-internal delegated children must remain within delegation-coordination scope
3917:         # unless an explicit broader execution envelope is verifiably authorized (not implemented).
3918:         if dctx.get("logical_internal") and effective and set(effective) - {"delegation.coordinate"}:
3919:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3920:                               errors.PolicyDenied("delegated execution blocked: unverifiable permission scope for logical-internal delegation"),
3921:                               "authorization", final=taskmod.ABORTED)
3922:         return None
3923: 
3924:     def _prepare_delegated_child_for_scheduling(self, task_id: str) -> Dict[str, Any]:
3925:         """Progress a delegated child through existing planning/authorization paths to a schedulable
3926:         or explicit waiting/deferred state. Does not dispatch/execute (scheduler owns dispatch)."""
3927:         record = self.tasks.get(task_id)
```

### Aj.handle
- **CALLABLE:** `Aj.handle`
- **CALLERS (file:line list):** `aj/__main__.py:_cmd_run` calls `aj.handle(...)`; handle-flow task transitions in `aj/orchestrator.py` per AST.
- **ENTRY PATH:** CLI/API-style assembly -> `Aj.handle` -> planning/authorization/execution with task transitions via wrapped TaskStore.
- **DELEGATION CONTEXT POSSIBLE:** Yes (including delegation-related flows).
- **CURRENT GUARD (quote exact lines):**
```python
247:     def handle(
248:         self,
249:         goal: str,
250:         *,
251:         capability_id: str = "",
252:         payload: Optional[Mapping[str, Any]] = None,
253:         approval: str = "",
254:         user_requested: bool = True,
255:         requester: str = "user",
256:         timeout_seconds: int = 120,
257:         idempotency_key: str = "",
258:         depends_on: Optional[List[str]] = None,
259:         priority: int = 0,
260:         deadline: Optional[float] = None,
261:     ) -> TaskOutcome:
262:         """Accept one request and run it as far as policy allows."""
263:         goal = (goal or "").strip()
264:         key = (idempotency_key or "").strip()
265:         if key and self.idempotency is not None:
266:             # Check for idempotency key conflict before claiming
267:             # Look up in capability-scoped namespace first
268:             existing_task_id = self.idempotency.lookup(capability_id or "auto", key)
269:             # Also check the full store for cross-capability key reuse
270:             # (key may have been claimed under a different capability)
271:             all_entries = self.idempotency.all()
272:             other_scope_task_id = None
273:             for scope, data in all_entries.items():
274:                 # scope format is "capability_id:key" or just "key"
275:                 scope_key = scope.split(":", 1) if ":" in scope else [scope, ""]
276:                 scope_id = scope_key[0] if len(scope_key) > 1 else None
277:                 store_key = scope_key[1] if len(scope_key) > 1 else scope
278:                 if store_key == key and scope_id and scope_id != (capability_id or ""):
279:                     other_scope_task_id = str(data.get("task_id", ""))
280:                     break
281:             existing_task_id = existing_task_id or other_scope_task_id
282:             if existing_task_id:
283:                 # Key already exists - verify it's for the same capability and payload
284:                 existing = self.tasks.get(existing_task_id)
285:                 if existing.capability_id == (capability_id or "") and existing.request_payload == dict(payload or {}):
286:                     # Same key, same capability, same payload: true idempotent replay
287:                     return self._idempotent_outcome(existing_task_id)
288:                 # Same key but different capability or payload: conflict
289:                 return self._fail(
290:                     self.tasks.create(goal or "(no goal text)", requester=requester),
```
- **CURRENT-STATE REVALIDATION:** Partial: TaskStore FSM validation, authorizer/capability checks, wrapped pre-guard for non-force COMPLETED; full current delegated authority and Doc58 D1-D5 revalidation at every boundary not proven.
- **PERMISSION CHECK:** Capability/authorizer checks present; delegated narrowing/current-state and unsupported-claim handling incomplete (A6/A7).
- **CANCELLATION CHECK:** Not fully enforced for delegated parent-cancel/revocation semantics across all paths (A2/A3/A4).
- **REVOCATION CHECK:** Partial in some delegated guards; not exhaustive.
- **RACE PROTECTION:** Store/file locks per store; no proven cross-store atomicity/stale-writer protection.
- **PERSISTED EVIDENCE:** Task JSONL, audit/journal/receipts/memory where emitted (non-atomic).
- **STATUS:** Partially guarded; delegation/Doc58 completeness unproven.
- **DISPOSITION (target stage):** **S1-FIX / S2-FIX / S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Exhaustive per-branch proof of current delegation authority, required classification, and unsupported-claim rejection.
- **What would make it verifiable:** Per-path stateful tests with persisted evidence for all handle branches and negative delegated/unsupported cases.

### Aj.resume
- **CALLABLE:** `Aj.resume`
- **CALLERS (file:line list):** `aj/scheduler.py` dispatch calls `aj.resume(task_id, leased=True)`; no direct CLI resume subcommand found.
- **ENTRY PATH:** Scheduler dispatch (intent/lease/start) or internal callers -> `Aj.resume` -> transitions/execution boundaries.
- **DELEGATION CONTEXT POSSIBLE:** Yes (delegated children).
- **CURRENT GUARD (quote exact lines):**
```python
2036:     def resume(self, task_id: str, *, leased: bool = False) -> TaskOutcome:
2037:         if leased:
2038:             return self._resume_locked(task_id)
2039:         with self.leases.hold(task_id, "execute"):
2040:             return self._resume_locked(task_id)
2041: 
2042:     def _resume_locked(self, task_id: str) -> TaskOutcome:
2043:         record = self.tasks.get(task_id)
2044:         spec = self.registry.find(record.capability_id) if record.capability_id else None
2045:         if spec is None:
2046:             raise errors.CapabilityNotFound(
2047:                 f"capability {record.capability_id!r} is not registered")
2048: 
2049:         # Promote eligible blocked/planned tasks only through explicit authorization.
2050:         if record.status == taskmod.BLOCKED:
2051:             missing = self.unsatisfied_dependencies(record)
2052:             if missing:
2053:                 raise errors.AjError(
2054:                     f"task {task_id} is still blocked by {', '.join(missing)}",
2055:                     code=errors.CALLING_INVALID_STATE)
2056:             # BLOCKED cannot transition directly to WAITING_FOR_APPROVAL/ABORTED in all cases;
2057:             # move through PLANNED for authorization decisions that require it.
2058:             self.tasks.transition(record.task_id, taskmod.PLANNED,
2059:                                   "dependencies satisfied; re-evaluating authorization")
2060:             record = self.tasks.get(task_id)
2061:             blocker = self._capability_blocker(spec)
2062:             if blocker is not None:
2063:                 final = (taskmod.ABORTED if isinstance(blocker, errors.PolicyDenied)
2064:                          else taskmod.FAILED)
2065:                 return self._fail(record, spec.owner_agent, spec.capability_id,
```
- **CURRENT-STATE REVALIDATION:** Partial; delegated current-authority (parent not cancelled/revoked/aborted/dead-letter, delegation active+linked, permission subset) not fully enforced at all boundaries (A3 xfail).
- **PERMISSION CHECK:** Delegated permission guard exists at boundary in parts; completeness/current-state proof missing.
- **CANCELLATION CHECK:** Cancelled/revoked parent/delegation handling incomplete for delegated cases.
- **REVOCATION CHECK:** Partial local checks; not exhaustive/proven fresh.
- **RACE PROTECTION:** Leases/dispatch ledger separate; no proven cross-store/race atomicity.
- **PERSISTED EVIDENCE:** Dispatch ledger, leases, task transitions, execution/audit evidence as applicable.
- **STATUS:** Partially guarded; D4 gaps.
- **DISPOSITION (target stage):** **S2-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Deterministic proof under lease/race windows for all prohibited delegated states.
- **What would make it verifiable:** Fault-injection/race seams with authoritative pre/post snapshots across stores.

### Aj.retry
- **CALLABLE:** `Aj.retry`
- **CALLERS (file:line list):** `aj/__main__.py:_cmd_retry` -> `aj.retry`; `aj/runtime.py` self-check (temp Aj).
- **ENTRY PATH:** CLI/internal -> `Aj.retry` -> recovery/transition logic.
- **DELEGATION CONTEXT POSSIBLE:** Possible (delegated contexts).
- **CURRENT GUARD (quote exact lines):**
```python
477:     def retry(self, task_id: str, *, approval: str = "") -> TaskOutcome:
478:         with self.leases.hold(task_id, "retry"):
479:             return self._retry_locked(task_id, approval=approval)
480: 
481:     def _retry_locked(self, task_id: str, *, approval: str = "") -> TaskOutcome:
482:         """Retry a failed task, bounded and gated by ``retry_safe``."""
483:         record = self.tasks.get(task_id)
484:         if record.status != taskmod.FAILED:
485:             raise errors.AjError(
486:                 f"task {task_id} is {record.status}; only FAILED tasks can be retried",
487:                 code=errors.CALLING_INVALID_STATE,
488:             )
489:         if record.attempt >= record.max_attempts:
490:             self.tasks.transition(task_id, taskmod.RECOVERING,
491:                                   "attempts exhausted")
492:             record = self.tasks.transition(task_id, taskmod.ESCALATED,
493:                                            "needs a human decision")
494:             record.requires_user_decision = True
495:             record = self.tasks.save(record, "retry_escalated")
496:             return TaskOutcome(
497:                 task_id=task_id, status=record.status, owner_agent=record.owner_agent,
498:                 capability_id=record.capability_id, ok=False,
499:                 summary=("Retry budget exhausted; the task is escalated and needs "
500:                          "a decision"),
```
- **CURRENT-STATE REVALIDATION:** Task/recovery checks apply; delegated D4 constraints (block/operator-evidence where required) not fully proven.
- **PERMISSION CHECK:** No proven full delegated current-authority revalidation.
- **CANCELLATION CHECK:** Delegated parent-cancelled/child-admin blocking not proven.
- **REVOCATION CHECK:** Not proven.
- **RACE PROTECTION:** Store locks; composite non-atomic.
- **PERSISTED EVIDENCE:** Task transitions/recovery evidence.
- **STATUS:** Partially guarded; delegation-specific constraints unproven.
- **DISPOSITION (target stage):** **S2-FIX / BLOCK-PER-D4 (as applicable) / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** All retry contexts involving delegated tasks and required D4 preconditions.
- **What would make it verifiable:** Caller/context inventory plus delegated negative/positive tests with persisted evidence.

### Aj.recover
- **CALLABLE:** `Aj.recover`
- **CALLERS (file:line list):** `aj/__main__.py:_cmd_recover` uses RecoveryManager and `aj.recovery_inspection`; `Aj.recover` task-level method exists.
- **ENTRY PATH:** CLI/internal -> recovery flows -> possible task transitions.
- **DELEGATION CONTEXT POSSIBLE:** Possible.
- **CURRENT GUARD (quote exact lines):**
```python
666:     def recover(self, task_id: str, *, approval: str = "") -> TaskOutcome:
667:         try:
668:             with self.leases.hold(task_id, "recover"):
669:                 return self._recover_locked(task_id, approval=approval)
670:         except (errors.LeaseHeld, errors.LeaseExpired) as exc:
671:             # Another active operation/execution owner serializes this task; recovery
672:             # must not steal ownership or replay. Report blocked/convergent refusal.
673:             try:
674:                 record = self.tasks.get(task_id)
675:                 self.audit.record(
676:                     "recovery_blocked", task_id=task_id,
677:                     operation_id=getattr(record, "operation_id", ""), agent="AJ",
678:                     capability=getattr(record, "capability_id", ""),
679:                     result="blocked", authorization="none",
680:                     detail=str(exc)[:300],
681:                 )
682:                 return TaskOutcome(
683:                     task_id=task_id, status=record.status, owner_agent="AJ",
684:                     capability_id=getattr(record, "capability_id", ""), ok=False,
685:                     summary=f"Recovery blocked: {exc}",
686:                     requires_user_decision=False, route_rule="recovery",
687:                 )
688:             except Exception:
689:                 raise
690: 
691:     # --- recovery evidence & decisions ------------------------------------
692: 
693:     def _recovery_evidence(self, record: taskmod.TaskRecord) -> Dict[str, Any]:
694:         """Collect best-effort durable evidence for recovery decisions.
695: 
696:         Evidence is observational and never implies success by absence. Journal/
697:         receipt reads are fail-closed on malformed or newer-schema data so recovery
698:         cannot infer a safe outcome from corrupted/incompatible evidence.
699:         """
700:         task_id = record.task_id
```
- **CURRENT-STATE REVALIDATION:** Recovery classification/inspection conservative in parts; delegated current authority/D4 not exhaustively enforced.
- **PERMISSION CHECK:** Not proven as full delegated permission/current-state gate.
- **CANCELLATION CHECK:** Not fully proven for delegated cancelled/revoked cases.
- **REVOCATION CHECK:** Not proven.
- **RACE PROTECTION:** No proven composite/race guarantees.
- **PERSISTED EVIDENCE:** Recovery findings/inspections and task evidence when applied.
- **STATUS:** Unproven for delegated edge cases.
- **DISPOSITION (target stage):** **S2-FIX / S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Proof prohibited delegated work never resumes/advances under revocation/cancellation/unverifiable delegation.
- **What would make it verifiable:** Boundary tests/seams with persisted pre/post delegated states.

### RecoveryManager._recover_one
- **CALLABLE:** `RecoveryManager._recover_one`
- **CALLERS (file:line list):** Internal to `RecoveryManager.recover` in `aj/recovery.py`.
- **ENTRY PATH:** Per-finding recovery action.
- **DELEGATION CONTEXT POSSIBLE:** Possible.
- **CURRENT GUARD (quote exact lines):**
```python
90:         # Delegate to orchestrator for a single source of truth on evidence,
91:         # convergence, ownership/lease safety, and fail-closed behavior.
92:         return self.aj.recover(task_id, approval="")
93: 
94:     def recover(self, task_id: Optional[str] = None) -> Dict[str, Any]:
95:         """Recover one task or every interrupted task.
96: 
97:         Explicit single-task recovery always runs through the orchestrator's
98:         evidence-based decision path and may return converged/blocked/manual
99:         outcomes without unsafe replay. Batch recovery attempts automatic recovery
100:         only for tasks assessed replay-safe; other findings are reported honestly.
101:         """
102:         if task_id:
103:             record = self.aj.tasks.get(task_id)
104:             finding = classify(self.aj, record)
105:             outcome = self._recover_one(task_id, finding=finding)
106:             # Re-read status after recovery attempt for honest reporting.
107:             try:
108:                 current = self.aj.tasks.get(task_id)
109:                 finding = Finding(finding.task_id, current.status, current.capability_id,
110:                                   finding.decision, finding.reason)
111:             except Exception:
112:                 pass
113:             return {"findings": [finding.to_dict()],
114:                     "outcomes": [outcome.to_dict()]}
115: 
116:         findings = self.scan()
117:         outcomes: List[Dict[str, Any]] = []
118:         for finding in findings:
119:             if finding.decision == REPLAY_SAFE:
120:                 try:
```
- **CURRENT-STATE REVALIDATION:** Depends on classification and downstream Aj/task behavior; delegated D4/current-authority not proven.
- **PERMISSION CHECK:** Not a dedicated delegated permission boundary.
- **CANCELLATION CHECK:** Not proven for delegated cancelled/revoked cases.
- **REVOCATION CHECK:** Not proven.
- **RACE PROTECTION:** No proven composite atomicity.
- **PERSISTED EVIDENCE:** Recovery outcomes and downstream task evidence.
- **STATUS:** Unproven for delegated cases.
- **DISPOSITION (target stage):** **S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Branch-complete behavior for delegated findings and required blocks.
- **What would make it verifiable:** Per-classification tests with delegated fixtures and persisted outcomes.

### Aj.cancel_task
- **CALLABLE:** `Aj.cancel_task`
- **CALLERS (file:line list):** `aj/__main__.py:_cmd_cancel` -> `aj.cancel_task`.
- **ENTRY PATH:** CLI/internal -> task cancellation transition(s).
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
607:     def cancel_task(self, task_id: str) -> TaskOutcome:
608:         with self.leases.hold(task_id, "cancel"):
609:             return self._cancel_locked(task_id)
610: 
611:     def _cancel_locked(self, task_id: str) -> TaskOutcome:
612:         """Cancel a task honestly: no forced termination of running work."""
613:         record = self.tasks.get(task_id)
614:         if record.terminal:
615:             self.audit.record("cancel_refused", task_id=task_id,
616:                               operation_id=record.operation_id, agent="AJ",
617:                               capability=record.capability_id, result=record.status,
618:                               authorization="none",
619:                               detail="task is already terminal")
620:             return TaskOutcome(
621:                 task_id=task_id, status=record.status,
622:                 owner_agent=record.owner_agent,
623:                 capability_id=record.capability_id, ok=False,
624:                 summary=f"Task is already {record.status}; nothing was changed",
625:                 route_rule="cancel",
626:             )
627:         if record.status == taskmod.EXECUTING:
628:             self.tasks.transition(record.task_id, taskmod.CANCEL_REQUESTED,
629:                                  "operator requested cancellation")
630:             record = self.tasks.get(record.task_id)
631:             record.requires_user_decision = True
632:             record = self.tasks.save(record, "cancel_requested")
633:             self.audit.record("cancel_requested", task_id=task_id,
634:                               operation_id=record.operation_id, agent="AJ",
635:                               capability=record.capability_id, result="requested",
636:                               authorization="operator",
637:                               detail="running execution was not interrupted")
638:             self._remember(record, "task.cancel_requested",
639:                            "cancellation requested; execution not interrupted",
640:                            {"status": record.status})
```
- **CURRENT-STATE REVALIDATION:** FSM checks on target transition; parent-cancel propagation to non-terminal delegated children incomplete/unsafe (A4 xfail).
- **PERMISSION CHECK:** Not a delegated permission-narrowing boundary.
- **CANCELLATION CHECK:** Target task cancelled path; propagation/safety for active delegated children not per D4.
- **REVOCATION CHECK:** Not proven.
- **RACE PROTECTION:** Store locks; no proven race safety with dispatch/child outcomes.
- **PERSISTED EVIDENCE:** Task status/history; required delegation/assignment propagation evidence not complete.
- **STATUS:** Known D4 propagation gap.
- **DISPOSITION (target stage):** **S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Cooperative propagation behavior for all child states (incl EXECUTING/CANCEL_REQUESTED) and concurrent/late outcomes.
- **What would make it verifiable:** Stateful/race-seam tests with delegation/assignment/task evidence assertions.

### Aj.cancel
- **CALLABLE:** `Aj.cancel`
- **CALLERS (file:line list):** `aj/orchestrator.py:663` wrapper (callers not fully enumerated).
- **ENTRY PATH:** Wrapper -> cancellation behavior.
- **DELEGATION CONTEXT POSSIBLE:** Possible.
- **CURRENT GUARD (quote exact lines):**
```python
663:     def cancel(self, task_id: str) -> bool:
664:         return self.cancel_task(task_id).ok
665: 
666:     def recover(self, task_id: str, *, approval: str = "") -> TaskOutcome:
```
- **CURRENT-STATE REVALIDATION:** Inherits underlying limits; no extra revalidation.
- **PERMISSION CHECK:** None specific.
- **CANCELLATION CHECK:** Inherits cancel gaps.
- **REVOCATION CHECK:** Inherits gaps.
- **RACE PROTECTION:** Inherits underlying.
- **PERSISTED EVIDENCE:** Inherits underlying.
- **STATUS:** Thin wrapper.
- **DISPOSITION (target stage):** **S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Complete caller inventory and context expectations.
- **What would make it verifiable:** Caller audit + context tests.

### Aj.reconcile (operator action dispatcher)
- **CALLABLE:** `Aj.reconcile (operator action dispatcher)`
- **CALLERS (file:line list):** `aj/__main__.py:_cmd_reconcile` -> `aj.reconcile`.
- **ENTRY PATH:** CLI/operator -> privileged action dispatch (dead_letter, abandon, clear_recovery_required, etc.).
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
2864:     def reconcile(self, task_id: str, action: str, *, reason: str,
2865:                   evidence_basis: Any = None, operator: str = "operator",
2866:                   target_status: str = "", operation_id: str = "",
2867:                   idempotency_key: str = "") -> Dict[str, Any]:
2868:         """Explicit, narrowly-scoped operator reconciliation (Phase 3D/3E).
2869: 
2870:         Supported actions (validated, fail-closed):
2871:           - abort: RECOVERY_REQUIRED -> ABORTED (operator confirms no safe replay / resolved as aborted)
2872:           - dead_letter: RECOVERY_REQUIRED -> DEAD_LETTER (explicit unrecoverable disposition)
2873:           - abandon: mark task as ABANDONED via existing controlled semantics (legacy-compatible terminal operator disposition)
2874:           - clear_recovery_required: RECOVERY_REQUIRED -> FAILED only when no active execution ownership and
2875:             evidence is not malformed/conflicting for this operator decision; allows subsequent explicit retry
2876:             flow under existing retry authorization/budget rules (no automatic execution, no ownership theft).
2877: 
2878:         Phase 3E: durable operation evidence (intent/outcome), idempotent duplicate prevention for known
2879:         operation IDs, and fail-closed privileged-operation authorization guardrail. Never fabricates success.
2880:         """
2881:         action = (action or "").strip().lower()
2882:         reason = (reason or "").strip()
2883:         # Caller-supplied label is metadata only; never authenticated identity.
2884:         requested_operator = "" if operator is None else str(operator)
2885:         idempotency_key = (idempotency_key or "").strip()
2886:         # Stable operation identity for this reconciliation attempt
2887:         op_id = (operation_id or "").strip() or ids.new_task_id("rop")
2888: 
2889:         def _authz_audit_params(decision):
2890:             d = getattr(decision, "to_dict", lambda: {})() or {}
2891:             prov = d.get("provenance") or {}
2892:             principal = d.get("principal") if d.get("principal") is not None else d.get("identity")
2893:             authenticated = bool(d.get("authenticated") and principal)
2894:             return {
2895:                 "operation_kind": "reconciliation",
2896:                 "action": action,
2897:                 "operation_id": op_id,
2898:                 "decision": d.get("outcome") or ("allow" if d.get("allowed") else "deny"),
2899:                 "authenticated": authenticated,
2900:                 "principal_identity": principal,
2901:                 "principal_source": d.get("principal_source") or prov.get("principal_source") or "none",
2902:                 "identity_provider": d.get("identity_provider") or prov.get("identity_provider") or "",
2903:                 "requested_operator": d.get("requested_operator") or prov.get("requested_operator") or requested_operator,
2904:                 "requested_operator_provided": bool(requested_operator),
2905:                 "trust_assumption": d.get("trust_assumption") or prov.get("trust_assumption") or "",
```
- **CURRENT-STATE REVALIDATION:** Privileged authorizer and action logic in parts; D4 constraints for delegated child dead_letter/abandon and parent-with-non-terminal-children not fully enforced/proven. Action set not exhaustively enumerated here.
- **PERMISSION CHECK:** Privileged auth may apply; delegated current-authority semantics unproven per action.
- **CANCELLATION CHECK:** Not fully enforced per D4 for delegated cases.
- **REVOCATION CHECK:** Not fully proven.
- **RACE PROTECTION:** No proven cross-store atomicity.
- **PERSISTED EVIDENCE:** Task/audit/journal/reconciliation evidence action-dependent.
- **STATUS:** Action-dependent; delegation constraints incomplete.
- **DISPOSITION (target stage):** **S2-FIX / S3-FIX / BLOCK-PER-D4 (per action) / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Exact implemented action list and per-action delegated preconditions/evidence requirements.
- **What would make it verifiable:** Enumerate handlers/actions and add allow/deny tests with persisted evidence.

### Aj.dead_letter
- **CALLABLE:** `Aj.dead_letter`
- **CALLERS (file:line list):** Operator/internal paths (incl reconcile actions) and potentially scheduler dispatch failure path; callers not exhaustively enumerated.
- **ENTRY PATH:** Caller -> transition to DEAD_LETTER (wrapped).
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
2244:     def dead_letter(self, task_id: str, reason: str) -> taskmod.TaskRecord:
2245:         record = self.tasks.get(task_id)
2246:         if record.status != taskmod.DEAD_LETTER:
2247:             if not record.can_transition(taskmod.DEAD_LETTER):
2248:                 raise errors.AjError(
2249:                     f"task {task_id} cannot be dead-lettered from {record.status}",
2250:                     code=errors.CALLING_INVALID_STATE)
2251:             self.tasks.transition(task_id, taskmod.DEAD_LETTER, reason)
2252:             record = self.tasks.get(task_id)
2253:             record.requires_user_decision = True
2254:             self.tasks.save(record, "dead_letter")
2255:             self.audit.record("task_dead_lettered", task_id=task_id,
2256:                               operation_id=record.operation_id,
2257:                               capability=record.capability_id,
2258:                               result="dead_letter", detail=reason[:300])
```
- **CURRENT-STATE REVALIDATION:** FSM/wrapped transition apply; direct delegated-child use not safely restricted per D4 (A2a xfail).
- **PERMISSION CHECK:** No delegated permission narrowing boundary.
- **CANCELLATION CHECK:** Parent-cancelled/child-admin D4 constraints not enforced as required.
- **REVOCATION CHECK:** Not proven.
- **RACE PROTECTION:** Store locks only.
- **PERSISTED EVIDENCE:** Task state/history; required delegation evidence/parent reconcile not guaranteed on all paths.
- **STATUS:** Unsafe in some delegated contexts.
- **DISPOSITION (target stage):** **BLOCK-PER-D4 / S2-FIX**
- **Exact missing information/seam (NOT VERIFIABLE reason):** All call sites and compliant operator-only path enforcement details.
- **What would make it verifiable:** Call-site audit and tests denying unsafe paths, allowing only compliant operator reconcile path.

### Aj.requeue
- **CALLABLE:** `Aj.requeue`
- **CALLERS (file:line list):** Internal/operator method (no direct CLI `_cmd_requeue` found); callers not exhaustive.
- **ENTRY PATH:** Caller -> `tasks.transition(..., DEAD_LETTER->PLANNED, force=True)`.
- **DELEGATION CONTEXT POSSIBLE:** Yes (must be blocked for delegated tasks per D4).
- **CURRENT GUARD (quote exact lines):**
```python
3408:     def requeue(self, task_id: str) -> TaskRecord:
3409: 
3410:         """Requeue a dead-letter task for re-execution.
3411: 
3412:         Transitions the task from DEAD_LETTER back to PLANNED state,
3413:         preserving all historical identity, attempts, failure history,
3414:         and audit/journal records. A new execution attempt will be
3415:         created when the task is next executed.
3416: 
3417:         Requirements:
3418:         - preserve original task identity
3419:         - preserve operation identity
3420:         - preserve historical attempts
3421:         - do not erase failure history
3422:         - do not reset historical audit/journal records
3423:         - create a new execution attempt when execution occurs
3424:         - preserve idempotency semantics
3425:         - respect dependencies
3426:         - respect task state transition rules
3427:         - prevent duplicate logical operations
3428: 
3429:         Requeue MUST NOT silently create a brand-new logical task.
3430:         """
3431:         record = self.tasks.get(task_id)
3432:         if record.status != taskmod.DEAD_LETTER:
3433:             raise errors.AjError(
3434:                 f"task {task_id} is not in DEAD_LETTER state (current: {record.status})",
3435:                 code=errors.CALLING_INVALID_STATE)
3436:         # Transition from DEAD_LETTER to PLANNED through store-controlled forced transition.
3437:         self.tasks.transition(task_id, taskmod.PLANNED, "requeue from dead-letter",
3438:                               force=True, reason="requeue")
3439:         record = self.tasks.get(task_id)
3440:         record.requires_user_decision = False
3441:         # Preserve the original operation_id and capability_id
3442:         # Create a new execution attempt tracking entry
3443:         number = max(int(record.attempt), len(record.attempts) + 1) if record.attempts else 1
3444:         record.attempt = number
3445:         attempt = {
```
- **CURRENT-STATE REVALIDATION:** `force=True` bypasses completion guard branch; delegated-task blocking not enforced (A2b xfail).
- **PERMISSION CHECK:** No D4 delegated revalidation.
- **CANCELLATION CHECK:** Not enforced (A2b).
- **REVOCATION CHECK:** Not enforced.
- **RACE PROTECTION:** No proven resurrection/race protection.
- **PERSISTED EVIDENCE:** Task transition persisted.
- **STATUS:** Known D4 gap.
- **DISPOSITION (target stage):** **BLOCK-PER-D4 / S2-FIX**
- **Exact missing information/seam (NOT VERIFIABLE reason):** All callers and required allowed/denied contexts.
- **What would make it verifiable:** Deny delegated-context tests and any policy-approved allowed path tests.

### Aj.abandon
- **CALLABLE:** `Aj.abandon`
- **CALLERS (file:line list):** Method callable directly and via operator flows (callers not exhaustive).
- **ENTRY PATH:** Caller -> refuses if already ABANDONED else `tasks.transition(..., ABANDONED, force=True)`.
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
3467:     def abandon(self, task_id: str, reason: str = "") -> TaskRecord:
3468:         """Explicitly abandon a dead-letter task.
3469: 
3470:         Produces a deterministic terminal state consistent with the
3471:         existing architecture. The task and operation history are preserved
3472:         entirely; all attempts are preserved; audit/journal history is
3473:         preserved; future automatic execution is prevented.
3474: 
3475:         Requirements:
3476:         - preserve the task and operation history
3477:         - preserve all attempts
3478:         - preserve audit/journal history
3479:         - prevent future automatic execution
3480:         - produce a deterministic terminal state consistent with the existing architecture
3481:         - remain inspectable
3482: 
3483:         Do not delete the task.
3484:         Do not erase evidence.
3485:         Do not silently convert abandonment into success.
3486:         """
3487:         record = self.tasks.get(task_id)
3488:         if record.status == "ABANDONED":
3489:             raise errors.AjError(
3490:                 f"task {task_id} is already abandoned",
3491:                 code=errors.CALLING_INVALID_STATE)
3492:         # Mark as abandoned through store-controlled mutation (ABANDONED is a
3493:         # special terminal state outside normal transitions).
3494:         record = self.tasks.transition(task_id, "ABANDONED",
3495:                                        reason or "task abandoned",
3496:                                        force=True, reason="abandoned")
3497:         record.requires_user_decision = False
3498:         if reason:
3499:             record.record_error(f"abandoned: {reason}", stage="abandonment")
3500:         else:
3501:             record.record_error("task abandoned", stage="abandonment")
3502:         record = self.tasks.save(record, "abandoned")
3503:         self.audit.record("task_abandoned", task_id=task_id,
3504:                           operation_id=record.operation_id,
3505:                           capability=record.capability_id,
```
- **CURRENT-STATE REVALIDATION:** No D3-refinement source-state validation (legal: FAILED/DEAD_LETTER/RECOVERY_REQUIRED/ESCALATED only). `force=True` used; ABANDONED model/load issues (A1/A1b/A8). Delegated direct abandon/parent constraints per D4 not enforced (A2c).
- **PERMISSION CHECK:** No delegated permission boundary.
- **CANCELLATION CHECK:** Delegated constraints unproven.
- **REVOCATION CHECK:** Not enforced.
- **RACE PROTECTION:** No proven race/composite guarantees.
- **PERSISTED EVIDENCE:** Task state persisted (reload/import semantics problematic).
- **STATUS:** D3/D4 mismatch.
- **DISPOSITION (target stage):** **S1-FIX / S2-FIX / BLOCK-PER-D4**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Approved migration/compat for ABANDONED and all caller contexts.
- **What would make it verifiable:** Implement D3/D4 then tests for allowed/denied sources, delegated contexts, reload/import.

### Aj.delegate
- **CALLABLE:** `Aj.delegate`
- **CALLERS (file:line list):** External/orchestrator callers (CLI not enumerated).
- **ENTRY PATH:** Request -> validate/create delegation, child task(s), assignments, prep evidence.
- **DELEGATION CONTEXT POSSIBLE:** Yes (delegation entry).
- **CURRENT GUARD (quote exact lines):**
```python
4230:     def delegate(self, request: Mapping[str, Any], *, actor: str = "aj") -> Dict[str, Any]:
4231:         """Controlled logical/internal delegation foundation (5A.6). No real remote transport."""
4232:         from .delegation import (
4233:             DelegationRequest, DelegationRecord, AssignmentRecord, LogicalAgentRecord,
4234:             stable_delegation_id, stable_assignment_id, match_agent, narrow_permissions,
4235:             validate_parent_chain, compute_root_task_id,
4236:             AS_PROPOSED, AS_ASSIGNED, AS_REJECTED, AGENT_TRUST_UNVERIFIED,
4237:         )
4238:         cfg = self._delegation_config()
4239:         if not bool(cfg.get("enabled", True)):
4240:             raise errors.PolicyDenied("delegation is disabled by configuration")
4241:         self._ensure_delegation_stores()
4242:         self._seed_logical_agents()
4243:         req = DelegationRequest.validate(request, config_max_children=int(cfg.get("max_children_per_delegation", 10)))
4244:         # idempotency: same key with different specification must be rejected.
4245:         if req.idempotency_key:
4246:             existing = self.delegations.find_by_idempotency(req.idempotency_key)
4247:             if existing:
4248:                 if existing.request.spec_hash() != req.spec_hash() or existing.request.parent_task_id != req.parent_task_id:
4249:                     raise errors.Conflict("same delegation idempotency key with different specification")
4250:                 return self.delegation_status(existing.delegation_id)
4251: 
4252:         parent = self.tasks.get(req.parent_task_id)
4253:         # parent must be allowed to delegate (conservative: not terminal/aborted/failed-final-only states for delegation intent)
4254:         if parent.terminal or parent.status in (taskmod.ABORTED, taskmod.CANCELLED, taskmod.DEAD_LETTER, taskmod.FAILED):
4255:             raise errors.Conflict(f"parent task {parent.task_id} is not allowed to delegate in state {parent.status}")
4256: 
4257:         # bounded per-parent delegations
4258:         existing_for_parent = self.delegations.list_for_parent(parent.task_id)
4259:         if len(existing_for_parent) >= int(cfg.get("max_delegations_per_parent", 20)):
4260:             raise errors.PolicyDenied("delegation bound exceeded: max_delegations_per_parent")
4261:         if len(req.child_specs) > int(cfg.get("max_children_per_delegation", 10)):
4262:             raise errors.PolicyDenied("delegation bound exceeded: max_children_per_delegation")
4263: 
4264:         # deterministic delegation id (stable for same idempotency key or same contract spec)
4265:         delegation_id = stable_delegation_id(req.idempotency_key, parent_task_id=parent.task_id, spec_hash=req.spec_hash())
4266:         existing_d = self.delegations.get(delegation_id)
4267:         if existing_d:
4268:             return self.delegation_status(delegation_id)
4269: 
4270:         # validate hierarchy/root
4271:         _, root_id = validate_parent_chain(self.tasks, parent.task_id)
4272:         root_id = root_id or (parent.root_task_id or parent.task_id)
4273: 
4274:         # pre-validate all child refs and hierarchy targets (no partial writes before record intent)
4275:         child_task_ids: List[str] = []
```
- **CURRENT-STATE REVALIDATION:** Partial validation; D1 explicit required bool/default_source and D5/T-11 unsupported-claim rejection/reporting incomplete (A6/A7).
- **PERMISSION CHECK:** Request/state validation not fully Doc58-compliant; narrowing partial and malformed/unsupported not fully rejected.
- **CANCELLATION CHECK:** Parent/task checks partial.
- **REVOCATION CHECK:** Linkage checks partial.
- **RACE PROTECTION:** Multi-store non-atomic writes.
- **PERSISTED EVIDENCE:** Delegation/child/assignment/journal/audit records (where emitted).
- **STATUS:** Known D1/D5 gaps.
- **DISPOSITION (target stage):** **S1-FIX / S2-FIX**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Complete unsupported-claim surface inventory and all reporting points.
- **What would make it verifiable:** Negative matrix for claims/classification with persisted/report assertions.

### Aj.reconcile_delegation_parent
- **CALLABLE:** `Aj.reconcile_delegation_parent`
- **CALLERS (file:line list):** `Aj._on_task_transition` and explicit public method callers.
- **ENTRY PATH:** Public wrapper -> guarded `_reconcile_delegation_parent` (dry-run/apply).
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
3828:             dry_run = True
3829:         batch = max(1, min(int(batch_size or 50), 100))
3830:         with self._delegation_reconcile_guard:
3831:             return self._reconcile_delegation_parent(parent_task_id, trigger=f"explicit:{'dry_run' if dry_run else 'apply'}",
3832:                                                      dry_run=dry_run, apply_parent_policy=bool(apply),
3833:                                                      bounded_batch=batch, actor=actor)
3834: 
3835:     def _delegated_permission_guard(self, record: taskmod.TaskRecord, spec: CapabilitySpec) -> Optional[TaskOutcome]:
3836:         """Fail-closed execution-boundary enforcement for delegated child permissions.
3837: 
3838:         Revalidates recorded delegation evidence against current local trusted state
3839:         where available (parent/delegation/task consistency). Does not claim
3840:         authenticated identity or cross-store atomicity.
3841:         """
3842:         dctx = ((getattr(record, "authorization_context", None) or {}).get("delegation") or {})
3843:         if not dctx:
3844:             return None
3845:         perm = dctx.get("permission_decision") or {}
3846:         if not isinstance(perm, dict) or not perm.get("ok"):
3847:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3848:                               errors.PolicyDenied("delegated execution blocked: permission narrowing evidence missing/invalid"),
3849:                               "authorization", final=taskmod.ABORTED)
3850:         effective = perm.get("effective_permissions")
3851:         if not isinstance(effective, list) or any(not isinstance(x, str) for x in effective):
3852:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3853:                               errors.PolicyDenied("delegated execution blocked: malformed effective permission envelope"),
3854:                               "authorization", final=taskmod.ABORTED)
3855:         # Current-state consistency checks (fail closed on unverifiable revocation/cancellation indicators).
3856:         parent_id = str(dctx.get("parent_task_id") or getattr(record, "parent_task_id", "") or "")
3857:         delegation_id = str(dctx.get("delegation_id") or "")
3858:         if not parent_id:
```
- **CURRENT-STATE REVALIDATION:** Dry-run/apply separation and locking present; contradiction/stale-writer correctness unproven.
- **PERMISSION CHECK:** N/A.
- **CANCELLATION CHECK:** Apply effects interact with D4 semantics but not fully proven safe.
- **REVOCATION CHECK:** Indirect.
- **RACE PROTECTION:** Reconcile guard + reentrancy controls; limited.
- **PERSISTED EVIDENCE:** Delegation evidence/history, possible task/assignment mutations.
- **STATUS:** Partially idempotent by design; unproven broadly.
- **DISPOSITION (target stage):** **S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Proof for stale/concurrent/contradictory/interrupted cases.
- **What would make it verifiable:** Concurrency/fault-injection seams and deterministic fixtures.

### Aj._reconcile_delegation_parent
- **CALLABLE:** `Aj._reconcile_delegation_parent`
- **CALLERS (file:line list):** Internal: wrapper and transition hook.
- **ENTRY PATH:** Core reconciliation/aggregation/apply logic.
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
4030:     def _reconcile_delegation_parent(self, parent_task_id: str, *, trigger: str = "explicit",
4031:                                      source_child_task_id: str = "", dry_run: bool = False,
4032:                                      apply_parent_policy: bool = False, bounded_batch: int = 50,
4033:                                      actor: str = "system") -> Dict[str, Any]:
4034:         """Delegation reconciliation (dry-run read-only or explicit apply, bounded/idempotent)."""
4035:         if not self.delegations:
4036:             return {"ok": False, "reason": "delegation_stores_unavailable", "dry_run": dry_run}
4037:         try:
4038:             dels = list(self.delegations.list_for_parent(parent_task_id) or [])
4039:         except Exception as exc:
4040:             return {"ok": False, "reason": f"delegation_read_failed:{type(exc).__name__}", "dry_run": dry_run}
4041:         batch = max(1, min(int(bounded_batch or 50), 100))
4042:         dels = dels[:batch]
4043:         from .delegation import aggregate_parent_progress
4044:         results = []
4045:         for d in dels:
4046:             child_ids = list(getattr(d, "child_task_ids", []) or [])
4047:             child_results = []
4048:             # In apply mode, attempt safe child preparation (bounded). Dry-run must not mutate.
4049:             if not dry_run and apply_parent_policy:
4050:                 for cid in child_ids:
4051:                     try:
4052:                         child_results.append(self._prepare_delegated_child_for_scheduling(cid))
4053:                     except Exception as exc:
4054:                         child_results.append({"task_id": cid, "ok": False, "reason": f"prepare_error:{type(exc).__name__}"})
4055:             snapshot = self._delegation_child_snapshot(child_ids, self.tasks)
4056:             agg = aggregate_parent_progress(self.tasks, parent_task_id=d.request.parent_task_id,
4057:                                             child_task_ids=child_ids,
4058:                                             aggregation_policy=d.request.aggregation_policy,
4059:                                             required_child_task_ids=(d.request.required_child_ids or child_ids))
4060:             agg = dict(agg)
4061:             agg["child_state_snapshot"] = snapshot
4062:             # stale/contradiction detection vs previous evidence
4063:             ev = dict(getattr(d, "evidence", {}) or {})
4064:             prev = ev.get("last_reconciliation") or {}
4065:             prev_hash = (((prev.get("aggregation") or {}).get("child_state_snapshot") or {}).get("hash")
```
- **CURRENT-STATE REVALIDATION:** Internal branch behavior not fully proven against Doc58 invariants.
- **PERMISSION CHECK:** N/A.
- **CANCELLATION CHECK:** D4 interactions unproven.
- **REVOCATION CHECK:** N/A.
- **RACE PROTECTION:** Caller lock context; limited.
- **PERSISTED EVIDENCE:** Delegation evidence/mutations.
- **STATUS:** Unproven.
- **DISPOSITION (target stage):** **S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Branch-complete spec/proof and interruption behavior.
- **What would make it verifiable:** White-box branch tests with injected failures.

### Aj._prepare_delegated_child_for_scheduling
- **CALLABLE:** `Aj._prepare_delegated_child_for_scheduling`
- **CALLERS (file:line list):** Internal from delegate/reconcile apply paths (AST: 2 call sites).
- **ENTRY PATH:** Prep delegated child through planning/authorization to schedulable/waiting state.
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
3924:     def _prepare_delegated_child_for_scheduling(self, task_id: str) -> Dict[str, Any]:
3925:         """Progress a delegated child through existing planning/authorization paths to a schedulable
3926:         or explicit waiting/deferred state. Does not dispatch/execute (scheduler owns dispatch)."""
3927:         record = self.tasks.get(task_id)
3928:         # Conservative parent-cancellation/delegation-authority enforcement (Priority B/A).
3929:         dctx = ((getattr(record, "authorization_context", None) or {}).get("delegation") or {})
3930:         if dctx:
3931:             parent_id = str(dctx.get("parent_task_id") or getattr(record, "parent_task_id", "") or "")
3932:             try:
3933:                 parent = self.tasks.get(parent_id) if parent_id else None
3934:             except Exception:
3935:                 parent = None
3936:             if parent is None or getattr(parent, "status", "") in (
3937:                 taskmod.CANCELLED, taskmod.CANCEL_REQUESTED, taskmod.ABORTED, taskmod.DEAD_LETTER
3938:             ):
3939:                 # Fail closed: do not prepare/authorize new delegated work under cancelled/revoked/unverifiable parent.
3940:                 if not record.terminal and record.can_transition(taskmod.ABORTED):
3941:                     try:
3942:                         self.tasks.transition(task_id, taskmod.ABORTED, "delegated parent cancelled/revoked/unverifiable")
3943:                     except Exception:
3944:                         pass
3945:                 return {"task_id": task_id, "status": self.tasks.get(task_id).status, "ok": False,
3946:                         "reason": "parent_cancelled_or_unverifiable"}
3947:         if record.terminal:
3948:             return {"task_id": task_id, "status": record.status, "ok": False, "reason": "terminal"}
3949:         if record.status == taskmod.AUTHORIZED:
3950:             return {"task_id": task_id, "status": record.status, "ok": True, "reason": "already_authorized"}
3951:         if record.status not in (taskmod.RECEIVED, taskmod.UNDERSTANDING, taskmod.PLANNED,
3952:                                  taskmod.WAITING_FOR_APPROVAL, taskmod.BLOCKED):
3953:             return {"task_id": task_id, "status": record.status, "ok": False, "reason": "not_prepareable"}
3954:         # advance to PLANNED
3955:         try:
```
- **CURRENT-STATE REVALIDATION:** Partial checks; must fully enforce current delegation/parent authority per D4 (not fully proven).
- **PERMISSION CHECK:** Incomplete/unproven for D4.
- **CANCELLATION CHECK:** Incomplete (A2/A3 context).
- **REVOCATION CHECK:** Partial.
- **RACE PROTECTION:** No proven race protection.
- **PERSISTED EVIDENCE:** Task transitions/prep evidence.
- **STATUS:** Incomplete for D4.
- **DISPOSITION (target stage):** **S2-FIX**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Exhaustive prohibited-state preconditions and race behavior.
- **What would make it verifiable:** Negative tests for each prohibited state and concurrent changes.

### Aj._delegated_permission_guard
- **CALLABLE:** `Aj._delegated_permission_guard`
- **CALLERS (file:line list):** Delegated execution boundary in orchestrator paths.
- **ENTRY PATH:** Validate delegation evidence, parent/delegation linkage/status, snapshots/scope before execution; fail closed.
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
3860:                               errors.PolicyDenied("delegated execution blocked: missing parent linkage"),
3861:                               "authorization", final=taskmod.ABORTED)
3862:         try:
3863:             parent = self.tasks.get(parent_id)
3864:         except Exception:
3865:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3866:                               errors.PolicyDenied("delegated execution blocked: parent task unverifiable"),
3867:                               "authorization", final=taskmod.ABORTED)
3868:         # Conservative revocation/cancellation handling: if parent delegation authority is no longer valid,
3869:         # delegated child execution must not proceed (no fabricated continuation).
3870:         if getattr(parent, "status", "") in (taskmod.CANCELLED, taskmod.CANCEL_REQUESTED, taskmod.ABORTED, taskmod.DEAD_LETTER):
3871:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3872:                               errors.PolicyDenied("delegated execution blocked: parent delegation authority revoked/cancelled"),
3873:                               "authorization", final=taskmod.ABORTED)
3874:         if self.delegations and delegation_id:
3875:             try:
3876:                 drec = self.delegations.get(delegation_id)
3877:             except Exception:
3878:                 drec = None
3879:             if drec is None:
3880:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3881:                                   errors.PolicyDenied("delegated execution blocked: delegation record unverifiable"),
3882:                                   "authorization", final=taskmod.ABORTED)
3883:             if str(getattr(drec.request, "parent_task_id", "") or "") != parent_id:
3884:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3885:                                   errors.PolicyDenied("delegated execution blocked: delegation-parent mismatch"),
3886:                                   "authorization", final=taskmod.ABORTED)
3887:             if getattr(drec, "status", "") in ("FAILED", "CANCELLED", "REVOKED"):
3888:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3889:                                   errors.PolicyDenied("delegated execution blocked: delegation no longer active"),
3890:                                   "authorization", final=taskmod.ABORTED)
3891:             if record.task_id not in list(getattr(drec, "child_task_ids", []) or []):
3892:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3893:                                   errors.PolicyDenied("delegated execution blocked: child not linked to delegation"),
3894:                                   "authorization", final=taskmod.ABORTED)
3895:         # Conservative envelope checks against recorded snapshots (narrowing only).
3896:         req_snapshot = dctx.get("requested_permissions_snapshot")
3897:         if isinstance(req_snapshot, list):
3898:             if not set(effective).issubset({str(x) for x in req_snapshot if isinstance(x, str)}):
3899:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3900:                                   errors.PolicyDenied("delegated execution blocked: effective permissions exceed requested envelope"),
3901:                                   "authorization", final=taskmod.ABORTED)
3902:         elif req_snapshot is not None:
3903:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3904:                               errors.PolicyDenied("delegated execution blocked: malformed requested permission snapshot"),
3905:                               "authorization", final=taskmod.ABORTED)
3906:         parent_snapshot = dctx.get("parent_permissions_snapshot")
3907:         if isinstance(parent_snapshot, list):
3908:             if not set(effective).issubset({str(x) for x in parent_snapshot if isinstance(x, str)}):
3909:                 return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3910:                                   errors.PolicyDenied("delegated execution blocked: effective permissions exceed parent envelope"),
3911:                                   "authorization", final=taskmod.ABORTED)
3912:         elif parent_snapshot is not None:
3913:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3914:                               errors.PolicyDenied("delegated execution blocked: malformed parent permission snapshot"),
3915:                               "authorization", final=taskmod.ABORTED)
3916:         # Logical-internal delegated children must remain within delegation-coordination scope
3917:         # unless an explicit broader execution envelope is verifiably authorized (not implemented).
3918:         if dctx.get("logical_internal") and effective and set(effective) - {"delegation.coordinate"}:
3919:             return self._fail(record, spec.owner_agent, record.capability_id or spec.capability_id,
3920:                               errors.PolicyDenied("delegated execution blocked: unverifiable permission scope for logical-internal delegation"),
3921:                               "authorization", final=taskmod.ABORTED)
3922:         return None
3923: 
3924:     def _prepare_delegated_child_for_scheduling(self, task_id: str) -> Dict[str, Any]:
3925:         """Progress a delegated child through existing planning/authorization paths to a schedulable
3926:         or explicit waiting/deferred state. Does not dispatch/execute (scheduler owns dispatch)."""
3927:         record = self.tasks.get(task_id)
```
- **CURRENT-STATE REVALIDATION:** Revalidates current local task/delegation records and snapshot subsets at boundary; cannot guarantee external freshness/atomicity.
- **PERMISSION CHECK:** Yes (effective vs snapshots, logical-internal scope).
- **CANCELLATION CHECK:** Blocks on parent cancelled/revoked/cancel-requested/aborted/dead-letter and inactive delegation states checked.
- **REVOCATION CHECK:** Blocks on unverifiable/missing/inactive delegation/parent linkage as implemented.
- **RACE PROTECTION:** Check-then-act not cross-store/race-proof.
- **PERSISTED EVIDENCE:** Failure leads to abort/fail outcomes and task evidence (path-dependent).
- **STATUS:** Strong local fail-closed intent with scope limits.
- **DISPOSITION (target stage):** **S2-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Coverage of every delegated execution entry path and race/freshness guarantees.
- **What would make it verifiable:** Call-site coverage instrumentation plus race/seam tests.

### Aj._before_task_transition
- **CALLABLE:** `Aj._before_task_transition`
- **CALLERS (file:line list):** Aj-wrapped `tasks.transition` pre-hook for all transitions on Aj-owned store.
- **ENTRY PATH:** Blocks non-force delegated-parent COMPLETED when aggregation cannot complete or requires manual review; fail-closed on unverifiable state.
- **DELEGATION CONTEXT POSSIBLE:** Yes (parent completion).
- **CURRENT GUARD (quote exact lines):**
```python
3733:     def _before_task_transition(self, task_id: str, status: str, detail: str = "",
3734:                                 *, force: bool = False, reason: str = "transition") -> None:
3735:         """Fail closed on invalid delegation-parent completion transitions."""
3736:         if force or status != taskmod.COMPLETED:
3737:             return
3738:         dels = self._delegations_for_parent(task_id)
3739:         if not dels:
3740:             return
3741:         try:
3742:             # Conservative: if any delegation for parent cannot be safely completed, block completion.
3743:             for d in dels:
3744:                 agg = aggregate_parent_progress(
3745:                     self.tasks, parent_task_id=d.request.parent_task_id,
3746:                     child_task_ids=d.child_task_ids,
3747:                     aggregation_policy=d.request.aggregation_policy,
3748:                     required_child_task_ids=(d.request.required_child_ids or d.child_task_ids),
3749:                 )
3750:                 if not agg.get("can_complete", False) or agg.get("requires_manual_review", False):
3751:                     raise errors.Conflict(
3752:                         f"parent task {task_id} cannot complete: required child work unresolved/uncertain/manual-review",
3753:                         detail={"delegation_id": getattr(d, "delegation_id", ""), "aggregation": agg},
3754:                     )
3755:         except errors.Conflict:
3756:             raise
3757:         except Exception as exc:
3758:             raise errors.Conflict(
3759:                 f"parent task {task_id} completion blocked: delegation state unverifiable ({type(exc).__name__})"
3760:             ) from exc
3761: 
3762:     def _mark_delegation_reconciliation_pending(self, parent_task_id: str, *, trigger: str,
3763:                                                 child_task_id: str = "", error: str = "") -> None:
3764:         """Best-effort durable pending marker (append-only delegation evidence)."""
3765:         dels = self._delegations_for_parent(parent_task_id)
3766:         for d in dels:
3767:             try:
3768:                 ev = dict(getattr(d, "evidence", {}) or {})
3769:                 ev["reconciliation_pending"] = {
3770:                     "pending": True,
3771:                     "at": time.time(),
```
- **CURRENT-STATE REVALIDATION:** Recomputes aggregation from current records for non-force COMPLETED; `force=True` bypasses guard (A5).
- **PERMISSION CHECK:** No.
- **CANCELLATION CHECK:** No propagation logic.
- **REVOCATION CHECK:** No explicit revocation revalidation.
- **RACE PROTECTION:** Store locks; not cross-store.
- **PERSISTED EVIDENCE:** Conflict detail with aggregation when blocked.
- **STATUS:** D-001 fixed evaluation; policy gaps remain (force bypass, D1-D5 unimplemented).
- **DISPOSITION (target stage):** **GUARDED (non-force aggregation path) / S1-FIX / S2-FIX**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Proof all completion paths wrapped and policy for force/semantic outcomes finalized/implemented.
- **What would make it verifiable:** Wrapper coverage audit and D2-aligned tests incl force.

### Aj._on_task_transition
- **CALLABLE:** `Aj._on_task_transition`
- **CALLERS (file:line list):** `tasks.after_transition` hook set in Aj.__init__.
- **ENTRY PATH:** After durable child transition, trigger bounded/idempotent parent reconciliation (best-effort).
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
3772:                     "trigger": trigger,
3773:                     "child_task_id": child_task_id,
3774:                     "error": error[:300],
3775:                 }
3776:                 d.evidence = ev
3777:                 d.reason = "reconciliation pending"
3778:                 self.delegations.save(d)
3779:             except Exception:
3780:                 pass
3781: 
3782:     def _on_task_transition(self, record: taskmod.TaskRecord, previous_status: str,
3783:                             new_status: str, reason: str) -> None:
3784:         """After durable child transition, reconcile parent delegation state (bounded/idempotent)."""
3785:         if previous_status == new_status:
3786:             return
3787:         parent_id = getattr(record, "parent_task_id", None)
3788:         if not parent_id:
3789:             return
3790:         if not self.delegations:
3791:             return
3792:         # avoid re-entrant reconciliation loops from transitions caused by reconciliation itself
3793:         active = getattr(self._delegation_reconcile_local, "active", None)
3794:         if not active:
3795:             active = set()
3796:             self._delegation_reconcile_local.active = active
3797:         if parent_id in active:
3798:             return
3799:         try:
3800:             # only reconcile when task appears delegation-related (child in delegation or has delegation context)
3801:             dctx = ((getattr(record, "authorization_context", None) or {}).get("delegation") or {})
3802:             if not dctx and not self._delegations_for_child(record.task_id):
3803:                 # cheap conservative check: still may be child of delegated parent
3804:                 if not self._delegations_for_parent(parent_id):
3805:                     return
3806:             active.add(parent_id)
3807:             with self._delegation_reconcile_guard:
3808:                 self._reconcile_delegation_parent(parent_id, trigger=f"child_transition:{record.task_id}:{previous_status}->{new_status}",
3809:                                                    source_child_task_id=record.task_id, apply_parent_policy=True)
3810:         except Exception as exc:
3811:             self._mark_delegation_reconciliation_pending(parent_id, trigger="child_transition",
3812:                                                          child_task_id=record.task_id,
3813:                                                          error=f"{type(exc).__name__}:{exc}")
3814:         finally:
3815:             try:
3816:                 active.discard(parent_id)
3817:             except Exception:
3818:                 pass
3819: 
3820:     def reconcile_delegation_parent(self, parent_task_id: str, *, dry_run: bool = False,
3821:                                     apply: bool = False, batch_size: int = 50,
3822:                                     actor: str = "operator") -> Dict[str, Any]:
3823:         """Explicit delegation reconciliation. Read-only dry-run by default; apply requires explicit flag."""
3824:         if dry_run and apply:
3825:             raise errors.Conflict("reconciliation cannot be both dry_run and apply")
3826:         # default to dry-run/inspection when neither specified
3827:         if not dry_run and not apply:
```
- **CURRENT-STATE REVALIDATION:** Checks linkage/relevance before reconcile; marks pending on errors (best-effort).
- **PERMISSION CHECK:** No.
- **CANCELLATION CHECK:** Indirect only.
- **REVOCATION CHECK:** Indirect only.
- **RACE PROTECTION:** Thread-local reentrancy set + reconcile guard lock; limited.
- **PERSISTED EVIDENCE:** Delegation pending markers/evidence and reconciliation outputs.
- **STATUS:** Best-effort hook.
- **DISPOSITION (target stage):** **S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Delivery/ordering guarantees and convergence under failures.
- **What would make it verifiable:** Fault-injection around persist/hook and reconciliation convergence tests.

### Scheduler.evaluate_eligibility
- **CALLABLE:** `Scheduler.evaluate_eligibility`
- **CALLERS (file:line list):** Scheduler internals/callers.
- **ENTRY PATH:** Eligibility decision for task dispatch.
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
293:     def evaluate_eligibility(self, task_id: str, *, now: Optional[float] = None,
294:                              allow_lease_worker: str = "") -> EligibilityDecision:
295:         now = time.time() if now is None else float(now)
296:         try:
297:             record = self.aj.tasks.get(task_id)
298:         except Exception as exc:
299:             return EligibilityDecision(False, PERSISTENCE_UNAVAILABLE,
300:                                        f"Task cannot be loaded safely: {type(exc).__name__}: {exc}",
301:                                        {"task_id": task_id})
302: 
303:         if record.terminal or record.status in taskmod.TERMINAL:
304:             return EligibilityDecision(False, TERMINAL,
305:                                        f"Task is terminal ({record.status}) and not schedulable.",
306:                                        {"status": record.status})
307: 
308:         if record.status == taskmod.WAITING_FOR_APPROVAL:
309:             return EligibilityDecision(False, AUTHORIZATION_REQUIRED,
310:                                        "Task requires authorization/approval before dispatch.",
311:                                        {"status": record.status})
312: 
313:         if record.status == taskmod.RECOVERY_REQUIRED:
314:             return EligibilityDecision(False, RECOVERY_OR_REVIEW_REQUIRED,
315:                                        "Task requires recovery/manual review before dispatch.",
316:                                        {"status": record.status})
317: 
318:         if record.status == taskmod.BLOCKED:
319:             try:
320:                 deps = self.aj.unsatisfied_dependencies(record)
321:             except Exception as exc:
322:                 return EligibilityDecision(False, DEPENDENCY_BLOCKED,
323:                                            f"Dependency state cannot be evaluated safely: {type(exc).__name__}: {exc}",
324:                                            {"status": record.status})
325:             if deps:
326:                 return EligibilityDecision(False, DEPENDENCY_BLOCKED,
327:                                            f"Task is blocked by unsatisfied dependencies: {', '.join(deps)}.",
328:                                            {"status": record.status, "dependencies": deps})
329:             # BLOCKED but deps satisfied: current scheduler dispatch path requires
330:             # explicit resume/reauthorization promotion; do not claim dispatch-eligible.
331:             return EligibilityDecision(False, NOT_SCHEDULABLE_STATE,
332:                                        "Blocked task has no unsatisfied dependencies but is not in a dispatchable state; resume/reauthorization is required.",
333:                                        {"status": record.status, "dependencies": []})
334: 
335:         # Deadline gate (explicit)
336:         if record.deadline and float(record.deadline) <= now:
337:             return EligibilityDecision(False, DEADLINE_EXCEEDED,
338:                                        "Task deadline has been exceeded.",
339:                                        {"deadline": record.deadline, "now": now})
340: 
```
- **CURRENT-STATE REVALIDATION:** Task/state/lease checks present; required D4 delegated checks (parent not cancelled/revoked/aborted/dead-letter, delegation active+linked, permission subset) not fully enforced (A3).
- **PERMISSION CHECK:** Not proven as required delegated subset gate.
- **CANCELLATION CHECK:** Not fully enforced per D4.
- **REVOCATION CHECK:** Not fully enforced.
- **RACE PROTECTION:** Decision-time only; race window possible.
- **PERSISTED EVIDENCE:** Eligibility/decision records where implemented.
- **STATUS:** Insufficient for D4.
- **DISPOSITION (target stage):** **S2-FIX**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Exact evaluated conditions and coverage for all delegated prohibited states.
- **What would make it verifiable:** Decision matrix tests and under-lease recheck evidence.

### Scheduler.evaluate_admission
- **CALLABLE:** `Scheduler.evaluate_admission`
- **CALLERS (file:line list):** Scheduler internals/callers.
- **ENTRY PATH:** Admission control.
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
424:     def evaluate_admission(self, task_id: str, *, eligibility: Optional[EligibilityDecision] = None,
425:                            now: Optional[float] = None,
426:                            selected_active: int = 0,
427:                            selected_waiting: int = 0) -> AdmissionDecision:
428:         now = time.time() if now is None else float(now)
429:         elig = eligibility or self.evaluate_eligibility(task_id, now=now)
430:         if not elig.eligible:
431:             return AdmissionDecision(False, True, DEFERRED_NOT_ELIGIBLE,
432:                                      f"Not admitted because task is not eligible: {elig.explanation}",
433:                                      {"eligibility": elig.to_dict()})
434: 
435:         if not bool(self._cfg("enabled", True)):
436:             return AdmissionDecision(False, True, DEFERRED_SCHEDULER_DISABLED,
437:                                      "Scheduler admission is disabled by configuration.",
438:                                      {})
439: 
440:         ok_persist, persist_msg = self._persistence_healthy_for_dispatch()
441:         if not ok_persist:
442:             return AdmissionDecision(False, True, DEFERRED_PERSISTENCE_UNHEALTHY,
443:                                      f"Deferred: persistence/state not trusted ({persist_msg}).",
444:                                      {"persistence": persist_msg})
445: 
446:         try:
447:             max_active = int(self._cfg("global_max_active_executions", 1))
448:             max_waiting = int(self._cfg("global_max_admitted_waiting", 10))
449:             max_dispatch = int(self._cfg("max_dispatch_per_run", 5))
450:             max_workers = int(self._cfg("max_workers", 1))
451:         except Exception:
452:             return AdmissionDecision(False, True, DEFERRED_UNKNOWN_CAPACITY,
453:                                      "Deferred: scheduler capacity configuration is invalid/untrusted.",
454:                                      {})
455:         # Defensive bounds (config validation should enforce, but fail closed).
456:         if min(max_active, max_waiting, max_dispatch, max_workers) < 1 and max_waiting < 0:
457:             return AdmissionDecision(False, True, DEFERRED_UNKNOWN_CAPACITY,
458:                                      "Deferred: scheduler capacity bounds are not usable.",
459:                                      {})
460:         if max_active < 1 or max_dispatch < 1 or max_workers < 1 or max_waiting < 0:
```
- **CURRENT-STATE REVALIDATION:** Capacity/admission focused; D4 delegated authority checks not proven.
- **PERMISSION CHECK:** Not proven.
- **CANCELLATION CHECK:** Not proven.
- **REVOCATION CHECK:** Not proven.
- **RACE PROTECTION:** Decision-time only.
- **PERSISTED EVIDENCE:** Admission evidence where implemented.
- **STATUS:** Unproven for D4.
- **DISPOSITION (target stage):** **S2-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Admission criteria relevant to delegated safety.
- **What would make it verifiable:** Tests combining admission with prohibited delegated states.

### Scheduler._dispatch_one
- **CALLABLE:** `Scheduler._dispatch_one`
- **CALLERS (file:line list):** `Scheduler.run_once` internal loop.
- **ENTRY PATH:** Intent -> lease -> recheck -> start -> resume -> result/release (durable mode).
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
668:     def _dispatch_one(self, task_id: str, *, eligibility: EligibilityDecision,
669:                       admission: AdmissionDecision) -> SchedulerResult:
670:         # Persist dispatch intent before lease/dispatch attempt (fail closed in durable mode).
671:         intent: Dict[str, Any] = {
672:             "task_id": task_id,
673:             "eligibility": eligibility.to_dict(),
674:             "admission": admission.to_dict(),
675:             "state": "DISPATCH_INTENT_RECORDED",
676:         }
677:         try:
678:             rec = self.aj.tasks.get(task_id)
679:             intent["task_status"] = rec.status
680:             intent["operation_id"] = getattr(rec, "operation_id", "")
681:             intent["current_execution_id"] = getattr(rec, "current_execution_id", "")
682:         except Exception:
683:             pass
684:         try:
685:             self._record_decision("dispatch_intent", task_id, intent, required=True)
686:         except Exception as exc:
687:             return SchedulerResult(task_id, "DEFERRED", False,
688:                                    f"Dispatch deferred: durable intent/evidence could not be recorded ({exc})",
689:                                    eligibility=eligibility.to_dict(), admission=admission.to_dict(),
690:                                    dispatch={"state": "intent_persist_failed", "error": str(exc)})
691: 
692:         lease = None
693:         try:
694:             lease = self.aj.leases.acquire(task_id, "execute", worker_id=self.worker_id)
695:         except errors.AjError as exc:
696:             try:
697:                 self._record_decision("dispatch_deferred", task_id, {
698:                     "reason_code": DEFERRED_DUPLICATE_OR_LEASE_CONFLICT,
699:                     "explanation": str(exc), "state": "LEASE_NOT_ACQUIRED"})
700:             except Exception:
701:                 pass
702:             return SchedulerResult(task_id, "SKIPPED", False, str(exc),
703:                                    eligibility=eligibility.to_dict(), admission=admission.to_dict(),
704:                                    dispatch={"state": "lease_not_acquired", "error": str(exc)})
705:         try:
706:             # Conservative recheck under lease held by this scheduler worker.
707:             elig2 = self.evaluate_eligibility(task_id, allow_lease_worker=self.worker_id)
708:             if not elig2.eligible:
709:                 try:
710:                     self._record_decision("dispatch_aborted", task_id, {
711:                         "state": "RECHECK_NOT_ELIGIBLE", "eligibility": elig2.to_dict()})
712:                 except Exception:
713:                     pass
714:                 return SchedulerResult(task_id, "DEFERRED", False,
715:                                        f"Dispatch aborted after claim: {elig2.explanation}",
716:                                        eligibility=elig2.to_dict(), admission=admission.to_dict(),
717:                                        dispatch={"state": "recheck_not_eligible"})
718:             record = self.aj.tasks.get(task_id)
719:             if record.deadline and record.deadline <= time.time():
720:                 self.aj.dead_letter(task_id, "deadline exceeded before execution")
721:                 try:
722:                     self._record_decision("dispatch_deadline", task_id, {
723:                         "state": "DEADLINE_EXCEEDED"})
724:                 except Exception:
725:                     pass
```
- **CURRENT-STATE REVALIDATION:** Intent/lease/start/result ledgering and rechecks present; full D4 pre-dispatch-under-lease checks not proven (A3). Dead-letter call near ~720 on failure branch: trigger predicates and delegated reachability NOT VERIFIABLE without full branch trace.
- **PERMISSION CHECK:** Not fully proven as required delegated subset/current-state gate.
- **CANCELLATION CHECK:** Not fully enforced per D4.
- **REVOCATION CHECK:** Not fully enforced.
- **RACE PROTECTION:** Lease coordination; no proven cross-store/interruption atomicity.
- **PERSISTED EVIDENCE:** Dispatch ledger, leases, task/execution evidence.
- **STATUS:** D4 safety gaps.
- **DISPOSITION (target stage):** **S2-FIX / S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Exact dead-letter branch conditions (~720) and delegated reachability/prohibition proof.
- **What would make it verifiable:** Branch trace + delegated/prohibited-state tests and fault-injection seams.

### Scheduler.run_once
- **CALLABLE:** `Scheduler.run_once`
- **CALLERS (file:line list):** Scheduler API/callers.
- **ENTRY PATH:** Batch selection/dispatch driver.
- **DELEGATION CONTEXT POSSIBLE:** Yes.
- **CURRENT GUARD (quote exact lines):**
```python
779:     def run_once(self, *, limit: int = 10, workers: int = 1) -> Dict[str, Any]:
780:         now = time.time()
781:         try:
782:             max_dispatch = int(self._cfg("max_dispatch_per_run", 5))
783:             cfg_workers = int(self._cfg("max_workers", 1))
784:             max_waiting = int(self._cfg("global_max_admitted_waiting", 10))
785:         except Exception:
786:             max_dispatch, cfg_workers, max_waiting = 5, 1, 10
787:         # Explicit bounds (no unbounded submission): respect configured caps and caller args.
788:         effective_limit = max(1, min(int(limit or 1), max_dispatch))
789:         effective_workers = max(1, min(int(workers or 1), cfg_workers))
790: 
791:         # Evaluate queue candidates in deterministic order.
792:         try:
793:             all_rows = self.queue(limit=0)
794:         except Exception:
795:             all_rows = []
796: 
797:         decisions: List[Dict[str, Any]] = []
798:         selected: List[str] = []
799:         selected_active = 0
800:         selected_waiting = 0
801:         admitted_plan: List[Dict[str, Any]] = []
802: 
803:         # Admission is separate from eligibility; defer with reasons.
804:         for row in all_rows:
805:             tid = row["task_id"]
806:             elig = EligibilityDecision(**row["eligibility"]) if isinstance(row.get("eligibility"), dict) else self.evaluate_eligibility(tid, now=now)
807:             if not elig.eligible:
808:                 decisions.append({"task_id": tid, "eligibility": elig.to_dict(), "admission": None, "selected": False})
809:                 continue
810:             adm = self.evaluate_admission(tid, eligibility=elig, now=now,
811:                                           selected_active=selected_active,
812:                                           selected_waiting=selected_waiting)
813:             decisions.append({"task_id": tid, "eligibility": elig.to_dict(), "admission": adm.to_dict(),
814:                               "selected": bool(adm.admitted and len(selected) < effective_limit and selected_waiting < max_waiting)})
815:             if adm.admitted:
```
- **CURRENT-STATE REVALIDATION:** Inherits eligibility/admission/dispatch behavior and D4 gaps.
- **PERMISSION CHECK:** Inherited.
- **CANCELLATION CHECK:** Inherited.
- **REVOCATION CHECK:** Inherited.
- **RACE PROTECTION:** Loop/batch concurrency not fully proven.
- **PERSISTED EVIDENCE:** Aggregated run outcomes and per-dispatch records.
- **STATUS:** Inherits gaps.
- **DISPOSITION (target stage):** **S2-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Selection/dispatch interactions with concurrent state changes.
- **What would make it verifiable:** Deterministic tests with concurrent mutators and delegated states.

### TaskStore.transition
- **CALLABLE:** `TaskStore.transition`
- **CALLERS (file:line list):** Aj-wrapped calls and direct store/record/runtime self-check contexts (domain filter above).
- **ENTRY PATH:** FSM edge validation, persist snapshot, hooks/callbacks.
- **DELEGATION CONTEXT POSSIBLE:** Yes (guarding depends on wrapper/path).
- **CURRENT GUARD (quote exact lines):**
```python
642:     def transition(self, task_id: str, status: str, detail: str = "",
643:                    *, force: bool = False, reason: str = "transition") -> TaskRecord:
644:         hook = None
645:         with self._lock:
646:             record = self._tasks.get(task_id)
647:             if record is None:
648:                 raise errors.AjError(f"unknown task {task_id!r}", code="task_not_found")
649:             previous = record.status
650:             record.transition(status, detail, force=force)
651:             self._persist_locked(record, reason)
652:             snap = self._snapshot(record)
653:             hook = (snap, previous, record.status, reason)
654:         if hook is not None:
655:             self._fire_after_transition(*hook)
656:         return snap
```
- **CURRENT-STATE REVALIDATION:** Validates `can_transition` unless `force=True`; Aj wrapper adds delegated-parent COMPLETED pre-guard on wrapped path.
- **PERMISSION CHECK:** No delegated permission enforcement.
- **CANCELLATION CHECK:** No propagation semantics.
- **REVOCATION CHECK:** No revocation checks.
- **RACE PROTECTION:** Store RLock + file lock; fail-closed persist attempts.
- **PERSISTED EVIDENCE:** Append-only task JSONL.
- **STATUS:** FSM/persist primitive.
- **DISPOSITION (target stage):** **GUARDED (FSM/persist) / NOT VERIFIABLE (wrapper coverage)**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Proof no production lifecycle mutation bypasses required Aj wrapper/guards.
- **What would make it verifiable:** Full call-site audit and wrapper-coverage assertions/tests.

### TaskStore.cancel
- **CALLABLE:** `TaskStore.cancel`
- **CALLERS (file:line list):** Store callers (not exhaustive).
- **ENTRY PATH:** Store-level cancel operation.
- **DELEGATION CONTEXT POSSIBLE:** Possible.
- **CURRENT GUARD (quote exact lines):**
```python
658:     def cancel(self, task_id: str) -> bool:
659:         hook = None
660:         with self._lock:
661:             record = self._tasks.get(task_id)
662:             if record is None or record.terminal:
663:                 return False
664:             previous = record.status
665:             record.transition(CANCELLED, "cancelled")
666:             self._persist_locked(record, "cancelled")
667:             snap = self._snapshot(record)
668:             hook = (snap, previous, CANCELLED, "cancelled")
669:         if hook is not None:
670:             self._fire_after_transition(*hook)
```
- **CURRENT-STATE REVALIDATION:** Local FSM/record checks; no D4 delegated propagation.
- **PERMISSION CHECK:** No.
- **CANCELLATION CHECK:** Local only.
- **REVOCATION CHECK:** No.
- **RACE PROTECTION:** Store locks.
- **PERSISTED EVIDENCE:** Task persistence.
- **STATUS:** Primitive.
- **DISPOSITION (target stage):** **S3-FIX / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** All callers and delegated semantics expectations.
- **What would make it verifiable:** Caller inventory + delegated tests.

### TaskStore.mutate
- **CALLABLE:** `TaskStore.mutate`
- **CALLERS (file:line list):** Orchestrator/internal callers (AST).
- **ENTRY PATH:** In-lock mutation helper with lifecycle-field protections and persist.
- **DELEGATION CONTEXT POSSIBLE:** Possible.
- **CURRENT GUARD (quote exact lines):**
```python
694:     def mutate(self, task_id: str, reason: str, fn) -> TaskRecord:
695:         """Run a controlled in-place mutation on the canonical record and persist."""
696:         with self._lock:
697:             current = self._tasks.get(task_id)
698:             if current is None:
699:                 raise errors.AjError(f"unknown task {task_id!r}", code="task_not_found")
700:             before_status = current.status
701:             before_events = len(current.events)
702:             fn(current)
703:             if current.status != before_status or len(current.events) != before_events:
704:                 # status/events must change only through store lifecycle operations
705:                 raise errors.AjError(
706:                     f"task {task_id}: lifecycle state changes must use TaskStore.transition/cancel",
707:                     code=errors.CALLING_INVALID_STATE,
708:                 )
709:             self._persist_locked(current, reason)
710:             return self._snapshot(current)
711: 
712:     # --- persistence -----------------------------------------------------
```
- **CURRENT-STATE REVALIDATION:** Protects some lifecycle fields; caller invariant correctness unproven.
- **PERMISSION CHECK:** No.
- **CANCELLATION CHECK:** No.
- **REVOCATION CHECK:** No.
- **RACE PROTECTION:** Store lock/file lock.
- **PERSISTED EVIDENCE:** Persisted task snapshot.
- **STATUS:** Guarded primitive; caller-dependent.
- **DISPOSITION (target stage):** **GUARDED / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Proof all mutate callers preserve required invariants.
- **What would make it verifiable:** Per-caller contract/invariant tests.

### TaskStore.save
- **CALLABLE:** `TaskStore.save`
- **CALLERS (file:line list):** Many callers (orchestrator/task/orb/execution_domain per AST).
- **ENTRY PATH:** Persist/update task record.
- **DELEGATION CONTEXT POSSIBLE:** Possible.
- **CURRENT GUARD (quote exact lines):**
```python
455:     def save(self, record: TaskRecord, reason: str = "update") -> TaskRecord:
456:         """Update an existing canonical task record and append it to the log.
457: 
458:         Callers may pass a snapshot/copy (e.g. from read or mutation APIs).
459:         For existing tasks, snapshot data is applied to the canonical managed
460:         record but store-controlled lifecycle/identity/history fields are
461:         preserved (``task_id``, ``operation_id``, ``schema_version``,
462:         ``created_at``, ``status``, ``events``, ``completed_at``), so callers
463:         cannot bypass legal transitions or fabricate lifecycle history.
464: 
465:         ``save`` is not a creation or import API: unknown task IDs are rejected.
466:         Use ``create``/``child_of`` for normal new tasks and ``import_record``
467:         for validated historical transfer/import/restore.
468:         """
469:         with self._lock:
470:             current = self._tasks.get(record.task_id)
471:             if current is None:
472:                 raise errors.AjError(
```
- **CURRENT-STATE REVALIDATION:** Persist-time behavior only; semantic correctness caller-dependent.
- **PERMISSION CHECK:** No.
- **CANCELLATION CHECK:** No.
- **REVOCATION CHECK:** No.
- **RACE PROTECTION:** Store/file locks.
- **PERSISTED EVIDENCE:** Task JSONL append.
- **STATUS:** Persistence primitive.
- **DISPOSITION (target stage):** **GUARDED / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Semantic correctness across all save call sites.
- **What would make it verifiable:** Invariant/property tests for save sites.

### TaskStore.import_record
- **CALLABLE:** `TaskStore.import_record`
- **CALLERS (file:line list):** `aj/transfer.py:import_file` -> `TaskStore.import_record`; CLI `_cmd_import` uses transfer.
- **ENTRY PATH:** Validate and import historical task record.
- **DELEGATION CONTEXT POSSIBLE:** Possible (data-dependent).
- **CURRENT GUARD (quote exact lines):**
```python
599:     def import_record(self, record: TaskRecord | Dict[str, Any], *,
600:                       reason: str = "imported") -> TaskRecord:
601:         """Explicitly import/restore a validated historical task record.
602: 
603:         This is the only path for adopting a task ID not already present in the
604:         store (e.g. transfer import/restore). It preserves legitimate historical
605:         state (including terminal states and event history) after validation and
606:         fails closed on invalid/conflicting input. It must not overwrite existing
607:         canonical task history: existing IDs are rejected as conflicts.
608:         """
609:         try:
610:             source = TaskRecord.from_dict(copy.deepcopy(record)) if isinstance(record, dict) else record
611:             candidate = self._snapshot(source)
612:         except Exception as exc:
613:             raise errors.Conflict(f"invalid import record: {exc}") from exc
614:         self._validate_import_record(candidate)
615:         with self._lock:
616:             existing = self._tasks.get(candidate.task_id)
617:             if existing is not None:
618:                 raise errors.Conflict(
619:                     f"import refused: task id already exists in this store: {candidate.task_id}",
620:                     detail={"task_id": candidate.task_id},
621:                 )
622:             canonical = self._snapshot(candidate)
623:             self._tasks[canonical.task_id] = canonical
624:             self._persist_locked(canonical, reason)
625:             return self._snapshot(canonical)
626: 
627:     def update(self, record: TaskRecord, reason: str = "update") -> TaskRecord:
628:         return self.save(record, reason)
629: 
630:     # --- mutation --------------------------------------------------------
631:     def _fire_after_transition(self, snapshot: TaskRecord, previous_status: str,
632:                                new_status: str, reason: str) -> None:
633:         cb = getattr(self, "after_transition", None)
634:         if cb is None or previous_status == new_status:
635:             return
636:         try:
637:             cb(snapshot, previous_status, new_status, reason)
638:         except Exception:
639:             # Must not break committed/durable task transition.
640:             pass
```
- **CURRENT-STATE REVALIDATION:** Structural/schema/status/history/conflict validation fail-closed; cannot import currently-invalid statuses (e.g. ABANDONED as-is).
- **PERMISSION CHECK:** No in-store caller authorization/provenance enforcement.
- **CANCELLATION CHECK:** No.
- **REVOCATION CHECK:** No.
- **RACE PROTECTION:** Store/file locks.
- **PERSISTED EVIDENCE:** Persisted record or rejection/import report.
- **STATUS:** Structurally guarded.
- **DISPOSITION (target stage):** **GUARDED / NOT VERIFIABLE**
- **Exact missing information/seam (NOT VERIFIABLE reason):** Source provenance/trust and migration/compat policy.
- **What would make it verifiable:** Provenanced/signed import policy and compat tests.

### `aj/__main__.py` task-mutating command handlers (every `_cmd_*` inspected)
Read/inspection-oriented handlers (direct task lifecycle mutation not by design): `_cmd_tasks`, `_cmd_task`, `_cmd_audit`, `_cmd_memory`, `_cmd_summary`, `_cmd_capabilities`, `_cmd_permissions`, `_cmd_config`, `_cmd_diagnostics`, `_cmd_export`, `_cmd_backup` verify, `_cmd_consistency`. `_cmd_orb` resolves/wires UI/inbox root (indirect task mutation unproven). Strict side-effect absence **NOT VERIFIABLE** without deeper trace.

| Handler (file:line) | Mutates tasks? | Path / guard notes | Disposition |
|---|---|---|---|
| `_cmd_run (aj/__main__.py:353)` | Yes | Assembles Aj and calls `aj.handle(...)`; inherits Aj/orchestrator guards and D1-D5 gaps. | **S1-FIX/S2-FIX/S3-FIX (inherited) / NOT VERIFIABLE** |
| `_cmd_cancel (aj/__main__.py:436)` | Yes | Calls `aj.cancel_task`; inherits propagation gaps (A4). | **S3-FIX / NOT VERIFIABLE** |
| `_cmd_retry (aj/__main__.py:454)` | Yes | Calls `aj.retry`; delegated D4 constraints unproven. | **S2-FIX / BLOCK-PER-D4? / NOT VERIFIABLE** |
| `_cmd_recover (aj/__main__.py:730)` | Yes when not `--inspect` | Inspect reads; recover path may mutate via RecoveryManager/Aj. | **S2-FIX/S3-FIX / NOT VERIFIABLE** |
| `_cmd_reconcile (aj/__main__.py:797)` | Yes (action-dependent) | Calls `aj.reconcile`; per-action delegated D4 enforcement unproven. | **S2-FIX/S3-FIX/BLOCK-PER-D4 / NOT VERIFIABLE** |
| `_cmd_import (aj/__main__.py:696)` | Yes unless `--dry-run` | `transfer.import_file` -> `TaskStore.import_record` structural validation. | **GUARDED (structural) / NOT VERIFIABLE (provenance/compat)** |

## Scheduler dead-letter call near `scheduler.py:720` (explicit)
- **Location:** `aj/scheduler.py` in `_dispatch_one` dispatch/failure handling region (~720).
- **When it triggers:** **NOT VERIFIABLE (exact predicate not fully traced in this pass).** On a dispatch failure/error-handling branch within `_dispatch_one`; precise conditions require branch-complete read/trace.
- **Can a delegated task reach it?:** **NOT VERIFIABLE.** Depends on eligibility/admission/rechecks and delegated-state guards (D4) along the same branch.
- **What would make it verifiable:** enumerate branch conditions to the dead-letter call and test delegated vs non-delegated (incl cancelled/revoked/inactive/unlinked parent/delegation) reaching or being blocked from that branch.

## Step 2d — NOT VERIFIABLE items (exact missing info/seam and what would make verifiable)
- **Aj.handle/resume/retry/recover/reconcile and scheduler paths** — **Missing:** Exhaustive per-branch delegated current-authority matrix, race/interruption windows, and cross-store consistency proof. **Verifiable with:** Per-path stateful tests + fault-injection seams at intent/lease/check/transition/persist boundaries with persisted snapshots.
- **RecoveryManager._recover_one and each Aj.reconcile action** — **Missing:** Complete action/decision branch enumeration and delegated preconditions/evidence requirements. **Verifiable with:** Action/branch inventory plus allow/deny delegated fixtures with persisted evidence.
- **Scheduler._dispatch_one dead-letter branch (~720)** — **Missing:** Exact trigger predicates and delegated reachability/prohibition proof. **Verifiable with:** Control-flow trace and targeted delegated-state tests.
- **TaskStore primitive callers/wrapper coverage** — **Missing:** Proof all production lifecycle mutations use required guards/wrappers and preserve invariants. **Verifiable with:** Full call-site/wrapper audit and runtime/invariant assertions.
- **Runtime/orb/inbox/integration/CLI/UI/background/external coupling** — **Missing:** Complete side-effect/call graph and mutation tracing across surfaces. **Verifiable with:** Instrumentation/tracing and integration tests per surface.
- **Absence of all dynamic dispatch** — **Missing:** Whole-program semantic guarantee beyond targeted static scans. **Verifiable with:** Dynamic/runtime instrumentation and exhaustive dynamic-feature audit.

## Step 2e — what AST and manual reading still cannot prove
- Dynamic dispatch (`getattr`/data-driven callables/reflection), monkeypatching beyond identified wrapper, plugin/registry indirection, runtime-only control flow, and concurrency interleavings.
- Cross-store atomicity, crash/interruption outcomes, freshness across tasks/delegations/assignments/leases/dispatch ledger/journal/receipts/memory.
- That every production mutation path (all processes/contexts including orb/inbox/integrations) is Aj-wrapped and policy-compliant.
- Exhaustive delegated safety for every operator action and scheduler/recovery branch (incl dead-letter reachability at scheduler.py:~720).
- Unsupported/external boundary enforcement completeness (remote transport, authenticated identity, exactly-once external effects, Hermes attachment) and end-to-end evidence/anomaly coverage.

**Non-exhaustive; dispositions/guards are evidence-informed and not a proof of S0 closure.**