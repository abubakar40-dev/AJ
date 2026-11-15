# 03 — Phase 3F Backlog Delta (additive)

This updates `MASTER_CORE_AUDIT_2026-11-13/03_MASTER_ISSUE_BACKLOG.md` additively based on Phase 3F investigation/implementation. Severity counts reflect 3F findings.

## Summary delta
- **Critical:** 0 open
- **High:** 0 open
- **Medium:** 6 open (AJ-AUD-001..006 remain; AJ-AUD-002 materially reduced/partially remediated in local-trust scope but not fully closed as "authenticated identity")
- **Low:** 8 open
- **Blocked/External:** 7 tracked
- **Resolved/partially remediated in Phase 3F:** identity/provenance hardening for privileged reconciliation (see below)

## Phase 3F findings

| ID | Component | Sev | Type | Evidence | Root cause | Impact | Remediation (3F) | Status | Acceptance criteria | Regression tests |
|---|---|---:|---|---|---|---|---|---|---|---|
| AJ-3F-001 | `aj/authorization.py`, `aj/orchestrator.py`, `aj/operation_evidence.py`, audit, CLI/API boundary | Medium | Security/trust-boundary gap | Pre-3F: caller-supplied `operator` metadata could be mistaken for identity; provenance incomplete in evidence/audit; no explicit verified-identity-required fail-closed mode | Privileged authorization lacked full principal/source/requested-metadata/decision/operation-scope provenance and explicit non-authentication semantics | Impersonating/misleading operator attribution in local/admin workflows; ambiguous auditability; risk of false security claims | Hardened context/decision model (principal, principal_source, requested_operator, authenticated, scope, runtime provenance), fail-closed modes incl. `require_verified_identity`, internal context construction, per-op scoped authorization, provenance persisted to op evidence + `privileged_authorization`/`operator_reconciliation` audit and results; documented trust boundary | **Partially remediated (local-trust scope)** | No caller metadata promoted to authenticated principal; unauthorized/missing-verified-identity fail closed; provenance distinguishes principal/source/requested/decision/op ID; existing 3A–3E guarantees intact | `tests/test_phase3f_identity_trust_boundary.py`, updated `tests/test_phase3e_evidence_consistency.py` |
| AJ-3F-002 | Privileged reconciliation identity | Medium (residual) | Blocked/architectural limitation | No built-in trusted identity provider/IPC/socket peer-cred boundary; `local_trust` is explicit assumption, not authentication | Cryptographic/verified operator identity requires trusted verifier/identity source or deployment boundary not present | Cannot prove authenticated human/operator identity in default local mode; remote/multi-user/untrusted-local scenarios not protected | Fail closed in `require_verified_identity` mode; keep local_trust only where assumptions hold; document exact blocker/alternatives | **Open (blocked on trusted identity provider/boundary decision)** | Authenticated principal recorded only from trusted provider; no fake auth; deployment claims accurate | Provider-adapter contract tests when implemented; negative tests for unavailable verified identity pass |
| AJ-3F-003 | Task lifecycle APIs vs reconcile workflow | Low | Documentation/integration boundary | `Aj.abandon/dead_letter/requeue` and other lifecycle APIs exist outside reconcile op-evidence/authorization workflow; scheduler/internal callers use them legitimately | Reconcile is the controlled privileged-admin workflow; direct lifecycle APIs are separate trusted-local programmatic surfaces | Potential misuse/confusion if treated as audited privileged-reconciliation path without reconcile controls | Documented boundary; no behavior-breaking guard added to avoid regressions in internal/scheduler/tested flows; reconcile remains sole controlled privileged path | **Documented / accepted for local-trust model** | Operators/integrators use reconcile for privileged admin dispositions; docs explicit | Existing lifecycle/dead-letter/scheduler tests remain green |
| AJ-AUD-001 (updated) | Multi-store persistence/evidence | Medium | Architectural weakness | Phase 3F investigation: independent append-only stores, no cross-file transaction; partial windows identified; intent/outcome/incomplete detection and consistency checks provide detectability but not atomicity | No transactional/outbox mechanism across stores | Partial/crash-window inconsistency possible; manual inspection may be required; not exactly-once/atomic | Recommended: correlation/completeness hardening first; evaluate WAL-intent/single append-only op log; no large redesign now | **Open** | All partial outcomes detectable/classified with actionable diagnostics; no false success | Fault-injection/crash-window/restart consistency tests (targeted expansion) |

## Master backlog items status after 3F
- **AJ-AUD-001:** Open (evidence/refinement updated).
- **AJ-AUD-002:** **Partially remediated** in controlled local-trust scope by 3F (provenance, fail-closed verified-identity mode, no metadata promotion, consistent reconcile enforcement). **Residual/open** for true authenticated/verified operator identity and remote/untrusted deployment (tracked as AJ-3F-002). Honest claims required.
- **AJ-AUD-003..AJ-AUD-009, AJ-AUD-013..AJ-AUD-020:** unchanged/open as previously classified.
- **AJ-AUD-010..AJ-AUD-012:** blocked/external, unchanged.

## Residual risks (explicit)
- No cryptographic/human-authenticated operator identity by default.
- Local-trust mode assumes trusted local runtime/caller and controlled host; OS/process provenance is not authentication.
- Multi-store writes remain non-atomic (detectable, not eliminated).
- Direct programmatic lifecycle APIs bypass reconcile-specific op-evidence workflow (by design/scope) and must be used only in trusted contexts.