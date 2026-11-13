"""Provider gateway.

Core code must never name a provider. It asks this gateway for a completion with
a set of requirements; the gateway chooses an adapter, handles timeouts, records
health, and falls back only to adapters that are actually usable.

Honesty rules
-------------
* An adapter is usable only when its credential is present. Nothing here assumes
  a free tier, a quota, or that a listed model accepts the request format.
* No network call happens unless a transport is supplied. The default transport
  raises :class:`ProviderError`, so constructing this module cannot phone home.
* Failures are normalized; an unknown failure is ``provider_unavailable``, never
  a silent empty answer.
* Quota exhaustion is remembered for a cooldown window rather than retried in a
  tight loop.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, runtime_checkable

from . import errors

Transport = Callable[[str, str, Dict[str, str], Optional[bytes], int], tuple]
"""``(method, url, headers, body, timeout) -> (status, bytes)``"""


@dataclass(frozen=True)
class Message:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class ChatRequest:
    messages: tuple
    model_hint: str = ""
    max_tokens: int = 1024
    temperature: float = 0.4
    require_tools: bool = False
    require_vision: bool = False
    min_context: int = 0

    def payload(self, model: str) -> Dict[str, Any]:
        return {
            "model": model,
            "messages": [m.to_dict() if isinstance(m, Message) else dict(m)
                         for m in self.messages],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


@dataclass
class ChatResponse:
    text: str
    provider: str
    model: str
    usage: Dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""
    attempts: int = 1
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    provider: str
    context_window: int = 8192
    supports_tools: bool = False
    supports_vision: bool = False
    notes: str = ""

    def fits(self, request: ChatRequest) -> bool:
        if request.require_tools and not self.supports_tools:
            return False
        if request.require_vision and not self.supports_vision:
            return False
        return self.context_window >= max(0, int(request.min_context))


@dataclass
class ProviderSpec:
    slug: str
    base_url: str = ""
    credential_env: str = ""
    enabled: bool = True
    models: List[ModelSpec] = field(default_factory=list)


@runtime_checkable
class ProviderAdapter(Protocol):
    slug: str

    def usable(self) -> bool:  # pragma: no cover - protocol
        ...

    def complete(self, request: ChatRequest, model: ModelSpec,
                 timeout: int) -> ChatResponse:  # pragma: no cover - protocol
        ...


@dataclass
class OpenAICompatibleAdapter:
    """One adapter shape for OpenRouter / Groq / NVIDIA / local OpenAI-compatible.

    The request/response shape is the chat-completions API these providers share;
    provider-specific headers are the only difference and are supplied by config.
    """

    slug: str
    base_url: str
    api_key: str = ""
    transport: Optional[Transport] = None
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def usable(self) -> bool:
        return bool(self.base_url) and bool(self.api_key) and self.transport is not None

    def complete(self, request: ChatRequest, model: ModelSpec, timeout: int) -> ChatResponse:
        if not self.usable():
            raise errors.ProviderError(
                f"{self.slug}: adapter is not usable (missing credential, base URL or transport)"
            )
        if self.transport is None:  # pragma: no cover - guarded by usable()
            raise errors.ProviderError(f"{self.slug}: no transport")
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.api_key}"}
        headers.update(self.extra_headers)
        body = json.dumps(request.payload(model.model_id)).encode("utf-8")
        try:
            status, raw = self.transport("POST", url, headers, body, timeout)
        except TimeoutError as exc:
            raise errors.ProviderError(f"{self.slug}: timeout", code=errors.PROVIDER_UNAVAILABLE,
                                       retryable=True) from exc
        except Exception as exc:
            raise errors.ProviderError(f"{self.slug}: transport failure: {exc}",
                                       retryable=True) from exc

        if status in (401, 403):
            raise errors.ProviderError(f"{self.slug}: authentication rejected",
                                       code=errors.PROVIDER_AUTH, retryable=False)
        if status == 429:
            raise errors.ProviderError(f"{self.slug}: rate limited",
                                       code=errors.PROVIDER_RATE_LIMITED, retryable=True)
        if 400 <= status < 500:
            snippet = (raw or b"")[:200].decode("utf-8", "replace")
            raise errors.ProviderError(
                f"{self.slug}: request rejected ({status}): {snippet}",
                code=errors.PROVIDER_BAD_REQUEST, retryable=False,
            )
        if status >= 500:
            raise errors.ProviderError(f"{self.slug}: upstream error {status}",
                                       retryable=True)
        try:
            data = json.loads((raw or b"{}").decode("utf-8"))
        except ValueError as exc:
            raise errors.ProviderError(f"{self.slug}: unparseable response") from exc
        choices = data.get("choices") or []
        if not choices:
            raise errors.ProviderError(f"{self.slug}: response contained no choices")
        message = choices[0].get("message") or {}
        return ChatResponse(
            text=str(message.get("content", "")),
            provider=self.slug,
            model=str(data.get("model", model.model_id)),
            usage=dict(data.get("usage", {}) or {}),
            finish_reason=str(choices[0].get("finish_reason", "")),
        )


@dataclass
class MockProvider:
    """A deterministic in-process provider for tests and offline demos.

    It implements the same :class:`ProviderAdapter` surface as a real adapter and
    never performs I/O, so foundation tests need no credential, no network and no
    paid call. ``error`` lets a test inject a normalized failure.
    """

    slug: str = "mock"
    text: str = "mock response"
    error: Optional[errors.AjError] = None
    requests: List[ChatRequest] = field(default_factory=list)
    models: List[str] = field(default_factory=list)

    def usable(self) -> bool:
        return True

    def complete(self, request: ChatRequest, model: ModelSpec,
                 timeout: int) -> ChatResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ChatResponse(text=self.text, provider=self.slug,
                            model=model.model_id or "mock-model")


@dataclass
class Health:
    failures: int = 0
    last_failure: float = 0.0
    quota_until: float = 0.0
    last_success: float = 0.0

    def usable(self, now: float, ttl: int) -> bool:
        if self.quota_until > now:
            return False
        if self.failures == 0:
            return True
        return (now - self.last_failure) > ttl


class ProviderRegistry:
    """Providers, models and their observed health."""

    def __init__(self, providers: Optional[List[ProviderSpec]] = None,
                 adapters: Optional[Dict[str, ProviderAdapter]] = None,
                 health_ttl: int = 60, clock=time.time):
        self.providers: Dict[str, ProviderSpec] = {p.slug: p for p in providers or []}
        self.adapters: Dict[str, ProviderAdapter] = dict(adapters or {})
        self.health: Dict[str, Health] = {s: Health() for s in self.providers}
        self.health_ttl = int(health_ttl)
        self._clock = clock

    def models(self) -> List[ModelSpec]:
        out: List[ModelSpec] = []
        for spec in self.providers.values():
            if spec.enabled:
                out.extend(spec.models)
        return out

    def candidates(self, request: ChatRequest) -> List[tuple]:
        """Usable ``(adapter, model)`` pairs that satisfy the request."""
        now = self._clock()
        pairs: List[tuple] = []
        for spec in self.providers.values():
            if not spec.enabled:
                continue
            adapter = self.adapters.get(spec.slug)
            health = self.health.setdefault(spec.slug, Health())
            if adapter is None or not adapter.usable():
                continue
            if not health.usable(now, self.health_ttl):
                continue
            for model in spec.models:
                if model.fits(request):
                    pairs.append((adapter, model))
        if request.model_hint:
            pairs.sort(key=lambda p: 0 if request.model_hint in p[1].model_id else 1)
        return pairs

    def note_success(self, slug: str) -> None:
        health = self.health.setdefault(slug, Health())
        health.failures = 0
        health.last_success = self._clock()

    def note_failure(self, slug: str, error: errors.AjError) -> None:
        health = self.health.setdefault(slug, Health())
        health.failures += 1
        health.last_failure = self._clock()
        if error.code == errors.PROVIDER_QUOTA_EXHAUSTED:
            health.quota_until = self._clock() + 3600

    def status(self) -> Dict[str, Any]:
        now = self._clock()
        return {
            slug: {
                "enabled": spec.enabled,
                "usable": bool(self.adapters.get(slug) and self.adapters[slug].usable()),
                "models": [m.model_id for m in spec.models],
                "cooling_down": not self.health.setdefault(slug, Health()).usable(
                    now, self.health_ttl),
            }
            for slug, spec in self.providers.items()
        }

    @classmethod
    def from_config(cls, config, transport: Optional[Transport] = None) -> "ProviderRegistry":
        import os

        providers: List[ProviderSpec] = []
        adapters: Dict[str, ProviderAdapter] = {}
        for slug, section in (config.get("providers.adapters", {}) or {}).items():
            if not isinstance(section, dict):
                continue
            credential_env = str(section.get("credential_env", ""))
            api_key = os.environ.get(credential_env, "") if credential_env else ""
            spec = ProviderSpec(
                slug=slug,
                base_url=str(section.get("base_url", "")),
                credential_env=credential_env,
                enabled=bool(section.get("enabled", False)),
                models=[
                    ModelSpec(model_id=f"{slug}:default", provider=slug)
                ],
            )
            providers.append(spec)
            if spec.enabled:
                adapters[slug] = OpenAICompatibleAdapter(
                    slug=slug, base_url=spec.base_url, api_key=api_key,
                    transport=transport,
                )
        return cls(providers, adapters,
                   health_ttl=int(config.get("providers.health_ttl_seconds", 60)))


class Gateway:
    """Bounded retries with fallback across usable providers."""

    def __init__(self, registry: ProviderRegistry, *,
                 max_attempts: int = 2, fallback_enabled: bool = True,
                 default_timeout: int = 60):
        self.registry = registry
        self.max_attempts = max(1, int(max_attempts))
        self.fallback_enabled = bool(fallback_enabled)
        self.default_timeout = int(default_timeout)

    def complete(self, request: ChatRequest, *, timeout: Optional[int] = None) -> ChatResponse:
        candidates = self.registry.candidates(request)
        if not candidates:
            raise errors.ProviderError(
                "no usable provider satisfies this request",
                code=errors.PROVIDER_UNAVAILABLE, retryable=False,
            )
        if not self.fallback_enabled:
            candidates = candidates[:1]
        timeout = int(timeout or self.default_timeout)
        last_error: Optional[errors.AjError] = None
        attempts = 0
        for index, (adapter, model) in enumerate(candidates):
            for _ in range(self.max_attempts):
                attempts += 1
                try:
                    response = adapter.complete(request, model, timeout)
                except errors.AjError as exc:
                    last_error = exc
                    self.registry.note_failure(adapter.slug, exc)
                    if not exc.retryable:
                        break
                    continue
                except Exception as exc:  # defensive normalisation
                    last_error = errors.ProviderError(str(exc))
                    self.registry.note_failure(adapter.slug, last_error)
                    break
                self.registry.note_success(adapter.slug)
                response.attempts = attempts
                response.fallback_used = index > 0
                return response
        raise last_error or errors.ProviderError("all providers failed")
