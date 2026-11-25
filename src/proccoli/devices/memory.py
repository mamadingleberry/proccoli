"""Memory: RAM and swap use from /proc/meminfo. Module details (DDR type,
speed, form factor, slots) from udev's database, which any user can read;
``dmidecode -t 17`` through the privileged helper is the fallback when udev
has none."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Optional

from .. import MEMORY_ICON
from ..core.sysroot import SysRoot
from ..core.units import Base, format_bytes, format_bytes_fixed, format_percent
from .base import DeviceInfo, DeviceKind, Monitor, Snapshot
from .manager import Discoverer
from ..core.ticker import graph_points


def parse_meminfo(text: str) -> dict[str, int]:
    """Values in bytes (the file reports kB)."""
    out = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            factor = 1024 if len(parts) > 1 and parts[1] == "kB" else 1
            out[key.strip()] = int(parts[0]) * factor
    return out


# -- dmidecode ---------------------------------------------------------------------------


@dataclass
class MemoryModule:
    locator: str = ""
    size: Optional[int] = None          # bytes; None = empty slot
    form_factor: str = ""
    type: str = ""
    type_detail: str = ""
    speed: str = ""                     # e.g. "3200 MT/s"


_SIZE = re.compile(r"(\d+)\s*(kB|KB|MB|GB|TB)")
_FACTORS = {"kB": 2 ** 10, "KB": 2 ** 10, "MB": 2 ** 20, "GB": 2 ** 30, "TB": 2 ** 40}


def parse_dmidecode_memory(text: str) -> list[MemoryModule]:
    """Memory Device records from ``dmidecode -t 17``."""
    modules = []
    for block in re.split(r"\n(?=Handle )", text):
        if "\nMemory Device" not in "\n" + block.split("\n", 1)[-1]:
            continue
        fields = {}
        for line in block.splitlines():
            if line.startswith("\t") and not line.startswith("\t\t") and ":" in line:
                key, _, value = line.strip().partition(":")
                fields[key.strip()] = value.strip()
        m = _SIZE.search(fields.get("Size", ""))
        size = int(m.group(1)) * _FACTORS[m.group(2)] if m else None
        speed = fields.get("Configured Memory Speed") or fields.get("Speed", "")
        modules.append(MemoryModule(
            locator=fields.get("Locator", ""), size=size,
            form_factor=fields.get("Form Factor", ""), type=fields.get("Type", ""),
            type_detail=fields.get("Type Detail", ""),
            speed="" if speed.lower() in ("unknown", "") else speed))
    return modules


UDEV_DMI = "/run/udev/data/+dmi:id"
_UDEV_MEMORY = re.compile(r"^E:MEMORY_DEVICE_(\d+)_([A-Z_]+)=(.*)$")


def parse_udev_memory(text: str) -> list[MemoryModule]:
    """Memory devices from udev's DMI record (systemd's dmi_memory_id
    writes ``E:MEMORY_DEVICE_<n>_<FIELD>=value``), in slot order. Empty
    slots (``PRESENT=0``) have no size."""
    devices: dict[int, dict[str, str]] = {}
    for line in text.splitlines():
        m = _UDEV_MEMORY.match(line.strip())
        if m:
            devices.setdefault(int(m.group(1)), {})[m.group(2)] = m.group(3).strip()
    modules = []
    for _n, f in sorted(devices.items()):
        size = f.get("SIZE")
        present = f.get("PRESENT", "1") != "0" and size not in (None, "", "0")
        speed = f.get("CONFIGURED_SPEED_MTS") or f.get("SPEED_MTS") or ""
        modules.append(MemoryModule(
            locator=f.get("LOCATOR", ""),
            size=int(size) if present and size.isdigit() else None,
            form_factor=_known(f.get("FORM_FACTOR")), type=_known(f.get("TYPE")),
            type_detail=_known(f.get("TYPE_DETAIL")),
            speed=f"{speed} MT/s" if speed.isdigit() and speed != "0" else ""))
    return modules


def _known(value: Optional[str]) -> str:
    return "" if not value or value in ("Unknown", "Other", "None", "Not Specified") else value


def memory_type(modules: Optional[list[MemoryModule]]) -> str:
    """The installed modules' type, e.g. "DDR4" (or "DDR4, DDR5")."""
    types = sorted({m.type for m in modules or [] if m.size and m.type})
    return ", ".join(types)


def memory_speed(modules: Optional[list[MemoryModule]]) -> str:
    """The speed the memory runs at, e.g. "2667 MT/s": the slowest
    installed module's (mixed modules all run at that)."""
    speeds = []
    for m in modules or []:
        match = re.match(r"(\d+)\s*(.*)", m.speed) if m.size else None
        if match:
            speeds.append((int(match.group(1)), match.group(2).strip() or "MT/s"))
    if not speeds:
        return ""
    value, unit = min(speeds)
    return f"{value} {unit}"


def memory_description(total: Optional[int], modules: Optional[list[MemoryModule]],
                       base: Base) -> str:
    """The sidebar description: "16.0 GB DDR4 @ 2667 MT/s" (parts left out
    when unknown)."""
    text = " ".join(p for p in (format_bytes_fixed(total, base, 1) if total else "",
                                memory_type(modules)) if p)
    speed = memory_speed(modules)
    return f"{text} @ {speed}" if text and speed else text or speed


def summarize_modules(modules: list[MemoryModule]) -> dict[str, str]:
    """Properties for the page, like Resources: Slots Used, Speed, ..."""
    used = [m for m in modules if m.size]
    if not modules:
        return {}

    def joined(attr):
        values = sorted({getattr(m, attr) for m in used if getattr(m, attr)
                         and getattr(m, attr) not in ("Unknown", "None")})
        return ", ".join(values)

    props = {"Slots Used": f"{len(used)} of {len(modules)}"}
    for key, attr in (("Speed", "speed"), ("Form Factor", "form_factor"),
                      ("Type", "type"), ("Type Detail", "type_detail")):
        if joined(attr):
            props[key] = joined(attr)
    return props


# -- discovery and monitoring ---------------------------------------------------------------


class MemoryDiscoverer(Discoverer):
    kind = DeviceKind.MEMORY

    def discover(self, sysroot: SysRoot, settings) -> list[DeviceInfo]:
        info = parse_meminfo(sysroot.read_text("/proc/meminfo") or "")
        total = info.get("MemTotal")
        self._modules = parse_udev_memory(sysroot.read_text(UDEV_DMI) or "") or None
        # "16.0 GB DDR4 @ 2667 MT/s", as the Processor shows its model.
        return [DeviceInfo("memory", DeviceKind.MEMORY, "Memory",
                           memory_description(total, self._modules,
                                              Base(settings.get("base"))), MEMORY_ICON)]

    def create_monitor(self, info, sysroot, settings) -> Monitor:
        monitor = MemoryMonitor(info, sysroot, graph_points(settings))
        monitor.modules = getattr(self, "_modules", None)
        return monitor


@dataclass
class MemorySnapshot(Snapshot):
    total: int = 0
    used: int = 0
    available: int = 0
    swap_total: int = 0
    swap_used: int = 0

    @property
    def swap_usage(self) -> Optional[float]:
        return 100.0 * self.swap_used / self.swap_total if self.swap_total else None

    def history_values(self):
        return {"usage": self.usage, "swap": self.swap_usage}

    def stats_values(self):
        return {**self.history_values(), "used": self.used, "total": self.total,
                "swap-used": self.swap_used, "swap-total": self.swap_total}

    def stats_units(self):
        return {**self.history_units(), "used": "B", "total": "B",
                "swap-used": "B", "swap-total": "B"}

    def history_units(self) -> Mapping[str, str]:
        return {"usage": "%", "swap": "%"}


class MemoryMonitor(Monitor):
    def __init__(self, info: DeviceInfo, sysroot: SysRoot, history_points: int = 60) -> None:
        super().__init__(info, history_points)
        self.sysroot = sysroot
        # From udev at discovery, or from dmidecode after authenticating.
        self.modules: Optional[list[MemoryModule]] = None
        self.history.define("usage", "%")
        self.history.define("swap", "%")

    def describe(self, encode) -> dict:
        """The memory modules too, once known."""
        out = super().describe(encode)
        if self.modules is not None:
            out["memory_modules"] = encode(self.modules)
        return out

    def described_properties(self) -> dict[str, str]:
        """The memory modules' summary, once read (udev or administrator
        rights): the Memory page's *Properties*."""
        modules = summarize_modules(self.modules or [])
        return {**super().described_properties(), **{k: v for k, v in modules.items() if v}}

    def sample(self, now: float) -> MemorySnapshot:
        mi = parse_meminfo(self.sysroot.read_text("/proc/meminfo") or "")
        total = mi.get("MemTotal")
        if not total:
            raise OSError("/proc/meminfo has no MemTotal")
        available = mi.get("MemAvailable", mi.get("MemFree", 0))
        used = max(total - available, 0)
        swap_total = mi.get("SwapTotal", 0)
        swap_used = max(swap_total - mi.get("SwapFree", 0), 0)
        usage = 100.0 * used / total
        return MemorySnapshot(
            time=now, usage=usage, usage_text=format_percent(usage),
            detail_text=f"{format_bytes(used)} / {format_bytes(total)}",
            total=total, used=used, available=available,
            swap_total=swap_total, swap_used=swap_used)
