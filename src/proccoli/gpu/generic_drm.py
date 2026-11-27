"""Resources-level GPU data from sysfs and DRM fdinfo; works for any GPU
with a DRM driver, so it's every GPU's fallback."""

from __future__ import annotations

import re
from typing import Optional

from .backend import Capability, GpuBackend, GpuDeps, GpuSummary, Probe, SupportLevel
from .fdinfo import DECODE_ENGINES, ENCODE_ENGINES, VIDEO_ENGINES, shared_reader
from .info import GpuInfo, GpuVendor


def active_dpm_hz(text: Optional[str]) -> Optional[float]:
    """The current level of an amdgpu pp_dpm_* table ("1: 2100Mhz *")."""
    for line in (text or "").splitlines():
        if line.rstrip().endswith("*"):
            m = re.search(r"(\d+)\s*Mhz", line, re.IGNORECASE)
            if m:
                return int(m.group(1)) * 1e6
    return None


class Residency:
    """Busy percent from an idle-residency counter: the milliseconds a GT
    has spent asleep (i915's RC6, xe's gtidle). Over ``Δt``, busy is
    ``100 × (1 − Δasleep / Δt)``. Anyone can read the counters, so an
    Intel GPU nothing has open still reads (0 %) without administrator
    rights. The GT falls asleep a few ms after work stops, so light loads
    read a little high. The first sample, and one after the counter went
    backwards (a reset, e.g. after a resume), have no figure."""

    def __init__(self) -> None:
        self._prev: Optional[tuple[float, int]] = None

    def sample(self, now_s: float, asleep_ms: Optional[int]) -> Optional[float]:
        if asleep_ms is None:
            self._prev = None
            return None
        prev, self._prev = self._prev, (now_s, asleep_ms)
        if prev is None or now_s <= prev[0] or asleep_ms < prev[1]:
            return None
        busy = 100 * (1 - (asleep_ms - prev[1]) / ((now_s - prev[0]) * 1000))
        return min(100.0, max(0.0, busy))


def residency_paths(gpu: GpuInfo, gt: int) -> tuple[str, ...]:
    """Where GT ``gt``'s idle residency may be: i915 per GT, i915 before
    per-GT files (GT 0 only), xe per tile and GT."""
    paths = [f"{gpu.sysfs}/gt/gt{gt}/rc6_residency_ms"]
    if gt == 0:
        paths.append(f"{gpu.sysfs}/power/rc6_residency_ms")
    paths.append(f"{gpu.device_path}/tile0/gt{gt}/gtidle/idle_residency_ms")
    return tuple(paths)


class GenericDrmBackend(GpuBackend):
    id = "generic"
    display_name = "Summary"
    capabilities = Capability.SUMMARY | Capability.PER_PROCESS

    def __init__(self, gpu: GpuInfo, deps: GpuDeps) -> None:
        super().__init__(gpu, deps)
        sysroot = deps.sysroot
        # An AMD APU: GTT is graphics memory too, and hwmon's
        # power is the whole package's.
        self.apu = gpu.vendor == GpuVendor.AMD and gpu.integrated
        self.fdinfo = shared_reader(deps, gpu.pci_slot, shared_memory=self.apu)
        self._summary = GpuSummary(combined_video=gpu.driver in ("i915", "xe"),
                                   shared_memory=self.apu)
        self._energy: Optional[tuple[float, int]] = None
        self.hwmon = next((f"{gpu.device_path}/hwmon/{h}"
                           for h in sysroot.listdir(f"{gpu.device_path}/hwmon")), None)
        # Intel: the render GT (0) and, from Meteor Lake on, the media GT (1).
        intel = gpu.driver in ("i915", "xe")
        self._residency = {gt: (next((p for p in residency_paths(gpu, gt) if sysroot.exists(p)),
                                     None), Residency())
                           for gt in (0, 1)} if intel else {}

    @classmethod
    def probe(cls, gpu, deps) -> Probe:
        return Probe(SupportLevel.FALLBACK, "basic statistics from sysfs")

    # -- readings -------------------------------------------------------------

    def _asleep(self, gt: int, now: float) -> Optional[float]:
        """GT ``gt``'s busy percent from its idle residency, if it has one."""
        path, residency = self._residency.get(gt, (None, None))
        if path is None:
            return None
        return residency.sample(now, self.sysroot.read_int(path))

    def _frequency(self) -> Optional[float]:
        r, dev = self.sysroot, self.gpu.device_path
        for path in (f"{self.gpu.sysfs}/gt_act_freq_mhz",           # i915
                     f"{dev}/tile0/gt0/freq0/act_freq",             # xe
                     f"{self.gpu.sysfs}/gt_cur_freq_mhz"):
            mhz = r.read_int(path)
            if mhz is not None:
                return mhz * 1e6            # 0: the GT is asleep, a reading too
        return active_dpm_hz(r.read_text(f"{dev}/pp_dpm_sclk"))      # amdgpu

    def _power(self, now: float) -> Optional[float]:
        if not self.hwmon:
            return None
        r = self.sysroot
        for f in ("power1_average", "power1_input"):
            uw = r.read_int(f"{self.hwmon}/{f}")
            if uw is not None:
                return uw / 1e6
        uj = r.read_int(f"{self.hwmon}/energy1_input")     # i915/xe dGPUs
        if uj is None:
            return None
        prev, self._energy = self._energy, (now, uj)
        if prev and now > prev[0]:
            return max(uj - prev[1], 0) / 1e6 / (now - prev[0])
        return None

    def refresh(self, now: float) -> None:
        r, dev = self.sysroot, self.gpu.device_path
        self.fdinfo.read(now)
        engines = self.fdinfo.engines
        # Sampled every tick, so either is ready when fdinfo has nothing.
        render, media = (self._asleep(gt, now) for gt in (0, 1))
        busy = r.read_int(f"{dev}/gpu_busy_percent")
        if busy is None and engines:
            busy = max((v for e, v in engines.items() if e not in VIDEO_ENGINES), default=0.0)
        if busy is None:
            busy = render                 # no client has it open: the GT's own figure
        s = self._summary
        s.usage = float(busy) if busy is not None else None
        s.decode = max((v for e, v in engines.items() if e in DECODE_ENGINES), default=None)
        s.encode = max((v for e, v in engines.items() if e in ENCODE_ENGINES), default=None)
        if s.decode is None and s.encode is None and s.combined_video:
            s.decode = media              # the media GT is encode and decode
        s.vram_used = r.read_int(f"{dev}/mem_info_vram_used")
        s.vram_total = r.read_int(f"{dev}/mem_info_vram_total")
        s.gtt_used = r.read_int(f"{dev}/mem_info_gtt_used")
        s.gtt_total = r.read_int(f"{dev}/mem_info_gtt_total")
        s.frequency_hz = self._frequency()
        s.vram_frequency_hz = active_dpm_hz(r.read_text(f"{dev}/pp_dpm_mclk"))
        s.power_w = self._power(now)
        s.power_is_package = self.apu and s.power_w is not None
        if self.hwmon:
            cap = r.read_int(f"{self.hwmon}/power1_cap")
            s.power_cap_w = cap / 1e6 if cap else None
            milli = r.read_int(f"{self.hwmon}/temp1_input")
            s.temperature_c = milli / 1000 if milli is not None else None
        self.emit("updated")

    def summary(self) -> GpuSummary:
        return self._summary

    def process_usage(self):
        return self.fdinfo.processes
