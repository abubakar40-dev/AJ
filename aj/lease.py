"""Per-task operation and execution leases.

Two distinct lease concepts:

  1. Operation lease:  serialises conflicting MUTATIONS (cancel, retry, recover,
     authorization changes) for one task.  It is short-lived, acquired under
     flock, and its expiry does NOT authorize any action.

  2. Execution lease: identifies the worker that OWNS an EXECUTING task and
     controls execution heartbeat, expiry, and graceful shutdown.  It also is
     short-lived but its purpose is execution lifecycle management, not
     mutation serialisation.

Both share the same file-backed JSON + flock infrastructure but serve
different responsibilities.  Operation ownership must always be validated at
every mutation boundary; execution ownership must be validated at every
execution boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from . import errors, ids
from .locking import file_lock

DEFAULT_TTL = 30.0
ACTIVE = "ACTIVE"
RELEASED = "RELEASED"
STALE = "STALE"
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Lease dataclass – both operation and execution leases share this shape
# ---------------------------------------------------------------------------

@dataclass
class Lease:
    lease_id: str
    task_id: str
    operation: str          # e.g. "execute" | "cancel" | "retry" | "recover"
    worker_id: str
    pid: int
    host: str
    acquired_at: float
    expires_at: float
    last_heartbeat_at: float
    status: str = ACTIVE
    released_at: Optional[float] = None
    schema_version: int = SCHEMA_VERSION

    def expired(self, now: Optional[float] = None) -> bool:
        return self.status == ACTIVE and (now or time.time()) >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "task_id": self.task_id,
            "operation": self.operation,
            "worker_id": self.worker_id,
            "pid": self.pid,
            "host": self.host,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "status": self.status,
            "released_at": self.released_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lease":
        known = set(cls.__dataclass_fields__.keys())  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


# ---------------------------------------------------------------------------
# Low-level atomic JSON + per-task flock sidecar
# ---------------------------------------------------------------------------

def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, ensure_ascii=False, default=str)
            handle.flush()
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


# ---------------------------------------------------------------------------
# LeaseManager – file-backed leases with separation of concerns:
#   • acquire_operation  → serialises conflicting MUTATIONS (cancel, retry, recover)
#   • acquire_execution  → identifies the EXECUTING worker and controls lifecycle
# ---------------------------------------------------------------------------

class LeaseManager:
    """File-backed leases, or an in-process map when ``base_dir`` is None.

    Two lease families share the same backing store:

      1. Operation leases  (operation="cancel" | "retry" | "recover")
         • Serialize conflicting mutations for one task.
         • Expired lease ⇝ reported + refused until operator breaks it stale.
         • Never implies the prior operation did or did not execute.

      2. Execution leases  (operation="execute")
         • Identify the worker currently executing a task.
         • Heartbeat extends the expiry; expiry ⇝ recovery assessment.
         • Worker cannot continue mutating after losing valid execution lease.
    """

    def __init__(
        self,
        base_dir: Optional[str | Path] = None,
        *,
        audit=None,
        journal=None,
        ttl: float = DEFAULT_TTL,
        worker_id: str = "",
        clock=time.time,
    ):
        self._memory: Dict[str, Lease] = {}
        self._rlock = threading.RLock()
        self.base_dir = Path(base_dir) if base_dir else None
        self.audit = audit
        self.journal = journal
        self.ttl = float(ttl)
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self.clock = clock
        if self.base_dir is not None:
            (self.base_dir / "leases").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Paths / stems
    # ------------------------------------------------------------------

    def _stem(self, task_id: str) -> str:
        return hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:20]

    def _path(self, task_id: str) -> Optional[Path]:
        return self.base_dir / "leases" / f"{self._stem(task_id)}.json" if self.base_dir else None

    def _lock_path(self, task_id: str) -> Optional[Path]:
        return self.base_dir / "leases" / f"{self._stem(task_id)}.lock" if self.base_dir else None

    # ------------------------------------------------------------------
    # Guard – serialises access per-task via flock (or in-process lock)
    # ------------------------------------------------------------------

    @contextmanager
    def _guard(self, task_id: str) -> Iterator[None]:
        if self.base_dir is None:
            with self._rlock:
                yield
        else:
            with file_lock(self._lock_path(task_id), timeout=5.0):
                yield

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _read(self, task_id: str) -> Optional[Lease]:
        if self.base_dir is None:
            return self._memory.get(task_id)
        path = self._path(task_id)
        if path is None or not path.is_file():
            return None
        try:
            return Lease.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None

    def _write(self, lease: Lease) -> None:
        if self.base_dir is None:
            self._memory[lease.task_id] = lease
            return
        _atomic_json(self._path(lease.task_id), lease.to_dict())

    def _history(self, lease: Lease, action: str) -> None:
        if self.base_dir is None:
            return
        path = self.base_dir / "lease-history.jsonl"
        line = json.dumps(
            {"action": action, "at": self.clock(), "lease": lease.to_dict()},
            ensure_ascii=False,
            default=str,
        )
        with file_lock(str(path) + ".lock", timeout=5.0):
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()

    # ------------------------------------------------------------------
    # Auditing / journal integration
    # ------------------------------------------------------------------

    def _event(
        self,
        action: str,
        lease: Lease,
        result: str,
        detail: str = "",
    ) -> None:
        if self.audit is not None:
            try:
                self.audit.record(
                    action,
                    task_id=lease.task_id,
                    agent="AJ",
                    capability="",
                    result=result,
                    authorization="lease",
                    detail=detail,
                    params={
                        "lease_id": lease.lease_id,
                        "operation": lease.operation,
                        "worker_id": lease.worker_id,
                        "expires_at": lease.expires_at,
                    },
                )
            except Exception:
                pass
        if self.journal is not None:
            try:
                self.journal.append(
                    action.upper(),
                    task_id=lease.task_id,
                    worker_id=lease.worker_id,
                    lease_id=lease.lease_id,
                    metadata={"operation": lease.operation, "result": result},
                )
            except Exception:
                pass
        self._history(lease, action)

    # ------------------------------------------------------------------
    # --- Operation leases: serialise mutations (cancel, retry, recover) ----
    # ------------------------------------------------------------------

    def acquire_operation(
        self,
        task_id: str,
        operation: str,
        *,
        ttl: Optional[float] = None,
        worker_id: str = "",
    ) -> Lease:
        """Acquire an operation lease to serialise conflicting mutations.

        Supported operations: "cancel", "retry", "recover".
        Only one operation lease may be ACTIVE per task at a time.
        An expired operation lease is reported and refused until an operator
        explicitly breaks it as stale.
        """
        now = self.clock()
        ttl = float(ttl if ttl is not None else self.ttl)
        with self._guard(task_id):
            current = self._read(task_id)
            if current is not None and current.status == ACTIVE and current.operation == operation:
                if current.expired(now):
                    raise errors.LeaseExpired(
                        f"task {task_id} has an expired {operation} lease {current.lease_id}; "
                        "an operator must break it as stale before mutation"
                    )
                raise errors.LeaseHeld(
                    f"task {task_id} is owned by {current.operation} "
                    f"({current.worker_id}, lease {current.lease_id})"
                )
            # If there is an ACTIVE lease of a *different* operation, also block
            if current is not None and current.status == ACTIVE and current.operation != operation:
                raise errors.LeaseHeld(
                    f"task {task_id} has an active {current.operation} lease; "
                    f"cannot acquire {operation} lease"
                )
            lease = Lease(
                lease_id=ids.new_task_id("lease"),
                task_id=task_id,
                operation=operation,
                worker_id=worker_id or self.worker_id,
                pid=os.getpid(),
                host=socket.gethostname(),
                acquired_at=now,
                expires_at=now + ttl,
                last_heartbeat_at=now,
            )
            self._write(lease)
        self._event("lease_acquired", lease, "acquired")
        return lease

    def release_operation(self, lease: Lease) -> None:
        """Release an operation lease, marking it RELEASED."""
        with self._guard(lease.task_id):
            current = self._read(lease.task_id)
            if current is None or current.lease_id != lease.lease_id:
                raise errors.LeaseOwnership(
                    f"lease {lease.lease_id} no longer owns task {lease.task_id}"
                )
            current.status = RELEASED
            current.released_at = self.clock()
            self._write(current)
        self._event("lease_released", current, "released")

    def break_stale_operation(self, task_id: str, *, reason: str, actor: str = "operator") -> Lease:
        """Break an expired operation lease.  Requires explicit operator action.

        An expired lease does NOT authorize mutation.  The operator must call
        this to move the lease to STALE state before any new operation can
        be acquired.
        """
        now = self.clock()
        with self._guard(task_id):
            current = self._read(task_id)
            if current is None or current.status != ACTIVE:
                raise errors.AjError(
                    f"no active lease for task {task_id}",
                    code=errors.LEASE_OWNERSHIP,
                )
            if not current.expired(now):
                raise errors.LeaseHeld("lease is still valid; it cannot be broken")
            current.status = STALE
            self._write(current)
        self._event(
            "lease_broken_stale",
            current,
            "stale",
            detail=f"{actor}: {reason}"[:300],
        )
        return current

    # ------------------------------------------------------------------
    # --- Execution leases: identify executing worker + heartbeat ----
    # ------------------------------------------------------------------

    def acquire_execution(
        self,
        task_id: str,
        *,
        ttl: Optional[float] = None,
        worker_id: str = "",
    ) -> Tuple[Lease, bool]:
        """Acquire an execution lease to identify the owning worker.

        Returns (lease, newly_acquired) where newly_acquired is True when
        the lease was freshly acquired and False when an existing valid lease
        was already held (should not normally happen in single-worker mode).

        The execution lease's expiry does NOT authorize a mutation; it only
        controls whether a worker may continue executing.  An expired
        execution lease triggers recovery assessment, not silent mutation.
        """
        now = self.clock()
        ttl = float(ttl if ttl is not None else self.ttl)
        with self._guard(task_id):
            current = self._read(task_id)
            if current is not None and current.status == ACTIVE and current.operation == "execute":
                if current.expired(now):
                    # Lease expired — report, do NOT authorize mutation.
                    # The worker must re-acquire or the runtime will assess recovery.
                    raise errors.LeaseExpired(
                        f"task {task_id} execution lease {current.lease_id} has expired; "
                        "execution must be re-authorized or recovery initiated"
                    )
                # Valid existing execution lease — ensure same worker or promote
                if current.worker_id == (worker_id or self.worker_id):
                    # Renew heartbeat on existing lease
                    current.last_heartbeat_at = now
                    current.expires_at = now + ttl
                    self._write(current)
                    self._event("lease_renewed", current, "renewed")
                    return current, False
                # Different worker with valid lease — cannot usurp it
                raise errors.LeaseHeld(
                    f"task {task_id} execution lease owned by {current.worker_id}; "
                    "cannot usurp"
                )
            # No active execution lease — acquire fresh
            lease = Lease(
                lease_id=ids.new_task_id("lease"),
                task_id=task_id,
                operation="execute",
                worker_id=worker_id or self.worker_id,
                pid=os.getpid(),
                host=socket.gethostname(),
                acquired_at=now,
                expires_at=now + ttl,
                last_heartbeat_at=now,
            )
            self._write(lease)
        self._event("lease_acquired", lease, "acquired")
        return lease, True

    def release_execution(self, lease: Lease) -> None:
        """Release an execution lease, marking it RELEASED."""
        with self._guard(lease.task_id):
            current = self._read(lease.task_id)
            if current is None or current.lease_id != lease.lease_id:
                raise errors.LeaseOwnership(
                    f"lease {lease.lease_id} no longer owns task {lease.task_id}"
                )
            if current.operation != "execute":
                raise errors.LeaseOwnership(
                    f"lease {lease.lease_id} is not an execution lease"
                )
            current.status = RELEASED
            current.released_at = self.clock()
            self._write(current)
        self._event("lease_released", current, "released")

    def renew_execution(self, lease: Lease, *, ttl: Optional[float] = None) -> Lease:
        """Renew the heartbeat on an execution lease.

        Only the owning worker may renew.  Extends the expiry window.
        """
        with self._guard(lease.task_id):
            current = self._read(lease.task_id)
            if current is None or current.lease_id != lease.lease_id:
                raise errors.LeaseOwnership("lease does not own this task")
            if current.operation != "execute":
                raise errors.LeaseOwnership("lease is not an execution lease")
            if current.status != ACTIVE or current.expired(self.clock()):
                raise errors.LeaseExpired("lease is no longer valid")
            current.last_heartbeat_at = self.clock()
            current.expires_at = self.clock() + float(ttl if ttl is not None else self.ttl)
            self._write(current)
        self._event("lease_renewed", current, "renewed")
        return current

    # ------------------------------------------------------------------
    # Unified acquire — dispatches to operation or execution depending on op
    # ------------------------------------------------------------------

    def acquire(
        self,
        task_id: str,
        operation: str,
        *,
        ttl: Optional[float] = None,
        worker_id: str = "",
    ) -> Lease:
        """Acquire a lease for the given operation type.

        Dispatches to ``acquire_operation`` or ``acquire_execution`` based
        on the operation string.  This is the main entry-point used by the
        orchestrator; callers that need the distinction should use the
        family-specific methods directly.
        """
        if operation in ("cancel", "retry", "recover"):
            return self.acquire_operation(task_id, operation, ttl=ttl, worker_id=worker_id)
        # Default: treat as execution
        lease, _ = self.acquire_execution(task_id, ttl=ttl, worker_id=worker_id)
        return lease

    # ------------------------------------------------------------------
    # Utility / status
    # ------------------------------------------------------------------

    def get(self, task_id: str) -> Optional[Lease]:
        lease = self._read(task_id)
        if lease is not None:
            if lease.status == ACTIVE and lease.expired(self.clock()):
                lease.status = "EXPIRED"
        return lease

    def list(self, status: str = "") -> List[Lease]:
        if self.base_dir is None:
            leases = list(self._memory.values())
        else:
            leases = []
            for path in sorted((self.base_dir / "leases").glob("*.json")):
                try:
                    leases.append(Lease.from_dict(json.loads(path.read_text(encoding="utf-8"))))
                except (OSError, ValueError):
                    continue
        out = []
        for lease in leases:
            if lease.status == ACTIVE and lease.expired(self.clock()):
                lease.status = "EXPIRED"
            if not status or lease.status == status.upper():
                out.append(lease)
        return sorted(out, key=lambda item: item.acquired_at)

    def status(self, task_id: str) -> str:
        lease = self.get(task_id)
        return lease.status if lease else "free"

    @contextmanager
    def hold(
        self,
        task_id: str,
        operation: str,
        *,
        ttl: Optional[float] = None,
    ):
        """Context manager that acquires and automatically releases a lease.

        Dispatches to the appropriate lease family based on *operation*.
        """
        lease = self.acquire(task_id, operation, ttl=ttl)
        try:
            yield lease
        finally:
            # Auto-release based on operation type
            if operation in ("cancel", "retry", "recover"):
                self.release_operation(lease)
            else:
                self.release_execution(lease)

    # ------------------------------------------------------------------
    # Generic release method expected by orchestrator and CLI
    # ------------------------------------------------------------------

    def release(self, lease: Lease) -> None:
        """Release a lease, auto-detecting its type.

        If the lease operation is "cancel", "retry", or "recover", release
        it as an operation lease.  Otherwise treat it as an execution lease.
        """
        if lease.operation in ("cancel", "retry", "recover"):
            self.release_operation(lease)
        else:
            self.release_execution(lease)


# ---------------------------------------------------------------------------
# Compatibility shim so existing callers that do ``leases.acquire(task, "execute")``
# keep working without change while getting the new execution-lease semantics.
# ---------------------------------------------------------------------------

acquire = LeaseManager.acquire  # type: ignore[assignment]  # noqa: F811


# ---------------------------------------------------------------------------
# CLI / test helpers — dump / load
# ---------------------------------------------------------------------------

def _dump_leases(lease_mgr: LeaseManager) -> Dict[str, Dict[str, Any]]:
    """Snapshot all known leases for debugging / inspection."""
    result: Dict[str, Dict[str, Any]] = {}
    for lease in lease_mgr.list(""):
        result[lease.task_id] = lease.to_dict()
    return result


def _load_leases(lease_mgr: LeaseManager, snapshot: Dict[str, Dict[str, Any]]) -> None:
    """Restore leases from a snapshot (debug / test utility)."""
    for task_id, data in snapshot.items():
        l = Lease.from_dict(data)
        lease_mgr._write(l)