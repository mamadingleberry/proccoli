"""Two graphs side by side in one row (e.g. video encode and decode), or
stacked when the page is narrow or portrait (DESIGN.md §9.1)."""

from __future__ import annotations

from typing import Optional

from gi.repository import Adw, Gtk

from .graph_box import GraphPane

SPACING = 12


class DoubleGraphBox(Adw.PreferencesRow):
    def __init__(self, start_title: str = "", end_title: str = "",
                 max_value: Optional[float] = 100.0, min_max: float = 0.0) -> None:
        super().__init__(activatable=False, focusable=False)
        self.start = GraphPane(start_title, max_value, min_max)
        self.end = GraphPane(end_title, max_value, min_max)
        self.box = box = Gtk.Box(spacing=SPACING, homogeneous=True)
        for m in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{m}")(12)
        box.append(self.start)
        box.append(self.end)
        self.set_child(box)
        self.set_title(f"{start_title} / {end_title}")

    @property
    def stacked(self) -> bool:
        return self.box.get_orientation() == Gtk.Orientation.VERTICAL

    def set_stacked(self, stacked: bool) -> bool:
        """One above the other (True) or side by side; True if it changed."""
        if stacked == self.stacked:
            return False
        self.box.set_orientation(Gtk.Orientation.VERTICAL if stacked
                                 else Gtk.Orientation.HORIZONTAL)
        return True

    @property
    def graphs(self):
        return [self.start.graph, self.end.graph]

    def refresh(self) -> None:
        self.start.refresh()
        self.end.refresh()
