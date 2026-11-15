# 06 — Security and Permission Boundary (Criterion 5)

## Future capability boundary (proposed): `hermes.gateway.ensure` (narrowly scoped)

| Control | Requirement | Rationale / evidence |
|---|---|---|
| Fixed executable | Resolved, validated Hermes executable path from trusted config/install provenance; no caller-supplied binary | Prevent command/path injection; align with existing AJ adapter strictness patterns |
| Fixed argv | Exactly `['<hermes>', 'gateway', 'ensure', '--json', '--timeout', '<bounded-int>']` (or equivalent fixed shape); no extra/user-controlled args | CLI supports bounded flags only (4B.5 source/help); reject unknown/variable argv |
| No shell | `shell=False`/no shell interpretation at all layers | Ensure/start paths use argv exec/spawn, not shell (4B.5) |
| Strict environment control | Allowlisted/minimal env for subprocess; no secret leakage from AJ env; avoid inheriting unsafe flags; set only required deterministic vars | Spawn path strips/carries specific vars (Hermes side); AJ must not broaden exposure |
| Executable provenance | Verify expected install/source/version/identity constraints where feasible; fail closed on mismatch/unverifiable provenance for mutating scope | Reduce TOCTOU/confused deputy to wrong binary/install |
| Bounded timeout | Mandatory bounded `--timeout` and AJ-side subprocess timeout budget; no unbounded waits | Deadline-based ensure behavior observed; 8 GB/resource safety |
| Bounded stdout/stderr collection | Cap capture size (incremental/limit) and parse only expected JSON/known structures | Prevent memory/log abuse; align with AJ hardening posture |
| Secret redaction | Redact tokens/credentials/paths/URLs as applicable before logging/persisting evidence; never emit secrets in errors/audit | Credential-free JSON intent, but logs/runtime outputs may contain sensitive data (4B.5 risk) |
| Restricted permissions | Default-disabled; capability/feature flags explicit; least-privilege permission checks per action class | Existing AJ deny-by-default/fail-closed model |
| Explicit feature flag | Separate, explicit flag(s) for any gateway lifecycle capability (distinct from `hermes.status.read`) | Prevent accidental enablement |
| Explicit capability flag | Registered capability identity for `hermes.gateway.ensure` (and/or split capabilities) with policy gating | Auditable authorization |
| Auditable operation evidence | Record request/decision/observation/action/read-back/outcome with IDs and provenance (no invented identity) | AJ auditability/invariant |

## Permission split (recommended; do not collapse observation and mutation)

| Permission (proposed) | Allows | Mutating? | Notes |
|---|---|---|---|
| `hermes.gateway.observe` (or reuse/extend status-read scope explicitly) | Read-only discovery/status/read-back probes and classification | No | May be needed for prechecks; still bounded/no side effects by AJ |
| `hermes.gateway.attach` | Treat validated ready endpoint as usable/attach without lifecycle change | No | Only when observed `ready`; no start/replace |
| `hermes.gateway.start` (or `ensure.start`) | Permit lifecycle action that may start service/unmanaged gateway when policy allows | **Yes** | Highest-risk common mutation; explicit confirmation/policy gates advised |
| `hermes.gateway.replace` (or `ensure.replace`) | Permit handling that may trigger/accept incompatible-owner replace path | **Yes (critical)** | Default deny; require strong evidence/conditions; often manual review preferred |

**Design rule:** a single unrestricted permission MUST NOT cover observation + start + replace. Least privilege and separate authorization decisions required.

## Trust and local-host limitations
- **`local_trust` is not authentication.** Do not claim authenticated operator/principal identity without a real trusted identity provider. AJ must record trust context honestly (e.g. local invocation context) without fabrication.
- **TOCTOU:** path/state/ownership checks and execution are separated in time; local filesystem/supervisor/control state can change between observe and act. Mitigate with re-validation/read-back and fail-closed ambiguity handling, but **cannot eliminate**.
- **Local-host trust:** same-user processes can influence profile dirs/sockets/state within permissions; compromised/malicious local context can affect outcomes. OS permissions and validation bound but do not remove risk.
- **Confused deputy:** even with fixed argv, ensure may start/replace runtime acting with Hermes’ configured privileges/integrations; scope must remain minimal and explicit.

## Uncertainties
- Completeness of redaction across all Hermes runtime logs/outputs and all failure branches.
- Provenance assurance strength on this host without additional attestation mechanisms.
