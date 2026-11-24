"""Processor: usage (total and per logical CPU), frequency, temperature."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Optional

from .. import PROCESSOR_ICON
from ..core.sysroot import SysRoot
from ..core.units import format_duration, format_frequency, format_percent
from .base import DeviceInfo, DeviceKind, Monitor, Snapshot
from .manager import Discoverer

# -- parsing (pure, unit-tested) -------------------------------------------------------


def parse_proc_stat(text: str) -> dict[str, list[int]]:
    """``{"cpu": [...], "cpu0": [...], ...}`` jiffy counters from /proc/stat."""
    out = {}
    for line in text.splitlines():
        if line.startswith("cpu"):
            name, *fields = line.split()
            out[name] = [int(f) for f in fields]
    return out


def busy_percent(prev: list[int], cur: list[int]) -> Optional[float]:
    """Busy share between two /proc/stat samples of one CPU line.

    Fields: user nice system idle iowait irq softirq steal (guest time is
    already counted in user, so it's left out)."""
    def split(f):
        f = (f + [0] * 8)[:8]
        idle = f[3] + f[4]
        return sum(f), idle
    total0, idle0 = split(prev)
    total1, idle1 = split(cur)
    dt = total1 - total0
    if dt <= 0:
        return None
    return min(max(100.0 * (dt - (idle1 - idle0)) / dt, 0.0), 100.0)


def parse_cpuinfo(text: str) -> list[dict[str, str]]:
    cpus, cur = [], {}
    for line in text.splitlines():
        if not line.strip():
            if cur:
                cpus.append(cur)
                cur = {}
            continue
        key, _, value = line.partition(":")
        cur[key.strip()] = value.strip()
    if cur:
        cpus.append(cur)
    return [c for c in cpus if "processor" in c]


def cpu_model(cpuinfo: list[dict[str, str]]) -> str:
    for c in cpuinfo:
        for key in ("model name", "Model", "Hardware", "cpu model"):
            if c.get(key):
                return re.sub(r"\s+", " ", c[key])
    return "Processor"


# Which hwmon chip and label hold the package temperature, by driver.
_TEMP_SENSORS = [
    ("coretemp", ("Package id 0",)),
    ("k10temp", ("Tctl", "Tdie")),
    ("zenpower", ("Tdie", "Tctl")),
    ("cpu_thermal", ()),   # many ARM boards: first sensor
]


def find_temperature_input(sysroot: SysRoot) -> Optional[str]:
    """Path of the hwmon ``temp*_input`` with the CPU package temperature."""
    hwmons = {d: sysroot.read_line(f"/sys/class/hwmon/{d}/name")
              for d in sysroot.listdir("/sys/class/hwmon")}
    for driver, labels in _TEMP_SENSORS:
        for d, name in hwmons.items():
            if name != driver:
                continue
            base = f"/sys/class/hwmon/{d}"
            inputs = sorted((f for f in sysroot.listdir(base)
                             if re.fullmatch(r"temp\d+_input", f)),
                            key=lambda f: int(re.sub(r"\D", "", f)))
            for f in inputs:
                label = sysroot.read_line(f"{base}/{f.replace('_input', '_label')}")
                if not labels or label in labels:
                    return f"{base}/{f}"
            if inputs:
                return f"{base}/{inputs[0]}"
    return None


# -- discovery ------------------------------------------------------------------------------


class CpuDiscoverer(Discoverer):
    kind = DeviceKind.CPU

    def __init__(self, machine: str) -> None:
        self.machine = machine          # e.g. System.machine(): "x86_64"

    def discover(self, sysroot: SysRoot, settings) -> list[DeviceInfo]:
        cpuinfo = parse_cpuinfo(sysroot.read_text("/proc/cpuinfo") or "")
        stat = parse_proc_stat(sysroot.read_text("/proc/stat") or "")
        logical = sum(1 for k in stat if k != "cpu") or len(cpuinfo)
        props: dict[str, str] = {}

        max_khz = [sysroot.read_int(f"/sys/devices/system/cpu/{c}/cpufreq/cpuinfo_max_freq")
                   for c in sysroot.listdir("/sys/devices/system/cpu")
                   if re.fullmatch(r"cpu\d+", c)]
        max_khz = [k for k in max_khz if k]
        if max_khz:
            props["Max Frequency"] = format_frequency(max(max_khz) * 1000)
        props["Logical Cores"] = str(logical)
        cores = {(c.get("physical id", "0"), c.get("core id")) for c in cpuinfo
                 if c.get("core id") is not None}
        if cores:
            props["Physical Cores"] = str(len(cores))
        sockets = {c.get("physical id") for c in cpuinfo if c.get("physical id") is not None}
        if sockets:
            props["Sockets"] = str(len(sockets))
        flags = set((cpuinfo[0].get("flags", "") if cpuinfo else "").split())
        if "vmx" in flags:
            props["Virtualization"] = "Intel VT-x"
        elif "svm" in flags:
            props["Virtualization"] = "AMD-V"
        props["Architecture"] = self.machine
        return [DeviceInfo("cpu", DeviceKind.CPU, "Processor", cpu_model(cpuinfo),
                           PROCESSOR_ICON, props)]

    def create_monitor(self, info, sysroot, settings) -> Monitor:
        return CpuMonitor(info, sysroot, settings.get("graph-data-points"))


# -- monitoring --------------------------------------------------------------------------------


@dataclass
class CpuSnapshot(Snapshot):
    per_thread: list[Optional[float]] = field(default_factory=list)
    frequency_hz: Optional[float] = None
    temperature_c: Optional[float] = None
    uptime_s: Optional[float] = None

    def history_values(self):
        values = {"usage": self.usage, "temperature": self.temperature_c}
        for i, v in enumerate(self.per_thread):
            values[f"cpu{i}"] = v
        return values

    def history_units(self) -> Mapping[str, str]:
        units = {"usage": "%", "temperature": "°C"}
        units.update({f"cpu{i}": "%" for i in range(len(self.per_thread))})
        return units


class CpuMonitor(Monitor):
    def __init__(self, info: DeviceInfo, sysroot: SysRoot, history_points: int = 60) -> None:
        super().__init__(info, history_points)
        self.sysroot = sysroot
        self.temperature_path = find_temperature_input(sysroot)
        self._prev: Optional[dict[str, list[int]]] = None
        self.history.define("usage", "%")
        self.history.define("temperature", "°C")

    def thread_names(self) -> list[str]:
        prev = self._prev or {}
        return sorted((k for k in prev if k != "cpu"), key=lambda k: int(k[3:]))

    def sample(self, now: float) -> Optional[CpuSnapshot]:
        stat = parse_proc_stat(self.sysroot.read_text("/proc/stat") or "")
        if "cpu" not in stat:
            raise OSError("/proc/stat has no cpu line")
        prev, self._prev = self._prev, stat
        if prev is None:
            return None  # usage needs two samples
        total = busy_percent(prev["cpu"], stat["cpu"])
        threads = self.thread_names()
        per_thread = [busy_percent(prev[t], stat[t]) if t in prev else None
                      for t in threads]

        freqs = [self.sysroot.read_int(f"/sys/devices/system/cpu/{t}/cpufreq/scaling_cur_freq")
                 for t in threads]
        freqs = [f for f in freqs if f]
        freq = sum(freqs) / len(freqs) * 1000 if freqs else None
        temp = None
        if self.temperature_path:
            milli = self.sysroot.read_int(self.temperature_path)
            temp = milli / 1000 if milli is not None else None
        uptime_line = self.sysroot.read_line("/proc/uptime")
        uptime = float(uptime_line.split()[0]) if uptime_line else None

        return CpuSnapshot(
            time=now, usage=total, usage_text=format_percent(total),
            detail_text=format_frequency(freq) if freq else "",
            per_thread=per_thread, frequency_hz=freq, temperature_c=temp,
            uptime_s=uptime)

    @staticmethod
    def uptime_text(snapshot: CpuSnapshot) -> Optional[str]:
        return format_duration(snapshot.uptime_s) if snapshot.uptime_s is not None else None
