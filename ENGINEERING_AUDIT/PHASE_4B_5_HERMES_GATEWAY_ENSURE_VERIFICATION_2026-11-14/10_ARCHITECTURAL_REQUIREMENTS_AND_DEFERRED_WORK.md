# 10 — Architectural Requirements and Deferred Work

## Preserved future requirements (not implemented in 4B.5)
1. AJ must support **multiple concurrent tasks** (not a serial one-task-at-a-time queue).
2. AJ must coordinate **multiple sub-agents/executions**.
3. Every task must have independent **task, operation, attempt, and correlation identities**.
4. Each execution must have independent **lifecycle, timeout, failure, and recovery handling**.
5. Scheduler must support **prioritization, dependencies, resource limits, and backpressure**.
6. AJ must detect **stuck, orphaned, and ambiguous executions**.
7. Cancellation semantics must distinguish **local process termination** from **actual runtime cancellation**.
8. **Evidence and task state** must remain traceable.
9. Architecture must support **graceful shutdown and recovery**.
10. Resource policy must account for the current **8 GB RAM** machine.

## Deferred work (explicitly out of scope now)
- Implementing `hermes.gateway.ensure` or any new Hermes capability/command integration.
- Changing AJ/Hermes source, configs, flags, services, schemas, or dependencies.
- Concurrency/sub-agent orchestration/scheduling implementation.
- Gateway lifecycle experiments (`ensure/start/restart/stop/enable/install`), stress/duplication tests on live environment.
- Filesystem/mount/fstab/repair/swap changes; auto-mount or boot-time AJ auto-start.
- SQLite/WAL remediation, storage migration, or persistence redesign (record limitations only).

## Design implications for future gateway lifecycle capability
- Must fit AJ’s future concurrent task model: per-task/operation/attempt identity, isolated timeouts/evidence, no global blocking assumptions.
- Must treat ensure as potentially mutating/ambiguous: resource-aware admission/backpressure, no unsafe parallel retries, explicit orphan/ambiguous detection and manual-review paths.
- Must preserve AJ↔JARVIS↔Hermes boundaries and non-authenticated `local_trust` semantics.
