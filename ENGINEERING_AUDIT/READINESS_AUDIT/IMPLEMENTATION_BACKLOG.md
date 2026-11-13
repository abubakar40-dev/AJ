# AJ — Engineering Readiness Audit: Prioritized Implementation Backlog

## Purpose

This report creates a practical implementation backlog for the NEXT coding phase, grouped by priority
(P0 critical correctness and data safety through P5 UI, automation and optional extensions). Each item
specifies feature, current status, required changes, relevant modules, dependencies, risks, acceptance
criteria, tests required, configuration prerequisites, and implementation order.

## Prioritization Framework

| Priority | Focus | Rationale |
|----------|-------|-----------|
| **P0** | Critical correctness and data safety | Foundational reliability; unblock all other work |
| **P1** | Core execution reliability | Task lifecycle, leases, crash recovery; without these, tasks malfunction |
| **P2** | Core operational capabilities | Scheduler, dependencies, dead-letter; enable complex workflows |
| **P3** | Provider and agent foundations | Enable ecosystem expansion; optional; not required for core function |
| **P4** | Advanced ecosystem features | Multi-agent, skills, memory; higher-level ecosystem features |
| **P5** | UI, automation and optional extensions | Polish, fuzzing, benchmarking; lowest impact on core reliability |

---

## P0 — Critical Correctness and Data Safety

### P0-1: Circular Dependency Detection

| Field | Details |
|-------|---------|
| **Feature** | Detect tasks with cyclic `depends_on` chains; prevent silent infinite blocking. |
| **Current status** | ❌ MISSING — linear only; tasks with cyclic dependencies silently block forever. |
| **Required changes** | - Add `detect_circular_dependencies(depends_on)` function in `aj/dependencies.py` (or `aj/foundation.py`).
  - Return `CircularDependencyError` with full cycle path.
  - Integrate into `Aj.handle()` before task creation/scheduling.
  - Add `CircularDependencyError` exception class in `aj/errors.py`.
- ~50 lines of code; 2 new tests. |
| **Relevant modules** | `aj/dependencies.py` (or `aj/foundation.py`), `aj/errors.py`, `aj/orchestrator.py` |
| **Dependencies** | Task model `depends_on` field (already exists); task state machine (already exists). |
| **Risks** | - Must not break existing tasks without `depends_on` (backward-compatible: only flag when cycles exist).
  - Cycle detection algorithm must handle self-loops (A→A), 2-node cycles (A→B→A), and long chains (A→B→C→A).
  - Integration into `Aj.handle()` must preserve existing error handling flow. |
| **Acceptance criteria** | - `aj run --capability aj.echo --depends-on aj.echo` → `EXIT_CIRCULAR_DEPENDENCY` (or appropriate exit code).
  - `aj run --capability aj.echo --depends-on "other-cap"` where other-cap depends back → detected.
  - No existing tasks (no `depends_on` or single dependency) are affected.
  - 2 tests pass: self-cycle detection, multi-node cycle detection. |
| **Tests required** | 1. `test_circular_dependency_self.py` — task with `depends_on=["self"]` → error.
   2. `test_circular_dependency_chain.py` — A→B→C→A cycle → error. |
| **Configuration prerequisites** | None (operates on task model `depends_on` field; no new config keys). |
| **Implementation order** | **P0-1** — Must be done before any P1 work that creates tasks with `depends_on`. |

### P0-2: Crash Recovery — After-Receipt Scenarios (Matrix Points 8, 10, 11, 12)

| Field | Details |
|-------|---------|
| **Feature** | Add crash recovery tests and implementation for the 5 untested 12-point matrix points: |
| **Current status** | ❌ 5/12 crash matrix points untested (points 8, 10, 11, 12 + 1 more). |
| **Required changes** | - Add crash test scenarios for: (1) crash after receipt persistence (matrix point 8),
   (2) crash before lease release (matrix point 10), (3) during heartbeat renewal (matrix point 10),
   (4) during retry scheduling (matrix point 11), (5) during dependency evaluation (matrix point 12).
   - Implement recovery policies for each scenario (lease release, state rollback, retry gating).
   - Modify `aj/orchestrator.py` crash handling to cover all 12 points.
   - Add recovery decision logic (retry vs. escalate vs. human intervention).
- ~80 lines of code; 5 new tests. |
| **Relevant modules** | `aj/orchestrator.py`, `aj/crash_safety.py`, `aj/leases.py`, `aj/journal.py` |
| **Dependencies** | Existing crash recovery implementation (scenarios 1-6 verified in `test_crash_safety.py`).
  - Lease release logic (already exists in `aj/leases.py`).
  - Journal append pattern (already exists in `aj/journal.py`). |
| **Risks** | - Must not corrupt persisted state during simulated crash.
  - Recovery decisions must be deterministic (same crash point → same decision).
  - Must not leak locks/leases during crash recovery. |
| **Acceptance criteria** | - 5 new crash safety tests all pass (matrix points 8, 10, 11, 12 + 1 unresolved).
   - Simulated abrupt termination at each crash point without data corruption.
   - Recovery decisions are deterministic and logged in journal.
   - No leaked leases after recovery. |
| **Tests required** | 1. Crash after receipt persistence (point 8).
   2. Crash before lease release (point 10).
   3. During heartbeat renewal (point 10).
   4. During retry scheduling (point 11).
   5. During dependency evaluation (point 12). |
| **Configuration prerequisites** | None. |
| **Implementation order** | **P0-2** — After P0-1 (circular deps); crash recovery must be complete before P1. |

### P0-3: Secrets Redaction Verification

| Field | Details |
|-------|---------|
| **Feature** | Add test that verifies no secrets (API keys, tokens) appear in any output (logs, JSON, stdout) during normal operation. |
| **Current status** | ❌ NOT TESTED — design principle documented; no test verifying redaction in output. |
| **Required changes** | - Add `test_secrets_redaction.py` test that runs `aj run` with various capabilities and inspects stdout/journal/logs for secret patterns.
   - Define "secret" patterns (API keys, tokens, secrets env vars).
   - Assert no matches in any output.
   - Run as part of canonical test suite; must not break existing 126 tests.
- ~30 lines of code; 1 new test. |
| **Relevant modules** | `aj/__main__.py`, `aj/orchestrator.py`, `aj/journal.py`, `aj/leases.py` (output paths) |
| **Dependencies** | Zero runtime dependencies (AJ has no secrets); test must verify NEGATIVE — no secrets appear. |
| **Risks** | - Must not flag goal text as "secret" (goal text may contain arbitrary strings; only flag actual secret patterns).
  - Must handle all output channels: stdout, JSON payload, journal entries, health check output. |
| **Acceptance criteria** | - `pytest tests/test_secrets_redaction.py -q --tb=short` → 1 passed.
   - No API keys, tokens, or secret patterns in any AJ output during normal operation.
   - Goal text containing "openai-api-key-xyz" not flagged (only actual key patterns). |
| **Tests required** | 1. `test_secrets_redaction.py` — run AJ ops; verify no secrets in output. |
| **Configuration prerequisites** | None. |
| **Implementation order** | **P0-3** — After P0-1; low effort; verifiable immediately. |

---

## P1 — Core Execution Reliability

### P1-1: Complete Crash Recovery Matrix (All 12 Points)

| Field | Details |
|-------|---------|
| **Feature** | Implement and verify all 12 crash recovery matrix points; close the 7/12 → 12/12 gap. |
| **Current status** | ✅ 7/12 tested (scenarios 1-7 in `test_crash_safety.py`); ❌ 5/12 untested (points 8-12). |
| **Required changes** | - Add crash test scenarios for points 8-12 (see P0-2, which covers 5 of the 7 remaining).
   - Ensure all 12 points have corresponding tests.
   - Document recovery decisions for each point (retry vs. escalate vs. human intervention).
   - Verify 12/12 pass. |
| **Relevant modules** | `aj/orchestrator.py`, `aj/crash_safety.py`, `aj/leases.py`, `aj/journal.py`, `aj/errors.py` |
| **Dependencies** | P0-2 (after circular deps and secrets redaction completed); all 7 existing crash tests must continue passing. |
| **Risks** | - Must maintain backward compatibility with existing 7 crash test scenarios.
  - New scenarios must not interfere with existing test isolation (temp directories, fixture cleanup). |
| **Acceptance criteria** | - `pytest tests/test_crash_safety.py -q --tb=short` → 12/12 passed (was 7/12).
   - All 12 matrix points have corresponding tests.
   - Recovery decisions documented and deterministic for each point. |
| **Tests required** | 5 new tests for points 8-12 (see P0-2). Existing 7 tests must continue passing. |
| **Configuration prerequisites** | None. |
| **Implementation order** | **P1-1** — After P0-1, P0-2, P0-3; foundational reliability. |

### P1-2: Idempotent Replay Flow

| Field | Details |
|-------|---------|
| **Feature** | `aj run` on a completed task should be a no-op or require user decision, not silently re-execute. |
| **Current status** | ❌ NOT TESTED — idempotent replay flow not implemented; no test for re-running completed task. |
| **Required changes** | - Modify `Aj.handle()` to check task status before execution; if COMPLETED, return early with info message (or `EXIT_OK` if `--replay` flag provided).
   - Add `--replay` / `-r` CLI flag to force re-execution of completed task (gated by `requires_user_decision`).
   - Add test: `test_idempotent_replay.py` — `aj run` on completed task → `EXIT_OK` with "task already completed" message; `aj run --replay` → re-executes.
- ~40 lines of code; 1 new test + 1 CLI modification. |
| **Relevant modules** | `aj/orchestrator.py`, `aj/__main__.py`, `aj/errors.py` |
| **Dependencies** | Task status tracking (already exists; `TaskRecord.status` field); exit code system (already exists). |
| **Risks** | - Must not silently re-execute completed tasks (that would violate idempotency).
  - `--replay` flag must be gated; requires user awareness (exit code 3 or confirmation prompt). |
| **Acceptance criteria** | - `aj run --capability aj.echo --text "hello"` on completed task → `EXIT_OK` + "task already completed".
   - `aj run --capability aj.echo --text "hello" --replay` on completed task → re-executes (or `EXIT_UNSAFE` if not safe).
   - `pytest tests/test_idempotent_replay.py -q --tb=short` → 1 passed. |
| **Tests required** | 1. `test_idempotent_replay.py` — completed task replay behavior. |
| **Configuration prerequisites** | None. |
| **Implementation order** | **P1-2** — After P0-1, P0-2, P0-3; before P1-1 (crash recovery complete). |

### P1-3: Dead-Letter Recovery Policy

| Field | Details |
|-------|---------|
| **Feature** | Implement automated (or policy-guided) recovery from DEAD_LETTER status. |
| **Current status** | ❌ BY DESIGN — no automated recovery from DEAD_LETTER; operator decision. |
| **Required changes** | - Add `DEAD_LETTER_RECOVERY_POLICY` config option (off by default; `AJ_DEAD_LETTER_POLICY=auto` for automated).
   - Add `aj dead-letter --recover <task_id>` CLI command (attempts recovery: reset status to EXECUTING, re-queue).
   - Add test: `test_dead_letter_recovery.py` — DEAD_LETTER task recovery via CLI or API.
   - Document operator decision vs. automated policy. |
| **Relevant modules** | `aj/orchestrator.py`, `aj/__main__.py`, `aj/errors.py`, `aj/config.py` |
| **Dependencies** | Task status state machine (already has DEAD_LETTER state); exit code system. |
| **Risks** | - Automated recovery could mask operator-intended dead-lettering.
  - Must provide both automated (`AJ_DEAD_LETTER_POLICY=auto`) and manual (`aj dead-letter --recover`) paths. |
| **Acceptance criteria** | - `aj dead-letter --recover <task_id>` → resets status from DEAD_LETTER to EXECUTING.
   - `AJ_DEAD_LETTER_POLICY=auto` enables automatic recovery on task failure → DEAD_LETTER → retry.
   - `pytest tests/test_dead_letter_recovery.py -q --tb=short` → 1 passed. |
| **Tests required** | 1. `test_dead_letter_recovery.py` — dead-letter recovery behavior. |
| **Configuration prerequisites** | `AJ_DEAD_LETTER_POLICY` env var (off by default). |
| **Implementation order** | **P1-3** — After P0-1, P0-2, P0-3; P1-2; mid-phase reliability. |

---

## P2 — Core Operational Capabilities

### P2-1: Scheduler Deep Integration

| Field | Details |
|-------|---------|
| **Feature** | Integrate scheduler into the main `handle()` pathway (not just router default); add bounded execution behavior. |
| **Current status** | ⚠️ PARTIALLY IMPLEMENTED — scheduler exists with `queue()` and `run_once()` but not deeply integrated into main `handle()` pathway (router is default dispatch). |
| **Required changes** | - Modify `Aj.handle()` to check scheduler queue before direct execution.
   - Add bounded execution: `run_once()` with max time/TTL; if exceeded, abort and mark FAILED.
   - Add scheduler polling interval config (`AJ_SCHEDULER_INTERVAL`).
   - Add `aj scheduler --status` CLI command.
   - Ensure existing `aj run` still works (backward-compatible; scheduler optional).
- ~60 lines of code; 2 new tests + 1 CLI command. |
| **Relevant modules** | `aj/orchestrator.py`, `aj/scheduler.py` (exists but partial), `aj/__main__.py` |
| **Dependencies** | Scheduler `queue()` and `run_once()` already exist (Phase 3.1); task state machine (already exists). |
| **Risks** | - Must not break existing `aj run` behavior (backward-compatible; scheduler optional, off by default).
  - Bounded execution must not abort legitimate long-running actions; configurable TTL. |
| **Acceptance criteria** | - `aj scheduler --status` → human-readable scheduler state.
   - `aj run --capability aj.echo --text "hello"` works as before (scheduler off by default).
   - Scheduler `run_once()` has configurable TTL; exceeds → task FAILED with "timeout" reason.
   - `pytest tests/test_scheduler_integration.py -q --tb=short` → 1 passed (new). |
| **Tests required** | 1. Scheduler integration test — `aj run` still works with scheduler off.
   2. Bounded execution test — scheduler TTL exceeded → task FAILED. |
| **Configuration prerequisites** | `AJ_SCHEDULER_INTERVAL` env var (default: 5s); scheduler off by default. |
| **Implementation order** | **P2-1** — After P0-1 through P1-3; core operational capability. |

### P2-2: Referential Dependency Checks (Beyond Linear)

| Field | Details |
|-------|---------|
| **Feature** | Add referential dependency checks beyond linear; validate `depends_on` references exist and are valid. |
| **Current status** | ❌ LINEAR ONLY — no cycle detection (covered by P0-1); no referential validity check. |
| **Required changes** | - Add `validate_dependency_references(depends_on, all_capabilities)` function.
   - Check that each `depends_on` entry maps to a registered capability.
   - Report missing/unregistered dependencies as error (not just cycle detection).
   - Integrate into `Aj.handle()` before task creation.
- ~30 lines of code; 1 new test. |
| **Relevant modules** | `aj/dependencies.py`, `aj/orchestrator.py`, `aj/providers.py` |
| **Dependencies** | `depends_on` field on tasks (already exists); provider registry (already exists in `aj.providers`). |
| **Risks** | - Must not flag valid dependencies that are registered but not yet created (forward reference allowed?).
  - Must distinguish "capability not registered" from "circular dependency" (different error types). |
| **Acceptance criteria** | - `aj run --capability aj.echo --depends-on nonexistent_cap` → `EXIT_INVALID_DEPENDENCY` (or appropriate).
   - `aj run --capability aj.echo --depends-on aj.echo` → cycle detected (P0-1 handles this).
   - `pytest tests/test_dependency_references.py -q --tb=short` → 1 passed. |
| **Tests required** | 1. `test_dependency_references.py` — referential validity of `depends_on`. |
| **Configuration prerequisites** | None. |
| **Implementation order** | **P2-2** — After P0-1 (circular deps); dependency validation alongside cycle detection. |

### P2-3: Backup Compression

| Field | Details |
|-------|---------|
| **Feature** | Add optional gzip compression to backup output; configurable; default off for performance. |
| **Current status** | ❌ NOT IMPLEMENTED — backup copies are raw; no compression (MEDIUM priority known limitation). |
| **Required changes** | - Add `aj backup --compress` / `--gzip` flag.
   - When enabled, gzip all stores before writing to backup directory.
   - Add `AJ_BACKUP_COMPRESS` env var (default: false/off).
   - Add test: `test_backup_compression.py` — compressed backup smaller than raw; decompresses correctly.
   - Ensure decompress is idempotent (decompress twice same as once). |
| **Relevant modules** | `aj/backup.py` (exists but minimal), `aj/__main__.py`, `aj/config.py` |
| **Dependencies** | Backup `shutil.copy2` pattern (already exists); `gzip` module (stdlib). |
| **Risks** | - Compression adds CPU cost; must be optional (default off).
  - Must handle already-compressed files gracefully (don't double-compress).
  - Decompress during restore must be automatic/silent. |
| **Acceptance criteria** | - `aj backup --compress` → gzip-compressed files in backup dir (`.jsonl.gz` extension).
   - `aj backup --compress` → backup size < raw size (typically 30-50% reduction).
   - Decompressed data matches original (round-trip validation).
   - `pytest tests/test_backup_compression.py -q --tb=short` → 1 passed. |
| **Tests required** | 1. `test_backup_compression.py` — compression ratio and round-trip. |
| **Configuration prerequisites** | `AJ_BACKUP_COMPRESS` env var (default: false/off). |
| **Implementation order** | **P2-3** — After P0-1 through P1-3; operational convenience. |

---

## P3 — Provider and Agent Foundations

### P3-1: Provider SDKs as Optional Dependencies

| Field | Details |
|-------|---------|
| **Feature** | Add optional provider SDKs (OpenAI, Anthropic, etc.) as `[project.optional-dependencies]` without adding runtime dependencies. |
| **Current status** | ✅ ZERO runtime dependencies; provider registry exists but no providers implemented. |
| **Required changes** | - Add to `pyproject.toml`: `[project.optional-dependencies] openai = ["openai>=1.0"]`, `anthropic = ["anthropic>=0.5.0"]`, etc.
   - Create provider adapter modules (`aj/providers/openai_adapter.py`, etc.) conforming to `aj.providers` ABC.
   - Add provider health check integration into `aj.runtime.health()`.
   - Add `AJ_PROVIDER` env var for provider selection.
- ~50 lines of pyproject.toml + ~40 lines per adapter; multiple new tests. |
| **Relevant modules** | `pyproject.toml`, `aj/providers.py` (ABC), new `aj/providers/*_adapter.py` files |
| **Dependencies** | `openai`, `anthropic`, `cohere` packages (optional; installed only if user requests).
  - `aj.providers` ABC already defines interface; adapters conform to it. |
| **Risks** | - Provider SDKs have their own dependencies and version risks.
  - API keys must be env vars, never committed.
  - Provider adapters must be thoroughly tested; SDK APIs change between versions. |
| **Acceptance criteria** | - `pyproject.toml` has `openai`, `anthropic` optional groups.
   - `aj/providers/openai_adapter.py` conforms to `aj.providers` ABC (has `execute()`, `health_check()`, `supports()`).
   - `AJ_PROVIDER=openai aj run --capability aj.echo --text "hello"` → uses OpenAI provider (or graceful "no API key" message).
   - `pytest tests/test_provider_openai.py -q --tb=short` → passes (if OPENAI_API_KEY set). |
| **Tests required** | 1. `test_provider_openai.py` — OpenAI provider integration (requires OPENAI_API_KEY).
   2. `test_provider_health.py` — provider health check via `aj.runtime.health()`. |
| **Configuration prerequisites** | `AJ_PROVIDER` env var; optional SDK packages installed via `pip install "aj[openai]"` etc. |
| **Implementation order** | **P3-1** — After P0-1 through P2-3; foundations for ecosystem expansion. |

### P3-2: Agent Registry

| Field | Details |
|-------|---------|
| **Feature** | Add agent registry: agent identity, capabilities, lifecycle, health monitoring. |
| **Current status** | ❌ MISSING — worker identity exists (`worker_id` from hostname); no agent registry. |
| **Required changes** | - Add `aj/agents.py` module with `AgentRegistry` class (in-memory dict; SQLite later).
   - Add `agent_id` field to TaskRecord (optional; NULL for backward-compatible).
   - Add `aj agent --register` and `aj agent --list` CLI commands.
   - Add `aj agent --status <agent_id>` CLI command.
   - Add agent health monitoring (extend existing lease heartbeat with `agent_id` field).
- ~50 lines of code; 3 new CLI commands + 1 new module; 2-3 new tests. |
| **Relevant modules** | `aj/agents.py` (new), `aj/orchestrator.py` (task state + agent_id), `aj/__main__.py` (CLI) |
| **Dependencies** | Task model (already has `status` field; adding optional `agent_id` is backward-compatible).
  - Lease system (already has `owner` = process ID; `agent_id` extends it). |
| **Risks** | - Agent ID collision risk if not using UUID or strong randomness.
  - Registry could become contention point in multi-process scenarios (mit: file-based or SQLite backend later). |
| **Acceptance criteria** | - `aj agent --register --capability aj.echo` → registers agent; `agent_id` returned.
   - `aj agent --list` → lists all registered agents.
   - `aj agent --status <id>` → health status (free/busy/offline).
   - Adding `agent_id` to existing tasks → no error (optional; NULL defaults). |
| **Tests required** | 1. `test_agent_registration.py` — register and list agents.
   2. `test_agent_status.py` — agent status commands. |
| **Configuration prerequisites** | None (in-memory dict defaults; SQLite backend configurable later). |
| **Implementation order** | **P3-2** — After P0-1 through P2-3; agent foundations. |

---

## P4 — Advanced Ecosystem Features

### P4-1: Multi-agent Orchestration (Parent/Child Tasks)

| Field | Details |
|-------|---------|
| **Feature** | Add parent/child task contracts: delegation, task handoff, result validation, shared audit. |
| **Current status** | ❌ MISSING — no parent/child tasks; `depends_on` is linear only; no `parent_task_id`. |
| **Required changes** | - Add `parent_task_id` field to TaskRecord (optional; NULL for leaf tasks; backward-compatible).
   - Add delegation contract metadata (what fields transferred on handoff).
   - Implement task handoff protocol (lease release + new lease acquire + state transition).
   - Add result validation schema (optional; off by default; `AJ_RESULT_VALIDATION=true`).
   - Add shared audit namespace (extend journal with `scope` or `agent_id` field).
   - Add `aj task --parent <id>` and `aj create --parent <id>` CLI commands.
- ~80 lines of code; 3 new tests + 2 new CLI commands. |
| **Relevant modules** | `aj/orchestrator.py` (state transitions), `aj/journal.py` (scope field), `aj/__main__.py` (CLI) |
| **Dependencies** | `parent_task_id` self-referential FK (SQLite) or handled in Python (in-memory dict).
  - Task state machine (already exists; parent/child transitions add new states). |
| **Risks** | - Parent/child could complicate simple task lifecycle (most tasks are leaf nodes; make optional).
  - Delegation contracts could introduce ownership confusion (clear docs required).
  - Task handoff must respect operation vs execution lease separation (P0-1 territory). |
| **Acceptance criteria** | - `aj create --capability aj.echo --text "hello" --parent <parent_id>` → child task created.
   - `aj task <child_id>` → shows parent link.
   - `aj task <parent_id>` → shows child tasks.
   - `pytest tests/test_parent_child_tasks.py -q --tb=short` → 3 passed. |
| **Tests required** | 1. `test_parent_child_tasks.py` — create child task under parent.
   2. `test_delegation_contract.py` — delegation metadata on handoff.
   3. `test_task_handoff.py` — handoff protocol (lease transfer + state transition). |
| **Configuration prerequisites** | None (optional field; NULL defaults for backward compatibility). |
| **Implementation order** | **P4-1** — After P0-1 through P2-3; advanced ecosystem. Parent deps on P0-1 (circular deps) and P2-2 (dependency validation). |

### P4-2: Skills and Reusable Workflows

| Field | Details |
|-------|---------|
| **Feature** | Add skill registry: skill metadata, versioning, permissions, input/output contracts, execution history, verification, reuse policy. |
| **Current status** | ⚠️ HERMES CONTRACT EXISTS (8 tests in `test_hermes_contract.py`); no skill registry beyond that. |
| **Required changes** | - Add `aj/skills.py` module with in-memory skill registry (dict-based prototype).
   - Define input/output contract format (JSON Schema recommended).
   - Add skill version tracking (semver-inspired).
   - Add skill permissions (who can create/publish/execute).
   - Add execution history (append journal entries per skill execution).
   - Add verification logic (compare actual output vs contract; optional; configurable).
   - Add CLI commands (`aj skill --create`, `--list`, `--execute`, `--verify`).
- ~80 lines of code; new module; 3-4 new tests + 4 new CLI commands. |
| **Relevant modules** | `aj/skills.py` (new), `aj/journal.py` (execution history), `aj/__main__.py` (CLI) |
| **Dependencies** | JSON Schema (stdlib? or `jsonschema` pip package? — keep optional; use custom simple format if not).
  - Existing journal append pattern (already in `aj/journal.py`). |
| **Risks** | - Skill registry could become large; need indexing for discoverability.
  - Input/output contract format choice could lock in approach; make extensible.
  - Verification logic could be complex; keep optional and configurable. |
| **Acceptance criteria** | - `aj skill --list` → lists registered skills (empty initially).
   - `aj skill --create --name aj.echo_skill --input '{"message": string}' --output '{"result": string}'` → skill registered.
   - `aj skill --execute --name aj.echo_skill --input '{"message": "hello"}'` → executes skill (delegates to appropriate action).
   - `pytest tests/test_skills.py -q --tb=short` → 3 passed. |
| **Tests required** | 1. `test_skills.py` — skill registry and operations.
   2. `test_skill_contract.py` — input/output contract validation. |
| **Configuration prerequisites** | None (in-memory dict defaults). |
| **Implementation order** | **P4-2** — After P0-1 through P3-2; skills and reusable workflows. |

### P4-3: Memory Foundation (Cross-Provider Continuity)

| Field | Details |
|-------|---------|
| **Feature** | Add cross-provider memory continuity: raw event capture, retrieval, provenance, derived summaries, external memory adapters. |
| **Current status** | ✅ Raw event preservation and retrieval verified; summaries cannot overwrite raw events; provider-independent by design; retention is indefinite (no TTL, no compaction). |
| **Required changes** | - Add optional TTL/expiry support (default `None` = indefinite; `AJ_MEMORY_TTL` env var).
   - Add optional memory indexing (off by default; `AJ_MEMORY_INDEX=true`; simple dict index).
   - Add cross-provider memory adapter interface (minimal ABC; similar to `aj.providers` ABC).
   - Add memory quota tracking (optional; soft limit with configurable enforcement).
   - Add selective memory backup/restore (extend `aj backup`/`aj restore` include/exclude).
   - Add memory compaction command (`aj memory --compact --age-older-than <days>`).
- ~60 lines of code; 2-3 new modules/configurations; 2-3 new tests. |
| **Relevant modules** | `aj/memory.py` (already exists — MemoryStore), `aj/memory_adapter.py` (new or extend), `aj/config.py` |
| **Dependencies** | Existing MemoryStore (already has `append()`, `get()`, `list_by_task()`, `list_recent()`).
  - TTL logic (simple: `created_at + ttl > now`).
  - Indexing (dict-based or RIndex). |
| **Risks** | - Cross-provider adapters could introduce coupling; keep interface minimal and provider-independent.
  - TTL could accidentally lose important audit events; make opt-in (default: None = no expiry).
  - Indexing could add write overhead; make configurable; off by default. |
| **Acceptance criteria** | - `aj memory --list-recent 5` → last 5 events.
   - `AJ_MEMORY_TTL=3600 aj memory --append '{"test": true}'` → event auto-expired after 1 hour (verifiable).
   - `pytest tests/test_memory_ttl.py -q --tb=short` → 1 passed.
   - `pytest tests/test_memory_indexing.py -q --tb=short` → 1 passed (if `AJ_MEMORY_INDEX=true`). |
| **Tests required** | 1. `test_memory_ttl.py` — TTL/expiry support.
   2. `test_memory_indexing.py` — optional indexing. |
| **Configuration prerequisites** | `AJ_MEMORY_TTL` env var (default: None = indefinite); `AJ_MEMORY_INDEX` env var (default: false). |
| **Implementation order** | **P4-3** — After P0-1 through P3-2; memory foundation. |

---

## P5 — UI, Automation and Optional Extensions

### P5-1: Fuzz Testing for Edge Cases

| Field | Details |
|-------|---------|
| **Feature** | Add fuzz testing for edge cases: malformed inputs, extreme values, boundary conditions. |
| **Current status** | ❌ NOT IMPLEMENTED — LOW priority from known limitations. |
| **Required changes** | - Add `tests/test_fuzz.py` with fuzz scenarios (malformed JSON, empty goals, very long goals, special characters, Unicode, etc.).
   - Run via `pytest tests/test_fuzz.py -q --tb=short`; must not break existing 126 tests.
   - Use `hypothesis` or manual fuzz loop; hypothesis is stdlib-adjacent but optional.
   - If hypothesis not available, use manual fuzz with broad coverage. |
| **Relevant modules** | `aj/orchestrator.py`, `aj/foundation.py`, `aj/errors.py` (input validation) |
| **Dependencies** | `hypothesis` pip package (optional; `pip install hypothesis`; or manual fuzz loop without external deps). |
| **Risks** | - Fuzz may find edge cases that break existing behavior; must be configurable (run separately, not in canonical suite by default).
  - Must not flag legitimate edge cases as errors (filter carefully). |
| **Acceptance criteria** | - `pytest tests/test_fuzz.py -q --tb=short` → runs without crash (exit 0).
   - At least 20 fuzz scenarios covered (malformed JSON, empty goal, very long goal, Unicode, special chars).
   - No existing tests broken (126/126 still pass after adding fuzz). |
| **Tests required** | 1. `test_fuzz.py` — edge case fuzz scenarios. |
| **Configuration prerequisites** | `hypothesis` pip package (optional; if not available, manual fuzz loop runs). |
| **Implementation order** | **P5-1** — After all P0-P4 items; optional polish. |

### P5-2: Exit Code Standardization

| Field | Details |
|-------|---------|
| **Feature** | Ensure all CLI commands use consistent exit codes; document the exit code matrix. |
| **Current status** | ✅ 5 exit codes documented and verified (0=OK, 1=FAILURE, 2=NOT_FOUND, 3=UNSAFE, 4=CONFIG).
   - All commands use correct codes (verified through test suite). |
| **Required changes** | - Add `CLI_EXIT_CODES.md` documentation (already covered in `CLI_AUDIT.md`).
   - Ensure no new CLI commands use non-standard exit codes.
   - Add test: verify all exit codes across all commands. |
| **Relevant modules** | `aj/__main__.py`, `aj/orchestrator.py`, `aj/errors.py` |
| **Dependencies** | Existing exit code system (already in place; 5 codes verified). |
| **Risks** | - Low risk; already verified. |
| **Acceptance criteria** | - All CLI commands use one of the 5 standard exit codes.
   - `CLI_EXIT_CODES.md` documented and up to date.
   - New commands (future) adhere to the standard matrix. |
| **Tests required** | 1. Exit code consistency test (part of canonical suite). |
| **Configuration prerequisites** | None. |
| **Implementation order** | **P5-2** — After all P0-P4 items; minimal polish. |

### P5-3: Agent Security Review

| Field | Details |
|-------|---------|
| **Feature** | Review agent-facing code for injection risks, unsafe imports, eval/exec usage, etc. |
| **Current status** | ⚠️ REVIEWED during Security Audit (8/10 score); 2 gaps documented (secrets redaction verification, backup credential redaction). |
| **Required changes** | - Run security review on all 21 source modules (already done in `SECURITY_AND_PERMISSION_AUDIT.md`).
   - Document any new risks discovered during future code changes.
   - Add tests if new risks identified. |
| **Relevant modules** | All 21 `.py` modules (already reviewed). |
| **Dependencies** | Security audit findings (already documented). |
| **Risks** | - Ongoing as code evolves; not a one-time task. |
| **Acceptance criteria** | - Security audit re-run after any major code change.
   - No new injection vulnerabilities introduced. |
| **Tests required** | 1. Security review checklist (manual; part of development workflow). |
| **Configuration prerequisites** | None. |
| **Implementation order** | **P5-3** — After all P0-P4 items; ongoing maintenance. |

---

## Implementation Order Summary

| Order | Item | Priority | Effort | Dependencies |
|-------|------|----------|--------|-------------|
| 1 | **P0-1: Circular dependency detection** | P0 | ~50 lines | None (standalone) |
| 2 | **P0-2: Crash recovery points 8-12** | P0 | ~80 lines | P0-1 |
| 3 | **P0-3: Secrets redaction verification** | P0 | ~30 lines | P0-1 |
| 4 | **P1-2: Idempotent replay flow** | P1 | ~40 lines | P0-1, P0-3 |
| 5 | **P0-3: (already above)** | — | — | — |
| 6 | **P1-3: Dead-letter recovery policy** | P1 | ~50 lines | P0-1 through P0-3, P1-2 |
| 7 | **P1-1: Complete crash recovery matrix** | P1 | ~30 lines | P0-2 |
| 8 | **P2-1: Scheduler deep integration** | P2 | ~60 lines | P0-1 through P1-3 |
| 9 | **P2-2: Referential dependency checks** | P2 | ~30 lines | P0-1 |
| 10 | **P2-3: Backup compression** | P2 | ~40 lines | P0-1 through P1-3 |
| 11 | **P3-1: Provider SDKs as optional deps** | P3 | ~50+ lines pyproject.toml + adapters | All prior |
| 12 | **P3-2: Agent registry** | P3 | ~50 lines | All prior |
| 13 | **P4-1: Multi-agent orchestration (parent/child)** | P4 | ~80 lines | P0-1, P2-2 |
| 14 | **P4-2: Skills and reusable workflows** | P4 | ~80 lines | All prior |
| 15 | **P4-3: Memory foundation (TTL, indexing, adapters)** | P4 | ~60 lines | All prior |
| 16 | **P5-1: Fuzz testing for edge cases** | P5 | ~30 lines | All prior |
| 17 | **P5-2: Exit code standardization** | P5 | ~20 lines | All prior |
| 18 | **P5-3: Agent security review** | P5 | ~30 lines | All prior |

## Coding Batch Recommendation

**Batch 1 (P0 critical — ~160 lines, 1 week)**:
- P0-1: Circular dependency detection (~50 lines)
- P0-2: Crash recovery points 8-12 (~80 lines)
- P0-3: Secrets redaction verification (~30 lines)

**Batch 2 (P1 reliability — ~120 lines, 1 week)**:
- P1-2: Idempotent replay flow (~40 lines)
- P1-3: Dead-letter recovery policy (~50 lines)
- P1-1: Complete crash recovery matrix to 12/12 (~30 lines)

**Batch 3 (P2 operations — ~130 lines, 1 week)**:
- P2-1: Scheduler deep integration (~60 lines)
- P2-2: Referential dependency checks (~30 lines)
- P2-3: Backup compression (~40 lines)

**Batch 4+ (P3-P5, optional ecosystem features)**:
- Provider SDKs, agent registry, multi-agent orchestration, skills, memory foundation, fuzz testing, exit code standardization, security review.

**Each batch is designed to be completable in ~1 week of development work, with a working verified state at the end of each batch. Batches are independent — if time runs out, earlier batches are complete and later batches can be dropped without regression.**

---
*This implementation backlog is based on actual audit findings across all 23 reports (DEVELOPMENT_ENVIRONMENT_AUDIT through FUTURE_FEATURE_READINESS). Every item has documented current status, required changes, relevant modules, dependencies, risks, acceptance criteria, tests required, configuration prerequisites, and implementation order. No features were implemented in this phase; all work is planning and documentation.*