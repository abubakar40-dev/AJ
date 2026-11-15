# 10 — Versioned Capability Contract Proposal (Criterion 5/12 deliverable)

## Compatibility and versioning
- **Preserve existing contract:** `aj.hermes.execution.v0` remains the contract for implemented `hermes.status.read` behavior. **No silent alteration.**
- **Proposal:** introduce a **new capability/profile/versioned extension** only when implemented (separately authorized), e.g. `aj.hermes.execution.v1` or `aj.hermes.lifecycle.v0`/capability-scoped profile, to represent mutating lifecycle semantics (start/replace attempts, ambiguous outcomes, read-back requirements) without overloading read-only status semantics.
- **Why new version/profile may be needed:** lifecycle mutation, pre/post-state observations, mutating action classification, `unknown/requires_manual_review` as first-class outcomes tied to side-effect ambiguity, and stricter authorization/evidence fields differ materially from read-only `status.read`. Exact version name TBD at implementation proposal; must be explicit and backwards-compatible in parsing/negotiation where applicable.

## A. Contract — proposed request/response structures (illustrative)

### Request (`hermes.gateway.ensure`, proposed)
```json
{
  "contract": "aj.hermes.lifecycle.v0 (proposed)",
  "capability": "hermes.gateway.ensure",
  "request": {
    "task_id": "string",
    "operation_id": "string",
    "attempt_id": "string",
    "correlation_id": "string",
    "target": { "profile": "default|<name>", "scope": "profile|host" },
    "mode": "observe_attach_only | allow_start_if_absent | allow_replace_if_authorized (policy-gated)",
    "timeout_ms": 30000,
    "authorization": { "permissions": ["..."], "feature_flags": ["..."], "policy_ref": "..." },
    "requested_at": "<iso8601>"
  }
}
```
**Notes:** fixed argv derived by adapter (`hermes gateway ensure --json --timeout <bounded>`), no caller-provided arbitrary args/env. `mode` constrained by permission split (doc 06).

### Response (proposed)
```json
{
  "contract": "aj.hermes.lifecycle.v0 (proposed)",
  "capability": "hermes.gateway.ensure",
  "result": {
    "operation_id": "string",
    "attempt_id": "string",
    "status": "submitted|accepted|running|completed|failed|rejected|cancel_requested|cancelled|timeout|unknown|requires_manual_review",
    "final_classification": "ready|rejected|failed|unknown|requires_manual_review|...",
    "mutating_action": "none|attach|service_start_requested|detached_spawn|replace_attempted|unknown",
    "observed_initial_state": { "state": "...", "reason_code": "...", "evidence_refs": [] },
    "ensure_verdict": { "exit_code": 0, "state": "ready", "reason_code": null, "detail_redacted": null },
    "readback": { "verified": true, "state": "ready", "identity": {}, "limitations": [] },
    "error": null,
    "timestamps": { "started": "...", "finished": "..." }
  }
}
```
Fields are illustrative; implementation must not fabricate Hermes-native fields/IDs or authenticated principal identity.

## B. Lifecycle (future, proposed)
1. **Request received** (validated schema/contract).
2. **Authorization checked** (feature flags, capability/permission split, policy, resource admission).
3. **Operation registered** (durable intent/evidence record where reliable; handle persistence uncertainty).
4. **Existing gateway observed** (read-only classification, state-gated).
5. **State decision made** (attach / observe-wait / reject / manual-review / or authorized mutation path).
6. **Optional lifecycle action authorized** (explicit for start/replace; fail closed otherwise).
7. **Operation executed** (fixed argv, no shell, bounded I/O/timeout, single in-flight per target).
8. **Read-back performed** (control/endpoint/status verification; re-observation as needed).
9. **Evidence persisted** (before/after observations, action, results, classification; persistence outcome recorded).
10. **Final outcome returned** (truthful status; ambiguity preserved).

## C. Outcome vocabulary
Reuse AJ/truthful statuses where appropriate: `submitted`, `accepted`, `running`, `completed`, `failed`, `rejected`, `cancel_requested`, `cancelled`, `timeout`, `unknown`, `requires_manual_review`.
- **Do not claim native Hermes states** where none exist; map Hermes verdicts/reasons into AJ observations/evidence fields.
- `cancel_requested/cancelled`: only if real cancellation semantics are supported/evidenced (local subprocess kill ≠ runtime cancellation).
- Ambiguous lifecycle side effects default to `timeout`/`unknown`/`requires_manual_review`.

## D. Evidence (must record)
- `task_id`, `operation_id`, `attempt_id`, `correlation_id`
- `capability_id` / requested operation (`hermes.gateway.ensure`)
- Authorization context (flags/permissions/policy decisions, **not** fabricated authenticated principal)
- Observed initial state (signals/verdicts/reasons)
- Action taken (none/attach/start requested/spawn/replace attempted/aborted) and mutating classification
- Process result (argv class, exit code, bounded redacted stdout/stderr summaries/timings)
- Read-back result (surfaces queried, verified fields, gaps)
- Final classification and rationale
- Error and recovery information (incl. no-rollback/no-autoretry notes when relevant)
- Timestamps and provenance (AJ component, adapter, executable identity/version if verified)

**Prohibitions:** no invented authenticated principal, no fabricated Hermes execution IDs, no false idempotency/exactly-once/health claims.
