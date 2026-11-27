"""The collector's D-Bus service: every
reading ``proccoli`` takes, for the window (and ``--watch``).

On the session bus as the app ID plus ``.Metrics`` (``BUS_NAME``):

- ``Devices() → s``: every device (JSON list: id, kind, name, description,
  icon, properties);
- ``Subscribe()`` / ``Unsubscribe()``: start or stop ``Readings`` for the
  caller; the service watches the caller's bus name and forgets it when it
  leaves, so with nobody subscribed nothing is encoded or sent;
- ``Readings(x time_ms, d monotonic, s readings)`` (signal, each update):
  ``{device id: {"snapshot": …, "gpu": {…}}}`` with snapshots encoded by
  ``devices/snapshot_codec``; a GPU adds its Details state, sample and
  per-process use;
- ``DeviceAdded(s device)``, ``DeviceRemoved(s id)`` (signals);
- ``Status() → s``: version, update interval, history state.

Payloads are JSON strings: one exact round trip for ``None``, nested
dataclasses and lists, which plain ``a{sv}`` can't carry (it has no
null). The bus connection, name owning and name watching are injected,
so tests run it on a private bus (a ``dbus-daemon`` of their own).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable, Optional

from gi.repository import Gio, GLib

from . import APP_ID, __version__
from .core.connections import Connections
from .devices import snapshot_codec

log = logging.getLogger(__name__)

BUS_NAME = f"{APP_ID}.Metrics"
OBJECT_PATH = "/" + BUS_NAME.replace(".", "/")
INTERFACE = BUS_NAME
INTROSPECTION = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="Devices"><arg type="s" direction="out" name="devices"/></method>
    <method name="Subscribe"/>
    <method name="Unsubscribe"/>
    <method name="Status"><arg type="s" direction="out" name="status"/></method>
    <method name="Retry"><arg type="s" direction="in" name="id"/>
      <arg type="b" direction="out" name="retried"/></method>
    <signal name="Readings">
      <arg type="x" name="time_ms"/><arg type="d" name="monotonic"/>
      <arg type="s" name="readings"/>
    </signal>
    <signal name="DeviceAdded"><arg type="s" name="device"/></signal>
    <signal name="DeviceRemoved"><arg type="s" name="id"/></signal>
  </interface>
</node>
"""


def device_info(monitor) -> dict:
    """What the window needs to build a device's page and sidebar entry:
    each monitor describes itself (``Monitor.describe``)."""
    return monitor.describe(snapshot_codec.encode)


def reading(monitor) -> Optional[dict]:
    """A device's latest reading (``Monitor.reading``), or None."""
    return monitor.reading(snapshot_codec.encode)


def owner_pid(connection: Gio.DBusConnection, name: str = BUS_NAME) -> Optional[int]:
    """The process ID of ``name``'s owner on ``connection``, or None (no
    owner, or the bus won't say). Asked of the bus daemon itself, so it
    can't wait on this process."""
    try:
        reply = connection.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "GetConnectionUnixProcessID", GLib.Variant("(s)", (name,)),
            GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 1000, None)
    except GLib.Error:
        return None
    return reply.unpack()[0]


class MetricsService:
    def __init__(self, devices, ticker, store=None, settings=None,
                 wall_clock: Callable[[], float] = time.time,
                 on_superseded: Optional[Callable[[Optional[int]], None]] = None) -> None:
        """``on_superseded(pid)``: called when another process already
        serves ``BUS_NAME`` (``pid`` is its process ID, None if the bus
        can't say), so this one has nothing to do."""
        self.devices = devices
        self.on_superseded = on_superseded
        self.ticker = ticker
        self.store = store
        self.settings = settings
        self.wall_clock = wall_clock
        self.connection: Optional[Gio.DBusConnection] = None
        self.subscribers: dict[str, int] = {}        # bus name -> name watch id
        self.sent = 0
        self._registration = 0
        self._owner = 0
        self.connections = Connections()
        self._node = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)

    # -- the bus ---------------------------------------------------------------------

    def start(self, connection: Optional[Gio.DBusConnection] = None) -> None:
        """Own the name on ``connection`` (tests) or the session bus."""
        c = self.connections
        c.connect(self.ticker, "tick", lambda *_: self.send_readings())
        c.connect(self.devices, "device-added", lambda _d, m: self._device_added(m))
        c.connect(self.devices, "device-removed",
                  lambda _d, i: self._emit("DeviceRemoved", GLib.Variant("(s)", (i,))))
        if connection is not None:
            self._acquired(connection)
            self._owner = Gio.bus_own_name_on_connection(
                connection, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
                lambda *_: log.info("serving readings as %s", BUS_NAME),
                lambda conn, _n: self._name_lost(conn))
            return
        self._owner = Gio.bus_own_name(
            Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
            lambda conn, _n: self._acquired(conn),
            lambda *_: log.info("serving readings as %s", BUS_NAME),
            lambda conn, _n: self._name_lost(conn))

    def _name_lost(self, connection) -> None:
        """The name is someone else's, or there's no bus. With a bus,
        another recorder serves the readings: say which and hand over."""
        if connection is None or connection.is_closed():
            log.warning("can't serve %s: no session bus", BUS_NAME)
            return
        pid = owner_pid(connection)
        log.info("another recorder (PID %s) already serves %s",
                 pid if pid is not None else "unknown", BUS_NAME)
        if self.on_superseded is not None:
            self.on_superseded(pid)

    def _acquired(self, connection) -> None:
        self.connection = connection
        self._registration = connection.register_object(
            OBJECT_PATH, self._node.interfaces[0], self._method_call, None, None)

    def stop(self) -> None:
        self.connections.disconnect_all()
        for watch in self.subscribers.values():
            Gio.bus_unwatch_name(watch)
        self.subscribers.clear()
        if self.connection is not None and self._registration:
            self.connection.unregister_object(self._registration)
            self._registration = 0
        if self._owner:
            Gio.bus_unown_name(self._owner)
            self._owner = 0

    # -- methods ------------------------------------------------------------------------

    def _method_call(self, connection, sender, _path, _iface, method, params, invocation):
        if method == "Devices":
            invocation.return_value(GLib.Variant("(s)", (json.dumps(
                [device_info(m) for m in self.devices.monitors()]),)))
        elif method == "Subscribe":
            # write out what's buffered (up to COMMIT_EVERY_S) before
            # the window fills its graphs from the history, or it shows those
            # seconds as a gap (and as time nothing was recording).
            if self.store is not None:
                self.store.commit()
            if sender not in self.subscribers:
                self.subscribers[sender] = Gio.bus_watch_name_on_connection(
                    connection, sender, Gio.BusNameWatcherFlags.NONE, None,
                    lambda _c, name: self._unsubscribe(name))
                log.info("readings for %s", sender)
            invocation.return_value(None)
        elif method == "Unsubscribe":
            self._unsubscribe(sender)
            invocation.return_value(None)
        elif method == "Status":
            invocation.return_value(GLib.Variant("(s)", (json.dumps(self.status()),)))
        elif method == "Retry":
            device_id = params.unpack()[0]
            retried = bool(self.devices.retry(device_id))
            invocation.return_value(GLib.Variant("(b)", (retried,)))
        else:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)

    def _unsubscribe(self, name: str) -> None:
        watch = self.subscribers.pop(name, None)
        if watch is not None:
            Gio.bus_unwatch_name(watch)
            log.info("no more readings for %s", name)

    def status(self) -> dict:
        from .core.ticker import update_interval_ms
        out = {"version": __version__, "devices": len(self.devices.monitors()),
               "subscribers": len(self.subscribers)}
        if self.settings is not None:
            out["update_interval_ms"] = update_interval_ms(self.settings)
            out["history"] = bool(self.settings.get("history"))
        if self.store is not None:
            out["writing"] = bool(self.store.writer and self.store.session is not None)
            out["session"] = self.store.session
        return out

    # -- signals ------------------------------------------------------------------------

    def _emit(self, signal: str, params: GLib.Variant) -> None:
        if self.connection is not None and self._registration:
            self.connection.emit_signal(None, OBJECT_PATH, INTERFACE, signal, params)

    def _device_added(self, monitor) -> None:
        self._emit("DeviceAdded", GLib.Variant("(s)", (json.dumps(device_info(monitor)),)))

    def send_readings(self) -> bool:
        """After each update (the devices refresh first: they connected to
        the ticker earlier): every device's reading, to subscribers only."""
        if not self.subscribers:
            return False
        payload = {}
        for monitor in self.devices.monitors():
            data = reading(monitor)
            if data is not None:
                payload[monitor.info.id] = data
        self._emit("Readings", GLib.Variant("(xds)", (
            int(round(self.wall_clock() * 1000)), time.monotonic(),
            json.dumps(payload, separators=(",", ":")))))
        self.sent += 1
        return True


# -- a client: proccoli --watch --------------------------------------------------


def watch(print_line: Callable[[str], None] = print, loop=None,
          connection: Optional[Gio.DBusConnection] = None, count: int = 0) -> int:
    """Print a line per update the running collector sends (``count``: stop
    after that many; 0: until Ctrl+C). Returns how many were printed. Calls
    are asynchronous, so it also works in the collector's own process
    (tests)."""
    connection = connection or Gio.bus_get_sync(Gio.BusType.SESSION, None)
    loop = loop or GLib.MainLoop()
    devices: dict[str, dict] = {}
    seen = [0]
    subscription = [0]

    def on_readings(_c, _sender, _path, _iface, _signal, params):
        from .core.units import iso_utc
        time_ms, _mono, text = params.unpack()
        parts = []
        for device_id, data in json.loads(text).items():
            snap = snapshot_codec.decode(data["snapshot"])
            label = (snap.usage_text or (f"{snap.usage:.0f} %" if snap.usage is not None else "")
                     or snap.detail_text or "–")
            parts.append(f"{devices.get(device_id, {}).get('name', device_id)} {label}")
        print_line(f"{iso_utc(time_ms / 1000)}  " + " · ".join(parts))
        seen[0] += 1
        if count and seen[0] >= count:
            loop.quit()

    def got_devices(conn, result):
        try:
            reply = conn.call_finish(result)
        except GLib.Error as exc:
            print_line(f"proccoli isn't running ({exc.message})")
            loop.quit()
            return
        for d in json.loads(reply.unpack()[0]):
            devices[d["id"]] = d
        print_line(f"{len(devices)} devices: " + ", ".join(devices))
        subscription[0] = conn.signal_subscribe(BUS_NAME, INTERFACE, "Readings", OBJECT_PATH,
                                                None, Gio.DBusSignalFlags.NONE, on_readings)
        conn.call(BUS_NAME, OBJECT_PATH, INTERFACE, "Subscribe", None, None,
                  Gio.DBusCallFlags.NONE, 5000, None, None)

    connection.call(BUS_NAME, OBJECT_PATH, INTERFACE, "Devices", None,
                    GLib.VariantType.new("(s)"), Gio.DBusCallFlags.NONE, 5000, None, got_devices)
    try:
        loop.run()
    finally:
        if subscription[0]:
            connection.signal_unsubscribe(subscription[0])
    return seen[0]
