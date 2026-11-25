"""The one place graphs get their preferences (Idea 4, DESIGN.md §9.1).

``ChartSettings(settings)`` applies *Show Graph Axes*, *Show Graph Grids*,
*Graph Time Range* (with the refresh speed) and the unit preferences
(*Data Unit Prefix*, *Show Network Speeds in Bits*, *Temperature Unit*) to
the graphs bound to it, now and on every change:

- ``bind(graph, kind)``: ``PAGE`` graphs (device pages, the GPU *Details*
  tabs) get axes, grids, the time span, a value axis in the user's units
  for any unit (``core.units.format_axis_label``, rounded in that unit),
  the hover box in the user's units, and the owner's entry color;
  ``CARD`` graphs (Overview cards) get axes, the time span and the hover
  box; ``METER`` graphs (sidebar meters) axes and the time span only.
- ``format_value(value, unit)`` / ``format_reading(graph, index, value)``:
  any reading in the user's units, for legends and info lines.
- ``set_entry_base(index)``: the owner's sidebar color, for its ``PAGE``
  graphs (a page's charts start at its entry's color).
- ``release()`` disconnects it; each owner (a page, the sidebar, a GPU
  page's detail tabs) has its own and releases it with its graphs.

``tests/test_static.py`` checks that no other view reads the graph keys.
"""

from __future__ import annotations

import weakref
from enum import Enum
from typing import Callable, Optional

from ..core.ticker import time_range_s
from ..core.units import (Base, TemperatureUnit, format_axis_label, format_reading,
                          nice_max_in_units)
from .axes import AxisGutter

GRAPH_KEYS = ("show-graph-axes", "show-graph-grids", "graph-time-range", "update-interval")
UNIT_KEYS = ("base", "network-bits", "temperature-unit")


class ChartKind(str, Enum):
    PAGE = "page"        # device pages and the GPU Details tabs
    CARD = "card"        # Overview cards
    METER = "meter"      # sidebar meters


class _Binding:
    __slots__ = ("kind", "bits", "show_axes")

    def __init__(self, kind: ChartKind, bits: bool,
                 show_axes: Optional[Callable[[bool], None]]) -> None:
        self.kind, self.bits, self.show_axes = kind, bits, show_axes


class ChartSettings:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.entry_base: Optional[int] = None
        self._bound: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()
        self._handlers = [settings.connect_changed(key, lambda *_: self.apply_all())
                          for key in GRAPH_KEYS + UNIT_KEYS]

    # -- preferences ---------------------------------------------------------------

    @property
    def show_axes(self) -> bool:
        return bool(self.settings.get("show-graph-axes"))

    @property
    def show_grid(self) -> bool:
        return bool(self.settings.get("show-graph-grids"))

    @property
    def span_s(self) -> float:
        """Seconds a full graph shows: the *Graph Time Range* (M58)."""
        return float(time_range_s(self.settings.get("graph-time-range")))

    @property
    def base(self) -> Base:
        return Base(self.settings.get("base"))

    @property
    def temperature(self) -> TemperatureUnit:
        return TemperatureUnit(self.settings.get("temperature-unit"))

    @property
    def network_bits(self) -> bool:
        return bool(self.settings.get("network-bits"))

    # -- binding ----------------------------------------------------------------------

    def bind(self, graph, kind: ChartKind = ChartKind.PAGE, rates_in_bits: bool = False,
             gutter: Optional[AxisGutter] = None,
             show_axes: Optional[Callable[[bool], None]] = None):
        """Apply the preferences to ``graph`` now and on every change.
        ``rates_in_bits``: *Show Network Speeds in Bits* applies (network
        pages). ``gutter`` lines up value axes with other graphs.
        ``show_axes(on)`` replaces ``graph.set_show_axes`` (a meter grows
        a label row)."""
        kind = ChartKind(kind)
        self._bound[graph] = _Binding(kind, rates_in_bits, show_axes)
        if graph.hover:
            graph.set_hover(True, lambda i, v, g=graph: self.format_reading(g, i, v))
        if kind == ChartKind.PAGE:
            graph.set_axis_format(lambda v, g=graph: self.axis_label(g, v), gutter)
            graph.nice_max = lambda peak, g=graph: self.nice_max(g, peak)
            graph.set_entry_base(self.entry_base)
        self.apply(graph)
        return graph

    def unbind(self, graph) -> None:
        self._bound.pop(graph, None)

    def bound(self) -> list:
        return list(self._bound.keys())

    def apply(self, graph) -> None:
        binding = self._bound.get(graph)
        if binding is None:
            return
        (binding.show_axes or graph.set_show_axes)(self.show_axes)
        graph.set_time_span(self.span_s)
        if binding.kind == ChartKind.PAGE:
            graph.set_show_grid(self.show_grid)
        graph.queue_draw()           # units may have changed

    def apply_all(self) -> None:
        for graph in self.bound():
            self.apply(graph)

    def set_entry_base(self, index: Optional[int]) -> None:
        self.entry_base = index
        for graph, binding in list(self._bound.items()):
            if binding.kind == ChartKind.PAGE:
                graph.set_entry_base(index)

    def release(self) -> None:
        for handler in self._handlers:
            self.settings.disconnect(handler)
        self._handlers = []
        self._bound.clear()

    # -- formats ------------------------------------------------------------------------

    def _bits(self, graph) -> bool:
        binding = self._bound.get(graph)
        return bool(binding and binding.bits and self.network_bits)

    @staticmethod
    def _unit(graph, index: int = 0) -> str:
        series = graph.series
        return series[index].unit if index < len(series) else ""

    def format_value(self, value: Optional[float], unit: str, bits: bool = False) -> str:
        """Any reading in the user's units (legends, info lines)."""
        return format_reading(value, unit, self.base, bits and self.network_bits,
                              self.temperature)

    def format_reading(self, graph, index: int, value: Optional[float]) -> str:
        """Series ``index`` of ``graph`` at ``value``: the hover box."""
        return format_reading(value, self._unit(graph, index), self.base, self._bits(graph),
                              self.temperature)

    def axis_label(self, graph, value: float) -> str:
        return format_axis_label(value, self._unit(graph), self.base, self._bits(graph),
                                 self.temperature)

    def nice_max(self, graph, peak: float) -> float:
        return nice_max_in_units(peak, self._unit(graph), self.base, self._bits(graph))
