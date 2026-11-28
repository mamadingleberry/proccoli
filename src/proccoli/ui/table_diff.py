"""How a table's rows change in one step.

A table keeps its rows in a list store in the order they first appeared.
Adding or removing rows one at a time makes the list, its filter, its
sorter and the column view react to each one (the view rebinds every
visible cell each time), which costs seconds when many processes come and
go. ``plan_splice`` turns one refresh's changes into a single splice: from
the first removed row to the end, the rows that stay (in order) and then
the new ones.

Pure arithmetic, unit-tested without a display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Hashable, Sequence


@dataclass(frozen=True)
class Splice:
    position: int              # where the change starts
    removed: int               # how many rows go from there
    added: list                # the keys put there, in order

    @property
    def empty(self) -> bool:
        return not self.removed and not self.added


def plan_splice(order: Sequence[Hashable], gone: set, new: Sequence[Hashable]) -> Splice:
    """The one splice that takes ``order`` (the store's keys, in order) to
    the same keys without ``gone``, followed by ``new``."""
    first = next((i for i, key in enumerate(order) if key in gone), len(order))
    kept = [key for key in order[first:] if key not in gone]
    if first == len(order):
        return Splice(len(order), 0, list(new))
    return Splice(first, len(order) - first, kept + list(new))


def apply_splice(order: list, splice: Splice) -> list[Any]:
    """``order`` after ``splice`` (the keys the store holds then)."""
    return order[:splice.position] + splice.added + order[splice.position + splice.removed:]
