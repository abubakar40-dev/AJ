"""GSConnect device-bridge discovery (read-only).

What this adapter does
----------------------
It asks GSConnect, over the session bus, which phones are paired and connected,
and which plugin interfaces each phone actually exports. That is enough to answer
the only question that matters before promising anything: *can this bridge place a
call, or only exchange notifications and files?*

What it does not do
-------------------
It does not invent DBus method names. Verified on 2026-11-09: one phone
("Redmi A3") is paired and connected, and its object exports Properties,
Introspectable, Peer, Device, gtk.Menus and gtk.Actions — **no telephony
interface**. So call control is reported as unavailable rather than guessed.

PyGObject is imported lazily so AJ keeps working (with the bridge marked
unavailable) on a machine without it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..calling import BridgeCapabilities, errors

BUS_NAME = "org.gnome.Shell.Extensions.GSConnect"
ROOT_PATH = "/org/gnome/Shell/Extensions/GSConnect"


@dataclass
class BridgeDevice:
    device_id: str
    name: str
    paired: bool
    connected: bool
    kind: str
    interfaces: List[str] = field(default_factory=list)

    @property
    def telephony_interfaces(self) -> List[str]:
        return [i for i in self.interfaces if "telephony" in i.lower()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "paired": self.paired,
            "connected": self.connected,
            "kind": self.kind,
            "interfaces": self.interfaces,
            "telephony_interfaces": self.telephony_interfaces,
        }


class GSConnectBridge:
    """DeviceBridge implementation backed by GSConnect."""

    name = "gsconnect"

    def __init__(self, timeout_ms: int = 2000):
        self.timeout_ms = int(timeout_ms)
        self._devices: Optional[List[BridgeDevice]] = None

    # --- discovery -------------------------------------------------------
    def _session_bus(self):
        try:
            from gi.repository import Gio  # type: ignore
        except Exception:
            return None
        try:
            return Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception:
            return None

    def devices(self, refresh: bool = False) -> List[BridgeDevice]:
        if self._devices is not None and not refresh:
            return self._devices
        devices: List[BridgeDevice] = []
        bus = self._session_bus()
        if bus is None:
            self._devices = devices
            return devices
        try:
            result = bus.call_sync(
                BUS_NAME, ROOT_PATH, "org.freedesktop.DBus.ObjectManager",
                "GetManagedObjects", None, None, 0, self.timeout_ms, None,
            )
            objects = result.unpack()[0] if isinstance(result.unpack(), tuple) \
                else result.unpack()
        except Exception:
            self._devices = devices
            return devices

        for path, interfaces in (objects or {}).items():
            if not str(path).startswith(ROOT_PATH + "/Device/"):
                continue
            props = interfaces.get("org.gnome.Shell.Extensions.GSConnect.Device", {})
            devices.append(
                BridgeDevice(
                    device_id=str(props.get("Id", str(path).rsplit("/", 1)[-1])),
                    name=str(props.get("Name", "unknown")),
                    paired=bool(props.get("Paired", False)),
                    connected=bool(props.get("Connected", False)),
                    kind=str(props.get("Type", "unknown")),
                    interfaces=sorted(interface for interface in interfaces),
                )
            )
        self._devices = devices
        return devices

    # --- DeviceBridge ----------------------------------------------------
    def available(self) -> bool:
        return any(d.paired and d.connected for d in self.devices())

    def capabilities(self) -> BridgeCapabilities:
        """Only advertise what a connected device actually exports."""
        caps = BridgeCapabilities()
        for device in self.devices():
            if not (device.paired and device.connected):
                continue
            if device.telephony_interfaces:
                # A telephony plugin is exported. Method names are still not
                # verified, so only presence-level capabilities are claimed.
                caps.can_receive_call_events = True
                caps.can_read_call_state = True
        return caps

    def describe(self) -> Dict[str, Any]:
        devices = self.devices(refresh=True)
        connected = [d for d in devices if d.paired and d.connected]
        return {
            "bridge": self.name,
            "available": bool(connected),
            "devices": [d.to_dict() for d in devices],
            "capabilities": self.capabilities().to_dict(),
            "notes": (
                "Paired/connected device present. Call control requires a telephony "
                "plugin interface, which is not exported on this machine."
                if connected and not any(d.telephony_interfaces for d in connected)
                else ""
            ),
        }

    def open_dialer(self, number: str) -> Dict[str, Any]:
        if not self.capabilities().can_open_dialer:
            raise errors.CallingError(
                "GSConnect does not expose a dialer handoff here; "
                "capability is unverified and therefore unavailable"
            )
        raise errors.CallingError("dialer handoff is implemented only after verification")

    def place_call(self, number: str) -> Dict[str, Any]:
        caps = self.capabilities()
        if not caps.can_place_call:
            raise errors.CallingError(
                "GSConnect exposes no call-control interface for this device; "
                "no call was placed"
            )
        raise errors.CallingError("call placement is implemented only after verification")


def probe() -> Dict[str, Any]:
    return GSConnectBridge().describe()


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    print(json.dumps(probe(), indent=2))
