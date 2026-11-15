# 08 — Test and Verification Evidence

## Executed in this phase (read-only / non-mutating)
| Command | Scope | Result | Notes |
|---|---|---|---|
| `cd AJ && PYTHONDONTWRITEBYTECODE=1 python3 -m aj --check` | AJ readiness/self-check | **exit 0**, `ok:true`, **23/23 checks**, `failures:[]`, `attached:{jarvis:false, helix:false, hermes:"NOT ATTACHED"}` | Re-run during 4B.5; integration remains unattached/default posture unchanged by this phase |
| `hermes --version` | Installed Hermes identity | `v0.23.0 (2026.9.24) · stable · local 2bd378ed1b8d`, install dir `~/.hermes/hermes-agent`, git | Verified executable `/home/abubakargcx/.local/bin/hermes` |
| `git -C ~/.hermes/hermes-agent rev-parse HEAD; git status --short` | Hermes source state | HEAD `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`, clean | Detached HEAD, no local mods observed |
| `hermes gateway --help`, `hermes gateway ensure --help` | CLI contract | Lists `ensure`, `--json`, `--timeout`, exit-code contract | Command exists in installed version |
| `hermes gateway status`, `hermes gateway status --deep`, `hermes gateway list` | Read-only runtime diagnostics | Service active/running (PID 5397), control artifacts present | **No lifecycle actions performed** |
| `ps`, `ls/stat` on `~/.hermes` gateway/state/log files | Runtime observation | Observed running gateway process tree and state/socket/lock/pid/log files | Evidence of current environment, not ensure execution |
| Source inspection (`grep/sed`) | Implementation/tests trace | Key modules and tests identified/read (see docs 02–07) | Static evidence |

## Not executed (by restriction/design)
- `hermes gateway ensure` — **NOT executed** (no live lifecycle experiment). Behavior assessed from source/help/tests/runtime state only.
- No start/restart/stop/install/uninstall/enable of Hermes gateway; no service/config/env/credential changes; no AJ/Hermes source or config modifications; no stress/duplicate-gateway tests.

## Existing Hermes tests identified (source observations, not re-run in this phase)
- Core ensure/runtime: `tests/hermes_cli/test_gateway_runtime_ensure.py` (CLI JSON boundary, update fence, service start/non-mutation cases, unmanaged spawn/env/flags, reservation/discovery interactions), `tests/hermes_cli/test_gateway_runtime_service.py`, `tests/hermes_cli/test_gateway_runtime_replace_incompatible.py`, `tests/hermes_cli/test_gateway_runtime_discovery.py`, `tests/hermes_cli/test_gateway_runtime_home_identity.py`, related TUI/gateway/docker/e2e/multiplex tests invoking `ensure_gateway_runtime` / `hermes gateway ensure --json` (grep results recorded during investigation). **Not executed here; cited as implementation evidence context only.**

## AJ regression context (inherited, not re-run in 4B.5)
- Phase 4B.4 baseline reported: targeted 78 passed; full regression 502 passed, 1 failed (`tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`, intermittent on NTFS-backed tmp), 13 warnings; `aj --check` 23/23 Hermes NOT ATTACHED. **Not re-run in this phase except `aj --check`. Intermittent SQLite failure not hidden/dismissed.**

## Evidence limitations
- No executed proof of `ensure` success/failure/timeout behavior on this live environment (intentionally avoided). Conclusions relying on runtime behavior are source/test-informed inferences where not directly observed.
