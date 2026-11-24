"""Devices: what's shown in the sidebar besides Apps and Processes.

A device has an immutable ``DeviceInfo`` (discovered once) and a ``Monitor``
that turns each tick into a ``Snapshot`` and records it in a ``History``.
See DESIGN.md §6.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional

from gi.repository import GObject

from ..core.history import History

log = logging.getLogger(__name__)


class DeviceKind(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    DRIVE = "drive"
    NETWORK = "network"
    BATTERY = "battery"
    DEMO = "demo"


@dataclass(frozen=True)
class DeviceInfo:
    id: str                       # stable, unique; also the page ID
    kind: DeviceKind
    name: str                     # sidebar title, e.g. "Wi-Fi Connection"
    description: str = ""         # sidebar subtitle, e.g. "wlp43s0"
    icon_name: str = ""
    properties: Mapping[str, str] = field(default_factory=dict, compare=False,
                                          hash=False)


@dataclass
class Snapshot:
    """One sample of a device. Subclasses add their own fields and list
    what goes into the history in ``history_values()``."""
    time: float
    usage: Optional[float] = None     # percent 0..100, drives the sidebar meter
    usage_text: str = ""              # sidebar usage label, e.g. "42 %"
    detail_text: str = ""             # sidebar detail, e.g. "3.1 of 16 GB"

    def history_values(self) -> dict[str, Optional[float]]:
        return {"usage": self.usage}

    def history_units(self) -> Mapping[str, str]:
        return {"usage": "%"}

    # What the history database records (core/history_store.py): the graphed
    # readings, plus absolute figures a snapshot only graphs as percentages.
    def stats_values(self) -> dict[str, Optional[float]]:
        return self.history_values()

    def stats_units(self) -> Mapping[str, str]:
        return self.history_units()


class Monitor(GObject.Object):
    """Base class for everything that samples a device on each tick.

    Subclasses implement ``sample(now)``. ``refresh(now)`` records the
    snapshot and emits ``updated``. A failing ``sample()`` never propagates
    into the main loop: it's logged and recorded as a gap.
    """

    __gsignals__ = {
        "updated": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, info: DeviceInfo, history_points: int = 60) -> None:
        super().__init__()
        self.info = info
        self.history = History(history_points)
        self.latest: Optional[Snapshot] = None
        self.failures = 0

    def sample(self, now: float) -> Optional[Snapshot]:
        """Read the device. Return None when there's nothing to record yet
        (e.g. the first sample of a delta-based measurement)."""
        raise NotImplementedError

    def refresh(self, now: float) -> None:
        try:
            snapshot = self.sample(now)
        except Exception:  # noqa: BLE001 - never raise into GTK callbacks
            self.failures += 1
            if self.failures == 1:
                log.exception("%s: sampling failed", self.info.id)
            self.history.add_gap(now)
            return
        self.failures = 0
        if snapshot is None:
            return
        self.history.add(now, snapshot.history_values(), snapshot.history_units())
        self.latest = snapshot
        self.emit("updated", snapshot)

    def set_history_points(self, n: int) -> None:
        self.history.set_max_points(n)

    def set_history_plan(self, points: int, every: int = 1,
                         step_s: Optional[float] = None) -> None:
        """The graphs' time range: ``points`` points of ``every`` samples
        (``ticker.graph_plan``)."""
        self.history.set_plan(points, every, step_s)

    def detail_history(self):
        """A second history to fill from the database (a GPU's Details
        tab), or None."""
        return None

    def start(self) -> None:
        """Hook for monitors with background work (streams, helpers)."""

    def stop(self) -> None:
        """Counterpart of ``start()``."""


class FailedMonitor(Monitor):
    """Stands in for a device whose monitor couldn't be built or started
    (Milestone 55). The device keeps its sidebar entry, and its page is an
    error page showing ``message`` (what went wrong, in words) and
    ``details`` (the technical part, e.g. a traceback), with *Try Again*
    (``DeviceManager.retry``). It records nothing."""

    def __init__(self, info: DeviceInfo, message: str, details: str = "") -> None:
        super().__init__(info, 2)
        self.message = message
        self.details = details

    def sample(self, now: float) -> Optional[Snapshot]:
        return None
