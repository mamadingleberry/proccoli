"""Container that fits the graph sections into whatever space the window has.

Instead of fixed graph heights and a fixed number of columns, the grid picks
the column count from the space it is actually given (snapped halves and
quarters, small screens, maximised windows on large displays) and shares the
height between the graphs, so everything stays in view.  Only when even the
most compact arrangement does not fit does the page start to scroll.
"""

from __future__ import annotations

from itertools import combinations
from typing import NamedTuple, Optional, Sequence

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from ...ui.layout import LIMITS, GraphLimits  # noqa: E402

COLUMN_SPACING = 18
ROW_SPACING = 6
MIN_COLUMN_WIDTH = 300
# A graph taller than width / ASPECT is not more useful than a wider one.
ASPECT = 3.0
# Prefer fewer columns unless more of them are clearly better.
FEWER_COLUMNS_BIAS = 0.85


class Item(NamedTuple):
    min_h: int       # minimum height of the whole section at the column width
    floor: int       # minimum height of its graph
    weight: float    # share of spare height the graph gets


def split_columns(heights: Sequence[float], columns: int) -> list[list[int]]:
    """Split items (by index, kept in order) into at most ``columns``
    consecutive runs so that the tallest run is as short as possible."""
    n = len(heights)
    if columns <= 1 or n <= 1:
        return [list(range(n))]
    columns = min(columns, n)
    best = None
    # A handful of sections and columns: trying every set of cuts is cheap.
    for cuts in combinations(range(1, n), columns - 1):
        bounds = (0, *cuts, n)
        runs = [list(range(bounds[i], bounds[i + 1])) for i in range(columns)]
        tallest = max(sum(heights[i] for i in r) + ROW_SPACING * (len(r) - 1)
                      for r in runs)
        if best is None or tallest < best[0]:
            best = (tallest, runs)
    return best[1]


def column_min(items: Sequence[Item]) -> int:
    return sum(i.min_h for i in items) + ROW_SPACING * max(0, len(items) - 1)


def graph_cap(col_w: float, limits: GraphLimits = LIMITS) -> int:
    """The tallest a graph in a column ``col_w`` wide gets (DESIGN.md §9.1):
    on a portrait screen one column is narrow but very tall."""
    return min(limits.max_height, int(col_w * limits.max_ratio))


def extra_heights(items: Sequence[Item], height: int,
                  cap: Optional[int] = None) -> list[int]:
    """Spare height of a column, shared out by weight; with ``cap``, no
    graph grows past it, and what it can't take goes to the others (any
    rest is left empty at the bottom)."""
    spare = max(0, height - column_min(items))
    room = [float("inf") if cap is None else max(0, cap - i.floor) for i in items]
    out = [0.0] * len(items)
    open_items = {k for k in range(len(items)) if room[k] > 0}
    while open_items and spare > 0.5:
        total = sum(items[k].weight for k in open_items) or 1.0
        give = {k: spare * items[k].weight / total for k in open_items}
        full = [k for k in open_items if out[k] + give[k] >= room[k]]
        if not full:
            for k in open_items:
                out[k] += give[k]
            spare = 0
            break
        for k in full:
            spare -= room[k] - out[k]
            out[k] = room[k]
            open_items.discard(k)
    result = [int(v) for v in out]
    if cap is None and result:
        result[-1] += max(0, height - column_min(items)) - sum(result)  # rounding
    return result


def layout_quality(columns: Sequence[Sequence[Item]], col_w: float,
                   height: int) -> float:
    """How good a layout is: the size of its smallest graph, where height
    beyond width / ASPECT does not count.  Negative (minus the overflow in
    pixels) when it does not fit and the page would scroll."""
    overflow = max(column_min(c) for c in columns) - height
    if overflow > 0:
        return -float(overflow)
    best = float("inf")
    for col in columns:
        for item, extra in zip(col, extra_heights(col, height, graph_cap(col_w))):
            best = min(best, min(item.floor + extra, col_w / ASPECT))
    return best


def choose_columns(qualities: dict[int, float]) -> int:
    """Pick a column count from {columns: quality}."""
    top = max(qualities.values())
    for n in sorted(qualities):
        q = qualities[n]
        if q == top or (top > 0 and q >= top * FEWER_COLUMNS_BIAS):
            return n
    return min(qualities)


class GraphGrid(Gtk.Widget):
    __gtype_name__ = "IgtgGraphGrid"

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
        n = (width + COLUMN_SPACING) // (MIN_COLUMN_WIDTH + COLUMN_SPACING)
        return max(1, min(int(n), len(self.sections), 4))

    @staticmethod
    def _col_width(width: int, n: int) -> int:
        return max(1, (width - COLUMN_SPACING * (n - 1)) // n)

    def _plan(self, width: int, n: int):
        col_w = self._col_width(width, n)
        items = []
        for s in self.sections:
            min_h = s.measure(Gtk.Orientation.VERTICAL, col_w)[0]
            floor = s.graph.measure(Gtk.Orientation.VERTICAL, col_w)[0]
            items.append(Item(min_h, floor, float(s.min_height)))
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
        natural += ROW_SPACING * (len(self.sections) - 1)
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
            x = c * (col_w + COLUMN_SPACING)
            y = 0
            for item, extra, i in zip(items, extra_heights(items, height, graph_cap(col_w)),
                                      idxs):
                rect = Gdk.Rectangle()
                rect.x, rect.y, rect.width, rect.height = x, y, col_w, item.min_h + extra
                self.sections[i].size_allocate(rect, -1)
                y += rect.height + ROW_SPACING
