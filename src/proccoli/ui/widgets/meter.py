"""The usage meter shown in sidebar items: a small area chart (the default,
as in Resources) or a slim progress bar, chosen by the *Sidebar Meter Type*
preference."""

from __future__ import annotations

from enum import Enum
from typing import Optional, Sequence

from gi.repository import Gtk

from ...core.history import Series
from ..theme import ENTRY_CSS_COUNT
from .graph import Graph, GraphStyle


METER_HEIGHT = 36             # the chart alone
METER_HEIGHT_WITH_AXES = 52   # plus a row of time labels


class MeterType(str, Enum):
    PROGRESS_BAR = "progress-bar"   # settings nicks
    GRAPH = "graph"


class Meter(Gtk.Stack):
    def __init__(self, meter_type: MeterType = MeterType.GRAPH,
                 max_value: Optional[float] = 100.0) -> None:
        super().__init__(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.progress = Gtk.ProgressBar(valign=Gtk.Align.CENTER)
        self.progress.add_css_class("slim")
        self.graph = Graph(GraphStyle.SMALL, max_value)
        self.add_named(self.progress, MeterType.PROGRESS_BAR.value)
        self.add_named(self.graph, MeterType.GRAPH.value)
        self.set_meter_type(meter_type)

    @property
    def meter_type(self) -> MeterType:
        return MeterType(self.get_visible_child_name())

    def set_meter_type(self, meter_type) -> None:
        self.set_visible_child_name(MeterType(meter_type).value)

    def set_fraction(self, fraction: Optional[float]) -> None:
        """0..1, or None for no data (empty bar)."""
        f = 0.0 if fraction is None else min(max(fraction, 0.0), 1.0)
        self.progress.set_fraction(f)

    def set_series(self, series: Sequence[Series]) -> None:
        self.graph.set_series(list(series))

    def set_show_axes(self, show: bool) -> None:
        """Axes need room: the chart grows by a label row when they're on."""
        self.graph.set_show_axes(show)
        self.graph.set_content_height(METER_HEIGHT_WITH_AXES if show else METER_HEIGHT)

    def set_entry_color(self, index) -> None:
        """Chart and progress bar in the colour of sidebar entry ``index``
        (``.entry-color-<i>`` comes from ``ThemeCss``)."""
        for cls in [c for c in self.progress.get_css_classes() if c.startswith("entry-color-")]:
            self.progress.remove_css_class(cls)
        if index is not None:
            self.progress.add_css_class(f"entry-color-{index % ENTRY_CSS_COUNT}")
        self.graph.set_entry_color(index)

    def refresh(self) -> None:
        self.graph.queue_draw()
