# 01 — HELIX Repository Comparison and Decision

**Workstream A (Phase 4B.0).** No repository consolidation, move, rename, merge, delete, overwrite, or active installation change performed.

## 1. Copies inspected
| Copy | Path | Symlink/launcher context | Evidence |
|---|---|---|---|
| A — AI workspace | `/run/media/abubakargcx/My Drive/AI_WORKSPACE/helix` | Referenced by user systemd units: `~/.config/systemd/user/helix-live.service` → `ExecStart ... "/run/media/abubakargcx/My Drive/AI_WORKSPACE/helix/tools/live_server.py"`; `oci-a1-launch.service` → `AI_WORKSPACE/helix/tools/oci-a1-launch.sh` (`grep` in `~/.config/systemd/user`) | `git rev-parse`, file tree, systemd unit inspection |
| B — Drive/hermes (runtime-linked) | `/run/media/abubakargcx/My Drive/hermes/helix` | `~/helix` symlink resolves to this path (`readlink -f ~/helix`); historically install target context in docs/scripts | symlink and tree inspection |

`AI_WORKSPACE/HELIX/` (capitalized) **missing**.

## 2. Git history, branches, ancestry, divergence
| Attribute | A — `AI_WORKSPACE/helix` | B — `Drive/hermes/helix` |
|---|---|---|
| Branch | `audit/consolidation-2026-11-06` | `main` (tracking `origin/main`) |
| HEAD | `99c7a3834fc5994fce9aae6964104d47fb74bd74` | `e8a64cf1269b857a0b86fc9f4899bccad4f47cf0` |
| Remote | `origin https://github.com/abubakar40-dev/helix.git` | same |
| Local branches seen | `audit/consolidation-2026-11-06`, `main`, `pre-ponytail-cleanup` | `main`, `pre-ponytail-cleanup` |
| Working tree | **Clean** | **Dirty** (tracked mods/deletions + untracked) |
| Recent commits (A) | `99c7a38 Point the live diagnostic...`, `07a2522 Consume the shared JARVIS voice contract...`, `c68326b Checkpoint: pre-consolidation...`, `e8a64cf Repair Helix dispatch...` | `e8a64cf Repair Helix dispatch...` (same commit as A base) |
| Ancestry | **A is 3 commits ahead of B's HEAD** (`git log e8a64cf..99c7a38` = `99c7a38,07a2522,c68326b`); `e8a64cf` exists in A (`git cat-file` commit) | B at `e8a64cf` (ancestor of A) |

**Evidence:** `git status --short --branch`, `git rev-parse HEAD`, `git log --oneline -10`, `git diff --stat e8a64cf..99c7a38`.

## 3. Tracked/untracked and unique files

### A committed delta over `e8a64cf` (63 files, per `git diff --stat/name-only`)
- **Added/rewritten major components:** `bridge/bridge_ws.py` (+1367), `bridge/helix.desktop`, `bridge/helix_desktop.py` (+370), `install.sh`, `docs/ADD_AN_AGENT.md`, `docs/AGENT_ARCHITECTURE.md`, `docs/PACKAGING_PLAN.md`, large `docs/PROGRESS.md` updates, `tools/lms_client.py`, `ui/build.js`, `ui/helix-ui.html`, `ui/package*.json`, `ui/src/*` modular JS/CSS/HTML, `uninstall.sh`.
- **Removed legacy:** `bridge/server.py`, `deploy/helix-gesture.service`, many `tools/check-*|audit-*|diagnose-*|gesture.py|helix_app.py|measure-layout.py|probe-town.py`, old monolithic `ui/console/*`, `ui/agent-town`, `ui/shell`, `ui/voice-core`, `ui/world-monitor`, inbox artifacts.
- **Modified:** `.gitignore`, `bridge/README.md`, `docs/VOICE_AUDIO_DIAGNOSTIC.md`, selected `tools/*voice/live*` and `tools/selfcheck.py`.

### B working-copy state relative to its HEAD (`e8a64cf`)
- **Tracked modifications:** `.gitignore`, `bridge/README.md`, `docs/PROGRESS.md`, `docs/VOICE_AUDIO_DIAGNOSTIC.md`, `tools/selfcheck.py`.
- **Tracked deletions:** mirrors removal of `bridge/server.py`, `deploy/helix-gesture.service`, legacy check/diagnostic/gesture/app tools, and old UI trees (`ui/agent-town`, `ui/console/*`, `ui/shell`, `ui/voice-core`, `ui/world-monitor`).
- **Untracked additions:** `bridge/bridge_ws.py`, `bridge/helix.desktop`, `bridge/helix_desktop.py`, `docs/ADD_AN_AGENT.md`, `docs/AGENT_ARCHITECTURE.md`, `docs/PACKAGING_PLAN.md`, `install.sh`, `tools/lms_client.py`, `ui/build.js`, `ui/helix-ui.html`, `ui/node_modules/`, `ui/package-lock.json`, `ui/package.json`, `ui/src/`, `uninstall.sh`.
- **Observation:** B's uncommitted direction substantially overlaps A's committed successor architecture (new bridge/desktop/docs/ui build/src/install), but **is not committed** in B and may differ in content details; B also carries local build artifacts (`ui/node_modules`) and lacks A's 3 committed refinement commits.

## 4. Source-code, runtime, dependency, config differences
| Dimension | A — AI workspace | B — Drive/hermes | Assessment |
|---|---|---|---|
| Core bridge/UI architecture | Committed `bridge_ws.py`/`helix_desktop.py`/modular `ui/src`+`build.js` | Same-named files present but untracked/uncommitted; old files deleted in index/worktree | Directionally similar; **B not a clean committed snapshot** |
| Refactor maturity | Includes 3 post-e8a64cf commits (voice contract alignment, live diagnostic fix) | At e8a64cf + local edits/untracked work | A ahead in committed history |
| Runtime coupling | Systemd services reference A paths for live/launch helpers | `~/helix` symlink targets B; install scripts historically target `$HOME/helix` context | **Mixed active references** |
| Dependencies/runtime | GTK/WebKit desktop (`helix_desktop.py`), Hermes CLI/DB paths hardcoded in bridge code patterns, UI node build artifacts possible | Untracked `ui/node_modules` indicates local build state | Env-coupled in both |
| Config differences | `.gitignore` differs as part of commits | `.gitignore` modified but uncommitted | Minor but divergent |
| Features present in one but absent in other | Committed refinements `07a2522`, `99c7a38` (and checkpoint metadata) in A | Possible uncommitted local experiments only in B working tree (unverified vs A content without line-by-line merge audit) | A has **known committed** deltas; B may have **uncommitted/unique** work |

## 5. Active usage and irreplaceable-work signals
- **Active/runtime indicators:** `~/helix` → Drive copy B (strong runtime/link signal). Systemd user units run `AI_WORKSPACE/helix/tools/live_server.py` and `oci-a1-launch.sh` (strong service-path signal). Hermes config showed no direct `helix` key matches in quick grep (inconclusive). Conclusion: **active usage is ambiguous/mixed by component**.
- **Irreplaceable work risk:** B is dirty with uncommitted code/docs/deletions and untracked files plus `ui/node_modules`; these may represent in-progress or machine-local work not captured in A. A contains committed work not present in B. **Neither can be safely discarded without explicit review/approval.**

## 6. Side-by-side comparison (summary)

| Criterion | A `AI_WORKSPACE/helix` | B `Drive/hermes/helix` |
|---|---|---|
| Git cleanliness | Clean | Dirty, uncommitted/untracked |
| Commit recency on shared line | Ahead (+3 commits) | Behind (at base `e8a64cf`) |
| Commit integrity | Coherent checkpoint/refactor commits | Architectural refactor mostly unstaged/uncommitted |
| Symlinked home path | No (`~/helix` not pointing here) | Yes (`~/helix` points here) |
| Systemd helper paths | Yes (live/oci-launch) | No direct match found |
| Data-loss risk if treated as sole source | Low-medium (clean committed) | **High** (uncommitted/untracked/local artifacts) |

## 7. Feature-preservation and data-loss risk assessment
- **If B overwritten/removed without preservation:** high risk of losing uncommitted edits, untracked implementation/docs, local UI build state, and any runtime assumptions tied to `~/helix`.
- **If A ignored:** risk of losing committed voice-contract/diagnostic refinements and cleanly recorded refactor history.
- **If consolidated naively:** high risk of merge conflicts, duplicated/contradictory bridges/UIs, broken launchers/services, and silent behavior changes.
- **Overall:** **High data-loss and operational regression risk** without a reviewed, approved consolidation plan and backups.

## 8. Recommendation (evidence-based) — **requires user approval**

**Recommendation (provisional, evidence-based):** treat **`AI_WORKSPACE/helix` (A, HEAD `99c7a38`, clean, ahead)** as the **authoritative development/source-of-truth candidate** for future integration planning/code review, because it contains the newer committed refactor and refinements; treat **`Drive/hermes/helix` (B, dirty, `~/helix` target)** as a **runtime-linked working copy requiring preservation and explicit reconciliation** before any consolidation.

**Rationale:** A is clean and ahead by 3 commits on the same lineage; B has equivalent-direction but uncommitted/untracked state and is tied to `~/helix` and potentially local runtime artifacts. Mixed service references mean no single copy is provably the sole active runtime for all components.

**Confidence:** Medium-high for source-history comparison; **medium** for "currently active in all contexts" due to mixed references.

## 9. Safe future consolidation plan (deferred) — **not authorized now**
*Decision requiring user approval before execution; no actions taken in 4B.0.*
1. **Freeze & inventory:** full backup/snapshot of both copies (including B untracked/node_modules and `~/helix` target), capture launcher/systemd/desktop references.
2. **Content reconciliation:** diff B working tree vs A commits; identify unique B changes worth preserving; produce patch/review.
3. **Decide canonical runtime path:** choose one install/runtime location and update `~/helix`, systemd units, desktop entries consistently.
4. **Merge in controlled branch:** apply reconciled changes onto chosen canonical repo, run helix/Hermes smoke checks in isolated environment.
5. **Cutover & verify:** switch references atomically, validate bridge/UI/Hermes-kanban flows, keep rollback snapshot.
6. **Retire duplicate:** archive/deprecate non-canonical copy only after verified parity and backup.

## 10. Labels
- **Evidence-based recommendation:** A as authoritative development candidate; preserve B.
- **Decision requiring user approval:** canonical repo/runtime location and any consolidation/cutover.
- **Deferred cleanup/migration:** all consolidation steps above.
- **Existing approved direction:** preserve independent HELIX identity and avoid destructive repo operations.
