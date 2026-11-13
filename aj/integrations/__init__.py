"""Adapters that connect AJ to concrete sub-agent surfaces.

Everything in this package is optional and lazily imported. If an integration
cannot load (missing module, absent bridge, no session bus), it reports that
plainly and AJ continues with the capability marked unavailable. No adapter here
modifies the sub-agent's code.
"""

from __future__ import annotations

__all__ = ["jarvis_registry", "gsconnect"]
