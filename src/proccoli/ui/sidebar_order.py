"""The user's sidebar order (DESIGN.md §9.2). Pure functions on page IDs.

Pinned entries (Apps, Processes) always come first, in their own order.
The rest follow the order the user saved; entries the saved order doesn't
know (a new drive, a first start) go where they'd be by default: right
after the entry that precedes them in the default order.
"""

from __future__ import annotations

from typing import Sequence


def arrange(default: Sequence[str], saved: Sequence[str],
            pinned: Sequence[str]) -> list[str]:
    """Display order of the IDs in ``default`` (the built-in order)."""
    present = set(default)
    head = [p for p in pinned if p in present]
    rest = [i for i in default if i not in head]
    order = [i for i in dict.fromkeys(saved) if i in rest]
    for index, page_id in enumerate(rest):
        if page_id in order:
            continue
        before = next((rest[j] for j in range(index - 1, -1, -1) if rest[j] in order), None)
        order.insert(order.index(before) + 1 if before is not None else 0, page_id)
    return head + order


def move(order: Sequence[str], page_id: str, delta: int,
         pinned: Sequence[str]) -> list[str]:
    """``order`` with ``page_id`` moved ``delta`` places (negative: up),
    never into or above the pinned entries; pinned ones don't move."""
    order = list(order)
    if page_id in pinned or page_id not in order:
        return order
    first = sum(1 for i in order if i in pinned)
    i = order.index(page_id)
    j = max(first, min(len(order) - 1, i + delta))
    order.insert(j, order.pop(i))
    return order


def move_before(order: Sequence[str], page_id: str, target: str,
                pinned: Sequence[str]) -> list[str]:
    """Drag and drop: put ``page_id`` where ``target`` is (target shifts
    down when moving up, up when moving down)."""
    if page_id not in order or target not in order:
        return list(order)
    return move(order, page_id, order.index(target) - order.index(page_id), pinned)


def can_move(order: Sequence[str], page_id: str, delta: int,
             pinned: Sequence[str]) -> bool:
    return move(order, page_id, delta, pinned) != list(order)
