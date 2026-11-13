"""Error taxonomy and normalisation.

Every failure that crosses a boundary (agent, provider, execution adapter,
calling bridge) is converted into :class:`AjError` with a stable ``code`` so that
callers can branch on the cause without string matching. Unknown exceptions are
preserved but reported as ``unknown`` — they are never upgraded to success.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# --- codes ---------------------------------------------------------------
CAPABILITY_NOT_FOUND = "capability_not_found"
CAPABILITY_UNAVAILABLE = "capability_unavailable"
POLICY_DENIED = "policy_denied"
APPROVAL_REQUIRED = "approval_required"
APPROVAL_INVALID = "approval_invalid"
AGENT_UNAVAILABLE = "agent_unavailable"
AGENT_TIMEOUT = "agent_timeout"
AGENT_REJECTED = "agent_rejected"
EXECUTION_UNAVAILABLE = "execution_unavailable"
EXECUTION_FAILED = "execution_failed"
EXECUTION_TIMEOUT = "execution_timeout"
PROVIDER_UNAVAILABLE = "provider_unavailable"
PROVIDER_RATE_LIMITED = "provider_rate_limited"
PROVIDER_QUOTA_EXHAUSTED = "provider_quota_exhausted"
PROVIDER_AUTH = "provider_auth"
PROVIDER_BAD_REQUEST = "provider_bad_request"
CALLING_AMBIGUOUS_CONTACT = "calling_ambiguous_contact"
CALLING_INVALID_STATE = "calling_invalid_state"
CALLING_UNAVAILABLE = "calling_unavailable"
CONFIG_INVALID = "config_invalid"
STORAGE_BUSY = "storage_busy"
STORAGE_ERROR = "storage_error"
CONFLICT = "conflict"
RETRY_UNSAFE = "retry_unsafe"
RECOVERY_REQUIRED = "recovery_required"
LEASE_HELD = "lease_held"
LEASE_EXPIRED = "lease_expired"
LEASE_OWNERSHIP = "lease_ownership"
UNKNOWN = "unknown"


class AjError(Exception):
    """Base class for every error AJ raises deliberately."""

    code = UNKNOWN
    retryable = False

    def __init__(self, message: str, *, code: Optional[str] = None,
                 retryable: Optional[bool] = None, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if retryable is not None:
            self.retryable = retryable
        self.detail = dict(detail or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "detail": self.detail,
        }


class ConfigError(AjError):
    code = CONFIG_INVALID


class CapabilityNotFound(AjError):
    code = CAPABILITY_NOT_FOUND


class CapabilityUnavailable(AjError):
    code = CAPABILITY_UNAVAILABLE


class PolicyDenied(AjError):
    code = POLICY_DENIED


class ApprovalRequired(AjError):
    code = APPROVAL_REQUIRED


class ApprovalInvalid(AjError):
    code = APPROVAL_INVALID


class AgentUnavailable(AjError):
    code = AGENT_UNAVAILABLE
    retryable = True


class AgentTimeout(AjError):
    code = AGENT_TIMEOUT
    retryable = True


class ExecutionUnavailable(AjError):
    """Raised when no execution runtime is attached (the Hermes boundary)."""

    code = EXECUTION_UNAVAILABLE


class ExecutionFailed(AjError):
    code = EXECUTION_FAILED


class ProviderError(AjError):
    code = PROVIDER_UNAVAILABLE
    retryable = True


class CallingError(AjError):
    code = CALLING_UNAVAILABLE


class StorageError(AjError):
    code = STORAGE_ERROR


class StorageBusy(StorageError):
    code = STORAGE_BUSY


class Conflict(StorageError):
    code = CONFLICT


class RetryUnsafe(AjError):
    code = RETRY_UNSAFE


class RecoveryRequired(AjError):
    code = RECOVERY_REQUIRED


class LeaseHeld(AjError):
    code = LEASE_HELD


class LeaseExpired(AjError):
    code = LEASE_EXPIRED


class LeaseOwnership(AjError):
    code = LEASE_OWNERSHIP


def normalize(exc: BaseException) -> AjError:
    """Convert any exception into an :class:`AjError` without losing the type."""
    if isinstance(exc, AjError):
        return exc
    err = AjError(f"{type(exc).__name__}: {exc}")
    err.code = UNKNOWN
    err.detail = {"exception": type(exc).__name__}
    return err
