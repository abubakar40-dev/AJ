# 09 — Decision and Implementation Entry Criteria

## Recommendation: **CONDITIONAL GO**

`hermes gateway ensure` (v0.23.0, HEAD 2bd378ed1b8d, as inspected) is **feasible in form** as a narrowly scoped future capability candidate (`hermes.gateway.ensure`) under strict AJ controls: fixed argv/flags, no shell, bounded timeout/output, credential-free JSON verdict contract, and read-only-with-respect-to-AJ integration posture. However, it is a **lifecycle operation** (may start/reconcile/replace gateway runtime with real side effects and ambiguity), and essential guarantees (native idempotency, concurrent-invocation safety across all cases, fully reliable success verification, timeout/partial-start recovery semantics) are **not sufficiently demonstrated** for unconditional approval.

**Implementation remains not authorized in this phase.** A separate, scoped implementation proposal/phase is required only if all conditions below are satisfied.

## Conditions required before any implementation proposal may proceed
1. **State-gated scope defined and enforced:** specify allowed preconditions (e.g. discovery/read-only attach-to-ready cases only vs. permit start when absent) and explicitly classify/handle mutating outcomes (`starting`, service-start requested, detached spawn, replace). If start/replace paths are in scope, treat as mutating lifecycle capability with corresponding permissions/confirmations and risk acceptance.
2. **Idempotency/concurrency evidence:** obtain defensible evidence (source+targeted tests or controlled isolated runs approved separately) for concurrent `ensure` invocations and absent->start races in the target supervisor/profile modes; document native guarantees or absence thereof. AJ must not claim idempotency/exactly-once.
3. **Read-back and success criteria:** define authoritative post-condition verification (control `identify`/endpoint readiness, not mere exit code or service-active alone) and handling for `starting/deadline/runtime_exited/inaccessible/incompatible/conflict/draining` verdicts, including partial-start ambiguity.
4. **Timeout/recovery semantics:** specify that local timeout/cancellation of AJ subprocess does **not** cancel/rollback gateway side effects; define no-unsafe-auto-retry policy, ambiguity -> `unknown/requires_manual_review`, and operator recovery expectations.
5. **Security controls:** fixed argv `hermes gateway ensure --json --timeout <bounded>` (or equivalent resolved executable + fixed args), `shell=False`, controlled env allowlist, bounded stdout/stderr capture and redaction-aware logging, default-disabled feature/config gating, fail-closed validation, no `local_trust` elevation.
6. **Resource/8 GB policy:** prohibit unbounded parallel ensure calls, assess target profile memory/start impact, and ensure no duplicate-runtime scenarios under expected use.
7. **Deterministic test plan:** contract/exit-code parsing, timeout handling, verdict-to-AJ-state mapping (honest/unknown-preserving), no-shell/fixed-argv enforcement, failure/ambiguity paths, and isolated integration evidence in a safe non-production profile/environment if lifecycle effects are permitted.
8. **Storage/reliability note:** any AJ-side evidence persistence for lifecycle actions must account for known NTFS/tmp SQLite reliability concerns on this host (separate track; do not assume persistence reliability).

## Why not GO now
- Native idempotency and concurrent-invocation safety not fully demonstrated.
- Ensure can have material side effects (start detached daemon or service, replace incompatible owner in specific case) with ambiguous outcomes and non-trivial recovery.
- Successful convergence/read-back is state-dependent and not reducible to command success alone.
- 8 GB host and existing gateway/runtime complexity raise duplication/resource risk.

## Why not NO-GO
- Command exists with a structured, bounded, machine-readable interface and no-shell/fixed-argv feasibility; discovery-first/ownership/service mechanisms show deliberate safety engineering; read-only attach/ready outcomes appear plausible in common cases. With strict scoping and evidence, a controlled implementation proposal may be justified.
