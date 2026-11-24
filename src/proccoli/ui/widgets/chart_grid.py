"""The GPU *Details* tabs' layout (Idea 4; the Intel tab's own grid from
Idea 3, moved here so every tab uses it).

``ChartGrid`` fits ``ChartCard``s into whatever space the window has:
instead of fixed graph heights and a fixed number of columns, it picks the
column count from the space it's given (snapped halves and quarters, small
screens, maximised windows on large displays) and shares the height
between the graphs, so everything stays in view. Only when even the most
compact arrangement doesn't fit does the page scroll. The arithmetic is in
``ui/layout.py`` (``split_columns``, ``extra_heights``, ``layout_quality``,
``choose_columns``), tested without a display.

``ChartGridView`` is the whole tab: a caption, the grid, an optional
placeholder while there's no data, in a scrolled window that goes compact
on short or narrow windows.
"""

from __future__ import annotations

from typing import Optional, Sequence

from gi.repository import Adw, Gdk, Gtk

from ..layout import (CHART_COLUMN_SPACING, CHART_MIN_COLUMN_WIDTH, CHART_ROW_SPACING,
                      GridItem, choose_columns, column_min, extra_heights, graph_cap,
                      layout_quality, split_columns)

COMPACT_CONDITIONS = ("max-height: 720sp", "max-width: 600sp")


class ChartGrid(Gtk.Widget):
    """Lays out ``ChartCard``s (anything with ``graph`` and ``min_height``)
    in as many columns as suit the space given, sharing spare height by
    weight; it scrolls only when even the most compact plan doesn't fit."""

    __gtype_name__ = "ProccoliChartGrid"

    def __init__(self) -> None:
        super().__init__()
        self.sections: list[Gtk.Widget] = []
        self.columns = 1
        self.set_hexpand(True)
        self.set_vexpand(True)

    def set_sections(self, sections: list[Gtk.Widget]) -> None:
        if sections == self.sections:
            return
        for s in self.sections:
            s.unparent()
        self.sections = list(sections)
        for s in self.sections:  # parent in order: focus follows reading order
            s.set_parent(self)
        self.queue_resize()

    def do_dispose(self) -> None:
        for s in self.sections:
            s.unparent()
        self.sections = []
        Gtk.Widget.do_dispose(self)

    # -- layout -------------------------------------------------------------

    def _max_columns(self, width: int) -> int:
        n = (width + CHART_COLUMN_SPACING) // (CHART_MIN_COLUMN_WIDTH + CHART_COLUMN_SPACING)
        return max(1, min(int(n), len(self.sections), 4))

    @staticmethod
    def _col_width(width: int, n: int) -> int:
        return max(1, (width - CHART_COLUMN_SPACING * (n - 1)) // n)

    def _plan(self, width: int, n: int):
        # Never narrower than a section can be (a chart's legend has a
        # minimum width): measuring below it is an error in GTK.
        narrowest = max(s.measure(Gtk.Orientation.HORIZONTAL, -1)[0] for s in self.sections)
        col_w = max(narrowest, self._col_width(width, n))
        items = []
        for s in self.sections:
            min_h = s.measure(Gtk.Orientation.VERTICAL, col_w)[0]
            floor = s.graph.measure(Gtk.Orientation.VERTICAL, col_w)[0]
            items.append(GridItem(min_h, floor, float(s.min_height)))
        cols = split_columns([i.min_h for i in items], n)
        return col_w, [[items[i] for i in c] for c in cols], cols

    def do_get_request_mode(self) -> Gtk.SizeRequestMode:
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        if not self.sections:
            return 0, 0, -1, -1
        if orientation == Gtk.Orientation.HORIZONTAL:
            sizes = [s.measure(orientation, -1) for s in self.sections]
            return max(m for m, _, _, _ in sizes), max(n for _, n, _, _ in sizes), -1, -1
        width = for_size
        if width < 0:
            width = max(s.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
                        for s in self.sections)
        # Minimum: the most compact arrangement this width allows.
        minimum = min(max(column_min(c) for c in self._plan(width, n)[1])
                      for n in range(1, self._max_columns(width) + 1))
        # Natural: one column at natural heights.
        natural = sum(s.measure(Gtk.Orientation.VERTICAL, width)[1]
                      for s in self.sections)
        natural += CHART_ROW_SPACING * (len(self.sections) - 1)
        return minimum, max(minimum, natural), -1, -1

    def do_size_allocate(self, width: int, height: int, _baseline: int) -> None:
        if not self.sections:
            return
        plans = {n: self._plan(width, n)
                 for n in range(1, self._max_columns(width) + 1)}
        n = choose_columns({n: layout_quality(p[1], p[0], height)
                            for n, p in plans.items()})
        self.columns = n
        col_w, item_cols, index_cols = plans[n]
        for c, (items, idxs) in enumerate(zip(item_cols, index_cols)):
            x = c * (col_w + CHART_COLUMN_SPACING)
            y = 0
            for item, extra, i in zip(items, extra_heights(items, height, graph_cap(col_w)),
                                      idxs):
                rect = Gdk.Rectangle()
                rect.x, rect.y, rect.width, rect.height = x, y, col_w, item.min_h + extra
                self.sections[i].size_allocate(rect, -1)
                y += rect.height + CHART_ROW_SPACING


class ChartGridView(Adw.BreakpointBin):
    """A Details tab: caption, ``ChartGrid`` of cards, and ``waiting``
    (shown instead of the grid until ``set_has_data(True)``)."""

    def __init__(self, waiting: Optional[Gtk.Widget] = None) -> None:
        super().__init__(width_request=320, height_request=200)
        self.compact = False
        self.cards: list = []
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                           margin_top=6, margin_bottom=18, margin_start=12, margin_end=18)
        self.caption = Gtk.Label(xalign=0, margin_top=6, wrap=True)
        for cls in ("dim-label", "caption", "device-caption"):
            self.caption.add_css_class(cls)
        self.box.append(self.caption)
        self.grid = ChartGrid()
        self.box.append(self.grid)
        self.waiting = waiting
        if waiting is not None:
            waiting.set_vexpand(True)
            self.box.append(waiting)
        self.set_child(Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                          child=self.box))
        for cond in COMPACT_CONDITIONS:
            bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(cond))
            bp.connect("apply", lambda *_: self.set_compact(True))
            bp.connect("unapply", lambda *_: self.set_compact(False))
            self.add_breakpoint(bp)

    def set_caption(self, text: str) -> None:
        if self.caption.get_label() != text:
            self.caption.set_label(text)

    def set_cards(self, cards: Sequence) -> None:
        """The cards to show, in order (hidden ones are left out)."""
        self.cards = list(cards)
        for card in self.cards:
            card.set_compact(self.compact)
        self.grid.set_sections([c for c in self.cards if c.get_visible()])

    def set_has_data(self, has_data: bool) -> None:
        self.grid.set_visible(has_data)
        if self.waiting is not None:
            self.waiting.set_visible(not has_data)

    def set_compact(self, compact: bool) -> None:
        if compact == self.compact:
            return
        self.compact = compact
        if compact:
            self.box.add_css_class("compact")
        else:
            self.box.remove_css_class("compact")
        self.caption.set_visible(not compact)
        self.box.set_margin_start(6 if compact else 12)
        self.box.set_margin_end(6 if compact else 18)
        for card in self.cards:
            card.set_compact(compact)
