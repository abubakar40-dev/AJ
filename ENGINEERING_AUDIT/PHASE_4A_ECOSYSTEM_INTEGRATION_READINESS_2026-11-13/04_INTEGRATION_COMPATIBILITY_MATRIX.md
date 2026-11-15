# 04 — Integration Compatibility Matrix

## 1. Readiness classification scale
- **Not present**: no implementation/interface evidence.
- **Present in source only**: code/docs exist but not wired/available.
- **Interface implemented**: callable/defined interface exists (may be stub/unwired).
- **Dependency/configuration available**: required runtime/config/endpoints/resources present.
- **Starts successfully**: component/process starts (observed or strong evidence).
- **Basic execution verified**: simple operation proven.
- **End-to-end verified**: full intended cross-component flow proven.
- **Reliability tested**: failures/retries/timeouts/restarts tested.
- **Security boundary verified**: authz/authn/permission/isolation boundary tested.

## 2. Integration readiness matrix

| Integration | Source | Interface | Dependency/config | Starts successfully | Basic execution | End-to-end | Reliability | Security boundary | Verdict | Key evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| **AJ ↔ JARVIS** | Present in source only (both sides) | Partial: AJ `HttpAgentAdapter` + `AgentRequest/Result`; JARVIS internal `agent_runtime`/`HelixManager` API | Partial/misaligned: AJ config points to JARVIS `127.0.0.1:8875` "bridge WS, no AJ task endpoint"; JARVIS exposes no agreed AJ endpoint | Unverified (JARVIS runtime/bridge not confirmed active for this contract) | No | No | No | No | **Not ready** | `aj/agents.py`, `aj/config.py` notes, `JARVIS/agent_runtime.py`, `HELIX_INTEGRATION.md` |
| **AJ ↔ HELIX** | Partial/ambiguous (AJ side present; HELIX canonical repo/path missing, helix copies diverged) | Not present for AJ (no agreed task API; helix bridge is UI↔Hermes/kanban oriented) | No/ambiguous (which helix runtime? endpoints/protocols differ from AJ expectation) | Unverified | No | No | No | No | **Not ready / blocked by ambiguity** | missing `AI_WORKSPACE/HELIX`, `AI_WORKSPACE/helix` vs `~/helix` symlink target divergence, `aj/agents.py`, helix `bridge/bridge_ws.py` |
| **AJ ↔ Hermes** | Present in source only (AJ port/contracts; Hermes runtime/src rich) | Partial: AJ `ExecutionPort`/`UnavailableExecutionAdapter`, `ExecutionRequest/Result`, `SkillSpec`; Hermes CLI/gateway/ACP/MCP/skills interfaces exist but no AJ adapter mapping | Yes (Hermes installed/configured; gateway observed running) | Hermes starts/runs: **Yes (observed)**; AJ↔Hermes adapter: No | Hermes independent basic operation likely/partial; **AJ-mediated execution: No** | No | No | No | **Not ready (promising dependency, missing adapter/contract/security mapping)** | `aj/execution.py`, `aj/contracts.py`, Hermes `hermes --help`, `gateway_state.json`, process list |
| **JARVIS ↔ HELIX** | Present in source only / conceptual | Internal JARVIS delegation layer exists (`HelixManager` fronts `AgentOrchestrator`); no verified external JARVIS↔standalone-helix service contract | Ambiguous (helix copies diverged; JARVIS also contains helix-derived bridge/ui elements) | Unverified | Unverified | No | No | No | **Not ready / ambiguous ownership** | `JARVIS/agent/helix_manager.py`, `JARVIS/agent_runtime.py`, `JARVIS/HELIX_INTEGRATION.md`, duplicate helix repos |

## 3. AJ integration compatibility details

### AJ ↔ JARVIS
| Question | Finding | Evidence |
|---|---|---|
| How JARVIS could submit a task to AJ | No implemented client/endpoint observed. AJ is CLI/Python-local API; JARVIS would need adapter calling AJ API/CLI or AJ would need inbound service contract (none present). | AJ CLI/runtime only; no JARVIS->AJ client code found |
| How AJ could return task IDs/status | AJ naturally returns task IDs/outcomes/inspection via CLI/API. | `aj/__main__.py`, orchestrator/task APIs |
| Progress/final results to JARVIS | No push/callback/channel contract implemented. Polling possible only if shared access/adapter defined. | no adapter/protocol |
| Cancellation/timeout/failure/recovery | AJ supports cancel/retry/recover/reconcile semantics internally; cross-system propagation undefined. | AJ task/recovery modules |
| Separation of JARVIS user context/memory from AJ execution state | Feasible by design (different stores/domains) but no enforced mapping/contract. | separate store implementations |
| User permission representation | AJ has levels/policy and reconcile guardrail; JARVIS has core policy/capabilities; no shared principal/permission envelope. | `aj/permissions.py`, `aj/authorization.py`, `JARVIS/core/policy.py` |
| JARVIS adapter/client to AJ | **Not found/verified.** | repo search/inspection |

### AJ ↔ HELIX
| Question | Finding | Evidence |
|---|---|---|
| Task submission path | Undefined. No canonical HELIX service/repo contract for AJ. | missing HELIX path, divergent helix copies |
| AJ coordination without taking HELIX identity | Requires explicit boundary/contract; currently no adapter. | AJ agent/execution ports unused for helix |
| Overlap with existing orchestration | Yes: JARVIS internal HelixManager/orchestrator and Hermes/kanban-oriented helix bridges indicate overlapping concepts. | JARVIS agent modules, helix docs/bridge |
| Parent/subtask ownership | Unassigned across systems. | no contract |
| Evidence/status flow | No mapping defined. | no integration code |
| Cancellation/recovery propagation | Undefined. | no integration code |
| Nested delegation loop/duplication risk | **High if wired naively** (multiple orchestrators/dispatchers: AJ scheduler/recovery, JARVIS orchestrator, Hermes kanban/gateway). | architecture inspection |

### AJ ↔ Hermes
| Question | Finding | Evidence |
|---|---|---|
| Real supported invocation interface for AJ | Hermes exposes CLI, gateway/ACP, MCP/tooling surfaces; **no AJ adapter implemented** to use any of them safely. | Hermes help/source, AJ `UnavailableExecutionAdapter` |
| Status/results reporting from Hermes | Possible in principle via Hermes session/task/gateway/CLI outputs; contract mapping to `ExecutionResult`/AJ evidence absent. | Hermes interfaces present; no adapter |
| Skill permission enforcement | Hermes has approvals/toolsets/profiles/config; enforcement in AJ-governed invocation path unverified. | Hermes config/toolsets, no AJ integration |
| Distinguish skill metadata vs execution evidence | AJ models support explicit results/evidence; mapping from Hermes runs not implemented. | AJ contracts/evidence stores |
| Timeouts/cancel/retry/partial execution handling | Hermes/gateway/tooling have mechanisms; AJ-compatible semantics undefined. | code/config both sides |
| Safe representation in AJ task lifecycle | Feasible with adapter and evidence mapping; currently not implemented. | AJ task/evidence model |
| Direct Hermes access bypassing AJ authz controls | **Possible in current ecosystem** (Hermes independently operable); AJ cannot enforce boundaries until integrated as choke point. | independent Hermes runtime |

### JARVIS ↔ HELIX
| Question | Finding | Evidence |
|---|---|---|
| Real delegation interface exists? | Internal in-process design exists in JARVIS (`agent_runtime` -> `HelixManager` -> `AgentOrchestrator`); external standalone HELIX delegation contract not verified. | `agent_runtime.py`, `helix_manager.py` |
| Routing/progress/completion | Implemented conceptually via callbacks/receipts/reports in JARVIS agent layer; operational E2E unverified. | source |
| Identity preservation | Separate naming/roles stated in docs/code intent; enforcement/UX/runtime separation unverified. | `HELIX_INTEGRATION.md`, manager code |
| Failure/timeout handling | Partial in orchestrator/manager patterns; external boundary behavior unknown. | source |
| Accidental duplicate execution | Possible given duplicate components/bridges and unclear canonical runtime. | duplicate helix copies, overlapping orchestrators |

## 4. Capability compatibility matrix (requested)

| Capability area | Existing implementation | Current owner | Proposed owner (integration target) | Required adapter/contract | Priority | Blockers |
|---|---|---|---|---|---:|---|
| AJ-orchestrated execution runtime | AJ execution port/contracts; Hermes runtime/tools/skills active | AJ port / Hermes runtime | AJ orchestrates, Hermes executes via adapter | `ExecutionPort` Hermes adapter, request/result/evidence mapping, timeout/cancel/idempotency | P1 | No adapter; permission mapping; security boundary; Hermes interface selection |
| JARVIS task submission to AJ | AJ task APIs; no JARVIS client | AJ (task system) / JARVIS (requester) | JARVIS submits, AJ records/coordinates | Versioned submit/status/result contract + client/server or local adapter | P2 | Missing contract/endpoint; identity propagation; ownership decisions |
| HELIX delegated complex work | helix/Hermes-kanban bridges, JARVIS HelixManager concepts, divergent copies | Ambiguous | HELIX executes delegated work; AJ coordinates if/when adopted | Canonical HELIX definition + delegation/evidence contract | P3 | Canonical target ambiguity; overlap with Hermes/JARVIS orchestrators |
| Cross-system evidence correlation | AJ strong evidence stores; Hermes/JARVIS local logs/state | Local per system | AJ canonical for AJ-orchestrated flows; others emit correlated evidence | Correlation schema (`task_id`, `operation_id`, external IDs, provenance) | P1 | No shared schema/emitters |
| Unified authz/identity propagation | AJ local-trust guardrail; JARVIS policy; Hermes approvals/profiles | Local per system | Explicit per-boundary trust model (no fake auth) | Principal/permission envelope, trusted channel/provider decision | P1 | No trusted identity provider/boundary; risk of bypass/forgery assumptions |
| Memory ownership/provenance links | Fragmented stores (AJ/JARVIS/Hermes/Obsidian) | Local/domain-specific | Domain-canonical with link records only | Provenance/link contract, no canonical merge | P2 | Conflicting stores, unclear canonical sources, backup/restore gaps |