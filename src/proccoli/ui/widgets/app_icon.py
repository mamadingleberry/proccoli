"""App icons in table rows (Apps, Processes, the GPU Processes tab)."""

from __future__ import annotations

from gi.repository import Gio, Gtk

from ... import MISSING_APP_ICON


def set_app_icon(image: Gtk.Image, icon) -> None:
    """Show ``icon`` (a Gio.Icon), or the solid puzzle piece when there's
    none or the icon theme doesn't have it (a broken .desktop entry)."""
    theme = Gtk.IconTheme.get_for_display(image.get_display())
    if icon is not None and (not isinstance(icon, Gio.ThemedIcon)
                             or theme.has_gicon(icon)):
        image.set_from_gicon(icon)
    else:
        image.set_from_icon_name(MISSING_APP_ICON)
