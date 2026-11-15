"""Privileged-operation authorization guardrails.

Phase 3E/3F: separate caller-supplied operator metadata from authenticated
principal identity and enforce a defensible trust boundary for privileged
operations.

Default posture is explicit local-runtime trust authorization for controlled
local/single-process use: it is **not** human authentication and must never be
presented as such. Caller-supplied metadata (e.g. CLI ``--operator``) is
recorded as requested operator metadata only and is never promoted to an
authenticated principal. A principal is marked authenticated only when a
trusted identity provider/verifier supplies verified identity; no built-in
mode fabricates that.
"""

from __future__ import annotations

import getpass
import os
import pwd
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Protocol

from .audit import _redact


def _runtime_provenance() -> Dict[str, Any]:
    """Best-effort OS/process provenance (environment-derived, not authentication).

    This describes the local runtime/process context. It does not prove human
    intent, does not authenticate a remote caller, and must not be treated as a
    verified principal across an untrusted boundary.
    """
    user = ""
    uid = None
    euid = None
    try:
        uid = os.getuid()
        euid = os.geteuid()
        try:
            user = pwd.getpwuid(uid).pw_name
        except Exception:
            user = ""
    except Exception:
        uid = None
        euid = None
    if not user:
        try:
            user = getpass.getuser() or ""
        except Exception:
            user = ""
    prov: Dict[str, Any] = {
        "kind": "os_process",
        "authenticated": False,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "ppid": os.getppid() if hasattr(os, "getppid") else None,
        "uid": uid,
        "euid": euid,
        "os_user": user or None,
        "cwd": None,
    }
    try:
        prov["cwd"] = os.getcwd()
    except Exception:
        prov["cwd"] = None
    return prov


@dataclass(frozen=True)
class AuthorizationContext:
    operation_kind: str
    action: str
    task_id: str
    operation_id: str = ""
    # Caller-supplied metadata only; never treated as verified identity.
    operator_label: str = ""
    requested_operator: str = ""
    # Verified/authenticated principal identity, only when supplied by a trusted
    # identity provider/verifier. Callers must never be able to set this to a
    # trusted value through normal API/CLI metadata.
    authenticated_identity: Optional[str] = None
    principal: Optional[str] = None
    principal_source: str = "none"  # none|trusted_identity_provider|os_process|...
    identity_provider: str = ""
    authenticated: bool = False
    trust_domain: str = "local_runtime"
    source: str = "local"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def bound_scope(self) -> Dict[str, Any]:
        return {
            "operation_kind": self.operation_kind,
            "action": self.action,
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "trust_domain": self.trust_domain,
            "source": self.source,
        }


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    outcome: str  # allow | deny | unavailable | invalid
    reason: str
    authenticated: bool = False
    # Verified principal identity (None unless authenticated by a trusted provider).
    principal: Optional[str] = None
    identity: Optional[str] = None  # compatibility alias for principal
    principal_source: str = "none"
    identity_provider: str = ""
    # Caller-supplied/requested operator metadata (never authenticated identity).
    requested_operator: str = ""
    operator_label: str = ""  # compatibility alias
    trust_assumption: str = ""
    scope: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        principal = self.principal if self.principal is not None else self.identity
        requested = self.requested_operator or self.operator_label
        prov = dict(self.provenance or {})
        prov.setdefault("principal_identity", principal)
        prov.setdefault("principal_source", self.principal_source or "none")
        prov.setdefault("requested_operator", requested)
        prov.setdefault("authenticated", bool(self.authenticated and principal))
        prov.setdefault("identity_provider", self.identity_provider or "")
        prov.setdefault("trust_assumption", self.trust_assumption or "")
        return {
            "allowed": bool(self.allowed),
            "outcome": self.outcome,
            "reason": self.reason,
            "authenticated": bool(self.authenticated and principal),
            "principal": principal,
            "identity": principal,
            "principal_source": self.principal_source or "none",
            "identity_provider": self.identity_provider or "",
            "requested_operator": requested,
            "operator_label": requested,
            "trust_assumption": self.trust_assumption or "",
            "scope": _redact("", dict(self.scope or {})),
            "provenance": _redact("", prov),
            "details": _redact("", dict(self.details or {})),
        }


class PrivilegedOperationAuthorizer(Protocol):
    def authorize(self, context: AuthorizationContext) -> AuthorizationDecision:  # pragma: no cover - protocol
        ...


class LocalTrustPrivilegedAuthorizer:
    """Explicit local-trust authorizer (default for controlled local use).

    Allows privileged operations only under documented local runtime trust
    assumptions (same trusted local process/operator context). Does **not**
    authenticate a human/operator identity. Captures environment-derived runtime
    provenance for auditability, but never marks it authenticated.
    """

    def __init__(self, *, mode: str = "local_trust", allow: bool = True):
        self.mode = (mode or "local_trust").strip().lower()
        self.allow = bool(allow)

    def _provenance(self, context: AuthorizationContext, trust_assumption: str, authenticated: bool = False,
                    principal: Optional[str] = None, principal_source: str = "none",
                    identity_provider: str = "none") -> Dict[str, Any]:
        requested = context.requested_operator or context.operator_label
        runtime = _runtime_provenance()
        return {
            "principal_identity": principal,
            "principal_source": principal_source,
            "requested_operator": requested,
            "authenticated": bool(authenticated and principal),
            "identity_provider": identity_provider,
            "trust_assumption": trust_assumption,
            "runtime": runtime,
        }

    def authorize(self, context: AuthorizationContext) -> AuthorizationDecision:
        requested = context.requested_operator or context.operator_label
        scope = context.bound_scope()
        # Fail closed on invalid/unavailable/denied configuration.
        if self.mode in ("deny", "disabled", "forbidden"):
            prov = self._provenance(context, "explicit_deny")
            return AuthorizationDecision(
                allowed=False, outcome="deny",
                reason="privileged operation authorization denied by policy",
                authenticated=False, principal=None, identity=None,
                principal_source="none", identity_provider="none",
                requested_operator=requested, operator_label=requested,
                trust_assumption="explicit_deny", scope=scope, provenance=prov,
                details={"source": context.source, "trust_domain": context.trust_domain},
            )
        # Modes requiring verified identity cannot be satisfied by this authorizer.
        if self.mode in ("require_verified_identity", "verified_identity_required", "verified_only", "authenticated_only"):
            prov = self._provenance(context, "verified_identity_required_unavailable")
            return AuthorizationDecision(
                allowed=False, outcome="unavailable",
                reason="verified/authenticated operator identity required but no trusted identity provider is configured",
                authenticated=False, principal=None, identity=None,
                principal_source="none", identity_provider="none",
                requested_operator=requested, operator_label=requested,
                trust_assumption="verified_identity_required_unavailable", scope=scope, provenance=prov,
                details={"source": context.source, "trust_domain": context.trust_domain},
            )
        if self.mode not in ("local_trust", "allow_local", "trusted_local"):
            prov = self._provenance(context, "invalid_configuration")
            return AuthorizationDecision(
                allowed=False, outcome="invalid",
                reason=f"unknown privileged authorization mode: {self.mode!r}",
                authenticated=False, principal=None, identity=None,
                principal_source="none", identity_provider="none",
                requested_operator=requested, operator_label=requested,
                trust_assumption="invalid_configuration", scope=scope, provenance=prov,
            )
        if not self.allow:
            prov = self._provenance(context, "authorization_unavailable")
            return AuthorizationDecision(
                allowed=False, outcome="unavailable",
                reason="privileged operation authorization unavailable",
                authenticated=False, principal=None, identity=None,
                principal_source="none", identity_provider="none",
                requested_operator=requested, operator_label=requested,
                trust_assumption="authorization_unavailable", scope=scope, provenance=prov,
                details={"source": context.source, "trust_domain": context.trust_domain},
            )
        # Local trusted runtime caller: explicit assumption, not authentication.
        # Never promote requested/caller metadata or OS environment to authenticated principal.
        trust = "local_runtime_trusted_caller"
        prov = self._provenance(context, trust, authenticated=False, principal=None, principal_source="none")
        return AuthorizationDecision(
            allowed=True, outcome="allow",
            reason="allowed under explicit local-runtime trust assumption (no authenticated identity)",
            authenticated=False,
            principal=None,
            identity=None,
            principal_source="none",
            identity_provider="none",
            requested_operator=requested,
            operator_label=requested,
            trust_assumption=trust,
            scope=scope,
            provenance=prov,
            details={
                "source": context.source,
                "trust_domain": context.trust_domain,
                "note": "caller-supplied operator metadata is not authenticated identity",
            },
        )


class UnavailablePrivilegedAuthorizer:
    def __init__(self, *, reason: str = "privileged operation authorizer unavailable"):
        self.reason = reason

    def authorize(self, context: AuthorizationContext) -> AuthorizationDecision:
        requested = context.requested_operator or context.operator_label
        return AuthorizationDecision(
            allowed=False, outcome="unavailable",
            reason=self.reason,
            authenticated=False, principal=None, identity=None,
            principal_source="none", identity_provider="none",
            requested_operator=requested, operator_label=requested,
            trust_assumption="authorization_unavailable",
            scope=context.bound_scope(),
            provenance={
                "principal_identity": None,
                "principal_source": "none",
                "requested_operator": requested,
                "authenticated": False,
                "identity_provider": "none",
                "trust_assumption": "authorization_unavailable",
            },
        )


class _CallableIdentityAuthorizerAdapter:
    """Adapter for a future trusted identity provider/authorizer callable.

    The callable must return a mapping/decision-like object. Any exception fails
    closed. Authentication is trusted only when the provider explicitly marks it.
    """

    def __init__(self, provider: Callable[[AuthorizationContext], Any]):
        self.provider = provider

    def authorize(self, context: AuthorizationContext) -> AuthorizationDecision:
        requested = context.requested_operator or context.operator_label
        scope = context.bound_scope()
        try:
            raw = self.provider(context)
        except Exception as exc:
            return AuthorizationDecision(
                allowed=False, outcome="unavailable",
                reason=f"identity/authorization provider error: {exc}",
                authenticated=False, principal=None, identity=None,
                principal_source="none", identity_provider="trusted_identity_provider",
                requested_operator=requested, operator_label=requested,
                trust_assumption="provider_error", scope=scope,
                provenance={"principal_identity": None, "principal_source": "none", "requested_operator": requested, "authenticated": False},
            )
        if raw is None:
            return AuthorizationDecision(
                allowed=False, outcome="unavailable",
                reason="identity/authorization provider returned no decision",
                authenticated=False, principal=None, identity=None,
                principal_source="none", identity_provider="trusted_identity_provider",
                requested_operator=requested, operator_label=requested,
                trust_assumption="provider_unavailable", scope=scope,
                provenance={"principal_identity": None, "principal_source": "none", "requested_operator": requested, "authenticated": False},
            )
        if isinstance(raw, AuthorizationDecision):
            # enforce scope/provenance consistency; never trust caller-supplied auth flags without principal
            principal = raw.principal or raw.identity
            authenticated = bool(raw.authenticated and principal)
            return AuthorizationDecision(
                allowed=bool(raw.allowed and (not raw.authenticated or authenticated)),
                outcome=raw.outcome, reason=raw.reason,
                authenticated=authenticated, principal=principal if authenticated or raw.principal_source != "none" else principal,
                identity=principal,
                principal_source=raw.principal_source or ("trusted_identity_provider" if authenticated else "none"),
                identity_provider=raw.identity_provider or "trusted_identity_provider",
                requested_operator=requested, operator_label=requested,
                trust_assumption=raw.trust_assumption,
                scope=scope, provenance=dict(raw.provenance or {}),
                details=dict(raw.details or {}),
            )
        if isinstance(raw, Mapping):
            allowed = bool(raw.get("allowed", False))
            outcome = str(raw.get("outcome") or ("allow" if allowed else "deny"))
            principal = raw.get("principal") or raw.get("identity")
            principal = str(principal) if principal not in (None, "") else None
            principal_source = str(raw.get("principal_source") or ("trusted_identity_provider" if principal else "none"))
            authenticated = bool(raw.get("authenticated", False) and principal)
            # fail closed: cannot claim allowed+authenticated without a principal
            if bool(raw.get("authenticated", False)) and not principal:
                allowed = False
                outcome = "invalid"
            prov = dict(raw.get("provenance") or {})
            prov.setdefault("principal_identity", principal)
            prov.setdefault("principal_source", principal_source)
            prov.setdefault("requested_operator", requested)
            prov.setdefault("authenticated", authenticated)
            prov.setdefault("identity_provider", str(raw.get("identity_provider") or "trusted_identity_provider"))
            return AuthorizationDecision(
                allowed=allowed, outcome=outcome,
                reason=str(raw.get("reason") or ""),
                authenticated=authenticated, principal=principal, identity=principal,
                principal_source=principal_source,
                identity_provider=str(raw.get("identity_provider") or "trusted_identity_provider"),
                requested_operator=requested, operator_label=requested,
                trust_assumption=str(raw.get("trust_assumption") or ""),
                scope=scope, provenance=prov,
                details=dict(raw.get("details") or {}),
            )
        return AuthorizationDecision(
            allowed=False, outcome="invalid",
            reason="identity/authorization provider returned invalid decision type",
            authenticated=False, principal=None, identity=None,
            principal_source="none", identity_provider="trusted_identity_provider",
            requested_operator=requested, operator_label=requested,
            trust_assumption="provider_invalid", scope=scope,
            provenance={"principal_identity": None, "principal_source": "none", "requested_operator": requested, "authenticated": False},
        )


def build_privileged_authorizer(config: Optional[Mapping[str, Any]] = None,
                                *, provider: Optional[Callable[[AuthorizationContext], Any]] = None) -> PrivilegedOperationAuthorizer:
    """Build from config mapping; fail closed on invalid config.

    Config (under permissions.privileged_reconciliation/privileged_operations):
      - mode: local_trust (default) | deny | unavailable | require_verified_identity
      - enabled/allow: bool
      - identity_provider / provider: optional callable (programmatic) or "none"
    """
    cfg = dict(config or {})
    mode = "local_trust"
    enabled = True
    if isinstance(cfg.get("mode"), str):
        mode = str(cfg.get("mode"))
    if "enabled" in cfg:
        enabled = bool(cfg.get("enabled"))
    if isinstance(cfg.get("allow"), bool):
        enabled = bool(cfg.get("allow"))

    # Programmatic trusted provider (e.g. future verified identity adapter)
    prov = provider or cfg.get("identity_provider") or cfg.get("provider")
    if callable(prov):
        # Optional hard gate: still honor explicit deny/disable
        if mode.strip().lower() in ("deny", "disabled", "forbidden") or not enabled:
            return LocalTrustPrivilegedAuthorizer(mode="deny", allow=False)
        return _CallableIdentityAuthorizerAdapter(prov)

    if mode.strip().lower() in ("unavailable", "none", "null", "error"):
        return UnavailablePrivilegedAuthorizer()
    try:
        return LocalTrustPrivilegedAuthorizer(mode=mode, allow=enabled)
    except Exception:
        return UnavailablePrivilegedAuthorizer()