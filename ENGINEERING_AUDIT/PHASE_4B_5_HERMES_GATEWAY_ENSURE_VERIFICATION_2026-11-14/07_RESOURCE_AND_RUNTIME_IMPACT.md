# 07 — Resource and Runtime Impact

## Target constraints (verified context)
- Dell Latitude 5480, Intel i5-7300U, **8 GB RAM**, Ubuntu 26.04.1, GNOME Wayland. AJ workspace on NTFS-mounted drive (My Drive). Manual desktop launch intended; no boot-time auto-start changes in this phase.

## Verified facts / runtime observations
- Current host gateway (`hermes-gateway.service`, PID 5397, started 2026-11-13 07:57:29 PKT) is a long-lived process tree: main Python `gateway run` plus WhatsApp bridge node process and supervisor shell.
  - `systemctl --user status` (observed): `Tasks: 30`, `Memory: ~340–352M` current (peak ~546.7M, swap shown in status history), `CPU ~12min+` over 1d+ uptime.
  - `ps` snapshot: RSS ~242 MB (main), ~89 MB (node bridge), small helpers (plus prior status deep process showed ensure/status client transiently).
- `ensure_gateway_runtime` can start an existing service or spawn an unmanaged detached `gateway run` daemon when absent/unserved conditions require; started gateways are long-lived runtimes (not one-shot probes).

## Source observations relevant to duplication/limits
- Discovery/ownership/multiplex/service logic aims to attach to or coordinate a single owner per profile/host context and avoid naive duplicate starts (e.g. wait for starting/retiring/reserved multiplexers, ownership fences, replace only specific incompatible owner). Service managers also enforce single-instance behavior per unit in typical cases.
- However, absent-state races, misconfiguration, or edge cases are not proven impossible; unmanaged detached spawns rely on runtime arbitration.

## Inferences
- Starting an additional gateway (or duplicate instance in error) can have significant RAM/CPU impact on an 8 GB machine (hundreds of MB observed for one active gateway stack, plus platform-specific workers/bridges/browsers/tools as configured).
- Invoking ensure against an **already running/ready** gateway is expected to be low-overhead (discovery/check + JSON verdict) compared to startup, but this was **not benchmarked** by executing ensure here.
- Port/socket/bind conflicts or platform polling duplication are plausible failure modes if duplicate runtimes arise (configuration-dependent).

## Unknowns
- Exact resource footprint of a cold start/ensure on this machine/profile (no lifecycle experiment performed).
- Built-in concurrency/resource limits enforced by `gateway ensure` itself against repeated/parallel invocations beyond discovery/ownership mechanisms (no stress tests performed).
- Behavior under memory pressure or when multiple profiles/gateways are involved.

## Risks
- On 8 GB RAM, accidental duplicate gateway/runtime startup or repeated ensure-induced churn could degrade system responsiveness or cause OOM/swap pressure. Any future integration must treat lifecycle operations as resource-sensitive and avoid unbounded/parallel invocations.
