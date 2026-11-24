"""Drives: busy time and read/write speeds from /sys/block/<dev>/stat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from ..core.sysroot import SysRoot
from ..core.units import Base, format_bytes, format_percent, format_rate
from .base import DeviceInfo, DeviceKind, Monitor, Snapshot
from .manager import Discoverer

SECTOR = 512                       # /sys/block counts 512-byte sectors, always
IGNORED = ("loop", "ram", "zram", "fd")
VIRTUAL = ("dm-", "md", "zd", "nbd", "drbd", "rbd")
# SCSI vendor strings that only name the bus, not the maker.
GENERIC_VENDORS = {"ATA", "ATAPI", "USB", "Generic", "Generic-", ""}


def is_virtual(name: str) -> bool:
    return name.startswith(VIRTUAL)


def drive_type(sysroot: SysRoot, name: str) -> tuple[str, str]:
    """(type label, icon name) for a block device."""
    base = f"/sys/block/{name}"
    if is_virtual(name):
        return "Virtual Drive", "drive-multidisk-symbolic"
    if name.startswith("sr"):
        return "Optical Drive", "media-optical-symbolic"
    if name.startswith("mmcblk"):
        return "Memory Card", "media-flash-symbolic"
    if name.startswith("nvme"):
        return "NVMe Drive", "drive-harddisk-solidstate-symbolic"
    link = sysroot.readlink(base) or ""
    if sysroot.read_int(f"{base}/removable") == 1 or "/usb" in link:
        return "Removable Drive", "drive-removable-media-symbolic"
    if sysroot.read_int(f"{base}/queue/rotational") == 1:
        return "Hard Disk Drive", "drive-harddisk-symbolic"
    return "Solid State Drive", "drive-harddisk-solidstate-symbolic"


def parse_disk_stat(text: str) -> Optional[tuple[int, int, int]]:
    """(sectors read, sectors written, io_ticks ms) from a block stat file."""
    f = text.split()
    if len(f) < 10:
        return None
    return int(f[2]), int(f[6]), int(f[9])


class DriveDiscoverer(Discoverer):
    kind = DeviceKind.DRIVE
    rescan = True
    settings_keys = ("show-virtual-drives",)

    def discover(self, sysroot: SysRoot, settings) -> list[DeviceInfo]:
        show_virtual = settings.get("show-virtual-drives")
        base = Base(settings.get("base"))
        found = []
        for name in sysroot.listdir("/sys/block"):
            if name.startswith(IGNORED) or (is_virtual(name) and not show_virtual):
                continue
            path = f"/sys/block/{name}"
            sectors = sysroot.read_int(f"{path}/size") or 0
            if sectors == 0:            # empty card reader, ejected disc
                continue
            label, icon = drive_type(sysroot, name)
            vendor = (sysroot.read_line(f"{path}/device/vendor") or "").strip()
            if vendor in GENERIC_VENDORS:
                vendor = ""
            model = " ".join(filter(None, (vendor, sysroot.read_line(f"{path}/device/model"))))
            if not model and is_virtual(name):
                model = sysroot.read_line(f"{path}/dm/name") or ""
            props = {"Type": label, "Device": f"/dev/{name}",
                     "Capacity": format_bytes(sectors * SECTOR, base),
                     "Writable": "No" if sysroot.read_int(f"{path}/ro") == 1 else "Yes",
                     "Removable": "Yes" if sysroot.read_int(f"{path}/removable") == 1 else "No"}
            if model:
                props["Model"] = model
            found.append(DeviceInfo(f"drive-{name}", DeviceKind.DRIVE, label,
                                    model or name, icon, props))
        return found

    def create_monitor(self, info, sysroot, settings) -> Monitor:
        return DriveMonitor(info, sysroot, settings.get("graph-data-points"))


@dataclass
class DriveSnapshot(Snapshot):
    read_bps: float = 0.0
    write_bps: float = 0.0
    total_read: int = 0
    total_written: int = 0

    def history_values(self):
        return {"usage": self.usage, "read": self.read_bps, "write": self.write_bps}

    def history_units(self) -> Mapping[str, str]:
        return {"usage": "%", "read": "B/s", "write": "B/s"}


class DriveMonitor(Monitor):
    def __init__(self, info: DeviceInfo, sysroot: SysRoot, history_points: int = 60) -> None:
        super().__init__(info, history_points)
        self.sysroot = sysroot
        self.block = info.id.removeprefix("drive-")
        self._prev: Optional[tuple[float, tuple[int, int, int]]] = None
        for name, unit in (("usage", "%"), ("read", "B/s"), ("write", "B/s")):
            self.history.define(name, unit)

    def sample(self, now: float) -> Optional[DriveSnapshot]:
        stat = parse_disk_stat(self.sysroot.read_text(f"/sys/block/{self.block}/stat") or "")
        if stat is None:
            raise OSError(f"{self.block}: no block statistics")
        prev, self._prev = self._prev, (now, stat)
        if prev is None or now <= prev[0]:
            return None
        dt = now - prev[0]
        (r0, w0, t0), (r1, w1, t1) = prev[1], stat
        busy = min(max(100.0 * (t1 - t0) / (dt * 1000), 0.0), 100.0)
        read = max(r1 - r0, 0) * SECTOR / dt
        write = max(w1 - w0, 0) * SECTOR / dt
        return DriveSnapshot(
            time=now, usage=busy, usage_text=format_percent(busy),
            detail_text=f"R {format_rate(read)} · W {format_rate(write)}",
            read_bps=read, write_bps=write,
            total_read=r1 * SECTOR, total_written=w1 * SECTOR)
