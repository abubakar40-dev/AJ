# 06 — Contract Gap Analysis (`aj.hermes.execution.v0`)

`v0` is sufficient for the **current read-only, fixed, no-external-ID status probe**. For any future **mutating** capability (e.g. preferred candidate `gateway.ensure`), gaps exist. Do **not** add fields speculatively; only add if truthfully sourceable.

| Proposed field/semantic | Needed for mutating? | Truthfully populatable? | Source | If unavailable |
|---|---|---|---|---|
| External operation/task/execution ID (distinct from AJ IDs) | Yes, when Hermes provides it | **Not for current probe** (`hermes_execution_id=null`). Hermes support for future ops **UNKNOWN** | Hermes CLI/API response/structured output (if added) | keep `null`, mark unknown linkage, require manual review on ambiguity |
| Explicit external state/result status mapping (Hermes-native) | Yes | **Partial/unknown** — current CLI output unstructured | Hermes interface contract | conservative AJ status (`unknown`/`requires_manual_review`) + raw bounded evidence |
| Cancellation state & request/result linkage | Yes if cancellable | **Unknown** per op; local process kill already distinguishable | Hermes cancellation API/command + response | represent `cancel_requested` only when AJ issued; do not claim remote cancelled without proof |
| Requested vs authenticated identity | Important clarity | **Requested/provenance available**, authenticated identity **not available** in `local_trust` | AJ permission context/runtime provenance | must state non-authenticated; never fabricate |
| Authorization decision/provenance (structured) | Yes | **Available** (AJ) | AJ authorizer/policy decision | n/a (must be present) |
| Capability/contract versioning & per-capability profile | Yes for multi-capability isolation | **Available to define** | AJ registry/contract selection | reject unsupported version/capability |
| Side-effect classification (`READ_ONLY`/`REVERSIBLE_MUTATION`/`IRREVERSIBLE_MUTATION`/`EXTERNAL_COMMUNICATION`/`SENSITIVE_OPERATION`) | Yes | **Available to declare in AJ policy/spec** (classification), but reversibility truth may be uncertain | AJ capability spec/policy; Hermes semantics inform | classify conservatively; require confirmation gates accordingly |
| Idempotency key & semantics (AJ-local vs Hermes-native) | Yes | AJ-local key **available**; Hermes-native **unknown/unavailable for many CLI ops** | AJ idempotency store; Hermes (if supported) | document local-dedupe only, no exactly-once claim, unknown on timeout-after-effect |
| Retry policy / retryability basis | Yes | **Partially available** (AJ policy/error class), external safety **unknown** | AJ + observed failure class + Hermes guarantees | default no-auto-retry for ambiguous mutating outcomes |
| Evidence provenance (who observed what) | Yes | **Available** (AJ/adapter/CLI output) | AJ runtime/adapter | required for every fact |
| Confirmation requirement / approval token binding | Yes for sensitive side effects | **Available** (AJ permissions/gates exist) | AJ authorizer/approval gate | fail closed if required confirmation absent/invalid |
| Dry-run support | Useful but optional | **Unknown** (op-dependent, likely unsupported for `ensure`) | Hermes interface | omit/false; never claim dry-run |
| Compensation/rollback info | Useful but rarely truthful | **Usually unavailable/unknown** | Hermes/app semantics | omit or explicit `unknown/not_supported`; never invent rollback |

## Conclusions
- **v0 remains valid** for `hermes.status.read`; do not bloat or break it implicitly.
- Future mutating capability likely requires **`v1` (or additive, separately versioned) contract/profile** with: per-capability fixed operation spec, side-effect class, explicit idempotency semantics (local vs external), external ID/result fields (nullable, truthful), cancellation semantics (nullable/unsupported), confirmation/authorization binding, and strict evidence provenance — all fail-closed when unknown.
- Unknown/unavailable fields must be represented honestly (`null`/`unknown`/`not_supported`), never inferred.
