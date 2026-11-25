"""Where devices come from: the base the window and the history read.

Two kinds:

- ``DeviceManager`` (``devices/manager.py``) reads the devices itself:
  the recorder, ``--demo``, and tests. Always connected.
- ``RemoteDeviceManager`` (``devices/remote.py``) receives what the
  recorder read, over D-Bus: the window. Connected while the recorder
  answers.

Both keep monitors by device id and emit ``device-added`` (the monitor)
and ``device-removed`` (its id) as devices come and go, and
``connection-changed`` when ``connected`` or ``status`` change.
"""

from __future__ import annotations

from typing import Optional

from gi.repository import GObject

from .base import DeviceKind, Monitor


class DeviceSource(GObject.Object):
    __gsignals__ = {
        "device-added": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "device-removed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # ``connected`` or ``status`` changed.
        "connection-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # True when this process reads no devices: they come from the recorder.
    remote = False

    def __init__(self, settings) -> None:
        super().__init__()
        self.settings = settings
        self._monitors: dict[str, Monitor] = {}
        self.started = False
        self.connected = True
        self.status = ""
        self.readings = 0       # readings received (remote) since starting

    # -- access ----------------------------------------------------------------

    def monitors(self, kind: Optional[DeviceKind] = None) -> list[Monitor]:
        return [m for m in self._monitors.values() if kind is None or m.info.kind == kind]

    def monitor(self, device_id: str) -> Optional[Monitor]:
        return self._monitors.get(device_id)

    # -- what each kind does ---------------------------------------------------

    def start(self, ticker=None) -> None:
        """Find the devices and start following them."""
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def refresh(self, now: float) -> None:
        """Read every device (or nothing, when readings arrive by themselves)."""
        raise NotImplementedError

    def rescan(self) -> None:
        """Look for devices that came or went."""
        raise NotImplementedError

    def retry(self, device_id: str) -> bool:
        """Try a failed device again (its page's *Try Again*); True if tried."""
        raise NotImplementedError

    def reconnect(self) -> None:
        """Connect again after losing the source; nothing to do locally."""

    def _set_status(self, connected: bool, status: str) -> None:
        if (connected, status) != (self.connected, self.status):
            self.connected, self.status = connected, status
            self.emit("connection-changed")
