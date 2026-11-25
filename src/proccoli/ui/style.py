"""Application-wide CSS."""

from __future__ import annotations

from typing import Optional

from gi.repository import Gdk, Gtk

from .compat import has_css_variables, without_css_variables

CSS = """
/* The Intel Details tab: intel_gpu_top_gui's look. */
.graph-section { padding: 12px 6px 6px 6px; }
.legend-item { padding: 2px 8px; min-height: 0; }
/* The per-CPU legend: no slot padding, so it takes little of the
   chart's area. */
flowbox.graph-legend > flowboxchild { padding: 0; margin: 0; }
.legend-off { opacity: 0.45; }
.device-caption { padding: 0 12px; }
.compact .graph-section { padding: 4px 0 0 0; }
.compact .legend-item { padding: 0 6px; }

/* Sidebar meters: a thinner progress bar than the default. */
progressbar.slim > trough,
progressbar.slim > trough > progress {
  min-height: 5px;
}
"""


def add_source_icons() -> None:
    """Running from a source checkout: let GTK find data/icons (an installed
    app has them in the system icon theme)."""
    import os
    display = Gdk.Display.get_default()
    icons = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                         "data", "icons")
    if display is not None and os.path.isdir(icons):
        Gtk.IconTheme.get_for_display(display).add_search_path(os.path.normpath(icons))


def install_css() -> None:
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    if hasattr(provider, "load_from_string"):   # GTK >= 4.12
        provider.load_from_string(CSS)
    else:
        provider.load_from_data(CSS.encode())
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class ThemeCss:
    """Keeps a CSS provider loaded with ``theme.accent_css()`` (the
    palette's accent color), following the theme's changes."""

    def __init__(self, theme, display=None, css_variables: Optional[bool] = None) -> None:
        self.theme = theme
        # GTK 4.14 (Ubuntu 24.04) can't read :root variables: leave them out
        # there (compat.has_css_variables()); injectable for tests.
        self.css_variables = has_css_variables() if css_variables is None else css_variables
        self.provider = Gtk.CssProvider()
        self.display = display or Gdk.Display.get_default()
        if self.display is not None:
            # Above the app's own CSS, so it wins over libadwaita's defaults.
            Gtk.StyleContext.add_provider_for_display(
                self.display, self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._handler = theme.connect("changed", lambda *_: self.reload())
        self.reload()

    def reload(self) -> None:
        css = self.theme.css()
        if not self.css_variables:
            css = without_css_variables(css)
        if hasattr(self.provider, "load_from_string"):   # GTK >= 4.12
            self.provider.load_from_string(css)
        else:
            self.provider.load_from_data(css.encode())

    def shutdown(self) -> None:
        self.theme.disconnect(self._handler)
        if self.display is not None:
            Gtk.StyleContext.remove_provider_for_display(self.display, self.provider)
