"""A chart in a card: the GPU *Details* tabs' one building block.

``ChartCard`` is a ``card`` box around a ``LegendChart`` (title, graph,
legend, info line, the same ``GraphPane`` as device pages), so spacing,
legend clicks and hover are the same everywhere. One rule for legends: a
chart with two or more lines shows its legend (each line's value in it);
a one-line chart shows none, and its value goes in the info line
(``set_values`` does both). ``ChartGrid`` reads ``graph`` (its floor) and
``min_height`` (its share of spare height). ``set_compact`` makes it
denser for short windows: a lower floor, no info line, the legend's values
only on hover.

Use::

    card = ChartCard("Clocks", max_value=None, min_max=1000.0, weight=140)
    charts.bind(card.graph) # ui.chart_settings
    card.set_lines(series, ["Graphics", "Memory"])
    card.set_values(["1.5 GHz", "7 GHz"]) # each refresh
"""

from __future__ import annotations

from typing import Optional, Sequence

from gi.repository import Gtk

from ...core.history import Series
from .legend_chart import LegendChart

GRAPH_FLOOR = 64
GRAPH_FLOOR_COMPACT = 56      # room for a plot between the axis labels


class ChartCard(Gtk.Box):
    def __init__(self, title: str, max_value: Optional[float] = 100.0,
                 min_max: float = 0.0, description: str = "", weight: float = 130) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("card")
        self.add_css_class("chart-card")
        self.title = title
        self.description = description
        self.min_height = weight
        self.compact = False
        self.chart = LegendChart(title, max_value=max_value, min_max=min_max)
        self.chart.set_vexpand(True)
        self.graph = self.chart.graph
        self.legend = self.chart.legend
        self.graph.set_vexpand(True)
        self.graph.set_content_height(GRAPH_FLOOR)
        self.legend.set_visible(False)
        if description:
            self.set_tooltip_text(description)
        self.info = description
        self.chart.set_info(description)
        self.append(self.chart)

    @property
    def lines(self) -> int:
        return len(self.graph.series)

    def set_lines(self, series: Sequence[Series], names: Sequence[str]) -> None:
        """The lines and their names; a legend only for two or more."""
        self.chart.set_lines(series, names)
        self.legend.set_visible(len(series) > 1)

    def set_values(self, texts: Sequence[str], info: Optional[str] = None) -> None:
        """Each line's current value: in the legend, or for one line in
        the info line (unless ``info`` is given, which always goes there)."""
        self.chart.set_values(texts)
        if info is None:
            info = texts[0] if self.lines == 1 and texts else self.description
        self.set_info(info)

    def set_info(self, text: str) -> None:
        self.info = text
        self.chart.set_info(text)

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        self.graph.set_content_height(GRAPH_FLOOR_COMPACT if compact else GRAPH_FLOOR)
        self.chart.pane.info_label.set_visible(not compact)
        self.legend.set_compact(compact)
