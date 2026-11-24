"""Drive page: busy time, read and write speeds, totals, properties."""

from __future__ import annotations

from ...core.units import format_bytes, format_percent, format_rate
from ...devices.drive import DriveMonitor, DriveSnapshot
from ..page import PageKind
from ..widgets.info_row import InfoRow
from .device import DevicePage


class DrivePage(DevicePage):
    def __init__(self, monitor: DriveMonitor, settings) -> None:
        super().__init__(monitor, settings, PageKind.DRIVE, sort_name=monitor.block)
        usage = self.add_group("Usage")
        self.busy = self.graph_box(usage, "Drive Usage", [("usage", "%")])
        self.read = self.graph_box(usage, "Read Speed", [("read", "B/s")],
                                   max_value=None, min_max=1e6)
        self.write = self.graph_box(usage, "Write Speed", [("write", "B/s")],
                                    max_value=None, min_max=1e6, color_offset=1)
        self.total_read = InfoRow("Total Read")
        self.total_written = InfoRow("Total Written")
        usage.add(self.total_read)
        usage.add(self.total_written)
        self.add_properties(monitor.info.properties)

    def update_labels(self, snap: DriveSnapshot) -> None:
        b = self.base
        self.busy.set_info(format_percent(snap.usage))
        self.read.set_info(format_rate(snap.read_bps, b))
        self.write.set_info(format_rate(snap.write_bps, b))
        self.total_read.set_value(format_bytes(snap.total_read, b))
        self.total_written.set_value(format_bytes(snap.total_written, b))
