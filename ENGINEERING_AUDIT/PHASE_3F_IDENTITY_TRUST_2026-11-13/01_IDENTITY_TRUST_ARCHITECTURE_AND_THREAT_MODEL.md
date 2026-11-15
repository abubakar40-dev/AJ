# 01 — Actual Identity & Authorization Architecture, Threat Model

## 1. Actual architecture (as of 3F, evidence-based)

### Privileged operation in scope
- **Controlled privileged reconciliation:** `Aj.reconcile(task_id, action, *, reason, evidence_basis, operator, operation_id, idempotency_key)` with actions `abort | dead_letter | abandon | clear_recovery_required`.
- **Entry points:** programmatic `Aj.reconcile(...)` and CLI `python -m aj reconcile ...` (`aj/__main__.py`). No alternate CLI/API/server path performs this privileged reconciliation workflow.
- **Durable evidence:** append-only `reconciliation_operations.jsonl` via `OperationEvidenceStore` (intent/progress/outcome, stable operation IDs, incomplete detection, idempotent duplicate handling for known terminal outcomes and no reapply for incomplete intent-only operations).
- **Authorization:** `aj.authorization` guardrail invoked inside `reconcile` for every attempt, fail-closed. Decision/audit/evidence bound to operation scope (`operation_kind=reconciliation`, `action`, `task_id`, `operation_id`, trust domain/source).
- **Audit/evidence provenance:** `privileged_authorization` and `operator_reconciliation` audit events, operation-evidence intent/progress metadata, and reconcile result payloads record requested operator metadata, principal identity, principal source, authenticated flag, identity provider, trust assumption, authorization decision, and operation scope/ID.

### Trust/identity model (actual, defensible)
- **Caller-supplied operator metadata (`--operator` / `operator` arg):** treated as **requested operator metadata only**. It may be empty, arbitrary, or impersonating; it is never promoted to authenticated principal identity.
- **Authenticated principal:** `authenticated=true` and `principal_identity` are set only when a trusted identity provider/verifier explicitly supplies a verified principal. **No built-in mode fabricates authenticated identity.**
- **Default mode `local_trust` (enabled):** allows privileged reconciliation under an **explicit local-runtime trusted-caller assumption** for controlled local/single-process use. It captures best-effort OS/process runtime provenance (host, pid/ppid, uid/euid, os user, cwd) as **environment-derived, non-authenticated** provenance and records it in decision provenance/details. This is **not** human authentication, not proof of intent, and not a verified identity across untrusted boundaries.
- **Fail-closed modes:** `deny/disabled/forbidden` denies; `unavailable/none/null/error` (or unavailable authorizer) denies as unavailable; invalid/unknown mode denies as invalid; `enabled=false` denies as unavailable. `require_verified_identity` / `verified_only` / `authenticated_only` fail closed (unavailable) because no built-in trusted identity provider is configured.
- **Extensibility:** builder accepts a programmatic callable identity/authorization provider adapter; provider exceptions/invalid decisions fail closed. Config remains local/mapping-based (`permissions.privileged_reconciliation` or `permissions.privileged_operations`).

### Other task lifecycle APIs (not the privileged reconciliation workflow)
- `Aj.abandon`, `Aj.dead_letter`, `Aj.requeue`, `Aj.retry`, `Aj.cancel_task`, `Aj.recover`, `LeaseManager.break_stale_operation`, scheduler-driven actions: governed by existing task-state/lease/safety rules and their own semantics. They do not mint authenticated operator identity and do not replace the controlled reconcile op-evidence/authorization workflow. Internal/system uses (e.g. scheduler deadline `dead_letter`, reconcile-internal controlled transitions/helpers) remain valid; direct programmatic use is a trusted-local-API concern and documented as outside the reconcile privileged boundary.

## 2. Threat model and attack scenarios

### Deployment assumptions (documented)
- **In-scope for default guarantees:** controlled local use, trusted operator/runtime context, same-machine local process/CLI/API invocation, single-user or equivalently trusted local environment, process-local file-backed stores.
- **Out-of-scope / not assumed safe without additional controls:** untrusted multi-user hosts, remote/network-exposed callers, hostile local co-tenants/processes with access to AJ runtime/data/APIs, distributed/shared trust domains, cryptographic operator authentication, non-repudiation.

### Scenarios analyzed and tested/mitigated

| ID | Scenario | Feasibility | Result / control |
|---|---|---|---|
| TM-1 | Caller supplies forged/arbitrary/impersonating `operator` metadata (e.g. `root`, another user) | Trivial via CLI/API | **Mitigated:** recorded only as `requested_operator` metadata; `authenticated=false`, `principal_identity=null`, `principal_source=none` in auth decision, audit, op evidence, result. No promotion. |
| TM-2 | Missing/empty operator metadata | Trivial | **Mitigated:** preserved as requested metadata (possibly empty); authorization/provenance still recorded; no principal invented. |
| TM-3 | Caller attempts to inject authenticated principal/decision via reconcile API/CLI args | Not supported by interface; tested by API shape | **Mitigated:** `reconcile` constructs authorization context internally (ignores caller for identity/auth fields), binds scope to operation, never accepts external decision/principal. |
| TM-4 | Unauthorized privileged operation (policy denies, unavailable, or verified identity required but absent) | Configurable / by mode | **Mitigated:** fail-closed deny/refuse, no state change, refused op-evidence outcome, audited decision/provenance. |
| TM-5 | Authorization provider/authorizer failure or exception during reconciliation | Fault injection | **Mitigated:** treated as unavailable/error, fail-closed refuse, no state change, refused op-evidence outcome. |
| TM-6 | Duplicate operation ID reuse after terminal outcome | Possible via caller-supplied op ID | **Mitigated (existing 3E, preserved):** idempotent duplicate returned, no reapply/state mutation. |
| TM-7 | Incomplete/interrupted operation (intent without outcome) | Crash/window or fabricated intent-only record | **Mitigated (existing 3E, preserved):** detected as incomplete, explicit duplicate op ID does not reapply, manual disposition required, no fabricated success. |
| TM-8 | Cross-operation authorization reuse/tampering across scope | Caller cannot reuse decision object; op IDs/scopes differ | **Mitigated by design:** each attempt computes fresh decision bound to `operation_kind/action/task_id/operation_id`; audit/evidence record per-operation scope/decision. |
| TM-9 | Alternate entry-point bypass of privileged reconciliation guardrail | Reviewed | **No alternate reconcile path found:** CLI and API converge on `Aj.reconcile`; no other endpoint invokes reconcile workflow. Other lifecycle APIs are distinct (see architecture) and documented. |
| TM-10 | Concurrent privileged-operation attempts on same task | Possible | **Mitigated:** lease serialization/ownership checks and fail-closed/blocked outcomes; no unsafe duplicate application; operations evidenced/audited. |
| TM-11 | Misrepresentation of local trust/OS provenance as authentication | Risk in docs/claims | **Mitigated:** explicit naming (`local_runtime_trusted_caller`, not authenticated), `authenticated=false`, principal null unless verified provider, documentation updated. |
| TM-12 | Remote/multi-user/distributed attacker with API/FS/runtime access | Out of default trust boundary | **Not fully mitigated by local model:** requires external/trusted identity boundary, network authz, hardened deployment controls (documented limitation/blocker class). |

## 3. Trust boundary conclusion
The privileged-operation trust boundary is now **defensible and accurately documented for controlled local-runtime use**: authorization is consistently enforced and fail-closed on reconcile, caller metadata cannot silently become authenticated identity, and provenance is preserved in audit/op evidence. It is **not** a cryptographically authenticated, non-repudiable, or remote-safe identity boundary without an approved/external verified identity mechanism and deployment hardening. This is stated explicitly (no fake auth).