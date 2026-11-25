"""The AMD detail source.

amdgpu publishes everything the Details tab needs in sysfs, readable by
every user, so there's no tool to install and no password: each refresh
reads the device's files (``sensors.read_sample()``) and DRM fdinfo for
per-engine use, keeps the readings in a ``History`` for the graphs, and
emits ``updated``.

APUs (Renoir and later) add ``gpu_metrics`` (``metrics.py``): SoC and
processor-core temperatures and the package's power split into cores and
SoC. Discrete GPUs get the same tab from hwmon (junction and memory
temperatures, board power, fan).

The GPU's processes come from this source's fdinfo reading while it runs,
with GTT counted as graphics memory on an APU.
"""

from __future__ import annotations

import math
from typing import Optional

from ...core.connections import Connections
from ...core.history import History
from ...core.ticker import PLAN_KEYS, graph_plan
from ..backend import (Capability, DetailBackend, GpuDeps, GpuSummary, Probe, SupportLevel,
                       TabSpec)
from ..fdinfo import shared_reader
from ..info import GpuInfo, GpuVendor
from .sensors import HISTORY_UNITS, AmdgpuSample, hwmon_dir, read_sample

SOURCE_NOTE = "amdgpu's statistics files"
# A file only amdgpu devices with power management have: without it (or
# gpu_metrics) there's nothing to chart.
USAGE_FILE = "gpu_busy_percent"


class AmdgpuBackend(DetailBackend):
    id = "amdgpu"
    display_name = "AMD"
    capabilities = (Capability.SUMMARY | Capability.PER_PROCESS | Capability.PER_ENGINE
                    | Capability.POWER | Capability.TEMPERATURE | Capability.VRAM)
    TABS = (TabSpec("details", "Details", "power-profile-performance-symbolic"),)

    def __init__(self, gpu: GpuInfo, deps: GpuDeps) -> None:
        super().__init__(gpu, deps)
        self.apu = gpu.integrated
        self.fdinfo = shared_reader(deps, gpu.pci_slot, shared_memory=self.apu)
        self.hwmon = hwmon_dir(deps.sysroot, gpu.device_path)
        self.history = History(graph_plan(deps.settings)[0])
        self.history.set_plan(*graph_plan(deps.settings))
        for name, unit in HISTORY_UNITS.items():
            self.history.define(name, unit)
        self._plan_connections = Connections()
        self.sample: Optional[AmdgpuSample] = None
        self.source_note = SOURCE_NOTE
        self._running = False

    @classmethod
    def probe(cls, gpu: GpuInfo, deps: GpuDeps) -> Probe:
        if gpu.vendor != GpuVendor.AMD:
            return Probe(SupportLevel.UNSUPPORTED, "not an AMD GPU")
        if gpu.driver != "amdgpu":
            return Probe(SupportLevel.UNSUPPORTED,
                         f"driver {gpu.driver or 'none'}; detailed statistics need amdgpu")
        dev = gpu.device_path
        if not (deps.sysroot.exists(f"{dev}/{USAGE_FILE}")
                or deps.sysroot.exists(f"{dev}/gpu_metrics")):
            return Probe(SupportLevel.UNSUPPORTED, "amdgpu doesn't report this GPU's usage")
        return Probe(SupportLevel.PREFERRED, SOURCE_NOTE)

    # -- lifecycle -----------------------------------------------------------------------

    def start(self, elevate: bool = False) -> None:
        super().start(False)                      # never needs administrator rights
        self._running = True
        # The graphs' time range, as on every page.
        self._plan_connections.watch(
            self.settings, PLAN_KEYS, lambda *_: self.history.set_plan(*graph_plan(self.settings)))

    def stop(self) -> None:
        self._running = False
        self._plan_connections.disconnect_all()

    def refresh(self, now: float) -> None:
        if not self._running:
            return
        self.fdinfo.read(now)
        sample = self._read(now)
        self.sample = sample
        self.history.add(now, sample.history_values(), HISTORY_UNITS)
        self.emit("updated")

    def _read(self, now: float) -> AmdgpuSample:
        return read_sample(self.sysroot, self.gpu.device_path, self.apu,
                           self.fdinfo.engines, self.hwmon)

    # -- data ----------------------------------------------------------------------------

    def summary(self) -> GpuSummary:
        return self.sample.to_summary() if self.sample else GpuSummary()

    def has_data(self) -> bool:
        return self.sample is not None

    def process_usage(self):
        return self.fdinfo.processes

    def history_readings(self) -> tuple[dict, dict]:
        """The Details tab's readings, recorded in the history database."""
        if self.sample is None:
            return {}, {}
        return dict(self.sample.history_values()), dict(HISTORY_UNITS)

    def history_target(self):
        return self.history

    def create_views(self, controller, services):
        from .views import create_views
        return create_views(self, controller, services)


class DemoAmdgpuBackend(AmdgpuBackend):
    """Synthetic amdgpu readings for --demo: an APU like the Ryzen 3 4300U
    whose files the tests use, with waves instead of files (it reads
    nothing)."""

    @classmethod
    def probe(cls, gpu, deps) -> Probe:
        return Probe(SupportLevel.PREFERRED, "synthetic data")

    def _read(self, now: float) -> AmdgpuSample:
        return demo_sample(now)

    def process_usage(self):
        return {}


def demo_sample(now: float) -> AmdgpuSample:
    """A busy-then-idle APU, deterministic in ``now``."""
    phase = 2 * math.pi * now / 20
    busy = max(0.0, 45 + 35 * math.sin(phase))
    video = max(0.0, 40 * math.sin(phase / 3))
    gib = 2 ** 30
    return AmdgpuSample(
        apu=True, usage=busy, video=video,
        engines={"gfx": busy, "compute": busy * 0.2, "dma": busy * 0.05,
                 "dec": video, "enc": video * 0.3},
        vram_used=int(0.85 * gib), vram_total=gib,
        gtt_used=int((0.4 + busy / 100) * gib), gtt_total=int(7.3 * gib),
        clock_hz=(400 + 10 * busy) * 1e6, memory_clock_hz=1333e6,
        fabric_clock_hz=(800 + 4 * busy) * 1e6, soc_clock_hz=(400 + 5 * busy) * 1e6,
        temperature_c=38 + busy * 0.25, soc_temperature_c=40 + busy * 0.2,
        cpu_temperature_c=45 + 15 * math.sin(phase / 2 + 1),
        package_power_w=9 + busy * 0.25, cpu_power_w=5 + busy * 0.18, soc_power_w=1.6,
        gfx_voltage_v=0.8 + busy / 250, nb_voltage_v=0.79,
        throttle=["Fast power limit"] if busy > 75 else [])
