# 00 — Phase 4B.0 Master Design Report

**Phase:** 4B.0 Design Lock, Integration Contracts & Architectural Prerequisites  
**Date:** 2026-11-13 (additive design/specification only; no live adapter implementation)  
**Scope:** AJ, JARVIS, `AI_WORKSPACE/helix`, `/run/media/abubakargcx/My Drive/hermes/helix`, `~/.hermes`, `~/.hermes/hermes-agent`

## 1. Objective and boundary (governing)
- **Objective:** remove architectural ambiguity and prepare a safe, testable, contract-first foundation for a future minimal AJ↔Hermes integration (Phase 4B.1), without implementing live integration now.
- **Role boundaries preserved:** AJ = AJ-governed control plane (lifecycle/state, authorization, correlation/coordination, durable evidence/audit, recovery/reconciliation, adapters/contracts). JARVIS = primary personal assistant (interaction, personal memory/continuity, routine workflows, delegation decisions, user-facing delivery). HELIX = independent advanced execution manager (complex/multi-step delegated work, own identity, directly accessible). Hermes = execution runtime (tools/skills/MCP/platforms/sessions/gateway/workers), never unrestricted authority for AJ. AJ coordinates AJ-governed execution only; independent identities and domain-specific data ownership preserved.
- **Safety/scope compliance:** read-only inspection plus additive design documentation only. No live Hermes adapter, no existing application source/config/env/test/db modification, no service changes, no installs/removals, no repo moves/renames/deletes/merges, no active HELIX installation change, no JARVIS/HELIX/Hermes app code modification, no Git staging/commit/push/merge/tag/reset/rewrite/destructive commands, no Docker/Honcho, no paid API calls, no secret exposure. All pre-existing modifications/untracked files preserved.

## 2. Phase 4A findings — revalidated (actual state)

| Prior 4A finding | Revalidation (evidence) | Status |
|---|---|---|
| Workspace present; `AJ/`, `JARVIS/` present; `AI_WORKSPACE/HELIX/` (capitalized) missing | `ls AI_WORKSPACE` shows `AJ`, `JARVIS`, `helix` (lowercase) only; no `HELIX/` | **Confirmed** |
| AJ 433 passed, 13 warnings, `aj --check` 23/23 (3F baseline) | Recorded in `AJ/ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/04_TEST_AND_REGRESSION_RESULTS.md`; 4A reported same; not re-run in 4B.0 (no test/runtime mutation) | **Confirmed as recorded evidence (not re-executed)** |
| AJ has execution ports/contracts but no verified live Hermes adapter | `aj/execution.py`: `ExecutionPort` + `UnavailableExecutionAdapter` (`"integration_status": "NOT ATTACHED"`, requires HERMES GREEN SIGNAL), `execute()` refuses unavailable; `aj/runtime.py` assembles `UnavailableExecutionAdapter`; `tests/test_hermes_contract.py` exercises contract-only test doubles | **Confirmed** |
| Hermes gateway observed running and connected | `~/.hermes/gateway_state.json`: `"gateway_state":"running"`, pid `5397`, `kind` hermes-gateway, platforms whatsapp connected, `updated_at` 2026-11-13T18:18:24Z, `code_sha=2bd378ed...`, `code_version=0.23.0`; `gateway.pid`/`gateway.sock` present; `ps` shows `hermes gateway run`, whatsapp bridge, supervisor processes | **Confirmed (observed active runtime)** |
| Two HELIX repository copies exist with different Git states | `AI_WORKSPACE/helix`: branch `audit/consolidation-2026-11-06`, HEAD `99c7a383...`, clean. `/run/media/abubakargcx/My Drive/hermes/helix` (`~/helix` symlink): branch `main`, HEAD `e8a64cf...`, dirty (tracked mods/deletions + untracked). Same remote `https://github.com/abubakar40-dev/helix.git`. `e8a64cf` is ancestor of `99c7a38` in AI_WS history; AI_WS has 3 commits ahead (`c68326b`, `07a2522`, `99c7a38`) | **Confirmed** |
| JARVIS has its own orchestration and HELIX delegation logic | `JARVIS/agent_runtime.py`, `agent/helix_manager.py`, `agent/orchestrator.py`, `HELIX_INTEGRATION.md` present; `core/capabilities.py`/`core/policy.py` exist | **Confirmed** |
| Cross-component authenticated identity not established | AJ 3F: `local_trust` explicit non-authenticated assumption, no verified identity provider by default (`aj/authorization.py`, 3F docs); no cross-component principal/permission envelope in interfaces inspected | **Confirmed** |

## 3. Exact Git states (all inspected repositories, preserved)

| Repository | Branch | HEAD | Working tree (preserved) |
|---|---|---|---|
| `AI_WORKSPACE/AJ` | `main` (ahead 1 of `origin/main`) | `468fdcebece5b25f02e53add4928d3650ef175f4` | Pre-existing tracked modified: `aj/__main__.py`, `aj/diagnostics.py`, `aj/orchestrator.py`, `aj/recovery.py`, `aj/task.py`, `aj/transfer.py`, `tests/test_foundation.py`, `tests/test_orchestrator.py`, `tests/test_path_config_hardening.py`, `tests/test_phase2.py`, `tests/test_phase3.py`, `tests/test_step_c_gap_closure.py`. Pre-existing untracked: `aj/authorization.py`, `aj/consistency.py`, `aj/operation_evidence.py`, `aj/storage_diagnostics.py`, `integrations/`, `ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/`, `tests/test_audit_reliability_security.py`, `tests/test_phase3_lifecycle_reliability.py`, `tests/test_phase3c_recovery_integrity.py`, `tests/test_phase3d_recovery_observability.py`, `tests/test_phase3e_evidence_consistency.py`, `tests/test_phase3f_identity_trust_boundary.py`, `tests/test_task_creation_import_integrity.py`, `tests/test_task_persistence_fail_closed.py`. **Additive this phase:** `ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/` only. |
| `AI_WORKSPACE/JARVIS` | `audit/consolidation-2026-11-06` | `d93c7027cd509c75eb6414d822017d320a8a06c2` | Untracked: `chat_history/2026-11-04.md`, `chat_history/2026-11-05.md` |
| `AI_WORKSPACE/helix` | `audit/consolidation-2026-11-06` | `99c7a3834fc5994fce9aae6964104d47fb74bd74` | Clean |
| `/run/media/abubakargcx/My Drive/hermes/helix` (`~/helix`) | `main` (tracks `origin/main`) | `e8a64cf1269b857a0b86fc9f4899bccad4f47cf0` | Tracked `M .gitignore, bridge/README.md, docs/PROGRESS.md, docs/VOICE_AUDIO_DIAGNOSTIC.md, tools/selfcheck.py`; tracked deletions `D bridge/server.py, deploy/helix-gesture.service, tools/{audit-geometry,check-aec,check-app,check-gesture,check-globe-patch,check-orb,check-talkover,diagnose-voice,gesture,helix_app,measure-layout,probe-town}.py, ui/{agent-town/index.html,console/{index.html,orbScene.js,town.js},shell/index.html,voice-core/{README.md,index.html},world-monitor/index.html}`; untracked `?? bridge/{bridge_ws.py,helix.desktop,helix_desktop.py}, docs/{ADD_AN_AGENT.md,AGENT_ARCHITECTURE.md,PACKAGING_PLAN.md}, install.sh, tools/lms_client.py, ui/{build.js,helix-ui.html,node_modules/,package-lock.json,package.json,src/}, uninstall.sh` |
| `~/.hermes/hermes-agent` | detached `HEAD` | `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19` | Clean |

## 4. Workstream outcomes (summary)

| Workstream | Outcome | Classification | Doc |
|---|---|---|---|
| A — HELIX canonical decision | Side-by-side comparison completed; AI_WS copy is committed successor of Drive HEAD (3 ahead) while Drive copy is dirty working/runtime-linked variant with overlapping intent; active references mixed (`~/helix`→Drive, systemd services→AI_WS paths). No consolidation performed. | Evidence-based recommendation + **decision requiring user approval** | `01` |
| B — Hermes integration boundary | Candidates compared (CLI, ACP/gateway projection, gateway RPC/WebSocket client, direct `AIAgent` Python import, kanban/task flows). Preferred first interface: **Hermes CLI subprocess (`hermes ...`) with strict bounded invocation contract** for v0 spike, subject to contract/testability constraints; alternatives documented. ACP/gateway RPC stronger for rich lifecycle but higher coupling/risk for first spike. | Evidence-based recommendation (provisional design); blocked if selected command cannot provide required observability/idempotency without runtime mutation risk | `02` |
| C — AJ↔Hermes contract | Versioned `aj.hermes.execution.v0` request/response/status/id mapping/failure semantics specified (additive spec). | Provisional design / evidence-based | `03` |
| D — Security/permission/identity | Deny-by-default allowlist design, narrow first capability (`hermes.status.read` — read-only runtime status probe), honest `local_trust` non-auth boundary, no promoted caller metadata. | Provisional design; identity provider **open decision** | `04` |
| E — Memory/data ownership | Domain ownership and cross-component reference/provenance/correlation rules specified; no store migration/unification. | Evidence-based recommendation | `05` |
| F — Lifecycle/failure/recovery | 12-step AJ↔Hermes lifecycle with ownership, durable evidence, retry/cancel/timeout/recovery/manual disposition, respecting AJ limits. | Provisional design | `06` |
| G — Contract test strategy | Future test matrix and isolated additive fixture/test guidance defined; no existing tests modified. Existing `tests/test_hermes_contract.py` already covers ExecutionPort/SkillRegistry contract doubles. | Provisional design (limited addable coverage before interface approval) | `07` |
| H — Phase 4B.1 blueprint | Exact module boundaries, feature flag, default-disabled behavior, evidence flow, tests, rollback, acceptance criteria for minimal adapter. | Evidence-based recommendation / provisional | `08` |
| Decisions/open questions | Canonical HELIX, Hermes interface approval, first capability approval, identity/auth strategy, idempotency/command contract confirmation. | **Requires user approval / open** | `09` |

## 5. Final recommendation (master)

### Is Phase 4B.1 safe to begin?
**Conditionally yes — for design-approved, tightly bounded implementation preparation only — not automatically.** Safe to begin **only if**: (1) user approves canonical HELIX handling stance for this effort (no consolidation required now, but target ambiguity acknowledged), (2) user approves preferred Hermes interface (**CLI subprocess boundary, bounded/read-only first command**) or selects alternative with equivalent evidence, (3) user approves first capability `hermes.status.read` (read-only, non-destructive, no external side effects), (4) integration remains feature-flagged, default-disabled, deny-by-default, `local_trust` single-operator/non-auth and non-remote as specified, and (5) 4B.1 implements only the blueprint scope with full contract/fault/security/regression tests. **If these approvals/constraints are not met, Phase 4B.1 should be blocked.**

### What exact interface should be used?
**Preferred (evidence-based): Hermes CLI subprocess interface** invoked by a future AJ `HermesExecutionAdapter` under strict allowlist/argument schema/timeout/output-capture/redaction, using a bounded read-only command for the first spike (see `02`, `04`, `08`). Rationale: stable operator-facing boundary, local/process isolation relative to in-process imports, observable exit/status/text outputs, minimal protocol coupling for v0. Alternatives: ACP/gateway projection or gateway RPC (richer lifecycle/IDs but higher internal coupling/complexity), direct Python `AIAgent` import (too coupled/unstable), kanban dispatch (side-effectful async workflow, unsuitable for minimal safe first capability). **Residual limitation:** CLI may not natively provide Hermes execution/session IDs or cooperative cancel/idempotency semantics for arbitrary commands — contract must represent unknown/unsupported honestly and first capability must be chosen to avoid unsafe retries/side effects.

### What exact capability should be integrated first?
**`hermes.status.read`** (proposed AJ-facing capability id) mapped to a **read-only Hermes runtime status query** via approved CLI boundary (e.g. gateway/status-equivalent command selected in 4B.1 after command-level verification) with no mutations, no tool/skill execution, no messaging/browser/filesystem side effects, bounded timeout and output size. Purpose: validate adapter wiring, correlation, evidence capture, timeout/error classification, and fail-closed behavior safely. (See `04`, `08`.)

### What decisions still require user approval?
1. **Canonical HELIX stance:** adopt `AI_WORKSPACE/helix` (committed, ahead, clean) as authoritative *development* reference for future work vs Drive dirty copy linked by `~/helix`, and approve that no consolidation/migration occurs until a separate approved plan (high data-loss risk). 
2. **Preferred Hermes interface approval:** CLI subprocess for v0 spike (or explicit selection of ACP/gateway RPC alternative).
3. **First capability approval:** `hermes.status.read` read-only status probe and exact command mapping once verified.
4. **Identity/auth scope:** accept documented `local_trust` single-operator, non-authenticated, local-only boundary for 4B.1, or require a verified identity mechanism before implementation (would block/delay).
5. **Any permission widening** beyond read-only status capability (all remain disabled by default).

### What risks remain?
- HELIX canonical/active-target ambiguity and divergent dirty copy (`~/helix`→Drive) can misroute future work.
- Hermes CLI may lack stable structured IDs/idempotency/cancel for some operations; unknown outcomes must remain unknown.
- Hermes gateway/runtime is independently operable (AJ cannot globally mediate direct use) — residual bypass outside AJ-governed path.
- Cross-component authenticated identity unresolved (`local_trust` non-auth).
- AJ non-atomic multi-store writes / no exactly-once external side effects (existing, unchanged).
- Provider/skill/tool safety and prompt-injection/untrusted-output risks if scope widens.
- Environment/path coupling (e.g. hermes home/bin assumptions) and unverified restore/operational hardening outside AJ.

### What must explicitly remain disabled?
- Live Hermes adapter/integration by default (`feature_flags.hermes_skills`/execution integration remains off until explicitly enabled and approved).
- All capabilities/tools/skills except the single approved read-only `hermes.status.read` allowlisted entry.
- Unrestricted shell, arbitrary Python execution, filesystem-wide access, browser automation, messaging/platform actions, financial/account operations, arbitrary MCP servers, unreviewed skills, and any external side-effecting or mutating commands.
- Remote/untrusted multi-user exposure, authenticated-identity claims, automatic retries without proven idempotency/side-effect safety, and any JARVIS/HELIX live wiring or memory migration/unification.
- Any repository consolidation, service/runtime reconfiguration, or application/config/test mutation outside separately approved 4B.1 implementation scope.

## 6. Evidence, confidence, and labels
- **High confidence (inspected):** Git states/ancestry, AJ execution port/contracts and `tests/test_hermes_contract.py`, Hermes gateway running state/pid/sock/processes, helix file/commit divergence and active path references, existence of Hermes CLI/ACP/gateway source surfaces.
- **Medium confidence:** operational suitability of specific CLI command for structured correlation/idempotency/cancel without side effects (requires command-level verification in 4B.1 preflight) — treated as **provisional**.
- **Labels used throughout package:** `Existing approved direction`, `Evidence-based recommendation`, `Provisional design`, `Decision requiring user approval`, `Deferred idea`.
