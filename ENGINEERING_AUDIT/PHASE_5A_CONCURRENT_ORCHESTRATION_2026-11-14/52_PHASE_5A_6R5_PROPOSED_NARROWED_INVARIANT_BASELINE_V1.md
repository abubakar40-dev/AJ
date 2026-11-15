# AJ — PHASE 5A.6R5
# NARROWED INVARIANT-BASED ACCEPTANCE BASELINE
## Proposed Engineering Contract — Version 1.0

**Status:** PROPOSED — PENDING USER REVIEW AND APPROVAL  
**Decision:** Option 3 — Narrowed invariant-based acceptance baseline  
**Implementation authorization:** NOT GRANTED  
**Next phase:** NOT AUTHORIZED  
**Scope:** AJ internal orchestration and delegation foundation only

---

# 1. PURPOSE

This document establishes the proposed engineering acceptance contract for the AJ orchestration and delegation foundation.

The purpose is to replace an unverified historical acceptance assumption with a smaller, explicit, evidence-based set of engineering invariants.

This is a baseline-definition and acceptance-governance document.

It does not authorize implementation, refactoring, integration, cleanup, or modification of protected repositories.

The objective is to establish what AJ must demonstrably guarantee, what it must refuse to guarantee, and what evidence is required before the delegation foundation can be considered acceptable.

# 2. REQUIREMENT AUTHORITY AND TRACEABILITY

The following distinction is mandatory:

### 2.1 Verified historical engineering direction

The following architectural decisions are retained from the established project history:

- AJ is the orchestration and control plane.
- Task, Operation, Execution, Attempt, Agent, Assignment, Lease, Delegation, and Aggregation represent distinct responsibilities.
- Existing AJ execution and scheduling foundations should be reused rather than duplicated.
- Authorization must fail closed when required information cannot be verified.
- Delegated permissions must never exceed the authority of the parent delegation.
- Parent completion must not falsely represent unresolved required child work as successfully completed.
- Recovery and reconciliation must be bounded and evidence-backed.
- Unsupported distributed-system guarantees must not be claimed.
- JARVIS, HELIX, and Hermes remain independent systems.

### 2.2 Reconstructed historical requirements

The reconstructed 45-scenario matrix and crash windows A–J remain preserved as supporting engineering material.

They are NOT automatically authoritative original requirements.

Their original source, version, date, and provenance were not recovered during Phase 5A.6R5.

They may be used as:
- Test-design references.
- Failure-mode discovery material.
- Supporting regression scenarios.
- Evidence for identifying uncovered behavior.

They must not silently become binding acceptance requirements.

### 2.3 New acceptance authority

This document, after explicit user approval, will become the proposed binding acceptance baseline for the scoped AJ delegation foundation.

Any future modification must be documented through a versioned baseline change with its rationale and impact.

# 3. SCOPE

The acceptance scope is restricted to:

- AJ task and execution orchestration.
- Parent-child task delegation.
- Delegation assignment and permission boundaries.
- Child execution authorization.
- Parent lifecycle enforcement.
- Cancellation behavior.
- Reconciliation and aggregation.
- Recovery and anomaly detection.
- Evidence and auditability.
- Local AJ regression and operational checks.

The scope does not include external agent transport or ecosystem integration.

# 4. MANDATORY ENGINEERING INVARIANTS

Every invariant below is mandatory within its explicitly stated supported operating boundary.

## INV-01 — Authorization must fail closed

AJ must refuse a delegated operation when the required authorization state is missing, malformed, contradictory, revoked, or unverifiable.

Acceptance evidence:
- Missing authorization is rejected.
- Invalid authorization is rejected.
- Revoked delegation is rejected.
- Malformed permission data is rejected.
- No unauthorized child execution occurs through any supported execution entry point.
- Rejection produces traceable evidence where the existing evidence model supports it.

A test covering only one execution path is insufficient to establish universal enforcement.

## INV-02 — Delegated permission narrowing

A child delegation must never receive more authority than its parent delegation permits.

Acceptance evidence:
- Child permissions are restricted to the permitted parent authority.
- Permission expansion is rejected.
- Missing or ambiguous permission data fails closed.
- Permission changes are revalidated at the relevant authorization boundary.
- Tests cover both ordinary and adversarial permission combinations.

Snapshot equality alone is not sufficient proof of current authorization.

## INV-03 — Parent lifecycle correctness

A parent must not be marked successfully complete while required child work remains unresolved or has an outcome that violates the declared completion policy.

Acceptance evidence:
- Pending required child work prevents successful completion.
- Running required child work prevents successful completion.
- Failed required child work is handled according to an explicitly defined policy.
- Cancelled child work is handled according to an explicitly defined policy.
- Contradictory or missing child evidence cannot silently produce successful parent completion.
- Parent state transitions remain consistent with the supported lifecycle rules.

Optional child failure, partial completion, and cancellation semantics must be explicitly defined before their behavior can be certified.

## INV-04 — Cancellation safety

Cancellation must prevent prohibited future delegated preparation and execution.

Acceptance evidence:
- Cancelled parent cannot authorize prohibited new child preparation.
- Cancelled parent cannot authorize prohibited child dispatch.
- Relevant authorization boundaries revalidate current parent and delegation state.
- Cancellation racing with child completion cannot silently produce an invalid terminal state.
- Unsupported race conditions are detected or safely rejected rather than treated as successful.

This invariant does not imply instantaneous cancellation of an already-running external side effect.

## INV-05 — Reconciliation correctness and boundedness

Parent-child reconciliation must be bounded, repeatable, and supported by traceable evidence.

Acceptance evidence:
- Repeated reconciliation does not create duplicate logical outcomes.
- Reconciliation processes only its declared bounded scope.
- Dry-run does not mutate authoritative state.
- Apply operations record their available provenance and outcome.
- Invalid or contradictory records fail closed or produce an explicit unresolved result.
- Read-only monitoring does not modify authoritative records.

Idempotency of AJ-local reconciliation must not be described as exactly-once execution of external side effects.

## INV-06 — Crash and recovery honesty

AJ must not falsely claim that recovery is safe for crash windows that have not been demonstrated.

Acceptance evidence:
- Every supported recovery transition has an explicit precondition.
- Recovery identifies incomplete or ambiguous operations where supported.
- Ambiguous state is not silently converted into success.
- Repeated recovery does not silently duplicate authoritative transitions.
- Recovery behavior is tested at declared persistence boundaries.
- Unsupported recovery cases remain explicitly classified as unsupported or unresolved.

No claim of complete crash recovery is allowed without corresponding restart and persistence-boundary evidence.

## INV-07 — Concurrency and stale-state safety

AJ must not claim mutating concurrency safety beyond what has been demonstrated.

Acceptance evidence:
- Covered concurrent reconciliation operations do not silently produce contradictory authoritative outcomes.
- Stale state cannot silently overwrite a newer authoritative state in the tested operating boundary.
- Relevant transitions are tested under controlled concurrency.
- Process-boundary limitations are documented.
- Unsupported multi-process or distributed concurrency is explicitly rejected or classified as unsupported.

A single in-process barrier test does not establish universal concurrency correctness.

## INV-08 — Anomaly visibility

AJ must identify and expose supported delegation inconsistencies without silently presenting them as healthy state.

Acceptance evidence:
- Missing or inconsistent delegation records can be detected where covered by the implementation.
- Contradictory terminal states can be detected.
- Stuck or ambiguous operations are surfaced where covered.
- Detection results identify the affected records and the available evidence.
- Detection does not silently mutate authoritative state.

Detection and remediation are separate capabilities. Detection success must not be presented as remediation success.

## INV-09 — Evidence and auditability

Important orchestration and delegation decisions must be traceable through the existing AJ evidence model.

Acceptance evidence:
- Relevant operations have correlatable identifiers.
- Available state transitions and reconciliation outcomes are recorded.
- Rejected operations have sufficient evidence for diagnosis where supported.
- Missing evidence is surfaced as uncertainty.
- Evidence records are not silently rewritten to manufacture successful outcomes.

This invariant does not imply atomic transactions across independent stores.

## INV-10 — Honest system boundaries

AJ must accurately represent its actual operating capabilities.

Mandatory restrictions:
- No claim of cross-store atomicity without proof.
- No claim of exactly-once external side effects.
- No claim of distributed correctness.
- No claim of authenticated operator identity from `local_trust`.
- No claim of real remote-agent execution or acceptance without actual transport and independently verifiable evidence.
- No claim that a capability works merely because its source code, dependency, API, or service exists.

Capability maturity must distinguish:
1. Source exists.
2. Dependencies are available.
3. Service starts.
4. Capability executes.
5. End-to-end behavior works.
6. Reliability and security are verified.

# 5. OPERATIONAL AND RESOURCE BOUNDARIES

The current supported target is controlled local AJ operation.

The acceptance baseline does not authorize:
- Docker adoption.
- Background daemon introduction.
- Remote orchestration.
- Multi-machine coordination.
- Unrestricted shell execution.
- Unrestricted Python execution.
- Unrestricted filesystem, browser, messaging, or external tool access.
- Automatic integration with JARVIS, HELIX, or Hermes.

Resource use must remain bounded within the declared local operating model.

Unsupported workloads must be rejected, deferred, or explicitly reported rather than silently accepted.

# 6. STORAGE AND REGRESSION ACCEPTANCE

The known SQLite/WAL failure remains an OPEN issue.

Observed historical failure:
`tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event`

Latest reported full-suite result:
576 passed, 1 failed, 13 warnings.

The failure was intermittent and was not conclusively diagnosed.

Acceptance rules:
- Do not weaken or delete the failing test to obtain a green suite.
- Do not dismiss the failure as harmless.
- Do not claim the filesystem is definitively responsible without reproducible evidence.
- Investigate filesystem, temporary-directory placement, WAL initialization, forked multiprocessing, and test-load sensitivity separately.
- Keep the issue OPEN until its cause is established or a clearly documented, approved limitation and safe operating boundary are established.
- Do not repair, reformat, remount, or migrate the user's filesystem as part of this acceptance work.

A successful isolated test is not sufficient to establish full-suite stability.

# 7. TESTING AND EVIDENCE STANDARD

Every mandatory invariant must have:

1. A written behavioral requirement.
2. Identified supported entry points.
3. Positive tests.
4. Negative and malformed-input tests.
5. Relevant lifecycle or race tests.
6. Evidence of the resulting authoritative state.
7. Explicit limitations.
8. A reproducible command and result.

Every invariant receives one of these classifications:

- VERIFIED — supported by sufficient reproducible evidence.
- PARTIALLY VERIFIED — some behavior demonstrated, meaningful coverage gaps remain.
- UNVERIFIED — insufficient evidence.
- UNSAFE — demonstrated behavior violates the invariant.
- UNSUPPORTED — capability is intentionally outside the accepted operating boundary.

A passing test count alone cannot determine acceptance.

No invariant may be upgraded solely because implementation code exists.

# 8. REGRESSION GATE

The following are required before declaring the scoped foundation acceptable:

- Full applicable AJ regression suite passes.
- Focused delegation, authorization, lifecycle, cancellation, reconciliation, and recovery suites pass.
- `aj --check` passes all applicable checks.
- No unexplained new test failures.
- Existing unrelated failures are identified, investigated, and explicitly dispositioned.
- Repository safety and protected-system boundaries remain intact.
- Final evidence is reproducible.

An intermittent full-suite failure cannot be silently ignored or removed from the report.

# 9. EXPLICIT NON-GOALS

The following are not acceptance requirements for this baseline:

- Universal crash recovery across arbitrary process and machine failures.
- Distributed transactions.
- Exactly-once execution.
- Multi-machine or distributed scheduler correctness.
- Authenticated multi-user identity.
- Real remote-agent transport.
- External service side-effect guarantees.
- Automatic JARVIS/HELIX/Hermes integration.
- Hermes gateway ensure.
- Production-grade multi-tenant security certification.

These may become future requirements through a separately approved scope and architecture decision.

# 10. PROTECTED SYSTEMS AND CHANGE CONTROL

The following boundaries remain mandatory:

- JARVIS remains an independent project.
- HELIX remains an independent project.
- Hermes remains independent and NOT ATTACHED.
- `hermes.gateway.ensure` remains unimplemented, disabled, and unexecuted.
- No protected repository or configuration is modified as part of AJ acceptance work.
- No destructive Git operations.
- No staging, commits, pushes, merges, tags, or history rewriting without explicit approval.
- No destructive migrations, mass deletion, or filesystem repair without explicit approval.

Existing uncommitted and untracked work must be preserved.

# 11. ACCEPTANCE DECISION RULE

The AJ delegation foundation may only be declared ACCEPTED when:

1. The user has approved this baseline.
2. All mandatory invariants are classified VERIFIED within their declared supported boundaries.
3. Unsupported behavior is safely rejected or explicitly outside scope.
4. Required regression gates pass.
5. Open defects have an explicit, evidence-backed disposition.
6. No critical authorization, lifecycle, cancellation, or recovery safety issue remains unresolved.
7. Final reports accurately describe the demonstrated capability and its limitations.

If any mandatory invariant remains PARTIALLY VERIFIED, UNVERIFIED, or UNSAFE, the foundation must remain INCOMPLETE.

A narrowed baseline does not lower the safety standard. It makes the scope explicit and the claims defensible.

# 12. APPROVAL AND IMPLEMENTATION GATE

Current state:

- Option 3 selected by user.
- This document is a proposed interpretation of that decision.
- Baseline approval is pending.
- Implementation authorization has NOT been granted.
- Phase 5A.7 has NOT been authorized.
- No code changes are authorized by this document.

Required next steps:

1. Review this proposed baseline.
2. Clarify any ambiguous policy semantics.
3. Approve or request revisions to the acceptance contract.
4. Only after explicit approval, prepare a scoped implementation and verification plan.
5. Obtain separate authorization before implementation begins.

**END OF PROPOSED ACCEPTANCE BASELINE**
