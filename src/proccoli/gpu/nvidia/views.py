"""The NVIDIA Details tab (Milestone 55): what nvidia-settings or nvidia-smi
reports, as graphs over time.

A caption names the GPU, its driver and the tool in use (and why that one),
then a card per measure: utilisation (graphics, memory controller, PCIe),
video engines, video memory, clocks, temperature, power and fan. Since
Idea 4 they're the shared ``ChartCard``s in a ``ChartGridView``, like the
Intel tab: they fill the window in columns, follow every chart preference
live, and show readings in the user's units. Cards with several lines get
a legend. A measure the tool doesn't report hides its line, or its card.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib  # noqa: E402

from ...core.units import format_bytes, format_frequency, format_percent, format_power  # noqa: E402
from ...ui.axes import AxisGutter  # noqa: E402
from ...ui.chart_settings import ChartSettings  # noqa: E402
from ...ui.widgets.chart_card import ChartCard  # noqa: E402
from ...ui.widgets.chart_grid import ChartGridView  # noqa: E402
from ..backend import DetailView, DetailViews  # noqa: E402

# (title, [(series, legend name)], fixed max or None, min of an automatic
# max, relative height)
GRAPHS = [
    ("GPU Utilization", [("graphics", "Graphics"), ("memory-controller", "Memory Controller"),
                         ("pcie", "PCIe")], 100.0, 0.0, 200),
    ("Video Engines", [("encoder", "Encoder"), ("decoder", "Decoder")], 100.0, 0.0, 140),
    ("Video Memory", [("vram", "Used")], 100.0, 0.0, 110),
    ("Clocks", [("clock", "Graphics"), ("memory-clock", "Memory")], None, 1e9, 140),
    ("Temperature", [("temperature", "GPU")], None, 100.0, 110),
    ("Power", [("power", "Draw")], None, 10.0, 110),
    ("Fan", [("fan", "Speed")], 100.0, 0.0, 110),
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


class NvidiaDetailsView(ChartGridView):
    def __init__(self, backend, charts: ChartSettings) -> None:
        super().__init__()
        self.backend = backend
        self.charts = charts
        self.gutter = AxisGutter(schedule=GLib.idle_add)
        self.boxes: dict[str, ChartCard] = {}
        self.legends: dict = {}
        for title, series, max_value, min_max, weight in GRAPHS:
            card = ChartCard(title, max_value=max_value, min_max=min_max, weight=weight)
            card.set_lines([backend.history.series(name) for name, _ in series],
                           [label for _, label in series])
            charts.bind(card.graph, gutter=self.gutter)
            if len(series) > 1:
                self.legends[title] = card.legend
            self.boxes[title] = card
        self.set_cards(list(self.boxes.values()))
        self.refresh()

    @property
    def groups(self) -> dict[str, ChartCard]:
        """Each measure's card (hidden when the tool doesn't report it)."""
        return self.boxes

    def refresh(self) -> None:
        """New reading: captions, values, which lines and cards show, redraw."""
        self.set_caption(caption_text(self.backend))
        s = self.backend.sample
        values = s.history_values() if s else {}
        visibility_changed = False
        for title, series, _max, _min, _w in GRAPHS:
            card = self.boxes[title]
            reported = [values.get(name) is not None for name, _ in series]
            shown = s is None or any(reported)
            if card.get_visible() != shown:
                card.set_visible(shown)
                visibility_changed = True
            legend = self.legends.get(title)
            for i, is_reported in enumerate(reported):
                if s is None:
                    continue
                # A measure the tool doesn't report: no line, no legend item,
                # and it doesn't count as shown. Otherwise the legend decides.
                if legend is not None:
                    legend.set_available(i, is_reported)
                else:
                    card.graph.set_series_shown(i, is_reported)
            units = [card.graph.series[i].unit for i in range(len(series))]
            card.set_values([self.charts.format_value(values.get(name), unit)
                             for (name, _), unit in zip(series, units)],
                            info=self._info(title, s))
            card.graph.queue_draw()
        if visibility_changed:
            self.set_cards(self.cards)

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
            base = self.charts.base
            return f"{format_bytes(s.vram_used, base)} of {format_bytes(s.vram_total, base)}"
        if title == "Clocks":
            return format_frequency(s.clock_hz) + (f" · {s.pstate}" if s.pstate else "")
        if title == "Temperature":
            return self.charts.format_value(s.temperature_c, "°C")
        if title == "Power":
            text = format_power(s.power_w)
            return text + (f" of {format_power(s.power_limit_w)}" if s.power_limit_w else "")
        if title == "Fan":
            return format_percent(s.fan)
        return ""


def create_views(backend, controller, services) -> DetailViews:
    view = NvidiaDetailsView(backend, services.charts or ChartSettings(services.settings))
    handler = backend.connect("updated", lambda _b: view.refresh())
    return DetailViews([DetailView("details", view, [])], [handler])
