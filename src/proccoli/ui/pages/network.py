"""Network page: receive and send speeds, totals, interface properties."""

from __future__ import annotations

from ...core.units import format_bytes, format_rate
from ...devices.network import NetworkMonitor, NetworkSnapshot
from ..page import PageKind
from ..widgets.info_row import InfoRow
from .device import DevicePage


class NetworkPage(DevicePage):
    RATES_IN_BITS = True             # the hover box follows the bits preference

    def __init__(self, monitor: NetworkMonitor, settings) -> None:
        super().__init__(monitor, settings, PageKind.NETWORK)
        usage = self.add_group("Usage")
        self.receiving = self.graph_box(usage, "Receiving", [("rx", "B/s")],
                                        max_value=None, min_max=1e5)
        self.sending = self.graph_box(usage, "Sending", [("tx", "B/s")],
                                      max_value=None, min_max=1e5, color_offset=1)
        self.total_rx = InfoRow("Total Received")
        self.total_tx = InfoRow("Total Sent")
        usage.add(self.total_rx)
        usage.add(self.total_tx)
        self.add_properties({**monitor.info.properties, "Network Name": "",
                             "Link Speed": ""})

    def _rate(self, bps: float) -> str:
        return format_rate(bps, self.base, bits=self.network_bits)

    def update_labels(self, snap: NetworkSnapshot) -> None:
        self.receiving.set_info(self._rate(snap.rx_bps))
        self.sending.set_info(self._rate(snap.tx_bps))
        self.total_rx.set_value(format_bytes(snap.total_rx, self.base))
        self.total_tx.set_value(format_bytes(snap.total_tx, self.base))
        self.property_rows["Network Name"].set_value(snap.network_name)
        self.property_rows["Link Speed"].set_value(
            f"{snap.link_speed_mbps} Mbit/s" if snap.link_speed_mbps else None)
