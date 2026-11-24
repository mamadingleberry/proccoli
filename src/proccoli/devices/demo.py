"""Synthetic device for ``--demo`` mode and tests."""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from typing import Mapping, Optional

from .. import GPU_ICON
from ..core.units import format_percent, format_rate
from .base import DeviceInfo, DeviceKind, Monitor, Snapshot
from ..core.sysroot import SysRoot
from .manager import Discoverer

DEMO_ROOT = "/nonexistent/proccoli-demo"


@dataclass
class DemoSnapshot(Snapshot):
    read: float = 0.0     # bytes per second
    write: float = 0.0

    def history_values(self) -> dict[str, Optional[float]]:
        return {"usage": self.usage, "read": self.read, "write": self.write}

    def history_units(self) -> Mapping[str, str]:
        return {"usage": "%", "read": "B/s", "write": "B/s"}


class SineMonitor(Monitor):
    """Smooth, deterministic waves: a usage percentage plus two transfer
    rates, so every widget has something to show."""

    def __init__(self, period_s: float = 20.0, history_points: int = 60) -> None:
        super().__init__(DeviceInfo("demo", DeviceKind.DEMO, "Demo Device",
                                    "Synthetic data", "computer-symbolic",
                                    {"Source": "sine waves"}), history_points)
        self.period_s = period_s

    def sample(self, now: float) -> DemoSnapshot:
        phase = 2 * math.pi * now / self.period_s
        usage = 50 + 35 * math.sin(phase) + 10 * math.sin(phase * 3.7)
        usage = min(max(usage, 0.0), 100.0)
        read = 40e6 * (1 + math.sin(phase * 0.8)) / 2
        write = 15e6 * (1 + math.cos(phase * 1.3)) / 2
        return DemoSnapshot(
            time=now, usage=usage, usage_text=format_percent(usage),
            detail_text=f"{format_rate(read)} read", read=read, write=write)


class DemoDiscoverer(Discoverer):
    """Provides the synthetic device to the DeviceManager in --demo mode."""
    kind = DeviceKind.DEMO

    def discover(self, sysroot, settings):
        return [SineMonitor().info]

    def create_monitor(self, info, sysroot, settings):
        return SineMonitor(history_points=settings.get("graph-data-points"))


class DemoGpuDiscoverer(Discoverer):
    """A synthetic Intel GPU for --demo: the detailed intel_gpu_top page fed
    by generated data, with a synthetic summary backend as the alternative.
    It uses an empty filesystem root, so nothing it reads can reach the real
    system (whose GPU may share the demo's PCI slot)."""
    kind = DeviceKind.GPU

    def __init__(self, system) -> None:
        self.system = system

    def discover(self, sysroot, settings):
        return [DeviceInfo("gpu-demo", DeviceKind.GPU, "GPU", "Demo Intel Graphics",
                           GPU_ICON,
                           {"Manufacturer": "Intel Corporation", "PCI Slot": "0000:00:02.0",
                            "Driver Used": "i915"})]

    def create_monitor(self, info, sysroot, settings):
        from ..gpu.backend import GpuDeps
        from ..gpu.controller import GpuController
        from ..gpu.info import GpuInfo, GpuVendor
        from ..gpu.intel_gpu_top.backend import DemoIntelGpuTopBackend
        from ..gpu.registry import GpuBackendRegistry

        gpu = GpuInfo("card-demo", "0000:00:02.0", GpuVendor.INTEL, 0x8086, 0x46A3, "i915",
                      "Demo Intel Graphics", True, None, dict(info.properties))
        registry = GpuBackendRegistry((DemoIntelGpuTopBackend, demo_summary_backend()))
        return GpuController(info, gpu, registry,
                             GpuDeps(SysRoot(DEMO_ROOT), settings, self.system),
                             settings.get("graph-data-points"))


@functools.lru_cache(maxsize=None)   # a GObject class may be registered only once
def demo_summary_backend():
    """The summary data source, fed by sine waves (defined lazily: the GPU
    package isn't needed unless the demo GPU is used)."""
    from ..gpu.generic_drm import GenericDrmBackend

    class DemoSummaryBackend(GenericDrmBackend):
        def refresh(self, now: float) -> None:
            phase = 2 * math.pi * now / 15
            s = self._summary
            s.usage = 40 + 30 * math.sin(phase)
            s.decode = s.encode = max(0.0, 30 * math.sin(phase / 2))
            s.frequency_hz = (400 + 8 * s.usage) * 1e6
            self.emit("updated")

        def process_usage(self):
            return {}

    return DemoSummaryBackend
