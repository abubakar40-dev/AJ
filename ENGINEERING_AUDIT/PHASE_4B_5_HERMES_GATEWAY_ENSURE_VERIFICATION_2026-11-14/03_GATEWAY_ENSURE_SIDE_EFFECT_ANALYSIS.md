# 03 — Gateway Ensure Side-Effect Analysis

## Verified facts (source observations)
- **Can start/reconcile runtime:** `ensure_gateway_runtime` may (a) request start of an **existing** service via supervisor command (`systemctl --user/system start`, `launchctl kickstart/bootstrap`, `schtasks /Run`, `s6 start` as applicable in `gateway_runtime_service.py`) if service discovered and not running, or (b) spawn an **unmanaged detached** gateway process (`spawn_unmanaged_gateway` → `... gateway run --quiet [--idle-exit]`) if no existing service/owner is present and conditions require. It may also **wait** for starting/retiring owners and, in the specific incompatible-older-same-install case, trigger **stop/replace** of that owner (`replace_incompatible_owner`: planned-stop marker + terminate/kill with bounded waits).
- **Does not install/replace service definitions in this path:** `gateway_runtime_service` docstring states “Never installs anything”; `spawn_unmanaged_gateway` states “No --replace, persistence, login changes, elevation, shell, or inherited stdio”. Ensure command/parser has no install flags. (Service install/uninstall are separate `gateway install/uninstall` commands.)
- **Persistent/runtime state side effects when a gateway runs/starts:** runtime ownership/control/state mechanisms create/use files under profile home such as `gateway.lock`, `gateway.pid`, `gateway_state.json`, `gateway.sock` (or pointer), `gateway-starts.log`, logs (`logs/gateway-stdio.log`, `logs/gateway.log`, etc.), and gateway-owned runtime data/DB/session artifacts as the started gateway operates. Observed on this host: `gateway.lock`, `gateway.pid`, `gateway.sock`, `gateway_state.json`, `logs/*` present and owned by user (see runtime observation).
- **Process/system interactions:** may interact with service managers (start existing unit/job/task/slot), spawn detached processes, gateway binds/owns local control socket and runtime/API endpoints as implemented by gateway runtime (exact ports/endpoints not fully enumerated here from run path), and may read/write lock/state/log files. `gateway_runtime_start` sets `HERMES_HOME`, `HERMES_GATEWAY_DETACHED=1`, strips many launch/session flags, carries profile pin/policy as coded.
- **Configuration/credentials/env files:** no source evidence that `ensure_gateway_runtime`/`cmd_gateway_ensure` edits Hermes config files, `.env`, credentials, scheduled-job definitions, or service definitions; it reads config/home state for discovery/multiplex decisions and starts runtime. A started gateway may itself read/write its normal runtime state (separate from ensure command).
- **Interactive input:** CLI command has only `--json`/`--timeout`; parser rejects unknown args with machine error (no prompts). `ensure_gateway_runtime` is programmatic; spawned `gateway run --quiet` is non-interactive by flags/context (no evidence of prompts in ensure path).
- **Blocking behavior:** bounded by `--timeout` (default 60s; loop sleeps with `remaining(deadline)` and returns `starting/deadline` or other verdicts). However, individual discovery/service calls may block up to budgets/timeouts; a stalled control identify path can lead to `starting/control_timeout/deadline` outcomes (tests show bounded behavior in cases). **Not proven unconditionally non-blocking in all environments.**

## Runtime observations
- Current host: gateway already active under systemd (`Active: active (running)`, PID 5397, children include WhatsApp bridge/node and supervisor shell), consuming memory/CPU over long uptime; sockets/state files present. No ensure execution performed to mutate state.

## Inferences
- If gateway absent/unhealthy in a profile without an installed service, ensure can have material side effects: starting a long-lived detached `gateway run` process, creating logs/state/control artifacts, and potentially enabling platform/runtime activity configured in that profile — a **lifecycle/start side effect**, not read-only.
- If gateway already healthy/served, likely near-idempotent observational outcome; but not guaranteed across all states/races.

## Unknowns / risks
- Exact network port bindings, external connections, and full downstream runtime side effects of a newly started gateway depend on profile configuration (platforms, cron, integrations) — **not fully determined without executing** (execution not performed).
- Whether “ensure that one is running” can in some race/edge case start an additional conflicting process instance or contend with supervisor-managed restarts (ownership/service checks mitigate but require scenario-specific proof).
- `gateway run` internals (beyond ensure/start wrapper) not exhaustively audited here for all config mutations at runtime.

## Risks (if treated as safe read-like op)
- Accidental gateway startup, duplicate/runtime contention, resource use on 8 GB host, or unintended platform activity if run against absent/misconfigured profile.
