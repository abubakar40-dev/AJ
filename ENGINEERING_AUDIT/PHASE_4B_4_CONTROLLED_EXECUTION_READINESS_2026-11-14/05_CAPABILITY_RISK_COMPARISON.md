# 05 — Capability Risk Comparison

Scoring (1 = lower risk/better control, 5 = higher risk/worse), based on available evidence; **UNKNOWN external semantics increase uncertainty**.

| Criterion | `hermes.gateway.ensure` (fixed, proposed) | `hermes.pause`/`resume` | `hermes.cron.*` mutations (general) |
|---|---:|---:|---:|
| Side-effect severity | 3 (local runtime state) | 4 (global dispatch/turn halt) | 5 (persistent scheduled/external potential) |
| Reversibility | 3 (stateful, not trivially rolled back) | 3 (paired toggle but operational impact/state ambiguity) | 2–5 (varies; creates/runs hard to undo) |
| Authentication requirement gap | 4 (`local_trust` only) | 4 | 5 |
| Secret exposure | 1–2 (no argv secrets if fixed) | 3 (pause reason possible) | 4 |
| External-system reach | 1 (local) | 2 (affects gateways/automation behavior) | 5 (downstream/external possible) |
| Idempotency | 3 (intent idempotent, native guarantee unknown) | 3 | 5 |
| Cancellation | 3 (process kill ≠ state rollback) | 2 (not long-running remote op) | 4 |
| Evidence quality / observability | 3 (unstructured CLI, no native op ID known) | 3 | 4–5 |
| Failure ambiguity | 3 | 4 | 5 |
| Testability in isolation | 3 | 3 | 4 |
| Blast radius | 2 | 4 | 5 |
| **Overall risk profile** | **Lowest among considered mutating candidates (still meaningful)** | **Medium-high** | **High** |

## Preferred candidate (for future design consideration only)
**`hermes.gateway.ensure`** — *conditional candidate*, not approved.

**Why:** fixed/no-user-arg interface is plausible (aligns with current fixed-command boundary), local-only blast radius, no required external messaging/credentials, conceptually narrower than global pause or persistent cron mutation. **But** Hermes-native semantics, idempotency, state observability, and timeout-ambiguity handling are not yet sufficiently evidenced/contracted for safe implementation.

## Rejected / not suitable yet
- **`hermes.pause`/`resume`:** broad operational impact; `pause` help indicates optional `--reason` (variable argument) increasing injection/redaction/contract complexity unless strictly removed; requires strong state verification and clearer rollback/confirmation model.
- **`hermes.cron.*` (and similar webhook/kanban/send mutations):** variable arguments, persistent side effects, weak/unknown idempotency and cancellation, high blast radius and ambiguity, external/downstream reach possible — incompatible with “smallest first mutating capability”.
- **`hermes send`, messaging, browser/desktop, agent/skill/MCP execution:** explicitly out of scope and/or high external/irreversible risk.
