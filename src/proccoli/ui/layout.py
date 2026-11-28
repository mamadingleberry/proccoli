"""Sizing rules for graphs that fill the page.

Graphs share the page's height, within limits that work on landscape and
portrait screens alike:

- never shorter than ``min_height`` (below it, the page scrolls);
- never taller than ``max_height``, nor than ``max_ratio`` × their width,
  so a tall, narrow (portrait) window doesn't stretch them into towers;
  height a capped graph can't use goes to the others;
- two graphs side by side (a pair, like Video Encoder / Decoder) stack
  when either would be narrower than ``min_width``, or when the window is
  portrait;
- the page column is at most ``MAX_CONTENT_WIDTH`` wide.

The Overview's cards instead try to fill the height
they're given as a grid, each chart shorter than it is wide:
``plan_grid`` picks how many columns, and so how tall each chart is.

Pure arithmetic, so it's unit-tested without a display.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, NamedTuple, Optional, Sequence

# Page graphs never get smaller than this: below it, the page scrolls.
MIN_GRAPH_HEIGHT = 120
# The page column never gets wider than this (Adw.Clamp).
MAX_CONTENT_WIDTH = 1600
CONTENT_TIGHTENING = 1200


@dataclass(frozen=True)
class GraphLimits:
    min_height: int = MIN_GRAPH_HEIGHT
    max_height: int = 560
    max_ratio: float = 0.5       # height / width
    min_width: int = 280         # narrower panes of a pair stack


LIMITS = GraphLimits()
# Ignore changes smaller than this, so rounding can't make layout oscillate.
HYSTERESIS = 2


def height_range(width: float, limits: GraphLimits = LIMITS) -> tuple[int, int]:
    """``(lowest, highest)`` height for a graph ``width`` wide."""
    lo = limits.min_height
    hi = min(limits.max_height, int(width * limits.max_ratio))
    return lo, max(lo, hi)


def fit_heights(viewport: float, fixed: float, row_widths: Sequence[float],
                limits: GraphLimits = LIMITS) -> list[int]:
    """One height per graph row (``row_widths``: each row's narrowest
    graph) so the rows, plus ``fixed`` pixels of everything else, fill
    ``viewport``. Rows share the spare height equally, each within its
    ``height_range``; what a capped row can't take goes to the others."""
    n = len(row_widths)
    if n == 0:
        return []
    ranges = [height_range(w, limits) for w in row_widths]
    spare = viewport - fixed
    heights: list[Optional[float]] = [None] * n
    open_rows = set(range(n))
    while open_rows:
        share = spare / len(open_rows)
        capped = [i for i in open_rows if ranges[i][1] < share]
        if not capped:
            break
        for i in capped:
            heights[i] = ranges[i][1]
            spare -= ranges[i][1]
            open_rows.discard(i)
    share = spare / len(open_rows) if open_rows else 0
    for i in open_rows:
        heights[i] = min(max(share, ranges[i][0]), ranges[i][1])
    return [int(h) for h in heights]


def is_portrait(width: float, height: float) -> bool:
    return height > width


def stack_pair(pair_width: float, viewport_width: float, viewport_height: float,
               spacing: float = 12, limits: GraphLimits = LIMITS) -> bool:
    """Whether a pair of graphs ``pair_width`` wide in all should stack."""
    pane = (pair_width - spacing) / 2
    return pane < limits.min_width or is_portrait(viewport_width, viewport_height)


def count_rows(tops: Iterable[float], tolerance: float = 1.0) -> int:
    """Graphs side by side share a row: count distinct top edges."""
    return len(group_rows(list(tops), tolerance))


def group_rows(tops: Sequence[float], tolerance: float = 1.0) -> list[list[int]]:
    """Indices of ``tops`` grouped into rows (top to bottom): graphs side
    by side share a row."""
    rows: list[list[int]] = []
    last = None
    for i in sorted(range(len(tops)), key=lambda i: tops[i]):
        if last is None or tops[i] - last > tolerance:
            rows.append([])
            last = tops[i]
        rows[-1].append(i)
    return rows


def aspect_height(width: float, ratio: float, minimum: int, maximum: int) -> int:
    """Height for a graph ``width`` wide, keeping ``ratio`` (height/width)."""
    return int(min(max(width * ratio, minimum), maximum))


# The least a graph keeps when something below it shares its area:
# room for a plot with 0 % and 100 % labels. Low on purpose, so the per-CPU
# chart and its legend keep the total chart's area even with many CPUs in
# a small window.
MIN_GRAPH_IN_AREA = 32


def graph_in_area(area: int, reserve: int, floor: int = MIN_GRAPH_IN_AREA) -> int:
    """The graph's height when it shares ``area`` with ``reserve`` pixels of
    something else (the per-CPU chart's legend): the area less the
    reserve, but never under ``floor`` (then the area grows instead)."""
    return max(floor, area - max(0, reserve))


# The per-CPU chart's comfortable height: below it, the legend drops its
# values (shown on hover instead) to leave the chart more of the area.
COMFORT_GRAPH = 96


def use_compact_legend(area: int, full_legend: int, comfort: int = COMFORT_GRAPH) -> bool:
    """Whether a legend with values (``full_legend`` pixels, gap included)
    would leave the chart under ``comfort`` in ``area``. The area doesn't
    depend on the legend, so the answer can't flip back and forth."""
    return area - full_legend < comfort


def needs_update(current: int, target: int) -> bool:
    return abs(current - target) >= HYSTERESIS


# -- the Overview's grid of cards -----------------------------------

GRID_TARGET_RATIO = 0.5      # chart height / width the grid aims for
GRID_MAX_COLUMNS = 4
GRID_MIN_CHART = 80          # below it, the page scrolls
GRID_MAX_RATIO = 1.0         # a chart's height stays below this × its width
EMPTY_CELL_WEIGHT = 2.0      # how much an empty cell costs, against chart shape
UNFILLED_WEIGHT = 2.0        # how much leaving the area empty costs
OVERFLOW_PENALTY = 10.0      # any plan that fits beats any that doesn't


@dataclass(frozen=True)
class GridPlan:
    """``columns`` × ``rows`` cards, each chart ``chart_height`` tall."""
    columns: int
    rows: int
    chart_height: int

    def height(self, chrome_h: float, spacing: float) -> float:
        """The grid's total height."""
        return self.rows * (self.chart_height + chrome_h) + (self.rows - 1) * spacing


def card_width(width: float, columns: int, spacing: float) -> float:
    return (width - (columns - 1) * spacing) / columns


def max_chart_height(chart_w: float, max_ratio: float = GRID_MAX_RATIO) -> int:
    """The tallest chart allowed ``chart_w`` wide: strictly under
    ``max_ratio`` × its width."""
    return math.ceil(chart_w * max_ratio) - 1


def _grid_score(count: int, columns: int, rows: int, chart_w: float, chart_h: float,
                wanted_h: float, target_ratio: float, unfilled: float) -> float:
    shape = abs(math.log(max(chart_h, 1.0) / max(chart_w, 1.0) / target_ratio))
    empty = (columns * rows - count) / (columns * rows)
    score = shape + EMPTY_CELL_WEIGHT * empty + UNFILLED_WEIGHT * unfilled
    if wanted_h < chart_h:          # clamped to the minimum: doesn't fit
        score += OVERFLOW_PENALTY + (chart_h - wanted_h) / chart_h
    return score


def plan_grid(count: int, width: float, height: float, spacing: float = 12,
              chrome_w: float = 0, chrome_h: float = 0,
              max_columns: int = GRID_MAX_COLUMNS, min_width: float = LIMITS.min_width,
              min_chart: int = GRID_MIN_CHART,
              target_ratio: float = GRID_TARGET_RATIO,
              max_ratio: float = GRID_MAX_RATIO) -> GridPlan:
    """The grid of ``count`` cards that best fills ``width`` × ``height``.

    Each card is a chart plus ``chrome_w`` × ``chrome_h`` of padding, title
    and labels; cards are ``spacing`` apart. Every column count from 1 to
    ``max_columns`` whose cards are at least ``min_width`` wide (one column
    always qualifies) is tried, the rows sharing the height equally.

    Charts *try* to fill the area but stay shorter than ``max_ratio``
    × their width, and never shorter than ``min_chart``: a plan that
    needs that doesn't fit, and loses to any that does. The winner fills
    the most of the area, with the chart shape nearest ``target_ratio``
    and the fewest empty cells."""
    if count <= 0:
        return GridPlan(0, 0, 0)
    best: Optional[tuple[float, GridPlan]] = None
    for columns in range(1, min(count, max_columns) + 1):
        cw = card_width(width, columns, spacing)
        if columns > 1 and cw < min_width:
            break
        rows = math.ceil(count / columns)
        chart_w = cw - chrome_w
        wanted = (height - (rows - 1) * spacing) / rows - chrome_h
        chart_h = max(min(int(wanted), max_chart_height(chart_w, max_ratio)), min_chart)
        plan = GridPlan(columns, rows, chart_h)
        unfilled = max(0.0, 1 - plan.height(chrome_h, spacing) / height) if height > 0 else 0.0
        score = _grid_score(count, columns, rows, chart_w, chart_h, wanted,
                            target_ratio, unfilled)
        if best is None or score < best[0]:
            best = (score, plan)
    return best[1]


# -- the chart grid of the GPU Details tabs: columns chosen from the space given, spare height shared out by
# each chart's weight. ``widgets/chart_grid.py`` is the widget over this.

CHART_COLUMN_SPACING = 18
CHART_ROW_SPACING = 6
CHART_MIN_COLUMN_WIDTH = 300
# A graph taller than width / CHART_ASPECT is not more useful than a wider one.
CHART_ASPECT = 3.0
# Prefer fewer columns unless more of them are clearly better.
FEWER_COLUMNS_BIAS = 0.85


class GridItem(NamedTuple):
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
        tallest = max(sum(heights[i] for i in r) + CHART_ROW_SPACING * (len(r) - 1)
                      for r in runs)
        if best is None or tallest < best[0]:
            best = (tallest, runs)
    return best[1]


def column_min(items: Sequence[GridItem]) -> int:
    return sum(i.min_h for i in items) + CHART_ROW_SPACING * max(0, len(items) - 1)


def graph_cap(col_w: float, limits: GraphLimits = LIMITS) -> int:
    """The tallest a graph in a column ``col_w`` wide gets:
    on a portrait screen one column is narrow but very tall."""
    return min(limits.max_height, int(col_w * limits.max_ratio))


def extra_heights(items: Sequence[GridItem], height: int,
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


def layout_quality(columns: Sequence[Sequence[GridItem]], col_w: float,
                   height: int) -> float:
    """How good a layout is: the size of its smallest graph, where height
    beyond width / CHART_ASPECT does not count. Negative (minus the overflow in
    pixels) when it does not fit and the page would scroll."""
    overflow = max(column_min(c) for c in columns) - height
    if overflow > 0:
        return -float(overflow)
    best = float("inf")
    for col in columns:
        for item, extra in zip(col, extra_heights(col, height, graph_cap(col_w))):
            best = min(best, min(item.floor + extra, col_w / CHART_ASPECT))
    return best


def choose_columns(qualities: dict[int, float]) -> int:
    """Pick a column count from {columns: quality}."""
    top = max(qualities.values())
    for n in sorted(qualities):
        q = qualities[n]
        if q == top or (top > 0 and q >= top * FEWER_COLUMNS_BIAS):
            return n
    return min(qualities)
