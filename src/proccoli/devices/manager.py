"""Discovers devices, owns their monitors and refreshes them on each tick.

Each device type contributes a ``Discoverer``. Types that can appear and
disappear at runtime (drives, network interfaces) set ``rescan = True`` and
are re-discovered every few seconds, or immediately when one of their
``settings_keys`` changes (e.g. *Show Virtual Drives*).

A device whose monitor can't be built or started still appears, as a
``FailedMonitor``: its page explains the error and offers *Try Again*
(``retry``), instead of the device silently missing (Milestone 55).
"""

from __future__ import annotations

import logging
import traceback
from typing import Optional

from gi.repository import GObject

from ..core.sysroot import SysRoot
from .base import DeviceInfo, DeviceKind, FailedMonitor, Monitor
from ..core.ticker import graph_plan

log = logging.getLogger(__name__)


class Discoverer:
    """Base class: find the devices of one kind and build their monitors."""
    kind: DeviceKind
    rescan = False                  # re-discover periodically (hotplug)
    settings_keys: tuple[str, ...] = ()  # settings that change what's found

    def discover(self, sysroot: SysRoot, settings) -> list[DeviceInfo]:
        raise NotImplementedError

    def create_monitor(self, info: DeviceInfo, sysroot: SysRoot, settings) -> Monitor:
        raise NotImplementedError


class DeviceManager(GObject.Object):
    __gsignals__ = {
        "device-added": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "device-removed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, sysroot: SysRoot, settings, rescan_interval_s: float = 5.0) -> None:
        super().__init__()
        self.sysroot = sysroot
        self.settings = settings
        self.rescan_interval_s = rescan_interval_s
        self.discoverers: list[Discoverer] = []
        self._monitors: dict[str, Monitor] = {}
        self._owner: dict[str, Discoverer] = {}
        self._last_rescan: Optional[float] = None
        self._ticker_handler = 0
        self.started = False
        # Graphs keep their time range: the number of points follows both
        # the range and the refresh speed (M58).
        for key in ("graph-time-range", "update-interval"):
            settings.connect_changed(key, lambda *_: self._on_points_changed())

    def register(self, discoverer: Discoverer) -> None:
        self.discoverers.append(discoverer)
        for key in discoverer.settings_keys:
            self.settings.connect_changed(key, lambda *_: self.rescan())

    # -- access ----------------------------------------------------------------

    def monitors(self, kind: Optional[DeviceKind] = None) -> list[Monitor]:
        return [m for m in self._monitors.values() if kind is None or m.info.kind == kind]

    def monitor(self, device_id: str) -> Optional[Monitor]:
        return self._monitors.get(device_id)

    # -- lifecycle -----------------------------------------------------------------

    def start(self, ticker=None) -> None:
        """Discover everything once, then refresh on each tick."""
        for d in self.discoverers:
            self._scan(d)
        self.started = True
        if ticker is not None:
            self._ticker = ticker
            self._ticker_handler = ticker.connect("tick", lambda _t, now: self.refresh(now))

    def stop(self) -> None:
        if self._ticker_handler:
            self._ticker.disconnect(self._ticker_handler)
            self._ticker_handler = 0
        for m in self._monitors.values():
            m.stop()

    def refresh(self, now: float) -> None:
        for m in list(self._monitors.values()):
            m.refresh(now)
        if self._last_rescan is None:
            self._last_rescan = now
        elif now - self._last_rescan >= self.rescan_interval_s:
            self._last_rescan = now
            self.rescan()

    def rescan(self) -> None:
        for d in self.discoverers:
            if d.rescan or d.settings_keys:
                self._scan(d)

    # -- internals ---------------------------------------------------------------------

    def _scan(self, discoverer: Discoverer) -> None:
        try:
            found = discoverer.discover(self.sysroot, self.settings)
        except Exception:  # noqa: BLE001 - one broken type must not stop the rest
            log.exception("discovering %s devices failed", discoverer.kind.value)
            return
        found_ids = {info.id for info in found}
        for device_id, owner in list(self._owner.items()):
            if owner is discoverer and device_id not in found_ids:
                self._remove(device_id)
        for info in found:
            if info.id not in self._monitors:
                self._add(discoverer, info)

    def _add(self, discoverer: Discoverer, info: DeviceInfo) -> None:
        monitor = self._build(discoverer, info)
        monitor.set_history_plan(*graph_plan(self.settings))
        self._monitors[info.id] = monitor
        self._owner[info.id] = discoverer
        log.debug("device added: %s%s", info.id,
                  " (failed)" if isinstance(monitor, FailedMonitor) else "")
        self.emit("device-added", monitor)

    def _build(self, discoverer: Discoverer, info: DeviceInfo) -> Monitor:
        """The device's monitor, started; a ``FailedMonitor`` if either step
        raised (one broken device must not stop the rest)."""
        try:
            monitor = discoverer.create_monitor(info, self.sysroot, self.settings)
        except Exception as exc:  # noqa: BLE001
            log.exception("creating the monitor for %s failed", info.id)
            return FailedMonitor(info, f"Proccoli couldn't set up this device: {exc}",
                                 traceback.format_exc())
        try:
            monitor.start()
        except Exception as exc:  # noqa: BLE001
            log.exception("starting the monitor for %s failed", info.id)
            try:
                monitor.stop()
            except Exception:  # noqa: BLE001
                log.debug("stopping %s after a failed start also failed", info.id)
            return FailedMonitor(info, f"Proccoli couldn't start reading this device: {exc}",
                                 traceback.format_exc())
        return monitor

    def retry(self, device_id: str) -> bool:
        """Build a failed device's monitor again (its page's *Try Again*).
        Emits ``device-removed`` then ``device-added``; True if it was a
        failed device that is still known."""
        monitor = self._monitors.get(device_id)
        discoverer = self._owner.get(device_id)
        if not isinstance(monitor, FailedMonitor) or discoverer is None:
            return False
        self._remove(device_id)
        self._add(discoverer, monitor.info)
        return True

    def _remove(self, device_id: str) -> None:
        monitor = self._monitors.pop(device_id)
        self._owner.pop(device_id, None)
        monitor.stop()
        log.debug("device removed: %s", device_id)
        self.emit("device-removed", device_id)

    def _on_points_changed(self) -> None:
        plan = graph_plan(self.settings)
        for m in self._monitors.values():
            m.set_history_plan(*plan)
