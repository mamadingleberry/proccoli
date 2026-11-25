"""Hover crosshair arithmetic for graphs (ported from the Intel
Details tab's ``GraphView._draw_hover()``).

Pure, so it's unit-tested without a display. A graph holds ``capacity``
points across its plot, newest at the right edge; ``n`` of them are
filled so far. The pointer picks the nearest point.
"""

from __future__ import annotations

from typing import NamedTuple, Optional, Sequence

from .axes import format_span


class HoverPoint(NamedTuple):
    index: int     # into the series' values (0 = oldest held)
    back: int      # points before the newest (0 = now)
    x: float       # the point's x in the plot, snapped to it


def hover_point(pointer_x: float, plot_w: float, capacity: int, n: int) -> Optional[HoverPoint]:
    """The point under ``pointer_x`` (plot coordinates, clamped to the
    plot), or None when there's no data there."""
    if capacity < 2 or n <= 0 or plot_w <= 0:
        return None
    step = plot_w / (capacity - 1)
    x = min(max(pointer_x, 0.0), plot_w)
    back = round((plot_w - x) / step)
    index = n - 1 - back
    if index < 0:
        return None
    return HoverPoint(index, back, plot_w - back * step)


def ago_text(back: int, capacity: int, span_s: Optional[float]) -> str:
    """"now", "12 s ago", "1.5 min ago": the time of a point ``back``
    points before the newest, when the full width is ``span_s``."""
    if back <= 0:
        return "now"
    if not span_s or capacity < 2:
        return f"{back} samples ago"
    return f"{format_span(back * span_s / (capacity - 1))} ago"


def offline_text(flags: Optional[Sequence[bool]], index: int, capacity: int,
                 span_s: Optional[float]) -> Optional[str]:
    """The hover heading over time Proccoli wasn't running (``flags[index]``
    set): how long that stretch lasted, or None over a recorded point."""
    if not flags or not 0 <= index < len(flags) or not flags[index]:
        return None
    first = last = index
    while first > 0 and flags[first - 1]:
        first -= 1
    while last < len(flags) - 1 and flags[last + 1]:
        last += 1
    if not span_s or capacity < 2:
        return "Proccoli wasn't running"
    return f"Proccoli wasn't running ({format_span((last - first + 1) * span_s / (capacity - 1))})"


def box_origin(x: float, box_w: float, box_h: float, width: float, height: float,
               top: float, gap: float = 12) -> tuple[float, float]:
    """Where the tooltip box goes: right of the crosshair, or left of it
    when it wouldn't fit; near the top, inside the widget if it can be."""
    bx = x + gap if x + gap + box_w <= width else x - gap - box_w
    return max(0.0, bx), max(0.0, min(top + 4, height - box_h))
