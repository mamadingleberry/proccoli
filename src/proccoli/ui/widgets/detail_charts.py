"""A GPU *Details* tab built from a table of charts (was the NVIDIA
tab's own code).

``DetailChartsView`` is a ``ChartGridView`` with one ``ChartCard`` per
``GRAPHS`` entry, its lines drawn from the backend's ``history``. Every
refresh it asks the subclass for the latest ``values`` (``None`` until
the first reading), its ``caption_line`` and each card's ``info(title)``; a
measure the source doesn't report hides its line (and legend item), and a
card with nothing reported hides itself. The NVIDIA and AMD tabs are
subclasses; the Intel tab has its own engine-driven layout.
"""

from __future__ import annotations

from typing import Optional

from gi.repository import GLib

from ..axes import AxisGutter
from ..chart_settings import ChartSettings
from .chart_card import ChartCard
from .chart_grid import ChartGridView

# (title, [(series, legend name)], fixed max or None, min of an automatic
# max, relative height)
GraphSpec = tuple


class DetailChartsView(ChartGridView):
    GRAPHS: list[GraphSpec] = []

    def __init__(self, backend, charts: ChartSettings) -> None:
        super().__init__()
        self.backend = backend
        self.charts = charts
        self.gutter = AxisGutter(schedule=GLib.idle_add)
        self.boxes: dict[str, ChartCard] = {}
        self.legends: dict = {}
        for title, series, max_value, min_max, weight in self.GRAPHS:
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
        """Each measure's card (hidden when the source doesn't report it)."""
        return self.boxes

    # -- what subclasses provide -----------------------------------------------------------

    def values(self) -> Optional[dict]:
        """The latest reading by series name, or None before the first."""
        raise NotImplementedError

    def caption_line(self) -> str:
        return ""

    def info(self, title: str) -> str:
        """The text under a card's title (its main reading)."""
        return ""

    # -- refresh -----------------------------------------------------------------------------

    def refresh(self) -> None:
        """New reading: caption, values, which lines and cards show, redraw."""
        self.set_caption(self.caption_line())
        latest = self.values()
        values = latest or {}
        visibility_changed = False
        for title, series, _max, _min, _w in self.GRAPHS:
            card = self.boxes[title]
            reported = [values.get(name) is not None for name, _ in series]
            shown = latest is None or any(reported)
            if card.get_visible() != shown:
                card.set_visible(shown)
                visibility_changed = True
            legend = self.legends.get(title)
            if latest is not None:
                for i, is_reported in enumerate(reported):
                    # A measure the source doesn't report: no line, no legend
                    # item, and it doesn't count as shown. Otherwise the
                    # legend decides.
                    if legend is not None:
                        legend.set_available(i, is_reported)
                    else:
                        card.graph.set_series_shown(i, is_reported)
            units = [card.graph.series[i].unit for i in range(len(series))]
            card.set_values([self.charts.format_value(values.get(name), unit)
                             for (name, _), unit in zip(series, units)],
                            info=self.info(title) if latest is not None else "")
            card.graph.queue_draw()
        if visibility_changed:
            self.set_cards(self.cards)
