"""amdgpu's ``gpu_metrics`` table.

``/sys/class/drm/cardN/device/gpu_metrics`` is a binary snapshot of the
power-management firmware's readings, readable by every user. It starts
with a header (``structure_size``, ``format_revision``,
``content_revision``); the layout after it depends on the version
(``struct gpu_metrics_vX_Y`` in the kernel's ``kgd_pp_interface.h``).

Format revision 2 is the APU layout (Renoir, Cezanne, Van Gogh,
Rembrandt...): temperatures, power and clocks of the graphics *and* the
processor cores. Revision 1 is the discrete-GPU layout; those GPUs report
the same things through hwmon, which ``sensors.py`` reads, so it isn't
decoded here.

Pure: bytes in, a ``GpuMetrics`` out. Checked against a Ryzen 3 4300U
(v2.2) idle and under load (``tests/fixtures/renoir-apu``).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional

HEADER = struct.Struct("<HBB")
# v2.1 and later, up to fan_pwm (v2.0 is the same with whole °C). Later
# minor versions only add fields after these.
_V2 = struct.Struct("<12H2HQ4H8H6H6H8H2HIH")
_V2_SIZE = HEADER.size + _V2.size
INVALID = 0xFFFF

# ASIC-independent throttle reasons (v2.2+, ``indep_throttle_status``;
# SMU_THROTTLER_*_BIT in the kernel's amdgpu_smu.h), grouped as the
# Details tab names them.
THROTTLE_BITS = {
    0: "Power limit (PPT0)", 1: "Power limit (PPT1)", 2: "Power limit (PPT2)",
    3: "Power limit (PPT3)", 4: "Sustained power limit", 5: "Fast power limit",
    6: "Slow power limit", 7: "APU power limit",
    16: "Graphics current limit", 17: "SoC current limit", 18: "Memory current limit",
    19: "Core current limit", 20: "CVIP current limit", 21: "Processor current limit",
    22: "Graphics current limit", 23: "Current limit (APCC)",
    32: "GPU temperature", 33: "Core temperature", 34: "Memory temperature",
    35: "Edge temperature", 36: "Hotspot temperature", 37: "SoC temperature",
    38: "Graphics regulator temperature", 39: "SoC regulator temperature",
    40: "Memory regulator temperature", 41: "Memory regulator temperature",
    42: "Liquid temperature", 43: "Liquid temperature",
    44: "Regulator hot", 45: "Regulator hot",
    46: "Processor hot (PROCHOT)", 47: "Graphics hot (PROCHOT)",
    56: "Peak power management", 57: "Reliability limit (FIT)",
}


@dataclass
class GpuMetrics:
    """One reading of the table, in base units. ``None``: not reported."""
    version: tuple[int, int]
    gfx_temperature_c: Optional[float] = None
    soc_temperature_c: Optional[float] = None
    core_temperatures_c: list[float] = field(default_factory=list)   # cores in use
    socket_power_w: Optional[float] = None         # the whole APU package
    cpu_power_w: Optional[float] = None
    soc_power_w: Optional[float] = None
    gfx_power_w: Optional[float] = None
    gfx_clock_hz: Optional[float] = None           # current
    soc_clock_hz: Optional[float] = None
    memory_clock_hz: Optional[float] = None        # uclk
    fabric_clock_hz: Optional[float] = None        # fclk
    video_clock_hz: Optional[float] = None         # vclk
    throttle: list[str] = field(default_factory=list)

    @property
    def hottest_core_c(self) -> Optional[float]:
        return max(self.core_temperatures_c, default=None)


def header(data: Optional[bytes]) -> Optional[tuple[int, int, int]]:
    """``(structure_size, format_revision, content_revision)`` or None."""
    if not data or len(data) < HEADER.size:
        return None
    return HEADER.unpack_from(data)


def is_apu_table(data: Optional[bytes]) -> bool:
    """Whether the table is the APU layout (format revision 2)."""
    h = header(data)
    return h is not None and h[1] == 2


def _valid(raw: int) -> bool:
    return raw not in (INVALID, 0)


def _hz(mhz: int) -> Optional[float]:
    return mhz * 1e6 if _valid(mhz) else None


def _mw(raw: int) -> Optional[float]:
    return raw / 1000 if raw != INVALID else None


def socket_power_w(raw: int, cpu_mw: int) -> Optional[float]:
    """The package power. The kernel documents milliwatts, but Renoir's
    firmware reports whole watts (15 at idle beside 11 672 mW for the
    cores alone). A package can't draw less than its cores, so a value
    that would be is in watts."""
    if raw == INVALID:
        return None
    if cpu_mw != INVALID and raw < cpu_mw:
        return float(raw)
    return raw / 1000


def throttle_reasons(bits: int) -> list[str]:
    """Names of the set ``indep_throttle_status`` bits, without repeats."""
    names: list[str] = []
    for bit, name in sorted(THROTTLE_BITS.items()):
        if bits >> bit & 1 and name not in names:
            names.append(name)
    return names


def parse_gpu_metrics(data: Optional[bytes]) -> Optional[GpuMetrics]:
    """The table's readings, or None for a layout this doesn't know (any
    revision 1 table, a truncated one)."""
    h = header(data)
    if h is None or h[1] != 2 or len(data) < _V2_SIZE:
        return None
    size, fmt, content = h
    v = _V2.unpack_from(data, HEADER.size)
    temps, (_gfx_activity, _mm_activity), _clock = v[0:12], v[12:14], v[14]
    socket, cpu, soc, gfx = v[15:19]
    core_power = v[19:27]
    current = v[33:39]                      # gfx, soc, uclk, fclk, vclk, dclk
    # Renoir reports a level number (6) as its memory clock: no clock is
    # under 100 MHz, so such a value isn't one.
    core_clocks = v[39:47]
    # v2.0 reports whole degrees; v2.1 and later hundredths.
    scale = 1.0 if content == 0 else 100.0

    def temp(raw: int) -> Optional[float]:
        return raw / scale if _valid(raw) else None

    # A core takes part when it has a clock or draws power; unused slots
    # (a 4-core part fills 4 of 8) still report a temperature.
    cores = [temp(t) for t, clk, pw in zip(temps[2:10], core_clocks, core_power)
             if _valid(clk) or _valid(pw)]
    m = GpuMetrics(
        version=(fmt, content),
        gfx_temperature_c=temp(temps[0]), soc_temperature_c=temp(temps[1]),
        core_temperatures_c=[t for t in cores if t is not None],
        socket_power_w=socket_power_w(socket, cpu),
        cpu_power_w=_mw(cpu), soc_power_w=_mw(soc), gfx_power_w=_mw(gfx),
        gfx_clock_hz=_hz(current[0]), soc_clock_hz=_hz(current[1]),
        memory_clock_hz=_hz(current[2]) if current[2] > 100 else None,
        fabric_clock_hz=_hz(current[3]), video_clock_hz=_hz(current[4]))
    # indep_throttle_status: v2.2 and later, after 3 words of padding.
    indep_at = _V2_SIZE + 6
    if content >= 2 and size >= indep_at + 8 and len(data) >= indep_at + 8:
        m.throttle = throttle_reasons(struct.unpack_from("<Q", data, indep_at)[0])
    return m
