"""Optional NetworkManager lookups over D-Bus (no extra packages needed).

Everything returns None when NetworkManager isn't running or the bus isn't
reachable, so callers can treat it as "not known".
"""

from __future__ import annotations

import logging
from typing import Optional

from gi.repository import Gio, GLib

log = logging.getLogger(__name__)

NM = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"


class NetworkManagerClient:
    def __init__(self) -> None:
        self._bus: Optional[Gio.DBusConnection] = None
        self._failed = False

    def _connection(self) -> Optional[Gio.DBusConnection]:
        if self._bus is None and not self._failed:
            try:
                self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            except GLib.Error as exc:
                log.debug("system bus unavailable: %s", exc.message)
                self._failed = True
        return self._bus

    def _call(self, path, interface, method, args, reply_type):
        bus = self._connection()
        if bus is None:
            return None
        try:
            return bus.call_sync(NM, path, interface, method, args,
                                 GLib.VariantType.new(reply_type),
                                 Gio.DBusCallFlags.NONE, 500, None).unpack()
        except GLib.Error as exc:
            log.debug("NetworkManager %s failed: %s", method, exc.message)
            return None

    def _property(self, path, interface, name):
        reply = self._call(path, "org.freedesktop.DBus.Properties", "Get",
                           GLib.Variant("(ss)", (interface, name)), "(v)")
        return reply[0] if reply else None

    def connection_name(self, interface: str) -> Optional[str]:
        """Name of the active connection on ``interface`` (for Wi-Fi this is
        normally the network's SSID)."""
        reply = self._call(NM_PATH, NM, "GetDeviceByIpIface",
                           GLib.Variant("(s)", (interface,)), "(o)")
        if not reply:
            return None
        active = self._property(reply[0], f"{NM}.Device", "ActiveConnection")
        if not active or active == "/":
            return None
        name = self._property(active, f"{NM}.Connection.Active", "Id")
        return name or None
