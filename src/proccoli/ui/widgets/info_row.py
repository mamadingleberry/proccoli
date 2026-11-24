"""A property row: small title above a prominent value.

``set_value(None)`` hides the row: pages never show "N/A" for values a
device doesn't have (DESIGN.md §9.1).
"""

from __future__ import annotations

from typing import Optional

from gi.repository import Adw, GLib


class InfoRow(Adw.ActionRow):
    def __init__(self, title: str, value: Optional[str] = None) -> None:
        super().__init__(title=title, activatable=False)
        self._value: Optional[str] = None
        self.add_css_class("property")      # libadwaita: title small, value large
        self.set_subtitle_selectable(True)  # values can be copied
        self.set_value(value)

    def set_value(self, value: Optional[str]) -> None:
        if value is None or value == "":
            self.set_visible(False)
            return
        # Compare with the value we keep, not get_subtitle(): libadwaita 1.5
        # returns the subtitle with its markup removed, newer versions the
        # markup itself, so neither matches what was set on both.
        if value != self._value:
            self._value = value
            # Subtitles are markup; values come from the system, so escape them.
            self.set_subtitle(GLib.markup_escape_text(value))
        self.set_visible(True)

    def get_value(self) -> Optional[str]:
        return self._value if self.get_visible() else None
