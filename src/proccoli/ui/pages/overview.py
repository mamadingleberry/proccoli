"""The Overview page (DESIGN.md §9.6, Milestones 39 and 41): one card per
sidebar entry with a chart (every device; not Apps or Processes), in the
sidebar's order and colours. A card shows the entry's icon, name, usage
line and a chart of its sidebar series; clicking it opens that page.
Below the cards, the ten busiest apps and processes (``TopTables``).

The cards form an N × M grid that tries to fill the height the page
gives it (Milestone 50), each chart shorter than it is wide (Milestone
51): ``layout.plan_grid`` picks the columns and chart height for the
space left above the tables, on every size change.

The page knows nothing about the sidebar: the window hands it the entries
(``sync([(page, colour index), ...])``) whenever they change, and a
``navigate(page_id)`` callback. Cards read ``page.sidebar_summary()`` and
follow each page's ``summary-changed``, so any page with a summary works,
fakes included.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from gi.repository import Gtk, Pango

from ... import OVERVIEW_ICON
from ...core.profile import Profile
from ..chart_settings import ChartKind, ChartSettings
from ..layout import (GRID_MAX_RATIO, GRID_MIN_CHART, LIMITS, GridPlan, card_width,
                      needs_update, plan_grid)
from ..page import FittingPage, PageKind, ResourcePage, ScrollingPage, SidebarSummary
from ...core.units import Base, format_bytes, format_percent
from ...processes.top import TOP_COUNT, TopMetric, top_apps, top_processes
from ..widgets.graph import Graph, GraphStyle
from ..widgets.top_table import TopTable

CARD_MIN_WIDTH = LIMITS.min_width      # narrower cards would cramp the chart
CARD_PADDING = 12
CARD_SPACING = 12
CARD_START_CHART = 120                 # until the first fit
CARD_CHROME_H = 70                     # header and labels, until measured
CARD_CHROME_W = 2 * CARD_PADDING + 8   # margins, border, padding: until measured
MAX_COLUMNS = 4
TOP_TABLE_MIN_WIDTH = 340              # two tables side by side above 2 × this


class OverviewCard(Gtk.Box):
    """One entry: icon, name, usage line, chart (DESIGN.md §9.6)."""

    def __init__(self, page: ResourcePage, color: Optional[int],
                 charts: Optional[ChartSettings], chart: bool = True) -> None:
        """``chart=False``: name and readings only (Lightweight Mode)."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                         width_request=CARD_MIN_WIDTH)
        self.add_css_class("card")
        self.add_css_class("overview-card")
        for side in ("top", "bottom", "start", "end"):
            getattr(self, f"set_margin_{side}")(0)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                        margin_top=CARD_PADDING, margin_bottom=CARD_PADDING,
                        margin_start=CARD_PADDING, margin_end=CARD_PADDING)
        header = Gtk.Box(spacing=8)
        self.icon = Gtk.Image()
        self.title_label = Gtk.Label(xalign=0, hexpand=True,
                                     ellipsize=Pango.EllipsizeMode.END)
        self.title_label.add_css_class("heading")
        self.usage_label = Gtk.Label(xalign=1)
        self.usage_label.add_css_class("numeric")
        header.append(self.icon)
        header.append(self.title_label)
        header.append(self.usage_label)
        self.detail_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.detail_label.add_css_class("caption")
        self.detail_label.add_css_class("dim-label")
        # Current readings: temperature, GPU memory used / total (M57).
        self.facts_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                     visible=False)
        self.facts_label.add_css_class("caption")
        self.facts_label.add_css_class("numeric")
        self.graph: Optional[Graph] = None
        self.empty_label: Optional[Gtk.Label] = None
        if chart:
            self.graph = Graph(GraphStyle.NORMAL)
            self.graph.set_content_height(CARD_START_CHART)   # the page fits it
            self.empty_label = Gtk.Label(label="No data", vexpand=True,
                                         height_request=CARD_START_CHART)
            self.empty_label.add_css_class("dim-label")
        inner.append(header)
        inner.append(self.detail_label)
        inner.append(self.facts_label)
        if chart:
            inner.append(self.graph)
            inner.append(self.empty_label)
        self.append(inner)
        self.charts = charts            # axes, time span, hover units (Idea 4)
        self.page: Optional[ResourcePage] = None
        self._handler = 0
        if charts is not None and self.graph is not None:
            charts.bind(self.graph, ChartKind.CARD)
        self.set_page(page, color)

    @property
    def page_id(self) -> str:
        return self.page.page_id

    def set_page(self, page: ResourcePage, color: Optional[int]) -> None:
        if self.page is not page:
            self._disconnect()
            self.page = page
            self._handler = page.connect("summary-changed", lambda *_: self.update())
        self.icon.set_from_icon_name(page.icon_name)
        self.title_label.set_label(page.title)
        if self.graph is not None:
            self.graph.set_entry_color(color)
        self.update()

    def update(self) -> None:
        summary: Optional[SidebarSummary] = self.page.sidebar_summary()
        has_chart = summary is not None and summary.has_chart() and self.graph is not None
        if self.graph is not None:
            self.graph.set_visible(has_chart)
            self.empty_label.set_visible(not has_chart)
        usage = ""
        detail = self.page.description
        if summary is not None:
            usage = summary.usage_text or (f"{summary.usage:.0f} %"
                                           if summary.usage is not None else "")
            parts = [p for p in (summary.detail, self.page.description) if p]
            detail = " · ".join(parts)
        self.usage_label.set_label(usage)
        self.detail_label.set_label(detail)
        self.detail_label.set_visible(bool(detail))
        facts = " · ".join(summary.facts) if summary is not None else ""
        if self.facts_label.get_label() != facts:
            self.facts_label.set_label(facts)
        self.facts_label.set_visible(bool(facts))
        text = summary.text() if summary is not None else ""
        self.update_property([Gtk.AccessibleProperty.LABEL],
                             [f"{self.page.title}: {text}" if text else self.page.title])
        if has_chart:
            if self.graph.series != summary.series:
                self.graph.set_series(summary.series)
            if self.graph.max_value != summary.max_value:
                self.graph.set_max(summary.max_value)
            if self.get_mapped():
                self.graph.queue_draw()

    def set_chart_height(self, height: int) -> None:
        """The page's grid decides (Milestone 50); "No data" takes the
        same space, so cards stay alike."""
        if self.graph is not None and needs_update(self.graph.get_content_height(), height):
            self.graph.set_content_height(height)
            self.empty_label.set_size_request(-1, height)

    def cell(self) -> Gtk.Widget:
        """What the grid lays out: the FlowBox child around the card (it
        adds padding), or the card itself before it's in a grid."""
        return self.get_parent() or self

    def chrome_height(self, width: int) -> int:
        """The cell's height apart from its chart, at ``width``."""
        natural = self.cell().measure(Gtk.Orientation.VERTICAL, width)[1]
        if self.graph is None:
            return natural
        chart = self.graph if self.graph.get_visible() else self.empty_label
        return natural - chart.measure(Gtk.Orientation.VERTICAL, -1)[1]

    def min_width(self) -> int:
        return self.cell().measure(Gtk.Orientation.HORIZONTAL, -1)[0]

    def chrome_width(self, slot: float) -> Optional[int]:
        """The width of a ``slot``-wide grid column apart from the chart
        (the FlowBox child's margins, the card's border and padding), once
        laid out; None before."""
        chart = self.graph.get_width() if self.graph is not None else 0
        if slot > 0 and chart > 0 and self.graph.get_visible():
            return int(round(slot - chart))
        return None

    def _disconnect(self) -> None:
        if self.page is not None and self._handler:
            self.page.disconnect(self._handler)
        self._handler = 0

    def shutdown(self) -> None:
        self._disconnect()
        if self.charts is not None and self.graph is not None:
            self.charts.unbind(self.graph)


class TopTables(Gtk.Box):
    """Top apps and top processes (Milestone 41), ranked by
    ``overview-top-by``. Samples processes only while mapped
    (``monitor.acquire``/``release``, as the Apps and Processes pages do)."""

    def __init__(self, monitor, grouper, settings, navigate: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.monitor = monitor
        self.grouper = grouper
        self.settings = settings
        self._acquired = False
        self._handlers: list[tuple[object, int]] = []

        header = Gtk.Box(spacing=12)
        title = Gtk.Label(label="Busiest", xalign=0, hexpand=True)
        title.add_css_class("title-4")
        header.append(title)
        self.by_buttons: dict[TopMetric, Gtk.ToggleButton] = {}
        toggles = Gtk.Box()
        toggles.add_css_class("linked")
        first = None
        for metric, label in ((TopMetric.CPU, "Processor"), (TopMetric.MEMORY, "Memory")):
            button = Gtk.ToggleButton(label=label, group=first)
            first = first or button
            button.connect("toggled", self._on_toggle, metric)
            self.by_buttons[metric] = button
            toggles.append(button)
        toggles.update_property([Gtk.AccessibleProperty.LABEL], ["Rank by"])
        header.append(toggles)
        self.append(header)

        self.apps = TopTable("Apps", TOP_COUNT, lambda: navigate("apps"))
        self.processes = TopTable("Processes", TOP_COUNT, lambda: navigate("processes"))
        # Side by side when there's room; stacked on narrow (portrait) pages.
        # Not homogeneous: the shorter table mustn't leave a gap below itself.
        self.flow = Gtk.FlowBox(homogeneous=False, min_children_per_line=1,
                                max_children_per_line=2, column_spacing=12, row_spacing=12,
                                selection_mode=Gtk.SelectionMode.NONE)
        for table in (self.apps, self.processes):
            table.set_valign(Gtk.Align.START)
            table.set_size_request(TOP_TABLE_MIN_WIDTH, -1)
            self.flow.append(table)
            table.get_parent().set_focusable(False)       # rows take the focus
        self.append(self.flow)

        self._handlers.append((monitor, monitor.connect("updated", lambda *_: self.refresh())))
        self._handlers.append((settings, settings.connect_changed(
            "overview-top-by", lambda *_: self._sync_metric())))
        self._handlers.append((settings, settings.connect_changed(
            "base", lambda *_: self.refresh())))
        self._sync_metric()

    @property
    def metric(self) -> TopMetric:
        return TopMetric(self.settings.get("overview-top-by"))

    def _on_toggle(self, button: Gtk.ToggleButton, metric: TopMetric) -> None:
        if button.get_active() and self.metric != metric:
            self.settings.set("overview-top-by", metric.value)

    def _sync_metric(self) -> None:
        button = self.by_buttons[self.metric]
        if not button.get_active():
            button.set_active(True)
        for table in (self.apps, self.processes):
            table.set_sorted_by(self.metric.value)
        self.refresh()

    def refresh(self) -> None:
        processes = list(self.monitor.processes.values())
        base = Base(self.settings.get("base"))

        def row(item, icon):
            return (item.name, icon, format_percent(item.cpu), format_bytes(item.memory, base))
        self.apps.set_rows([row(a, a.icon) for a in
                            top_apps(self.grouper.group(processes).values(), self.metric)])
        self.processes.set_rows([row(p, self.grouper.icon_for(p)) for p in
                                 top_processes(processes, self.metric)])

    def start(self) -> None:
        if not self._acquired:
            self.monitor.acquire()
            self._acquired = True
            self.refresh()

    def stop(self) -> None:
        if self._acquired:
            self.monitor.release()
            self._acquired = False

    def shutdown(self) -> None:
        self.stop()
        for source, handler in self._handlers:
            source.disconnect(handler)
        self._handlers = []


class OverviewPage(FittingPage):
    """A grid of ``OverviewCard`` s that tries to fill the page (charts
    shorter than wide), then the top apps
    and processes (when there's a process monitor). The tables keep their
    natural height and the cards share what's left; when that would make
    the charts shorter than ``GRID_MIN_CHART``, the cards take the whole
    page and the tables scroll into view below them."""

    def __init__(self, settings, navigate: Callable[[str], None],
                 processes=None, grouper=None, profile: Optional[Profile] = None) -> None:
        """``profile``: Lightweight Mode makes it a list of names and
        readings, without charts or the busiest tables (Idea 1)."""
        super().__init__("overview", PageKind.OVERVIEW, "Overview", OVERVIEW_ICON)
        self.settings = settings
        self.profile = profile or Profile.full()
        self.navigate = navigate
        self.cards: dict[str, OverviewCard] = {}
        self.plan = GridPlan(1, 0, CARD_START_CHART)
        self._settling = False
        self.chrome_measured = False
        self.flow = Gtk.FlowBox(homogeneous=True, min_children_per_line=1,
                                max_children_per_line=1, column_spacing=CARD_SPACING,
                                row_spacing=CARD_SPACING, selection_mode=Gtk.SelectionMode.NONE,
                                activate_on_single_click=True, valign=Gtk.Align.START)
        if not self.profile.overview_charts:
            self.flow.set_max_children_per_line(3)     # a list in columns
        self.flow.connect("child-activated", self._on_activated)
        self.box.append(self.flow)
        self.empty = Gtk.Label(label="No devices yet", vexpand=True)
        self.empty.add_css_class("dim-label")
        self.box.append(self.empty)
        self.charts = ChartSettings(settings) if settings is not None else None
        # Without a process monitor (demo mode, tests) there are no tables.
        self.tops: Optional[TopTables] = None
        if processes is not None and grouper is not None and self.profile.overview_tables:
            self.tops = TopTables(processes, grouper, settings, navigate)
            self.box.append(self.tops)

    def do_map(self) -> None:
        ScrollingPage.do_map(self)
        if self.tops is not None:
            self.tops.start()

    def do_unmap(self) -> None:
        if self.tops is not None:
            self.tops.stop()
        ScrollingPage.do_unmap(self)

    def sync(self, entries: Sequence[tuple[ResourcePage, Optional[int]]]) -> None:
        """Show these ``(page, colour index)`` entries, in this order;
        pages with no summary at all (placeholders) are left out."""
        entries = [(p, c) for p, c in entries if p.sidebar_summary() is not None]
        wanted = [page.page_id for page, _ in entries]
        for page_id in [i for i in self.cards if i not in wanted]:
            card = self.cards.pop(page_id)
            card.shutdown()
            self.flow.remove(card.get_parent())
        for page, color in entries:
            card = self.cards.get(page.page_id)
            if card is None:
                card = self.cards[page.page_id] = OverviewCard(page, color, self.charts,
                                                                  self.profile.overview_charts)
                self.flow.append(card)
            else:
                card.set_page(page, color)
        # Reorder the FlowBox children to match.
        for index, page_id in enumerate(wanted):
            child = self.cards[page_id].get_parent()
            if child.get_index() != index:
                self.flow.remove(child)
                child.set_child(None)
                self.flow.insert(self.cards[page_id], index)
        self.empty.set_visible(not self.cards)
        self.flow.set_visible(bool(self.cards))

    def order(self) -> list[str]:
        """Card page IDs in display order."""
        out, child = [], self.flow.get_first_child()
        while child is not None:
            out.append(child.get_child().page_id)
            child = child.get_next_sibling()
        return out

    # -- the grid fills the page (Milestone 50) ---------------------------------------

    def fit_key(self) -> tuple:
        # The tables grow from "Waiting for data…" to ten rows, and the
        # cards come and go: either changes the space to share.
        # A card's readings line appears with its first data (M57): the
        # cards' chrome changes, so fit again then too.
        return (*self.viewport_size(), len(self.cards), self._tables_height(),
                sum(c.facts_label.get_visible() for c in self.cards.values()))

    def _tables_height(self) -> int:
        if self.tops is None or not self.tops.get_visible():
            return 0
        width = self.box.get_width()
        if width <= 0:
            return 0
        return self.tops.measure(Gtk.Orientation.VERTICAL, width)[1]

    def _chrome(self, card_width: int) -> int:
        """The cards' height apart from their charts (they're all alike)."""
        cards = [c for c in self.cards.values()
                 if c.graph is not None and c.graph.get_visible()] \
            or list(self.cards.values())
        if not cards or card_width <= 0:
            return CARD_CHROME_H
        return max(c.chrome_height(card_width) for c in cards)

    def grid_area(self, viewport_h: int, with_tables: bool) -> int:
        """Height the cards may fill: the viewport, less the column's
        margins and, ``with_tables``, the tables and the gap above them."""
        area = viewport_h - self.box.get_margin_top() - self.box.get_margin_bottom()
        tables = self._tables_height()
        if with_tables and tables:
            area -= tables + self.box.get_spacing()
        return area

    def plan_for(self, width: int, viewport_h: int) -> GridPlan:
        """The grid for a ``width``-wide column in a ``viewport_h`` page."""
        count = len(self.cards)
        min_width = max([CARD_MIN_WIDTH] + [c.min_width() for c in self.cards.values()])
        # The chart's real width, so "shorter than wide" holds on screen
        # (M51). Before the first layout it's estimated, and the page fits
        # again once laid out.
        slot = card_width(self.flow.get_width(), self.flow.get_max_children_per_line(),
                          CARD_SPACING)
        measured = [w for w in (c.chrome_width(slot) for c in self.cards.values()) if w]
        self.chrome_measured = bool(measured)
        chrome_w = max(measured) if measured else CARD_CHROME_W
        rough = plan_grid(count, width, self.grid_area(viewport_h, True), CARD_SPACING,
                          chrome_w, CARD_CHROME_H, MAX_COLUMNS, min_width)
        if not rough.columns:
            return rough
        chrome = self._chrome(int(card_width(width, rough.columns, CARD_SPACING)))

        def plan(with_tables: bool) -> GridPlan:
            return plan_grid(count, width, self.grid_area(viewport_h, with_tables),
                             CARD_SPACING, chrome_w, chrome, MAX_COLUMNS,
                             min_width, GRID_MIN_CHART, max_ratio=GRID_MAX_RATIO)
        best = plan(True)
        if best.chart_height <= GRID_MIN_CHART and self._tables_height():
            best = plan(False)          # too cramped: the tables go below the fold
        return best

    def fit(self, _vw: int, vh: int) -> bool:
        if not self.profile.overview_charts:       # a plain list: nothing to fit
            return False
        width = self.box.get_width()
        if not self.cards or width <= 0 or vh <= 0:
            return False
        plan = self.plan_for(width, vh)
        changed = plan.columns != self.plan.columns
        self.plan = plan
        if changed:
            # Only the maximum: the plan's cards fit, so the FlowBox fills
            # each line, and its minimum width stays one card's, so the
            # window can still be made narrower.
            self.flow.set_max_children_per_line(plan.columns)
        for card in self.cards.values():
            card.set_chart_height(plan.chart_height)
        # New columns change the cards' width (and so their measured
        # chrome), and a first fit only estimated the chart's width: fit
        # once more after layout, but only once, so rounding can never make
        # the column count flip back and forth.
        again = (changed or not self.chrome_measured) and not self._settling
        self._settling = again
        return again

    def _on_activated(self, _flow, child: Gtk.FlowBoxChild) -> None:
        self.navigate(child.get_child().page_id)

    def shutdown(self) -> None:
        for card in self.cards.values():
            card.shutdown()
        if self.charts is not None:
            self.charts.release()
        if self.tops is not None:
            self.tops.shutdown()
        super().shutdown()
