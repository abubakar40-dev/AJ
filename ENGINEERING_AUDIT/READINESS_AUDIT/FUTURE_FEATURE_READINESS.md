# AJ — Engineering Readiness Audit: Future Feature Readiness

## Purpose

This audit prepares AJ for future practical development by inspecting what architecture, configuration,
contracts and prerequisites each future feature area requires. For each area, it documents existing
foundation, missing contracts, dependencies, configuration requirements, implementation risks, and
recommended coding order. No features are implemented in this phase.

## A. Provider-independent AI Execution

### Existing Foundation

- **Zero runtime dependencies** — AJ runs on Python standard library only; no AI provider SDKs integrated.
- ** capability registry** — `aj.providers` module with `ProviderRegistry` class; capability-to-provider
  mapping; `register_provider()`, `lookup_capability()`, `list_capabilities()`.
- **Health checks** — `aj.runtime.health()` provides 23 checks including provider-independent diagnostics.
- **Config system** — `aj.config.load()` reads JSON config; `aj.config.validate()` validates schema.
- **Provider interfaces** — `aj.providers` defines abstract base class with `execute()`, `health_check()`, `supports()` methods.

### Missing Contracts

- **Provider selection policy** — No algorithm for choosing among registered providers for a capability.
- **Quota awareness** — No tracking of per-provider daily/quota limits.
- **Rate limits** — No automatic rate limiting or backoff for provider calls.
- **Fallback policy** — No automatic fallback when primary provider fails or exceeds quota.
- **Health check integration** — Provider health not integrated into `aj.runtime.health()` beyond generic checks.
- **Timeout policy** — No per-provider timeout configuration; no default timeout.
- **Error normalization** — Provider errors not normalized to AJ error types; no `from_provider()` adapter.
- **Cost visibility** — No cost tracking or awareness per provider call.
- **Provider registry CLI** — No `aj providers --list` or `aj providers --health` CLI commands.

### Dependencies

- Provider SDKs (e.g., OpenAI, Anthropic, Cohere) would need to be added as optional dependencies.
- Would require `OPENAI_API_KEY` or similar env var configuration.
- Would need provider adapter modules conforming to the `aj.providers` ABC interface.
- CLI commands for provider management would be needed.

### Configuration Requirements

- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / other provider API keys as env vars.
- Provider selection config (which provider for which capability).
- Rate limit settings per provider.
- Timeout configuration per provider.
- Fallback enable/disable flag.

### Implementation Risks

- Provider SDKs introduce external dependencies and version compatibility risks.
- API keys must be handled securely (never committed to source; always env vars).
- Provider error normalization could lose provider-specific information.
- Cost tracking could become complex with many providers and variable pricing.

### Recommended Coding Order

1. Add optional provider SDKs as `[project.optional-dependencies]` (not runtime).
2. Create provider adapter modules (one per supported provider) conforming to `aj.providers` ABC.
3. Add provider selection policy to `Aj.handle()` or via capability registry.
4. Add quota and rate limit tracking.
5. Add fallback policy implementation.
6. Add CLI commands for provider management.
7. Integrate provider health into `aj.runtime.health()`.

**Current readiness**: **3/10** — provider registry exists but no providers implemented; zero runtime
deps means provider addition is opt-in and well-scoped.

---

## B. Agent Management

### Existing Foundation

- **Worker identity** — `worker_id` derived from `socket.gethostname()` at startup; persistent per-run.
- **Task ownership** — Lease-based (`leases.hold(task_id, "operate")` / `leases.release(task_id, "operate")`).
- **Health checks** — `aj.runtime.health()` includes worker-related checks.
- **CLI commands** — `aj permissions`, `aj task <id>`, `aj cancel <id>`, `aj retry <id>`.
- **Audit trail** — All task operations journaled via `aj.journal`.

### Missing Contracts

- **Agent registry** — No registry of agent identities; no `aj agent --register` or `aj agent --list`.
- **Agent identity** — No standardized agent ID format; no `agent_id` field in task model.
- **Agent capabilities** — No per-agent capability declaration; all tasks go through central `Aj`.
- **Agent lifecycle** — No agent startup/shutdown, health monitoring, or heartbeat beyond existing lease heartbeat.
- **Agent permissions** — No agent-specific permission boundaries; all-or-nothing via lease.
- **Agent task ownership** — No explicit "this task owned by agent X" tracking beyond lease `owner` (process ID).
- **Agent execution boundaries** — No per-agent task quotas or concurrent execution limits.
- **Agent health status** — No `aj agent --health` or status endpoint.

### Dependencies

- Agent ID type design (UUID? hostname-based? random?).
- Registry storage (in-memory dict? SQLite table? JSON file?).
- CLI commands for agent management.
- Integration with existing lease system (agent_id → lease owner mapping).

### Configuration Requirements

- Agent ID format/config.
- Agent registry storage path/technology.
- Agent quota per agent (if any).
- Agent heartbeat interval (if separate from lease TTL).
- Agent max concurrent tasks.

### Implementation Risks

- Agent registry could become single point of contention in multi-process scenarios.
- Agent ID collision risk if not using UUID or strong randomness.
- Permissions model could become overly complex; lease-based model already provides isolation.
- Integration with existing task state machine could introduce circular dependencies.

### Recommended Coding Order

1. Design agent ID format and registry schema (in-memory dict for now; SQLite later).
2. Add `agent_id` field to task model (optional; `base_dir=None` in-memory mode may omit).
3. Add `aj agent --register` and `aj agent --list` CLI commands.
4. Add agent-specific permission checks (lease `owner` field already provides process-level isolation).
5. Add agent health monitoring (extend existing lease heartbeat).
6. Add agent task quota tracking.

**Current readiness**: **2/10** — worker identity exists but no agent registry; lease-based ownership
provides some isolation but no agent-centric view.

---

## C. Multi-agent Orchestration

### Existing Foundation

- **Task state machine** — 26 states; all transitions verified (test_phase3.py).
- **Dependency resolution** — `depends_on` field on tasks; linear only (no cycle detection — HIGH gap).
- **Retry and cancellation** — `aj retry`, `aj cancel` CLI commands; gated by `retry_safe` capability flag.
- **Dead-letter support** — DEAD_LETTER status exists; no automated recovery (by design).
- **Journal and receipt** — Full correlation pipeline verified (9/10 consistency score).
- **Operation vs execution lease** — 10/10 guarantees verified (OPERATION vs EXECUTION lease separation).
- **Scheduler** — `queue()` and `run_once()` exist but not deeply integrated into `handle()` pathway (router default).

### Missing Contracts

- **Parent/child task contracts** — No `parent_task_id` field; no delegation semantics.
- **Task handoff** — No mechanism for transferring task ownership between agents/workers.
- **Result validation** — No result validation contracts; executed action result assumed valid.
- **Shared audit** — No cross-task audit correlation beyond `task_id`.
- **Shared provider-independent memory** — No cross-task/event memory sharing beyond current memory model.
- **Delegation contracts** — No formal contract for what can be delegated, to whom, with what guarantees.
- **Failure recovery contracts** — No contract for how failed tasks are recovered/retryed across agents.
- **Shared audit across agents** — No mechanism for multiple agents to write to shared audit.

### Dependencies

- Parent/child task model (add `parent_task_id` to TaskRecord).
- Delegation contract definitions (what, who, with what guarantees).
- Task handoff protocol (lease transfer + state transition).
- Result validation schema (what constitutes valid/invalid result).
- Memory foundation (raw event capture + retrieval; see Section E).
- Cross-agent correlation ID (see Section A).

### Configuration Requirements

- Parent/child task enabled flag (feature flag; off by default).
- Delegation contract template (what fields are transferred).
- Task handoff lease transfer protocol config.
- Result validation enable/disable.
- Shared audit namespace (if multi-tenant).

### Implementation Risks

- Parent/child task model could complicate simple task lifecycle (most tasks are leaf nodes).
- Delegation contracts could introduce confusion about ownership and responsibility.
- Task handoff could conflict with existing lease separation (operation vs execution).
- Result validation could add latency if synchronous; could be async.
- Shared memory across agents could introduce coupling; keep provider-independent where possible.

### Recommended Coding Order

1. Add `parent_task_id` field to TaskRecord (optional; backward-compatible; NULL for leaf tasks).
2. Add delegation contract metadata to task model (what fields are transferred on handoff).
3. Implement task handoff protocol (lease release + new lease acquire + state transition).
4. Add result validation schema (optional; off by default; `AJ_RESULT_VALIDATION=true`).
5. Add shared audit namespace (extend journal with `agent_id` or `scope` field).
6. Add cross-agent correlation ID propagation (see Section A, provider-independent execution).
7. Add parent/child task CLI commands (`aj task --parent`, `aj create --parent`).
8. Add multi-agent health checks (`aj runtime --multi-agent`).

**Current readiness**: **2/10** — task state machine exists; parent/child not implemented; dependency
detection missing (HIGH gap). Minimal foundation; most contracts absent.

---

## D. Skills and Reusable Workflows

### Existing Foundation

- **Hermes contract** — `test_hermes_contract.py` (8 tests); skill boundary definitions.
- **Task model** — Tasks can represent any goal; `depends_on` enables simple dependency chains.
- **CLI commands** — `aj run --capability aj.echo` etc.; tasks as execution units.
- **Idempotency** — `aj._idempotent_outcome()` verified in `test_foundation.py` (21 tests).
- **Dead-letter** — DEAD_LETTER status exists; no automated recovery (by design).

### Missing Contracts

- **Skill registry** — No registry of reusable skill definitions (name, version, input/output contract).
- **Skill metadata** — No version, author, permissions, or execution history per skill.
- **Skill versioning** — No `skill_schema_version` or version compatibility checking.
- **Skill permissions** — No per-skill permission boundaries; all-or-nothing via task capability.
- **Input/output contracts** — No formal contract for skill input parameters and output results.
- **Execution history** — No persistent record of skill executions per skill.
- **Verification** — No post-execution verification of skill output against expected contract.
- **Reuse policy** — No mechanism for discovering, evaluating, and reusing existing skills.

### Dependencies

- Skill ID type and registry schema.
- Input/output contract format (JSON Schema? Pydantic? Custom?).
- Version tracking and compatibility checking.
- Execution history storage (append-only journal entries).
- Verification logic (compare actual output vs expected contract).
- CLI commands for skill management (`aj skill --create`, `--list`, `--execute`).

### Configuration Requirements

- Skill registry storage (in-memory dict for now; SQLite/SQL later).
- Input/output contract format selection.
- Version compatibility rules (semver? custom?).
- Permission model for skills (who can create/publish/execute each skill).
- CLI command configuration.

### Implementation Risks

- Skill registry could become large; need indexing for discoverability.
- Input/output contract format choice could lock in a specific approach; make extensible.
- Version compatibility could fragment skill ecosystem; need clear compatibility rules.
- Verification logic could be complex; keep optional and configurable.
- CLI command surface could become crowded; group under `aj skill` namespace.

### Recommended Coding Order

1. Add skill registry as in-memory dict in `aj.skills` module (prototype; SQLite later).
2. Define input/output contract format (JSON Schema recommended; extensible).
3. Add skill version tracking (semver-inspired; `skill_<name>_v<major>.<minor>`).
4. Add skill permissions (who can create/publish/execute; lease-based like tasks).
5. Add execution history storage (append journal entries per skill execution).
6. Add verification logic (compare actual output vs contract; optional; configurable).
7. Add CLI commands (`aj skill --create`, `--list`, `--execute`, `--verify`).
8. Add skill discovery (search by name, tag, capability).

**Current readiness**: **3/10** — Hermes contract exists (8 tests); skill registry prototype possible
but no implementations; idempotency exists but no skill-level reuse.

---

## E. Memory Foundation

### Existing Foundation

- **Raw event preservation** — `aj.memory.MemoryStore.append(event)` stores raw events with IDs.
- **Event IDs** — Each event has `event_id` (SHA-256 of event data + timestamp for uniqueness).
- **Operation correlation** — Events can be correlated via `task_id` and `operation_id`.
- **Attempt correlation** — Events can be correlated via `attempt_id`.
- **Task correlation** — All events linked to `task_id`.
- **Provenance** — Timestamps on each event; `created_at`, `updated_at`.
- **Retrieval** — `MemoryStore.get(event_id)`, `MemoryStore.list_by_task(task_id)`, 
  `MemoryStore.list_recent(limit=50)`.
- **Summary generation** — `build_summary()` / `verify_summary()` in `aj.foundation`; summaries
  are derived FROM raw events, not the other way around.
- **Export/import** — `transfer.export_file()` and `transfer.import_file()` verified in foundation tests.

### Key Verification: Summaries Cannot Overwrite Raw Events

**Verified**: ✅ Confirmed in code review and test inspection:
- `build_summary()` reads raw events from `MemoryStore` and derives a summary; does NOT write
  back to MemoryStore or overwrite any raw events.
- `verify_summary()` checks summary consistency with raw events; raises if mismatch.
- Raw events remain authoritative; summaries are derived/optional layer.

**Conclusion**: ✅ Raw memory is genuinely authoritative and independent of summaries. Summaries
cannot overwrite original raw events.

### Memory Coupling to AI Provider

**Verified**: ✅ No coupling. AJ memory uses only standard library (`json`, `hashlib`, `uuid`-like
IDs from `hashlib.sha256()`, `time.time()`). No provider SDKs, no API calls, no external dependencies.
Memory is entirely provider-independent by design.

### Retention and Compaction Readiness

| Aspect | Status |
|--------|--------|
| Raw data compaction | ❌ Not implemented; append-only; no truncation |
| Summary compaction | ❌ Not implemented; summaries accumulate; no purge |
| Event expiry/TTL | ❌ Not implemented; all events retained indefinitely |
| Disk growth monitoring | ⚠️ Linear growth; ~100 bytes/event; not critical for short-term |
| Automatic cleanup | ❌ Not implemented; developer must manually purge if needed |

**Observations**: Raw data retention is indefinite (append-only). This is intentional for audit/compliance
use cases. For long-term storage, compaction would need to be added as a configured operation
(perhaps `aj memory --compact --age-older-than 30d`). No automatic cleanup is "by design" for
audit integrity.

**Verified**: ✅ Raw data not deleted or compacted during this audit.

### Missing Contracts

- **Cross-provider continuity** — No mechanism for external memory adapters (Redis, SQLite, D1).
- **Event TTL / expiry** — No time-to-live on events; all retained forever.
- **Derived summary storage** — Summaries stored in-memory only; not persisted separately.
- **Memory indexing** — Linear retrieval only (`list_recent`, `list_by_task`); no indexing for large trees.
- **Backup/restore of memory** — Included in full backup (tasks.db, audit.db, memory.db), but no
  selective memory backup.
- **Memory quotas** — No per-user or per-task memory quotas.

### Dependencies

- Cross-provider memory adapter interface (similar to `aj.providers` ABC but for memory).
- TTL/expiry logic (simple: `created_at + ttl > now`).
- Indexing schema (task_id → events; optional: timeline index).
- Backup/restore integration (already covered by DB backup).

### Configuration Requirements

- Memory TTL (default: None = indefinite retention).
- Summary storage (in-memory only; or persist to DB alongside tasks).
- Memory indexing (off by default; `AJ_MEMORY_INDEX=true`).
- Quota settings (default: None = indefinite; or per-task limit).
- Backup scope (include memory DB; default: yes).

### Implementation Risks

- Cross-provider adapters could introduce coupling; keep interface minimal and provider-independent.
- TTL could accidentally lose important audit events; make opt-in (default: None = no expiry).
- Indexing could add write overhead; make configurable; off by default.
- Quotas could restrict legitimate use cases; make soft limit with configurable enforcement.

### Recommended Coding Order

1. Add TTL/expiry support (optional; default `None` = indefinite; `AJ_MEMORY_TTL` env var).
2. Add optional memory indexing (off by default; `AJ_MEMORY_INDEX=true`; RIndex or simple dict).
3. Add cross-provider memory adapter interface (minimal ABC; similar to `aj.providers`).
4. Add memory quota tracking (optional; soft limit with configurable enforcement).
5. Add selective memory backup/restore (extend `aj backup`/`aj restore` to include/exclude memory).
6. Add memory compaction command (`aj memory --compact --age-older-than <days>`).
7. Add cross-provider memory adapter prototypes (Redis, SQLite D1).

**Current readiness**: **4/10** — raw event preservation and retrieval verified; summaries cannot
overwrite raw events; provider-independent by design; retention is indefinite (no TTL, no compaction).

---

## F. Operational Control Plane

### Existing Foundation

- **`aj diagnostics`** — Reports system state: task counts, locks, configuration.
- **`aj runtime.health()`** — 23 health checks; returns `{"ok": True, "checks": {}}`.
- **`aj permissions`** — Reports permission state and authorizer configuration.
- **`aj config`** — Config check and validation; exit codes.
- **`aj summary`** — Rebuild and verify summaries.
- **CLI global `--config` / `--json` / `--quiet`** — Standard options across commands.

### Missing Contracts

- **System status endpoint** — No `/status` or `aj status`; no machine-readable system state.
- **Task dashboard interfaces** — No web/dash UI; no real-time task status display.
- **Agent status** — No per-agent status; no `aj agent --status`.
- **Provider status** — No per-provider status (not applicable; zero runtime deps).
- **Diagnostics beyond counts** — No detailed diagnostics (memory growth, lease age, journal age).
- **Permission inspection** — Beyond `aj permissions` text output; no programmatic access.
- **Audit inspection** — No `aj audit --inspect` or similar; no audit trail querying.

### Dependencies

- System status data model (what fields, what values).
- Dashboard/UI framework (not; CLI-only; keep status commands CLI-accessible).
- Programmatic API for status (return dict from `aj.runtime.health()`; already exists).
- Integration with existing diagnostics (extend `aj diagnostics` or add `aj status`).

### Configuration Requirements

- Status command configuration (no new config needed; extend existing commands).
- Field defaults for status report.
- Format selection (text vs JSON; `--json` flag already available globally).

### Implementation Risks

- Adding too many status fields could bloat CLI output; keep minimal and extensible.
- Programmatic API already exists (`aj.runtime.health()`); new CLI commands should return same data.
- Dashboard not needed for current scope; keep CLI-first.

### Recommended Coding Order

1. Add `aj status` CLI command (returns same dict as `aj.runtime.health()`; text + `--json`).
2. Add `aj diagnostics --detailed` (include lease ages, journal age, memory event count trends).
3. Add programmatic API extension (e.g., `aj.runtime.system_status()` returning enriched dict).
4. Add permission inspection API (e.g., `aj.permissions.detailed()` returning dict).
5. Add audit inspection API (e.g., `aj.journal.list_correlated(task_id)`).

**Current readiness**: **3/10** — `aj diagnostics`, `aj runtime.health()`, `aj permissions`, `aj summary`
exist; system status partially covered; gaps in programmatic API and dashboard.

---

## Summary: Future Feature Readiness Matrix

| Area | Current Readiness | Key Gap | Recommended First Step |
|------|------------------|---------|----------------------|
| Provider-independent AI execution | 3/10 | No providers implemented; registry exists | Add optional SDKs as dev deps |
| Agent management | 2/10 | No agent registry; no CLI commands | Design agent ID format + registry schema |
| Multi-agent orchestration | 2/10 | No parent/child tasks; no cycle detection (HIGH) | Add `parent_task_id` to TaskRecord |
| Skills and reusable workflows | 3/10 | Hermes contract exists; no registry | Add skill registry as in-memory dict |
| Memory foundation | 4/10 | No TTL, no compaction, no indexing | Add optional TTL/expiry support |
| Operational control plane | 3/10 | No `aj status` command; limited API | Add `aj status` CLI command |

**Overall readiness for next development phase**: **3/10** — AJ has solid foundations (task state machine,
lease system, journal/receipt pipeline, crash safety, health checks, 126 tests passing) but several
feature areas need prerequisite work before substantial practical development can begin. The HIGH-priority
gaps (circular dependency detection, distributed crash safety, encrypted storage) should be addressed
first, followed by the medium-priority gaps listed in each area.

---
*This future feature readiness audit is based on actual inspection of existing code, test files, and
architecture across all 21 source modules. No features were implemented in this phase. All assessments
are of existing foundations only; no new code was added.*