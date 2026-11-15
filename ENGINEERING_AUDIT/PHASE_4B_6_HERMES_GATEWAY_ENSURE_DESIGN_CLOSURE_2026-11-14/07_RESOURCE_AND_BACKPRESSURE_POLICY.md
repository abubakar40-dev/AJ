# 07 — Resource and Backpressure Policy (Criterion 6)

## Target machine (verified context)
- Dell Latitude 5480, Intel i5-7300U, **8 GB RAM**, Intel HD 620, Ubuntu 26.04.1, GNOME Wayland.
- Runtime observation (read-only): existing Hermes gateway service active (PID 5397) with ~340M current / ~547M peak memory reported by systemd, plus child processes (bridge/node/helpers). No new gateway processes started during 4B.6.

## Evaluation (design)

| Area | Assessment | Evidence / confidence |
|---|---|---|
| Gateway singleton assumptions | Hermes runtime/profile coordination and AJ design should assume **shared gateway runtime per target profile/scope** where applicable; `ensure` attaches to existing owner when ready. Duplicates are hazardous. | Source ownership/lock/control/service logic (4B.5/03); not proof against all races |
| Maximum concurrent tasks | AJ future requirement (multi-task/sub-agents) but must be resource-aware; no measured optimum | **Provisional only** |
| Maximum concurrent Hermes executions | Constrained by runtime capacity, configured providers/tools, and RAM; gateway may multiplex sessions but limits unknown | **Unmeasured** |
| Gateway lifecycle ownership | Lifecycle ops (start/replace) are **global-to-target-runtime** concerns, not per-task spawn triggers. Tasks share runtime; lifecycle serialized/gated per profile/resource. | Architecture requirement + 4B.5 side effects |
| Memory budgets | One gateway stack can consume hundreds of MB; headroom limited on 8 GB with desktop/IDE/browser/other services | Runtime observation; profile-dependent unknowns |
| CPU contention | i5-7300U (2C/4T) susceptible under parallel model/runtime workloads | Hardware fact; load unmeasured |
| Process monitoring | Required: track gateway/child PIDs, RSS/CPU, restarts, duplicates, stuck states | Design requirement |
| Queue backpressure | Required before admitting mutating lifecycle ops or heavy executions when budgets exceeded | Design requirement |
| Priority handling | Lifecycle health/attach/readiness checks may need priority over non-urgent starts; starvation avoidance needed | Design requirement |
| Graceful degradation | Shed/queue/reject new lifecycle or execution requests under pressure; prefer attach/read-only over start | Design requirement |

## Conservative proposed defaults (PROVISIONAL — for later measurement/tuning)

> **Marked provisional:** not evidence-optimized. Apply only if/when implementation is separately authorized; tune from telemetry on target hardware.

| Knob | Provisional default | Rationale |
|---|---|---|
| Concurrent `hermes.gateway.ensure` (mutating/start/replace) in-flight globally per AJ instance | **1** | Avoid duplicate/racing lifecycle side effects and resource spikes |
| Concurrent `ensure` per target profile/resource | **1** (with dedupe/lease) | Target-level serialization |
| Parallel `ensure` calls issued by scheduler | **0 extra** beyond single in-flight mutating op; observe/attach reads may be limited/batched | Backpressure |
| Auto-start on absent when tasks pending | **Disabled by default**; require explicit policy/permission + admission check | Minimize surprise resource use on 8 GB |
| Admission before mutating lifecycle action | Require free-memory/headroom check threshold (e.g. keep substantial headroom; exact MB threshold **TBD by measurement**) and no existing healthy duplicate | Prevent OOM/swap thrash |
| Max concurrent heavy task executions sharing gateway | **Conservative small number (e.g. 1–2)** provisional, subject to runtime/profile measurement | 8 GB/2C4T constraint |
| Retry after lifecycle ambiguity | **0 automatic** | Safety over throughput |

## Rules
- **AJ must not start duplicate gateways simply because multiple tasks are running.** Distinguish **shared runtime lifecycle** from **independent task execution**.
- Prefer **attach to ready shared runtime**; queue or reject tasks needing unavailable runtime rather than spawning duplicates.
- Backpressure must propagate to scheduler/orchestrator (future phase) with truthful task states.

## Unknowns
- Cold-start and steady-state memory/CPU per profile/config, provider/tool usage, and under concurrent task load.
- Safe measured concurrency ceilings for this machine.
