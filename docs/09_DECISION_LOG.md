# 09 — Decision Log

Statuses follow the approved vocabulary. A decision is only `FINAL` when AbuBakar has
approved it; anything else is marked as direction, discussion or backlog.

## 1. Inherited from the approved planning package

| Decision | Status |
|---|---|
| AJ is the parent identity and orchestrator | FINAL |
| JARVIS = general/major-work sub-agent, own repo | FINAL |
| HELIX = calling/communications sub-agent, own repo | FINAL |
| Hermes = execution/skill runtime, not an identity | CURRENT DIRECTION |
| Modular monolith + ports/adapters | FINAL DIRECTION |
| No Docker, no local LLM in production | FINAL |
| Provider-independent canonical memory | FINAL REQUIREMENT |
| Multi-provider gateway | CURRENT DIRECTION |
| Calling routed through HELIX under AJ policy | FINALIZED DIRECTION |
| KDE Connect / GSConnect as candidate bridge | VERIFICATION REQUIRED → **now measured: no telephony interface** |
| AJ repository boundary | **UNDER DISCUSSION** (unchanged) |
| Exact Hermes integration contract | UNDER DISCUSSION → **contract drafted here**, attachment gated |

## 2. Decisions made in this phase

| # | Decision | Rationale | Reversible? |
|---|---|---|---|
| D-1 | AJ lives in `AJ/` as a plain package, **not** a git repo | The repo boundary is UNDER DISCUSSION; creating one would pre-empt it | Yes — `rm -rf AJ/` and nothing else changes |
| D-2 | No JARVIS/HELIX source file is modified | Preserve working functionality; the directive forbids risking a running assistant for architectural neatness | N/A |
| D-3 | JARVIS capabilities are **imported** from `core/capabilities.py`, not copied | Prevents two authorities drifting | Yes |
| D-4 | Two permission layers: JARVIS in-process, AJ at the ecosystem boundary | Different scopes; importing the control plane into a sub-agent would invert the dependency | Yes |
| D-5 | Capability ids are namespaced `<agent>.<tool>` | Makes ownership unambiguous in audit lines and routing | Yes (migration is a rename) |
| D-6 | `executable` requires non-unknown availability | A capability whose bridge is down must not be offered | Yes, per capability |
| D-7 | FAILED is recoverable; COMPLETED/ABORTED/CANCELLED are final | Failure is the entry point of the recovery path, not a dead end | Yes |
| D-8 | Provider adapters require an injected transport | Guarantees no accidental network call and makes routing testable | Yes |
| D-9 | GSConnect reports discovery only | The telephony interface is genuinely absent; inventing DBus method names would be fiction | Yes, when a bridge exposes it |
| D-10 | Rollout of AJ into JARVIS/HELIX is opt-in, not automatic | Avoids touching a running assistant without runtime verification | Yes |

## 3. Awaiting the owner

| # | Question | Why it matters |
|---|---|---|
| Q-1 | Should `AJ/` become a repository? | Determines versioning, backup and review workflow |
| Q-2 | Approve an additive `POST /aj/task` endpoint in JARVIS and HELIX? | Without it, delegation cannot be productive |
| Q-3 | Which bridge is allowed to place calls (GSConnect plugin, native dialer handoff, VoIP)? | Calling capability is blocked on this |
| Q-4 | May the two HELIX trees (`AI_WORKSPACE/helix` and `My Drive/hermes/helix`) be reconciled? | The running service uses the diverged copy |
| Q-5 | Provider credentials and the real model catalogue | The gateway cannot make a verified call without them |
| Q-6 | Is JARVIS's live voice path allowed to be policy-gated now? | Closes `S-5`, but requires an edit plus audio verification |
| Q-7 | `memory/personal_memory.sqlite3` in git — untrack? | `S-6`; owner's data, owner's decision |

## 4. Explicitly not decided here

Microservices, a message broker, Docker, local inference, autonomous skills, permission
escalation, phone automation beyond the verified bridge, UI redesign, Windows/macOS/mobile
adapters, robotics.
