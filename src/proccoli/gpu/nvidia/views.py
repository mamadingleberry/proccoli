"""The NVIDIA Details tab (Milestone 55): what nvidia-settings or nvidia-smi
reports, as graphs over time.

A caption names the GPU, its driver and the tool in use (and why that one),
then one graph per measure: utilisation (graphics, memory controller,
PCIe), video engines, video memory, clocks, temperature, power and fan.
Graphs with several lines get a legend. A measure the tool doesn't report
hides its graph.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ...core.units import (Base, TemperatureUnit, format_bytes, format_frequency,  # noqa: E402
                           format_percent, format_power, format_temperature)
from ...ui.axes import history_span_s  # noqa: E402
from ...ui.widgets.graph_box import GraphBox  # noqa: E402
from ...ui.widgets.legend_chart import LegendChart  # noqa: E402
from ..backend import DetailView, DetailViews  # noqa: E402

# (title, [(series, legend name)], fixed max or None, min of an automatic max)
GRAPHS = [
    ("GPU Utilization", [("graphics", "Graphics"), ("memory-controller", "Memory Controller"),
                         ("pcie", "PCIe")], 100.0, 0.0),
    ("Video Engines", [("encoder", "Encoder"), ("decoder", "Decoder")], 100.0, 0.0),
    ("Video Memory", [("vram", "Used")], 100.0, 0.0),
    ("Clocks", [("clock", "Graphics"), ("memory-clock", "Memory")], None, 1000.0),
    ("Temperature", [("temperature", "GPU")], None, 100.0),
    ("Power", [("power", "Draw")], None, 10.0),
    ("Fan", [("fan", "Speed")], 100.0, 0.0),
]


def caption_text(backend) -> str:
    """GPU name, driver, and the tool in use with the reason for it."""
    s = backend.sample
    parts = [s.name if s and s.name else backend.gpu.name]
    if s and s.driver:
        parts.append(f"driver {s.driver}")
    if backend.source_note:
        parts.append(f"from {backend.source_note}")
    return " · ".join(parts)


class NvidiaDetailsView(Gtk.ScrolledWindow):
    def __init__(self, backend, settings) -> None:
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self.backend = backend
        self.settings = settings
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      margin_top=18, margin_bottom=18, margin_start=12, margin_end=12)
        self.caption = Gtk.Label(xalign=0, wrap=True)
        self.caption.add_css_class("dim-label")
        box.append(self.caption)
        self.boxes: dict[str, GraphBox] = {}
        self.legends: dict = {}
        self.groups: dict[str, Adw.PreferencesGroup] = {}
        for title, series, max_value, min_max in GRAPHS:
            group = Adw.PreferencesGroup()
            lines = [backend.history.series(name) for name, _ in series]
            if len(series) > 1:
                # The reusable many-line chart (M59): legend in the card, the
                # same click rules as the per-CPU chart.
                graph_box = LegendChart(title, max_value=max_value, min_max=min_max)
                graph_box.set_lines(lines, [label for _, label in series])
                self.legends[title] = graph_box.legend
            else:
                graph_box = GraphBox(title, max_value=max_value, min_max=min_max)
                graph_box.set_series(lines)
            graph_box.graph.set_show_axes(settings.get("show-graph-axes"))
            graph_box.graph.set_time_span(history_span_s(settings))
            group.add(graph_box)
            self.boxes[title] = graph_box
            self.groups[title] = group
            box.append(group)
        self.set_child(Adw.Clamp(maximum_size=1600, child=box))
        self.refresh()

    def refresh(self) -> None:
        """New reading: captions, info lines, which graphs show, redraw."""
        self.caption.set_label(caption_text(self.backend))
        s = self.backend.sample
        values = s.history_values() if s else {}
        for title, series, _max, _min in GRAPHS:
            reported = [values.get(name) is not None for name, _ in series]
            self.groups[title].set_visible(s is None or any(reported))
            graph = self.boxes[title].graph
            legend = self.legends.get(title)
            for i, is_reported in enumerate(reported):
                if s is None:
                    continue
                # A measure the tool doesn't report: no line, no legend item,
                # and it doesn't count as shown. Otherwise the legend decides.
                if legend is not None:
                    legend.set_available(i, is_reported)
                else:
                    graph.set_series_shown(i, is_reported)
            if legend is not None:
                legend.set_values([self._format(name, values.get(name)) for name, _ in series])
            self.boxes[title].set_info(self._info(title, s))
            graph.queue_draw()

    def _format(self, name: str, value) -> str:
        if value is None:
            return "—"
        if name in ("clock", "memory-clock"):
            return format_frequency(value * 1e6)
        return format_percent(value)

    def _info(self, title: str, s) -> str:
        if s is None:
            return ""
        if title == "GPU Utilization":
            return format_percent(s.usage)
        if title == "Video Engines":
            if s.encoder is None and s.decoder is None:
                return format_percent(s.video)
            return f"Encoder {format_percent(s.encoder)} · Decoder {format_percent(s.decoder)}"
        if title == "Video Memory" and s.vram_used is not None:
            base = Base(self.settings.get("base"))
            return f"{format_bytes(s.vram_used, base)} of {format_bytes(s.vram_total, base)}"
        if title == "Clocks":
            return format_frequency(s.clock_hz) + (f" · {s.pstate}" if s.pstate else "")
        if title == "Temperature":
            return format_temperature(s.temperature_c,
                                      TemperatureUnit(self.settings.get("temperature-unit")))
        if title == "Power":
            text = format_power(s.power_w)
            return text + (f" of {format_power(s.power_limit_w)}" if s.power_limit_w else "")
        if title == "Fan":
            return format_percent(s.fan)
        return ""


def create_views(backend, controller, services) -> DetailViews:
    view = NvidiaDetailsView(backend, services.settings)
    handler = backend.connect("updated", lambda _b: view.refresh())
    return DetailViews([DetailView("details", view, [])], [handler])
