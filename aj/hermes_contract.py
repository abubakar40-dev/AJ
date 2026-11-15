"""AJ↔Hermes v0 contract helpers (read-only spike).

Pure validation/mapping utilities for `aj.hermes.execution.v0`.
No subprocess execution, no side effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

CONTRACT_VERSION = "aj.hermes.execution.v0"
CAPABILITY_STATUS_READ = "hermes.status.read"
TRUST_MODE_LOCAL = "local_trust"

# Honest adapter status vocabulary (v0 mapping surface).
STATUSES = {
    "submitted",
    "accepted",
    "running",
    "completed",
    "failed",
    "rejected",
    "cancel_requested",
    "cancelled",
    "timeout",
    "unknown",
    "requires_manual_review",
}

_SENSITIVE_PATTERNS = [
    # Authorization header with scheme + token (redact full token)
    re.compile(r'(?i)\b(authorization)\b\s*[:=]\s*(bearer|basic)\s+([^\s,;\"\']+)'),
    # Bearer / basic auth tokens in headers or text
    re.compile(r'(?i)\b(bearer)\s+([A-Za-z0-9\-._~+/=]{4,})'),
    re.compile(r'(?i)\b(basic)\s+([A-Za-z0-9+/=]{8,})'),
    # credential-bearing URLs (best-effort)
    re.compile(r'(?i)\b([a-z][a-z0-9+.-]*://[^/\s:@]+):([^@\s/]+)@'),
    # quoted JSON-like key/value secrets: "token": "value" or 'token':'value'
    re.compile(r'(?i)([\"\'])(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|token|secret|password|passwd|pwd|session[_-]?id|session|cookie|authorization)\1\s*:\s*([\"\'])([^\"\']+)\3'),
    # key/value or header-like assignments (unquoted/simple quoted handled loosely)
    re.compile(r'(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|token|secret|password|passwd|pwd|session[_-]?id|session|cookie|authorization)\b\s*[:=]\s*([\"\']?)([^\s,;\"\']+)\2'),
    # common env-style secrets
    re.compile(r'(?i)\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|SESSION|COOKIE|AUTH)[A-Z0-9_]*)\s*=\s*([\"\']?)([^\s\"\']+)\2'),
]


def redact_text(text: Any, *, limit: int = 4000) -> str:
    """Best-effort redaction + bound for untrusted output/text.

    Not a guarantee that every possible secret format is removed.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            text = "<unprintable>"
    # Normalize NULs/control-ish chars but keep newlines/tabs for diagnostics.
    text = text.replace("\x00", "\ufffd")
    for pat in _SENSITIVE_PATTERNS:
        def repl(m):
            g = m.groups()
            # credential URL: scheme://user:PASS@
            if len(g) >= 2 and "://" in m.group(0):
                return f"{g[0]}:[REDACTED]@"
            # Authorization: Bearer/Basic TOKEN
            if len(g) == 3 and str(g[0]).lower() == "authorization":
                return f"{g[0]}: {g[1]} [REDACTED]"
            # Bearer/Basic TOKEN
            if len(g) == 2 and str(g[0]).lower() in ("bearer", "basic"):
                return f"{g[0]} [REDACTED]"
            # quoted JSON-like "key": "value" -> groups (q1, key, q2, value)
            if len(g) == 4 and g[0] in ('"', "'") and g[2] in ('"', "'"):
                return f"{g[0]}{g[1]}{g[0]}: {g[2]}[REDACTED]{g[2]}"
            # key/value or env with optional quote groups (key, q, value)
            if len(g) == 3:
                return f"{g[0]}=[REDACTED]"
            if len(g) >= 2:
                return f"{g[0]}=[REDACTED]"
            return "[REDACTED]"
        text = pat.sub(repl, text)
    if len(text) > limit:
        return text[: max(0, limit - 20)] + "\n...[truncated]"
    return text


@dataclass(frozen=True)
class V0Request:
    contract_version: str
    aj_task_id: str
    operation_id: str
    attempt_id: str
    correlation_id: str
    capability_id: str
    input: Dict[str, Any]
    timeout_ms: int
    permission_context: Dict[str, Any]
    idempotency_key: str = ""


def _nonempty_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def validate_request(data: Mapping[str, Any], *, max_timeout_ms: int) -> Tuple[Optional[V0Request], Optional[str]]:
    """Validate a v0 request envelope. Returns (request, error_code_or_none)."""
    if not isinstance(data, Mapping):
        return None, "request_invalid"
    cv = _nonempty_str(data.get("contract_version"))
    if cv != CONTRACT_VERSION:
        return None, "contract_version_unsupported"
    aj_task_id = _nonempty_str(data.get("aj_task_id"))
    operation_id = _nonempty_str(data.get("operation_id"))
    attempt_id = _nonempty_str(data.get("attempt_id"))
    correlation_id = _nonempty_str(data.get("correlation_id"))
    capability_id = _nonempty_str(data.get("capability_id"))
    if not all([aj_task_id, operation_id, attempt_id, correlation_id, capability_id]):
        return None, "request_invalid"
    if capability_id != CAPABILITY_STATUS_READ:
        return None, "capability_not_allowed"
    input_val = data.get("input", {})
    if input_val is None:
        input_val = {}
    if not isinstance(input_val, Mapping):
        return None, "request_invalid"
    # v0 hermes.status.read: fixed/empty input only (no arbitrary args)
    if dict(input_val):
        return None, "request_invalid"
    try:
        timeout_ms = int(data.get("timeout_ms", 0))
    except Exception:
        return None, "request_invalid"
    if timeout_ms <= 0 or timeout_ms > max_timeout_ms:
        return None, "request_invalid"
    pctx = data.get("permission_context")
    if not isinstance(pctx, Mapping):
        return None, "request_invalid"
    # Fail closed: AJ must assert allow and local_trust scope for this spike.
    if str(pctx.get("authorizer", "")) != "AJ":
        return None, "permission_denied"
    if str(pctx.get("authorization_decision", "")) != "allow":
        return None, "permission_denied"
    if str(pctx.get("trust_mode", "")) != TRUST_MODE_LOCAL:
        return None, "permission_denied"
    idem = data.get("idempotency_key", "")
    if idem is None:
        idem = ""
    if not isinstance(idem, str):
        return None, "request_invalid"
    return (
        V0Request(
            contract_version=cv,
            aj_task_id=aj_task_id,
            operation_id=operation_id,
            attempt_id=attempt_id,
            correlation_id=correlation_id,
            capability_id=capability_id,
            input={},
            timeout_ms=timeout_ms,
            permission_context=dict(pctx),
            idempotency_key=idem.strip(),
        ),
        None,
    )


def normalize_status(raw: str) -> str:
    return raw if raw in STATUSES else "unknown"


def response_envelope(
    req: V0Request,
    *,
    accepted: bool,
    status: str,
    hermes_execution_id: Optional[str] = None,
    result_payload: Any = None,
    result_ref: Any = None,
    error: Optional[Dict[str, Any]] = None,
    timestamps: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    status = normalize_status(status)
    return {
        "contract_version": CONTRACT_VERSION,
        "aj_task_id": req.aj_task_id,
        "operation_id": req.operation_id,
        "attempt_id": req.attempt_id,
        "correlation_id": req.correlation_id,
        "capability_id": req.capability_id,
        "hermes_execution_id": hermes_execution_id,  # nullable, never invented
        "accepted": bool(accepted),
        "status": status,
        "result_ref": result_ref,
        "result_payload": result_payload,
        "error": error,
        "timestamps": dict(timestamps or {}),
        "evidence": dict(evidence or {}),
        "provenance": dict(provenance or {}),
    }
