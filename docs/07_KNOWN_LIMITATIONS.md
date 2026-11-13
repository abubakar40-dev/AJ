# 07 — Known Limitations

Every item below is a limitation, a failure or an unverified claim. Nothing here is
dressed up as working.

## 1. Failing tests that pre-date this phase (JARVIS)

`JARVIS: 514 passed, 2 failed` (verified again today, 9 Nov 2026). Both are the same two
recorded in the November audit and were neither caused nor fixed by this work:

| Test | Meaning | Severity |
|---|---|---|
| `test_the_audio_writer_uses_the_lock` | `_send_realtime` writes to the Live session without the `_session_write` lock | High — concurrent writes can drop or reorder audio |
| `test_boot_speaks_the_greeting_not_the_briefing` | `_speak_boot_greeting` is no longer called from `main()` | Medium — startup is silent |

Both sit inside the live voice path of a 3,600-line async method, and audio behaviour
cannot be verified from this session (no microphone, no speaker, no display). Fixing them
without that verification would be guessing. **UNVERIFIED / OPEN.**

## 2. AJ-side gaps

| # | Gap | Impact |
|---|---|---|
| A-1 | No sub-agent task endpoint exists | Delegation returns `rejected` with an explanation; no live task has been delegated |
| A-2 | Only 2 of 38 capabilities executable | JARVIS/HERMES capabilities need availability + verification evidence |
| A-3 | Router is a rule table, not an intent classifier | Deterministic and testable, but "call" vocabulary is the only domain split |
| A-4 | Memory search is `LIKE`, no embeddings | Adequate for small stores; recall quality is untested at scale |
| A-5 | Provider gateway has no transport wired | No live completion has been made; model catalogues are placeholders |
| A-6 | Audit is not yet written by JARVIS's live dispatch chain | JARVIS `S-5` remains open; its agent path is gated, its live voice path is not |
| A-7 | Tasks persist to JSONL but are not rehydrated on start | History is complete; in-memory task lookup after a restart is not restored |
| A-8 | No scheduler/queue | Long-running or queued work is not implemented |

## 3. Calling (HELIX domain)

| Claim | Status |
|---|---|
| Paired phone present (Redmi A3) | **verified** |
| Dial a number through the bridge | **unavailable** — no telephony interface exported |
| Receive/answer/reject/end a call | **unavailable** |
| Call state reading | **unavailable** |
| Laptop audio routed into a cellular call | **unverified** |
| `kdeconnect-cli` route | **unverified** — binary not installed |
| HELIX `tools/whatsapp.py` message send | **implemented_unverified** — no delivery test |

## 4. Environment

| Item | Status |
|---|---|
| Running HELIX tree | `~/helix` → `My Drive/hermes/helix` (diverged copy), **not** `AI_WORKSPACE/helix` |
| JARVIS app | not running; bridge 8875 closed |
| Hermes runtime | present under `~/.hermes`, **owner-led preparation, not inspected or touched** |
| Desktop automation | **broken/unknown** per the November audit; not re-tested (needs the real display) |
| Machine headroom | 6.9 GiB RAM, 2 concurrent HELIX services already running; keep new work in-process |

## 5. Security items still open from the November audit

- `S-2` LMS client authenticates with a stored password; downloads uncapped.
- `S-3` JARVIS bridge sends `Access-Control-Allow-Origin: *` on a loopback service.
- `S-5` JARVIS live dispatch chain is not policy-gated (see A-6).
- `S-6` `memory/personal_memory.sqlite3` is tracked in git.
- `S-9` dependency manifests are unpinned.

None were touched in this phase; they belong to JARVIS, and changing them is a separate
approved task.

## 6. What this phase did **not** attempt

Hermes integration, provider accounts, phone calls, desktop automation, UI work, Docker,
local LLMs, microservices, repository merges, branch changes, pushes, deletions or
migrations.
