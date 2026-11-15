# 01 — Preflight and CLI Safety Verification

**Phase:** 4B.1 Minimal AJ↔Hermes Execution Adapter (read-only `hermes.status.read`)  
**Date:** 2026-11-13  
**Status:** Stage A preflight complete for approved scope; **CLI safety gate PASS (conditional, adapter-bounded)**.

## 1. Scope and constraints observed
- AJ-only changes; no modifications to JARVIS, HELIX app/source/config/runtime/services, Hermes source/runtime/config, `~/helix` symlink, or `Drive/hermes/helix`.
- No commits/staging/push/merge/rebase/reset/clean, no installs, no env/secret changes/disclosure, no service start/stop/restart/reconfigure, no Docker/Honcho/paid APIs, no DB changes outside intended AJ implementation.
- All pre-existing tracked modifications and untracked files preserved (see Section 2).

## 2. Git and runtime preflight evidence (recorded before source changes)

| Repo / path | Root | Branch | HEAD | Ahead/behind | Working tree (summary) |
|---|---|---|---|---|---|
| `AJ` | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ` | `main` | `468fdcebece5b25f02e53add4928d3650ef175f4` | `origin/main [ahead 1]` | Pre-existing tracked M: `aj/__main__.py, aj/diagnostics.py, aj/orchestrator.py, aj/recovery.py, aj/task.py, aj/transfer.py, tests/test_foundation.py, tests/test_orchestrator.py, tests/test_path_config_hardening.py, tests/test_phase2.py, tests/test_phase3.py, tests/test_step_c_gap_closure.py`; pre-existing/unrelated untracked incl. `ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/`, `ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/`, `aj/authorization.py, aj/consistency.py, aj/operation_evidence.py, aj/storage_diagnostics.py, integrations/`, and untracked tests from prior phases. |
| `JARVIS` | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/JARVIS` | `audit/consolidation-2026-11-06` | `d93c702...` | `origin/audit/consolidation-2026-11-06` | Untracked: `chat_history/2026-11-04.md`, `chat_history/2026-11-05.md` (preserved). |
| `AI_WORKSPACE/helix` | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/helix` | `audit/consolidation-2026-11-06` | `99c7a38...` | `origin/audit/consolidation-2026-11-06` | Clean. |
| `Drive/hermes/helix` (`~/helix`) | `/run/media/abubakargcx/My Drive/hermes/helix` | `main` | `e8a64cf...` | diverged/dirty | Tracked mods/deletions + untracked; **untouched** (no consolidation/migration). |
| Hermes source | `~/.hermes/hermes-agent` | detached | `2bd378ed...` | n/a | Clean. |

**Hermes runtime observed (read-only evidence):** `hermes --version` => `Hermes Agent v0.23.0 (2026.9.24) · stable · local 2bd378ed1b8d` (Python 3.14.9, OpenAI SDK 2.54.0), wrapper `~/.local/bin/hermes`. `~/.hermes/gateway_state.json` indicates running gateway (pid 5397, whatsapp connected, v0.23.0) — not proof of AJ integration.

## 3. Governing design inputs read
- `AJ/ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/00-09` (all ten documents), especially `02_HERMES_INTERFACE_SELECTION.md`, `03_AJ_HERMES_VERSIONED_CONTRACT.md`, `04_SECURITY_PERMISSION_AND_IDENTITY_DESIGN.md`, `06_EXECUTION_LIFECYCLE_FAILURE_AND_RECOVERY.md`, `08_PHASE_4B_1_IMPLEMENTATION_BLUEPRINT.md`.
- AJ source inspected: `aj/execution.py`, `aj/runtime.py`, `aj/contracts.py`, `aj/config.py`, `aj/errors.py`, `aj/diagnostics.py`, `aj/operation_evidence.py`, `aj/recovery.py`, `aj/task.py`, `aj/authorization.py`, `aj/capability.py`, `aj/orchestrator.py`, `tests/test_hermes_contract.py`.
- Hermes source inspected: `hermes_cli/gateway.py` (`_cmd_status`, `get_gateway_runtime_snapshot`, service-status/health helpers), `gateway/status.py` (runtime status/PID/lock readers), `gateway/runtime_contract.py`, `hermes_cli/gateway_profile_lifecycle.py` (`print_parked_status`), `hermes_cli/gateway_status_notes.py`, wrapper/help behavior.

## 4. Candidate command evaluation

| Candidate | Evidence | Verdict |
|---|---|---|
| `hermes gateway status` (no `--deep/--full`) | Implemented by `_cmd_status` (`hermes_cli/gateway.py`): obtains runtime snapshot via `get_gateway_runtime_snapshot` (reads runtime/ownership state), prints profile/parked/service/standalone state, queries installed service status (e.g. `systemctl --user status ...` path in `systemd_status`), prints runtime health/duplicate-credential warnings via readers, and prints served/ingress info where applicable. Source inspection shows diagnostic/read-oriented flow; no `AIAgent`/session creation, no tool/skill/MCP invocation, no message send, no gateway start/stop/restart/config mutation observed in inspected status path. Help confirms bounded options (`--deep`, `--full`, `--system`, `--json`). | **Selected for 4B.1 spike (adapter-bounded).** |
| `hermes status` (top-level, deep doctor-style) | Broader diagnostics surface; not required for minimal read-only status capability. | Not selected. |
| Session/agent/ACP/kanban commands, `gateway run/start/restart/stop` | Mutating or agent-executing by purpose. | Rejected. |

## 5. Read-only / side-effect analysis (`hermes gateway status`)
- **State mutation:** No writes/atomic updates/session creation/agent dispatch/tool execution/message sends observed in `_cmd_status` and inspected helper paths (`get_gateway_runtime_snapshot`, `read_runtime_status`, `print_parked_status` read/print logic, service status queries). No evidence of Hermes runtime config/state mutation.
- **External effects:** Reads local runtime files/pids/lock/service state and invokes OS service-status query for diagnostics (e.g. systemd status read). No outbound platform messaging or agent-external task execution observed.
- **Session/agent/tool/skill/MCP:** None observed.
- **Native Hermes IDs:** None required/invented; capability is coarse runtime/status read.

## 6. Boundedness, stability, and sensitivity
- **Blocking risk:** External status probes (e.g. systemd) can hang in pathological environments. **Adapter must enforce bounded timeout and safe termination/cleanup**; timeout => honest `timeout`/unknown outcome, never success.
- **Output size/shape:** Human-readable, environment-dependent (service manager output, cgroup/process lines, health warnings). Not a stable machine schema; may include verbose process command text. **Adapter must bound stdout/stderr capture, truncate by documented policy (not treated as complete), and redact sensitive patterns before persistence/logging/diagnostics.**
- **Environment/profile:** Reads current Hermes home/profile/runtime state; adapter must run with controlled cwd/env allowlist (no arbitrary sensitive env inheritance) and fixed argv array (no shell, no user-controlled args).
- **Bounded live probe (read-only):** `timeout 10 "$HOME/.local/bin/hermes" gateway status` exited `0` and printed service/runtime status (including verbose gateway cgroup command text). Demonstrates command viability but confirms need for output bounds/redaction.

## 7. CLI safety gate outcome

**PASS (conditional).** `hermes gateway status` (no `--deep/--full`) is acceptable for `hermes.status.read` **only** when invoked through the AJ adapter with: fixed argv `["hermes", "gateway", "status"]` (resolved executable path), no shell, controlled env/cwd, bounded timeout, bounded stdout/stderr capture with documented truncation, redaction, fail-closed validation/authorization, honest status mapping (including timeout/unknown/manual review), and nullable Hermes IDs. The command is treated as an untrusted-output diagnostic read; adapter controls make the integration bounded/safe for this spike.

If runtime behavior diverges from inspected evidence (mutation/side effects/uncontrollable blocking or unsafe output), integration must fail closed/disable and be documented.

## 8. AJ regression baseline (before source changes)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` (AJ/): **exit 0**, `ok: true`, **23/23 checks**, `attached.hermes: "NOT ATTACHED"`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` (AJ/): **433 passed, 13 warnings in 39.63s, 0 failed**.
  - Warnings: `PyGIDeprecationWarning` from `gi.overrides` (environment) and 12 `DeprecationWarning` from `multiprocessing/popen_fork.py` in `tests/test_phase3.py` (`fork()` in multi-threaded process) — pre-existing baseline observations, not failures.

## 9. Proceed decision
- **Proceed to Stage B (minimal adapter implementation)** under approved constraints: CLI subprocess interface, capability `hermes.status.read` only, contract `aj.hermes.execution.v0`, `local_trust` (non-authenticated), adapter/capability default-disabled, deny-by-default, fixed argv/no shell/controlled env/bounded timeout+output/redaction, separate memory domains, AJ-only code.
- No widening beyond read-only status; no live enablement in normal runtime; controlled live preflight only if safe and explicitly isolated, then restore disabled state.
