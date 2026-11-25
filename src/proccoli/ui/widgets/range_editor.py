"""The custom time range editor: a number and a unit
(seconds, minutes, hours or days), for Preferences' *Custom…* row and the
toolbar's *Custom…* dialog. It reports seconds; the clamping and its note
are ``ui/time_range.py``'s."""

from __future__ import annotations

from typing import Callable, Optional

from gi.repository import Gtk

from ..time_range import UNITS, split, to_seconds

MAX_NUMBER = 30 * 86400            # in seconds, the largest any unit needs


class RangeEditor(Gtk.Box):
    def __init__(self, seconds: int,
                 on_change: Optional[Callable[[int], None]] = None) -> None:
        super().__init__(spacing=6, valign=Gtk.Align.CENTER)
        self.on_change = on_change
        self._setting = False
        self.number = Gtk.SpinButton.new_with_range(1, MAX_NUMBER, 1)
        self.number.set_valign(Gtk.Align.CENTER)
        self.number.update_property([Gtk.AccessibleProperty.LABEL], ["Time Range"])
        self.unit = Gtk.DropDown.new_from_strings([label for _, label, _ in UNITS])
        self.unit.set_valign(Gtk.Align.CENTER)
        self.unit.update_property([Gtk.AccessibleProperty.LABEL], ["Unit"])
        self.append(self.number)
        self.append(self.unit)
        self.set_seconds(seconds)
        self.number.connect("value-changed", lambda *_: self._changed())
        self.unit.connect("notify::selected", lambda *_: self._changed())

    def seconds(self) -> int:
        return to_seconds(self.number.get_value(), self.unit.get_selected())

    def set_seconds(self, seconds: int) -> None:
        number, index = split(seconds)
        self._setting = True
        self.unit.set_selected(index)
        self.number.set_value(number)
        self._setting = False

    def _changed(self) -> None:
        if not self._setting and self.on_change is not None:
            self.on_change(self.seconds())
