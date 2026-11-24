"""Base class of every device page (Processor, Memory, Drive, ...).

Handles what all of them share: following the graph and unit preferences,
redrawing only while visible, the sidebar summary, and the Properties group.
Subclasses build their groups in ``__init__`` and fill labels in
``update_labels()``.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional

from gi.repository import Adw, GLib, Gtk

from ...core.units import Base, TemperatureUnit
from ...devices.base import Monitor, Snapshot
from ..page import FittingPage, PageKind, ScrollingPage, SidebarSummary
from ..axes import history_span_s
from ..layout import LIMITS, GraphLimits, fit_heights, group_rows, needs_update, stack_pair
from ..widgets.graph import Graph, GraphStyle
from ..widgets.double_graph_box import SPACING as PAIR_SPACING, DoubleGraphBox
from ..widgets.graph_box import GraphBox
from ..widgets.info_row import InfoRow

# Preferences that change how values are formatted.
UNIT_KEYS = ("base", "network-bits", "temperature-unit")


class DevicePage(FittingPage):
    def __init__(self, monitor: Monitor, settings, kind: PageKind,
                 sort_name: str = "", title: Optional[str] = None) -> None:
        info = monitor.info
        super().__init__(info.id, kind, title or info.name, info.icon_name,
                         description=info.description, sort_name=sort_name)
        self.monitor = monitor
        self.settings = settings
        self.graphs: list[Graph] = []
        self.pairs: list[DoubleGraphBox] = []
        self.limits: GraphLimits = LIMITS
        self.entry_index: Optional[int] = None    # set by the sidebar
        self.track(settings, settings.connect_changed(
            "show-graph-grids", lambda _k, v: self._set_grid(v)))
        for key in ("graph-data-points", "refresh-speed", "show-graph-axes"):
            self.track(settings, settings.connect_changed(key, lambda *_: self._set_axes()))
        for key in UNIT_KEYS:
            self.track(settings, settings.connect_changed(key, lambda *_: self.refresh_labels()))
        self.track(monitor, monitor.connect("updated", self._on_updated))

    # -- building blocks --------------------------------------------------------

    def add_banner(self, title: str = "", button_label: str = "") -> Adw.Banner:
        """An Adw.Banner fixed above the scrolling content."""
        banner = Adw.Banner(title=title, button_label=button_label)
        content = self.get_child()
        self.set_child(None)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(banner)
        outer.append(content)
        self.set_child(outer)
        return banner

    def set_entry_color(self, index: Optional[int]) -> None:
        """The sidebar gave this page's entry colour ``index``: the page's
        graphs start at the same colour (DESIGN.md §9.3)."""
        self.entry_index = index
        for g in self.graphs:
            g.set_entry_base(index)

    def add_graph(self, graph: Graph) -> Graph:
        graph.set_show_grid(self.settings.get("show-graph-grids"))
        graph.set_show_axes(self.settings.get("show-graph-axes"))
        graph.set_time_span(history_span_s(self.settings))
        graph.set_entry_base(self.entry_index)
        self.graphs.append(graph)
        return graph

    def graph_box(self, group: Adw.PreferencesGroup, title: str,
                  series: Iterable[tuple[str, str]], max_value: Optional[float] = 100.0,
                  min_max: float = 0.0, color_offset: int = 0) -> GraphBox:
        """A GraphBox plotting history series ``[(name, unit), ...]``."""
        box = GraphBox(title, max_value=max_value, min_max=min_max)
        box.set_series([self.monitor.history.define(n, u) for n, u in series],
                       color_offset=color_offset)
        self.add_graph(box.graph)
        group.add(box)
        return box

    def add_pair(self, group: Adw.PreferencesGroup, pair: DoubleGraphBox) -> DoubleGraphBox:
        """A DoubleGraphBox; it stacks on narrow or portrait pages."""
        for g in pair.graphs:
            self.add_graph(g)
        self.pairs.append(pair)
        group.add(pair)
        return pair

    def add_properties(self, properties: Mapping[str, str],
                       title: str = "Properties") -> Adw.PreferencesGroup:
        group = self.add_group(title)
        self.property_rows = {}
        for key, value in properties.items():
            row = InfoRow(key, value)
            self.property_rows[key] = row
            group.add(row)
        return group

    # -- preferences -------------------------------------------------------------

    @property
    def base(self) -> Base:
        return Base(self.settings.get("base"))

    @property
    def temperature_unit(self) -> TemperatureUnit:
        return TemperatureUnit(self.settings.get("temperature-unit"))

    @property
    def network_bits(self) -> bool:
        return self.settings.get("network-bits")

    # -- updates ---------------------------------------------------------------------

    def update_labels(self, snapshot: Snapshot) -> None:
        """Fill labels from the latest snapshot (subclasses)."""

    def refresh_labels(self) -> None:
        if self.monitor.latest is not None:
            self.update_labels(self.monitor.latest)

    def redraw(self) -> None:
        for g in self.graphs:
            g.queue_draw()

    def sidebar_summary(self) -> Optional[SidebarSummary]:
        snap = self.monitor.latest
        series = [self.monitor.history.series("usage")]
        if snap is None:
            return SidebarSummary(series=series)
        return SidebarSummary(snap.usage, snap.usage_text, snap.detail_text, series)

    def _set_axes(self) -> None:
        show, span = self.settings.get("show-graph-axes"), history_span_s(self.settings)
        for g in self.graphs:
            g.set_show_axes(show)
            g.set_time_span(span)
        self.redraw()

    def _set_grid(self, show: bool) -> None:
        for g in self.graphs:
            g.set_show_grid(show)

    def _on_updated(self, _monitor, snapshot: Snapshot) -> None:
        self.update_labels(snapshot)
        if self.get_mapped():   # hidden pages record history but don't redraw
            self.redraw()
        self.summary_changed()

    def do_map(self) -> None:
        ScrollingPage.do_map(self)
        self.redraw()           # catch up on what was recorded while hidden

    # -- graphs fill the page (DESIGN.md §9.1) -------------------------------------

    def fitting_graphs(self) -> list[Graph]:
        """The page graphs that share the height: normal-size, on screen."""
        return [g for g in self.graphs
                if g.style == GraphStyle.NORMAL and g.is_drawable()]

    def fit(self, vw: int, vh: int) -> bool:
        if self._arrange_pairs(vw, vh):
            return True          # the rows changed: fit again once laid out
        graphs = self.fitting_graphs()
        if not graphs:
            return False
        bounds = [g.compute_bounds(self.box) for g in graphs]
        if any(not ok for ok, _ in bounds):
            return False
        rows = group_rows([b.get_y() for _, b in bounds])
        current = [max(graphs[i].get_content_height() for i in r) for r in rows]
        widths = [min(bounds[i][1].get_width() for i in r) for r in rows]
        bottom = 0.0
        for g in graphs:      # the lowest graph row, with its title and info
            row = g.get_ancestor(Adw.PreferencesRow) or g
            ok, b = row.compute_bounds(self.box)
            if ok:
                bottom = max(bottom, b.get_y() + b.get_height())
        # Everything down to the last graph row, minus the graphs themselves,
        # plus the column's top and bottom margins.
        fixed = bottom - sum(current) + self.box.get_margin_top() \
            + self.box.get_margin_bottom()
        targets = fit_heights(vh, fixed, widths, self.limits)
        for r, target in zip(rows, targets):
            for i in r:
                if needs_update(graphs[i].get_content_height(), target):
                    graphs[i].set_content_height(target)
        return False

    def _arrange_pairs(self, viewport_w: int, viewport_h: int) -> bool:
        """Stack or unstack pairs for this viewport; True if any changed."""
        changed = False
        for pair in self.pairs:
            if not pair.get_visible():
                continue
            width = pair.box.get_width() or self.box.get_width()
            changed |= pair.set_stacked(stack_pair(width, viewport_w, viewport_h,
                                                   PAIR_SPACING, self.limits))
        return changed

