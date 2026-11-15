# 04 — Security, Permission, and Identity Design

**Workstream D (Phase 4B.0).** Deny-by-default, fail-closed, AJ-controlled execution boundary design. Provisional; no live adapter implemented.

## 1. Design principles (existing approved direction + evidence)
- **Deny-by-default:** only explicitly allowlisted capability/command mappings may execute; everything else rejected before invocation.
- **AJ authorization is authoritative:** AJ validates capability and permission; Hermes/runtime is never an unrestricted authority for AJ-governed execution.
- **Fail closed:** unknown contract/version/capability/identity scope/validation failure/ambiguous policy => reject or `unknown`/`requires_manual_review` (never success).
- **Honest identity:** `local_trust` is a non-authenticated trusted-local assumption, not verified human/service authentication.
- **No secret exposure:** redact credentials/tokens/keys from inputs, argv, logs, evidence, and results.
- **Untrusted outputs:** Hermes stdout/stderr/results treated as untrusted data (sanitize, bound, never execute).

## 2. Initial integration capability (narrow, low-risk) — **evidence-based recommendation / requires approval**

| Field | Proposed value | Justification |
|---|---|---|
| AJ capability id | `hermes.status.read` | Read-only runtime observability probe; validates wiring/correlation/evidence/timeout/error paths without side effects |
| Description | Read Hermes runtime/gateway status via approved bounded CLI command | Hermes gateway observed running; status-style queries are typically non-mutating (command-level verification required in 4B.1 preflight) |
| Risk | **Low** (non-destructive, reversible, no external side effects intended) | No file mutation, no messaging, no tool/skill execution, no account changes |
| Side effects | None intended; must be verified | Any discovered mutation => capability not eligible |
| Boundedness | Fixed argv template, no user-controlled shell fragments, timeout cap, output byte/line cap, single attempt by default | Prevents resource abuse and injection |
| Availability | Only when Hermes CLI present, feature flag enabled, allowlist entry enabled, AJ authorization allows | Default disabled |

**If no suitable read-only command can be verified (no mutation, stable bounded behavior):** do not select a capability; block 4B.1 until criteria met (`02`, `08`).

## 3. Permission and allowlist design (explicit, testable)

### 3.1 Allowlist entry model (proposed, AJ-owned config/data)
Each entry: `allowlist_id`, `enabled` (default `false`), `capability_id`, `hermes_interface` (`cli`), `command_template_id`, `argv_template` (fixed tokens + strictly typed placeholders), `cwd_policy`, `env_allowlist` (minimal), `timeout_ms_max`, `output_max_bytes`, `side_effect_class` (`none|read_only|mutating|external` — v0 must be `read_only/none`), `idempotency_policy`, `retry_policy`, `required_aj_permission_level/risk_ceiling`, `evidence_requirements`, `approved_by`/`review_state`.

### 3.2 v0 allowlist (only entry permitted when explicitly enabled)
- **Allow:** `hermes.status.read` → single verified read-only Hermes CLI status command template (exact argv finalized in 4B.1 after verification), `timeout_ms_max` small (e.g. <= 10s proposed, bounded), output capped, no stdin, no shell interpolation.
- **Deny (explicitly out of scope):** all other capabilities/commands, wildcard commands, dynamic argv composition from untrusted input, any command that can create/modify/delete/send/execute tools/skills/MCP/sessions/tasks.

### 3.3 Explicitly prohibited in initial integration
- Shell execution / `bash -c` / arbitrary command strings.
- Arbitrary Python execution or in-process Hermes agent/tool invocation.
- Filesystem-wide or unscoped write access; config/env/db mutation.
- Browser automation, desktop automation beyond none.
- Messaging (WhatsApp/Telegram/Discord/etc.), external notifications, network side-effecting actions.
- Financial operations, account management, credential changes.
- Arbitrary MCP servers or unreviewed skills/tools enablement.
- Any mutating or externally side-effecting capability.

## 4. Input validation and execution bounds
- **Schema validation:** strict per `contract_version` and per capability; reject unknown fields (or ignore only if explicitly specified safe) — prefer fail-closed.
- **Input constraints:** v0 `input` must be empty `{}` or fixed enum/typed fields; max serialized size enforced; path/command separators/control chars rejected where applicable.
- **Command construction:** argv array only (no shell), template-based, no string concatenation of raw input into executable form.
- **Timeouts:** per-attempt timeout enforced by adapter; overall operation budget enforced by AJ.
- **Output limits:** cap stdout/stderr capture (bytes/lines); truncate with explicit marker and evidence; store digests/refs for large outputs.
- **Concurrency:** bounded (v0: single in-flight attempt per operation/capability unless proven safe).

## 5. Filesystem, network, and side-effect assumptions
- **Filesystem:** adapter reads only what required to invoke Hermes CLI in known install/home; **no writes** by v0 capability. Hermes may read its own state for status (runtime behavior) — accepted as read-only assumption but verified in 4B.1.
- **Network:** v0 read-only local status should avoid external side effects; however Hermes gateway may maintain existing connections — no new network action initiated by capability intent. Any observed external side effect => fail safety review.
- **External side effects:** `none` required for v0 allowlist.
- **Process environment:** pass minimal sanitized env; never pass secrets not required; do not inherit/forward caller secrets.

## 6. Secret handling and redaction
- Never log/persist raw credentials, tokens, API keys, cookies, session secrets, private keys, or `.env`/`auth.json` contents.
- Redact argv/env/output fields matching secret patterns and known sensitive keys before audit/evidence/storage.
- Evidence stores bounded hashes/metadata instead of raw sensitive payloads where possible.

## 7. Untrusted tool/output handling
- Treat all Hermes CLI output, stderr, and derived text as **untrusted data**, not instructions.
- Normalize/parse defensively; on parse/schema mismatch return `failed` (`response_invalid`) or `unknown` with evidence.
- No direct execution/eval of output; no propagation into privileged decisions without AJ validation.

## 8. Identity boundary (honest)

| Aspect | v0 design (provisional) | Evidence/constraint |
|---|---|---|
| Trust mode | `local_trust` | AJ 3F: explicit non-authenticated trusted-local assumption (`aj/authorization.py`, 3F docs) |
| Operator identity | **Not verified/authenticated**; provenance labels only | No trusted identity provider/peer-credential boundary established |
| Caller-supplied metadata | Recorded as metadata/provenance only; **never promoted** to authenticated principal or authorization grant | AJ 3F guardrails; contract §2.1 |
| Deployment boundary | Controlled local environment, single trusted operator, no remote/untrusted multi-user exposure | Required initial constraint |
| Cross-component identity | **Unsolved/not claimed**; AJ↔Hermes/Hermes-internal identities not cryptographically bound in v0 | `06_SECURITY_AND_TRUST_BOUNDARY_ASSESSMENT.md`, INT4A-003/011 |
| Residual risk | Local process/user compromise, confused deputy via mis-scoping, metadata spoofing assumptions | Documented and accepted only within stated boundary |

**Decision requiring user approval:** proceed under `local_trust` non-auth local-only scope for 4B.1, or block until verified identity mechanism is selected/implemented.

## 9. Audit/evidence requirements
- Every request: AJ authorization decision, allowlist match, validation result, correlation/IDs, sanitized command template ref, timeout/bounds, and operator/trust provenance labels.
- Every outcome: status with rationale, timestamps, exit/transport classification, bounded output refs/digests, Hermes IDs if evidenced, redaction notes, and reconciliation/disposition markers for `unknown`/`requires_manual_review`.
- Denials/failures recorded as first-class evidence (fail-closed visibility).

## 10. Labels
- **Existing approved direction:** fail-closed AJ authorization, no fake auth, least privilege.
- **Evidence-based recommendation:** `hermes.status.read` read-only first capability, CLI allowlist boundary.
- **Provisional design:** allowlist schema, bounds, redaction/evidence fields.
- **Decision requiring user approval:** identity scope acceptance, capability/command approval, any widening.
- **Deferred idea:** strong authenticated identity provider, mTLS/signed envelopes, remote-safe exposure.
