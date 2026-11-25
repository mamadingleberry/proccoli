"""One reading of an amdgpu device's sysfs files.

``read_sample`` gathers what the Details tab charts, from files every user
may read:

- ``gpu_busy_percent``, ``mem_busy_percent``, ``vcn_busy_percent``;
- ``mem_info_vram_*`` (on an APU, the carve-out) and ``mem_info_gtt_*``;
- the clock tables ``pp_dpm_sclk``, ``_mclk``, ``_fclk``, ``_socclk``;
- hwmon: temperatures by label (edge, junction, mem), power (``PPT``: the
  package's on an APU, the board's on a discrete GPU), its cap, voltages
  (vddgfx, vddnb) and the fan;
- ``gpu_metrics`` (APUs): SoC and processor-core temperatures, the
  package's power split into cores and SoC, clocks, throttle reasons;
- per-engine use from DRM fdinfo, passed in (``FdinfoReader.engines``).

Pure apart from the ``SysRoot`` reads; no GTK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from ...core.sysroot import SysRoot
from ..backend import GpuSummary
from ..fdinfo import DECODE_ENGINES, ENCODE_ENGINES
from ..generic_drm import active_dpm_hz
from .metrics import GpuMetrics, parse_gpu_metrics

# History keys and their base units (what the Details tab graphs).
HISTORY_UNITS = {
    "graphics": "%", "memory-controller": "%", "video": "%",
    "gfx": "%", "compute": "%", "dma": "%", "dec": "%", "enc": "%",
    "vram": "%", "gtt": "%",
    "clock": "Hz", "memory-clock": "Hz", "fabric-clock": "Hz", "soc-clock": "Hz",
    "temperature": "°C", "junction": "°C", "memory-temperature": "°C",
    "soc-temperature": "°C", "cpu-temperature": "°C",
    "power": "W", "package-power": "W", "cpu-power": "W", "soc-power": "W",
    "gfx-voltage": "V", "nb-voltage": "V", "fan": "%",
}


@dataclass
class AmdgpuSample:
    """Readings in base units; ``None``: the device doesn't report it."""
    apu: bool = False
    usage: Optional[float] = None                 # gpu_busy_percent
    memory_controller: Optional[float] = None     # mem_busy_percent (discrete GPUs)
    video: Optional[float] = None                 # vcn_busy_percent
    engines: dict = field(default_factory=dict)   # fdinfo: gfx, compute, dma, dec, enc
    vram_used: Optional[int] = None
    vram_total: Optional[int] = None
    gtt_used: Optional[int] = None
    gtt_total: Optional[int] = None
    clock_hz: Optional[float] = None
    memory_clock_hz: Optional[float] = None
    fabric_clock_hz: Optional[float] = None
    soc_clock_hz: Optional[float] = None
    temperature_c: Optional[float] = None         # edge (or the graphics', on an APU)
    junction_c: Optional[float] = None
    memory_temperature_c: Optional[float] = None
    soc_temperature_c: Optional[float] = None
    cpu_temperature_c: Optional[float] = None     # the hottest core (APU)
    power_w: Optional[float] = None               # the GPU's own
    package_power_w: Optional[float] = None       # the whole APU
    cpu_power_w: Optional[float] = None
    soc_power_w: Optional[float] = None
    power_cap_w: Optional[float] = None
    gfx_voltage_v: Optional[float] = None
    nb_voltage_v: Optional[float] = None
    fan: Optional[float] = None                   # percent of full speed
    throttle: list = field(default_factory=list)  # reasons, while limited

    @staticmethod
    def _percent(used: Optional[int], total: Optional[int]) -> Optional[float]:
        return 100.0 * used / total if used is not None and total else None

    def history_values(self) -> dict[str, Optional[float]]:
        """For the Details tab's graphs (``HISTORY_UNITS`` names)."""
        e = self.engines
        return {
            "graphics": self.usage, "memory-controller": self.memory_controller,
            "video": self.video,
            "gfx": e.get("gfx"), "compute": e.get("compute"), "dma": e.get("dma"),
            "dec": e.get("dec"), "enc": e.get("enc"),
            "vram": self._percent(self.vram_used, self.vram_total),
            "gtt": self._percent(self.gtt_used, self.gtt_total),
            "clock": self.clock_hz, "memory-clock": self.memory_clock_hz,
            "fabric-clock": self.fabric_clock_hz, "soc-clock": self.soc_clock_hz,
            "temperature": self.temperature_c, "junction": self.junction_c,
            "memory-temperature": self.memory_temperature_c,
            "soc-temperature": self.soc_temperature_c,
            "cpu-temperature": self.cpu_temperature_c,
            "power": self.power_w, "package-power": self.package_power_w,
            "cpu-power": self.cpu_power_w, "soc-power": self.soc_power_w,
            "gfx-voltage": self.gfx_voltage_v, "nb-voltage": self.nb_voltage_v,
            "fan": self.fan,
        }

    def to_summary(self) -> GpuSummary:
        """The Overview tab's view of this reading (the same rules as the
        generic source's and 3)."""
        e = self.engines
        package = self.power_w is None and self.package_power_w is not None
        return GpuSummary(
            usage=self.usage, encode=e.get("enc"), decode=e.get("dec"),
            vram_used=self.vram_used, vram_total=self.vram_total,
            gtt_used=self.gtt_used, gtt_total=self.gtt_total, shared_memory=self.apu,
            frequency_hz=self.clock_hz, vram_frequency_hz=self.memory_clock_hz,
            power_w=self.package_power_w if package else self.power_w,
            power_cap_w=self.power_cap_w, power_is_package=package,
            temperature_c=self.temperature_c)


def engine_classes(engines: Mapping[str, float]) -> dict[str, float]:
    """fdinfo's engines as the tab's five: graphics, compute, copy (dma)
    and the video decoder and encoder (``dec``, ``jpeg``, ``enc_1``... the
    busiest of each kind). Engines no client has used are left out."""
    out = {}
    for name in ("gfx", "compute", "dma"):
        if name in engines:
            out[name] = engines[name]
    dec = [v for e, v in engines.items() if e in DECODE_ENGINES]
    enc = [v for e, v in engines.items() if e in ENCODE_ENGINES]
    if dec:
        out["dec"] = max(dec)
    if enc:
        out["enc"] = max(enc)
    return out


def hwmon_dir(sysroot: SysRoot, device_path: str) -> Optional[str]:
    return next((f"{device_path}/hwmon/{h}"
                 for h in sysroot.listdir(f"{device_path}/hwmon")), None)


def _labelled(sysroot: SysRoot, hwmon: str, prefix: str) -> dict[str, int]:
    """``{label: raw value}`` of hwmon's ``<prefix>N_input`` files."""
    out = {}
    for name in sysroot.listdir(hwmon):
        if name.startswith(prefix) and name.endswith("_input"):
            n = name[len(prefix):-len("_input")]
            label = sysroot.read_line(f"{hwmon}/{prefix}{n}_label") or f"{prefix}{n}"
            value = sysroot.read_int(f"{hwmon}/{name}")
            if value is not None:
                out[label.lower()] = value
    return out


def read_sample(sysroot: SysRoot, device_path: str, apu: bool,
                engines: Mapping[str, float] = (),
                hwmon: Optional[str] = None) -> AmdgpuSample:
    r, dev = sysroot, device_path
    metrics: Optional[GpuMetrics] = parse_gpu_metrics(r.read_bytes(f"{dev}/gpu_metrics"))
    s = AmdgpuSample(apu=apu, engines=engine_classes(dict(engines)))
    busy = r.read_int(f"{dev}/gpu_busy_percent")
    s.usage = float(busy) if busy is not None else None
    for attr, name in (("memory_controller", "mem_busy_percent"), ("video", "vcn_busy_percent")):
        value = r.read_int(f"{dev}/{name}")
        setattr(s, attr, float(value) if value is not None else None)
    s.vram_used = r.read_int(f"{dev}/mem_info_vram_used")
    s.vram_total = r.read_int(f"{dev}/mem_info_vram_total")
    s.gtt_used = r.read_int(f"{dev}/mem_info_gtt_used")
    s.gtt_total = r.read_int(f"{dev}/mem_info_gtt_total")

    def dpm(name: str, fallback: Optional[float]) -> Optional[float]:
        return active_dpm_hz(r.read_text(f"{dev}/pp_dpm_{name}")) or fallback

    m = metrics or GpuMetrics(version=(0, 0))
    s.clock_hz = dpm("sclk", m.gfx_clock_hz)
    s.memory_clock_hz = dpm("mclk", m.memory_clock_hz)
    s.fabric_clock_hz = dpm("fclk", m.fabric_clock_hz)
    s.soc_clock_hz = dpm("socclk", m.soc_clock_hz)
    s.soc_temperature_c = m.soc_temperature_c
    s.cpu_temperature_c = m.hottest_core_c
    s.cpu_power_w = m.cpu_power_w
    s.soc_power_w = m.soc_power_w
    s.throttle = list(m.throttle)

    hwmon = hwmon or hwmon_dir(r, dev)
    temps = _labelled(r, hwmon, "temp") if hwmon else {}
    volts = _labelled(r, hwmon, "in") if hwmon else {}

    def celsius(label: str) -> Optional[float]:
        return temps[label] / 1000 if label in temps else None
    s.temperature_c = celsius("edge") if "edge" in temps else (
        celsius("temp1") if "temp1" in temps else m.gfx_temperature_c)
    s.junction_c = celsius("junction")
    s.memory_temperature_c = celsius("mem")
    s.gfx_voltage_v = volts["vddgfx"] / 1000 if "vddgfx" in volts else None
    s.nb_voltage_v = volts["vddnb"] / 1000 if "vddnb" in volts else None

    board = None
    if hwmon:
        for f in ("power1_average", "power1_input"):
            uw = r.read_int(f"{hwmon}/{f}")
            if uw is not None:
                board = uw / 1e6
                break
        cap = r.read_int(f"{hwmon}/power1_cap")
        s.power_cap_w = cap / 1e6 if cap else None
        pwm = r.read_int(f"{hwmon}/pwm1")
        s.fan = 100.0 * pwm / 255 if pwm is not None else None
    if apu:
        # The package's power. The firmware's own GPU figure, when
        # it has one (Renoir doesn't), is the GPU's.
        s.package_power_w = m.socket_power_w if m.socket_power_w is not None else board
        s.power_w = m.gfx_power_w
    else:
        s.power_w = board
    return s
