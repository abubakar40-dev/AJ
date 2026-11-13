# 06 — Workspace and Repository Status

**Measured:** 9 November 2026 · **Changes made by this phase:** additive only (`AJ/`)

## 1. Top level

| Path | Role | Touched? |
|---|---|---|
| `AJ/` | **new** control plane, contracts, docs, tests | created |
| `JARVIS/` | JARVIS sub-agent repo (`audit/consolidation-2026-11-06`) | **no source change** |
| `helix/` | HELIX sub-agent repo (`audit/consolidation-2026-11-06`) | **no change** |
| `gods-eye-view/` | third-party upstream, consumed by the globe service | no |
| `audit/` | Nov 2026 audit set | no |
| `backup/` | recovery store (tarballs, relocated duplicates) | no |
| `DATA/`, `LMS Docs/` | data and research | no |
| `.hermes/` | Hermes runtime — **present again**, owner-led preparation | **not touched** |

`.hermes/` was absent on 6 November and is present now. The owner is preparing Hermes
separately; this phase read only the directory listing and did not open files, services,
databases or configuration.

## 2. Git

| Repo | Branch | Working tree | Remotes |
|---|---|---|---|
| `JARVIS` | `audit/consolidation-2026-11-06` | 2 untracked (`chat_history/2026-11-04.md`, `2026-11-05.md`); transient sqlite `-shm`/`-wal` appeared and cleared on their own | none configured |
| `helix` | `audit/consolidation-2026-11-06` | clean | `abubakar40-dev/helix` (unchanged) |

No commit, push, branch, remote or history change was made. `AJ/` is **not** a git
repository: the approved architecture leaves the AJ repository boundary `UNDER DISCUSSION`,
so creating one would pre-empt an owner decision.

## 3. Discrepancy found: the running HELIX is not the workspace HELIX

```
$ readlink -f ~/helix
/run/media/abubakargcx/My Drive/hermes/helix
```

`~/helix` is a **symlink to `My Drive/hermes/helix`**, not to `AI_WORKSPACE/helix`.
`helix-live.service` and `oci-a1-launch.service` execute scripts from `~/helix`, so they
run that tree. The November audit flagged this as unverified (§5.1); it is now verified.

**Consequence:** changes under `AI_WORKSPACE/helix/` do not affect the running voice
service. `My Drive/hermes/helix` has diverged history with unique commits, and the audit
deliberately left it untouched. Reconciling the two trees needs an owner decision — this
phase did not touch either.

## 4. Running services (observed, not modified)

| Unit | State | Port |
|---|---|---|
| `helix-globe.service` | active | Vite globe |
| `helix-live.service` | active | `127.0.0.1:8788` |
| `oci-a1-launch.service` | active | — |
| HELIX bridge (own process) | listening | `127.0.0.1:8765` |
| JARVIS bridge | **not running** | 8875 not listening |

## 5. Integration test plan for the sub-agents (not yet executed)

Neither sub-agent exposes an AJ task endpoint today:

- JARVIS's `bridge_ws.py` is a WebSocket protocol; there is no documented HTTP task
  route. When JARVIS runs, `HttpAgentAdapter.available()` will be true but
  `protocol_verified` false, and a delegation returns `rejected` with an explanation.
- HELIX's `bridge/bridge_ws.py` is also WebSocket-only (HTTP `GET /` returns nothing).

So the adapters are wired and honest, not productive. Making them productive requires an
approved, additive endpoint on the sub-agent side, for example:

```
POST /aj/task   {AgentRequest}  → {AgentResult}
```

with the same JSON shapes as `schemas/`. That is a change to a working codebase, so it
needs the owner's approval; AJ must not reach into their internals instead.

## 6. Unrelated projects

Dental Lounge, OmniRest and every other project are out of scope and untouched. No Docker
was introduced, no local model was installed, no dependency was added to JARVIS or HELIX.
