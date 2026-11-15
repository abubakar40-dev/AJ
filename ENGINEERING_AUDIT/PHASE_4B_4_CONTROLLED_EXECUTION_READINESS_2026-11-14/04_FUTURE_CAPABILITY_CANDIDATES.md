# 04 — Future Capability Candidates (design only, NOT implemented)

Evidence sources: installed Hermes CLI `v0.23.0` help/status inspection (`hermes --help`, `gateway/cron/webhook/send/pause/resume/kanban/profile --help`, `hermes status`, `hermes gateway list/status`) and AJ current boundary (`hermes.status.read` via fixed `hermes gateway status`). No mutating commands executed.

## Candidate 1 — `hermes.gateway.ensure` (preferred for analysis)
| Field | Assessment |
|---|---|
| Capability name | `hermes.gateway.ensure` (proposed) |
| Exact interface/command | `hermes gateway ensure` (fixed argv, no user args) — **must be verified as fixed/no-interactive side channels before implementation** |
| Read-only/mutating | **Mutating (local runtime/service state)** per CLI description: “Ensure a local runtime without installing or replacing a service” (may start/ensure gateway runtime) |
| Inputs | None (fixed) in proposed form; no user-controlled payload |
| Outputs | CLI stdout/stderr/exit code (unstructured text), bounded |
| Side effects | May start or reconcile local gateway runtime/process state; no service install/replace claimed by help, but effect is operational |
| Required permissions | AJ capability allow + operator-authorized local control (AJ 5-level: likely level 1/2 local reversible-ish action depending policy; **not** authenticated identity) |
| Identity assumptions | `local_trust` only (non-authenticated); operator environment trust |
| Idempotency | Potentially idempotent-by-intent (“ensure”) but **Hermes-native idempotency/operation ID unknown**; AJ can dedupe request keys locally but cannot prove single external effect without evidence |
| Cancellation | Local process termination possible; remote/runtime “ensure” cancellation semantics **unknown**; kill ≠ rollback |
| Failure modes | spawn failure, nonzero, timeout with ambiguous runtime state, partial/changed state despite failure, unknown outcome |
| Evidence requirements | fixed argv, timestamps, exit/signal, bounded/redacted output, correlation IDs, `hermes_execution_id=null` unless Hermes returns one (none known), explicit uncertainty notes |
| Secret requirements | none in argv; env allowlist only; output redaction best-effort |
| Blast radius | **Local host/process scope** (gateway runtime availability) — lower than messaging/external comms or arbitrary task creation, but can affect running sessions/dispatch behavior |
| Testing strategy | mock/runner contract tests, fixed-argv enforcement, config gating, timeout/failure/ambiguity classification, isolated controlled integration only if safe and explicitly approved (not in 4B.4) |
| Relative safety | Safer than external messaging or arbitrary board mutation; more side-effect than status. **Unknowns remain (exact ensure semantics, idempotency, observability).** |

## Candidate 2 — `hermes.pause` / `hermes.resume` (state toggle pair; assessed as one control capability family)
| Field | Assessment |
|---|---|
| Capability name | `hermes.pause` (and inverse `hermes.resume`) — proposed as separate capabilities if ever considered |
| Exact interface/command | `hermes pause [--reason REASON?]` (help shows optional reason) / `hermes resume` (fixed) |
| Read-only/mutating | **Mutating/sensitive operational control** |
| Inputs | `pause` accepts optional reason text in CLI; `resume` none |
| Outputs | CLI text/exit (unstructured) |
| Side effects | Global emergency stop of new work (cron/kanban dispatch, new gateway turns incl. CLI/TUI/Desktop held) until resume; in-flight work not killed; resume removes sentinel |
| Required permissions | Elevated local operational control (high impact on availability/automation), explicit authorization/confirmation likely required by AJ policy for side effects; no authenticated remote identity |
| Identity assumptions | `local_trust` only |
| Idempotency | Pause/resume are state toggles; repeated calls may be benign or state-dependent — **Hermes semantics not formally contracted to AJ** |
| Cancellation | Not applicable as cancellable remote job; effect is immediate local state change |
| Failure modes | spawn/timeout/nonzero/ambiguous state (paused or not?), partial application unknown from text alone |
| Evidence requirements | command/args actually executed (reason handling risk), resulting state evidence unclear from exit alone; strong need for read-back verification capability |
| Secret requirements | reason text may contain sensitive info — must be treated as untrusted input and redacted/bounded if ever accepted (currently increases risk) |
| Blast radius | **Broad operational disruption** across automation/turn handling |
| Testing strategy | would require strict arg validation (or fixed/no-reason only), state verification, rollback (resume) considerations, high caution |
| Relative safety | **More dangerous** than ensure due to broad availability impact and (for pause) user-supplied reason argument unless eliminated |

## Candidate 3 — `hermes.cron.create` / other cron-webhook mutations (rejected class example)
| Field | Assessment |
|---|---|
| Capability name | e.g. `hermes.cron.create` / `pause` / `resume` / `remove` / `run` (CLI exposes full management) |
| Exact interface/command | multiple subcommands with required/variable arguments (schedules, prompts, targets, job IDs) — **not fixed argv** in general form |
| Read-only/mutating | **Mutating, persistent, potentially high-impact** (scheduled execution, external actions depending job content) |
| Inputs | complex user/task-controlled parameters |
| Outputs | unstructured CLI output, job IDs/state not standardized in AJ contract |
| Side effects | creates/modifies/deletes/triggers scheduled jobs; downstream effects may be external, delayed, and hard to attribute |
| Required permissions | would require strict schema/allowlist, confirmation, and possibly higher trust; `local_trust` insufficient for high-impact automation |
| Identity assumptions | none verified |
| Idempotency | **poor/unknown** (duplicate creates, ambiguous retries) without strong external keys |
| Cancellation | job-level controls exist in CLI but cancellation/stop semantics for running effects are complex/unknown |
| Failure modes | high ambiguity, duplicate scheduling, unintended execution, difficult recovery |
| Evidence requirements | durable job IDs, schedules, payload provenance, run linkage — not available in current AJ-Hermes contract/evidence path |
| Secret requirements | prompts/targets may carry secrets |
| Blast radius | **High** (persistent automation, possible external side effects over time) |
| Testing strategy | complex; needs end-to-end controlled environment and strong rollback/cleanup |
| Relative safety | **Significantly more dangerous** than gateway ensure/status; not suitable as first mutating capability |

**Selection note:** no candidate is approved for implementation in 4B.4. Candidates chosen to illustrate smallest-to-riskier mutating/local-control space based on actual CLI surface.
