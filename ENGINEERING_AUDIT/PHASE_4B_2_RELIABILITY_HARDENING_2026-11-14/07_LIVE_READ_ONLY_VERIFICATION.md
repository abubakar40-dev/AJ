# 07 — Live Read-Only Verification

## Controlled preflight (isolated, in-memory, read-only)
- **Command (approved only):** `hermes gateway status` via adapter fixed argv `["<resolved-hermes>", "gateway", "status"]` (no `--deep/--full`, no shell).
- **Configuration:** in-memory overrides only (`load_config(overrides=...)` + `assemble(...)`), temp data/audit dirs, `persist_memory/tasks=false`, explicit enablement set only for process (`feature_flags.hermes_execution_adapter=true`, `execution.runtime="hermes_cli"`, `execution.hermes.enabled=true`, `execution.hermes.capability_status_read_enabled=true`, timeout/output bounds set). No persistent config/env/service files changed; no Hermes/JARVIS/HELIX runtime or service changes.

## Results (3 repeated probes)
- Adapter attached in isolated process: `available=true`, `integration_status=attached_read_only`, capabilities `['hermes.status.read']`, limits active (`default_timeout_ms=10000, max_timeout_ms=15000, stdout_max_bytes=6000, stderr_max_bytes=2000`).
- Each run (`/3`): `ExecutionResult status=completed ok=True`, envelope `status=completed`, `hermes_execution_id=None`, evidence `argv_template=['<hermes>','gateway','status']`, `collection=bounded_incremental`.
- Consistency: `ALL_COMPLETED=True` across 3 probes. Output bounded/sanitized (no known test secrets injected; adapter redaction/collection active).

## Restoration
- Isolated process exited; no persistent enablement written. Post-state: `python -m aj --check` **23/23 ok, `attached.hermes: "NOT ATTACHED"`**, defaults unchanged.

## Evidence level
- **Verified:** controlled live AJ-mediated read-only probes in isolated process (bounded, repeated), fixed command/argv, honest completed mapping, no fabricated IDs, default-disabled restored.
- **Not claimed:** long-term/continuous reliability, semantic gateway health from unstructured text, or behavior under Hermes runtime changes beyond inspected/observed evidence. Live gateway was available in this environment; if unavailable, results would be reported honestly (not fabricated).