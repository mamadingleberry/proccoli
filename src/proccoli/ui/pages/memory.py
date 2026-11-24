"""Memory page: RAM and swap graphs; module properties after authenticating."""

from __future__ import annotations

from typing import Callable, Optional

from ...core.units import format_bytes, format_percent
from ...devices.memory import MemoryMonitor, MemorySnapshot, summarize_modules
from ..page import PageKind
from ..widgets.info_row import InfoRow
from .device import DevicePage

PROPERTY_KEYS = ("Slots Used", "Speed", "Form Factor", "Type", "Type Detail")


class MemoryPage(DevicePage):
    def __init__(self, monitor: MemoryMonitor, settings,
                 authenticate: Optional[Callable[["MemoryPage"], None]] = None) -> None:
        super().__init__(monitor, settings, PageKind.MEMORY)
        # Supplied once the privileged helper exists (Milestone 12): called
        # with the page, it fetches the modules and calls show_modules().
        self.authenticate = authenticate
        self.banner = self.add_banner("You need to authenticate to see memory properties",
                                      "Authenticate")
        self.banner.set_revealed(True)
        self.banner.connect("button-clicked", self._on_authenticate)

        usage = self.add_group("Usage")
        self.memory = self.graph_box(usage, "Memory", [("usage", "%")])
        self.swap = self.graph_box(usage, "Swap", [("swap", "%")], color_offset=1)

        self.properties = self.add_group("Properties")
        self.property_rows = {k: InfoRow(k) for k in PROPERTY_KEYS}
        for row in self.property_rows.values():
            self.properties.add(row)
        self.properties.set_visible(False)
        if monitor.modules is not None:
            self.show_modules()

    def _on_authenticate(self, _banner) -> None:
        if self.authenticate is not None:
            self.authenticate(self)
            return
        self.report("Reading memory properties needs administrator rights: "
                    "install Proccoli (and pkexec) to use them")

    def elevation_offer(self):
        if self.authenticate is None or self.monitor.modules is not None:
            return None             # nothing to unlock (udev had the modules)
        from ..elevation import ElevationOffer
        return ElevationOffer(self.page_id, "Memory properties",
                              "Module type, speed and slots",
                              lambda done: self.authenticate(self, done))

    def show_modules(self) -> None:
        props = summarize_modules(self.monitor.modules or [])
        for key, row in self.property_rows.items():
            row.set_value(props.get(key))
        self.properties.set_visible(bool(props))
        self.banner.set_revealed(False)

    def update_labels(self, snap: MemorySnapshot) -> None:
        b = self.base
        self.memory.set_info(f"{format_bytes(snap.used, b)} of {format_bytes(snap.total, b)}"
                             f" ({format_percent(snap.usage)})")
        if snap.swap_total:
            self.swap.set_visible(True)
            self.swap.set_info(f"{format_bytes(snap.swap_used, b)} of "
                               f"{format_bytes(snap.swap_total, b)} "
                               f"({format_percent(snap.swap_usage)})")
        else:
            self.swap.set_visible(False)
