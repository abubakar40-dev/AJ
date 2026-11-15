# 09 — Architectural Decisions and Open Questions

**Workstream consolidation (Phase 4B.0).** Clear separation of approved direction, evidence-based recommendations, provisional designs, decisions requiring user approval, and deferred ideas.

## 1. Existing approved direction (preserve)
| Item | Basis | Implication |
|---|---|---|
| AJ as AJ-governed control plane; JARVIS/HELIX/Hermes keep independent identities and responsibilities | Governing mission, prior architecture, 4A/3F docs | No role collapse; AJ coordinates only AJ-governed execution |
| AJ `ExecutionPort`/contracts boundary; Hermes attached only with explicit approval/signal and real adapter | `aj/execution.py`, `tests/test_hermes_contract.py` ("NOT ATTACHED", GREEN SIGNAL) | 4B.1 must be explicit, bounded, approved |
| Fail-closed authorization, evidence-before/with control actions, honest status semantics | AJ 3A–3F implementation/evidence | No invented success/IDs/auth |
| `local_trust` is non-authenticated assumption; no caller-metadata promotion | `aj/authorization.py`, 3F audit | Identity claims must remain honest |
| Domain-specific canonical data ownership; Obsidian as projection | 4A/ownership analysis | No memory merges/unification |
| No destructive ops, no live integration in 4B.0, preserve all existing work | Phase 4B.0 constraints (satisfied) | Safe design lock only |

## 2. Evidence-based recommendations
| ID | Recommendation | Evidence | Risk/trade-off | Confidence |
|---|---|---|---|---|
| R-01 | Treat `AI_WORKSPACE/helix` (clean, 3 commits ahead) as authoritative **development candidate**; preserve Drive dirty copy as runtime-linked/uncommitted variant pending reconciliation | `01` (ancestry, commit delta, mixed active refs) | May miss unique uncommitted B work if ignored; B may be active via `~/helix` | Med-High (history), Med (active use) |
| R-02 | Use **Hermes CLI subprocess** as preferred v0 integration interface | `02` (boundary clarity, observability, lower coupling/complexity vs ACP/gateway RPC/AIAgent) | Weaker native structured IDs/idempotency/cancel than internal protocols | Med-High (choice), Med (command semantics) |
| R-03 | First capability **`hermes.status.read`** (read-only, bounded, no side effects) | `04/08`, Hermes gateway running, need safe adapter validation | Requires command-level verification; limited functional value (intentional) | High (safety fit), Med (exact command) |
| R-04 | Default-disabled, feature-flagged, single-allowlist-entry adapter with injectable CLI runner | `08`, AJ port/config patterns | Slower to broaden capability; safer rollout | High |
| R-05 | Keep AJ/Hermes/JARVIS/HELIX stores separate with correlation/provenance references only | `05`, 4A memory findings | More mapping work; avoids corruption/ownership collapse | High |
| R-06 | Block 4B.1 if chosen command/interface cannot satisfy bounded observability/idempotency/safety requirements | `02/08` | Delays integration; prevents unsafe guesswork | High |

## 3. Provisional designs (subject to implementation verification and approval)
| ID | Design | Notes |
|---|---|---|
| P-01 | Contract `aj.hermes.execution.v0` schemas/status/id/error/failure semantics | `03`; field names/serialization may align with AJ conventions at implementation |
| P-02 | Allowlist/policy object model and bounds (timeout/output/argv templates/env) | `04/08`; exact config schema to fit `aj.config` patterns |
| P-03 | Adapter module split (`hermes_adapter`/`hermes_contract` helpers) | `08`; may be consolidated if AJ style prefers |
| P-04 | Status mapping to existing `ExecutionResult.status` vs extended internal states | `03/08`; must remain honest and backward-compatible where possible |
| P-05 | Read-only retry policy (conservative, no retry on unknown) | `03/06/08` |
| P-06 | ACP/gateway RPC as future alternative if CLI insufficient | `02` |

## 4. Decisions requiring user approval (blocking or gating)

| ID | Decision | Options | Recommendation | Impact if unresolved |
|---|---|---|---|---|
| D-01 | **Canonical HELIX stance for future work** | (A) `AI_WORKSPACE/helix` dev-candidate + preserve/reconcile Drive copy; (B) Drive copy authoritative; (C) defer with explicit dual-target ambiguity; no consolidation now in all cases | **A** with preservation of B and no moves/merges | Continued misrouting/drift risk; blocks confident HELIX integration planning |
| D-02 | **Approved Hermes interface for 4B.1** | CLI subprocess (preferred), ACP/gateway projection, gateway RPC, block | **CLI subprocess** for read-only v0, with re-evaluation gate | Wrong boundary choice increases coupling/security risk; block if unsafe |
| D-03 | **First capability and exact command** | `hermes.status.read` with verified read-only CLI command; or block/no suitable capability | Approve capability class now; approve exact command after 4B.1 preflight evidence | Cannot safely validate adapter without bounded non-mutating target |
| D-04 | **Identity/trust scope for 4B.1** | Proceed under `local_trust` (single trusted local operator, non-auth, no remote/untrusted multi-user); or require verified identity mechanism first | Accept `local_trust` scope **only** with documented constraints and disabled remote exposure | Misrepresented security if assumed authenticated; implementation blocked if strong auth required now |
| D-05 | **Enablement policy** | Keep default-disabled until explicit enable + preflight; any earlier enablement forbidden | Default-disabled, explicit approval gate | Accidental exposure/bypass risk |
| D-06 | **Future widening** | Any capability beyond `hermes.status.read` requires separate design/approval | Require separate review | Scope creep into unsafe side effects |

## 5. Open questions (need evidence or decision)
| ID | Question | Why it matters | How to resolve |
|---|---|---|---|
| Q-01 | Which exact Hermes CLI command provides stable, read-only, bounded status suitable for `hermes.status.read` without side effects? | Determines feasibility/safety of v0 spike | 4B.1 preflight: inspect help/behavior, verify non-mutation, capture output contract, run in controlled read-only manner |
| Q-02 | Does selected command expose stable Hermes-native execution/session identifiers? | Correlation completeness | Command-level verification; if absent, contract uses null + evidence |
| Q-03 | Are any uncommitted changes in Drive helix copy unique/required vs AI_WS commits? | Data-loss risk, canonical decision | User/maintainer review and diff reconciliation (separately approved) |
| Q-04 | Which active runtime paths (systemd/`~/helix`/desktop launchers) are authoritative in practice for each HELIX function? | Operational correctness | Controlled runtime audit with user approval |
| Q-05 | Is a verified identity/auth propagation mechanism required before any cross-component integration, or is `local_trust` local-only sufficient for v0? | Security posture/go/no-go | User/architecture decision (D-04) |
| Q-06 | Can CLI boundary provide sufficient cooperative cancellation semantics for future (non-v0) capabilities? | Lifecycle richness | Reassess in future phase; may motivate ACP/gateway RPC |

## 6. Deferred ideas (not in 4B.1)
- Live Hermes adapter for mutating/skill/tool/MCP execution.
- AJ↔JARVIS and AJ↔HELIX live task delegation wiring.
- JARVIS↔HELIX externalization/refactor and orchestration deduplication.
- ACP/gateway RPC adapter implementation (unless promoted by approved decision).
- Cross-component memory unification, Obsidian canonicalization, Honcho integration.
- Authenticated identity provider/remote-safe multi-user boundary.
- Repository consolidation/cutover, service reconfiguration, provider/model live verification/expansion.

## 7. Go/No-Go summary for 4B.1
- **Go (conditional):** approvals D-02/D-03/D-04/D-05 accepted; D-01 stance recorded; Q-01 resolved with verified safe command; blueprint `08` constraints enforced.
- **No-Go (block):** no verified safe read-only command, no interface approval, requirement for strong auth before local-only v0 not satisfied, or pressure to widen scope/enable side-effecting capabilities.
