"""Provider gateway tests: selection, fallback, rate limits, no silent success."""

from __future__ import annotations

import json

import pytest

from aj import errors
from aj.providers import (
    ChatRequest,
    Gateway,
    Message,
    ModelSpec,
    OpenAICompatibleAdapter,
    ProviderRegistry,
    ProviderSpec,
)


def _ok_transport(text="hello"):
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append({"url": url, "headers": headers, "body": body})
        payload = {"model": "m", "choices": [{"message": {"content": text},
                                              "finish_reason": "stop"}],
                   "usage": {"total_tokens": 5}}
        return 200, json.dumps(payload).encode()

    transport.calls = calls
    return transport


def _transport_with(status, text=""):
    def transport(method, url, headers, body, timeout):
        if status == 200:
            return 200, json.dumps(
                {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}
            ).encode()
        return status, json.dumps({"error": {"message": text or "nope"}}).encode()

    return transport


def _registry(*entries, transport):
    providers, adapters = [], {}
    for slug, status in entries:
        providers.append(ProviderSpec(
            slug=slug, base_url=f"https://{slug}.test/v1", credential_env=f"{slug.upper()}_KEY",
            enabled=True, models=[ModelSpec(model_id=f"{slug}-model", provider=slug)],
        ))
        adapter_transport = transport if callable(transport) else transport
        adapters[slug] = OpenAICompatibleAdapter(
            slug=slug, base_url=f"https://{slug}.test/v1", api_key="k",
            transport=adapter_transport if status == 200 else _transport_with(status),
        )
    return ProviderRegistry(providers, adapters)


def request():
    return ChatRequest(messages=(Message("user", "hi"),))


def test_successful_completion_is_normalised():
    registry = _registry(("alpha", 200), transport=_ok_transport("hello"))
    response = Gateway(registry).complete(request())
    assert response.text == "hello" and response.provider == "alpha"
    assert response.attempts == 1 and response.fallback_used is False
    assert response.usage == {"total_tokens": 5}


def test_rate_limit_falls_back_to_the_next_provider():
    registry = _registry(("alpha", 429), ("beta", 200), transport=_ok_transport("from beta"))
    response = Gateway(registry, max_attempts=1).complete(request())
    assert response.provider == "beta"
    assert response.fallback_used is True


def test_auth_failure_does_not_retry_and_does_not_fall_back_silently():
    registry = _registry(("alpha", 401), transport=_ok_transport())
    with pytest.raises(errors.AjError) as excinfo:
        Gateway(registry, max_attempts=3).complete(request())
    assert excinfo.value.code == errors.PROVIDER_AUTH


def test_no_usable_provider_is_an_error_not_an_empty_answer():
    registry = ProviderRegistry([], {})
    with pytest.raises(errors.AjError) as excinfo:
        Gateway(registry).complete(request())
    assert excinfo.value.code == errors.PROVIDER_UNAVAILABLE


def test_quota_exhaustion_cools_the_provider_down():
    registry = _registry(("alpha", 429), ("beta", 200), transport=_ok_transport("ok"))
    registry.adapters["alpha"].complete = lambda *a, **k: (_ for _ in ()).throw(
        errors.ProviderError("quota", code=errors.PROVIDER_QUOTA_EXHAUSTED, retryable=True)
    )
    Gateway(registry, max_attempts=1).complete(request())
    assert any(v["cooling_down"] for v in registry.status().values())


def test_low_level_adapter_refuses_without_a_transport():
    adapter = OpenAICompatibleAdapter(slug="x", base_url="https://x.test", api_key="k")
    assert adapter.usable() is False
    with pytest.raises(errors.AjError):
        adapter.complete(request(), ModelSpec("m", "x"), 5)


def test_model_capability_requirements_filter_candidates():
    strict = ChatRequest(messages=(Message("user", "hi"),), require_vision=True)
    registry = ProviderRegistry(
        [ProviderSpec(slug="alpha", base_url="https://a.test", credential_env="A",
                      enabled=True,
                      models=[ModelSpec("text-only", "alpha", supports_vision=False)])],
        {"alpha": OpenAICompatibleAdapter("alpha", "https://a.test", "k", _ok_transport())},
    )
    assert registry.candidates(strict) == []
