"""A reusable chart of many lines with a legend inside its card
(Milestone 59; first made for the per-CPU chart, M55–M58).

``LegendChart`` is a ``GraphBox`` whose graph draws lines only (filled
areas would muddy many lines), each in its own colour (however many), with
a ``Legend`` under the graph inside the same card:

- left-click an item hides or shows its line, right-click shows only it
  (again: all); the chart never shows nothing (``series_visibility``);
- the legend counts as part of the chart's area: on a ``DevicePage``,
  ``add_legend_chart`` registers it, so the chart and its legend together
  get the area a plain graph would (``legend_height``);
- when the values in the legend would leave the graph under ``comfort``
  pixels, the legend goes compact: swatch and name, the value on hover
  (``fit_legend``; ``layout.use_compact_legend``).

Standalone (outside a ``DevicePage``) it's an ordinary card: nothing fits
it, and its legend keeps its values.

Use::

    chart = page.add_legend_chart(group, "Usage per Logical CPU")
    chart.set_lines(series, ["CPU 0", "CPU 1", ...])
    chart.set_values(["12 %", "3.0 %", ...])      # each refresh
"""

from __future__ import annotations

from typing import Optional, Sequence

from gi.repository import Gtk

from ...core.history import Series
from ..layout import COMFORT_GRAPH, use_compact_legend
from .graph_box import GraphBox
from .legend import Legend


class LegendChart(GraphBox):
    def __init__(self, title: str = "", max_value: Optional[float] = 100.0,
                 min_max: float = 0.0, fill: bool = False, distinct: bool = True,
                 comfort: int = COMFORT_GRAPH) -> None:
        super().__init__(title, max_value=max_value, min_max=min_max)
        self.graph.set_fill(fill)
        self.graph.set_distinct_colors(distinct)
        self.legend = Legend(self.graph)
        self.pane.set_footer(self.legend)
        self.comfort = comfort                # the graph's comfortable height
        self._full_legend: dict[int, int] = {}   # width -> legend height with values

    def set_lines(self, series: Sequence[Series], names: Sequence[str]) -> None:
        """The lines and their legend names (kept if unchanged)."""
        if list(series) != self.graph.series:
            self.set_series(list(series))
        self.legend.set_names(list(names))

    def set_values(self, texts: Sequence[str]) -> None:
        """Each line's current value, in the legend."""
        self.legend.set_values(texts)

    def legend_height(self, width: int) -> int:
        """The legend's height at ``width``, with the gap above it: what
        the chart's area holds besides the graph."""
        if not self.legend.get_visible() or not self.legend.items:
            return 0
        return self.legend.measure(Gtk.Orientation.VERTICAL, width)[1] \
            + self.pane.get_spacing()

    def fit_legend(self) -> bool:
        """Values in the legend only if the graph keeps ``comfort`` pixels
        of its area; True when the legend changed (fit again). The area
        doesn't depend on the legend, so this settles."""
        graph = self.graph
        if not graph.get_mapped():
            return False
        width = graph.get_width()
        if not self.legend.compact:
            self._full_legend[width] = self.legend_height(width)
        full = self._full_legend.get(width)
        if full is None:                      # a new width: measure it with values
            self.legend.set_compact(False)
            return True
        area = graph.get_content_height() + self.legend_height(width)
        compact = use_compact_legend(area, full, self.comfort)
        if compact == self.legend.compact:
            return False
        self.legend.set_compact(compact)
        return True
