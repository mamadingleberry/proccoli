"""Axis ticks and labels for percentage graphs (DESIGN.md §9.1).

Pure arithmetic and formatting, so it's unit-tested without a display.
The y axis runs 0–100 %; the x axis is time, oldest on the left, "now" on
the right.
"""

from __future__ import annotations

from typing import Optional

PERCENT_STEPS = (0, 25, 50, 75, 100)


def percent_ticks(plot_height: float, label_height: float) -> list[tuple[float, Optional[str]]]:
    """``(value, label or None)`` for 0, 25, 50, 75 and 100 %. Every tick
    gets a mark; labels go on as many as fit without overlapping (always 0
    and 100 %)."""
    labelled = {0, 50, 100}
    if plot_height >= 5 * label_height:
        labelled = set(PERCENT_STEPS)
    elif plot_height < 3 * label_height:
        labelled = {0, 100}
    return [(v, f"{v} %" if v in labelled else None) for v in PERCENT_STEPS]


def span_unit(span_s: float) -> str:
    """One unit for a whole axis: "s" up to 2 minutes, "min" up to 2 hours,
    else "h" (so labels never mix "1 min" with "48 s")."""
    return "s" if span_s <= 120 else "min" if span_s <= 7200 else "h"


def format_span(seconds: float, unit: str = "") -> str:
    """"45 s", "2 min", "1.5 min", "1 h"; ``unit`` forces one."""
    seconds = max(0.0, seconds)
    unit = unit or ("s" if seconds < 60 else "min" if seconds < 3600 else "h")
    if unit == "s":
        return f"{seconds:.0f} s"
    if unit == "min":
        return f"{seconds / 60:.3g} min"
    return f"{seconds / 3600:.3g} h"


# Round tick steps, seconds.
NICE_STEPS = (1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1200, 1800, 3600,
              7200, 10800, 21600, 43200, 86400)


def nice_step(span_s: float, max_ticks: int) -> float:
    """The smallest round step giving at most ``max_ticks`` intervals."""
    for step in NICE_STEPS:
        if span_s / step <= max_ticks:
            return float(step)
    return float(NICE_STEPS[-1])


def time_ticks(span_s: float, plot_width: float,
               min_label_width: float = 56) -> list[tuple[float, str]]:
    """``(x fraction 0..1 from the left, label)``, oldest first: round
    steps back from "now" (at the right edge), as many as fit
    ``min_label_width`` apart, all in one unit."""
    if span_s <= 0 or plot_width <= 0:
        return [(1.0, "now")]
    fit = max(1, min(6, int(plot_width // min_label_width)))
    step = nice_step(span_s, fit)
    unit = span_unit(span_s)
    ticks = []
    k = int(span_s // step + 1e-9)
    for i in range(k, -1, -1):
        ago = i * step
        ticks.append((1 - ago / span_s, "now" if i == 0 else format_span(ago, unit)))
    return ticks


def history_span_s(settings) -> float:
    """Seconds a full graph shows: graph data points × the refresh interval."""
    from ..core.ticker import interval_for
    return settings.get("graph-data-points") * interval_for(settings.get("refresh-speed")) / 1000


def is_percent_graph(units: list[str], max_value: Optional[float]) -> bool:
    """Axes are for graphs of percentages on a fixed 0–100 scale."""
    return bool(units) and all(u == "%" for u in units) and max_value == 100.0
