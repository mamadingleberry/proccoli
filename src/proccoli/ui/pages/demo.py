"""Demo page (``--demo``): a synthetic device laid out like a real one."""

from __future__ import annotations

from ...core.units import format_percent, format_rate
from ...devices.base import Monitor
from ...devices.demo import DemoSnapshot
from ..page import PageKind
from ..widgets.double_graph_box import DoubleGraphBox
from ..widgets.info_row import InfoRow
from .device import DevicePage


class DemoPage(DevicePage):
    def __init__(self, monitor: Monitor, settings) -> None:
        super().__init__(monitor, settings, PageKind.DEMO)
        self.peak = 0.0
        h = monitor.history

        usage_group = self.add_group("Usage")
        self.usage = self.graph_box(usage_group, "Usage", [("usage", "%")])
        self.io = DoubleGraphBox("Read", "Write", max_value=None, min_max=1e6)
        self.io.start.set_series([h.define("read", "B/s")])
        self.io.end.set_series([h.define("write", "B/s")], color_offset=1)
        self.add_pair(usage_group, self.io)
        self.current = InfoRow("Current Usage")
        self.peak_row = InfoRow("Peak Usage")
        self.samples = InfoRow("Samples")
        for row in (self.current, self.peak_row, self.samples):
            usage_group.add(row)

        self.add_properties({**monitor.info.properties, "Device": monitor.info.name})

    def update_labels(self, snap: DemoSnapshot) -> None:
        self.peak = max(self.peak, snap.usage or 0.0)
        self.usage.set_info(format_percent(snap.usage))
        self.io.start.set_info(format_rate(snap.read, self.base))
        self.io.end.set_info(format_rate(snap.write, self.base))
        self.current.set_value(format_percent(snap.usage))
        self.peak_row.set_value(format_percent(self.peak))
        self.samples.set_value(str(len(self.monitor.history)))
