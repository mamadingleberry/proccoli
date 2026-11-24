"""Vendor and device names from the system's PCI ID database (``pci.ids``,
from the hwdata / pciutils package)."""

from __future__ import annotations

import functools
import os
from typing import Optional

DEFAULT_PATHS = ("/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids")


class PciIds:
    def __init__(self, vendors: dict[int, str], devices: dict[tuple[int, int], str]) -> None:
        self.vendors = vendors
        self.devices = devices

    @classmethod
    def parse(cls, text: str) -> "PciIds":
        vendors, devices = {}, {}
        vendor = None
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            if line.startswith("C "):        # device classes: end of the vendor list
                break
            if line.startswith("\t\t"):      # subsystems: not needed
                continue
            if line.startswith("\t"):
                if vendor is not None:
                    dev_id, _, name = line.strip().partition(" ")
                    devices[(vendor, int(dev_id, 16))] = name.strip()
                continue
            vid, _, name = line.partition(" ")
            try:
                vendor = int(vid, 16)
            except ValueError:
                vendor = None
                continue
            vendors[vendor] = name.strip()
        return cls(vendors, devices)

    def vendor(self, vendor_id: Optional[int]) -> Optional[str]:
        return self.vendors.get(vendor_id) if vendor_id is not None else None

    def device(self, vendor_id: Optional[int], device_id: Optional[int]) -> Optional[str]:
        if vendor_id is None or device_id is None:
            return None
        return self.devices.get((vendor_id, device_id))


class OnDemandPciIds:
    """The same lookups as ``PciIds``, without parsing the whole file
    (about 3.6 MB of Python objects): each vendor's block is scanned for
    when first asked, and only the answers are kept (lightweight mode)."""

    def __init__(self, path: Optional[str]) -> None:
        self.path = path
        self._vendors: dict[int, Optional[str]] = {}
        self._devices: dict[tuple[int, int], Optional[str]] = {}

    def _scan(self, vendor_id: int, device_id: Optional[int] = None) -> None:
        self._vendors.setdefault(vendor_id, None)
        if device_id is not None:
            self._devices.setdefault((vendor_id, device_id), None)
        if not self.path:
            return
        wanted = f"{vendor_id:04x} "
        dev = f"\t{device_id:04x} " if device_id is not None else None
        with open(self.path, encoding="utf-8", errors="replace") as fh:
            inside = False
            for line in fh:
                if line.startswith("C "):
                    return
                if not line.startswith("\t") and not line.startswith("#"):
                    if inside:
                        return                  # the next vendor: done
                    if line.startswith(wanted):
                        self._vendors[vendor_id] = line[5:].strip()
                        inside = True
                        if dev is None:
                            return
                elif inside and dev is not None and line.startswith(dev):
                    self._devices[(vendor_id, device_id)] = line[len(dev):].strip()
                    return

    def vendor(self, vendor_id: Optional[int]) -> Optional[str]:
        if vendor_id is None:
            return None
        if vendor_id not in self._vendors:
            self._scan(vendor_id)
        return self._vendors[vendor_id]

    def device(self, vendor_id: Optional[int], device_id: Optional[int]) -> Optional[str]:
        if vendor_id is None or device_id is None:
            return None
        if (vendor_id, device_id) not in self._devices:
            self._scan(vendor_id, device_id)
        return self._devices[(vendor_id, device_id)]


def find(path: Optional[str] = None) -> Optional[str]:
    for p in ([path] if path else DEFAULT_PATHS):
        if p and os.path.isfile(p):
            return p
    return None


def on_demand(path: Optional[str] = None) -> OnDemandPciIds:
    return OnDemandPciIds(find(path))


@functools.lru_cache(maxsize=4)
def load(path: Optional[str] = None) -> PciIds:
    """The parsed database (cached), or an empty one if none is installed."""
    for p in ([path] if path else DEFAULT_PATHS):
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                return PciIds.parse(fh.read())
    return PciIds({}, {})
