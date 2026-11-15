# 04 — Idempotency and Concurrency Analysis

## Definitions applied
- **Native Hermes idempotency:** repeated `ensure` calls converge to “runtime ensured/ready” without harmful duplicate effects by Hermes’ own guarantees.
- **AJ-side duplicate prevention:** AJ request dedupe/conflict handling (separate concern; not implemented for this capability).
- **Process-level duplicate prevention:** single gateway owner enforced by locks/service/discovery.
- **Concurrent invocation safety:** two+ simultaneous `ensure` calls behave safely.
- **External side-effect duplication:** no duplicated externally visible/runtime side effects.

## Verified facts (source observations)
- **Discovery-first loop:** `ensure_gateway_runtime` repeatedly observes state (`discover_gateway_endpoint`, service/multiplexer/start-child status) before/while deciding. If owner becomes `ready` (or attachable restart-wait cases handled specially), it returns that verdict; it does not blindly spawn every call.
- **Single-start intent per invocation:** once an owner/start request is observed or issued, code sets `requested=True` and avoids launching another in the same loop (`if observed.state == "starting" and not retiring: requested = True`; `if observed.state == "absent" and not requested: ... start/service/start_unmanaged ... requested=True`). After its spawned child exits absent, it reports `inaccessible/runtime_exited` rather than launching a second one.
- **Ownership/coordination primitives:** profile/gateway runtime uses lock/state/control mechanisms (`gateway.lock`/`ProfileOwnership`, control socket/identify, service discovery, multiplex reservation/state logic) to arbitrate owners. `spawn_unmanaged_gateway` notes “The gateway runtime's own exclusive ownership fence arbitrates racing starts.” `gateway_runtime_replace` replaces only specific incompatible older same-install owner once (tracks `replaced` set per call context).
- **Service start:** `start_existing_gateway_service` no-ops if `service.running` else issues a single start request; supervisor decides actual behavior.
- **Already-running case:** if discovery returns ready/served endpoint, ensure returns it (no start path taken). Runtime observations show existing ready service-managed gateway on host.
- **Tests indicate intended convergence/wait behavior:** e.g. waits for real control owner, reports starting/deadline, handles draining/update-paused/retiring/replaced cases, non-mutating installed-service start assertions in specific fixture (see `tests/hermes_cli/test_gateway_runtime_ensure.py`).

## Inferences
- **Exit success on repeat is insufficient proof of idempotency.** A repeated call may return `ready` after attaching to existing owner (good), or `starting/deadline`/other transitional verdicts depending timing/state; “second exits 0” alone does not prove no side effects occurred during convergence.
- **Process-level duplicate prevention is architected but not fully proven here across all races.** Concurrent absent-state ensures could both reach start decisions before a lock/owner becomes visible; mitigations (service manager behavior, runtime ownership fence inside gateway, reservations/multiplex logic) exist but were not exhaustively validated by executed concurrency experiments in this phase.

## Unknowns (must be recorded)
- **Native Hermes idempotency guarantee:** **not demonstrated as a formal guarantee** for all states/supervisors/platforms/multiplex modes from inspected evidence alone.
- **Concurrent invocation safety (multiple simultaneous `ensure` processes):** **unknown/unproven** for all environments (especially absent->start races, cross-process timing, service-manager races).
- **External side-effect duplication:** **unknown** in edge cases (e.g. duplicate spawn attempts contended by locks, repeated service start requests, downstream platform reconnect/start behavior).

## Risks
- Treating ensure as idempotent without proof could lead AJ to unsafe retries or parallel invocations causing duplicate daemons/resource contention (critical on 8 GB host) or ambiguous ownership.
- Any future AJ capability must assume **no exactly-once/no native idempotency** unless Hermes provides verifiable guarantees; AJ-side dedupe alone cannot prevent external duplication once multiple ensure commands run.
