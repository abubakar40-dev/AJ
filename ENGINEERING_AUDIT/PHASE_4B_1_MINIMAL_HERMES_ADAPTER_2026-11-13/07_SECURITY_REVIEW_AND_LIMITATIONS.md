# 07 — Security Review and Limitations

## Controls implemented
- **Deny-by-default allowlist:** only `hermes.status.read` permitted; capability registration and adapter execution gated by explicit flags/config. Unknown/invalid requests rejected fail-closed.
- **No command injection surface:** fixed argv `["<resolved-hermes>", "gateway", "status"]`, `shell=False`, no user-controlled args/executable path at request time, cli_path validated (no whitespace/NUL) and resolved.
- **Environment minimization:** controlled env allowlist for subprocess (PATH/HOME/USER/locale/term/XDG/DBus/HERMES_HOME/HERMES_PROFILE); arbitrary sensitive env vars not forwarded.
- **Resource bounds:** configured/bounded timeout (adapter-enforced kill/timeout handling via subprocess timeout), bounded stdout/stderr capture with truncation markers/policy.
- **Untrusted output handling:** Hermes CLI output treated as untrusted diagnostic text; bounded and best-effort redacted before persistence/logging/return payloads. No execution/eval of output.
- **Identity honesty:** `local_trust` only (non-authenticated, not cryptographic, not remote/multi-user identity). No promotion of caller metadata to verified identity.
- **No secret exposure by design:** no secrets required; no config/env/service/secret files modified; redaction applied to captured text/error messages.

## Verified safe for this spike (bounded conditions)
- `hermes gateway status` (no deep/full) as read-only diagnostic probe, per source inspection and controlled live preflight, when mediated by adapter bounds and validation.

## Limitations / residual risks
- **Output semantics unstructured:** human-readable, environment-dependent; adapter does not guarantee stable parsing/complete interpretation (and may truncate large output by policy).
- **Service-status side dependencies:** status command may invoke OS service queries (e.g. systemd) whose behavior/latency depends on host; adapter timeout bounds impact but cannot prove host-level non-blocking.
- **Redaction best-effort:** pattern-based; unusual secret formats may not be fully detected (minimized by env allowlist and no secret requirements).
- **No authenticated identity / not multi-user safe:** local_trust assumption only for controlled single-operator environment.
- **No cooperative Hermes cancellation / no Hermes-native IDs:** CLI probe provides none; unknown/ambiguous states must remain honest.
- **No cross-store atomicity / no exactly-once claims:** AJ evidence model constraints unchanged.
- **Scope:** read-only status capability only; does not authorize or imply safety of agent/skill/tool/MCP/mutating execution.

## Security conclusion
Implementation meets 4B.1 bounded security goals for the approved read-only capability with fail-closed defaults and evidenced controls. Any scope expansion requires new design lock, command verification, and tests.