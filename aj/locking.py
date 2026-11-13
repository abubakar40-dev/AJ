"""Advisory file locking (POSIX).

Append-only logs need serialised writers, not atomic replacement: two processes
must not interleave partial lines. ``flock`` on a sidecar lock file is enough,
releases automatically when the owning process dies, and needs no stale-lock
heuristics.

Portability: this is Linux/POSIX-first. On platforms without ``fcntl`` the lock
degrades to a no-op so imports still work, and ``available()`` reports False.
That limitation is deliberate and documented, not hidden.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Iterator, Optional

from . import errors

try:  # pragma: no cover - platform dependent
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

DEFAULT_TIMEOUT = 5.0
POLL_SECONDS = 0.02


def available() -> bool:
    return fcntl is not None


@contextmanager
def file_lock(path: str | Path, *, exclusive: bool = True,
              timeout: float = DEFAULT_TIMEOUT) -> Iterator[None]:
    """Hold an advisory lock for the duration of the block.

    Raises :class:`errors.StorageBusy` if the lock cannot be acquired before the
    deadline. The descriptor is always closed, so an exception cannot leave the
    lock held.
    """
    if fcntl is None:  # pragma: no cover - non-POSIX fallback
        with nullcontext():
            yield
        return

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(target), os.O_CREAT | os.O_RDWR, 0o600)
    mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    deadline: Optional[float] = None if timeout is None else time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, mode | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if deadline is not None and time.monotonic() >= deadline:
                    raise errors.StorageBusy(
                        f"could not acquire {'write' if exclusive else 'read'} "
                        f"lock on {target} within {timeout}s"
                    ) from None
                time.sleep(POLL_SECONDS)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def lock_status(path: str | Path) -> str:
    """Report ``free`` or ``held`` without waiting. Read-only in effect."""
    if fcntl is None:  # pragma: no cover
        return "unsupported"
    target = Path(path)
    if not target.exists():
        return "free"
    fd = os.open(str(target), os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "held"
        fcntl.flock(fd, fcntl.LOCK_UN)
        return "free"
    finally:
        os.close(fd)
