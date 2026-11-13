"""Agent boundary — how AJ talks to JARVIS and HELIX.

AJ does not import the agents' application code and does not know their internal
module layout. It reaches them through an adapter that speaks a transport. This
keeps the two sub-agents replaceable and keeps AJ from becoming a monolith.

Current reality (verified 2026-11-09):
    JARVIS   loopback bridge on 127.0.0.1:8875 — the app was not running, so the
             adapter reports unavailable. The bridge protocol is
             WebSocket-based; there is no documented HTTP task endpoint yet.
    HELIX    loopback bridge on 127.0.0.1:8765 — a WebSocket protocol server. An
             HTTP GET on the root returns no response.

Therefore :class:`HttpAgentAdapter` is wired but honest: it probes the socket and
returns ``rejected`` with ``agent_unavailable`` rather than pretending a task was
accepted. Adding a real task endpoint is sub-agent-side work that needs the
owner's approval, so it is documented as a remaining item instead of invented.
"""

from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable
from urllib.parse import urlparse

from . import errors
from .contracts import AgentRequest, AgentResult


@runtime_checkable
class AgentPort(Protocol):
    name: str

    def available(self) -> bool:  # pragma: no cover - protocol
        ...

    def describe(self) -> Dict[str, object]:  # pragma: no cover - protocol
        ...

    def execute(self, request: AgentRequest) -> AgentResult:  # pragma: no cover - protocol
        ...


def _probe(host: str, port: int, timeout: float = 0.4) -> bool:
    """Cheap TCP reachability probe. Says nothing about protocol correctness."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@dataclass
class HttpAgentAdapter:
    """Adapter for an agent that exposes a loopback HTTP/WS endpoint.

    ``transport`` is injected so the adapter is testable without a server. The
    default transport refuses to run: AJ must not silently make network calls to
    an endpoint that has not been agreed.
    """

    name: str
    endpoint: str
    task_path: str = "/aj/task"
    timeout_seconds: int = 120
    transport: Optional[Callable[[str, str, Optional[bytes], int], tuple]] = None
    notes: str = ""

    def _host_port(self) -> tuple:
        parsed = urlparse(self.endpoint)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return host, port

    def available(self) -> bool:
        host, port = self._host_port()
        return _probe(host, port)

    def describe(self) -> Dict[str, object]:
        host, port = self._host_port()
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "host": host,
            "port": port,
            "reachable": self.available(),
            "task_path": self.task_path,
            "protocol_verified": bool(self.transport),
            "notes": self.notes,
        }

    def execute(self, request: AgentRequest) -> AgentResult:
        started = time.time()
        if request.assigned_agent.upper() != self.name.upper():
            return AgentResult(
                task_id=request.task_id, agent=self.name, status="rejected",
                summary="request addressed to another agent",
                errors=[{"code": errors.AGENT_REJECTED,
                         "message": f"this adapter serves {self.name}"}],
                started_at=started,
            )
        if not self.available():
            return AgentResult(
                task_id=request.task_id, agent=self.name, status="rejected",
                summary=f"{self.name} is not reachable at {self.endpoint}",
                errors=[{"code": errors.AGENT_UNAVAILABLE,
                         "message": f"{self.name} is not reachable; no task was accepted"}],
                started_at=started,
            )
        if self.transport is None:
            return AgentResult(
                task_id=request.task_id, agent=self.name, status="rejected",
                summary="no agreed task transport is configured",
                errors=[{
                    "code": errors.AGENT_UNAVAILABLE,
                    "message": (f"{self.name} is reachable but exposes no agreed AJ task "
                                "endpoint; wiring one requires an approved change on the "
                                "sub-agent side"),
                }],
                started_at=started,
            )

        url = self.endpoint.rstrip("/") + self.task_path
        body = json.dumps(request.to_dict()).encode("utf-8")
        try:
            status, raw = self.transport("POST", url, body, self.timeout_seconds)
        except socket.timeout:
            return AgentResult(
                task_id=request.task_id, agent=self.name, status="failed",
                summary="agent timed out", started_at=started,
                errors=[{"code": errors.AGENT_TIMEOUT, "message": "timeout"}],
            )
        except Exception as exc:
            return AgentResult(
                task_id=request.task_id, agent=self.name, status="failed",
                summary="agent call failed", started_at=started,
                errors=[errors.normalize(exc).to_dict()],
            )

        if status >= 500:
            return AgentResult(
                task_id=request.task_id, agent=self.name, status="failed",
                summary=f"agent returned HTTP {status}", started_at=started,
                errors=[{"code": errors.AGENT_REJECTED,
                         "message": f"HTTP {status}"}],
            )
        try:
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (ValueError, AttributeError):
            return AgentResult(
                task_id=request.task_id, agent=self.name, status="failed",
                summary="agent returned a non-JSON body", started_at=started,
                errors=[{"code": errors.AGENT_REJECTED,
                         "message": "unparseable response"}],
            )
        payload.setdefault("task_id", request.task_id)
        payload.setdefault("agent", self.name)
        try:
            return AgentResult.from_dict(payload)
        except errors.AjError as exc:
            return AgentResult(
                task_id=request.task_id, agent=self.name, status="failed",
                summary="agent returned an invalid result", started_at=started,
                errors=[exc.to_dict()],
            )


class UnconfiguredAgent:
    """Placeholder for an agent that has no adapter yet."""

    def __init__(self, name: str, reason: str = "no adapter configured"):
        self.name = name
        self.reason = reason

    def available(self) -> bool:
        return False

    def describe(self) -> Dict[str, object]:
        return {"name": self.name, "available": False, "reason": self.reason}

    def execute(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            task_id=request.task_id, agent=self.name, status="rejected",
            summary=self.reason,
            errors=[{"code": errors.AGENT_UNAVAILABLE, "message": self.reason}],
        )


class AgentRegistry:
    """The agents AJ may delegate to, and their honest availability."""

    def __init__(self, agents: Optional[List[AgentPort]] = None):
        self._agents: Dict[str, AgentPort] = {}
        for agent in agents or []:
            self.register(agent)

    def register(self, agent: AgentPort) -> None:
        self._agents[agent.name.upper()] = agent

    def get(self, name: str) -> AgentPort:
        try:
            return self._agents[name.upper()]
        except KeyError:
            raise errors.AgentUnavailable(f"agent {name!r} is not configured") from None

    def find(self, name: str) -> Optional[AgentPort]:
        return self._agents.get((name or "").upper())

    def names(self) -> List[str]:
        return sorted(self._agents)

    def status(self) -> Dict[str, Dict[str, object]]:
        return {name: self._agents[name].describe() for name in self.names()}

    @classmethod
    def from_config(cls, config) -> "AgentRegistry":
        registry = cls()
        for name in ("jarvis", "helix"):
            section = config.get(f"agents.{name}", {}) or {}
            if not section.get("enabled", True):
                registry.register(UnconfiguredAgent(name.upper(), "disabled in configuration"))
                continue
            registry.register(
                HttpAgentAdapter(
                    name=name.upper(),
                    endpoint=str(section.get("endpoint", "")),
                    timeout_seconds=int(section.get("timeout_seconds", 120)),
                    notes=str(section.get("notes", "")),
                )
            )
        return registry
