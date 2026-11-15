# 05 — Lifecycle, Failure, and Recovery Analysis

## Verified facts (source observations)
- **Read-back/verdict signals:** ensure returns structured discovery verdicts (`ready`, `starting`, `draining`, `inaccessible`, `incompatible`, `conflict`, `absent` mapped via flow) with `reason_code`, optional `detail`, and endpoint/identity fields when available. `discover_gateway_endpoint`/control `identify` (`gateway/control_socket.py`, `gateway_runtime_discovery.py`) query live control socket/pipe and validate runtime protocol, served profile match, state, capabilities (`session-authority-v1`), identity, loopback `api_origin`, supervisor; distinguishes states like starting/draining/restart-wait/idle_exit/parked/inaccessible reasons. `gateway status` and runtime status files (`gateway_state.json`, PID/lock/socket, heartbeat/start logs) provide operator-facing/runtime diagnostics.
- **Healthy/already-running determination:** `attachable()` accepts `ready` and specific restart-wait draining case; endpoint discovery checks served profile/home canonicalization and liveness via control response/state. Service discovery also checks manager-reported active/running states.
- **Timeout behavior:** ensure loop bounded by deadline; on timeout raises/returns `starting, reason_code=deadline` (or control timeout mapped) in several paths; `cmd_gateway_ensure` maps deadline/starting/absent to exit 5. `remaining()` enforces budget.
- **Spawned child died before serving:** if requested child polled exited and observed state absent, returns `inaccessible, reason_code=runtime_exited` with redacted startup failure report from `logs/gateway-stdio.log` tail/status (`startup_failure_report`).
- **Update fence:** `_update_fenced` + `_fenced_verdict` return draining/update-paused (or attachable restart-wait) without starting/replacing while update owns install.
- **Retiring/replace cases:** idle-exit/replaced draining owners waited out before starting replacement; incompatible older same-install owner may be stopped once with planned-stop marker + graceful/forced termination attempts and specific refusal/details if unverified/unreachable/newer/foreign/did-not-exit.
- **Killing local ensure subprocess:** ensure is a short-lived client command that may have requested service start or spawned a detached daemon; terminating the ensure process does **not** inherently stop an already started detached/service-managed gateway. Detached spawn uses independent session/process-group/platform detach mechanisms.
- **Retry behavior:** loop can continue polling within deadline; after child exit -> runtime_exited verdict (no second launch in same invocation). External retries (new invocations) may re-enter discovery/start logic; safety under ambiguous prior state is not fully guaranteed.

## Runtime observations
- `hermes gateway status --deep` reports service active/running (PID 5397, uptime ~1d+), control artifacts present (`gateway.pid/lock/sock/state.json`), recent logs/shutdown history visible. Demonstrates existing read-back surfaces (systemd status, state files, logs) but not a post-`ensure` mutation sequence.

## Inferences
- **Partial startup is plausible:** service start requested or detached process spawned but not yet ready can yield `starting/deadline`; gateway may later become ready or fail independently. Ensure’s verdict is point-in-time/bounded.
- **Orphan/conflicting process risk:** unmanaged detached start, failed supervision, or race conditions can leave gateway processes/state requiring operator intervention; source contains recovery/refusal logic but not absolute prevention proof.

## Unknowns / recovery gaps
- **Reliable verification of successful startup in all cases:** control `identify`/endpoint validation is strong when reachable and well-formed, but `gateway status` text/state sufficiency across every partial-failure/platform-adapter scenario is **not fully proven**. Service “active” != gateway semantically healthy for all internal components.
- **Whether killing CLI process stops gateway it started:** **No for detached/service-managed started gateway in general** (by design for detached start and service requests) — ensure process exit is not a rollback mechanism.
- **Orphan gateway after interruption:** possible if ensure interrupted mid-flow after triggering start/spawn before convergence; detection/recovery depends on status/discovery and operator actions.
- **Retry safety after timeout/ambiguity:** **unknown** in cases where side effect may have begun but outcome unknown (could be harmless convergence or conflict depending state).

## Risks
- Misinterpreting `starting/deadline` or process-level signals as success/failure without read-back; unsafe automated retries; orphaned gateways consuming 8 GB RAM resources.
