"""GPU discovery from /sys/class/drm."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..core import pciids
from ..core.sysroot import SysRoot


class GpuVendor(Enum):
    INTEL = 0x8086
    AMD = 0x1002
    NVIDIA = 0x10DE
    OTHER = 0

    @classmethod
    def from_id(cls, vendor_id: Optional[int]) -> "GpuVendor":
        for v in cls:
            if v.value == vendor_id:
                return v
        return cls.OTHER

    @property
    def short_name(self) -> str:
        return {"INTEL": "Intel", "AMD": "AMD", "NVIDIA": "NVIDIA"}.get(self.name, "")


@dataclass(frozen=True)
class GpuInfo:
    card: str                         # "card1"
    pci_slot: str                     # "0000:00:02.0"
    vendor: GpuVendor
    vendor_id: int
    device_id: int
    driver: str                       # "i915", "xe", "amdgpu", "nvidia", ...
    name: str                         # "Intel UHD Graphics"
    integrated: bool
    render_node: Optional[str] = None  # "renderD128"
    properties: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def sysfs(self) -> str:
        return f"/sys/class/drm/{self.card}"

    @property
    def device_path(self) -> str:
        return f"/sys/class/drm/{self.card}/device"


def pretty_name(vendor: GpuVendor, vendor_name: Optional[str],
                device_name: Optional[str]) -> str:
    """"Alder Lake-P GT1 [UHD Graphics]" -> "Intel UHD Graphics"."""
    prefix = vendor.short_name or (vendor_name or "").split(" ")[0]
    if device_name:
        m = re.search(r"\[(.+)\]", device_name)
        model = m.group(1) if m else device_name
        if prefix and not model.startswith(prefix):
            model = f"{prefix} {model}"
        return model
    return f"{prefix} GPU".strip() if prefix else "GPU"


def _uevent(sysroot: SysRoot, path: str) -> dict[str, str]:
    out = {}
    for line in (sysroot.read_text(f"{path}/uevent") or "").splitlines():
        k, _, v = line.partition("=")
        out[k] = v
    return out


def discover_gpus(sysroot: SysRoot, pci: pciids.PciIds) -> list[GpuInfo]:
    gpus = []
    for card in sysroot.listdir("/sys/class/drm"):
        if not re.fullmatch(r"card\d+", card):
            continue
        dev = f"/sys/class/drm/{card}/device"
        vendor_id = sysroot.read_int(f"{dev}/vendor", 0)
        device_id = sysroot.read_int(f"{dev}/device", 0)
        if vendor_id is None:
            continue           # not a PCI GPU (e.g. a USB display adapter)
        ue = _uevent(sysroot, dev)
        slot = ue.get("PCI_SLOT_NAME", card)
        driver = ue.get("DRIVER") or sysroot.link_name(f"{dev}/driver") or ""
        vendor = GpuVendor.from_id(vendor_id)
        render = next((n for n in sysroot.listdir(f"{dev}/drm") if n.startswith("renderD")),
                      None)
        vram_total = sysroot.read_int(f"{dev}/mem_info_vram_total")
        if vendor == GpuVendor.INTEL:
            integrated = slot.endswith("00:02.0")        # Intel iGPUs live at 00:02.0
        elif vendor == GpuVendor.AMD:
            integrated = vram_total is not None and vram_total < 2 * 2 ** 30  # APU carve-out
        else:
            integrated = False
        props = {}
        vendor_name = pci.vendor(vendor_id)
        if vendor_name:
            props["Manufacturer"] = vendor_name
        props["PCI Slot"] = slot
        if driver:
            props["Driver Used"] = driver
        speed = sysroot.read_line(f"{dev}/current_link_speed")
        width = sysroot.read_line(f"{dev}/current_link_width")
        if speed and width and not speed.startswith("Unknown") and width != "0":
            props["Link"] = f"{speed} x{width}"
        gpus.append(GpuInfo(card, slot, vendor, vendor_id, device_id, driver,
                            pretty_name(vendor, vendor_name, pci.device(vendor_id, device_id)),
                            integrated, render, props))
    return gpus
