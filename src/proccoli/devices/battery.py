"""Batteries, from /sys/class/power_supply (type "Battery")."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from ..core.sysroot import SysRoot
from ..core.units import format_percent, format_power
from .base import DeviceInfo, DeviceKind, Monitor, Snapshot
from .manager import Discoverer

BASE = "/sys/class/power_supply"


def _read(sysroot: SysRoot, name: str, attr: str) -> Optional[int]:
    return sysroot.read_int(f"{BASE}/{name}/{attr}")


def energy_wh(sysroot: SysRoot, name: str, kind: str) -> Optional[float]:
    """``kind`` "full", "full_design" or "now", in Wh. Batteries report
    energy (µWh) or charge (µAh, times the design voltage in µV)."""
    uwh = _read(sysroot, name, f"energy_{kind}")
    if uwh is not None:
        return uwh / 1e6
    uah = _read(sysroot, name, f"charge_{kind}")
    uv = _read(sysroot, name, "voltage_min_design") or _read(sysroot, name, "voltage_now")
    if uah is not None and uv:
        return uah * uv / 1e12
    return None


def power_watts(sysroot: SysRoot, name: str) -> Optional[float]:
    uw = _read(sysroot, name, "power_now")
    if uw is not None:
        return abs(uw) / 1e6
    ua = _read(sysroot, name, "current_now")
    uv = _read(sysroot, name, "voltage_now")
    if ua is not None and uv:
        return abs(ua) * uv / 1e12
    return None


class BatteryDiscoverer(Discoverer):
    kind = DeviceKind.BATTERY
    rescan = True          # batteries can be removed (and some docks add one)

    def discover(self, sysroot: SysRoot, settings) -> list[DeviceInfo]:
        found = []
        for name in sysroot.listdir(BASE):
            if sysroot.read_line(f"{BASE}/{name}/type") != "Battery":
                continue
            if sysroot.read_line(f"{BASE}/{name}/scope") == "Device":
                continue       # a mouse or headset battery, not the system's
            if _read(sysroot, name, "present") == 0:
                continue
            props = {}
            full, design = energy_wh(sysroot, name, "full"), energy_wh(sysroot, name, "full_design")
            if full and design:
                props["Battery Health"] = format_percent(100.0 * full / design)
            if design:
                props["Design Capacity"] = f"{design:.1f} Wh"
            cycles = _read(sysroot, name, "cycle_count")
            if cycles:
                props["Charge Cycles"] = str(cycles)
            for key, attr in (("Technology", "technology"), ("Manufacturer", "manufacturer"),
                              ("Model Name", "model_name")):
                value = sysroot.read_line(f"{BASE}/{name}/{attr}")
                if value and value != "Unknown":
                    props[key] = value
            props["Device"] = name
            found.append(DeviceInfo(f"battery-{name}", DeviceKind.BATTERY, "Battery",
                                    props.get("Model Name", name), "battery-symbolic", props))
        return found

    def create_monitor(self, info, sysroot, settings) -> Monitor:
        return BatteryMonitor(info, sysroot, settings.get("graph-data-points"))


@dataclass
class BatterySnapshot(Snapshot):
    charge: Optional[float] = None
    power_w: Optional[float] = None
    state: str = ""

    def history_values(self):
        return {"usage": self.charge, "power": self.power_w}

    def history_units(self) -> Mapping[str, str]:
        return {"usage": "%", "power": "W"}


class BatteryMonitor(Monitor):
    def __init__(self, info: DeviceInfo, sysroot: SysRoot, history_points: int = 60) -> None:
        super().__init__(info, history_points)
        self.sysroot = sysroot
        self.name = info.id.removeprefix("battery-")
        self.history.define("usage", "%")
        self.history.define("power", "W")

    def sample(self, now: float) -> BatterySnapshot:
        charge = _read(self.sysroot, self.name, "capacity")
        if charge is None:
            e_now = energy_wh(self.sysroot, self.name, "now")
            e_full = energy_wh(self.sysroot, self.name, "full")
            charge = round(100 * e_now / e_full) if e_now is not None and e_full else None
        if charge is None:
            raise OSError(f"{self.name}: no charge level")
        state = self.sysroot.read_line(f"{BASE}/{self.name}/status") or "Unknown"
        power = power_watts(self.sysroot, self.name)
        detail = state if power is None or state == "Full" else f"{state} · {format_power(power)}"
        return BatterySnapshot(time=now, usage=float(charge), usage_text=format_percent(charge),
                               detail_text=detail, charge=float(charge), power_w=power,
                               state=state)
