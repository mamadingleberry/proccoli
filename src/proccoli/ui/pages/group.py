"""A sidebar group's page (GPUs, Drives, Network, Batteries): the
Overview's cards for the group's devices, side by side to compare them,
and, where adding up means something, the group's total: the machine's
download and upload, all drives' reads and writes. Percentages (GPU
usage) are never added up.

The group's sidebar entry shows the count of devices, the total where
there is one, and the first device's chart.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from ...core.units import Base, format_reading
from ..page import PageKind, ResourcePage, SidebarSummary
from ..sidebar_groups import GroupSpec, count_text
from .overview import OverviewPage

# What a group adds up: (snapshot field, label) pairs, per kind.
TOTALS = {
    PageKind.NETWORK: (("rx_bps", "↓"), ("tx_bps", "↑")),
    PageKind.DRIVE: (("read_bps", "Read"), ("write_bps", "Write")),
}


def total_text(snapshots: Sequence, fields, base: Base = Base.DECIMAL) -> str:
    """ "↓ 1.2 MB/s · ↑ 30 kB/s": each field summed over the snapshots
    that have it; "" when none do."""
    parts = []
    for name, label in fields:
        values = [getattr(s, name) for s in snapshots if getattr(s, name, None) is not None]
        if values:
            parts.append(f"{label} {format_reading(sum(values), 'B/s', base)}")
    return " · ".join(parts)


class GroupPage(OverviewPage):
    def __init__(self, spec: GroupSpec, settings, navigate: Callable[[str], None],
                 profile=None) -> None:
        super().__init__(settings, navigate, profile=profile, page_id=spec.page_id,
                         kind=spec.kind, title=spec.title, icon=spec.icon)
        self.spec = spec
        self.sort_name = ""                 # before its devices, which have names
        self.members: list[ResourcePage] = []
        self._member_handlers: list[tuple] = []
        self.total = ""

    @property
    def is_group(self) -> bool:
        return True

    def sync(self, entries: Sequence[tuple[ResourcePage, Optional[int]]]) -> None:
        """The group's devices ``(page, color index)``, in sidebar order."""
        self._forget_members()
        self.members = [page for page, _ in entries]
        for page in self.members:
            self._member_handlers.append(
                (page, page.connect("summary-changed", lambda *_: self._member_changed())))
        self.description = count_text(self.spec, len(self.members))
        super().sync(entries)
        self._member_changed()

    def _member_changed(self) -> None:
        fields = TOTALS.get(self.spec.kind)
        if fields:
            base = Base(self.settings.get("base")) if self.settings is not None else Base.DECIMAL
            snapshots = [getattr(getattr(p, "monitor", None), "latest", None) for p in self.members]
            self.total = total_text([s for s in snapshots if s is not None], fields, base)
        self.summary_changed()

    def sidebar_summary(self) -> Optional[SidebarSummary]:
        """The total (where there is one) and the first device's chart."""
        first = next((s for s in (p.sidebar_summary() for p in self.members)
                      if s is not None), None)
        return SidebarSummary(usage=None, usage_text=self.total,
                              series=list(first.series) if first else [],
                              max_value=first.max_value if first else 100.0)

    def _forget_members(self) -> None:
        for page, handler in self._member_handlers:
            page.disconnect(handler)
        self._member_handlers = []

    def shutdown(self) -> None:
        self._forget_members()
        super().shutdown()
