"""Network interfaces: receive/send speeds from /sys/class/net statistics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Optional

from ..core import pciids
from ..core.sysroot import SysRoot
from ..core.units import format_rate
from .base import DeviceInfo, DeviceKind, Monitor, Snapshot
from .manager import Discoverer


class NetType(Enum):
    # (sidebar title, icon, sort order)
    ETHERNET = ("Ethernet Connection", "network-wired-symbolic", 0)
    WIFI = ("Wi-Fi Connection", "network-wireless-symbolic", 1)
    VPN = ("VPN", "network-vpn-symbolic", 2)
    BRIDGE = ("Network Bridge", "network-wired-symbolic", 3)
    OTHER = ("Network Interface", "network-wired-symbolic", 4)

    @property
    def title(self) -> str:
        return self.value[0]

    @property
    def icon(self) -> str:
        return self.value[1]

    @property
    def order(self) -> int:
        return self.value[2]


def uevent(sysroot: SysRoot, path: str) -> dict[str, str]:
    out = {}
    for line in (sysroot.read_text(f"{path}/uevent") or "").splitlines():
        k, _, v = line.partition("=")
        out[k] = v
    return out


def net_type(sysroot: SysRoot, iface: str) -> NetType:
    base = f"/sys/class/net/{iface}"
    devtype = uevent(sysroot, base).get("DEVTYPE", "")
    if sysroot.is_dir(f"{base}/wireless") or devtype == "wlan":
        return NetType.WIFI
    if devtype in ("wireguard", "vpn") or iface.startswith(("tun", "tap", "wg", "ppp")):
        return NetType.VPN
    if sysroot.is_dir(f"{base}/bridge") or devtype == "bridge":
        return NetType.BRIDGE
    if sysroot.read_int(f"{base}/type") == 1 and sysroot.exists(f"{base}/device"):
        return NetType.ETHERNET
    return NetType.OTHER


def is_physical(sysroot: SysRoot, iface: str) -> bool:
    return sysroot.exists(f"/sys/class/net/{iface}/device")


class NetworkDiscoverer(Discoverer):
    kind = DeviceKind.NETWORK
    rescan = True
    settings_keys = ("show-virtual-network-interfaces",)

    def __init__(self, pci: pciids.PciIds,
                 connection_name: Optional[Callable[[str], Optional[str]]] = None) -> None:
        self.pci = pci
        self.connection_name = connection_name     # e.g. NetworkManagerClient

    def discover(self, sysroot: SysRoot, settings) -> list[DeviceInfo]:
        show_virtual = settings.get("show-virtual-network-interfaces")
        found = []
        for iface in sysroot.listdir("/sys/class/net"):
            if iface == "lo" or not sysroot.is_dir(f"/sys/class/net/{iface}"):
                continue
            if not is_physical(sysroot, iface) and not show_virtual:
                continue
            kind = net_type(sysroot, iface)
            base = f"/sys/class/net/{iface}"
            props = {}
            vendor = self.pci.vendor(sysroot.read_int(f"{base}/device/vendor", 0))
            if vendor:
                props["Manufacturer"] = vendor
            driver = sysroot.link_name(f"{base}/device/driver")
            if driver:
                props["Driver Used"] = driver
            props["Interface"] = iface
            mac = sysroot.read_line(f"{base}/address")
            if mac and mac != "00:00:00:00:00:00":
                props["Hardware Address"] = mac
            found.append(DeviceInfo(f"net-{iface}", DeviceKind.NETWORK, kind.title, iface,
                                    kind.icon, props))
        return found

    def create_monitor(self, info, sysroot, settings) -> Monitor:
        return NetworkMonitor(info, sysroot, settings.get("graph-data-points"),
                              connection_name=self.connection_name)


@dataclass
class NetworkSnapshot(Snapshot):
    rx_bps: float = 0.0
    tx_bps: float = 0.0
    total_rx: int = 0
    total_tx: int = 0
    link_speed_mbps: Optional[int] = None
    network_name: Optional[str] = None

    def history_values(self):
        return {"rx": self.rx_bps, "tx": self.tx_bps}

    def history_units(self) -> Mapping[str, str]:
        return {"rx": "B/s", "tx": "B/s"}


class NetworkMonitor(Monitor):
    NAME_REFRESH_EVERY = 10   # samples between connection-name lookups

    def __init__(self, info: DeviceInfo, sysroot: SysRoot, history_points: int = 60,
                 connection_name: Optional[Callable[[str], Optional[str]]] = None) -> None:
        super().__init__(info, history_points)
        self.sysroot = sysroot
        self.iface = info.id.removeprefix("net-")
        self.connection_name = connection_name
        self._name: Optional[str] = None
        self._samples = 0
        self._prev: Optional[tuple[float, int, int]] = None
        self.history.define("rx", "B/s")
        self.history.define("tx", "B/s")

    def sort_order(self) -> int:
        return net_type(self.sysroot, self.iface).order

    def sample(self, now: float) -> Optional[NetworkSnapshot]:
        base = f"/sys/class/net/{self.iface}/statistics"
        rx = self.sysroot.read_int(f"{base}/rx_bytes")
        tx = self.sysroot.read_int(f"{base}/tx_bytes")
        if rx is None or tx is None:
            raise OSError(f"{self.iface}: no statistics")
        if self.connection_name and self._samples % self.NAME_REFRESH_EVERY == 0:
            self._name = self.connection_name(self.iface)
        self._samples += 1
        prev, self._prev = self._prev, (now, rx, tx)
        if prev is None or now <= prev[0]:
            return None
        dt = now - prev[0]
        rx_bps = max(rx - prev[1], 0) / dt
        tx_bps = max(tx - prev[2], 0) / dt
        speed = self.sysroot.read_int(f"/sys/class/net/{self.iface}/speed")
        return NetworkSnapshot(
            time=now, usage=None,
            detail_text=f"↓ {format_rate(rx_bps)} · ↑ {format_rate(tx_bps)}",
            rx_bps=rx_bps, tx_bps=tx_bps, total_rx=rx, total_tx=tx,
            link_speed_mbps=speed if speed and speed > 0 else None,
            network_name=self._name)
