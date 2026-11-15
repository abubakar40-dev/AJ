# 05 — Memory and Data Ownership

## 1. Actual memory/data implementations (inspected)

| System | Data types present (actual) | Storage/location | IDs/provenance/timestamps | Mutability/history behavior | Backup/restore evidence | Confidence |
|---|---|---|---|---|---|---|
| **AJ** | Raw task/control events & evidence: task records/history, audit events, journal, receipts, leases, operation evidence; canonical memory raw events + derived summaries; idempotency records | `~/.local/share/aj` defaults (configurable): `tasks.jsonl`, `audit/events-*.jsonl`, `journal.jsonl`, `receipts.jsonl`, `reconciliation_operations.jsonl`, `leases/*`, `idempotency.json`, `memory.sqlite3` (WAL) | Task/operation/attempt/lease/receipt/event IDs present; timestamps in records/events; append-only emphasis in 3A–3E design | Append-only stores for evidence/task envelopes; summaries derived/rebuildable; conservative import/export/backup tooling exists (`transfer.py`) | `backup/export/import/verify` implemented in CLI/code; restore validation tested in prior suites (not re-run 4A) | High |
| **JARVIS** | Personal memory facts (SQLite), workspace/conversation/task-ish persistence, raw chat history markdown, Obsidian vault markdown (dual-write intent), browser profile/config data | `JARVIS/memory/personal_memory.sqlite3`, `JARVIS/config/workspace_store.sqlite3`, `JARVIS/chat_history/*.md`, Obsidian vault `~/.obsidian-vault/` (per `obsidian_integration.py`), config/browser profile dirs | SQLite rows/keys/timestamps vary (`memory_db`, `workspace_store`, chat markdown headings/dates); Obsidian markdown frontmatter/content; provenance across stores not unified | Dual-write SQLite+Obsidian and markdown logs can diverge; overwrite/update semantics depend on component; historical preservation not guaranteed across all stores | No verified cross-store backup/restore workflow observed; SQLite/markdown files exist but restore integrity unproven | Medium-High (presence), Medium (integrity guarantees) |
| **Hermes** | Runtime/session state, gateway state, kanban tasks/events, memories/user profile, skills, cron/jobs, platform/channel metadata, caches/logs | `~/.hermes/` (e.g. `config.yaml`, `state`/session DBs implied, `kanban.db`, `gateway_state.json`, `memories/`, `skills/`, `cron/`, `cache/`, logs), source/skills in `~/.hermes/hermes-agent` | Rich internal IDs (sessions, task/run IDs like `t_*` in kanban ecosystem, message/chat IDs in gateway/platforms) implied; timestamps present in state/config/log artifacts | Mix of append/event-like and mutable state records; schema/semantics owned by Hermes subsystems | Hermes manages its own state/backups features in general product scope (CLI has backup/import commands), but **not verified** in this environment/audit | High (presence/runtime), Medium (semantics/restore) |
| **helix copies** | UI/bridge state primarily derived from Hermes/kanban; local logs/artifacts; minimal independent canonical memory observed | `AI_WORKSPACE/helix` and `~/helix -> Drive/hermes/helix` source trees, `~/.local/state/helix` paths referenced | Mostly consumes Hermes task/profile IDs; limited own persistence | Not a canonical data owner in observed design; acts as viewer/bridge | No independent backup/restore evidence | Medium |

## 2. Classification by requested memory/data type

| Data type | Current primary location(s) | Canonical owner today | Provenance quality | Reliability/integrity notes | Integration risk |
|---|---|---|---|---|---|
| 1. Raw conversation records | JARVIS `chat_history/*.md`, JARVIS workspace interactions; Hermes sessions/messages/gateway logs; helix displays | **Ambiguous (domain split)** | Medium (timestamps/text exist) but fragmented | Duplicated across assistant/runtime surfaces; no unified replay guarantee | Conflicting histories if merged naively |
| 2. Raw task and execution events | AJ audit/journal/receipts/op-evidence/leases; Hermes kanban events/sessions/gateway state; JARVIS agent runtime events/logs | **AJ for AJ-orchestrated tasks; Hermes/JARVIS for their own** | AJ high within scope; others variable | AJ append-only/evidence-based; Hermes/JARVIS event models differ; cross-store non-atomicity in AJ and no cross-system tx | Mapping errors, false completion claims |
| 3. Canonical structured memory | JARVIS `personal_memory.sqlite3`; Hermes memories/profile stores; AJ task/memory domain stores (different purpose) | **Ambiguous by domain** | Medium | Different schemas/semantics; AJ memory is control/event oriented, not personal canonical memory | Overwrite/collision if treated as same domain |
| 4. Derived summaries | AJ `summary.py` outputs; Hermes compression/summaries; JARVIS/Obsidian notes | **Local per system** | AJ deterministic/rebuildable; others unverified | Non-equivalent derivations; possible drift | Misinterpretation across systems |
| 5. Search indexes | Hermes FTS5/session search capabilities implied; JARVIS search over memory/chat/obsidian patterns; AJ simple memory retrieval/LIKE-style in places | **Local per system** | Medium-Low for cross-system | Rebuildability/index freshness unverified | Inconsistent retrieval results |
| 6. Obsidian notes and backlinks | JARVIS integration targets `~/.obsidian-vault`; `OBSIDIAN_SETUP.md` and code present | **JARVIS-adjacent knowledge/navigation layer** | Medium (markdown provenance fields possible) | Obsidian is not a canonical DB; dual-write sync risk | Stale/broken links, divergence from canonical stores |
| 7. Runtime/session context | Hermes sessions/gateway context; JARVIS in-memory/runtime/UI state; AJ process-local execution context | **Local runtime owners** | Medium | Ephemeral/rotating; not durable canonical records | Context loss on restart/handoff |
| 8. External memory services/adapters | Hermes plugins/memory providers possible; JARVIS Obsidian local REST/API integration in code | **None verified as canonical external service** (Honcho present locally as dirs but not integrated/installed per audit constraints) | Low-Medium | Availability/auth/consistency unverified | Hidden dependency, privacy/trust risks |

## 3. Key ownership findings

### Stable IDs / provenance / ordering
- **AJ:** strong ID discipline within control-plane domain (task/operation/attempt/lease/receipt/event identifiers) and timestamps; provenance suitable for audit/recovery in scope. **Cross-store atomicity lacking** but detectable.
- **JARVIS:** mixed identifiers (markdown time blocks, sqlite keys, orchestration/task IDs in agent runtime) with no single provenance envelope across sqlite/markdown/Obsidian.
- **Hermes:** rich internal IDs (sessions, kanban tasks/runs, platform chat IDs) but cross-system mapping to AJ/JARVIS undefined.
- **Ecosystem:** no global correlation/provenance contract.

### Reconstruction / backup / restore
- **AJ:** reconstructable in-domain via append-only records and derived summary rebuild; backup/export/import/verify tooling exists (recorded tests). Restore **tested in prior cycles** (not re-run now).
- **JARVIS:** no verified unified restore procedure across personal memory DB, chat history, workspace store, and Obsidian vault; dual-write increases divergence risk.
- **Hermes:** state spread across multiple DB/files; backup/import capabilities exist in product CLI surface, but environment-specific restore verification **not evidenced** here.
- **helix:** derivative/UI layer; not authoritative.

### Conflict / canonical-database risks
- **High risk:** treating JARVIS personal memory, Hermes memories/sessions, and AJ task evidence/memory as one canonical source.
- **Medium-high risk:** JARVIS dual-write (SQLite + Obsidian) and chat markdown side logs creating conflicting truths without reconciliation.
- **Medium risk:** duplicate helix copies pointing to/deriving from Hermes state causing operator confusion (which runtime/UI is authoritative).
- **Mitigation principle (recommended):** preserve domain-canonical stores; use immutable provenance links/correlation records for cross-references; Obsidian remains navigation/knowledge projection, not canonical DB.

## 4. Recommended ownership model (evidence-based, not an approved architecture change)
| Domain | Canonical owner | Other components may | Must not |
|---|---|---|---|
| AJ-orchestrated task lifecycle, control evidence, reconciliation records | **AJ** | Read/subscribe via adapter; mirror status with correlation IDs | Overwrite AJ task/evidence history; claim completion without AJ/evidence mapping |
| Personal assistant conversation & personal continuity memory | **JARVIS** | Project/export to Obsidian/notes; share references to AJ tasks | Store AJ execution evidence as personal memory truth; let other systems mutate canonical personal records |
| Hermes runtime sessions/skill execution internals and kanban operational records | **Hermes** | Emit mapped results/evidence to AJ when delegated | Become AJ canonical task store or JARVIS personal memory store |
| HELIX complex-work artifacts (once canonical) | **HELIX** | Return artifacts/summaries/evidence links to requester/AJ | Duplicate AJ control-plane evidence as authority |
| Knowledge navigation/notes graph | **Obsidian (projection)** | Render links/backlinks/views from canonical sources | Serve as sole canonical database for tasks, auth, or raw event truth |

**Decision status:** recommendation based on evidence; requires explicit architectural approval before implementation.