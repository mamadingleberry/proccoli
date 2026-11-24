"""Sizing rules for graphs that fill the page (DESIGN.md §9.1).

Graphs share the page's height, within limits that work on landscape and
portrait screens alike (Milestone 36):

- never shorter than ``min_height`` (below it, the page scrolls);
- never taller than ``max_height``, nor than ``max_ratio`` × their width,
  so a tall, narrow (portrait) window doesn't stretch them into towers;
  height a capped graph can't use goes to the others;
- two graphs side by side (a pair, like Video Encoder / Decoder) stack
  when either would be narrower than ``min_width``, or when the window is
  portrait;
- the page column is at most ``MAX_CONTENT_WIDTH`` wide.

The Overview's cards (Milestone 50) instead try to fill the height
they're given as a grid, each chart shorter than it is wide (Milestone
51): ``plan_grid`` picks how many columns, and so how tall each chart is.

Pure arithmetic, so it's unit-tested without a display.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

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


def needs_update(current: int, target: int) -> bool:
    return abs(current - target) >= HYSTERESIS


# -- the Overview's grid of cards (Milestone 50) -----------------------------------

GRID_TARGET_RATIO = 0.5      # chart height / width the grid aims for
GRID_MAX_COLUMNS = 4
GRID_MIN_CHART = 80          # below it, the page scrolls
GRID_MAX_RATIO = 1.0         # a chart's height stays below this × its width (M51)
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

    Charts *try* to fill the area (M50) but stay shorter than ``max_ratio``
    × their width (M51), and never shorter than ``min_chart``: a plan that
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
