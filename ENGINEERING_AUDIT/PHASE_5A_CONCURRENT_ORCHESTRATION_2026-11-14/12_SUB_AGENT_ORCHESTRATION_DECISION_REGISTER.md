# 12 — Sub-Agent & Execution Orchestration Decision Register (Stage 5A.3)

**Status:** Proposed decisions and open questions only. **No decisions here are approved architectural changes or implementation authorizations.**  
**Legend:** *Verified current behavior* = evidenced in current source/tests/docs; *Proposed design* = recommended future architecture; *Open question* = insufficient evidence/needs later stage; *Deferred decision* = intentionally later.

---

## A. Verified current behavior (baseline)

| ID | Item | Evidence | Notes |
|---|---|---|---|
| EV-A01 | AJ “agents” are logical in-memory adapters/registry entries (JARVIS/HELIX) with TCP probe and honest rejection when unreachable or no agreed transport; `AgentRequest/AgentResult` contracts exist | `aj/agents.py`, `aj/contracts.py`, `aj/runtime.py::_check_agents` context, `tests/test_orchestrator.py` | No real sub-agent instance lifecycle/capacity/heartbeat/assignment ledger. |
| EV-A02 | Execution is implicit in orchestrator task flow (`_execute` for internal/calling/HERMES port/agent delegation), not a first-class persisted entity; no `execution_id` | `aj/orchestrator.py`, `aj/execution.py`, `aj/task.py`, `aj/receipts.py`, `aj/journal.py`, 5A.1 `02` | Attempts/receipts/journal provide partial correlation only. |
| EV-A03 | `TaskStore.child_of` and parent/root/dependency fields exist, but no orchestrated parent-child delegation/dispatch/aggregation workflow observed | `aj/task.py`, `aj/orchestrator.py` grep/inspection | Data primitive ≠ orchestration capability. |
| EV-A04 | Per-task execution leases, scheduler-claimed resume, and recovery/consistency/invariant checks provide partial coordination/evidence, but cross-store non-atomic and restart/ambiguity cases remain | `aj/lease.py`, `aj/scheduler.py`, `aj/recovery.py`, `aj/consistency.py`, `aj/invariants.py` | No duplicate-proof external guarantees. |
| EV-A05 | Authorization/permissions are task-level and fail-closed in inspected paths; `local_trust` is not authenticated identity; delegation-specific inheritance/narrowing/provenance not implemented | `aj/permissions.py`, `aj/authorization.py`, `aj/orchestrator.py`, 4B.3–4B.6 | Child must not gain authority by delegation (principle). |
| EV-A06 | Hermes boundary remains read-only `status.read`, default-disabled/fail-closed, AJ↔Hermes NOT ATTACHED; `gateway.ensure` unauthorized; JARVIS/HELIX boundaries preserved | 4B.3–4B.6, `aj/runtime.py`, `aj/hermes_*`, `aj --check` | No runtime lifecycle/capability expansion. |
| EV-A07 | Stage 5A.2 scheduler/admission architecture is proposed (not implemented): eligibility→admission→dispatch separation, bounded capacity/resource-aware/fail-closed gating, Option D staged direction | `06`–`09` | 5A.3 must remain consistent. |

---

## B. Proposed design decisions

| ID | Proposed decision | Existing evidence | Alternatives considered | Rationale | Trade-offs | Resource implications | Security implications | Reliability implications | Required for first implementation | Deferrable | Confidence | Evidence that could invalidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AD-01 | Adopt **Hybrid delegation model (Model C)**: parent creates child Tasks for logically distinct work; each Task may have 0..N Executions and each Execution 0..N Attempts | 5A.1 gaps (no execution entity), `child_of` primitive exists, 20 scenarios ambiguous/not representable | A child-tasks only; B multi-execution only; complex actor graph | Best identity clarity, auditability, retries/aggregation flexibility, compatibility with 5A.1/5A.2 | More entities/records/coordination logic | Moderate metadata/storage growth (bounded by caps) | Clearer per-scope authz/provenance boundaries | Reduces ambiguity in fan-out/retry/recovery | **Yes (conceptual foundation)** | No | High | Evidence that simpler model satisfies all concurrency/aggregation/safety cases without ambiguity |
| AD-02 | Introduce first-class **`execution_id`** (AJ-owned stable dispatch instance) distinct from task/attempt/agent/runtime/process identities | EV-A02, 5A.1 PD-01, scenarios 1,2,11,12,15,16,17 | Overload attempt/lease/task IDs; keep implicit execution | Enables unambiguous assignment, cancellation scope, duplicate detection, and evidence correlation for concurrency | Schema/store evolution, migration/compat complexity | Additional durable records/events | Better scoped control/audit | Major improvement in reconciliation correctness | **Yes** | No | High | Proof existing IDs are sufficient and unambiguous under concurrent multi-execution |
| AD-03 | Treat **Attempt** as first-class per-execution try with immutable outcome lineage; retries create new attempts (and/or new dispatch per policy) | EV-A02/EV-A04, 5A.1 PD-02 | Mutable single attempt record; counter-only | Honest history, safer recovery/analysis, supports unknown outcomes | More records/storage | Small | Preserves evidence integrity | Avoids loss/overwrite of failure context | **Yes** | No | High | Strong evidence current attempt model is sufficient without ambiguity |
| AD-04 | Model **Agent as logical capability/profile** in AJ; treat runtime/worker/process/session as transient observed holders correlated by evidence | EV-A01, `aj/agents.py`/leases worker_id | Persist process/PID as primary identity; opaque external agent objects as AJ truth | Replaceable adapters, restart-safe reasoning, clear AJ-vs-runtime ownership | Must maintain correlation/heartbeat evidence quality | Low | Avoids trusting unstable/process-local identity as authority | Prevents stale-instance ownership errors | **Yes** | No | High | Need for durable agent-instance identity proven by runtime behavior |
| AD-05 | Assignment flow: **Eligibility → Admission → Capability/Permission match → Persist dispatch intent → Claim lease/assignment → Runtime handoff → Evidence** (single decision ownership, consistent with 5A.2) | 5A.2 `07`/SD-01..04, EV-A04 | Direct dispatch from authorized tasks; parallel admission/placement authorities | Prevents conflicting decisions, enforces fail-closed gates, enables audit/recovery | Coordination complexity/latency | Bounded by budgets; avoids wasted work | Enforces deny-by-default and narrowing before handoff | Improves restart/ambiguity handling | **Yes** | No | High | Evidence of safe simpler flow without split responsibilities |
| AD-06 | Capability matching and **permission inheritance by intersection/narrowing only** (never amplification); parent cannot delegate unpossessed/unauthorized capabilities | EV-A05, `Authorizer`/`local_trust` limits, scenarios 7,18,20 | Full inheritance by default; runtime-only enforcement | Least privilege, predictable delegated authority, safer fan-out | May require explicit grants/approvals for legitimate work | Minimal | **Core security control** | Reduces unsafe/unauthorized execution scope | **Yes** | No | High | Verified stronger authn/authz infrastructure changing trust model (future) |
| AD-07 | Separate lifecycles/state semantics for **Task, Execution, Attempt, Agent(logical)** (and assignment/lease) rather than one machine | 5A.1/5A.2 findings, scenarios 7–10,13–17 | Single unified status enum | Prevents semantic conflation (local cancel vs external unknown, agent health vs execution outcome) | More modeling/validation rules | Low-moderate | Clearer auditability of control actions | Correct recovery/aggregation decisions | **Yes** | No | High | Formal proof a unified model is unambiguous and sufficient |
| AD-08 | Cancellation/distinction model: requested vs local-completed vs externally-confirmed vs unknown; scoped to attempt/execution/task/descendants per policy | Task cancel behavior today, 4B/5A honesty rules, scenarios 7–9 | Treat local stop as cancelled; always cascade | Honest handling of external/ambiguous effects, scoped blast radius | More states/operator involvement | Avoids unnecessary teardown/restart churn | Prevents false claims enabling unsafe follow-ups | Avoids unsafe retries/duplication | **Yes** | No | High | Runtime contracts providing verifiable cancellation guarantees |
| AD-09 | Aggregation: parent never succeeds on dispatch; outcomes require verified correlated evidence; initial policies `all_required`, `best_effort`, `manual_review` | EV-A03, scenarios 1,5,6,20 | Optimistic parent completion; full quorum/weighted in v1 | Correctness and honesty for partial/unknown results | Slower/stricter completion in ambiguous cases | Minimal | Prevents authority/success laundering | Avoids false-positive completion | **Yes (basic semantics)** | Quorum/weighted deferred | High | Product requirements mandating different default semantics with safety proof |
| AD-10 | Recommend **Option D: Hybrid staged architecture** (AJ-owned orchestration state + stable adapter boundary; in-process/logical first, supervised/runtime-backed/process-isolated only when evidenced/authorized) consistent with 5A.2 SD-07 | Current in-process reality, 8 GB/NTFS constraints, Hermes/JARVIS/HELIX boundaries | A only, B now, C now | Best fit for constraints, incremental hardening, boundary preservation | Slower path to strong isolation | Lowest initial footprint | Smaller initial attack/ops surface | Controlled evolution with fail-closed gates | **Yes (direction)** | Stronger isolation stages | High | Sustained evidence requiring immediate process/runtime isolation outweighing costs |

---

## C. Open questions

| ID | Question | Why it matters | Evidence needed | Likely stage |
|---|---|---|---|---|
| OQ-A01 | Minimal durable schema/records for `execution_id`, dispatch intent, and assignment compatible with append-only stores and non-atomic persistence | AD-02/AD-05, scenarios 12,15,16 | 5A.4 persistence design + failure analysis | 5A.4 |
| OQ-A02 | Aggregate task completion policy details for mixed child/execution outcomes (required/optional/critical children, timeout behavior) | AD-01/AD-09, scenarios 5,6,20 | Product semantics + workflow examples | 5A.4/5A.5 |
| OQ-A03 | Safe, evidence-backed lease/heartbeat/timeout defaults and renewal responsibility per execution/attempt on 8 GB/NTFS | Reliability, scenarios 13,15 | Controlled measurement (authorized) + runtime behavior | pre-impl verification / 5A.4 |
| OQ-A04 | How to represent and enforce descendant cancellation cascade without affecting unrelated work or assuming external stop | AD-08, scenarios 7–9 | Detailed state/permission/runtime contract design | 5A.4/5A.5 |
| OQ-A05 | What correlation contract is feasible for future Hermes-backed executions (IDs/progress/cancel/outcomes) without implying guarantees now | AD-04/AD-08, Hermes boundary | Hermes source/runtime evidence under separate authorized phase | 4B.x/5B+ |
| OQ-A06 | Duplicate-work detection scope for logically identical delegated work across retries/restarts/processes | AD-02/AD-05, scenarios 11,12 | Idempotency/dispatch-key semantics design | 5A.4 |
| OQ-A07 | Observable capability advertisement/verification mechanism for logical agents/runtimes (to avoid incorrect matching) | AD-05/AD-06, capability matching | Adapter/registry design and evidence sources | 5A.4 |

---

## D. Deferred decisions

| ID | Deferred item | Reason | Dependency |
|---|---|---|---|
| DD-A01 | Concrete implementation of execution/attempt/assignment stores, APIs, and state machines in code | Stage 5A.3 is audit/design only | 5A.4+ approved implementation planning |
| DD-A02 | Quorum/weighted/any-sufficient aggregation policies and conflict resolution | Require product semantics and evidence | OQ-A02 |
| DD-A03 | Process-isolated or runtime-backed worker pools and supervision daemons | Premature on 8 GB; Option D staged | Evidence/need + 5A.4+ |
| DD-A04 | Hermes/JARVIS/HELIX live integration protocols, capability mappings, and lifecycle control | Not authorized; boundaries must remain | Separate authorized phases |
| DD-A05 | Authentication/cryptographic provenance for delegated agents/runtimes | `local_trust` is not authenticated identity; infra not present | Future security architecture |
| DD-A06 | UI/dashboard for agent/execution monitoring | Out of scope | Future ops/product work |
MARKDOWN
