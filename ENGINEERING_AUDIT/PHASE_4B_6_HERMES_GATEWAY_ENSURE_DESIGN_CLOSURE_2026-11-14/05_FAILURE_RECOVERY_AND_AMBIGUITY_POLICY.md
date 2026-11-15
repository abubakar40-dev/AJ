# 05 — Failure, Recovery, and Ambiguity Policy (Criterion 4)

## Distinctions (must be explicit)

| Concept | Meaning | Implication |
|---|---|---|
| **CLI/process termination (AJ-side or ensure subprocess)** | Local client process ended/killed/timed out | **Does not** imply gateway stopped, cancelled, or rolled back |
| **Gateway process termination** | Target runtime/daemon exits or is stopped | May be intended or failure; verify via read-back; side effects may persist |
| **Remote/runtime cancellation** | Actual runtime accepts and effects cancellation of an operation | **Not established** for ensure lifecycle effects; must not be assumed |
| **Rollback of lifecycle side effect** | Reverting started/replaced service/runtime/state to prior state | Generally **unavailable/unreliable**; must not be assumed |

## Failure-handling matrix (proposed)

| Scenario | Expected observations/verdicts | Default AJ handling | Retry? | Manual intervention? |
|---|---|---|---|---|
| CLI timeout (AJ subprocess budget exceeded) | No final JSON or partial; ensure may still be running/effected start | Mark `timeout` -> `unknown`, record ambiguity, no rollback assumption | **No automatic retry** | Likely if mutating scope possible; observe later separately |
| Gateway startup timeout (`starting/deadline`) | exit 5 / `starting` `deadline` | `timeout` -> `unknown/requires_manual_review` | **No** | Yes, if not converged after safe observation window |
| Partial startup | mixed signals, control not ready, `runtime_exited` after request, service up but endpoint invalid | `requires_manual_review`/`unknown` | **No** | Yes |
| Process crash (`runtime_exited`, daemon dies) | `inaccessible/runtime_exited`, logs/status indicate exit | `failed` if clearly post-attempt and no ambiguity remains; else `requires_manual_review` | Only if state proven safely `stopped/absent` and fresh authorized attempt policy allows (start scope) | Maybe |
| Gateway already running / ready | `ready` attachable | Read-only attach/success classification (no mutation) | N/A (idempotent observation goal, not guaranteed native) | No |
| Runtime replacement (incompatible older owner, conditional) | `draining/replaced` transitions or refusal codes | Treat as **high-risk mutation/ambiguity** unless fully verified end-state; default manual review | **No automatic retry** | Yes |
| Failed read-back | probe errors/timeouts/invalid data | `unknown/requires_manual_review` | No (retrying mutation unsafe); read-only re-observation may be attempted cautiously | Yes if persistent |
| Lost control connection | transient/permanent identify/control failures | Reclassify via fresh observation; if mutating action in-flight/possible -> ambiguous | No auto lifecycle retry | Maybe |
| AJ process interruption (mid-operation) | incomplete local record | On recovery: read-back and reconcile; if unknown -> `requires_manual_review` | No blind retry | Possible |
| Duplicate requests | concurrent ops targeting same profile/resource | Deduplicate/block per AJ policy; if both may have executed -> ambiguous/manual review | No | Maybe |
| Interrupted recovery | recovery step incomplete | Preserve evidence, remain conservative | No | Yes |
| SQLite persistence errors (evidence write) | `disk I/O error` / WAL issues (known risk on NTFS tmp) | Treat persistence outcome as uncertain: do **not** claim durable evidence; fail closed/escalate; avoid unsafe compensating retries | **No** (especially no retry that can duplicate side effects) | Yes; storage remediation separate track |

## Decision rules
- **Default for ambiguous lifecycle side effect:** **conservative** -> `unknown` or `requires_manual_review`, **no automatic retry**, require observation/operator decision.
- **Retry safely only when:** (a) no mutating action was taken, or (b) read-back conclusively proves target in a safe precondition (e.g. clean absent) **and** policy/authorization permits a fresh attempt **as a new attempt**. Never on timeout/partial/unknown.
- **Observe again/wait:** allowed as read-only steps with bounds/backoff when state is transitional (`starting`, `retiring`) and no mutation implied.
- **Stop:** when policy disallows mutation, budget exhausted, or risk unacceptable.
- **No exactly-once execution claim.** No claim that local kill/cancel rolls back runtime side effects.

## Operator recovery expectations (when required)
- Inspect `hermes gateway status/list`, service state, logs, control/state files, and running processes for target profile.
- Confirm single intended owner and readiness before allowing AJ to proceed.
- Resolve storage/persistence issues separately (see doc 09) before relying on durable lifecycle evidence.
