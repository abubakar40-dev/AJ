# 12 — Final Decision and Next Phase

## Decision: **CONDITIONAL GO**

A future narrowly scoped `hermes.gateway.ensure` capability is **potentially feasible** within AJ’s control-plane model **if and only if** the bounded conditions below are satisfied in a separately scoped, evidence-backed phase. Unconditional GO is **not** issued because native Hermes idempotency/concurrency guarantees, universal read-back/success verification, safe recovery under all ambiguous lifecycle cases, live resource/start behavior on this 8 GB host, and durable evidence persistence on the current NTFS-backed environment are **not sufficiently demonstrated**.

## Conditions required before any production implementation proposal
1. **State-gated enforcement (doc 02):** implement explicit observed-state classification and fail-closed state→action matrix; never start on non-ready by default except explicitly authorized `absent/stopped` start scope; unknown/contradictory/readback-unavailable => no mutation, `unknown/requires_manual_review`.
2. **Idempotency/concurrency closure (doc 03):** obtain defensible evidence for target supervisor/profile modes (source + Hermes tests and/or separately authorized controlled non-production experiments) covering concurrent ensures and absent->start races. Document native guarantees/limits. AJ must enforce per-target serialization/leases/dedupe and **must not claim idempotency or exactly-once**.
3. **Read-back/verification contract (doc 04):** implement authoritative post-condition verification (validated control/endpoint readiness, not exit code/service-active alone), verdict handling for all relevant states, and mandatory `unknown/requires_manual_review` recording when unverifiable.
4. **Timeout/failure/ambiguity policy (doc 05):** codify no-rollback-on-local-timeout/kill, no automatic retry after ambiguity, conservative defaults, and operator-recovery pathways; distinguish CLI vs gateway vs runtime-cancel vs rollback.
5. **Security/permissions (doc 06):** fixed executable+argv, no shell, controlled env, provenance checks, bounded I/O+timeout, redaction, default-disabled explicit feature/capability flags, split permissions (`observe`/`attach`/`start`/`replace`), `local_trust` non-authenticated, TOCTOU documented.
6. **Resource/backpressure (doc 07):** enforce serialized mutating lifecycle ops (provisional: 1 in-flight per profile/global), admission checks, no duplicate gateways for multi-task load, measured tuning on 8 GB host before broad enablement.
7. **Deterministic tests (doc 08):** extend isolated AJ tests to full mapping/contract coverage; add safe integration evidence in isolated non-production environment if lifecycle effects permitted (separately authorized). Keep distinction from native Hermes proof explicit.
8. **Storage reliability (doc 09):** place durable lifecycle evidence on reliable POSIX storage with proven persistence/recovery behavior, or document/accept residual risk with controls; handle persistence uncertainty as first-class.

## Missing evidence that would require separately authorized controlled experiments (later phase)
- Concurrent `hermes gateway ensure` behavior across relevant states/supervisors/profiles in a safe, isolated, non-production Hermes profile/environment with explicit authorization for lifecycle effects and cleanup.
- Observation of duplicate-process/service outcomes, discovery-start races, timeout/partial-start/orphan recovery behavior, and actual resource footprint.
- Any experiment design must: avoid production/user-impacting profiles, prohibit broad enablement, capture read-back/log/process evidence, and preserve rollback/cleanup plan (noting rollback of side effects may be limited).

## Recommended next phase
**Phase 4B.7 (proposed, separately scoped): Evidence closure and implementation-prep for `hermes.gateway.ensure`** — complete conditions above (including any authorized controlled experiments and storage reliability evidence), then produce a concrete implementation proposal/PR plan. **No production implementation in this recommendation.** If evidence cannot be closed safely, retain read-only `hermes.status.read` only.

## Explicit non-authorization
- **PRODUCTION IMPLEMENTATION AUTHORIZED:** NO
- **HERMES GATEWAY LIFECYCLE ACTION PERFORMED:** NO
- **FEATURE FLAGS CHANGED:** NO
- **AJ↔HERMES STATUS:** NOT ATTACHED
