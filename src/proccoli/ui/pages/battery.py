"""Battery page: charge and power draw, battery health and details."""

from __future__ import annotations

from ...core.units import format_percent, format_power
from ...devices.battery import BatteryMonitor, BatterySnapshot
from ..page import PageKind
from ..widgets.info_row import InfoRow
from .device import DevicePage


class BatteryPage(DevicePage):
    def __init__(self, monitor: BatteryMonitor, settings) -> None:
        super().__init__(monitor, settings, PageKind.BATTERY)
        usage = self.add_group("Usage")
        self.charge = self.graph_box(usage, "Charge", [("usage", "%")])
        self.power = self.graph_box(usage, "Power Usage", [("power", "W")], max_value=None,
                                    min_max=10.0, color_offset=1)
        self.state = InfoRow("State")
        usage.add(self.state)
        self.add_properties(monitor.info.properties)

    def update_labels(self, snap: BatterySnapshot) -> None:
        self.charge.set_info(format_percent(snap.charge))
        self.power.set_visible(snap.power_w is not None)
        if snap.power_w is not None:
            self.power.set_info(format_power(snap.power_w))
        self.state.set_value(snap.state)
