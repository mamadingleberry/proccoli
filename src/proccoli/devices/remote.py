"""The window's devices, read by ``proccoli``: the window itself reads no device files.

``RemoteDeviceManager`` has the ``DeviceManager`` interface the window
uses (``monitors``, ``monitor(id)``, ``device-added``,
``device-removed``, ``retry``), filled from the collector's D-Bus service
(``metrics_service``). Its monitors have the ``Monitor`` interface (and a
GPU's the ``GpuController`` one the GPU page uses), so pages, the sidebar,
the Overview and the history's graph filling don't change: each
``Readings`` signal is decoded (``snapshot_codec``) and fed to each
monitor's ``refresh``, which records it in its ``History`` and emits
``updated``, as a local monitor does after sampling.

Watching the collector's name asks the bus to start it if nobody owns it
(D-Bus activation, ``AUTO_START``); while it's away ``connected`` is False
and ``status`` says why, for the window's banner. All calls are
asynchronous; the bus connection and the clock are injected, so tests run
it against a collector on a private bus.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time
from typing import Callable, Optional

from gi.repository import Gio, GLib, GObject

from ..core.connections import Connections
from .source import DeviceSource
from ..core.history import History
from ..core.ticker import PLAN_KEYS, graph_plan
from ..gpu.backend import GpuProcessUsage, GpuSummary
from ..gpu.controller import DetailState
from ..metrics_service import BUS_NAME, INTERFACE, OBJECT_PATH
from . import snapshot_codec
from .base import DeviceInfo, DeviceKind, FailedMonitor, Monitor

log = logging.getLogger(__name__)

TIMEOUT_MS = 10_000
# Calls never start the collector: only the name watcher asks the bus to
# (``auto_start``), so a window closing after it stopped can't launch one.
NO_START = Gio.DBusCallFlags.NO_AUTO_START


def detail_classes() -> dict:
    """The detail sources whose views the window can show from readings
    alone. ``intel_gpu_top``'s views need its own process."""
    from ..gpu.amdgpu.backend import AmdgpuBackend
    from ..gpu.nvidia.backend import NvidiaBackend
    return {AmdgpuBackend.id: AmdgpuBackend, NvidiaBackend.id: NvidiaBackend}


def device_info_of(data: dict) -> DeviceInfo:
    return DeviceInfo(data["id"], DeviceKind(data["kind"]), data.get("name", data["id"]),
                      data.get("description", ""), data.get("icon", ""),
                      dict(data.get("properties") or {}))


class RemoteMonitor(Monitor):
    """A device the collector reads; ``feed`` gives it each reading."""

    def __init__(self, data: dict, settings) -> None:
        super().__init__(device_info_of(data))
        self.settings = settings
        self._sort_name = data.get("sort_name", "")
        self._described = dict(data.get("described") or self.info.properties)
        self._pending = None
        cpu = data.get("cpu") or {}
        self._thread_names = list(cpu.get("thread_names") or [])
        # The Processor page shows its sensor group when there is one.
        self.temperature_path = "collector" if cpu.get("has_temperature") else None
        modules = data.get("memory_modules")
        self.modules = snapshot_codec.decode(modules) if modules is not None else None
        # Lines up front, as a local monitor defines them: the
        # sidebar and the Overview chart them before the first reading.
        for name, unit in (data.get("history") or {}).items():
            self.history.define(name, unit)

    def sort_name(self) -> str:
        return self._sort_name

    def described_properties(self) -> dict[str, str]:
        return dict(self._described)

    def thread_names(self) -> list[str]:
        return list(self._thread_names)

    def feed(self, data: dict, now: float) -> None:
        """One reading, on this process's clock ``now``."""
        snap = snapshot_codec.decode(data.get("snapshot"))
        if not dataclasses.is_dataclass(snap):
            return
        self._pending = dataclasses.replace(snap, time=now)
        self.refresh(now)

    def sample(self, now: float):
        snap, self._pending = self._pending, None
        return snap


class Plan:
    """What detection chose for a GPU, as the collector said it."""

    def __init__(self, detail_text: str, explain: str) -> None:
        self._detail_text, self._explain = detail_text, explain

    def detail_text(self) -> str:
        return self._detail_text

    def explain(self) -> str:
        return self._explain


class RemoteDetailBackend(GObject.Object):
    """Stands in for a running detail source (AMD, NVIDIA) for its views:
    ``sample``, ``history``, ``gpu``, ``source_note`` and ``updated``, from
    the GPU's readings."""

    __gsignals__ = {
        "updated": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, cls, gpu, settings) -> None:
        super().__init__()
        self.cls = cls
        self.id = cls.id
        self.display_name = cls.display_name
        self.TABS = cls.TABS
        self.gpu = gpu
        self.apu = bool(getattr(gpu, "integrated", False))
        self.settings = settings
        self.source_note = ""
        self.sample = None
        plan = graph_plan(settings)
        self.history = History(plan[0])
        self.history.set_plan(*plan)

    def feed(self, sample, values: dict, units: dict, note: str, now: float) -> None:
        self.sample = sample
        self.source_note = note or self.source_note
        self.history.add(now, values, units)
        self.emit("updated")

    def has_data(self) -> bool:
        return self.sample is not None

    def history_target(self):
        return self.history

    def create_views(self, controller, services):
        # The vendor's own views, given this stand-in as their backend.
        return self.cls.create_views(self, controller, services)


class RemoteGpuController(RemoteMonitor):
    """A GPU the collector reads, with what the GPU page uses of a
    ``GpuController``."""

    __gsignals__ = {
        "detail-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, data: dict, settings) -> None:
        super().__init__(data, settings)
        gpu = data.get("gpu") or {}
        self.gpu = snapshot_codec.decode(gpu.get("info"))
        self.plan = Plan(gpu.get("plan_text", ""), gpu.get("plan_explain", ""))
        self.detail_class = detail_classes().get(gpu.get("detail_source"))
        self._needs_elevation = bool(gpu.get("needs_elevation"))
        self.detail_state = DetailState.UNAVAILABLE
        self.detail_message = ""
        self.detail_can_elevate = False
        self.detail_backend: Optional[RemoteDetailBackend] = None
        self._processes: dict[int, GpuProcessUsage] = {}

    @property
    def needs_elevation(self) -> bool:
        return self._needs_elevation

    @property
    def details_enabled(self) -> bool:
        return self.gpu.pci_slot not in self.settings.get("gpu-details-disabled")

    def set_details_enabled(self, on: bool) -> None:
        """The setting only: the collector starts or stops the source."""
        disabled = [s for s in self.settings.get("gpu-details-disabled")
                    if s != self.gpu.pci_slot]
        if not on:
            disabled.append(self.gpu.pci_slot)
        self.settings.set("gpu-details-disabled", disabled)

    def start_details(self, elevate: bool = False) -> None:
        """The collector runs detail sources; it never asks for a password
        (sources that need one aren't started)."""
        log.info("%s: details are the collector's to start", self.info.id)

    @property
    def detail_running(self) -> bool:
        return self.detail_state == DetailState.RUNNING and self.detail_backend is not None \
            and self.detail_backend.has_data()

    def summary(self) -> GpuSummary:
        snap = self.latest
        return (snap.summary if snap is not None and snap.summary is not None
                else GpuSummary())

    def process_usage(self) -> dict:
        return self._processes

    def detail_history(self):
        return self.detail_backend.history if self.detail_running else None

    def set_history_plan(self, points: int, every: int = 1,
                         step_s: Optional[float] = None) -> None:
        super().set_history_plan(points, every, step_s)
        if self.detail_backend is not None:
            self.detail_backend.history.set_plan(points, every, step_s)

    def feed(self, data: dict, now: float) -> None:
        super().feed(data, now)
        gpu = data.get("gpu") or {}
        self._processes = {int(pid): usage for pid, usage in
                           (snapshot_codec.decode(gpu.get("processes")) or {}).items()
                           if isinstance(usage, GpuProcessUsage)}
        state = DetailState.__members__.get(gpu.get("detail_state", ""), DetailState.UNAVAILABLE)
        if self.detail_class is None and state != DetailState.UNAVAILABLE:
            state = DetailState.UNAVAILABLE           # its views can't be shown here
        message = gpu.get("detail_message", "")
        if state == DetailState.RUNNING:
            if self.detail_backend is None:
                self.detail_backend = RemoteDetailBackend(self.detail_class, self.gpu,
                                                          self.settings)
                self.detail_backend.history.set_plan(*graph_plan(self.settings))
            snap = self.latest
            self.detail_backend.feed(snapshot_codec.decode(gpu.get("detail_sample")),
                                     snap.detail if snap is not None else {},
                                     snap.detail_units if snap is not None else {},
                                     gpu.get("detail_note", ""), now)
        else:
            self.detail_backend = None
        if (state, message) != (self.detail_state, self.detail_message):
            self.detail_state, self.detail_message = state, message
            self.emit("detail-changed", state.value)


def monitor_for(data: dict, settings) -> Monitor:
    failed = data.get("failed")
    if failed is not None:
        return FailedMonitor(device_info_of(data), failed.get("message", ""),
                             failed.get("details", ""))
    if data.get("gpu") is not None:
        return RemoteGpuController(data, settings)
    return RemoteMonitor(data, settings)


class RemoteDeviceManager(DeviceSource):
    """Receives the recorder's readings over D-Bus; this process reads no devices."""

    remote = True

    def __init__(self, settings, connection: Optional[Gio.DBusConnection] = None,
                 clock: Callable[[], float] = time.monotonic,
                 auto_start: bool = True) -> None:
        """``connection``: a bus to use (tests); None: the session bus.
        ``auto_start``: ask the bus to start the collector when it's away."""
        super().__init__(settings)
        self.connection = connection
        self.clock = clock
        self.auto_start = auto_start
        self.connected = False
        self.status = "Connecting to proccoli…"
        self._watch = 0
        self._subscriptions: list[int] = []
        self.connections = Connections()
        self.connections.watch(settings, PLAN_KEYS, lambda *_: self._on_plan_changed())

    # -- the interface the window uses ---------------------------------------------------

    def refresh(self, now: float) -> None:
        """The collector refreshes; readings arrive by themselves."""

    def rescan(self) -> None:
        """The collector rescans."""

    def retry(self, device_id: str) -> bool:
        """A failed device's *Try Again*: the collector rebuilds it (and
        says so with ``DeviceRemoved`` / ``DeviceAdded``)."""
        if not isinstance(self._monitors.get(device_id), FailedMonitor) or not self.connected:
            return False
        self.connection.call(BUS_NAME, OBJECT_PATH, INTERFACE, "Retry",
                             GLib.Variant("(s)", (device_id,)), None, NO_START,
                             TIMEOUT_MS, None, None)
        return True

    def flush(self, then: Callable[[], None]) -> None:
        """Ask the collector to write out its buffered readings, and call
        ``then`` when it has (or at once, when it's away or doesn't know
        how), so the window's history refill includes the last seconds."""
        if not self.connected or self.connection is None or self.connection.is_closed():
            then()
            return

        def done(conn, result) -> None:
            try:
                conn.call_finish(result)
            except GLib.Error as exc:            # an older collector: refill anyway
                log.debug("collector Flush: %s", exc.message)
            then()

        self.connection.call(BUS_NAME, OBJECT_PATH, INTERFACE, "Flush", None, None,
                             NO_START, TIMEOUT_MS, None, done)

    # -- lifecycle ---------------------------------------------------------------------

    def start(self, ticker=None) -> None:
        """Start watching for the collector (the ticker isn't needed: the
        collector's readings set the pace)."""
        self.started = True
        if self.connection is not None:
            self._watch_name()
        else:
            Gio.bus_get(Gio.BusType.SESSION, None, self._got_bus)

    def _got_bus(self, _source, result) -> None:
        try:
            self.connection = Gio.bus_get_finish(result)
        except GLib.Error as exc:
            self._set_status(False, f"No session bus: {exc.message}")
            return
        self._watch_name()

    def _watch_name(self) -> None:
        flags = (Gio.BusNameWatcherFlags.AUTO_START if self.auto_start
                 else Gio.BusNameWatcherFlags.NONE)
        self._watch = Gio.bus_watch_name_on_connection(
            self.connection, BUS_NAME, flags,
            lambda *_: self._appeared(), lambda *_: self._vanished())
        conn = self.connection
        self._subscriptions = [
            conn.signal_subscribe(BUS_NAME, INTERFACE, "Readings", OBJECT_PATH, None,
                                  Gio.DBusSignalFlags.NONE, self._on_readings),
            conn.signal_subscribe(BUS_NAME, INTERFACE, "DeviceAdded", OBJECT_PATH, None,
                                  Gio.DBusSignalFlags.NONE, self._on_device_added),
            conn.signal_subscribe(BUS_NAME, INTERFACE, "DeviceRemoved", OBJECT_PATH, None,
                                  Gio.DBusSignalFlags.NONE, self._on_device_removed),
        ]

    def stop(self) -> None:
        self.connections.disconnect_all()
        if self.connection is not None:
            for s in self._subscriptions:
                self.connection.signal_unsubscribe(s)
            if self.connected and not self.connection.is_closed():
                self.connection.call(BUS_NAME, OBJECT_PATH, INTERFACE, "Unsubscribe", None,
                                     None, NO_START, TIMEOUT_MS, None, None)
        self._subscriptions = []
        if self._watch:
            Gio.bus_unwatch_name(self._watch)
            self._watch = 0
        for m in self._monitors.values():
            m.stop()

    # -- the collector comes and goes ------------------------------------------------------

    def _set_status(self, connected: bool, status: str) -> None:
        if (connected, status) != (self.connected, self.status):
            log.info("collector: %s", status)
        super()._set_status(connected, status)

    def _appeared(self) -> None:
        self.connection.call(BUS_NAME, OBJECT_PATH, INTERFACE, "Devices", None,
                             GLib.VariantType.new("(s)"), NO_START, TIMEOUT_MS,
                             None, self._got_devices)

    def _got_devices(self, conn, result) -> None:
        try:
            devices = json.loads(conn.call_finish(result).unpack()[0])
        except (GLib.Error, ValueError) as exc:
            self._set_status(False, f"proccoli didn't answer: {exc}")
            return
        seen = set()
        for data in devices:
            seen.add(data["id"])
            if data["id"] not in self._monitors:
                self._add(data)
        for device_id in [i for i in self._monitors if i not in seen]:
            self._remove(device_id)
        conn.call(BUS_NAME, OBJECT_PATH, INTERFACE, "Subscribe", None, None,
                  NO_START, TIMEOUT_MS, None, self._subscribed)

    def _subscribed(self, conn, result) -> None:
        """Connected once the collector has us down for readings."""
        try:
            conn.call_finish(result)
        except GLib.Error as exc:
            self._set_status(False, f"proccoli didn't answer: {exc.message}")
            return
        self._set_status(True, "Receiving readings from proccoli")

    def _vanished(self) -> None:
        self._set_status(False, "Not receiving readings: proccoli isn't running")

    def reconnect(self) -> None:
        """*Try Again*: watch afresh (and ask the bus to start it)."""
        if self.connection is None:
            return
        if self._watch:
            Gio.bus_unwatch_name(self._watch)
        for s in self._subscriptions:
            self.connection.signal_unsubscribe(s)
        self._watch_name()

    # -- devices and readings ----------------------------------------------------------------

    def _add(self, data: dict) -> None:
        monitor = monitor_for(data, self.settings)
        monitor.set_history_plan(*graph_plan(self.settings))
        self._monitors[monitor.info.id] = monitor
        self.emit("device-added", monitor)

    def _remove(self, device_id: str) -> None:
        monitor = self._monitors.pop(device_id, None)
        if monitor is not None:
            monitor.stop()
            self.emit("device-removed", device_id)

    def _on_device_added(self, _c, _sender, _path, _iface, _signal, params) -> None:
        data = json.loads(params.unpack()[0])
        if data["id"] in self._monitors:
            self._remove(data["id"])               # rebuilt (Retry)
        self._add(data)

    def _on_device_removed(self, _c, _sender, _path, _iface, _signal, params) -> None:
        self._remove(params.unpack()[0])

    def _on_readings(self, _c, _sender, _path, _iface, _signal, params) -> None:
        _time_ms, _mono, text = params.unpack()
        now = self.clock()
        self.readings += 1
        for device_id, data in json.loads(text).items():
            monitor = self._monitors.get(device_id)
            if isinstance(monitor, RemoteMonitor):
                monitor.feed(data, now)

    def _on_plan_changed(self) -> None:
        plan = graph_plan(self.settings)
        for m in self._monitors.values():
            m.set_history_plan(*plan)
