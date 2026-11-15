# 11 — Concurrent Orchestration Compatibility (Mandatory Future Requirement)

## Preserved requirement
AJ must eventually support **multiple simultaneous tasks** and **multiple concurrent sub-agents/executions** with scheduling, prioritization, dependencies, resource/backpressure, isolation, independent lifecycles/timeouts/cancellation semantics, stuck/orphan detection, recovery, persistent evidence, and graceful shutdown/restart recovery. **AJ must not become a serial one-task-at-a-time execution queue.**

## Compatibility constraints for `hermes.gateway.ensure` design

| Principle | Design implication |
|---|---|
| Gateway lifecycle is not per-task blind start | **Do not** start/ensure a new gateway for every task. Treat gateway as **shared runtime** (per profile/scope) whose lifecycle is managed/coordinated separately from task execution fan-out. |
| Shared runtime vs task execution isolation | Multiple tasks/sessions may share one ready gateway runtime; each task/execution keeps independent `task/operation/attempt/correlation` IDs, evidence, timeout/failure handling, and (where supported) cancellation semantics. |
| Per-resource coordination | Lifecycle mutations serialized per target runtime/profile with leases/locks/backpressure; observation/attach can be concurrent-safe reads subject to policy. |
| Independent operation evidence | Every ensure/observe/attach action is an auditable operation with its own identity and outcome, linkable to requesting task/scheduler context when applicable. |
| Scheduler coordination | Scheduler/admission control decides when lifecycle actions are permitted based on state, policy, and resource budgets; no unbounded parallel ensure. |
| Per-task cancellation semantics | Distinguish cancelling a task/execution/session from terminating local ensure CLI and from gateway/runtime shutdown. No false remote-cancellation claims. |
| Resource-aware admission control | 8 GB constraints require bounded concurrency, memory-aware admission, and graceful degradation (doc 07). |
| Orphan/stuck monitoring | Detect stuck `starting`, orphan processes, ambiguous post-timeout states, and reconcile via read-back/recovery workflows. |

## Future dedicated phase (recorded)
**AJ Concurrent Task & Sub-Agent Orchestration Architecture** — to define scheduler, task graph/dependencies/priorities, execution pools/sub-agent coordination, shared runtime lifecycle manager, cross-process leases, recovery/restart semantics, and observability. **Not implemented in 4B.6.**

## Non-goals in 4B.6
- No scheduler/orchestrator implementation, no concurrency runtime, no multi-agent execution engine, no gateway lifecycle implementation.
