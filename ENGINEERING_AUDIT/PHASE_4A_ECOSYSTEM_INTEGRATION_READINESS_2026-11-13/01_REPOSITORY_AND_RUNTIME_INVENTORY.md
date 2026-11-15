# 01 — Repository and Runtime Inventory

## 1. Workspace verification (actual)
| Item | Observed | Evidence |
|---|---|---|
| Workspace mount/path | Present and accessible | `ls /run/media/abubakargcx/My Drive/AI_WORKSPACE` succeeded; contains `AJ/`, `JARVIS/`, `helix/` (lowercase), `ENGINEERING_AUDIT/`, etc. |
| Expected `AJ/` | Present | `AI_WORKSPACE/AJ` exists, git repo |
| Expected `JARVIS/` | Present | `AI_WORKSPACE/JARVIS` exists, git repo |
| Expected `HELIX/` (capitalized) | **Missing** | `ls AI_WORKSPACE/HELIX` → not found |
| Hermes runtime `~/.hermes` | Present | `~/.hermes` populated (config, state dbs, gateway pid/sock/state, `hermes-agent/` src) |
| Hermes source/runtime locations | `~/.hermes/hermes-agent`, `~/.local/state/hermes` | `find ~ -maxdepth 2 -iname "*hermes*"`; `~/.config/Hermes` present |
| Duplicate/legacy candidates | `AI_WORKSPACE/helix`, `/run/media/abubakargcx/My Drive/hermes/helix`, `~/helix` symlink → Drive copy, `AI_WORKSPACE/honcho_local` | `find ... helix` results; `ls -la ~/helix` |

## 2. AJ (`AI_WORKSPACE/AJ`)

| Field | Actual state | Evidence / confidence |
|---|---|---|
| Root | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ` | `git rev-parse --show-toplevel` |
| Git | `main`, HEAD `468fdcebece5b25f02e53add4928d3650ef175f4` (`AJ: harden runtime path configuration`), ahead of `origin/main` by 1 | `git status --short --branch`, `git log -1` |
| Tracked modifications (preserved) | `aj/__main__.py`, `aj/diagnostics.py`, `aj/orchestrator.py`, `aj/recovery.py`, `aj/task.py`, `aj/transfer.py`, `tests/test_foundation.py`, `tests/test_orchestrator.py`, `tests/test_path_config_hardening.py`, `tests/test_phase2.py`, `tests/test_phase3.py`, `tests/test_step_c_gap_closure.py` | `git status` (High) |
| Untracked (preserved/additive) | `aj/authorization.py`, `aj/consistency.py`, `aj/operation_evidence.py`, `aj/storage_diagnostics.py`, `integrations/`, `ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/`, multiple `tests/test_*` files | `git status` (High) |
| Entry points | `python -m aj` / `aj.__main__` (CLI: run/tasks/task/cancel/retry/audit/memory/summary/capabilities/permissions/config/diagnostics/consistency/export/import/backup/recover/reconcile/orb/inbox); `aj.runtime.assemble/build`; `aj.orchestrator.Aj` | `aj/__main__.py`, `README.md` (High) |
| Core modules/layers | Config/runtime/CLI, task store/lifecycle/locking/leases, audit/journal/receipts/operation evidence/idempotency, recovery/inspection/reconciliation/consistency, permissions/authorization, capability registry/contracts, agents/execution/calling/providers adapters, memory/summary, diagnostics/storage diagnostics/transfer, scheduler/retention helpers, inbox/orb subsystems | `aj/*.py`, prior 3E/3F audit docs (High) |
| Config | `config/aj.config.json` (non-secret defaults), layered loader `aj.config` (defaults < file < env < overrides), `config/capabilities.json` | file inspection (High) |
| Dependencies | Stdlib-first; `pyproject.toml` minimal (pytest dev in practice per README); POSIX-oriented file locking/SQLite usage | `pyproject.toml`, `README.md` (Medium-High) |
| Runtime/env | Local CLI/process; stores under configured data dirs (e.g. `~/.local/share/aj` defaults); no daemon by default | `aj/config.py`, `README.md` (High) |
| Tests | 35+ test files; Phase 3F reported **433 passed, 13 warnings, 0 failed**, `aj --check` 23/23 | `ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/04_TEST_AND_REGRESSION_RESULTS.md` (High, recorded evidence; not re-run in 4A) |
| Logging/errors | `aj.errors` normalized codes, audit/journal/receipts/CLI diagnostics; logging configured in runtime | source inspection (High) |
| Persistence | Append-only TaskStore JSONL, audit monthly JSONL, journal/receipts/leases/op-evidence files, SQLite memory (`memory.sqlite3` WAL), idempotency JSON; inbox separate SQLite/artifacts | `aj/task.py`, `aj/audit.py`, `aj/memory.py`, `aj/operation_evidence.py`, etc. (High) |
| APIs/integrations | CLI primary; internal Python APIs; `HttpAgentAdapter` to JARVIS/HELIX (no agreed transport) ; `ExecutionPort`/`UnavailableExecutionAdapter` (Hermes not attached); provider gateway abstractions without live transport by default | `aj/agents.py`, `aj/execution.py`, `aj/providers.py`, config (High) |
| Background/services | No core daemon; scheduler/retention helpers exist but not primary integrated service; optional orb/inbox worker artifacts | source/config (Medium) |
| Docs | `README.md`, `docs/01-10`, engineering audit packages; generally explicit about limits (Hermes not attached, no live provider, local trust not auth) | docs review (High) |
| Known gaps | Non-atomic multi-store writes, no authenticated operator identity by default, process-local guarantees, external integrations unattached/unverified | Phase 3F audit (High) |

## 3. JARVIS (`AI_WORKSPACE/JARVIS`)

| Field | Actual state | Evidence / confidence |
|---|---|---|
| Root | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/JARVIS` | git toplevel |
| Git | Branch `audit/consolidation-2026-11-06`, HEAD `d93c7027cd509c75eb6414d822017d320a8a06c2`; untracked `chat_history/2026-11-04.md`, `chat_history/2026-11-05.md` only | `git status` (High) |
| Main entry points | `main.py`, `bridge_ws.py`, `jarvis_desktop.py`, `agent_runtime.py`, `ui.py`/desktop UI components, various clients/controllers | file listing (High) |
| Core modules/layers | `core/` (capabilities, policy, audit, confirmation, voice, prompt), `agent/` (base, orchestrator, planner/supervisor, helix_manager, specialized agents), `actions/`, `memory/`, `config/`, `tools/` integration helpers, `obsidian_integration.py`, `workspace_store.py`, `chat_history_manager.py` | source tree (High) |
| Config | `config/api_keys.json` (presence; not read for secrets), `config/app_settings.json`, workspace sqlite, browser profile artifacts | listing (Medium-High) |
| Dependencies | `requirements.txt` (Windows/desktop-heavy: PyQt6, google-genai, playwright, pyautogui, discord, fastapi/uvicorn, etc.), no `pyproject.toml` | file inspection (High) |
| Runtime/env | Designed as desktop assistant (voice/UI/automation); bridge/desktop scripts present; active runtime state not fully verified in 4A | code/docs (Medium) |
| Tests | `tests/` with ~30+ test modules/pyc artifacts present (e.g. `test_agent_runtime.py`, `test_core_policy.py`, `test_desktop_input.py`, `test_screen_capture*.py`, `test_helix_manager.py`) | listing (High for presence; execution not rerun) |
| Logging/errors | `error_logger.py`, core audit/policy modules; UI/bridge logging patterns in code | source inspection (Medium) |
| Persistence/storage | `memory/personal_memory.sqlite3` + memory manager/db, `config/workspace_store.sqlite3`, `chat_history/*.md`, Obsidian vault integration (`~/.obsidian-vault` targeted), browser profile data | source/listing (High) |
| APIs/boundaries | Internal Python agent runtime API (`agent_runtime.submit/task_status/cancel`, `HelixManager`), `bridge_ws.py` WebSocket/HTTP UI bridge (talks to Hermes/kanban paths per code), no documented AJ task endpoint | `agent_runtime.py`, `agent/helix_manager.py`, `bridge_ws.py` (High) |
| Integrations | Gemini/OpenRouter/groq clients, browser/desktop automation, LMS tools, discord/whatsapp/telegram-related deps/files in tree, Obsidian, Helix manager delegation concepts | code/deps (Medium; operational status unverified) |
| Background/workers | Agent orchestrator worker thread, bridge server loops, desktop app patterns | source (Medium) |
| Docs | Rich but mixed/dated (`README.md`, `AGENTS.md`, `HELIX_INTEGRATION.md`, `docs/*`, progress notes); contains historical claims needing verification | docs review (Medium) |
| Notable issues | Windows-oriented README/deps vs Linux workspace; audit branch not mainline; duplicated/legacy UI bridges concepts with helix; `chat_history` untracked files | inspection (High) |

## 4. HELIX (expected) and actual `helix` copies

| Field | Actual state | Evidence / confidence |
|---|---|---|
| `AI_WORKSPACE/HELIX` (capitalized) | **Not present** | `ls` missing (High) |
| `AI_WORKSPACE/helix` (lowercase) | Present git repo, branch `audit/consolidation-2026-11-06`, HEAD `99c7a3834fc5994fce9aae6964104d47fb74bd74`, clean working tree | `git status` (High) |
| `~/helix` | Symlink to `/run/media/abubakargcx/My Drive/hermes/helix` | `ls -la ~/helix` (High) |
| `/run/media/abubakargcx/My Drive/hermes/helix` | Git repo, branch `main...origin/main`, HEAD `e8a64cf...` (short), **modified tracked files and untracked files** (bridge/UI/tools/docs changes/deletions/additions) | `git status`, `git diff --name-only` (High) |
| Divergence | AI_WORKSPACE copy and Drive/~/helix target are **different commits/states** (99c7a38 vs e8a64cf, different dirty state) | compare heads/status (High) |
| Entry points (both copies, similar intent) | `bridge/bridge_ws.py`, `bridge/helix_desktop.py`, `install.sh`, UI assets (`ui/`), tools under `tools/` | listings (High) |
| Architecture focus | Hermes/Kanban/profile-driven multi-agent desktop UI/bridge; reads `~/.hermes/kanban.db`/state, invokes `hermes` CLI/kanban flows per code/docs | `bridge/bridge_ws.py`, `docs/AGENT_ARCHITECTURE.md`, `docs/HELIX_BUILD_SPEC.md` (High) |
| Dependencies/runtime | Python stdlib-heavy bridge (GTK/WebKit for desktop), relies on local Hermes installation/DB/bin paths (`/home/abubakargcx/.local/bin/hermes`) | code inspection (Medium-High) |
| Tests | No obvious test suite found in AI_WORKSPACE copy | `find` (Medium) |
| Docs | `docs/PROGRESS.md`, `AGENT_ARCHITECTURE.md`, `HELIX_BUILD_SPEC.md`, `bridge/README.md` present (AI_WORKSPACE copy has no top-level README) | listings (High) |
| Integration posture | No evidence of AJ-facing task API/adapter; acts as UI/bridge over Hermes/kanban rather than AJ-orchestrated service | inspection (Medium-High) |

## 5. Hermes (`~/.hermes`, `~/.hermes/hermes-agent`)

| Field | Actual state | Evidence / confidence |
|---|---|---|
| Runtime home | `~/.hermes` exists with config/state/dbs/sessions/skills/plugins/cache/gateway files | listing (High) |
| Source/agent root | `~/.hermes/hermes-agent` git checkout, **detached HEAD** at `2bd378ed1b`, version signals include `0.23.0` in gateway state and pyproject `0.0.0` metadata context | git/state/pyproject (High) |
| Gateway/runtime status | **Running (observed):** `gateway run` process (pid ~5397 at inspection), whatsapp bridge node process, supervisor shell; `gateway_state.json` shows `"gateway_state":"running"`, platform whatsapp connected, updated recently (`2026-11-13T17:47:22Z` at read), `code_sha` matches checkout | `ps aux`, `gateway_state.json`, pid/sock files (High for observed moment) |
| Entry points/interfaces | `hermes` CLI (rich subcommands incl. `gateway`, `kanban`, `cron`, `skills`, `tools`, `mcp`-related workflows implied), `run_agent.py`/agent runtime, ACP/gateway adapter (`acp_adapter/gateway_server.py`, gateway commands/protocol modules), messaging platform integrations | `hermes --help`, source tree (High) |
| Config | `~/.hermes/config.yaml` (large; redacted view shows model/provider, toolsets, platforms, gateway/compression/memory/agent settings, whatsapp enabled/home channel metadata), `.env` exists (not read), `auth.json` present | inspection (High for presence/structure) |
| Skills/tools | Bundled/categorized skills in source (`skills/*`) and home skills dirs; toolsets system (`toolsets.py`), MCP-related code/tests extensive | listings/grep (High) |
| Persistence | `state.db`/related DBs implied, `kanban.db`, session stores, memories, cron/jobs, gateway/session state, caches, logs; SQLite WAL files present for some DBs | `~/.hermes` listing (High) |
| Tests/docs | Very large test corpus in source (`~7600` python test files reported by `find tests -name "*.py" | wc -l`), README and docs content present in repo; no `docs/` dir at top-level listing point checked | counts/listings (High for count) |
| Operational distinctions | Installation/runtime/source present and gateway active; per-skill/tool execution correctness, permission enforcement in AJ context, and AJ integration behavior **not verified** | evidence basis (High) |

## 6. Cross-cutting inventory findings
- **Canonical HELIX target unclear:** capitalized repo missing; two diverged helix implementations exist (one likely active via `~/helix` symlink).
- **Hermes is independently active:** integration readiness depends on contract/adapter/security mapping, not on Hermes installation alone.
- **JARVIS contains overlapping orchestration/memory/UI-bridge concerns** with both AJ and helix/Hermes ecosystems.
- **Git hygiene varies:** AJ and JARVIS have preserved/untracked local work; helix Drive copy dirty; Hermes source detached HEAD in runtime-managed install context. All states reported as-is.