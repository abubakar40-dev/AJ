# 03 Callable Inventory (CORE, read-only)

## Sweep commands used (for re-run)

Executed from `AJ` root:
```bash
# Orchestrator/scheduler/delegation method discovery
grep -n "def " aj/orchestrator.py | grep -E "handle|_execute|resume|retry|recover|cancel|dead_letter|requeue|abandon|reconcile|delegate|_prepare_delegated|_reconcile_delegation|_delegated_permission|_before_task|_on_task|run_once"
grep -n "def " aj/scheduler.py
grep -n "def \|@dataclass\|class " aj/delegation.py

# Callers/usages
grep -rn '\.dead_letter\|dead_letter(' aj tests
grep -rn '\.requeue\|requeue(' aj tests
grep -rn '\.abandon\|abandon(' aj tests
grep -rn '\.delegate\|delegate(' aj tests
grep -rn '_prepare_delegated_child_for_scheduling\|_reconcile_delegation_parent\|reconcile_delegation_parent' aj tests
grep -rn 'run_once\|_dispatch_one\|evaluate_eligibility\|evaluate_admission' aj tests
grep -rn '\.resume(' aj tests
grep -rn '\.retry(' aj tests
grep -rn '\.recover(' aj tests
grep -rn '\.cancel(' aj tests
grep -rn 'ABANDONED\|abandon\|abandoned' aj tests config docs
grep -rn '\.status\s*=' aj
grep -rn 'force=True' aj tests
grep -rn 'requeue' aj/inbox_cli.py aj/inbox.py
grep -rn 'cancel\|retry\|recover\|dead_letter\|requeue\|abandon\|reconcile' aj/inbox_cli.py aj/consistency.py aj/invariants.py

# CLI handlers
grep -n "_cmd_" aj/__main__.py
```

**Exhaustiveness:** **NOT PROVEN EXHAUSTIVE.** Sweep covered primary `aj/` and `tests/` call sites for target verbs/methods and enumerated CLI handlers, but did not fully close call graphs across all wrappers, UI/orb surfaces, runtime integrations, external entry points, or every indirect invocation path. Unknown/untraced paths must be treated as **NOT VERIFIABLE / UNSAFE for claims** until proven.

---

## Required/core callables

### CALLABLE: `aj/orchestrator.py:247` `Aj.handle`
- **CALLERS:** (grep: `Aj.handle`/`.handle(` in `aj`/tests not exhaustively enumerated here; known API/runtime entry) `aj/__main__.py:392` (`_cmd_run` -> `aj.handle(...)` for internal capability execution), tests across suites invoke `aj.handle(...)` broadly (e.g. permission/authz/orchestrator/phase tests). **UNVERIFIED exhaustive list.**
- **ENTRY PATH:** CLI (`run` for internal caps, via `assemble`), API/internal runtime, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (delegated child tasks/context may reach execution/authz boundaries; delegation metadata in task/authz context possible).
- **CURRENT GUARD:** routing, capability lookup/blocker/policy/authorizer checks in handle flow; `_execute` applies delegated guard when applicable (`aj/orchestrator.py:1294+`, guard at `3835+`). Mandatory audit/error handling present in observed sections.
- **CURRENT-STATE REVALIDATION:** partial/indirect for delegation (execute-boundary guard revalidates parent/delegation linkage/status and snapshots in covered cases); not proven universal/dynamic across all handle variants.
- **PERMISSION CHECK:** yes (authorizer/capability policy/permission model paths).
- **CANCELLATION CHECK:** partial (task state/lease/execute boundaries; not proven delegation-parent-aware at all pre-dispatch points).
- **REVOCATION CHECK:** partial (snapshot/record checks in covered delegated execute boundary; not full current-source revocation proof).
- **RACE PROTECTION:** leases/locks/store locking in components (e.g. `self.leases.hold` used in some ops; handle flow uses lease/release patterns), but **unknown** for all races/variants.
- **PERSISTED EVIDENCE:** task store transitions/events, audit/journal/memory/receipts/attempts/executions as applicable.
- **STATUS:** **GUARDED BUT NOT PROVEN** (delegation-safety and exhaustive path coverage unverified).

### CALLABLE: `aj/orchestrator.py:477` `Aj.retry` / `aj/orchestrator.py:481` `Aj._retry_locked`
- **CALLERS:** `aj/__main__.py:457` (`_cmd_retry`), `aj/runtime.py:429`, many tests (`tests/test_phase5a4_execution_domain.py:110`, `tests/test_dead_letter.py`, `tests/test_f2_permission_enforcement.py`, `tests/test_orchestrator.py`, `tests/test_phase3.py`, `tests/test_step_f_calling_dispatcher.py:454`, `tests/test_crash_safety.py`, etc.).
- **ENTRY PATH:** CLI, internal/API, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (retrying delegated/child tasks possible if they reach FAILED state).
- **CURRENT GUARD:** `retry` acquires `leases.hold(task_id,"retry")`; `_retry_locked` requires FAILED, enforces attempt budget/max_attempts, checks capability registered + `retry_safe`, refuses with audit/memory when unsafe, escalates when exhausted; delegates to `_execute` for permitted retry path.
- **CURRENT-STATE REVALIDATION:** task state/budget/capability checks; delegated authorization revalidated only if/when `_execute` + delegated guard applies (partial, not independently proven for all contexts).
- **PERMISSION CHECK:** capability/policy via execute/authz paths (indirect); explicit retry precondition on retry_safe.
- **CANCELLATION CHECK:** partial/unknown (not explicitly enumerated in retry preamble beyond execute boundaries).
- **REVOCATION CHECK:** partial via delegated execute guard in covered cases; not proven.
- **RACE PROTECTION:** operation lease (`retry`) serializes conflicting mutations for task.
- **PERSISTED EVIDENCE:** task transitions/saves, attempts/events, audit (`retry_refused` etc.), memory, receipts/journal/execution artifacts on execution.
- **STATUS:** **GUARDED BUT NOT PROVEN** for delegated revocation/cancellation/race completeness.

### CALLABLE: `aj/orchestrator.py:607` `Aj.cancel_task` / `aj/orchestrator.py:611` `Aj._cancel_locked` / `aj/orchestrator.py:663` `Aj.cancel`
- **CALLERS:** `aj/__main__.py:439` (`_cmd_cancel` -> `cancel_task`), `aj/orchestrator.py:663` wrapper `cancel()` returns bool, tests (`tests/test_orchestrator.py:169`, `tests/test_phase3.py:137`). (Note: `TaskStore.cancel` also exists and is used in some tests/paths; different callable.)
- **ENTRY PATH:** CLI, internal/API, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (any cancellable task incl. delegated parent/child if applicable).
- **CURRENT GUARD:** `cancel_task` holds `leases.hold(task_id,"cancel")`; refuses if terminal (audits `cancel_refused`), if EXECUTING sets `CANCEL_REQUESTED` (honest no forced interruption) and requires user decision, else transitions to `CANCELLED`; audits/journals/memory as shown.
- **CURRENT-STATE REVALIDATION:** current task status checked under lock/lease.
- **PERMISSION CHECK:** no explicit privileged permission model shown beyond operator context/authorization label; **partial/none specific**.
- **CANCELLATION CHECK:** implements cancellation state transitions (cooperative semantics) but does **not** orchestrate delegated child cancellation/propagation.
- **REVOCATION CHECK:** not applicable as authz revocation mechanism; no delegation revocation propagation.
- **RACE PROTECTION:** task operation lease (`cancel`).
- **PERSISTED EVIDENCE:** task transition/save/events, audit, journal, memory.
- **STATUS:** **GUARDED BUT NOT PROVEN** for delegation-wide cancellation safety (INV-04 gaps).

### CALLABLE: `aj/orchestrator.py:666` `Aj.recover` / `aj/orchestrator.py:988` `Aj._recover_locked` (plus `aj/recovery.py:77` `RecoveryManager` / `:92` `_recover_one` / `:62` `classify`)
- **CALLERS:** `aj/__main__.py:736` (`aj.recovery_inspection`), `aj/__main__.py:775` (`RecoveryManager(...).recover(...)`), `aj/recovery.py:92` calls `self.aj.recover(task_id, approval="")`; many tests (`tests/test_crash_safety.py`, `tests/test_phase3c_recovery_integrity.py`, `tests/test_phase3_lifecycle_reliability.py`, `tests/test_phase2.py`, `tests/test_f2_permission_enforcement.py:220`, `tests/test_step_f_calling_dispatcher.py:315`, etc.).
- **ENTRY PATH:** CLI (`recover` command), internal API, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (recovering delegated/executing/child tasks possible depending state).
- **CURRENT GUARD:** `Aj.recover` acquires `leases.hold(task_id,"recover")` and fails closed/blocked on lease conflicts; `_recover_locked` convergent for terminal, assesses via evidence-based `_assess_recovery`, blocks/manual-review/replay-safe decisions per assessment (fail-closed on ambiguity/malformed/conflict), never resurrect terminal; `RecoveryManager.scan` read-only classification, batch replays only assessed replay-safe via orchestrator.
- **CURRENT-STATE REVALIDATION:** evidence/state assessment (leases, receipts, journal, executions, attempts, etc.) as implemented; delegated-specific current authz/cancel/revocation revalidation **not proven exhaustive**.
- **PERMISSION CHECK:** approval parameter accepted; replay/execute paths subject to normal authz where resumed; not fully enumerated.
- **CANCELLATION CHECK:** partial/assessment-dependent; resurrection prevention and delegation interactions **not fully proven**.
- **REVOCATION CHECK:** not explicitly comprehensive for delegated permission revocation.
- **RACE PROTECTION:** recovery lease; blocked on conflicting active ownership.
- **PERSISTED EVIDENCE:** recovery assessment stored in task metadata (`mutate`/save), audit (`recovery_blocked/converged/assessed` etc.), task transitions/outcomes, journal/receipt/execution evidence when actions taken.
- **STATUS:** **GUARDED BUT NOT PROVEN** for all delegated/cancellation/race/crash-boundary cases.

### CALLABLE: `aj/orchestrator.py:2036` `Aj.resume` / `aj/orchestrator.py:2042` `Aj._resume_locked`
- **CALLERS:** `aj/scheduler.py:740` (`Scheduler._dispatch_one` -> `self.aj.resume(task_id, leased=True)`), tests (`tests/test_f2_authorization_context.py`, `tests/test_f2_scheduler_resume.py`, etc.). **CLI:** no direct `resume` subcommand found in `aj/__main__.py` (UNVERIFIED if exposed elsewhere).
- **ENTRY PATH:** scheduler dispatch (leased), internal/API, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (authorized/delegated child tasks; scheduler dispatch path).
- **CURRENT GUARD:** if not leased acquires execute lease; `_resume_locked` resolves capability, enforces state-specific promotion/authorization (BLOCKED deps satisfied then reauth path, PLANNED reauth, stale-authorization handling `_handle_stale_authorization` at 2000+), computes/stores authorization context, applies `_delegated_permission_guard` before execute in delegated contexts (observed around `2236`), then `_execute`.
- **CURRENT-STATE REVALIDATION:** capability/policy/authz context/stale checks; delegated guard performs current-state parent/delegation linkage/status and snapshot envelope checks in covered path (partial, not fully dynamic/per-source).
- **PERMISSION CHECK:** yes (authorizer, capability blocker, delegated guard).
- **CANCELLATION CHECK:** partial (guard blocks cancelled/revoked/unverifiable parent authority in covered delegated path; scheduler pre-dispatch not delegation-aware).
- **REVOCATION CHECK:** partial (guard checks delegation/parent status and envelope snapshots; not exhaustive dynamic revocation proof).
- **RACE PROTECTION:** execute lease (held by scheduler/dispatch or acquired here), leases/dispatch intent evidence in scheduler.
- **PERSISTED EVIDENCE:** task transitions/saves/authz context, audit/journal, execution/attempt/receipt records via execute flow.
- **STATUS:** **GUARDED BUT NOT PROVEN** (delegated boundary and race completeness).

### CALLABLE: `aj/orchestrator.py:2244` `Aj.dead_letter`
- **CALLERS:** `aj/orchestrator.py:3269` (operator `Aj.reconcile` action `dead_letter`), `aj/scheduler.py:720` (deadline exceeded before execution in `_dispatch_one`), tests (`tests/test_dead_letter.py` many cases).
- **ENTRY PATH:** operator reconciliation (API/CLI path via `Aj.reconcile`), scheduler internal, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (any task id passed; no delegation filter observed).
- **CURRENT GUARD:** requires transition legality to `DEAD_LETTER` (`can_transition` check) unless already `DEAD_LETTER`; sets `requires_user_decision=True`; no delegation/parent/child/assignment safety checks observed.
- **CURRENT-STATE REVALIDATION:** task current status/transition legality only.
- **PERMISSION CHECK:** none specific (relies on caller; operator reconcile path has privileged authz/evidence controls around operation, but `dead_letter` method itself does not).
- **CANCELLATION CHECK:** no delegated cancellation/authority checks.
- **REVOCATION CHECK:** none.
- **RACE PROTECTION:** **none internal** (no lease/lock acquired inside method in inspected code); caller may hold different context (e.g. scheduler holds lease during dispatch flow around deadline branch; operator reconcile has its own controls).
- **PERSISTED EVIDENCE:** task transition/save, audit `task_dead_lettered`, journal `TASK_DEAD_LETTERED`, memory `task.dead_letter`.
- **STATUS:** **UNSAFE** for delegated contexts (can terminalize without delegation lifecycle/authority validation) / **GUARDED BUT NOT PROVEN** only by external callers.

### CALLABLE: `aj/orchestrator.py:3408` `Aj.requeue`
- **CALLERS:** tests (`tests/test_dead_letter.py` multiple, including repeated requeue cases), no non-test `aj/` callers found by grep except definition/pycache; `aj/inbox_cli.py` and `aj/inbox.py` "requeue" refer to **inbox capture stale-processing recovery** (different domain) — **not** `Aj.requeue`.
- **ENTRY PATH:** internal/API, tests (**no CLI handler found** in `aj/__main__.py`).
- **DELEGATION CONTEXT POSSIBLE:** yes if invoked on delegated task id.
- **CURRENT GUARD:** requires `status == DEAD_LETTER`; performs forced transition `DEAD_LETTER -> PLANNED` (`force=True`), clears `requires_user_decision`, appends attempt metadata, preserves identities/history; **no delegation/authority/cancellation checks**.
- **CURRENT-STATE REVALIDATION:** source state only.
- **PERMISSION CHECK:** none.
- **CANCELLATION CHECK:** none.
- **REVOCATION CHECK:** none.
- **RACE PROTECTION:** none internal.
- **PERSISTED EVIDENCE:** forced task transition/save, audit `task_requeued`, journal `TASK_REQUEUED`, memory `task.requeued`.
- **STATUS:** **UNSAFE** for delegated contexts (resurrection/unsafe reactivation risk) unless externally blocked.

### CALLABLE: `aj/orchestrator.py:3467` `Aj.abandon`
- **CALLERS:** `aj/orchestrator.py:3279` (operator `Aj.reconcile` action `abandon`), tests (`tests/test_dead_letter.py`, `tests/test_audit_reliability_security.py`). No direct CLI subcommand; exposed via `reconcile --action abandon`.
- **ENTRY PATH:** operator reconciliation (API/CLI via reconcile), tests.
- **DELEGATION CONTEXT POSSIBLE:** yes.
- **CURRENT GUARD:** idempotent error if already `"ABANDONED"`; forced transition to `"ABANDONED"` (`force=True`), records error/audit/journal/memory; **no delegation checks**. `"ABANDONED"` not modeled in `aj/task.py` `TRANSITIONS/TERMINAL` (model inconsistency).
- **CURRENT-STATE REVALIDATION:** current status equality only.
- **PERMISSION CHECK:** none in method (operator reconcile wrapper has authz controls).
- **CANCELLATION CHECK:** none delegation-specific.
- **REVOCATION CHECK:** none.
- **RACE PROTECTION:** none internal.
- **PERSISTED EVIDENCE:** forced task transition/save, task error/note, audit `task_abandoned`, journal `TASK_ABANDONED`, memory `task.abandoned`.
- **STATUS:** **UNSAFE** for delegated contexts and **model-inconsistent** (`ABANDONED` outside FSM).

### CALLABLE: `aj/orchestrator.py:2864` `Aj.reconcile` (operator reconciliation)
- **CALLERS:** `aj/__main__.py:800` (`_cmd_reconcile` -> `aj.reconcile(...)`), tests (`tests/test_audit_reliability_security.py` etc. via grep). Distinct from `reconcile_delegation_parent`.
- **ENTRY PATH:** CLI (`reconcile`), API/internal, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (any task id).
- **CURRENT GUARD:** input validation (action/reason), operation evidence intent/progress/outcome handling, idempotent duplicate detection for known operation IDs, privileged authorization/audit (`privileged_authorization`), lease/ownership safety for some actions, evidence/conflict checks (esp. `clear_recovery_required`), supported actions `abort|dead_letter|abandon|clear_recovery_required`; dispatches to `dead_letter`/`abandon` methods or direct transitions. **No delegation-aware guards observed.**
- **CURRENT-STATE REVALIDATION:** task state/inspection/evidence checks vary by action (partial, conservative in places).
- **PERMISSION CHECK:** yes (privileged operation authorizer for reconciliation action context).
- **CANCELLATION CHECK:** action/state dependent; not delegation-orchestration aware.
- **REVOCATION CHECK:** none delegation-specific.
- **RACE PROTECTION:** lease/ownership checks and operation-id idempotency logic in covered cases (best-effort).
- **PERSISTED EVIDENCE:** operation evidence store (intent/progress/outcome), audit records, task transitions/inspection outputs, delegated method side effects for dead_letter/abandon.
- **STATUS:** **GUARDED BUT NOT PROVEN** (generally stronger controls) but **UNSAFE/NOT PROVEN** for delegated-context semantics due to action targets lacking delegation guards.

### CALLABLE: `aj/orchestrator.py:4230` `Aj.delegate`
- **CALLERS:** many tests in 5A.6/5A.6R suites (`tests/test_phase5a6*`, `tests/test_phase5a6r*`), capability/dispatch metadata tests reference `aj.delegate` as non-executable capability (`tests/test_step_e_registry_dispatch.py`, `tests/test_step_f_calling_dispatcher.py`).
- **ENTRY PATH:** API/internal, tests. No direct CLI subcommand found.
- **DELEGATION CONTEXT POSSIBLE:** yes (creates delegation).
- **CURRENT GUARD:** config enable/bounds checks, store availability, request validation (`DelegationRequest.validate`), idempotency-key conflict detection, parent existence/state checks (rejects terminal/aborted/cancelled/dead_letter/failed as coded), max delegations/children, hierarchy/root validation, capability matching (`match_agent`, fail-closed), permission narrowing (`narrow_permissions`, fail-closed), child task creation/linkage/evidence, assignment/delegation persistence with partial-failure handling, preparation attempt and reconciliation trigger.
- **CURRENT-STATE REVALIDATION:** parent/task/store/request state at call time; not a general runtime revalidator for future mutations.
- **PERMISSION CHECK:** permission narrowing enforced at creation (recorded/evidenced).
- **CANCELLATION CHECK:** rejects delegation if parent in cancelled/terminal-invalid states at creation; later cancellation handling separate.
- **REVOCATION CHECK:** not applicable as post-hoc revocation mechanism.
- **RACE PROTECTION:** store/task locking/persistence semantics as implemented; **not fully proven** for concurrent create/race cases beyond covered tests.
- **PERSISTED EVIDENCE:** delegation/assignment/logical-agent/task records, child authz/delegation context snapshots, journal `DELEGATION_RECORDED` (best-effort), reconciliation evidence.
- **STATUS:** **GUARDED BUT NOT PROVEN** (controlled foundation, but downstream lifecycle/cancel/revocation/race completeness unverified).

### CALLABLE: `aj/orchestrator.py:3924` `Aj._prepare_delegated_child_for_scheduling`
- **CALLERS:** `aj/orchestrator.py:4052` (`_reconcile_delegation_parent` apply path), `aj/orchestrator.py:4392` (`delegate` after child creation), tests (`tests/test_phase5a6r4_gap_closure.py:125` direct call).
- **ENTRY PATH:** internal orchestration/reconciliation, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (delegated children).
- **CURRENT GUARD:** checks delegation context and parent existence/status; blocks/aborts if parent cancelled/cancel-requested/aborted/dead-letter or unverifiable; advances RECEIVED/UNDERSTANDING->PLANNED, handles terminal/already-authorized/waiting/blocked states, resolves capability/blocker, authorizes via `authorizer.authorize` and transitions to AUTHORIZED/WAITING_FOR_APPROVAL/ABORTED/FAILED accordingly; preserves delegation context snapshots. **No explicit delegation-record revocation/status/assignment/current narrowing revalidation observed.**
- **CURRENT-STATE REVALIDATION:** partial (parent task state/current capability/authorizer decision).
- **PERMISSION CHECK:** authorizer + recorded narrowing context preserved; not full dynamic revalidation.
- **CANCELLATION CHECK:** parent task state checked (covered cases).
- **REVOCATION CHECK:** partial/insufficient (does not recheck delegation record active/revoked state explicitly).
- **RACE PROTECTION:** relies on task store transitions/locking; **not proven** race-safe against concurrent revocation/cancel/transition.
- **PERSISTED EVIDENCE:** task transitions/saves, authz context, journal `TASK_AUTHORIZED` on authorization.
- **STATUS:** **GUARDED BUT NOT PROVEN** (known gaps per Doc 56/57).

### CALLABLE: `aj/orchestrator.py:3820` `Aj.reconcile_delegation_parent` / `aj/orchestrator.py:4030` `Aj._reconcile_delegation_parent`
- **CALLERS:** `Aj.reconcile_delegation_parent` public: `aj/orchestrator.py:3831`, many tests (`tests/test_phase5a6r2_parent_lifecycle.py`, `tests/test_phase5a6r3_scenario_certification.py`, `tests/test_phase5a6r4_gap_closure.py`). Internal `_reconcile_delegation_parent`: `3808` (post-transition hook), `4432` (after delegate), `3831` (public wrapper), tests (`tests/test_phase5a6r4_gap_closure.py:252`, `tests/test_phase5a6r_delegation_closure.py`). Also `reconcile_delegation_parent` name appears in monitoring/status helpers.
- **ENTRY PATH:** internal hooks, API/internal, tests. No direct CLI handler found.
- **DELEGATION CONTEXT POSSIBLE:** yes (delegation reconciliation).
- **CURRENT GUARD:** reconciliation guard lock (`_delegation_reconcile_guard`), bounded batch, dry-run/apply separation, aggregation from current task/delegation snapshots, apply may attempt child preparation and persists evidence/history/provenance/pending markers; dry-run non-mutating by intent. **Not a dispatch/authorization grant by itself**, but apply mutates tasks/delegation evidence.
- **CURRENT-STATE REVALIDATION:** reads current stores/records/snapshots at execution; idempotency via snapshot hash comparison.
- **PERMISSION CHECK:** none direct (may invoke preparation which uses authorizer).
- **CANCELLATION CHECK:** indirect via preparation/aggregation/guards; not a full cancellation orchestrator.
- **REVOCATION CHECK:** indirect/partial.
- **RACE PROTECTION:** in-process reconcile guard and re-entrancy tracking; **stale-writer/cross-process/cross-store safety not proven**.
- **PERSISTED EVIDENCE:** delegation record evidence/history/provenance/pending markers, child preparation side effects in apply mode.
- **STATUS:** **GUARDED BUT NOT PROVEN** (idempotent/bounded in covered cases; mutating apply and race/stale safety gaps).

### CALLABLE: `aj/scheduler.py:293` `Scheduler.evaluate_eligibility`
- **CALLERS:** scheduler internals (`429,534,615,707,806`), `tests/test_phase5a5_scheduler_admission.py` (many), `tests/test_phase5a6r_delegation_closure.py:109` indirect patterns.
- **ENTRY PATH:** internal scheduler/API, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes (tasks may be delegated children).
- **CURRENT GUARD:** checks loadability, terminal states, waiting/recovery/active/uncertain/blocked/dependency/deadline/capability/persistence/lease/execution states; conservative fail-closed on unknown/untrusted state; dispatchable focus = AUTHORIZED.
- **CURRENT-STATE REVALIDATION:** task/lease/execution/capability/persistence state at evaluation time.
- **PERMISSION CHECK:** capability blocker/policy availability (not full delegated permission narrowing).
- **CANCELLATION CHECK:** excludes active/cancel-requested/uncertain states in cases; **no explicit parent-delegation cancellation/authority check observed**.
- **REVOCATION CHECK:** none delegation-specific.
- **RACE PROTECTION:** read/decision-time checks only; races possible between evaluation and dispatch (dispatch rechecks under lease).
- **PERSISTED EVIDENCE:** none directly (decision objects/monitoring).
- **STATUS:** **GUARDED BUT NOT PROVEN** for delegated authority/cancellation awareness.

### CALLABLE: `aj/scheduler.py:424` `Scheduler.evaluate_admission`
- **CALLERS:** scheduler internals (`429,620,810`), tests (`tests/test_phase5a5_scheduler_admission.py`).
- **ENTRY PATH:** internal scheduler, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes.
- **CURRENT GUARD:** requires eligibility, scheduler enabled, persistence trusted, capacity/config bounds, active-count and lease conflict checks, backpressure/defer reasons.
- **CURRENT-STATE REVALIDATION:** capacity/lease/persistence/eligibility inputs.
- **PERMISSION CHECK:** indirect via eligibility/capability; none delegation-specific.
- **CANCELLATION CHECK:** indirect via eligibility/lease/active state; no explicit delegated parent checks.
- **REVOCATION CHECK:** none delegation-specific.
- **RACE PROTECTION:** conservative capacity accounting per run; not race-proof without lease/dispatch recheck.
- **PERSISTED EVIDENCE:** none directly.
- **STATUS:** **GUARDED BUT NOT PROVEN** for delegated contexts.

### CALLABLE: `aj/scheduler.py:668` `Scheduler._dispatch_one`
- **CALLERS:** `aj/scheduler.py:836,839` (`run_once`), not directly external.
- **ENTRY PATH:** internal scheduler.
- **DELEGATION CONTEXT POSSIBLE:** yes.
- **CURRENT GUARD:** records dispatch intent (durable mode fail-closed), acquires execute lease, rechecks eligibility under held lease worker, handles deadline -> `Aj.dead_letter`, records dispatch start/result evidence, calls `Aj.resume(task_id, leased=True)`, releases lease; defers/fails closed on evidence/lease/recheck issues.
- **CURRENT-STATE REVALIDATION:** re-eligibility under lease; task/deadline checks.
- **PERMISSION CHECK:** delegated to resume/execute/authz chain.
- **CANCELLATION CHECK:** limited (deadline path, eligibility excludes some states); no explicit parent-delegation authority check.
- **REVOCATION CHECK:** delegated downstream.
- **RACE PROTECTION:** execute lease claim + recheck + evidence sequencing.
- **PERSISTED EVIDENCE:** dispatch ledger records (intent/start/result/deferred/error) when available, plus downstream task/execution evidence.
- **STATUS:** **GUARDED BUT NOT PROVEN** (especially delegation-authority/cancel and deadline-dead-letter safety for delegated tasks).

### CALLABLE: `aj/scheduler.py:779` `Scheduler.run_once`
- **CALLERS:** tests (`tests/test_phase5a5_scheduler_admission.py`, `tests/test_phase5a6r*`, `tests/test_f2_scheduler_resume.py:174` etc.). **CLI:** no direct scheduler subcommand found in `aj/__main__.py` (UNVERIFIED).
- **ENTRY PATH:** internal/API, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes.
- **CURRENT GUARD:** computes bounded limits, builds deterministic queue, evaluates eligibility/admission, applies backpressure/selection bounds, dispatches via bounded pool/serial calls to `_dispatch_one`.
- **CURRENT-STATE REVALIDATION:** per-candidate eligibility/admission and dispatch-time rechecks.
- **PERMISSION CHECK:** indirect.
- **CANCELLATION CHECK:** indirect.
- **REVOCATION CHECK:** none specific.
- **RACE PROTECTION:** bounded submission; per-task safety delegated to leases/dispatch logic.
- **PERSISTED EVIDENCE:** dispatch decisions/ledger via `_dispatch_one`, downstream effects.
- **STATUS:** **GUARDED BUT NOT PROVEN**.

### CALLABLE: `aj/orchestrator.py:2419` `Aj.recovery_inspection` (read-only inspection, mutating? no state mutation intended)
- **CALLERS:** `aj/__main__.py:736` (`_cmd_recover --inspect`), `aj/__main__.py:762` scan-inspect loop, used for reporting.
- **ENTRY PATH:** CLI, internal/API.
- **DELEGATION CONTEXT POSSIBLE:** yes (inspects task/delegation evidence views).
- **CURRENT GUARD:** read-only aggregation/inspection; fail-closed surfacing of missing/conflicting evidence where implemented.
- **CURRENT-STATE REVALIDATION:** reads current persisted state/evidence.
- **PERMISSION CHECK:** none shown.
- **CANCELLATION CHECK:** n/a (observational).
- **REVOCATION CHECK:** n/a.
- **RACE PROTECTION:** read-time consistency not guaranteed (observational).
- **PERSISTED EVIDENCE:** none written (intended read-only).
- **STATUS:** **GUARDED (read-only intent) BUT NOT PROVEN** for completeness/atomic view (reports uncertainty; monitor/inspection should not mutate).

### CALLABLE: `aj/orchestrator.py:4183` `Aj.delegation_status` / `aj/orchestrator.py:4197` `Aj.delegation_monitor` (observational)
- **CALLERS:** used by `Aj.delegate` return/status flows (`4230+` returns `delegation_status`), tests/utilities (not exhaustively listed). **CLI:** no direct handler found.
- **ENTRY PATH:** internal/API, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes.
- **CURRENT GUARD:** read-only aggregation/anomaly detection (`detect_delegation_anomalies`, `aggregate_parent_progress`) over current stores.
- **CURRENT-STATE REVALIDATION:** read-only view.
- **PERMISSION/CANCELLATION/REVOCATION CHECK:** n/a (observational).
- **RACE PROTECTION:** none (point-in-time best-effort).
- **PERSISTED EVIDENCE:** none intended.
- **STATUS:** **GUARDED (observational) BUT NOT PROVEN** for detector completeness.

### CALLABLE: `aj/orchestrator.py:3733` `Aj._before_task_transition` (lifecycle guard hook)
- **CALLERS:** invoked by monkey-patched `TaskStore.transition` wrapper installed in `Aj.__init__` (`235-241`).
- **ENTRY PATH:** internal (all transitions routed through patched store transition when wrapper active).
- **DELEGATION CONTEXT POSSIBLE:** yes.
- **CURRENT GUARD:** blocks non-forced parent `COMPLETED` when delegation aggregation unsafe/unverifiable/manual-review (fail-closed); no checks for other statuses.
- **CURRENT-STATE REVALIDATION:** computes aggregation from current task/delegation state.
- **PERMISSION CHECK:** n/a.
- **CANCELLATION CHECK:** indirect via aggregation/child states only for completion case.
- **REVOCATION CHECK:** n/a.
- **RACE PROTECTION:** depends on store/transition locking and caller context; **not proven**.
- **PERSISTED EVIDENCE:** none directly (raises on block; transition proceeds/fails elsewhere).
- **STATUS:** **GUARDED BUT NOT PROVEN** (scope limited to COMPLETED, bypass via `force=True`, wrapper-coverage assumptions).

### CALLABLE: `aj/orchestrator.py:3782` `Aj._on_task_transition` (post-transition hook)
- **CALLERS:** `TaskStore.after_transition` callback set in `Aj.__init__` (`236`), fired by `TaskStore.transition` (`aj/task.py:655`).
- **ENTRY PATH:** internal hook.
- **DELEGATION CONTEXT POSSIBLE:** yes.
- **CURRENT GUARD:** re-entrancy guard, triggers bounded delegation reconciliation for parent on relevant child transitions, records pending markers on failure (best-effort).
- **CURRENT-STATE REVALIDATION:** reconciliation reads current state.
- **PERMISSION/CANCELLATION/REVOCATION CHECK:** indirect via reconciliation/preparation behaviors.
- **RACE PROTECTION:** in-process guard/local tracking; incomplete.
- **PERSISTED EVIDENCE:** delegation reconciliation evidence/pending markers, potential child prep side effects.
- **STATUS:** **GUARDED BUT NOT PROVEN**.

### CALLABLE: `aj/recovery.py:77` `RecoveryManager.scan` / `:62` `classify` / `:94` `recover`
- **CALLERS:** `aj/__main__.py:758,775`, tests (many recovery/crash suites). Delegates actual recovery to `Aj.recover`.
- **ENTRY PATH:** CLI, API/internal, tests.
- **DELEGATION CONTEXT POSSIBLE:** yes.
- **CURRENT GUARD:** read-only scan/classify uses `Aj._assess_recovery` fail-closed; batch recover only `REPLAY_SAFE` findings via orchestrator; single-task recover always evidence-based in orchestrator.
- **CURRENT-STATE REVALIDATION:** assessment-time reads.
- **PERMISSION/CANCELLATION/REVOCATION CHECK:** inherited from `Aj.recover` path (limited).
- **RACE PROTECTION:** scan read-only; recover uses orchestrator lease.
- **PERSISTED EVIDENCE:** via `Aj.recover`.
- **STATUS:** **GUARDED BUT NOT PROVEN**.

### CALLABLE: `aj/task.py:642` `TaskStore.transition` (and related `:455 save`, `:694 mutate`, `:499 _validate_import_record`, `:400 reload`)
- **CALLERS:** ubiquitous via `self.tasks.transition(...)` in orchestrator/scheduler/tests/CLI flows.
- **ENTRY PATH:** internal core API.
- **DELEGATION CONTEXT POSSIBLE:** yes (task domain).
- **CURRENT GUARD:** `TaskRecord.transition` enforces legal edges unless `force` and terminal rules; store validates/normalizes on load/import, preserves lifecycle fields on save, restricts lifecycle mutation via `mutate`, fires hooks.
- **CURRENT-STATE REVALIDATION:** state/edge validation at call; reload/import validation against `TRANSITIONS/TERMINAL`.
- **PERMISSION/CANCELLATION/REVOCATION CHECK:** n/a (mechanism-level).
- **RACE PROTECTION:** store-internal locking/persistence discipline (`_lock`, file locking patterns as implemented) — **not fully analyzed here**.
- **PERSISTED EVIDENCE:** `tasks.jsonl` append/update semantics, events/history.
- **STATUS:** **GUARDED BUT NOT PROVEN** (and has known `ABANDONED`/force interaction inconsistencies with FSM model).

### CALLABLE: `aj/lease.py:111` `LeaseManager` (acquire/release/hold/heartbeat/get/list semantics; operation & execution leases)
- **CALLERS:** orchestrator/scheduler/task mutation flows (`leases.hold`, acquire/release), tests.
- **ENTRY PATH:** internal.
- **DELEGATION CONTEXT POSSIBLE:** indirect (serializes task operations/execution ownership).
- **CURRENT GUARD:** file-backed/in-process lease records with status/expiry/ownership semantics; distinguishes operation vs execution lease usage.
- **CURRENT-STATE REVALIDATION:** lease state/expiry checks.
- **PERMISSION/CANCELLATION/REVOCATION CHECK:** n/a.
- **RACE PROTECTION:** flock/atomic writes/thread/file coordination as implemented (partially inspected).
- **PERSISTED EVIDENCE:** lease store file(s).
- **STATUS:** **GUARDED BUT NOT PROVEN** for all contention/crash windows.

### CALLABLE: `aj/execution_domain.py` `ExecutionStore` / `ExecutionRecord` transitions (domain foundation)
- **CALLERS:** orchestrator execution lifecycle integration (`_ensure_execution`, transition updates), tests (`tests/test_phase5a4_execution_domain.py`).
- **ENTRY PATH:** internal.
- **DELEGATION CONTEXT POSSIBLE:** yes (executions linked to tasks/assignments/agents).
- **CURRENT GUARD:** state machine validation, append-only persistence fail-closed.
- **PERSISTED EVIDENCE:** `executions.jsonl`.
- **STATUS:** **GUARDED BUT NOT PROVEN** for cross-store atomicity/crash recovery claims.

### CALLABLE: `aj/authorization.py` `build_privileged_authorizer` / authorizers (`LocalTrustPrivilegedAuthorizer`, `UnavailablePrivilegedAuthorizer`, etc.)
- **CALLERS:** `aj/orchestrator.py` (privileged reconciliation authz), runtime assembly/config paths.
- **ENTRY PATH:** internal.
- **DELEGATION CONTEXT POSSIBLE:** yes (operator/privileged ops affecting tasks).
- **CURRENT GUARD:** explicit local-runtime trust model (not authenticated human identity), fail-closed defaults in unavailable modes; provenance/decision records.
- **STATUS:** **GUARDED BUT NOT PROVEN** as authenticated identity; **correctly non-authenticated by design** (`local_trust`).

### CALLABLE: `aj/memory.py` `MemoryStore.record/init` (evidence, not task mutation control)
- **CALLERS:** orchestrator/runtime/tests (memory events), `tests/test_phase3.py` concurrent writers.
- **ENTRY PATH:** internal/tests.
- **DELEGATION CONTEXT POSSIBLE:** indirect evidence only.
- **GUARD:** SQLite schema/init and record operations as implemented.
- **PERSISTED EVIDENCE:** SQLite `memory.sqlite3`.
- **STATUS:** **GUARDED BUT NOT PROVEN** under concurrent/fork/NTFS-sensitive conditions (**OPEN**).

---

## CLI command handlers (every handler in `aj/__main__.py`)

Command map source: `aj/__main__.py:933-954` (`_COMMANDS`).

| Handler (file:line) | CLI command | Mutates task/execution/delegation? | Delegation context possible | Key guards/evidence | Status |
|---|---|---|---|---|---|
| `_cmd_run` (353) | `run` | yes (creates/executes internal task/capability via `aj.handle`) | yes | assembles AJ, requires registered internal capability, executes `aj.handle`, closes memory | GUARDED BUT NOT PROVEN |
| `_cmd_tasks` (406) | `tasks` | no (read/query) | n/a | read-only listing, reports load errors | read-only |
| `_cmd_task` (423) | `task` | no (read) | n/a | read-only | read-only |
| `_cmd_cancel` (436) | `cancel` | yes (task lifecycle via `aj.cancel_task`) | yes | `Aj.cancel_task` lease/transition guards | GUARDED BUT NOT PROVEN (delegation propagation) |
| `_cmd_retry` (454) | `retry` | yes (retry flow) | yes | `Aj.retry` lease/budget/retry-safe/execute guards | GUARDED BUT NOT PROVEN |
| `_cmd_audit` (473) | `audit` | no (read) | n/a | read-only | read-only |
| `_cmd_memory` (483) | `memory` | no (read) | n/a | read-only | read-only |
| `_cmd_summary` (506) | `summary` | no (derived/read) | n/a | read-only/derived | read-only |
| `_cmd_capabilities` (565) | `capabilities` | no (inspect) | n/a | read-only | read-only |
| `_cmd_permissions` (619) | `permissions` | no (inspect) | n/a | read-only | read-only |
| `_cmd_config` (643) | `config` | no (inspect/validate) | n/a | read-only | read-only |
| `_cmd_diagnostics` (663) | `diagnostics` | no (inspect) | n/a | read-only | read-only |
| `_cmd_export` (686) | `export` | file export (data movement), not task FSM mutation | indirect data | transfer/export logic | SUPPORTED BUT NOT PROVEN (for safety scope) |
| `_cmd_import` (696) | `import` | can create/import persisted records | yes (data/content dependent) | import validation in transfer/store paths (not fully audited here) | NOT VERIFIABLE (exhaustive safety) |
| `_cmd_backup` (709) | `backup` | creates/verifies backup artifacts | indirect | transfer/verify logic | read/write artifacts, safety NOT VERIFIABLE |
| `_cmd_recover` (730) | `recover` | yes when not inspect-only; inspection read-only | yes | `--inspect` uses `recovery_inspection`/scan; else `RecoveryManager.recover` -> `Aj.recover` | GUARDED BUT NOT PROVEN |
| `_cmd_reconcile` (797) | `reconcile` | yes (operator reconciliation; can dead-letter/abandon/abort/clear_recovery_required) | yes | `Aj.reconcile` privileged authz/evidence/idempotency/lease checks; actions delegate to guarded/unguarded task mutators | GUARDED BUT NOT PROVEN / action-dependent UNSAFE for delegated semantics |
| `_cmd_orb` (822) | `orb` | launches UI/process; not direct task FSM mutation | possible indirect | environment/GTK checks and subprocess launch | NOT VERIFIABLE (side effects/UI) |
| `_cmd_consistency` (917) | `consistency` | no (read-only check intended) | n/a | `Aj.consistency_check` | read-only intent |
| `cmd_inbox` (imported, `aj/inbox_cli.py`) | `inbox` | inbox subsystem mutations (capture/process/retry/requeue-stale etc.), **not AJ task FSM mutation** by same APIs except separate domain logic | no (task delegation domain) unless coupled elsewhere (UNVERIFIED) | inbox store/worker logic; "retry"/"requeue-stale" are inbox-domain terms | OUT OF SCOPE for task/delegation mutators; NOT VERIFIABLE for cross-domain effects |

**CLI notes:** `reconcile` choices include `abort, dead_letter, abandon, clear_recovery_required` (`aj/__main__.py:312`). No CLI for `Aj.requeue`, `Aj.delegate`, `reconcile_delegation_parent`, or `Scheduler.run_once` found.

## Non-task-domain "retry/requeue" (distinguished)

- `aj/inbox_cli.py`: inbox `retry` subcommand retries failed capture via `retry_failed(...)`; `worker --requeue-stale-seconds` and `requeue_stale()` recover stale PROCESSING inbox items to queued. These are **inbox-store operations**, not `Aj.requeue`/task FSM transitions.

## Overall inventory status

- **Best-effort corrected for required targets:** yes.
- **Provably exhaustive for every callable/wrapper in repo:** **no** (explicitly NOT VERIFIABLE in this pass). All untraced paths remain unclassified-for-safety and must not be treated as safe.
