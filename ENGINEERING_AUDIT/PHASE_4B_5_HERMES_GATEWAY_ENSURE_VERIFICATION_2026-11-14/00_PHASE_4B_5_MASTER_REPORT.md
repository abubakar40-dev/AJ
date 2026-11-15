# 00 — Phase 4B.5 Master Report
## Hermes Gateway Ensure: Pre-Implementation Verification Gate

**Project:** AJ (Agent Junction)  
**Phase:** 4B.5 — verification and evidence-gathering (NOT implementation)  
**Date:** 2026-11-14  
**Scope target:** verify whether exact Hermes command `hermes gateway ensure` can safely serve as a future narrowly scoped capability `hermes.gateway.ensure`.

## Executive summary
`hermes gateway ensure` **exists** in the installed/inspected Hermes `v0.23.0` (`~/.local/bin/hermes`, source `~/.hermes/hermes-agent` @ `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`, clean/detached) with a machine-readable JSON CLI (`--json`, `--timeout`, fixed exit-code mapping) backed by `ensure_gateway_runtime` (discovery-first; may attach to ready/served owner, wait on starting/retiring states, request start of an existing service, spawn an unmanaged detached `gateway run`, or—in a specific upgrade case—replace an incompatible older same-install owner). It is **not read-only**: it can produce lifecycle side effects (process/service start, runtime state/log/socket/lock files, potential downstream gateway activity) and has ambiguous/timeout/concurrency cases not fully proven safe. Read-back surfaces exist (control `identify`/endpoint validation, `gateway status`, runtime state files) but end-to-end startup success/partial-failure verification and native idempotency/concurrent safety are not sufficiently demonstrated for unconditional approval.

**Result:** evidence gathered; no implementation, no lifecycle experiments, no config/flag changes, AJ remains unattached.

## Verified facts
- AJ baseline preserved: `main` @ `468fdce...`, pre-existing 41 status entries unchanged by work; only `ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/` added (docs 00–10). No Git mutations beyond working-tree doc creation.
- Hermes identity/command contract/source path traced (`hermes_cli/gateway_runtime_cli.py`, `gateway_runtime*.py`, discovery/service/start/replace/multiplex, `subcommands/gateway.py`, control/runtime ownership/status modules) with supporting tests identified.
- Read-only checks: `aj --check` **ok 23/23, Hermes NOT ATTACHED**; `hermes gateway status/status --deep/list` and local runtime inspection showed existing user service gateway active (PID 5397) with expected control/state artifacts. **`hermes gateway ensure` not executed.**

## Source-code observations
- Ensure is bounded in interface but stateful in effect: discovery before start, single-start intent per invocation, service start-or-spawn paths, update fence, multiplex/retiring handling, incompatible-owner replacement (conditional), structured verdicts/exit codes, redacted startup-failure detail for dead child.
- Unmanaged spawn uses detached `gateway run --quiet` with controlled env stripping/carry-over (no shell, no `--replace` in spawn path, no install/login changes).

## Runtime observations
- Live host has active systemd gateway (`hermes-gateway.service`, long-lived, ~340M current observed in status, bridge/node children), control socket/state/pid/lock/logs present under `~/.hermes`.

## Inferences
- Likely low-risk when attaching to an already-ready owner; potentially mutating/high-impact when absent/start/replace paths trigger. “Second call exits successfully” is not proof of idempotency or absence of side effects.

## Unknowns
- Native Hermes idempotency and concurrent-invocation safety across all supervisor/profile/multiplex/race scenarios.
- Reliable success verification for all partial-start/platform states; full timeout/ambiguity recovery behavior in live cases.
- Exact downstream side effects/resource footprint for a newly started gateway in target profiles; complete redaction/logging behavior across all runtime paths.
- Unexercised platform branches (Windows/launchd/s6) on this machine.

## Risks
- **Security/boundary:** lifecycle side effects despite fixed argv/no-shell; TOCTOU/local-state influence; `local_trust` not authentication; log/output sensitivity outside JSON boundary.
- **Reliability:** start/partial-start/timeout ambiguity, possible orphan/conflict processes, duplicate-resource risk on 8 GB RAM, retry-after-ambiguity hazards.
- **Storage:** NTFS-backed workspace/tmp SQLite/WAL intermittency remains a separate unresolved reliability concern; persistence must not be assumed reliable.
- **Operational:** killing ensure subprocess does not rollback started gateway.

## Recommended next engineering phase
- **Phase 4B.6 (proposed): `hermes.gateway.ensure` controlled design & entry-criteria closure** — no implementation until: state-gated mutating/read-only scope decided, concurrency/idempotency/read-back evidence obtained (approved isolated tests if needed), AJ contract/verdict mapping and fail-safe ambiguity policy designed, fixed-argv/env/output controls and resource/backpressure policy specified, deterministic test plan completed. If criteria cannot be evidenced, remain on read-only `hermes.status.read`.

## Repository preservation evidence
- AJ `main`/`468fdce...` unchanged; final status 42 entries (41 pre-existing + this audit dir). No staging/commits/push/destructive Git ops. Hermes/JARVIS/HELIX repos untouched. No gateway lifecycle action performed. Feature flags/config unchanged. `aj --check` reports Hermes NOT ATTACHED.

---
**PHASE 4B.5 RESULT:** COMPLETE

**RECOMMENDATION:** CONDITIONAL GO

**IMPLEMENTATION AUTHORIZED:** NO

**FEATURE FLAGS CHANGED:** NO

**HERMES GATEWAY LIFECYCLE ACTION PERFORMED:** NO

**AJ↔HERMES STATUS:** NOT ATTACHED

### What was verified
- Baseline/HEAD/status preservation; Hermes executable/version/source identity (`v0.23.0`, `2bd378ed...`); `gateway ensure` existence, CLI contract, and source-level execution/side-effect/discovery/start/replace/ownership behavior; read-only runtime state and `aj --check` (23/23, NOT ATTACHED); existing Hermes test coverage identified (not re-run).

### What remains unknown
- Native idempotency and concurrent-invocation safety guarantees; fully reliable success/partial-failure verification and recovery across all states; unexecuted live ensure outcomes and downstream startup effects/resource footprint; platform branches not exercised locally.

### Security findings
- Fixed-argv/no-shell CLI boundary feasible; credential-free JSON intent; controlled spawn env stripping in code; discovery/control local-boundary checks present. Risks: lifecycle side effects, TOCTOU/local-state influence, `local_trust` not authentication, potential sensitive runtime/log data outside ensure payload, ambiguity-driven misuse.

### Reliability findings
- Bounded verdict/timeout model exists but can return ambiguous/transitional states (`starting/deadline/runtime_exited/inaccessible/...`); ensure may start long-lived runtime or (conditionally) replace incompatible owner; subprocess termination not rollback; duplicate/orphan/resource risks on 8 GB host; NTFS/SQLite persistence reliability remains separately unresolved.

### Exact conditions for the next phase
- Satisfy `09_DECISION_AND_IMPLEMENTATION_ENTRY_CRITERIA.md` conditions 1–8 (scoped state gating, idempotency/concurrency evidence, read-back/verification, timeout/recovery/no-unsafe-retry, security controls, 8 GB resource policy, deterministic tests, storage reliability posture). No implementation before evidence-backed closure.

### Repository preservation evidence
- AJ unchanged except new `ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/` (00–10). Pre-existing tracked/untracked work preserved. Protected repos untouched. No Git staging/commits/push/destructive actions.

### Recommended next engineering phase
- **Phase 4B.6 — `hermes.gateway.ensure` controlled design & entry-criteria closure** (separately scoped, evidence-gated; implementation only after conditions met; otherwise remain read-only `hermes.status.read`).
