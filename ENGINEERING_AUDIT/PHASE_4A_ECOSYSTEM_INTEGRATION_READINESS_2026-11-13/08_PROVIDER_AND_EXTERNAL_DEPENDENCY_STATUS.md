# 08 — Provider and External Dependency Status

## 1. Providers and model integrations

| Component | Provider/model surface | Config/adapter evidence | Credential/config presence (no secrets) | Reachability/execution verified? | Fallback/error handling (observed) | Free-first / cost risk | Status |
|---|---|---|---|---:|---|---|---|
| **AJ** | Provider gateway abstraction with named adapters (OpenRouter/Groq/Gemini/NVIDIA/Cloudflare/local) in config; placeholder/default model behavior noted previously | `aj/providers.py`, `config/aj.config.json` (`providers.adapters.*`), env-based credential names | Env var names configured; values not inspected; no live transport wired by default | **No** (no live provider calls made/verified) | Gateway includes retry/cooldown/fallback logic in code (unverified live) | Compatible with free-first if configured, but quotas/availability unverified | **Present in source/config only; live unverified** |
| **JARVIS** | Multiple client modules (`groq_client.py`, `or_client.py`, `nrouter_client.py`, `grok_client.py`, `ollama_client.py` implied by deps/history), Gemini/OpenRouter references in README/code | `requirements.txt`, client files, `config/api_keys.json` exists | `config/api_keys.json` present (contents not disclosed); env/config usage patterns in code | **No** in 4A | Fallback/resilience claims in docs/code (e.g. OpenRouter fallback) not runtime-verified | Depends on configured providers; free tiers not assumed | **Partially implemented, unverified** |
| **Hermes** | Rich provider/model/fallback system (`model.provider=openrouter`, `fallback_providers` in config, `hermes model/fallback` CLI) | `~/.hermes/config.yaml`, `hermes --help`, Hermes docs/source | Provider auth/config present in Hermes home (`auth.json`, `.env` exists; values redacted/not disclosed) | **Indirect/partial:** gateway runtime active and configured; specific provider calls not executed in 4A | Config shows fallback providers, retries/guards in multiple subsystems | Configured with free/openrouter models in observed config; availability/quotas still unverified | **Configured and runtime-active; provider E2E unverified** |
| **HELIX (helix copies)** | Primarily delegates to Hermes/profiles/models; UI/bridge may invoke TTS/STT/local tools | helix docs/bridge code | Depends on Hermes/local tool installs | **No** | Dependent on Hermes/toolchain availability | Indirect | **Dependent/unverified** |

**Notes:** No paid API calls made. Advertised models/quotas/stealth/free availability treated as unverified; adapter/model names are not proof of function.

## 2. External dependencies and integrations

| Dependency/integration | Used by | Evidence of presence | Configuration/dependency available? | Starts/loads? | Basic execution verified? | Risk/constraints | Status |
|---|---|---|---|---:|---:|---|---|
| **Hermes gateway/platform runtime** | Hermes, helix bridges consume Hermes state | `~/.hermes` state, `gateway_state.json` running, processes (`hermes gateway run`, whatsapp bridge, supervisor) | Yes | **Yes (observed)** | Partial/indirect only | Active runtime can mutate state; integration boundary unverified | **Running, unverified for AJ integration** |
| **WhatsApp platform (Hermes)** | Hermes | `platforms.whatsapp.enabled: true`, connected in gateway state | Yes (in Hermes config/state) | Yes | Not tested | Privacy/external side effects; credential/channel coupling | **Connected (observed), functional depth unverified** |
| **Other messaging platforms (Telegram/Discord/Slack/Signal etc.)** | Hermes/JARVIS deps | Hermes toolsets/platform config scaffolding; JARVIS has discord deps/bridge-related code | Mixed/unverified | Unverified | No | Auth/secrets/side effects | **Source/config present to varying degrees, unverified** |
| **MCP servers/tools** | Hermes | Extensive MCP code/tests and CLI/config support in Hermes source/config structures | Unverified per server | Unverified | No | Supply-chain/permission risks, runtime variability | **Framework present, instances unverified** |
| **Kanban (`~/.hermes/kanban.db`)** | Hermes, helix bridges | DB present; helix reads/integrates; Hermes CLI has `kanban` | Yes | DB accessible likely (not probed destructively) | No | Schema/dispatch correctness and contention unverified | **Present, unverified** |
| **SQLite stores (AJ/JARVIS/Hermes)** | All | Multiple `.sqlite3` files/WAL/SHM observed | Yes | N/A | AJ tested previously; others not verified | WAL/locking/fs semantics, corruption/consistency risks | **Present; AJ verified in-domain, others unverified** |
| **Obsidian vault + local API** | JARVIS | `obsidian_integration.py` targets `~/.obsidian-vault`, references local REST API config; Obsidian setup docs | Partially (code/config present); vault/app runtime unverified | Unverified | No | Token handling, sync divergence, API availability | **Implemented in source, unverified** |
| **GTK/WebKit/PyQt/desktop UI deps** | JARVIS, helix, AJ orb | Source/scripts require GTK3/WebKit2GTK or PyQt6; environment support unverified | Unverified | Unverified | No | Platform/display dependency, headless incompatibility | **Source present, environment unverified** |
| **Browser automation/Playwright/CDP** | JARVIS, Hermes toolsets | JARVIS deps include playwright; Hermes browser toolsets present; helix tools include browser scripts | Unverified | Unverified | No | Fragile env, security/sandbox concerns | **Present in source/config, unverified** |
| **Speech/TTS/STT (edge/piper/espeak/live/whisper/etc.)** | JARVIS, helix, Hermes | Code references and config (Hermes STT enabled in config) ; binaries/venvs referenced in helix scripts | Partially/unverified | Unverified | No | Device/audio availability, network for edge services | **Partially configured/implemented, unverified** |
| **Git/CLI tooling (`hermes`, shells, system utilities)** | Hermes/helix/AJ ops | Hermes CLI installed/help works in environment context? (not executed fully to avoid side effects beyond read-only help not run here except planning), paths referenced | Yes for Hermes home binaries/paths observed | Hermes processes active | Limited | Path coupling (`/home/abubakargcx/.local/bin/hermes`) | **Available/active in parts, fragile paths** |
| **Network access (local loopback/external APIs)** | All | Configs/endpoints defined; gateway connected to whatsapp | Available in environment (inferred) | N/A | Not exercised for providers in 4A | Data egress/privacy, quota/cost, reliability | **Available but untrusted for claims** |

## 3. Credential ownership and coupling (high-level, non-secret)
- **AJ:** expects provider credentials via environment variables per config; no credentials stored in repo config by design.
- **JARVIS:** `config/api_keys.json` and client modules suggest local credential storage/use; ownership/coupling to assistant-specific workflows likely.
- **Hermes:** centralized in `~/.hermes` (`config.yaml`, `.env`, `auth.json`, platform credentials/state); serves Hermes runtime broadly (CLI/gateway/channels).
- **Risk:** cross-project credential reuse/copying and over-broad access are possible; exact sharing cannot be confirmed without exposing secrets (not done). Integration must apply least privilege and explicit credential boundaries.

## 4. External dependency readiness verdict
- **Verified operational now:** Hermes gateway process/state active (independent of AJ integration).
- **Verified in-domain (historical):** AJ local stores/control-plane behaviors per Phase 3F recorded results.
- **Unverified:** all live provider completions, messaging/tool side effects, desktop/voice/browser automations, Obsidian sync, cross-component integrations, and restore/HA behaviors.
- **Constraint adherence:** no paid API calls, no installs/upgrades, no service restarts, no Honcho installation, no dependency removal. Free-first remains policy, not proof of availability.