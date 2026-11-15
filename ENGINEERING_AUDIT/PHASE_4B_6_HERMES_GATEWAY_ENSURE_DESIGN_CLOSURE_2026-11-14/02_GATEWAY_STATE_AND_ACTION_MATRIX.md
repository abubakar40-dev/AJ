# 02 — Gateway State and Action Matrix (Criterion 1)

## Evidence basis
- **Verified/4B.5:** `ensure` is stateful (`ensure_gateway_runtime`: discovery-first, may attach/wait/start/spawn/replace conditionally). Read-only status/read-back surfaces exist but can be ambiguous/unavailable.
- **Source observations:** `GatewayDiscovery`/control `identify` states and reason codes include (non-exhaustive) `ready`, `starting`, `draining` (incl retiring/update-paused/replaced/wait cases), `inaccessible` (e.g. `runtime_exited`, control timeout/path issues), `incompatible` (older runtime/replace/refusal cases), `conflict`, `absent`, endpoint/ownership validation paths; service states and multiplex reservation states influence flow.

## AJ-observed state model (proposed, pre-invocation classification)
AJ must classify from bounded read-only observation before any lifecycle action. Classification is **observational**, not a claim of Hermes-native semantics beyond evidence.

| AJ-observed state | Meaning (observational) | Typical evidence signals | Confidence notes |
|---|---|---|---|
| `ready` | Existing runtime attachable/serving expected profile and healthy enough by control contract | Valid control `identify`/endpoint, `attachable`/ready verdict, matching profile/home/identity/protocol/capabilities as applicable | Strongest available; not proof of all internal component health |
| `starting` | Runtime start/transition in progress, outcome not final | `starting` verdict, service starting, spawned child pending, control not yet ready | Ambiguous duration/outcome |
| `stopped` / `absent` | No serving owner observed for target profile | `absent` discovery, no attachable endpoint/service running for scope | May race with concurrent starts |
| `unavailable` | Endpoint/service/control not reachable or unusable | `inaccessible` (permissions/refused/timeout/invalid response/runtime exited contexts) without clear stopped-only proof | Cause-specific handling required |
| `retiring` | Owner draining/exiting/replaced/idle-exit path in progress | `draining` with retiring reason codes (e.g. `idle_exit`, `replaced`, update/parked cases) | May become absent then ready/other |
| `incompatible` | Owner/protocol/profile/install mismatch requiring refusal or special handling | `incompatible` verdict/reasons (older/newer protocol, foreign install, unverified owner, replace refusal details) | Mutating replace only in narrowly evidenced cases; often manual |
| `partially_started` | Side effects may exist but readiness/read-back incomplete or contradictory | `starting` past budget, `runtime_exited` after start attempt, process/service present but control not valid/ready, mixed signals | Must be treated as ambiguous |
| `unknown` | Insufficient evidence to classify safely | Missing/partial observation, internal AJ error in classification | Fail closed |
| `readback_unavailable` | Observation channels required for safe decision not obtainable | Control/status query failure/timeout/denied, corrupted/unreadable state, tool/probe failure | Fail closed |

## State-to-action matrix (proposed, default fail-closed)

| Observed state | Read-only observation | Attach to existing runtime | Lifecycle mutation (ensure/start/replace) | Ambiguous/manual review | Default AJ action (future capability, if ever authorized) | Permission gate (split, proposed) |
|---|---|---|---|---|---|---|
| `ready` | Yes | **Allowed (preferred)** | No | No | Attach/use existing runtime; no start/replace | `observe` + `attach` |
| `starting` | Yes | No (not ready) | No (no parallel start) | Possible if exceeds policy/budget | Observe/wait with bounded budget & re-readback; no blind retry/start | `observe` |
| `stopped` / `absent` | Yes | No | **Possible but mutating** (service start or unmanaged spawn may occur) | No (if clearly absent) but race-sensitive | **Default: do not mutate.** Only explicit `start`-authorized lifecycle action in approved scope/profile; otherwise reject/fail-closed | `observe` + explicit `start` |
| `unavailable` | Yes | No | No by default | **Yes** | Fail closed -> `requires_manual_review`/`unknown` depending evidence; no start | `observe` |
| `retiring` | Yes | No | No immediate start; replacement wait may be needed after exit | Possible | Observe/wait boundedly for transition, then reclassify; no forced mutation | `observe` |
| `incompatible` | Yes | No | **Only conditional replace path is mutating/risky** | **Often yes** | Fail closed/manual review by default; replace only if separately permitted, evidenced same-install older-owner case, and verification possible | `observe` (+ explicit `replace` only if ever allowed) |
| `partially_started` | Yes | No | No further blind mutation/retry | **Yes (mandatory)** | `requires_manual_review`/`unknown`; observe/read-back only; no auto-retry | `observe` |
| `unknown` | Limited | No | No | **Yes (mandatory)** | Fail closed `unknown`/`requires_manual_review` | none beyond safe diagnostics |
| `readback_unavailable` | Failed/unreliable | No | No | **Yes (mandatory)** | Fail closed `unknown`/`requires_manual_review` | none beyond safe diagnostics |

## Rules (normative for design)
- **Do not treat every non-ready state as permission to start.** `stopped/absent` is the only class where start may be considered, and only under explicit mutating authorization/scope.
- **Unknown or contradictory state must fail closed.** No lifecycle mutation, no success claim.
- **Observation vs mutation split:** `observe/attach` are read-only/control-plane observations in intent; `start/replace` are lifecycle mutations with side effects and ambiguity.
- **Concurrency compatibility:** pre-invocation classification and any future action must be per-target-resource/per-profile with independent operation identity; no global serial queue implied.

## Open uncertainties
- Exact Hermes-internal states beyond observed verdicts (profile/platform-specific).
- Distinguishing clean `stopped` from transient absence during races without stronger atomic/read-after-observe guarantees.
- Completeness of detection for `partially_started` across all failure modes.
