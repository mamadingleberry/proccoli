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
        self.add_css_class("property")      # libadwaita: title small, value large
        self.set_subtitle_selectable(True)  # values can be copied
        self.set_value(value)

    def set_value(self, value: Optional[str]) -> None:
        if value is None or value == "":
            self.set_visible(False)
            return
        # Subtitles are markup; values come from the system, so escape them.
        escaped = GLib.markup_escape_text(value)
        if self.get_subtitle() != escaped:
            self.set_subtitle(escaped)
        self.set_visible(True)

    def get_value(self) -> Optional[str]:
        return self.get_subtitle() if self.get_visible() else None
