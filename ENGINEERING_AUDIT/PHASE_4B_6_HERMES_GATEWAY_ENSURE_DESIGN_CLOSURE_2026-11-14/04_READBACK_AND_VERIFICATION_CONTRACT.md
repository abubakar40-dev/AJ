# 04 — Read-back and Verification Contract (Criterion 3)

## Evidence surfaces (source observations / 4B.5)
- **Control socket `identify` / endpoint discovery:** validates reachable local control owner, protocol/identity/profile/home/served scope/capabilities/supervisor/api origin as implemented (`gateway_runtime_discovery.py`, `gateway/control_socket.py`, `ensure_gateway_runtime` attachable/ready logic).
- **Ensure verdict payload:** `state`, `reason_code`, `detail`, `endpoint` (when present), exit code mapping (`hermes_cli/gateway_runtime_cli.py`).
- **Service/process state:** supervisor status (e.g. systemd active/running), PID/lock/state files (`gateway.pid`, `gateway.lock`, `gateway_state.json`, socket/pointer), logs (`gateway-stdio.log`, etc.).
- **`hermes gateway status`:** operator-facing aggregation (not a sole authoritative AJ success oracle).

**Principles:** do not infer health from process existence alone; do not infer successful execution from exit code alone; prefer validated control/read-back evidence; treat gaps as `unknown`/`requires_manual_review`.

## Verification matrix

| Observation | What it proves | What it does not prove |
|---|---|---|
| Process exists (PID alive / service active) | A process/unit is running or reported active at observation time | Correct runtime/owner/profile; readiness; endpoint validity; semantic health; absence of duplicates; that lifecycle goal is satisfied; that side effects completed safely |
| Gateway status says active/running (e.g. systemd/status text) | Supervisor/CLI reports active state per its view | Control endpoint readiness; protocol/profile match; internal component health; successful attach/ensure outcome; no partial startup or conflicting owner elsewhere |
| Control `identify` succeeds with valid response | A reachable control owner answered and passed implemented response/validation checks (bounded identity/protocol/profile/scope/capability/origin constraints as applicable) | Full application/platform health; absence of downstream errors; durability of state; that start/replace side effects were intended/authorized; future liveness beyond observation instant |
| Endpoint validation succeeds (discovery/attachable-ready criteria met) | Endpoint is consistent with discovery contract for attachment/use at observation time (strongest available readiness/ownership signal) | Complete functional correctness; no latent partial startup elsewhere; absence of external side-effect duplication; exactly-once/idempotency |
| Ensure returns success (exit 0 / `state=ready`) | CLI/ensure reports ready verdict per its logic at completion | That no mutation occurred earlier in other attempts; that state remains stable; full health; that AJ preconditions/authorization were satisfied; proof against races/concurrency issues |
| Ensure returns `starting`/deadline/runtime_exited/inaccessible/incompatible/conflict/draining | Specific bounded verdict/reason observed | Final steady state in ambiguous cases (`starting/deadline`), root cause completeness, or safe retry eligibility |

## Read-back outcomes and AJ recording (proposed)

| Condition | AJ final classification guidance | Required evidence to record |
|---|---|---|
| Validated ready endpoint/identity after observation or ensure | `completed` (attach/ready) **only if** preconditions/authorization satisfied and evidence consistent | verdict, endpoint identity/profile/home/api origin as available, control/read-back facts, timestamps |
| Bounded failure with no ambiguity of side effect beyond known safe classification | `failed` or `rejected` per policy | verdict/state/reason_code/detail (redacted), exit code, observations |
| `starting`, local timeout, process exit but readiness unconfirmed, or contradictory signals | **`timeout`/transitional observation with final `unknown` or `requires_manual_review`** (no success claim) | all verdicts/reasons, what was/was not verified, last observations, explicit ambiguity flag |
| Read-back channels unavailable/untrusted/insufficient | **`unknown` or `requires_manual_review`** | probe failures, missing surfaces, partial data, reason unverifiable |
| Possible partial startup / incompatible / conflict / runtime_exited after mutating attempt | **`requires_manual_review`** unless safe convergence proven by re-readback | before/after observations, mutating attempt indicator, no-rollback note |

## Contract requirements
- Record **observed initial state**, **action taken** (or none), **process result** (argv class/exit/stdout-stderr bounded+redacted summaries, not secrets), **read-back result**, and **final classification** separately.
- Never collapse “command ran” into “gateway healthy/ensured”.
- Re-readback before/after any mutating attempt (if ever authorized) is mandatory; single snapshot insufficient for ambiguous transitions.
