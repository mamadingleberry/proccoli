"""The AMD Details tab: what amdgpu's statistics files
report, as graphs over time.

A ``DetailChartsView`` like the NVIDIA tab (the shared ``ChartCard``s in a
``ChartGridView``, every chart preference live, readings in the user's
units). A caption names the GPU, its driver and the source, then a card per
measure: utilization, engines (from the apps Proccoli can see), memory
(dedicated and, on an APU, shared), clocks, temperatures, power (the
package's split into cores and SoC on an APU, with what's limiting it),
voltages and fan. Lines and cards the GPU doesn't report are hidden.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from ...core.units import format_bytes, format_frequency, format_percent, format_power  # noqa: E402
from ...ui.chart_settings import ChartSettings  # noqa: E402
from ...ui.widgets.detail_charts import DetailChartsView  # noqa: E402
from ..backend import DetailView, DetailViews  # noqa: E402

GRAPHS = [
    ("GPU Utilization", [("graphics", "Graphics"), ("memory-controller", "Memory Controller"),
                         ("video", "Video")], 100.0, 0.0, 200),
    ("Engines", [("gfx", "Graphics"), ("compute", "Compute"), ("dma", "Copy"),
                 ("dec", "Video Decode"), ("enc", "Video Encode")], 100.0, 0.0, 160),
    ("Memory", [("vram", "Dedicated"), ("gtt", "Shared")], 100.0, 0.0, 120),
    ("Clocks", [("clock", "Graphics"), ("memory-clock", "Memory"),
                ("fabric-clock", "Fabric"), ("soc-clock", "SoC")], None, 1e9, 140),
    ("Temperature", [("temperature", "GPU"), ("junction", "Junction"),
                     ("memory-temperature", "Memory"), ("soc-temperature", "SoC"),
                     ("cpu-temperature", "Processor")], None, 100.0, 140),
    ("Power", [("power", "GPU"), ("package-power", "Package"), ("cpu-power", "Processor Cores"),
               ("soc-power", "SoC")], None, 10.0, 120),
    ("Voltage", [("gfx-voltage", "Graphics"), ("nb-voltage", "Northbridge")], None, 1.0, 100),
    ("Fan", [("fan", "Speed")], 100.0, 0.0, 100),
]


def caption_text(backend) -> str:
    """GPU name, driver and source; engines count only the visible apps."""
    gpu = backend.gpu
    kind = "integrated" if backend.apu else ""
    parts = [gpu.name, f"driver {gpu.driver}" + (f", {kind}" if kind else ""),
             f"from {backend.source_note}", "engines: the apps Proccoli can see"]
    return " · ".join(parts)


def power_info(s) -> str:
    """The main power reading, its cap, and what's limiting it."""
    if s.power_w is not None:
        text = format_power(s.power_w)
    elif s.package_power_w is not None:
        text = f"Package {format_power(s.package_power_w)}"
    else:
        return ""
    if s.power_cap_w:
        text += f" of {format_power(s.power_cap_w)}"
    if s.throttle:
        text += " · limited by " + ", ".join(r.lower() for r in s.throttle)
    return text


class AmdgpuDetailsView(DetailChartsView):
    GRAPHS = GRAPHS

    def values(self):
        s = self.backend.sample
        return s.history_values() if s else None

    def caption_line(self) -> str:
        return caption_text(self.backend)

    def info(self, title: str) -> str:
        s = self.backend.sample
        if title == "GPU Utilization":
            return format_percent(s.usage)
        if title == "Memory":
            summary = s.to_summary()
            if not summary.memory_total:
                return ""
            base = self.charts.base
            return (f"{format_bytes(summary.memory_used, base)} of "
                    f"{format_bytes(summary.memory_total, base)}")
        if title == "Clocks":
            return format_frequency(s.clock_hz) if s.clock_hz else ""
        if title == "Temperature":
            return self.charts.format_value(s.temperature_c, "°C")
        if title == "Power":
            return power_info(s)
        if title == "Fan":
            return format_percent(s.fan)
        return ""


def create_views(backend, controller, services) -> DetailViews:
    view = AmdgpuDetailsView(backend, services.charts or ChartSettings(services.settings))
    handler = backend.connect("updated", lambda _b: view.refresh())
    return DetailViews([DetailView("details", view, [])], [handler])
