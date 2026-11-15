# 04 — Authorization, Permission, and Feature Flags

## Deny-by-default / fail-closed
- **Adapter attachment:** `_build_execution` returns `UnavailableExecutionAdapter` unless `feature_flags.hermes_execution_adapter==true`, `execution.runtime=="hermes_cli"`, and `execution.hermes.enabled==true`; config/exception => fail closed to unavailable.
- **Capability execution:** `HermesExecutionAdapter.available()` requires adapter enabled **and** `execution.hermes.capability_status_read_enabled==true`. Disabled => `ExecutionUnavailable`.
- **Capability allowlist:** only `hermes.status.read` accepted; unknown/non-allowlisted capability rejected before invocation. No arbitrary commands/args/executables/env/paths/skills/tools/MCP/messaging/filesystem-wide ops.
- **Capability registration:** `hermes.status.read` CapabilitySpec (owner HERMES, risk 0, read-only, `execution_adapter=hermes_cli:gateway.status`) registered in AJ registry **only** when adapter is attached/available; otherwise not executable/dispatchable as Hermes capability.
- **Request authorization:** v0 envelope requires AJ permission context (`authorizer=AJ`, `authorization_decision=allow`, `trust_mode=local_trust`) and is validated fail-closed. AJ orchestration still performs normal capability/permission checks before execution routing.
- **CLI safety:** fixed argv array `["<resolved-hermes>", "gateway", "status"]`, `shell=False`, no user-controlled executable/args, validated cli path, controlled env allowlist (no arbitrary sensitive inheritance).

## Configuration (defaults)
- `feature_flags.hermes_execution_adapter`: `false`
- `execution.runtime`: `"none"`
- `execution.hermes.enabled`: `false`
- `execution.hermes.capability_status_read_enabled`: `false`
- `execution.hermes.cli_path`: `"hermes"`
- `execution.hermes.default_timeout_ms`: `10000`
- `execution.hermes.max_timeout_ms`: `30000`
- `execution.hermes.stdout_max_bytes`: `8000`
- `execution.hermes.stderr_max_bytes`: `4000`

Invalid/missing enablement conditions do not enable execution. No existing user config/env/service files changed. No secrets required for read-only status probe.

## Explicit opt-in for controlled local test (example, non-persistent)
Enable only in isolated process/config (e.g. temp overrides or ephemeral config object):
- `feature_flags.hermes_execution_adapter=true`
- `execution.runtime="hermes_cli"`
- `execution.hermes.enabled=true`
- `execution.hermes.capability_status_read_enabled=true`
Then restore/exit to disabled state. Normal runtime and `python -m aj --check` remain unattached/disabled by default.

## Explicitly prohibited (remain unavailable)
Arbitrary shell/Python/direct AIAgent execution, general skill/tool/MCP execution, browser/desktop automation, filesystem-wide ops, file create/delete, messaging/WhatsApp/platform actions, email, account/financial/remote-admin ops, any mutating or external-side-effecting operation.