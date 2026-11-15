# 05 — Memory and Data Ownership Contract

**Workstream E (Phase 4B.0).** Domain ownership and cross-component reference rules for future integration. No memory store migration, merge, or unification performed/specified as implementation.

## 1. Principles (existing approved direction)
- Preserve **independent project identities** and **domain-specific data ownership**.
- **No canonical store merges** across components; no component becomes canonical for another domain's records.
- **Obsidian is navigation/knowledge projection, not a canonical database.**
- Cross-component integration uses **stable identifiers, correlation, provenance, and references** — not overwrite/copy-as-authority.
- AJ coordinates AJ-governed execution; personal memory and runtime internals remain with their owners.

## 2. Domain ownership

| Domain / data class | Canonical owner | Evidence (current systems) | Other components may | Must not |
|---|---|---|---|---|
| AJ task state, lifecycle transitions, leases/attempt records (AJ-governed) | **AJ** | `aj/task.py`, task store/audit/journal/receipts/leases (`aj/*`, 3A–3F) | Read/reference by correlated IDs; receive status updates mapped through approved contract | Mutate AJ task history/evidence as authority; claim completion without AJ evidence criteria |
| AJ operation evidence, authorization decisions, audit, recovery/reconciliation records | **AJ** | `aj/audit.py`, `aj/operation_evidence.py`, `aj/receipts.py`, `aj/recovery.py`, `aj/authorization.py` | Consume evidence refs/summaries; append correlated external refs via AJ records | Store external runtime logs as AJ-canonical truth without provenance mapping; forge/alter evidence |
| JARVIS personal conversations, user preferences, personal continuity memory | **JARVIS** | `chat_history/*`, `memory/*sqlite*`, `workspace_store.sqlite3`, `obsidian_integration.py` | Project/export references to Obsidian/notes; link AJ task IDs/correlation IDs as references | Allow AJ/Hermes/HELIX to overwrite canonical personal memory; mix AJ control evidence as personal-memory truth |
| HELIX delegated work artifacts and internal execution context | **HELIX** (once canonical target approved) | helix repos/bridges/UI/tools (diverged copies; `01`) | Return artifacts/summaries/evidence refs to requester/AJ via contract | Duplicate AJ control-plane evidence as authority; assume current helix copy canonical before decision |
| Hermes runtime sessions, skill/tool execution state, kanban and runtime internals | **Hermes** | `~/.hermes/state/sessions/kanban.db/gateway_state/logs/config` | Emit mapped results/IDs/status to AJ when delegated through approved adapter; expose read-only status evidence as allowed | Become AJ canonical task store or JARVIS personal memory store; be treated as unrestricted authority |
| Knowledge navigation, notes, backlinks, projections | **Obsidian (projection layer)** | JARVIS Obsidian integration/vault usage (implementation present) | Render links/views from canonical sources with provenance | Serve as canonical DB for tasks/auth/raw events; be source of truth over canonical stores |

## 3. Cross-component reference model (no merge)

### 3.1 Reference envelope (logical)
Cross-system records exchange **references**, not ownership transfer:
- `source_system` (`aj|jarvis|helix|hermes|obsidian`), `source_record_type`, `source_record_id`
- `correlation_id` (AJ/global), plus mapped IDs (`aj_task_id`, `operation_id`, `attempt_id`, `hermes_execution_id/session_id/run_id` when evidenced)
- `provenance` (who produced, interface/adapter, trust mode, timestamps, confidence/evidence pointers)
- `integrity` hints (hash/digest/size where applicable, optional)
- `classification` (control-evidence / personal-memory / runtime-internal / projection) and redaction marker

### 3.2 Stable identifiers and timestamp handling
- Preserve native IDs as **opaque strings**; never rewrite Hermes/JARVIS/HELIX native IDs into AJ IDs except via explicit mapping records.
- All mapping records stored in AJ for AJ-governed flows must include AJ correlation + native external ID + observation time.
- Timestamps recorded in UTC ISO-8601 where serialized; keep source timestamp and AJ-observed timestamp distinct when both known.
- If external ID/timestamp unavailable, store `null` + `unavailable/unobserved` reason (no invention).

### 3.3 Provenance and correlation
- Every cross-boundary status/result/ref must carry `correlation_id` and provenance of producing component/interface.
- AJ evidence distinguishes: AJ-derived facts, adapter-observed facts, Hermes-reported facts (untrusted until validated/mapped).
- Conflicts resolved by domain ownership: AJ canonical for AJ task/evidence, Hermes canonical for Hermes runtime internals, JARVIS canonical for personal memory, etc.

## 4. Redaction, retention, and boundaries
- **Redaction:** secrets/credentials/tokens removed before cross-domain persistence; personal-memory content excluded from AJ control evidence unless explicitly required and approved (minimize by default).
- **Retention boundaries:** each owner applies its own retention/lifecycle; AJ retains correlation/evidence refs needed for audit/recovery per AJ policy (not full Hermes/JARVIS stores).
- **Result references:** prefer bounded refs/digests and ownership-aware pointers over copying large/runtime-private artifacts into foreign canonical stores.

## 5. Backup/restore responsibilities
| Owner | Responsibility | 4B.0 finding |
|---|---|---|
| AJ | Backup/restore/verify for AJ stores per existing tools/procedures | Tooling exists; prior verification recorded (not re-run) |
| JARVIS | Personal memory/chat/workspace/Obsidian projection backups and restore integrity | Unified restore unverified; dual-write divergence risk (4A) |
| Hermes | `~/.hermes` state/sessions/kanban/config/skills backup/restore | Capabilities exist in product surface but environment-specific restore unverified |
| HELIX | Canonical artifacts once target decided | Ambiguous due to duplicate copies; deferred |

**Integration implication:** AJ evidence must record that external references may become unavailable; `unknown/result_unavailable` handled per `03/06`.

## 6. Prohibited actions (contract)
- No migration or unification of memory stores in 4B.0/4B.1 without separate approved plan.
- No Obsidian-as-canonical-database behavior.
- No copying personal conversation/memory into Hermes execution prompts/logs beyond minimal, explicitly approved, redacted operational context.
- No collapsing distinct status models into guessed unified states.

## 7. Labels
- **Existing approved direction / evidence-based recommendation:** domain separation, projection-not-canonical for Obsidian.
- **Provisional design:** reference envelope fields and mapping persistence.
- **Deferred idea:** automated cross-store reconciliation/indexing products.
