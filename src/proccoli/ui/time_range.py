"""A custom graph time range as a number and a unit.
Display-free: the editor widget (``widgets/range_editor.py``), Preferences
and the toolbar use these.

A stored range is seconds (``graph-time-range-custom``); it's shown in the
largest unit that divides it evenly (5400 s is "90 Minutes", 7200 s
"2 Hours"), so what the user typed comes back as typed.
"""

from __future__ import annotations

from ..core.ticker import MAX_RANGE_S, MIN_RANGE_S, clamp_range_s

# (id, label, seconds), smallest first.
UNITS = (("seconds", "Seconds", 1), ("minutes", "Minutes", 60),
         ("hours", "Hours", 3600), ("days", "Days", 86400))
CUSTOM_LABEL = "Custom…"


def split(seconds: int) -> tuple[int, int]:
    """``(number, unit index)``: the largest unit dividing ``seconds``."""
    seconds = max(1, int(seconds))
    for index in range(len(UNITS) - 1, -1, -1):
        size = UNITS[index][2]
        if seconds % size == 0:
            return seconds // size, index
    return seconds, 0


def to_seconds(number: float, unit_index: int) -> int:
    return int(round(number * UNITS[unit_index][2]))


def describe(seconds: int) -> str:
    """"2 Hours", "90 Minutes", "1 Day"."""
    number, index = split(seconds)
    label = UNITS[index][1]
    return f"{number} {label[:-1] if number == 1 else label}"


def limit_note(requested: int, interval_ms: int = 1000) -> str:
    """Why ``requested`` seconds became something else, or ""."""
    clamped = clamp_range_s(requested, interval_ms)
    if clamped == requested:
        return ""
    if requested > MAX_RANGE_S:
        return f"At most {describe(MAX_RANGE_S)}"
    if clamped > MIN_RANGE_S:
        return f"At least two update intervals ({describe(clamped)})"
    return f"At least {describe(MIN_RANGE_S)}"
