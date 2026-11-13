"""Layered configuration.

Precedence, lowest to highest::

    DEFAULTS (this file)  <  config file  <  environment  <  runtime overrides

Environment variables use the ``AJ_`` prefix and ``__`` for nesting, e.g.
``AJ_PERMISSIONS__UNATTENDED_CEILING=1``.

Design rules
------------
* Secrets are never stored here and never defaulted. A provider key arrives from
  the environment or the owner's own secret store; ``AJ_*_API_KEY`` values are
  read by the provider layer, not written into a config object that gets logged.
* Unknown top-level sections are rejected so a typo cannot silently do nothing.
* Every value has a documented default so the system runs with no config file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import errors

DEFAULTS: Dict[str, Any] = {
    "core": {
        "ecosystem_name": "AJ",
        "audit_dir": str(Path(os.path.expanduser("~")) / ".local" / "share" / "aj" / "audit"),
        "data_dir": str(Path(os.path.expanduser("~")) / ".local" / "share" / "aj"),
        "memory_path": "",
        "require_verification_before_execute": True,
    },
    "permissions": {
        "unattended_ceiling": 1,
        "approval_ttl_seconds": 300,
    },
    "agents": {
        "jarvis": {
            "enabled": True,
            # JARVIS exposes a loopback HTTP/WS bridge; AJ talks to it, it does
            # not import JARVIS internals.
            "transport": "http",
            "endpoint": "http://127.0.0.1:8875",
            "timeout_seconds": 120,
        },
        "helix": {
            "enabled": True,
            "transport": "http",
            "endpoint": "http://127.0.0.1:8765",
            "timeout_seconds": 60,
        },
    },
    "capability": {
        "declarations": "config/capabilities.json",
        "load_jarvis_registry": True,
        "jarvis_root": "",
    },
    "providers": {
        "default_timeout_seconds": 60,
        "max_attempts": 2,
        "fallback_enabled": True,
        "health_ttl_seconds": 60,
        # Adapters are declared, not trusted: an adapter is only usable when its
        # credential is present in the environment.
        "adapters": {
            "openrouter": {"enabled": True, "credential_env": "OPENROUTER_API_KEY",
                           "base_url": "https://openrouter.ai/api/v1"},
            "groq": {"enabled": True, "credential_env": "GROQ_API_KEY",
                     "base_url": "https://api.groq.com/openai/v1"},
            "gemini": {"enabled": True, "credential_env": "GEMINI_API_KEY",
                       "base_url": "https://generativelanguage.googleapis.com/v1beta"},
            "nvidia": {"enabled": False, "credential_env": "NVIDIA_API_KEY",
                       "base_url": ""},
            "cloudflare": {"enabled": False, "credential_env": "CLOUDFLARE_API_TOKEN",
                           "base_url": ""},
            "local": {"enabled": False, "credential_env": "",
                      "base_url": "http://127.0.0.1:11434/v1"},
        },
    },
    "execution": {
        # The Hermes boundary. "none" means no runtime is attached, which is the
        # correct state until the owner gives the HERMES GREEN SIGNAL.
        "runtime": "none",
        "hermes_endpoint": "",
        "max_attempts": 1,
    },
    "integrations": {
        "device_bridge": "gsconnect",
        "device_bridge_enabled": True,
        "voice_separate_from_calls": True,
    },
    "runtime": {
        "persist_tasks": True,
        "persist_memory": True,
        "memory_filename": "memory.sqlite3",
        "log_level": "info",
    },
    "feature_flags": {
        "hermes_skills": False,
        "calling": False,
        "provider_fallback": True,
    },
}

KNOWN_SECTIONS = tuple(DEFAULTS)


def _deep_merge(base: Dict[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _deep_merge(dict(out[key]), value)
        else:
            out[key] = value
    return out


_NULL_TEXT = {"none", "null"}


def _coerce(text: str) -> Any:
    lowered = text.strip().lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in _NULL_TEXT or lowered == "":
        return "" if lowered == "" else None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def invalid_path_reason(value: Any, *, allow_empty: bool = False) -> Optional[str]:
    """Return why *value* is unusable as a filesystem path, else None."""
    if value is None:
        return "must be a path string, not null"
    if isinstance(value, bool):
        return "must be a path string, not a boolean"
    if not isinstance(value, str):
        return f"must be a path string, not {type(value).__name__}"
    stripped = value.strip()
    if not stripped:
        return None if allow_empty else "must be a non-empty path"
    if stripped.lower() in _NULL_TEXT:
        return f"must be a filesystem path, not {stripped!r}"
    return None


def require_path(
    config: "Config",
    key: str,
    *,
    allow_empty: bool = False,
) -> Path:
    """Resolve a path-bearing config value or fail closed.

    Raises :class:`errors.ConfigError` for null-like, blank, or otherwise
    invalid values so callers never coerce them into ``Path("None")`` or write
    before rejection.
    """
    value = config.get(key)
    reason = invalid_path_reason(value, allow_empty=allow_empty)
    if reason is not None:
        raise errors.ConfigError(f"{key} {reason}")
    text = str(value).strip() if isinstance(value, str) else str(value)
    if allow_empty and not text:
        return Path("")
    return Path(text).expanduser()


def _env_overrides(env: Mapping[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, raw in env.items():
        if not key.startswith("AJ_"):
            continue
        # AJ_CONFIG selects the config file; AJ_INBOX_ROOT is an inbox convenience
        # env var consumed directly by inbox resolution (not a config schema section).
        if key in ("AJ_CONFIG", "AJ_INBOX_ROOT"):
            continue
        path = key[len("AJ_"):].lower().split("__")
        cursor = out
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
            if not isinstance(cursor, dict):  # pragma: no cover - defensive
                break
        else:
            cursor[path[-1]] = _coerce(raw)
    return out


class Config:
    """Read-only view over the merged configuration."""

    def __init__(self, data: Dict[str, Any],
                 sources: Optional[Mapping[str, str]] = None):
        self._data = data
        self.sources: Dict[str, str] = dict(sources or {})

    def source(self, section: str) -> str:
        return self.sources.get(section, "default")

    def get(self, path: str, default: Any = None) -> Any:
        """Dotted-path lookup: ``config.get('agents.jarvis.endpoint')``."""
        cursor: Any = self._data
        for part in path.split("."):
            if not isinstance(cursor, Mapping) or part not in cursor:
                return default
            cursor = cursor[part]
        return cursor

    def section(self, name: str) -> Dict[str, Any]:
        value = self._data.get(name, {})
        return dict(value) if isinstance(value, Mapping) else {}

    def as_dict(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._data, default=str))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Config(sections={sorted(self._data)})"


def load(
    path: Optional[str | Path] = None,
    *,
    env: Optional[Mapping[str, str]] = None,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Config:
    """Load configuration from defaults, an optional file, env and overrides."""
    env = os.environ if env is None else env
    data = json.loads(json.dumps(DEFAULTS))
    sources: Dict[str, str] = {section: "default" for section in DEFAULTS}

    resolved = path or env.get("AJ_CONFIG") or ""
    if resolved:
        config_path = Path(resolved).expanduser()
        if not config_path.is_absolute():
            config_path = Path(__file__).resolve().parent.parent / config_path
        if config_path.is_file():
            try:
                file_data = json.loads(config_path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise errors.ConfigError(f"{config_path}: invalid JSON: {exc}") from exc
            if not isinstance(file_data, dict):
                raise errors.ConfigError(f"{config_path}: expected a JSON object")
            # ``$``-prefixed keys are documentation comments, not sections.
            file_data = {k: v for k, v in file_data.items()
                         if not str(k).startswith("$")}
            unknown = [k for k in file_data if k not in KNOWN_SECTIONS]
            if unknown:
                raise errors.ConfigError(
                    f"{config_path}: unknown section(s) {unknown}; "
                    f"known sections are {list(KNOWN_SECTIONS)}"
                )
            data = _deep_merge(data, file_data)
            for section in file_data:
                sources[str(section)] = "file"

    env_data = _env_overrides(env)
    data = _deep_merge(data, env_data)
    for section in env_data:
        sources[str(section)] = "env"
    if overrides:
        data = _deep_merge(data, dict(overrides))
        for section in overrides:
            sources[str(section)] = "override"

    for section in data:
        if section not in KNOWN_SECTIONS:
            raise errors.ConfigError(f"unknown configuration section {section!r}")

    return Config(data, sources)


def memory_path(config: "Config") -> Path:
    """Where canonical raw events live. Explicit path wins over the data dir."""
    explicit_value = config.get("core.memory_path", "")
    reason = invalid_path_reason(explicit_value, allow_empty=True)
    if reason is not None:
        raise errors.ConfigError(f"core.memory_path {reason}")
    explicit = str(explicit_value).strip() if isinstance(explicit_value, str) else ""
    if explicit:
        return Path(explicit).expanduser()
    data_dir = require_path(config, "core.data_dir")
    return data_dir / str(config.get("runtime.memory_filename", "memory.sqlite3"))


def _writable_path(path: Path) -> bool:
    probe = path
    while not probe.exists():
        if probe.parent == probe:
            return False
        probe = probe.parent
    return probe.is_dir() and os.access(probe, os.W_OK)


def validate(config: Config) -> List[str]:
    """Return human-readable configuration problems. Empty means valid."""
    issues: List[str] = []
    ceiling = config.get("permissions.unattended_ceiling")
    if not isinstance(ceiling, int) or isinstance(ceiling, bool) or not 0 <= ceiling <= 2:
        issues.append("permissions.unattended_ceiling must be an integer 0..2")
    ttl = config.get("permissions.approval_ttl_seconds")
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl < 1:
        issues.append("permissions.approval_ttl_seconds must be an integer >= 1")
    for key in ("core.data_dir", "core.audit_dir"):
        value = config.get(key)
        reason = invalid_path_reason(value, allow_empty=False)
        if reason is not None:
            issues.append(f"{key} {reason}")
        elif not _writable_path(Path(str(value)).expanduser()):
            issues.append(f"{key} is not writable: {value}")
    mem_value = config.get("core.memory_path", "")
    mem_reason = invalid_path_reason(mem_value, allow_empty=True)
    if mem_reason is not None:
        issues.append(f"core.memory_path {mem_reason}")
    attempts = config.get("providers.max_attempts")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
        issues.append("providers.max_attempts must be an integer >= 1")
    runtime = config.get("execution.runtime")
    if runtime not in ("none", "hermes"):
        issues.append("execution.runtime must be 'none' or 'hermes'")
    if runtime != "none" and not config.get("feature_flags.hermes_skills", False):
        issues.append("execution.runtime is set but feature_flags.hermes_skills is disabled")
    return issues
