# 03 — Provider Gateway

**Status:** implemented, no live provider verified · **No credentials were used**

## 1. Shape

```
ChatRequest (messages, requirements)
        │
        ▼
ProviderRegistry.candidates()      usable adapter + model that fits the request
        │                          (enabled, credentialed, healthy, capability match)
        ▼
Gateway.complete()                 bounded attempts per provider, then fallback
        │
        ├── OpenAICompatibleAdapter  OpenRouter · Groq · NVIDIA · local
        ├── (same shape)             Gemini, Cloudflare — declared, disabled by default
        └── transport                injected; absent means no network call
```

## 2. Rules encoded

| Rule | Where |
|---|---|
| An adapter is usable only with base URL **and** credential **and** transport | `OpenAICompatibleAdapter.usable` |
| No provider name in business logic | callers use `ChatRequest`, never a slug |
| 401/403 is not retried | `PROVIDER_AUTH`, `retryable=False` |
| 429 is retried then cooled down | `note_failure` → `quota_until` |
| 5xx is retryable, then falls back | `Gateway.complete` |
| No usable provider is an error | `PROVIDER_UNAVAILABLE`, never an empty answer |
| Advertised free tiers are not assumed | nothing in the code references a quota figure |

## 3. Capability-aware selection

`ChatRequest` carries `require_tools`, `require_vision`, `min_context` and an optional
`model_hint`. `ModelSpec.fits()` filters candidates; a model that cannot do the job is
never chosen because it was listed. This is the mechanism that prevents the NaraRouter
mistake (a model appearing in a list does not mean it accepts the request).

## 4. Health

Per-provider `Health` tracks failures, last failure, last success and a quota cooldown. A
provider that failed recently is skipped until `health_ttl_seconds` elapses. Cooldowns
prevent the tight retry loop that turns one rate limit into an outage.

## 5. What is *not* done

- No live request was made. Every adapter needs a transport, and none is supplied in this
  phase. That is intentional: constructing the gateway must not phone home.
- Model catalogues are placeholders (`<provider>:default`). Real model ids and context
  windows come from the owner's current provider documentation, not from memory.
- Cost/usage accounting is not implemented beyond passing `usage` through.
- Streaming is not implemented.

## 6. Wiring a real provider (later, with owner approval)

```python
def transport(method, url, headers, body, timeout):
    # urllib / httpx / requests — the caller owns the dependency and the retry policy
    ...

registry = ProviderRegistry.from_config(config, transport=transport)
gateway  = Gateway(registry, max_attempts=config.get("providers.max_attempts", 2))
```

Credential names are fixed by configuration (`OPENROUTER_API_KEY`, `GROQ_API_KEY`,
`GEMINI_API_KEY`, …) and read from the environment. Never store them in
`config/aj.config.json`, and never log `headers`.

## 7. Accepted durability risk

The month-to-month reality of free tiers means a provider can disappear. The gateway
treats that as normal operation: unhealthy providers are skipped, fallback is bounded, and
the caller gets a normalized error when nothing is left. No capability is allowed to
depend on one provider being alive.
