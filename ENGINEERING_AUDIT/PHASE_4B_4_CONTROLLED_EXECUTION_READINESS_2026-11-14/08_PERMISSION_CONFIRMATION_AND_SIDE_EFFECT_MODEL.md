# 08 — Permission, Confirmation, and Side-Effect Model (future design, not implemented)

## Minimal side-effect classification
| Class | Meaning | Examples (potential) | Baseline AJ handling (future) |
|---|---|---|---|
| `READ_ONLY` | No intended state change; observational | `hermes.status.read` (`gateway status`) | Current path: explicit allowlist + AJ authorization, bounded evidence, no confirmation beyond policy; still fail-closed |
| `REVERSIBLE_MUTATION` | Intended state change with plausible, evidenced rollback path | limited local toggles only if rollback truly provable (rare) | Explicit capability + side-effect policy + stronger authorization; confirmation likely; rollback evidence required, else treat as higher class |
| `IRREVERSIBLE_MUTATION` | State change not reliably reversible | creates/deletes persistent artifacts, one-way runtime changes without proven undo | Deny by default until dedicated design; explicit confirmation and elevated policy; prefer not first capability |
| `EXTERNAL_COMMUNICATION` | Sends data/messages outside local boundary | `hermes send`, messaging bridges | Out of near-term scope; highest scrutiny (recipients/content/identity/secrets) |
| `SENSITIVE_OPERATION` | Broad operational/security/availability impact or sensitive data handling | global pause, credential/secret-touching flows, security-sensitive controls | Explicit confirmation, tight allowlist, enhanced evidence/redaction, possibly manual review gates |

## Confirmation model (design requirements)
- Confirmation is an **AJ policy/authorization input** (e.g. approval gate/token bound to capability + action fingerprint/scope + freshness as per existing `permissions` patterns), **not** authentication and **not** proof of identity.
- `local_trust` remains non-authenticated; confirmation cannot upgrade trust into verified human/remote identity.
- For mutating/sensitive classes: require explicit, scope-bound, non-reusable-or-controlled approval as applicable; fail closed if absent/expired/mismatched.
- No confirmation UX implemented in 4B.4.

## Permission model requirements for first mutating capability
- Distinguish and record: `capability_id`, exact operation/argv template, `task_id`, `operation_id/attempt_id/correlation_id`, requested operator/provenance, trust mode, authorization decision, side-effect class, confirmation evidence (if required).
- Deny-by-default: capability registered/enabled only by explicit config+flag+allowlist; per-request contract validation mandatory.
- Prefer **fixed argv, no user-controlled input** for first mutating op (eliminates argument-injection and reduces evidence ambiguity).
