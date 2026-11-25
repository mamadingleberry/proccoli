"""Running and reading NVIDIA's tools (pure: argv builders and parsers).

**nvidia-settings** talks to the GPU through the NV-CONTROL X extension, so
it works only in an X11 session on NVIDIA's driver. Two steps:

1. ``settings_targets_argv``: which ``[gpu:N]`` target is which PCI slot
   (``PCIDomain``/``PCIBus``/``PCIDevice``/``PCIFunc``, normal output:
   ``Attribute 'PCIBus' (host:0[gpu:0]): 2.``).
2. ``settings_argv``: the readings of that target, terse (``-t``): one value
   per line, in the order asked.

On Wayland (Ubuntu's default) step 1 answers "No targets match", and the
backend falls back to **nvidia-smi**, which reads the driver directly:
``smi_argv`` asks for ``SMI_FIELDS`` as CSV for one PCI slot.

Values come back as ``NvidiaSample``; anything a tool doesn't report (or
reports as ``[N/A]``) is None.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..backend import GpuSummary

MIB = 1024 * 1024


class NvidiaError(Exception):
    """A tool answered, but not with readings. ``unreachable``: this tool
    can't see the GPU at all (try the other one)."""

    def __init__(self, message: str, unreachable: bool = False) -> None:
        super().__init__(message)
        self.unreachable = unreachable


@dataclass
class NvidiaSample:
    tool: str
    name: Optional[str] = None
    driver: Optional[str] = None
    usage: Optional[float] = None            # graphics engine, %
    memory_util: Optional[float] = None      # memory controller, %
    encoder: Optional[float] = None          # %
    decoder: Optional[float] = None          # %
    video: Optional[float] = None            # one video engine figure (nvidia-settings)
    pcie: Optional[float] = None             # PCIe bandwidth, %
    vram_used: Optional[int] = None          # bytes
    vram_total: Optional[int] = None
    temperature_c: Optional[float] = None
    power_w: Optional[float] = None
    power_limit_w: Optional[float] = None
    clock_hz: Optional[float] = None
    memory_clock_hz: Optional[float] = None
    fan: Optional[float] = None              # %
    pstate: Optional[str] = None             # P0 (fastest) … P12

    @property
    def vram_percent(self) -> Optional[float]:
        if self.vram_used is None or not self.vram_total:
            return None
        return 100.0 * self.vram_used / self.vram_total

    def to_summary(self) -> GpuSummary:
        """The Resources-level figures (the GPU's Overview tab and sidebar)."""
        combined = self.encoder is None and self.decoder is None and self.video is not None
        return GpuSummary(
            usage=self.usage,
            encode=self.video if combined else self.encoder,
            decode=self.video if combined else self.decoder,
            combined_video=combined,
            vram_used=self.vram_used, vram_total=self.vram_total,
            frequency_hz=self.clock_hz, vram_frequency_hz=self.memory_clock_hz,
            power_w=self.power_w, power_cap_w=self.power_limit_w,
            temperature_c=self.temperature_c)

    def history_values(self) -> dict[str, Optional[float]]:
        """For the Details tab's graphs (``HISTORY_UNITS`` names)."""
        return {"graphics": self.usage, "memory-controller": self.memory_util,
                "encoder": self.encoder if self.encoder is not None else self.video,
                "decoder": self.decoder if self.decoder is not None else self.video,
                "pcie": self.pcie, "vram": self.vram_percent,
                "temperature": self.temperature_c, "power": self.power_w,
                "clock": self.clock_hz, "memory-clock": self.memory_clock_hz,
                "fan": self.fan}


HISTORY_UNITS = {"graphics": "%", "memory-controller": "%", "encoder": "%", "decoder": "%",
                 "pcie": "%", "vram": "%", "temperature": "°C", "power": "W",
                 "clock": "Hz", "memory-clock": "Hz", "fan": "%"}   # base units


def _number(text: str) -> Optional[float]:
    text = text.strip()
    if not text or text.startswith("[") or text.upper() in ("N/A", "NOT SUPPORTED"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _text(text: str) -> Optional[str]:
    text = text.strip()
    return None if not text or text.startswith("[") else text


# -- nvidia-smi -----------------------------------------------------------------------------

SMI_FIELDS = ("name", "driver_version", "utilization.gpu", "utilization.memory",
              "utilization.encoder", "utilization.decoder", "memory.used", "memory.total",
              "temperature.gpu", "power.draw", "power.limit", "clocks.gr", "clocks.mem",
              "fan.speed", "pstate")


def smi_argv(binary: str, pci_slot: str) -> list[str]:
    return [binary, f"--query-gpu={','.join(SMI_FIELDS)}",
            "--format=csv,noheader,nounits", "-i", pci_slot]


def parse_smi(rc: int, out: str, err: str) -> NvidiaSample:
    """One CSV line in ``SMI_FIELDS`` order."""
    if rc != 0:
        message = (err or out).strip() or f"nvidia-smi exited with status {rc}"
        # 6: no such device; 9: the driver isn't loaded.
        raise NvidiaError(message, unreachable=rc in (6, 9))
    line = next((l for l in out.splitlines() if l.strip()), "")
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != len(SMI_FIELDS):
        raise NvidiaError(f"unexpected nvidia-smi output: {line!r}")
    v = dict(zip(SMI_FIELDS, parts))

    def mib(key):
        n = _number(v[key])
        return None if n is None else int(n * MIB)

    def mhz(key):
        n = _number(v[key])
        return None if n is None else n * 1e6
    return NvidiaSample(
        tool="nvidia-smi", name=_text(v["name"]), driver=_text(v["driver_version"]),
        usage=_number(v["utilization.gpu"]), memory_util=_number(v["utilization.memory"]),
        encoder=_number(v["utilization.encoder"]), decoder=_number(v["utilization.decoder"]),
        vram_used=mib("memory.used"), vram_total=mib("memory.total"),
        temperature_c=_number(v["temperature.gpu"]), power_w=_number(v["power.draw"]),
        power_limit_w=_number(v["power.limit"]), clock_hz=mhz("clocks.gr"),
        memory_clock_hz=mhz("clocks.mem"), fan=_number(v["fan.speed"]),
        pstate=_text(v["pstate"]))


# -- nvidia-settings ---------------------------------------------------------------------------

PCI_ATTRS = ("PCIDomain", "PCIBus", "PCIDevice", "PCIFunc")
SETTINGS_ATTRS = ("GPUUtilization", "GPUCoreTemp", "GPUCurrentClockFreqs",
                  "UsedDedicatedGPUMemory", "TotalDedicatedGPUMemory")
_ATTRIBUTE = re.compile(r"Attribute '(\w+)' \([^)\[]*\[gpu:(\d+)\]\):\s*(.*?)\.?\s*$")
# What nvidia-settings says when it can't reach NV-CONTROL (no X11 session
# on NVIDIA's driver: Wayland, or no display at all).
_UNREACHABLE = ("no targets match", "unable to load info", "cannot open display",
                "unable to init server", "control display is undefined",
                "nv-control extension is not available")


def settings_targets_argv(binary: str) -> list[str]:
    argv = [binary]
    for attr in PCI_ATTRS:
        argv += ["-q", attr]
    return argv


def _settings_failure(rc: int, out: str, err: str) -> Optional[NvidiaError]:
    text = f"{err}\n{out}".strip()
    lower = text.lower()
    if any(s in lower for s in _UNREACHABLE):
        first = next((l.strip() for l in text.splitlines()
                      if any(s in l.lower() for s in _UNREACHABLE)), text)
        return NvidiaError(first.removeprefix("ERROR: "), unreachable=True)
    if rc != 0:
        return NvidiaError(text or f"nvidia-settings exited with status {rc}")
    return None


def parse_settings_targets(rc: int, out: str, err: str) -> dict[str, int]:
    """PCI slot (``0000:02:00.0``) -> nvidia-settings GPU index."""
    failure = _settings_failure(rc, out, err)
    if failure is not None:
        raise failure
    found: dict[int, dict[str, int]] = {}
    for line in out.splitlines():
        m = _ATTRIBUTE.search(line.strip())
        if m and m.group(1) in PCI_ATTRS:
            value = _number(m.group(3))
            if value is not None:
                found.setdefault(int(m.group(2)), {})[m.group(1)] = int(value)
    slots = {}
    for index, a in found.items():
        if {"PCIBus", "PCIDevice"} <= a.keys():
            slots[f"{a.get('PCIDomain', 0):04x}:{a['PCIBus']:02x}:{a['PCIDevice']:02x}."
                  f"{a.get('PCIFunc', 0):x}"] = index
    if not slots:
        raise NvidiaError("nvidia-settings lists no GPUs", unreachable=True)
    return slots


def settings_argv(binary: str, index: int) -> list[str]:
    argv = [binary, "-t"]
    for attr in SETTINGS_ATTRS:
        argv += ["-q", f"[gpu:{index}]/{attr}"]
    return argv


def _key_values(text: str) -> dict[str, str]:
    """``graphics=12, memory=4, video=0, PCIe=1`` -> {'graphics': '12', ...}"""
    out = {}
    for part in text.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


def parse_settings(rc: int, out: str, err: str) -> NvidiaSample:
    """Terse answers to ``settings_argv``: one line per attribute, in order."""
    failure = _settings_failure(rc, out, err)
    if failure is not None:
        raise failure
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    if len(lines) != len(SETTINGS_ATTRS):
        raise NvidiaError(f"unexpected nvidia-settings output: {out.strip()!r}")
    v = dict(zip(SETTINGS_ATTRS, lines))
    util = _key_values(v["GPUUtilization"])
    clocks = [_number(c) for c in v["GPUCurrentClockFreqs"].split(",")]

    def mib(key):
        n = _number(v[key])
        return None if n is None else int(n * MIB)

    def num(key):
        return _number(util[key]) if key in util else None
    return NvidiaSample(
        tool="nvidia-settings", usage=num("graphics"), memory_util=num("memory"),
        video=num("video"), pcie=num("pcie"),
        temperature_c=_number(v["GPUCoreTemp"]),
        clock_hz=clocks[0] * 1e6 if clocks and clocks[0] is not None else None,
        memory_clock_hz=clocks[1] * 1e6 if len(clocks) > 1 and clocks[1] is not None else None,
        vram_used=mib("UsedDedicatedGPUMemory"), vram_total=mib("TotalDedicatedGPUMemory"))
