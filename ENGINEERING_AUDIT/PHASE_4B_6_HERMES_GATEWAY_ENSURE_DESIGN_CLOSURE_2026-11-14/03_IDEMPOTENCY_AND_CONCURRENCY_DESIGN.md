# 03 — Idempotency and Concurrency Design (Criterion 2)

## Hermes source/test observations (evidence, non-exhaustive)

| Question | Findings (source observations) | Evidence pointers | Status |
|---|---|---|---|
| Native synchronization present? | Yes, multiple mechanisms: discovery-first loop, per-invocation `requested/replaced/retiring` flags, runtime ownership/lock files (`gateway.lock`, `ProfileOwnership`), control socket/identify ownership checks, service manager coordination, multiplex reservation/state, planned-stop/replace flow. `spawn_unmanaged_gateway` relies on gateway runtime exclusive ownership fence for racing starts. | `hermes_cli/gateway_runtime.py` (`ensure_gateway_runtime`, `requested`, `replaced`), `gateway_runtime_start.py`, `gateway/runtime_ownership.py` (flock/open/inode checks, non-unlinking held lock, stale-foreign handling), `gateway_runtime_discovery.py` (`_private_lock`, reservation checks), `gateway/control_socket.py`, `gateway/status.py` (pid/lock/state), `gateway_runtime_replace.py` | **Observed in code**; completeness across modes unproven |
| Process-local or cross-process? | **Both intended:** in-process loop flags are process-local; locks/sockets/PID/state/service/multiplex artifacts are cross-process coordination surfaces. | ownership/lock flock + inode identity; control socket single owner; service manager single unit state | **Observed**; atomicity/race freedom not formally proven |
| systemd/service supervision protection? | `discover_existing_gateway_service`/`start_existing_gateway_service` use existing supervisor state/commands (`running` no-op, request start once). systemd typically enforces single main service instance per unit, but semantics depend on unit/config and races. | `gateway_runtime_service.py` (source per 4B.5), runtime observations (user unit active/running) | **Partial**; not a general cross-supervisor guarantee |
| Discovery and start race window? | Yes: state can change between discovery, decision, and start/effect (TOCTOU). Loop re-observes, but absent->start transition is inherently racy across concurrent invocations/processes. | `ensure_gateway_runtime` branches on observed state then may start; external actors can mutate | **Risk present (inference from design)** |
| Two separate ensure invocations conflict? | Possible in edge/race cases (simultaneous absent observation, supervisor races, multiplex/profile transitions) despite mitigations. Hermes tests exist for some scenarios but not exhaustively re-run/validated here. | 4B.5 unknowns; ownership fence intended to arbitrate | **Unproven / cannot rule out** |
| Multiple profiles/runtime owners change guarantees? | Yes: multiplexing/served profiles, profile homes, default vs named profiles, and ownership/replace constraints (`_within_install`, `hermes_home` match, served-by-multiplexer targeting) affect behavior. | `gateway_runtime_multiplex.py`, `gateway_runtime_replace.py` (`_identify`, `_verified_owner`, refuse foreign install/wrong home), discovery control-home selection | **Complex; guarantees not generalized** |
| Lock files/sockets/PID/ownership metadata? | Yes: `gateway.lock` (flock/private), `gateway.pid`, `gateway.sock`/pointer/control socket, `gateway_state.json`, ownership/reservation metadata, planned-stop markers, service state. | `gateway/runtime_ownership.py`, `gateway/status.py`, `gateway/control_socket.py`, `gateway_runtime_discovery.py` | **Observed** |
| Existing ready owner reliably reused? | Discovery returns ready/attachable endpoint and loop can return/attach without starting when already ready/served (common case); depends on valid control identify and matching identity. | `discover_gateway_endpoint`, `attachable`, ready branches; runtime observed ready host | **Likely in normal cases; not universally proven** |
| Incompatible owner can be replaced? | Conditionally yes: only older-Hermes same-install verified owner (`runtime_protocol` older/missing) via `replace_incompatible_owner` (planned stop marker in owner home, SIGTERM/wait, guarded force kill), refusal for newer/foreign/unverified/unreachable/did-not-exit. Once per ensure call context (`replaced` set) to avoid loops. | `gateway_runtime_replace.py`, `_observe_replacing_stale` in `gateway_runtime.py` | **Observed**; side effects/mutation significant |
| Timeout leaves uncertain state? | Yes: deadline may return `starting/deadline` (or related) while service start/spawn/daemon transition continues; ensure process exit does not rollback. | `ensure_exit_code` (5 for deadline/starting/absent), `remaining`, runtime_exited handling, 4B.5/05 | **Observed/inferred risk** |

## Native Hermes idempotency/concurrency assessment
- **Native Hermes idempotency:** **NOT demonstrated as a formal guarantee.** Repeated calls may converge to ready in many cases, but not equivalent to safe/no-op under all races/states/side effects.
- **Concurrent invocation safety:** **UNPROVEN.** Absent->start races and multi-process timing remain open without controlled experiments.
- **AJ must not claim idempotency or exactly-once execution.**

## AJ-side concurrency policy design (future-compatible, NOT implemented)

| Concern | Proposed AJ design (future) | Notes |
|---|---|---|
| Per-resource execution locks | Serialize lifecycle-mutating actions per gateway target/profile/resource key (and coordinate with discovery state). | Local/cross-process lock primitive required if multiple AJ workers/processes; storage/location must be reliable (see doc 09). |
| Duplicate operation detection | Dedupe by normalized operation intent + target + active/ambiguous operation window; reject or coalesce reads, never coalesce ambiguous mutations unsafely. | Distinct from Hermes native behavior. |
| Cross-process coordination | Shared durable coordination record/lease for mutating lifecycle ops if multi-process AJ introduced. | Depends on future orchestration/storage design. |
| Independent operation identities | Every request gets unique `task_id` (if task-scoped), `operation_id`, `attempt_id`, `correlation_id`; gateway ensure must not be task-blind singleton side effect without evidence linkage. | Compatible with concurrent multi-task/sub-agent model. |
| Attempt tracking | Explicit attempt records for observe/wait/retry decisions; retries create new attempts, never hidden. | No auto-retry after ambiguity. |
| Stale lock/lease detection | Time-bounded leases with owner metadata/heartbeats or fencing; stale detection => `unknown/requires_manual_review`, not forced takeover. | Avoid split-brain. |
| Recovery from interrupted operations | On AJ restart/interruption, reconcile incomplete ops via read-back; if outcome ambiguous, mark `unknown/requires_manual_review` with evidence. | No rollback assumption. |

## Distinction: AJ duplicate prevention vs native Hermes idempotency
- **AJ-side duplicate prevention:** policy/locking/dedupe/identity/evidence in AJ to avoid issuing conflicting/unsafe requests. Can reduce but **cannot guarantee** Hermes-side single-effect if requests already executed or if Hermes lacks guarantees.
- **Native Hermes idempotency:** property of Hermes ensure/runtime to make repeated/concurrent invocations converge safely without harmful duplication. **Not proven; must not be assumed.**

## Missing evidence / required controlled experiment (separately authorized later, if needed)
- Controlled, isolated (non-production profile/service) concurrent `ensure` invocations across states (ready, starting, absent, retiring, incompatible) and target supervisor modes on supported platforms, with process/state/log inspection and cleanup authorization.
- Measurement of discovery-start race outcomes and any duplicate-process/service effects.
- Verification that no real user-facing integrations/platforms are impacted in test profile.
**No such experiment performed in 4B.6.**
