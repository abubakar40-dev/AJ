# PROOF_SPECS (S0 E3)

Purpose: executable proof specifications for INV-01..INV-10 and T-01..T-12 (Doc 54 / Doc 58 intent). Each item states setup, invocation, authoritative persisted record(s), expected result, forbidden result, stage (S1–S4) for implementation/proof, and covering test (existing/new). Items that cannot honestly be tested are marked explicitly. **No implementation performed in S0.**

## Round 4 refresh note (2026-11-15 context)
- Stale "pending approved mapping" statements refreshed to reflect that D2 outcome semantics are approved in Doc 58 / `58_POLICY_DECISIONS.md`; implementation/proof remains incomplete. No "COMPLETE" claim added.

## Legend
- **Authoritative persisted record:** record(s) that constitute ground truth for the assertion (tasks.jsonl, delegations.jsonl, assignments.jsonl, scheduler_decisions.jsonl, leases/state, receipts/journal/audit where applicable).
- **Stage:** planned stage to implement/fix and/or prove (S1 policy/model, S2 authz/scheduler/admin guards, S3 lifecycle/cancel/reconcile, S4 crash/concurrency feasible boundaries). S0 = spec/evidence only.
- **Status note:** `UNTESTABLE NOW` = cannot honestly be tested without seams/decisions/mechanisms not present; must not be claimed VERIFIED.

## INV-01 — Authorization must fail closed
| Field | Spec |
|---|---|
| Setup | Delegated parent+child (real Aj/TaskStore/Scheduler, persisted /tmp). Construct cases: valid current delegation/permission/linkage; missing/malformed/revoked delegation record; parent cancelled/revoked/aborted/dead_letter; child unlinked; widened/contradictory permission envelope; unverifiable state. |
| Invocation | Exercise each supported entry point: delegation prep/authorization, scheduler eligibility/admission+pre-dispatch under lease, resume/execute boundary, retry/recover/reconcile/CLI-admin paths as applicable per inventory disposition. |
| Authoritative persisted record | `tasks.jsonl` (child/parent status, events, authorization_context/delegation evidence), `delegations.jsonl`, `assignments.jsonl`, `scheduler_decisions.jsonl`, audit/receipt/journal where emitted. |
| Expected | Valid+current state may proceed only where authorized; all invalid/missing/malformed/revoked/unverifiable/widened/contradictory cases **rejected or deferred** with traceable reason/evidence; no unauthorized child execution/dispatch. |
| Forbidden | Unauthorized dispatch/execution; success on unverifiable/missing/revoked authority; silent widening; dispatch when parent cancelled/revoked or delegation inactive/unlinked. |
| Stage | S1/S2 (classification/guards/scheduler/admin blocking), S4 for race timing where feasible. |
| Covering test | Existing: partial coverage in delegation/scheduler tests (some now corrected for real reasons post D-001). New/needed: per-path negative matrix incl. `tests/s0_proof/test_s0_characterization.py::test_a2a_*`, `a2b`, `a2c`, `a3` (currently xfail characterizations) and exhaustive path tests per inventory S2-FIX/BLOCK-PER-D4 items. |
| Untestable now? | **Exhaustive “every supported/alternative/administrative path” untestable now** until inventory fully closed and all paths guarded/blocked; dynamic external revocation/IAM-style proofs **NOT VERIFIABLE/UNSUPPORTED**. |

## INV-02 — Delegated permission narrowing
| Field | Spec |
|---|---|
| Setup | Delegation requests with explicit permission contexts: valid narrowing intersections; missing/malformed/ambiguous contexts; widened requested/effective sets; contradictory snapshots; post-assignment reduction/revocation scenarios. |
| Invocation | `Aj.delegate` validation/creation; prep/authorization boundaries; execution guard revalidation; any mutation path touching permission envelope. |
| Authoritative persisted record | `delegations.jsonl` (request/evidence), child task `authorization_context.delegation.permission_decision` snapshots in `tasks.jsonl`, assignment records. |
| Expected | Effective permissions = intersection/narrowing-only; missing/malformed/unverifiable/widened/contradictory rejected fail-closed; boundary revalidation against current state per approved design. |
| Forbidden | Privilege escalation/widening; acceptance of malformed/ambiguous permission data; snapshot-only equality treated as sufficient where revalidation required. |
| Stage | S1 (model/validation) + S2 (boundary revalidation). |
| Covering test | Existing: delegation foundation/closure tests cover parts. New: `test_a6` aspects (classification context) indirect; dedicated narrowing/adversarial matrix needed. |
| Untestable now? | Full current-source revalidation across all boundaries **NOT VERIFIABLE** until implemented/proven. |

## INV-03 — Parent lifecycle correctness
| Field | Spec |
|---|---|
| Setup | Parent with required/optional children (per D1 once implemented): children in completed/failed/cancelled/unresolved/ambiguous/missing/unloadable/contradictory states; aggregation policies (all_required, subset_required, any_sufficient). |
| Invocation | Child transitions, reconciliation, and parent completion attempts including direct `tasks.transition(..., COMPLETED, force=True)` and any other completion-capable path. |
| Authoritative persisted record | Child+parent `tasks.jsonl` states/events, `delegations.jsonl` reconciliation evidence/aggregation snapshots. |
| Expected | Parent COMPLETED only when all required COMPLETED and no unresolved child remains (per D2); required failed/cancelled => cannot complete (reconcile moves parent to FAILED with evidence as specified); unresolved/ambiguous required => blocked + manual review; optional semantics per D2; **guard applies regardless of `force=True`**. |
| Forbidden | False completion with unresolved/failed/cancelled required child; partial-success mapped to COMPLETED; silent optional default for missing/malformed classification. |
| Stage | S1 (classification/state mapping) + S3 (guards/reconcile semantics). |
| Covering test | Existing: post D-001 completion guard now real in covered cases. New/needed: `test_a5` (xfail), `test_b5` (PASS for current aggregation block), `test_a6`/T-04, full D1/D2 matrix. |
| Untestable now? | D2 outcome semantics are approved in Doc 58 / `58_POLICY_DECISIONS.md`, but implementation/proof not complete; cannot claim full conformance until implemented and proven across all paths. |

## INV-04 — Cancellation safety
| Field | Spec |
|---|---|
| Setup | Delegated parent with non-terminal children in various states (AUTHORIZED, EXECUTING, WAITING_FOR_APPROVAL, etc.), active assignments; in-flight dispatch/recovery windows where feasible. |
| Invocation | `cancel_task(parent)` / cancellation transitions; scheduler dispatch attempts; child prep/resume/retry/recover; late child completion/failure outcomes; recovery after cancellation. |
| Authoritative persisted record | Parent/child `tasks.jsonl`, `delegations.jsonl`/assignment state, scheduler decisions/leases, audit/journal evidence. |
| Expected | Durable parent cancellation prevents prohibited prep/dispatch; parent cancel propagates to non-terminal children via child cancel flow (EXECUTING => CANCEL_REQUESTED cooperative) with delegation evidence and assignment updates (D4); no resurrection of prohibited work; ambiguous outcomes unresolved/non-success. |
| Forbidden | Dispatch/prep/execute under cancelled/revoked parent authority; children left silently active/orphaned; late outcomes silently creating success or overwriting authoritative terminal states. |
| Stage | S2 (scheduler/dispatch guards) + S3 (orchestration/cancel propagation) + S4 (race boundaries). |
| Covering test | `test_a2a/a2b/a2c` (xfail), `test_a3` (xfail), `test_a4` (xfail); existing scheduler/guard tests partial. |
| Untestable now? | True race/late-outcome/interruption safety **needs S4 seams/boundaries**; instant stop of external side effects **UNSUPPORTED**. |

## INV-05 — Reconciliation correctness and boundedness
| Field | Spec |
|---|---|
| Setup | Delegations with consistent, unchanged, stale, contradictory, or partially missing records; concurrent mutating/apply calls (single-process controlled); dry-run vs apply. |
| Invocation | `reconcile_delegation_parent` / `Aj.reconcile_delegation_parent` (dry-run, apply), monitoring/status reads, anomaly detection; repeated calls. |
| Authoritative persisted record | `delegations.jsonl` evidence/history/reconciliation markers, affected `tasks.jsonl`/assignment records when apply mutates. |
| Expected | Idempotent/no-op on unchanged state; dry-run no authoritative mutation; apply records provenance/outcome; bounded batch respected; contradictions/unverifiable inputs fail closed or explicit unresolved; read-only monitoring non-mutating. |
| Forbidden | Duplicate logical outcomes; dry-run/monitor mutation; unbounded processing claims; silent auto-repair of unverifiable contradictions. |
| Stage | S3 (correctness/safety) + S4 (concurrency/stale-writer where feasible). |
| Covering test | Existing r2/r3/r4 reconciliation tests cover parts; need contradiction/stale-writer/duplicate-apply race matrix. |
| Untestable now? | Proven stale-writer protection and multi-store interruption atomicity **NOT VERIFIABLE** without mechanisms/seams. |

## INV-06 — Crash and recovery honesty
| Field | Spec |
|---|---|
| Setup | Persisted states at derived boundaries (see CRASH_FEASIBILITY): interrupted task transitions, dispatch intent/lease/start/result splits, delegation multi-record writes, recovery-required/abandoned/ambiguous records. |
| Invocation | Process restart/reload, `RecoveryManager`/recover flows, scheduler re-evaluation, reconciliation/inspection. |
| Authoritative persisted record | All relevant append-only stores on disk at interruption point and after recovery attempt. |
| Expected | Supported boundaries recover or become explicitly unresolved/manual-review with evidence; no silent success; no duplicate authoritative transitions on repeated recovery. |
| Forbidden | Fabricated success from ambiguous/incomplete state; resurrection of prohibited work; claiming recovery for unsupported boundaries. |
| Stage | S4 (feasible boundaries only) + S5 constraints for storage. |
| Covering test | `test_a1`, `test_a1b` (xfail characterizations for ABANDONED/load/resurrection gap); existing recovery tests partial. |
| Untestable now? | **Most crash windows NOT VERIFIABLE/need S4 seams**; OS/power/fs failures **UNSUPPORTED**; original A–H **UNRECOVERED**. |

## INV-07 — Concurrency and stale-state safety
| Field | Spec |
|---|---|
| Setup | Controlled single-process concurrent operations: mutating reconciliations, dispatch attempts, cancel-vs-complete, recovery-vs-dispatch, duplicate apply, assignment/execution mutations (where representable). |
| Invocation | Thread/process-coordinated harness within declared boundary; repeated runs. |
| Authoritative persisted record | Task/delegation/assignment/lease/scheduler ledgers showing consistent final state and no contradictory authoritative outcomes. |
| Expected | No silently contradictory authoritative outcomes; no stale overwrite in demonstrated boundary; idempotent handling where specified. |
| Forbidden | Universal concurrency/multi-process/distributed correctness claims; silent corruption/duplication. |
| Stage | S3/S4 (mechanism-backed tests within feasible boundary). |
| Covering test | Some concurrent reconciliation tests exist; sqlite/storage concurrency experiments (E6) are storage-specific. |
| Untestable now? | Multi-process/distributed and many race classes **NOT VERIFIABLE/UNSUPPORTED**; stale-writer mechanism proof pending. |

## INV-08 — Anomaly visibility
| Field | Spec |
|---|---|
| Setup | Inject/construct supported anomaly classes: missing/inconsistent delegation records, contradictory terminal states, stuck/ambiguous operations, stale aggregation, incorrect completed parent, missing linkage/provenance, expired/uncertain lease (detectable). |
| Invocation | `detect_delegation_anomalies` / `delegation_monitor` / inspection APIs (read-only). |
| Authoritative persisted record | Unchanged authoritative stores before/after detection; monitor findings with ids/evidence. |
| Expected | Each supported anomaly detected/surfaced with affected ids and available evidence; detection read-only. |
| Forbidden | Silent mutation by detection; presenting known inconsistencies as healthy. |
| Stage | S3 (detector completeness) + S4 where anomaly arises from races/crash. |
| Covering test | Existing anomaly/monitor tests partial; full class-by-class fixtures needed. |
| Untestable now? | Complete coverage/certification for all classes **UNVERIFIABLE** now. |

## INV-09 — Evidence and auditability
| Field | Spec |
|---|---|
| Setup | Operations across authorize/reject/dispatch/cancel/reconcile/recover/transition paths including failures and ambiguities. |
| Invocation | Execute each supported decision path. |
| Authoritative persisted record | Correlatable ids and records across tasks, attempts, executions, assignments, delegations, receipts/journal/audit/operation-evidence as applicable. |
| Expected | Traceable, non-fabricated evidence for decisions and rejections/ambiguities; missing evidence surfaced as uncertainty. |
| Forbidden | Evidence rewritten to claim success; atomic cross-store guarantees claimed. |
| Stage | S1–S4 (cross-cutting). |
| Covering test | Existing tests touch evidence; comprehensive per-decision matrix missing. |
| Untestable now? | Full coverage across every supported path **UNVERIFIABLE** now. |

## INV-10 — Honest system boundaries
| Field | Spec |
|---|---|
| Setup | Requests/claims for unsupported capabilities: remote agent transport/execution, exactly-once external effects, cross-store atomicity, authenticated identity, Hermes attachment, distributed correctness. |
| Invocation | Delegation/CLI/runtime/reporting surfaces where such claims could be made or accepted. |
| Authoritative persisted record | Request/response records, task/delegation evidence, logs/reports showing rejection or explicit UNSUPPORTED reporting. |
| Expected | Rejected/blocked or explicitly reported **UNSUPPORTED**; no silent acceptance or false capability claim. |
| Forbidden | Silent acceptance of unsupported claims; reporting success/capability without proof. |
| Stage | S1/S2 (validation/guards/reporting). |
| Covering test | `test_a7_t11_unsupported_capability_claim_rejected` (xfail characterization: remote agent transport claim currently accepted). |
| Untestable now? | All possible surfaces not exhaustively enumerated (**inventory closure required**). |

---

## T-01 — Authz paths positive/negative
- **Setup:** Valid vs missing/malformed/revoked/widened delegation & permission contexts for each supported path (prep, scheduler eligibility, dispatch/lease recheck, resume/execute, retry/recover, reconcile/admin as applicable).
- **Invocation:** Call each path with constructed contexts.
- **Authoritative persisted record:** Task/delegation/assignment/scheduler decision/audit records showing decision and no side effects on reject.
- **Expected:** Authorized only on valid/current; otherwise fail closed/defer/reject.
- **Forbidden:** Unauthorized execution/dispatch; success on invalid state.
- **Stage:** S1/S2. **Covering test:** partial existing; needs exhaustive matrix (see A2/A3). **Untestable now:** until all paths enumerated/blocked.

## T-02 — Revocation/cancellation lifecycle/race
- **Setup:** Post-assignment revocation or durable parent cancellation before/at prep/dispatch/execute/retry/recover.
- **Invocation:** Timed sequences (and race harness where feasible).
- **Authoritative persisted record:** State transitions, scheduler decisions, guard outcomes, lease/dispatch evidence.
- **Expected:** Prohibited actions blocked; no success.
- **Forbidden:** Prep/dispatch/execute after durable cancellation/revocation.
- **Stage:** S2/S3/S4. **Covering test:** A2/A3/A4 (xfail). **Untestable now:** race timing proofs need S4 seams.

## T-03 — Parent outcome / required vs optional
- **Setup:** Required satisfied vs pending/running/failed/cancelled/unresolved/ambiguous; optional cases per explicit policy.
- **Invocation:** Child outcomes + reconciliation + parent completion attempts (incl. force).
- **Authoritative persisted record:** Child/parent tasks, aggregation evidence.
- **Expected:** COMPLETED only when policy satisfied; never unsafe/partial-as-success.
- **Forbidden:** False completion, partial-as-success.
- **Stage:** S1/S3. **Covering test:** A4/A5/B5/A6. **Untestable now:** D2 mapping approved (Doc 58), but not implemented/proven for all cases.

## T-04 — Missing/malformed/contradictory classification
- **Setup:** `child_spec.required` missing, non-bool (`"maybe"`, 0/1, null), contradictory with `required_child_ids`/policy as applicable.
- **Invocation:** `Aj.delegate` creation/validation.
- **Authoritative persisted record:** `delegations.jsonl` request/evidence (or rejection evidence/error).
- **Expected:** Missing => required true + `classification_source=default_required`; non-bool => validation rejection; legacy read-time default without persisted rewrite.
- **Forbidden:** Silent optional default; accepting malformed classification.
- **Stage:** S1. **Covering test:** `test_a6_t04...` (xfail). **Untestable now:** legacy compatibility behavior until implemented.

## T-05 — Cancel vs completion/dispatch/recovery/prep; late outcome
- **Setup:** Races and sequences: cancel concurrent with child completion/dispatch/recovery/prep; late child outcome after cancel; resurrection attempts.
- **Invocation:** Interleaved operations (controlled harness).
- **Authoritative persisted record:** Task/assignment/delegation/scheduler/lease evidence timeline.
- **Expected:** No invalid overwrite/success/resurrection; outcomes traceable or unresolved.
- **Forbidden:** Prohibited prep/dispatch, silent success, resurrection.
- **Stage:** S3/S4. **Covering test:** A2/A3/A4 (xfail, partial). **Untestable now:** deterministic race/late-outcome proofs need seams.

## T-06 — Reconciliation idempotency/bounds/contradictions
- **Setup:** Repeated reconcile, dry-run, apply, batch bounds, contradictory/stale/duplicate concurrent actions.
- **Invocation:** `reconcile_delegation_parent` variants and concurrent calls.
- **Authoritative persisted record:** Delegation reconciliation history/evidence, record snapshots.
- **Expected:** Idempotent/no-op on unchanged; no mutation in dry-run; bounded; fail-closed on contradictions.
- **Forbidden:** Duplicate logical outcomes, mutation in dry-run, unbounded work, silent corruption.
- **Stage:** S3/S4. **Covering test:** existing reconciliation tests partial. **Untestable now:** stale-writer/concurrent proofs limited.

## T-07 — Restart/persistence-boundary recovery
- **Setup:** Declared supported interruption boundaries (derived, CRASH_FEASIBILITY) and ambiguous cases.
- **Invocation:** Simulated interruption/restart (seam or boundary-specific harness) then recovery.
- **Authoritative persisted record:** Durable pre/post store states and recovery outcomes.
- **Expected:** Recover or explicit unresolved/manual-review; never silent success/duplication.
- **Forbidden:** Fabricated success, duplication.
- **Stage:** S4. **Covering test:** A1/A1b (xfail). **Untestable now:** most boundaries need S4 seams; original A–H unrecovered.

## T-08 — Controlled concurrency/races
- **Setup:** Completion-vs-cancel, recovery-vs-dispatch, stale writer, duplicate apply (single-process declared boundary).
- **Invocation:** Controlled concurrent harness.
- **Authoritative persisted record:** Consistent authoritative records/snapshots/logs.
- **Expected:** No contradictory authoritative outcome/silent overwrite.
- **Forbidden:** Multi-process/distributed claims; silent corruption.
- **Stage:** S4. **Covering test:** limited existing. **Untestable now:** many races/seams unavailable.

## T-09 — Anomaly detection (supported classes)
- **Setup:** Each supported anomaly class present vs healthy state.
- **Invocation:** Monitor/detection APIs.
- **Authoritative persisted record:** Findings with ids/evidence; authoritative stores unchanged.
- **Expected:** Detected/surfaced accurately; read-only.
- **Forbidden:** Mutation, false healthy presentation.
- **Stage:** S3. **Covering test:** existing partial. **Untestable now:** full certified class coverage.

## T-10 — Evidence/traceability for decisions and failures
- **Setup:** Key decisions and rejections/ambiguities across supported paths.
- **Invocation:** Execute paths.
- **Authoritative persisted record:** Correlated task/execution/delegation/assignment/receipt/journal/audit records.
- **Expected:** Traceable evidence; uncertainty surfaced; no fabricated success.
- **Forbidden:** Missing evidence treated as success, cross-store atomicity claims.
- **Stage:** S1–S4. **Covering test:** partial. **Untestable now:** exhaustive coverage.

## T-11 — Unsupported capability/claim attempts
- **Setup:** Unsupported claims/capabilities: remote agent transport, exactly-once external effects, cross-store atomicity, authenticated identity, Hermes attachment, distributed correctness.
- **Invocation:** Submit via delegation/other relevant surfaces.
- **Authoritative persisted record:** Rejection/error or explicit UNSUPPORTED response/evidence; no created capability effect.
- **Expected:** Rejected/blocked or explicitly reported **UNSUPPORTED**.
- **Forbidden:** Silent acceptance or false capability.
- **Stage:** S1/S2. **Covering test:** `test_a7_t11_unsupported_capability_claim_rejected` (xfail; attempts remote agent transport claim). **Untestable now:** all surfaces not enumerated.

## T-12 — SQLite/WAL investigation/disposition
- **Setup:** Path/FS variants and concurrency/init modes per matrix; targeted concurrent memory writer test with controlled env.
- **Invocation:** `sqlite_wal_experiment.py` matrix; repeated `test_concurrent_memory_writers_keep_every_event` (E6 runs).
- **Authoritative persisted record:** `sqlite_wal_matrix_results.json`, `sqlite_wal_matrix_summary.txt`, `E6_ntfs_default_tmpdir.json`, `E6_ntfs_tmpdir_tmp.json`, suite logs.
- **Expected:** Facts recorded; hypotheses labelled; no false stability claim.
- **Forbidden:** Fix in S0, weakening tests, claiming resolved without disposition.
- **Stage:** S5 (experiments/disposition), constrains certification. **Covering test:** N/A (investigation). **Untestable now:** definitive root-cause attribution not complete (**OPEN**).
