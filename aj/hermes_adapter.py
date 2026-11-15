"""Hermes CLI execution adapter (minimal, read-only spike).

Implements AJ ExecutionPort for `hermes.status.read` via a bounded CLI
subprocess (`hermes gateway status`). Default-disabled and fail-closed by
construction at runtime assembly/config; this module enforces request/command
safety regardless of caller.
"""

from __future__ import annotations

import os
import selectors
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from . import errors
from .contracts import ExecutionRequest, ExecutionResult
from .hermes_contract import (
    CAPABILITY_STATUS_READ,
    CONTRACT_VERSION,
    TRUST_MODE_LOCAL,
    redact_text,
    response_envelope,
    validate_request,
)

# Conservative bounds.
DEFAULT_TIMEOUT_MS = 10_000
MAX_TIMEOUT_MS = 30_000
DEFAULT_STDOUT_MAX = 8_000
DEFAULT_STDERR_MAX = 4_000
MIN_OUTPUT_MAX = 256
MAX_OUTPUT_MAX = 64_000
MIN_TIMEOUT_MS = 100


def _checked_int(name: str, value: Any, *, lo: int, hi: int) -> int:
    if isinstance(value, bool):
        raise errors.ConfigError(f"execution.hermes.{name} must be an integer, not boolean")
    try:
        if isinstance(value, str) and not value.strip():
            raise ValueError("empty")
        v = int(value)
    except Exception as exc:
        raise errors.ConfigError(f"execution.hermes.{name} must be an integer") from exc
    if v < lo or v > hi:
        raise errors.ConfigError(f"execution.hermes.{name} must be between {lo} and {hi}")
    return v


@dataclass
class RunnerResult:
    started: bool
    exit_code: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool
    error: Optional[str] = None
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    terminated: bool = False
    signal: Optional[int] = None


Runner = Callable[[Sequence[str], float, int, int, Optional[Mapping[str, str]]], RunnerResult]


def _drain_limited(stream, limit: int):
    """Return (text, truncated) from a binary stream with incremental cap."""
    chunks = bytearray()
    truncated = False
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            remaining = limit - len(chunks)
            if remaining > 0:
                chunks.extend(chunk[:remaining])
            if len(chunk) > max(0, remaining):
                truncated = True
                # keep draining to avoid blocking the child, but do not store
                while True:
                    more = stream.read(4096)
                    if not more:
                        break
                break
    except Exception:
        pass
    text = chunks.decode("utf-8", "replace")
    return text, truncated


def default_runner(
    argv: Sequence[str],
    timeout_s: float,
    stdout_max: int,
    stderr_max: int,
    env: Optional[Mapping[str, str]] = None,
) -> RunnerResult:
    """Run fixed argv with bounded timeout/output collection. No shell.

    Output is collected incrementally and capped during collection. On timeout,
    the process (and its process group where possible) is terminated/killed and
    reaped best-effort.
    """
    import threading

    timeout_s = max(0.1, float(timeout_s))
    stdout_max = max(MIN_OUTPUT_MAX, int(stdout_max))
    stderr_max = max(MIN_OUTPUT_MAX, int(stderr_max))
    try:
        popen_kwargs = {
            "shell": False,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": dict(env) if env is not None else None,
            "cwd": os.getcwd(),
        }
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(list(argv), **popen_kwargs)
    except FileNotFoundError:
        return RunnerResult(False, None, "", "", False, "cli_not_found", False, False, False, None)
    except Exception as exc:
        return RunnerResult(False, None, "", "", False, f"spawn_failed:{type(exc).__name__}", False, False, False, None)

    out_buf = bytearray()
    err_buf = bytearray()
    flags = {"out_trunc": False, "err_trunc": False}

    def _reader(stream, buf: bytearray, limit: int, key: str):
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                rem = limit - len(buf)
                if rem > 0:
                    buf.extend(chunk[:rem])
                if len(chunk) > max(0, rem):
                    flags[key] = True
                    # keep draining to EOF to avoid blocking writer, but do not store
                    while True:
                        more = stream.read(4096)
                        if not more:
                            break
                    break
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    threads = []
    if proc.stdout is not None:
        t = threading.Thread(target=_reader, args=(proc.stdout, out_buf, stdout_max, "out_trunc"), daemon=True)
        threads.append(t); t.start()
    if proc.stderr is not None:
        t = threading.Thread(target=_reader, args=(proc.stderr, err_buf, stderr_max, "err_trunc"), daemon=True)
        threads.append(t); t.start()

    timed_out = False
    terminated = False
    try:
        try:
            rc = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminated = True
            def _kill(sig: int) -> None:
                try:
                    if os.name != "nt":
                        os.killpg(proc.pid, sig)
                except Exception:
                    pass
                try:
                    if os.name != "nt":
                        os.kill(proc.pid, sig)
                    elif sig == signal.SIGKILL:
                        proc.kill()
                    else:
                        proc.terminate()
                except Exception:
                    pass
            _kill(signal.SIGTERM)
            try:
                rc = proc.wait(timeout=0.8)
            except Exception:
                _kill(signal.SIGKILL)
                try:
                    rc = proc.wait(timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                        rc = proc.wait(timeout=0.5)
                    except Exception:
                        rc = proc.poll()

        # After process exit/kill, pipes will reach EOF; readers will finish.
        for t in threads:
            t.join(timeout=1.0)

        out = out_buf.decode("utf-8", "replace")
        err = err_buf.decode("utf-8", "replace")
        if flags["out_trunc"]:
            out += "\n...[truncated]"
        if flags["err_trunc"]:
            err += "\n...[truncated]"
        sig = None
        if isinstance(rc, int) and rc < 0:
            sig = -rc
        return RunnerResult(True, int(rc) if rc is not None else None, out, err, timed_out,
                            "timeout" if timed_out else None, flags["out_trunc"], flags["err_trunc"], terminated, sig)
    finally:
        try:
            if proc.poll() is None:
                try:
                    if os.name != "nt":
                        os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    pass
                try:
                    proc.kill()
                    proc.wait(timeout=0.5)
                except Exception:
                    pass
        except Exception:
            pass


class HermesExecutionAdapter:
    """ExecutionPort for bounded, read-only Hermes CLI status reads."""

    name = "hermes_cli"

    def __init__(
        self,
        *,
        enabled: bool = False,
        capability_enabled: bool = False,
        cli_path: str = "hermes",
        default_timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_timeout_ms: int = MAX_TIMEOUT_MS,
        stdout_max_bytes: int = DEFAULT_STDOUT_MAX,
        stderr_max_bytes: int = DEFAULT_STDERR_MAX,
        runner: Optional[Runner] = None,
        env_allow: Optional[List[str]] = None,
        strict_config: bool = False,
    ) -> None:
        self.enabled = bool(enabled)
        self.capability_enabled = bool(capability_enabled)
        if cli_path is None:
            self.cli_path = "hermes"
        elif isinstance(cli_path, str):
            self.cli_path = cli_path.strip()
        else:
            self.cli_path = str(cli_path).strip()
        # Keep explicit empty as empty so resolution fails closed; strict mode also validates.
        if strict_config:
            self.default_timeout_ms = _checked_int("default_timeout_ms", default_timeout_ms, lo=MIN_TIMEOUT_MS, hi=MAX_TIMEOUT_MS)
            self.max_timeout_ms = _checked_int("max_timeout_ms", max_timeout_ms, lo=MIN_TIMEOUT_MS, hi=MAX_TIMEOUT_MS)
            self.stdout_max_bytes = _checked_int("stdout_max_bytes", stdout_max_bytes, lo=MIN_OUTPUT_MAX, hi=MAX_OUTPUT_MAX)
            self.stderr_max_bytes = _checked_int("stderr_max_bytes", stderr_max_bytes, lo=MIN_OUTPUT_MAX, hi=MAX_OUTPUT_MAX)
        else:
            def _bound(value, default, lo, hi):
                try:
                    if isinstance(value, bool):
                        return default
                    v = int(value)
                except Exception:
                    return default
                if v < lo or v > hi:
                    return default
                return v
            self.default_timeout_ms = _bound(default_timeout_ms, DEFAULT_TIMEOUT_MS, MIN_TIMEOUT_MS, MAX_TIMEOUT_MS)
            self.max_timeout_ms = _bound(max_timeout_ms, MAX_TIMEOUT_MS, MIN_TIMEOUT_MS, MAX_TIMEOUT_MS)
            self.stdout_max_bytes = _bound(stdout_max_bytes, DEFAULT_STDOUT_MAX, MIN_OUTPUT_MAX, MAX_OUTPUT_MAX)
            self.stderr_max_bytes = _bound(stderr_max_bytes, DEFAULT_STDERR_MAX, MIN_OUTPUT_MAX, MAX_OUTPUT_MAX)
        if self.default_timeout_ms > self.max_timeout_ms:
            # fail closed in strict mode, clamp in permissive legacy construction
            if strict_config:
                raise errors.ConfigError("execution.hermes.default_timeout_ms must be <= execution.hermes.max_timeout_ms")
            self.default_timeout_ms = self.max_timeout_ms
        self._runner = runner or default_runner
        self.env_allow = list(env_allow) if env_allow is not None else [
            "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE",
            "TERM", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
            "HERMES_HOME", "HERMES_PROFILE",
        ]

    def available(self) -> bool:
        return bool(self.enabled and self.capability_enabled)

    def describe(self) -> Dict[str, Any]:
        attached = self.available()
        return {
            "name": self.name,
            "available": attached,
            "integration_status": "attached_read_only" if attached else "disabled",
            "contract_version": CONTRACT_VERSION,
            "capabilities": [CAPABILITY_STATUS_READ] if self.capability_enabled else [],
            "default_disabled": not (self.enabled and self.capability_enabled),
            "identity_model": TRUST_MODE_LOCAL,
            "cli_path_configured": bool(self.cli_path),
            "limits": {
                "default_timeout_ms": self.default_timeout_ms,
                "max_timeout_ms": self.max_timeout_ms,
                "stdout_max_bytes": self.stdout_max_bytes,
                "stderr_max_bytes": self.stderr_max_bytes,
            },
        }

    def _controlled_env(self) -> Dict[str, str]:
        env: Dict[str, str] = {}
        for k in self.env_allow:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # Avoid inheriting arbitrary secret-bearing vars outside allowlist.
        return env

    def _resolve_cli(self) -> str:
        path = self.cli_path
        if not isinstance(path, str):
            raise errors.ExecutionUnavailable("hermes cli path is invalid")
        if not path or any(ch.isspace() for ch in path) or "\x00" in path:
            raise errors.ExecutionUnavailable("hermes cli path is invalid")
        # Fixed argv only: reject argument-like payloads in cli_path.
        if path.startswith("-"):
            raise errors.ExecutionUnavailable("hermes cli path is invalid")
        resolved = shutil.which(path) if not os.path.isabs(path) else (path if os.path.isfile(path) and os.access(path, os.X_OK) else None)
        if not resolved:
            raise errors.ExecutionUnavailable("hermes cli is not available")
        return resolved

    def _v0_from_execution_request(self, request: ExecutionRequest) -> Dict[str, Any]:
        args = dict(getattr(request, "arguments", {}) or {})
        # Accept explicit v0 envelope fields in arguments as-is for validation
        # (including invalid versions/fields must be rejected, not rewritten).
        if "contract_version" in args or "permission_context" in args or "operation_id" in args:
            data = dict(args)
            data.setdefault("aj_task_id", request.task_id or "")
            data.setdefault("capability_id", request.capability_id or "")
            return data
        timeout_ms = int(max(1, int(getattr(request, "timeout_seconds", 60) or 60)) * 1000)
        timeout_ms = min(timeout_ms, self.max_timeout_ms)
        pctx = {
            "authorizer": "AJ",
            "authorization_decision": "allow",
            "decision_scope": {"capability": request.capability_id, "task_id": request.task_id},
            "trust_mode": TRUST_MODE_LOCAL,
            "principal_provenance": "local_trust_non_authenticated",
            "allowlist_entry_id": CAPABILITY_STATUS_READ,
        }
        # Caller of ExecutionPort in AJ has already passed AJ authorization checks;
        # we still require explicit allow context in v0 envelope construction.
        return {
            "contract_version": CONTRACT_VERSION,
            "aj_task_id": request.task_id or "",
            "operation_id": request.request_id or "",
            "attempt_id": request.request_id or "",
            "correlation_id": request.task_id or request.request_id or "",
            "capability_id": request.capability_id or "",
            "input": {},
            "timeout_ms": timeout_ms,
            "permission_context": pctx,
            "idempotency_key": "",
        }

    def _reject(self, req_data: Mapping[str, Any], reason: str, message: str) -> ExecutionResult:
        # Build best-effort echo ids
        task_id = str(req_data.get("aj_task_id") or req_data.get("task_id") or "")
        op = str(req_data.get("operation_id") or "")
        att = str(req_data.get("attempt_id") or "")
        corr = str(req_data.get("correlation_id") or "")
        cap = str(req_data.get("capability_id") or "")
        err = {"class": reason, "code": reason, "message": redact_text(message, limit=500), "retryable": False, "source": "aj"}
        payload = {
            "contract_version": CONTRACT_VERSION,
            "aj_task_id": task_id,
            "operation_id": op,
            "attempt_id": att,
            "correlation_id": corr,
            "capability_id": cap,
            "hermes_execution_id": None,
            "accepted": False,
            "status": "rejected",
            "result_payload": None,
            "error": err,
            "timestamps": {"observed_at": time.time()},
            "evidence": {"reason": reason},
            "provenance": {"adapter_id": self.name, "hermes_interface": "cli", "trust_mode": TRUST_MODE_LOCAL},
        }
        return ExecutionResult(request_id=str(req_data.get("request_id") or op or task_id or "hermes"), status="rejected", output=payload, error=err, verified=False)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not self.enabled or not self.capability_enabled:
            raise errors.ExecutionUnavailable("hermes execution adapter is disabled")
        req_data = self._v0_from_execution_request(request)
        v0, err_code = validate_request(req_data, max_timeout_ms=self.max_timeout_ms)
        if err_code or v0 is None:
            return self._reject(req_data, err_code or "request_invalid", "request rejected by contract/allowlist validation")

        # Deny-by-default capability allowlist (explicit)
        if v0.capability_id != CAPABILITY_STATUS_READ:
            return self._reject(req_data, "capability_not_allowed", "capability not allowlisted")

        try:
            cli = self._resolve_cli()
        except errors.AjError as exc:
            env = response_envelope(
                v0, accepted=False, status="failed",
                error={"class": "dependency_unavailable", "code": errors.EXECUTION_UNAVAILABLE,
                       "message": redact_text(str(exc)), "retryable": False, "source": "adapter"},
                timestamps={"observed_at": time.time()},
                evidence={"cli_path": redact_text(self.cli_path, limit=200)},
                provenance={"adapter_id": self.name, "hermes_interface": "cli", "trust_mode": TRUST_MODE_LOCAL},
            )
            return ExecutionResult(request_id=request.request_id, status="failed", output=env, error=env["error"], verified=False)

        argv = [cli, "gateway", "status"]  # fixed, no user-controlled args
        timeout_s = max(0.1, min(v0.timeout_ms, self.max_timeout_ms) / 1000.0)
        started_at = time.time()
        rr = self._runner(argv, timeout_s, self.stdout_max_bytes, self.stderr_max_bytes, self._controlled_env())
        finished_at = time.time()
        ts = {"started_at": started_at, "finished_at": finished_at, "observed_at": finished_at}
        safe_out = redact_text(rr.stdout, limit=self.stdout_max_bytes)
        safe_err = redact_text(rr.stderr, limit=self.stderr_max_bytes)
        out_trunc = bool(getattr(rr, "stdout_truncated", False) or "[truncated]" in (rr.stdout or ""))
        err_trunc = bool(getattr(rr, "stderr_truncated", False) or "[truncated]" in (rr.stderr or ""))
        evidence = {
            "argv_template": ["<hermes>", "gateway", "status"],
            "cli_resolved": redact_text(cli, limit=300),
            "exit_code": rr.exit_code,
            "signal": getattr(rr, "signal", None),
            "timed_out": rr.timed_out,
            "terminated": bool(getattr(rr, "terminated", False)),
            "stdout_truncated": out_trunc,
            "stderr_truncated": err_trunc,
            "stdout_chars": len(safe_out),
            "stderr_chars": len(safe_err),
            "collection": "bounded_incremental",
        }
        prov = {"adapter_id": self.name, "adapter_version": "v0", "hermes_interface": "cli", "trust_mode": TRUST_MODE_LOCAL}

        if not rr.started:
            err = {"class": "spawn_failed", "code": errors.EXECUTION_FAILED,
                   "message": redact_text(rr.error or "failed to start hermes cli", limit=300),
                   "retryable": False, "source": "adapter"}
            env = response_envelope(v0, accepted=False, status="failed", error=err, timestamps=ts, evidence=evidence, provenance=prov)
            return ExecutionResult(request_id=request.request_id, status="failed", output=env, error=err, verified=False)

        if rr.timed_out:
            err = {"class": "timeout", "code": "TIMEOUT", "message": "hermes gateway status timed out", "retryable": False, "source": "adapter"}
            env = response_envelope(
                v0, accepted=True, status="timeout",
                result_payload={"stdout": safe_out, "stderr": safe_err, "partial": True,
                                "observation": "timeout", "note": "timeout/partial output is not proof of gateway health"},
                error=err, timestamps=ts, evidence=evidence, provenance=prov,
            )
            return ExecutionResult(request_id=request.request_id, status="timeout", output=env, error=err, verified=False)

        if rr.exit_code == 0:
            # Bounded, sanitized diagnostic payload. Read-only probe completed (process exit 0).
            # No semantic health inference from unstructured text.
            payload = {
                "stdout": safe_out,
                "stderr": safe_err,
                "probe": "hermes.gateway.status",
                "observation": "exit_zero",
                "note": "diagnostic status output is untrusted text; process exit 0 does not by itself prove semantic gateway health",
            }
            env = response_envelope(
                v0, accepted=True, status="completed",
                result_payload=payload, timestamps=ts, evidence=evidence, provenance=prov,
            )
            return ExecutionResult(request_id=request.request_id, status="completed", output=env, verified=True,
                                   verification={"mode": "process_exit_zero", "command": "hermes gateway status"},
                                   started_at=started_at, finished_at=finished_at)

        err = {"class": "runtime_error", "code": errors.EXECUTION_FAILED,
               "message": f"hermes gateway status exited with code {rr.exit_code}", "retryable": False, "source": "hermes"}
        if getattr(rr, "signal", None) is not None:
            err["message"] = f"hermes gateway status terminated by signal {rr.signal}"
        env = response_envelope(
            v0, accepted=True, status="failed",
            result_payload={"stdout": safe_out, "stderr": safe_err, "observation": "nonzero_exit",
                            "note": "diagnostic status output is untrusted text; failure is based on process outcome"},
            error=err, timestamps=ts, evidence=evidence, provenance=prov,
        )
        return ExecutionResult(request_id=request.request_id, status="failed", output=env, error=err, verified=False,
                               started_at=started_at, finished_at=finished_at)
