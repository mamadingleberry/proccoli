"""Which lines of a many-line graph show (any ``LegendChart``: the per-CPU
chart, NVIDIA's details; Milestones 55, 58 and 59). Pure functions on a
list of booleans.

- left-click an item: ``toggle`` its line (hide or show it);
- right-click an item: ``solo`` its line (show only it); right-clicking the
  only line shown brings every line back;
- a chart never shows nothing: hiding the last line shown (say, the one
  core selected with a right-click) brings every line back
  (``never_empty``, M59). Every change goes through it.
"""

from __future__ import annotations

from typing import Optional, Sequence


def never_empty(shown: Sequence[bool],
                available: Optional[Sequence[bool]] = None) -> list[bool]:
    """``shown``, or every available line if that would show none.
    ``available``: lines that have data at all (default: every line); a
    line without data never counts as shown."""
    out = list(shown)
    avail = list(available) if available is not None else [True] * len(out)
    if any(s and a for s, a in zip(out, avail)) or not any(avail):
        return out
    return [s or a for s, a in zip(out, avail)]


def toggle(shown: Sequence[bool], index: int,
           available: Optional[Sequence[bool]] = None) -> list[bool]:
    """Hide or show one line; hiding the last one shown shows them all."""
    out = list(shown)
    out[index] = not out[index]
    return never_empty(out, available)


def solo(shown: Sequence[bool], index: int,
         available: Optional[Sequence[bool]] = None) -> list[bool]:
    """Only ``index`` shown; if it already is the only one, all of them."""
    only = [i == index for i in range(len(shown))]
    if list(shown) == only:
        return [True] * len(shown)
    return never_empty(only, available)
