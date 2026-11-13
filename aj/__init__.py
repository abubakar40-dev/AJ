"""AJ — the ecosystem control plane (pre-Hermes foundation).

AJ is the parent identity of the ecosystem: it owns routing, task records,
permission policy, capability discovery, audit, provider selection and the
Governed execution boundary. JARVIS (general/major work) and HELIX (calling and
communications) remain separate agents with their own repositories; Hermes is an
execution runtime that will be attached later through the port in
:mod:`aj.execution`.

What this package is
--------------------
A dependency-free, stdlib-only library. It imports no agent application code, so
it can be used from the JARVIS virtualenv, the HELIX runtime or a plain
``python3`` session without creating an import cycle. Agent-specific knowledge
enters through adapters (:mod:`aj.agents`, :mod:`aj.integrations`).

What this package is not
------------------------
It is not a second assistant runtime and it does not contain tool
implementations. It is the layer that decides *who* may do *what* and records the
outcome. Nothing here performs network I/O, reads secrets or writes user data on
import.

Status vocabulary used throughout (never upgrade silently):

    FINAL / APPROVED / UNDER DISCUSSION / BACKLOG / UNKNOWN / UNVERIFIED /
    DEPRECATED

Capability verification vocabulary:

    verified / implemented_unverified / partial / experimental / broken /
    stub / planned / unknown
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "__version__",
]
