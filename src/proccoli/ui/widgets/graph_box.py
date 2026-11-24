"""A graph with a title and an info line, as a preferences-group row."""

from __future__ import annotations

from typing import Optional, Sequence

from gi.repository import Adw, Gtk, Pango

from ...core.history import Series
from .graph import RGB, Graph, GraphStyle


class GraphPane(Gtk.Box):
    """Graph above a bold title and a dimmed info line. Used on its own in
    ``GraphBox`` and twice side by side in ``DoubleGraphBox``."""

    def __init__(self, title: str = "", max_value: Optional[float] = 100.0,
                 min_max: float = 0.0) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_hexpand(True)
        self.graph = Graph(GraphStyle.NORMAL, max_value, min_max)
        self.append(self.graph)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.title_label = Gtk.Label(label=title, xalign=0)
        self.title_label.add_css_class("heading")
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.info_label = Gtk.Label(label="", xalign=0)
        self.info_label.add_css_class("dim-label")
        self.info_label.add_css_class("numeric")
        self.info_label.set_ellipsize(Pango.EllipsizeMode.END)
        labels.append(self.title_label)
        labels.append(self.info_label)
        self.append(labels)
        self._update_accessible()

    def set_title(self, title: str) -> None:
        self.title_label.set_label(title)
        self._update_accessible()

    def set_info(self, info: str) -> None:
        if info != self.info_label.get_label():
            self.info_label.set_label(info)
            self._update_accessible()

    def set_series(self, series: Sequence[Series],
                   colors: Optional[Sequence[Optional[RGB]]] = None,
                   color_offset: int = 0) -> None:
        self.graph.set_series(series, colors, color_offset)

    def refresh(self) -> None:
        """New data arrived in the series: redraw."""
        self.graph.queue_draw()

    def _update_accessible(self) -> None:
        text = self.title_label.get_label()
        info = self.info_label.get_label()
        self.graph.update_property([Gtk.AccessibleProperty.LABEL],
                                   [f"{text}: {info}" if info else text])


class GraphBox(Adw.PreferencesRow):
    def __init__(self, title: str = "", max_value: Optional[float] = 100.0,
                 min_max: float = 0.0) -> None:
        super().__init__(activatable=False, focusable=False)
        self.pane = GraphPane(title, max_value, min_max)
        self.pane.set_margin_top(12)
        self.pane.set_margin_bottom(12)
        self.pane.set_margin_start(12)
        self.pane.set_margin_end(12)
        self.set_child(self.pane)
        self.set_title(title)

    @property
    def graph(self) -> Graph:
        return self.pane.graph

    def set_title(self, title: str) -> None:
        Adw.PreferencesRow.set_title(self, title)
        self.pane.set_title(title)

    def set_info(self, info: str) -> None:
        self.pane.set_info(info)

    def set_series(self, series, colors=None, color_offset: int = 0) -> None:
        self.pane.set_series(series, colors, color_offset)

    def refresh(self) -> None:
        self.pane.refresh()
