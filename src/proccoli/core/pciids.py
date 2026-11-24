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


@functools.lru_cache(maxsize=4)
def load(path: Optional[str] = None) -> PciIds:
    """The parsed database (cached), or an empty one if none is installed."""
    for p in ([path] if path else DEFAULT_PATHS):
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                return PciIds.parse(fh.read())
    return PciIds({}, {})
