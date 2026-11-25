"""A legend for a graph with many lines (used by ``LegendChart``, 58 and 59).

One toggle per series: a color swatch in the line's color, its name and
its current value. Left-click an item to hide or show its line; right-click
it to show only that line (again: all lines), so a busy chart of 16 or
more lines can be read one line at a time. The rules are
``series_visibility``'s, applied to every change, so the chart never shows
nothing: hiding the last line shown brings them all back. Swatches ask the
graph for their color when they draw, so they follow palette and style
changes like the graph does.
"""

from __future__ import annotations

from typing import Sequence

from gi.repository import Gdk, Gtk

from .. import series_visibility
from .graph import Graph, rounded_rect

HINT = "Click to hide or show · Right-click to show only this one"

SWATCH = 12


class LegendItem(Gtk.ToggleButton):
    def __init__(self, graph: Graph, index: int, name: str) -> None:
        super().__init__(active=graph.series_shown(index), focus_on_click=False)
        self.add_css_class("flat")
        self.add_css_class("legend-item")
        self.graph, self.index, self.name = graph, index, name
        box = Gtk.Box(spacing=6)
        self.swatch = Gtk.DrawingArea(content_width=SWATCH, content_height=SWATCH,
                                      valign=Gtk.Align.CENTER)
        self.swatch.set_draw_func(self._draw_swatch)
        self.name_label = Gtk.Label(label=name, xalign=0)
        self.name_label.add_css_class("caption-heading")
        self.value_label = Gtk.Label(xalign=1, hexpand=True, width_chars=5)
        self.value_label.add_css_class("caption")
        self.value_label.add_css_class("numeric")
        for w in (self.swatch, self.name_label, self.value_label):
            box.append(w)
        self.set_child(box)
        self.compact = False
        self.on_solo = None                       # set by the Legend
        self.on_toggled = None                    # set by the Legend: its rules
        self.set_tooltip_text(f"{name}\n{HINT}")
        self.connect("toggled", self._on_toggled)
        self._on_toggled(self)
        # Right-click (or a long press on touch): this line only.
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", lambda g, *_: (g.set_state(Gtk.EventSequenceState.CLAIMED),
                                                 self.solo()))
        self.add_controller(click)
        press = Gtk.GestureLongPress(touch_only=True)
        press.connect("pressed", lambda *_: self.solo())
        self.add_controller(press)

    def solo(self) -> None:
        if self.on_solo is not None:
            self.on_solo(self.index)

    def _draw_swatch(self, _area, cr, width, height) -> None:
        r, g, b = self.graph.color_for(self.index)
        rounded_rect(cr, 0, 0, width, height, 3)
        cr.set_source_rgba(r, g, b, 1.0 if self.get_active() else 0.25)
        cr.fill()

    def _on_toggled(self, _button) -> None:
        shown = self.get_active()
        self.graph.set_series_shown(self.index, shown)
        self.name_label.set_opacity(1.0 if shown else 0.5)
        self.value_label.set_opacity(1.0 if shown else 0.5)
        self.swatch.queue_draw()
        self.update_property([Gtk.AccessibleProperty.LABEL],
                             [f"{self.name}: {'shown' if shown else 'hidden'}"])
        if self.on_toggled is not None:
            self.on_toggled(self.index)

    def set_value(self, text: str) -> None:
        if self.value_label.get_label() != text:
            self.value_label.set_label(text)
            if self.compact:
                self.set_tooltip_text(f"{self.name}: {text}\n{HINT}")

    def set_compact(self, compact: bool) -> None:
        """Swatch and name only; the value moves to the hover text."""
        self.compact = compact
        self.value_label.set_visible(not compact)
        self.value_label.set_hexpand(not compact)
        self.set_tooltip_text(f"{self.name}: {self.value_label.get_label()}\n{HINT}"
                              if compact else f"{self.name}\n{HINT}")


class Legend(Gtk.FlowBox):
    """Items in series order, as many per line as fit."""

    def __init__(self, graph: Graph) -> None:
        super().__init__(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                         min_children_per_line=2, max_children_per_line=12,
                         column_spacing=2, row_spacing=0)
        self.add_css_class("graph-legend")      # compact slots (ui/style.py)
        self.graph = graph
        self.items: list[LegendItem] = []
        self.compact = False
        self._applying = False                    # set_shown is changing items
        self.available: list[bool] = []           # lines with data (set_available)

    def set_names(self, names: Sequence[str]) -> None:
        """One item per name; existing items are kept (and their toggles)."""
        if [i.name for i in self.items] == list(names):
            return
        for item in self.items:
            self.remove(item.get_parent())
        self.items = [LegendItem(self.graph, i, name) for i, name in enumerate(names)]
        self.available = [True] * len(self.items)
        for item in self.items:
            item.set_compact(self.compact)
            item.on_solo = self.solo
            item.on_toggled = self._on_item_toggled
            self.append(item)

    def shown(self) -> list[bool]:
        return [item.get_active() for item in self.items]

    def set_shown(self, shown) -> None:
        """Show exactly these lines (never none: ``never_empty``)."""
        self._applying = True
        try:
            fixed = series_visibility.never_empty(shown, self.available)
            for item, on in zip(self.items, fixed):
                if item.get_active() != on:
                    item.set_active(on)           # "toggled" updates the graph
        finally:
            self._applying = False

    def _on_item_toggled(self, _index: int) -> None:
        """A click on an item (it has already toggled itself): apply the
        rules, so deselecting the last line shown shows them all."""
        if not self._applying:
            shown = self.shown()
            fixed = series_visibility.never_empty(shown, self.available)
            if fixed != shown:
                self.set_shown(fixed)
        self._sync_graph()

    def set_available(self, index: int, available: bool) -> None:
        """Whether line ``index`` has data at all (a measure a tool doesn't
        report): an unavailable line is drawn nowhere, its item is hidden,
        and it never counts as shown, so hiding the others still brings
        every available line back."""
        if self.available[index] == available:
            return
        self.available[index] = available
        self.items[index].get_parent().set_visible(available)
        self._sync_graph()

    def _sync_graph(self) -> None:
        for i, item in enumerate(self.items):
            self.graph.set_series_shown(i, item.get_active() and self.available[i])

    def toggle(self, index: int) -> None:
        """A left-click: hide or show that line."""
        self.set_shown(series_visibility.toggle(self.shown(), index, self.available))

    def solo(self, index: int) -> None:
        """A right-click: only that line (again: every line)."""
        self.set_shown(series_visibility.solo(self.shown(), index, self.available))

    def set_compact(self, compact: bool) -> None:
        """Every item without its value (shown on hover): more per line."""
        if compact != self.compact:
            self.compact = compact
            for item in self.items:
                item.set_compact(compact)

    def set_values(self, texts: Sequence[str]) -> None:
        for item, text in zip(self.items, texts):
            item.set_value(text)
