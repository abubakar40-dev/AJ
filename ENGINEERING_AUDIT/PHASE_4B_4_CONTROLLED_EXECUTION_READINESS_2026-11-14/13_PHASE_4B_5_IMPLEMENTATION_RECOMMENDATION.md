# 13 — Phase 4B.5 Implementation Recommendation

## Decision: **CONDITIONAL GO** (narrow, single-capability, design-gated) — **NO implementation in 4B.4**

### Specific capability (only if conditions satisfied)
**`hermes.gateway.ensure`** — proposed as a **single, fixed-argv, no-user-input, local-only** mutating control capability (`hermes gateway ensure`) under a new/extended versioned contract/profile (not implicit reuse of v0 assumptions).

**Why this candidate (evidence-based):** among inspected Hermes CLI operations, it has the smallest plausible blast radius compared to global pause/resume disruption, persistent cron/webhook mutation, or external communication (`send`), and can align with the fixed-command/no-shell boundary. However, exact runtime semantics, idempotency, observability, and post-timeout state certainty are not fully evidenced from current CLI/help output alone.

### Prerequisites/conditions before implementation (must all be met)
1. **Hermes semantics verified (read-only verification steps only unless separately approved):** confirm `gateway ensure` is fixed/non-interactive, produces no hidden prompts/side channels, and document actual state effects and exit/output meaning; identify any safe read-back verification (e.g. `gateway status`) mapping without semantic overclaim.
2. **Contract & isolation design:** introduce per-capability operation spec/contract (v1 or additive) with side-effect class, truthful external ID/result fields (nullable), local-vs-external idempotency semantics, cancellation/ambiguity handling, confirmation/authorization binding, and evidence provenance; keep `shell=False`, fixed argv, deny-by-default, default-disabled.
3. **Authorization/confirmation policy:** classify as mutating (likely `SENSITIVE_OPERATION` or narrowly bounded reversible/local mutation only if rollback is evidenced); require explicit scope-bound confirmation if policy demands; preserve `local_trust` non-authenticated.
4. **Failure/recovery rules implemented-by-design:** no auto-retry on timeout/ambiguous outcomes; `unknown/requires_manual_review` on possible-effect cases; distinguish local process termination from runtime state change.
5. **Evidence & tests:** deterministic tests for allowlist/immutability/config-fail-closed/authz/timeout-redaction-honest outcomes plus controlled isolated integration evidence (if safe) before enablement.
6. **Storage/environment reliability:** ensure AJ evidence/state paths for mutating operations are on reliable local storage in the target environment (address ntfs3/WAL intermittency risk per doc 11); require passing persistence/recovery/idempotency evidence tests in that environment.

### Explicit NO-GO / excluded recommendations
- **NO-GO:** “enable Hermes execution generally”, arbitrary commands/shell, user-controlled argv, `send`/messaging, browser/desktop automation, MCP/skill/agent execution, cron/webhook/kanban mutating management, JARVIS/HELIX integration, persistent enablement, or any capability without op-specific evidence/contract/threat review.
- **NO-GO for now:** `hermes.pause`/`resume` and cron mutations as first capability due to higher blast radius, argument/state/ambiguity concerns, and weaker fit to “smallest next side effect”.

### If conditions cannot be satisfied with evidence
**NO-GO** for mutating implementation; remain at read-only `hermes.status.read` and continue reliability/contract-readiness work on separate tracks.
