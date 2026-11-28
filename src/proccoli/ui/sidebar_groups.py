"""Groups in the sidebar: GPUs, Drives, Network and Batteries each get a
group entry with its own page, and their devices sit beneath it.

A kind groups whenever it has a device, so the sidebar looks the same
whether there's one GPU or three, and nothing moves when a second drive
is plugged in. The Processor and Memory stay top-level (there's only ever
one of each), as do Apps, Processes and the Overview.

Everything here works on page IDs, without a display: which group a page
belongs to, the display order (each group followed by its devices), and
moving an entry among its neighbours (a device within its group, a group
as a whole among the other entries).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from . import reorder
from .page import PageKind

COLLAPSED_SETTING = "sidebar-collapsed-groups"


@dataclass(frozen=True)
class GroupSpec:
    kind: PageKind
    page_id: str
    title: str
    icon: str
    noun: str            # one device: "GPU" ("2 GPUs")
    plural: str


GROUPS = {spec.kind: spec for spec in (
    GroupSpec(PageKind.GPU, "group-gpu", "GPUs", "video-display-symbolic", "GPU", "GPUs"),
    GroupSpec(PageKind.DRIVE, "group-drive", "Drives", "drive-multidisk-symbolic",
              "drive", "drives"),
    GroupSpec(PageKind.NETWORK, "group-network", "Network", "network-workgroup-symbolic",
              "connection", "connections"),
    GroupSpec(PageKind.BATTERY, "group-battery", "Batteries", "battery-symbolic",
              "battery", "batteries"),
)}
GROUP_IDS = {spec.page_id for spec in GROUPS.values()}


def group_for(kind) -> Optional[GroupSpec]:
    """The group a page of ``kind`` belongs to, or None (top-level)."""
    try:
        return GROUPS.get(PageKind(kind))
    except ValueError:
        return None


def count_text(spec: GroupSpec, n: int) -> str:
    """ "1 GPU", "3 drives". """
    return f"{n} {spec.noun if n == 1 else spec.plural}"


def nest(order: Sequence[str], group_of: Mapping[str, str]) -> list[str]:
    """``order`` with every group's devices right after the group, in the
    order they have among themselves. Devices whose group isn't in
    ``order`` keep their place."""
    present = set(order)
    out = []
    for page_id in order:
        if group_of.get(page_id) in present:
            continue                      # placed after its group
        out.append(page_id)
        out.extend(c for c in order if group_of.get(c) == page_id)
    return out


def _units(order: Sequence[str], group_of: Mapping[str, str]) -> list[str]:
    """The top-level entries (groups and ungrouped pages), in order."""
    present = set(order)
    return [i for i in order if group_of.get(i) not in present]


def _children(order: Sequence[str], group_of: Mapping[str, str], group: str) -> list[str]:
    return [i for i in order if group_of.get(i) == group]


def _flatten(units: Sequence[str], order: Sequence[str],
             group_of: Mapping[str, str], replaced: Optional[tuple] = None) -> list[str]:
    out = []
    for unit in units:
        out.append(unit)
        if replaced is not None and replaced[0] == unit:
            out.extend(replaced[1])
        else:
            out.extend(_children(order, group_of, unit))
    return out


def move(order: Sequence[str], page_id: str, delta: int, pinned: Sequence[str],
         group_of: Mapping[str, str]) -> list[str]:
    """``reorder.move`` with groups: a device moves among its group's
    devices; a group (with its devices) or an ungrouped entry moves among
    the top-level entries."""
    order = nest(order, group_of)
    group = group_of.get(page_id)
    if group in order:
        kids = reorder.move(_children(order, group_of, group), page_id, delta, [])
        return _flatten(_units(order, group_of), order, group_of, (group, kids))
    units = reorder.move(_units(order, group_of), page_id, delta, pinned)
    return _flatten(units, order, group_of)


def move_before(order: Sequence[str], page_id: str, target: str, pinned: Sequence[str],
                group_of: Mapping[str, str]) -> list[str]:
    """Drag and drop with groups: a device lands among its own group's
    devices only; anything else dropped on a device lands at its group."""
    order = nest(order, group_of)
    if page_id not in order or target not in order:
        return list(order)
    group = group_of.get(page_id)
    if group in order:
        kids = _children(order, group_of, group)
        if target not in kids:
            return list(order)
        kids = reorder.move_before(kids, page_id, target, [])
        return _flatten(_units(order, group_of), order, group_of, (group, kids))
    target = group_of.get(target, target) if group_of.get(target) in order else target
    units = reorder.move_before(_units(order, group_of), page_id, target, pinned)
    return _flatten(units, order, group_of)


def can_move(order: Sequence[str], page_id: str, delta: int, pinned: Sequence[str],
             group_of: Mapping[str, str]) -> bool:
    return move(order, page_id, delta, pinned, group_of) != nest(order, group_of)


def hidden_children(group_of: Mapping[str, str], collapsed) -> set[str]:
    """The devices out of sight: those whose group is collapsed."""
    collapsed = set(collapsed)
    return {child for child, group in group_of.items() if group in collapsed}
