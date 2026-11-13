# 01 — AJ Control Plane

**Status:** implemented and tested · **Scope:** pre-Hermes foundation

## 1. Position in the ecosystem

AJ is the parent identity and the only layer that decides authority. It is not a chat
front-end, not a tool implementation, and not a replacement for either sub-agent.

```
user
  │
  ▼
AJ ── route ── capability lookup ── permission decision ── task record ── audit
  │
  ├── JARVIS   general / major work     (separate repo, own history)
  ├── HELIX    calling / communications (separate repo, own history)
  └── HERMES   execution runtime        (NOT ATTACHED)
```

## 2. Modules

| Concern | Module | Enforced? |
|---|---|---|
| Routing | `aj.orchestrator.Router` | yes — deterministic rules + explicit capability |
| Permission | `aj.permissions.Authorizer` | yes — one decision point per invocation |
| Approval | `aj.permissions.ApprovalGate` | yes — single-use, payload-bound, 300 s |
| Task lifecycle | `aj.task.TaskStore` | yes — illegal transitions raise |
| Audit | `aj.audit.AuditLog` | yes — every handle writes events |
| Capability truth | `aj.capability.CapabilityRegistry` | yes — execution checks availability |
| Agent boundary | `aj.agents.AgentRegistry` | yes — probes, never assumes |
| Execution boundary | `aj.execution.ExecutionPort` | yes — raises when unattached |
| Skills | `aj.execution.SkillRegistry` | yes — withheld until approved + tested |
| Providers | `aj.providers.Gateway` | yes — no transport means no call |
| Memory | `aj.memory.MemoryStore` | yes — no raw-event deletion API |
| Calling | `aj.calling.CallingService` | yes — state machine + approval |

## 3. One request, end to end

1. `Aj.handle(goal)` creates a task in `RECEIVED` and writes `task_received`.
2. The router picks an owner: explicit capability → its `owner_agent`; calling
   vocabulary → HELIX; otherwise JARVIS. The rule that fired is recorded.
3. `UNDERSTANDING → PLANNED`. If the capability is unknown, forbidden, unavailable or
   has unknown verification, the task ends in `FAILED`/`ABORTED` with a specific code.
4. The authorizer returns `allow`, `confirm` or `deny`. `confirm` parks the task in
   `WAITING_FOR_APPROVAL` and returns `requires_user_decision=True`.
5. `AUTHORIZED → EXECUTING`: HERMES capabilities go through the execution port;
   everything else goes through the owning agent's adapter.
6. `VERIFYING → COMPLETED` only when the agent reports `completed`; anything else ends
   `FAILED` with the agent's own errors preserved.
7. `Aj.retry()` is the only way out of `FAILED`: `RECOVERING → RETRYING → EXECUTING`,
   bounded by `max_attempts`, otherwise `ESCALATED`.

## 4. Why the permission model has two layers

JARVIS already enforces its own tiers for direct tool calls (`core/policy.py`). AJ's
authorizer governs *ecosystem* actions — delegation, calling, execution — where JARVIS's
in-process gate cannot see the request. Two layers, two scopes, one vocabulary: AJ's
`level_from_tier()` translates JARVIS tiers rather than redefining them.

This is deliberate. Importing JARVIS's gate into AJ would make the control plane depend
on a sub-agent's internals; duplicating the tier list would let the two drift.

## 5. What AJ deliberately does not own

- **Identity prompts.** `JARVIS/core/voice.py` remains the voice and persona contract.
- **Tool implementations.** AJ never imports `actions/`.
- **Sub-agent repositories.** No file in JARVIS or HELIX was modified to build this.
- **Skills.** AJ registers metadata; Hermes will execute them. There is no skill
  interpreter here and no fake one.

## 6. Verified behaviour

`tests/` (65 tests) exercises routing, every policy outcome, approval replay and
payload-swap rejection, illegal task transitions, retry escalation, audit redaction and
file permissions, provider fallback and rate-limit cooldown, memory citation integrity,
call-state legality, ambiguity refusal, and the unattached execution port.

What is **not** verified: any live agent endpoint (neither sub-agent exposes an AJ task
endpoint yet), any real provider request, and any real phone call. See
`07_KNOWN_LIMITATIONS.md`.
