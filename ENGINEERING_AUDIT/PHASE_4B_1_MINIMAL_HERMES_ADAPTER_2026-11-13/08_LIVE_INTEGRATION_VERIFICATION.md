# 08 — Live Integration Verification

## Evidence levels (distinguished)
1. **Unit-tested adapter:** yes (`tests/test_phase4b1_hermes_adapter.py`, fake runner).
2. **Contract-tested adapter:** yes (v0 validation/envelope/status/ID/correlation mapping, fake runner).
3. **Fake-process integration-tested adapter:** yes (injected runner + assembly/wiring tests).
4. **Live Hermes CLI preflight:** yes (prior bounded probe `timeout 10 hermes gateway status` exit 0 observed; read-only behavior evidenced by source inspection).
5. **Live AJ-to-Hermes status operation:** yes (controlled, isolated, in-memory enablement; see below).
6. **End-to-end reliability and security verification:** partial for this bounded scope (unit/contract/security/fault-injection + controlled live read; no long-haul/chaos/service-manipulation; Hermes runtime not altered).

## Controlled live AJ-mediated preflight (read-only)
- **Date:** 2026-11-13
- **Method:** in-process, isolated execution using `aj.config.load(overrides=...)` + `assemble(...)` with temp data/audit dirs and `runtime.persist_memory/tasks=False`. Feature flag and adapter/capability explicitly enabled **only in-memory for this run**; no config/env/service files changed, no services restarted, no Hermes runtime/config modified.
- **Command executed by adapter:** fixed `hermes gateway status` (resolved CLI path, no deep/full), timeout 10000ms, stdout cap 6000, stderr cap 2000, controlled env allowlist.
- **Observed result:** `ADAPTER_AVAILABLE=True`, integration `attached_read_only`, capabilities `["hermes.status.read"]`, ExecutionResult `status=completed ok=True verified=True`, envelope `status=completed accepted=True hermes_execution_id=null`, bounded sanitized stdout captured (len ~5995, contained active/running gateway evidence), no secret markers observed in sanitized output.
- **Independent corroboration:** consistent with observed Hermes runtime/gateway active state and direct CLI status preflight evidence.

## Post-test restoration/verification
- **Feature state:** no persistent enablement created; isolated process exited (temp dirs). Default repo/runtime config remains disabled (`execution.runtime=none`, flags false).
- **`python -m aj --check`:** exit 0, 23/23, `attached.hermes: "NOT ATTACHED"`.
- **No unrelated changes/services/processes:** no Hermes/JARVIS/HELIX/HELIX-symlink/service modifications; no unexpected background processes started by adapter (bounded synchronous subprocess).
- **Pre-existing Git changes preserved:** all pre-existing tracked modifications and untracked files remained present after implementation/testing.