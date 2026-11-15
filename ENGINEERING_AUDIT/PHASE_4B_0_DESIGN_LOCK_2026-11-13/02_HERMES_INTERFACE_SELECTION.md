# 02 — Hermes Interface Selection

**Workstream B (Phase 4B.0).** Selection based on actual inspected source/runtime evidence. A running gateway is not treated as a secure integration boundary by itself.

## 1. Hermes runtime/source evidence (inspected)
- Runtime: `~/.hermes/` active (`gateway_state.json` running, pid `5397`, `gateway.sock`, `kanban.db`, sessions/state/config/logs, whatsapp connected, v0.23.0 / sha `2bd378ed`).
- Source: `~/.hermes/hermes-agent` (detached `2bd378ed`), rich CLI (`hermes_cli/*`, `hermes` entrypoint packaging), `run_agent.py` (`AIAgent` Python API), ACP adapter (`acp_adapter/*` including `gateway_server.py`, `gateway_client` usage), gateway internals (`hermes_cli/gateway*.py`, `gateway_client.py` RPC/WS transport), kanban CLI/workflow (`hermes_cli/kanban_*`), extensive tests including `tests/acp_adapter/test_gateway_*`.
- AJ side: `ExecutionPort` protocol + `UnavailableExecutionAdapter` (`aj/execution.py`), `ExecutionRequest/Result/SkillSpec` (`aj/contracts.py`), config `execution.runtime="none"`, feature flag `hermes_skills=false`.

## 2. Candidate interfaces

### Candidate 1 — Hermes CLI subprocess (local `hermes` commands)
| Criterion | Evidence / assessment |
|---|---|
| Implementation location | `hermes_cli/` subcommands/parsers (`_parser.py`, `subcommands/gateway.py`, `kanban_*`, etc.), installed/runtime-managed Hermes environment; `pyproject` defines `hermes-agent` package/entrypoints |
| Documented / actively used | Yes (README, `--help` surface, primary operator interface; gateway/kanban/skills etc. implemented) |
| Request/response format | Command argv/stdin → stdout/stderr text, exit code; some commands may emit structured-ish output, but not uniformly versioned as AJ contract |
| Execution lifecycle | Per-process invocation (or interaction with background gateway/DB depending command); lifecycle observable at process level |
| Authn/authz | Runs under local user/Hermes home/profile config and credentials; command-specific permissions depend on Hermes internals/tools/config; **no AJ-mediated boundary** by default |
| Permission enforcement | Hermes-side tool/approval/policy enforcement applies internally (unverified per-command for AJ use); AJ must enforce allowlist before invocation |
| Timeout/cancellation | OS process timeout/kill possible from AJ; **cooperative cancellation inside Hermes not guaranteed** via generic CLI kill; may leave unknown/partial state for side-effecting commands |
| Duplicate submission / idempotency | Command-dependent; generic CLI provides no universal idempotency key protocol |
| IDs/correlation | No standard AJ↔Hermes execution ID mapping; command output may include IDs in some domains (e.g. kanban/session) but not contract-guaranteed |
| Progress/result retrieval | Streaming stdout possible for some commands; usually synchronous result; no standard progress callback |
| Error handling | Exit codes + stderr/stdout; must be normalized/classified by adapter |
| State-mutation risk in testing | **High variability by command**; read-only status/info commands safer, task-creating/chat-executing commands can mutate state |
| Compatibility with AJ `ExecutionPort` | Good fit as a wrapped `execute(request)->ExecutionResult` call if bounded/normalized |

### Candidate 2 — ACP adapter / gateway projection (`acp_adapter/*`, gateway-backed)
| Criterion | Evidence / assessment |
|---|---|
| Implementation location | `acp_adapter/server.py`, `gateway_server.py`, `gateway_client.py`, `gateway_reply.py`, `session.py`, permissions/tools/modes; large gateway test suite under `tests/acp_adapter/test_gateway_*` |
| Documented / actively used | Implemented as ACP stdio server/projection over running gateway/profile home; protocol/version handling present (`acp.PROTOCOL_VERSION`, initialize/capabilities) |
| Request/response format | ACP JSON-RPC over stdio (editor↔agent) with session/prompt/tool/permission/update semantics; gateway RPC/events internally |
| Execution lifecycle | Rich: session create/load/resume/fork/list, prompt turns, streaming updates, tool calls, cancellation/stop semantics exposed in protocol flows |
| Authn/authz | Tied to local Hermes profile/gateway, auth methods in adapter, editor-client trust model; not designed as AJ server-to-runtime authorization boundary |
| Permission enforcement | ACP permission request bridging to Hermes approvals (`acp_adapter/permissions.py`); complex interaction model |
| Timeout/cancellation | Better protocol-level support than generic CLI in principle; actual behavior depends on gateway/turn state |
| Duplicate/idempotency | Session/admission/input-id handling exists internally (gateway-side); adapter-level idempotency for AJ requests would need careful mapping |
| IDs/correlation | Sessions, admissions, tool call IDs, message IDs available internally; mappable but complex |
| Progress/result retrieval | Strong (streamed chunks, tool start/complete, plan/thought updates, usage) |
| Error handling | Structured protocol errors plus gateway errors; normalization required |
| State-mutation risk in testing | Session/prompt operations can mutate Hermes state/sessions/history; careful isolation required |
| Compatibility with AJ `ExecutionPort` | Possible but **high integration complexity/coupling** for v0; better as future evolution if richer lifecycle needed |

### Candidate 3 — Direct gateway WebSocket/RPC client (`hermes_cli/gateway_client.py`)
| Criterion | Evidence / assessment |
|---|---|
| Implementation location | `hermes_cli/gateway_client.py` (tickets, WS target, RPC/event queue, timeouts, error semantics), used by ACP/gateway tooling |
| Documented / actively used | Internal transport/client implementation; actively used by Hermes components |
| Request/response format | JSON-RPC-like frames over websocket (`method/params/result/error`, events); internal protocol |
| Execution lifecycle | Can interact with running gateway sessions/verbs depending exposed methods; potentially rich |
| Authn/authz | Session tickets/subprotocols, local gateway socket/endpoint assumptions; internal trust model |
| Permission enforcement | Inherited from gateway/agent behavior, not an AJ policy boundary |
| Timeout/cancellation | RPC timeouts and event handling primitives present; method-specific semantics vary |
| Duplicate/idempotency | Depends on method; some internal handling exists, but AJ-facing idempotency contract unspecified |
| IDs/correlation | Access to internal IDs possible, but protocol stability/contract not externalized for AJ |
| Progress/result retrieval | Event stream/RPC responses available |
| Error handling | Typed client/RPC errors; requires deep protocol knowledge |
| State-mutation risk in testing | Method-dependent; high risk without strict read-only method selection |
| Compatibility with AJ `ExecutionPort` | Technically feasible, but **internal/protocol-coupling risk high** for first bounded adapter |

### Candidate 4 — Direct Python API import (`run_agent.AIAgent` / agent internals)
| Criterion | Evidence / assessment |
|---|---|
| Implementation location | `run_agent.py` (`AIAgent`), `agent/*` modules in `~/.hermes/hermes-agent` |
| Documented / actively used | Internal library-like surface (`from run_agent import AIAgent` documented in module header) |
| Request/response format | Python objects/strings/tool loops, in-process stateful behavior |
| Execution lifecycle | Full agent conversation/tool loop in-process; rich but complex and side-effect capable |
| Authn/authz | Uses local env/config/credentials directly; bypasses process boundary; AJ cannot constrain except in-process |
| Permission enforcement | Hermes internal approval/tool mechanisms apply if configured; AJ mediation weaker and coupling high |
| Timeout/cancellation | Requires thread/interrupt handling integration; non-trivial and failure-prone |
| Duplicate/idempotency | No AJ contract-level idempotency; session semantics internal |
| IDs/correlation | Internal session/tool IDs available only via deep coupling |
| Progress/result retrieval | Callbacks/return values possible but tightly coupled |
| Error handling | Exceptions/internal states; adapter would absorb large surface |
| State-mutation risk in testing | **High** (agent/tool execution can mutate many subsystems) |
| Compatibility with AJ `ExecutionPort` | Poor for safe first boundary (violates "Hermes-specific code must not spread" spirit, high instability)

### Candidate 5 — Kanban/task workflow interfaces (`hermes kanban`, `kanban.db`, dispatch)
| Criterion | Evidence / assessment |
|---|---|
| Implementation location | `hermes_cli/kanban_*`, `~/.hermes/kanban.db`, docs/bridge integrations in helix |
| Documented / actively used | Present and used by Hermes/helix flows |
| Request/response format | CLI/DB/task records and workflow states |
| Execution lifecycle | Asynchronous task lifecycle/dispatch/worker semantics (non-trivial, board/workflow specific) |
| Authn/authz | Local profile/Hermes permissions; board/task semantics |
| Permission enforcement | Workflow/dispatch rules, not AJ capability allowlist boundary |
| Timeout/cancellation | Task-level states exist but mapping complex; not a simple bounded execution call |
| Duplicate/idempotency | Task creation/dispatch can duplicate work if misused |
| IDs/correlation | Kanban/task/run IDs exist (`t_*` ecosystem), but asynchronous and domain-specific |
| Progress/result retrieval | Indirect (task state/comments/artifacts), eventual |
| Error handling | Workflow/dispatch failures, blocked/review states |
| State-mutation risk in testing | **High** (creates/mutates tasks, may trigger dispatch/workers) |
| Compatibility with AJ `ExecutionPort` | Mismatch for first bounded synchronous-safe probe; better for later delegated work queueing (deferred)

## 3. Comparison matrix

| Criterion | CLI subprocess | ACP/gateway projection | Gateway RPC/WS client | Direct Python `AIAgent` | Kanban/task |
|---|---:|---:|---:|---:|---:|
| Security / boundary clarity | **Medium-High** (process boundary, narrow argv allowlist possible) | Medium (complex trusted local protocol/client model) | Medium-Low (internal protocol coupling) | **Low** (in-process, broad access) | Medium (workflow side effects) |
| Operational stability for v0 | **Medium-High** | Medium | Medium-Low (internal) | Low-Medium | Low for bounded probe |
| Contract clarity | Medium (normalize text/exit) | Medium-High (structured protocol) but complex mapping | Low-Medium (internal) | Low (internal API drift) | Low for ExecutionPort |
| Correlation support | Low-Medium (command-dependent) | **High** (sessions/admissions/tool IDs) | High (internal IDs) | Medium (internal) | Medium (task IDs) |
| Cancellation support | Medium (process kill; cooperative unknown) | Medium-High (protocol/cancel paths) | Medium (method-dependent) | Medium (interrupt complexity) | Medium (task state changes) |
| Idempotency support | Low (command-dependent) | Medium (input/admission concepts) | Medium (method-dependent) | Low | Low-Medium |
| Observability | **High for bounded command** (argv/exit/stdout/stderr captured) | High but voluminous/complex | Medium | Medium (in-process) | Medium (async state) |
| Implementation complexity | **Low-Medium** | **High** | High | Medium-High | High |
| Compatibility with AJ `ExecutionPort` | **High for minimal v0** | Medium | Medium | Medium-Low | Low |
| Safety for read-only first capability | **High if command is read-only/allowlisted** | Medium (session/prompt side effects possible) | Medium (depends method) | Low | Low |

## 4. Recommendation (exactly one preferred interface)

**Preferred interface for the first adapter spike:** **Hermes CLI subprocess boundary** (`hermes` CLI), invoked only via a strict, AJ-owned allowlisted command/argument template for a single **read-only** capability (`hermes.status.read`) with bounded timeout/output capture and normalized `ExecutionResult`/evidence.

**Rationale (evidence-based):**
- Aligns with AJ's explicit boundary principle (adapter/port; no Hermes internals spread) and minimizes protocol coupling versus ACP/gateway RPC internals.
- Process-level invocation provides clear observability and enforceable pre-execution allowlist/validation in AJ.
- Hermes CLI is the primary, actively used operator surface; gateway is already running, so read-only status/introspection-style commands can be evaluated for safe bounded use.
- Fits `ExecutionPort.execute(request)->ExecutionResult` with lowest implementation complexity for v0 while preserving fail-closed behavior.

**Confidence:** **Medium-high** for boundary choice; **Medium** for exact command-level ID/idempotency guarantees (must be verified per command in 4B.1 preflight; unknowns must remain unknown).

## 5. Alternatives not selected (and why)
- **ACP/gateway projection:** strongest structured lifecycle/correlation/progress potential (`session/prompt/tool/permission` semantics, rich IDs), but **too complex and editor-oriented** for minimal v0; higher risk of incorrect mapping and stateful session side effects. **Deferred as future candidate** if CLI cannot meet lifecycle/observability needs.
- **Gateway RPC/WS client (`gateway_client`)**: powerful/internal and can reach rich semantics, but **internal protocol coupling and auth/ticket complexity** make it unsafe as first minimal boundary.
- **Direct Python `AIAgent` import:** **rejected for v0** due to in-process coupling, broad mutable surface, instability, and weak AJ mediation boundary.
- **Kanban/task workflows:** **rejected for v0** because task creation/dispatch is asynchronous and side-effectful, unsuitable for narrow, reversible, bounded first capability.

## 6. Minimum safety requirements check
- **Can a safe read-only bounded command be allowlisted and validated?** Likely, but **command-specific verification required** in 4B.1 before enablement (no state mutation, bounded output, predictable exit semantics). 
- **Can AJ fail closed without inventing IDs/success?** Yes (contract requires unknown/unsupported fields and honest statuses).
- **If no command satisfies requirements:** **implementation must be blocked** for 4B.1 and escalated to interface re-selection (ACP/gateway RPC) under new approval.

**Conclusion:** preferred interface selected provisionally with explicit command-level verification gate; no invention of integration behavior.
