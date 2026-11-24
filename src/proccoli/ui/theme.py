"""The app's look: light/dark style and colour palette (DESIGN.md §9.3).

``Theme`` applies the ``color-scheme`` preference to a style manager
(``system`` maps to ``Adw.ColorScheme.DEFAULT``, which follows the desktop)
and resolves the ``palette`` preference into series and accent colours for
the current style. The style manager is injected (the real one is
``Adw.StyleManager.get_default()``), so tests use a fake.

Widgets find the theme through their window (``theme_of(widget)``, which
reads ``widget.get_root().theme``); without one they use
``default_theme_colors()``.
"""

from __future__ import annotations

from typing import Optional

from gi.repository import Adw, GObject

from ..core.styles import Style, style_by_id, style_css
from ..core.palette import (DEFAULT_PALETTE, RGB, Palette, accent_of, entry_colors,
                            palette_by_id, rgb_to_hex, secondary, series_colors)

# Sidebar entries that get a progress-bar colour rule (more wrap around).
ENTRY_CSS_COUNT = 24

# A style's base -> Adw.ColorScheme ("system" follows the desktop).
COLOR_SCHEMES = {
    "system": Adw.ColorScheme.DEFAULT,
    "light": Adw.ColorScheme.FORCE_LIGHT,
    "dark": Adw.ColorScheme.FORCE_DARK,
}

# libadwaita < 1.6 has no accent colour API: Adwaita blue.
DEFAULT_ACCENT: RGB = (0x35 / 255, 0x84 / 255, 0xE4 / 255)


class Theme(GObject.Object):
    """Emits ``changed`` whenever anything that affects drawing changes:
    the light/dark style, the palette or the desktop's accent colour."""

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, settings, style_manager) -> None:
        super().__init__()
        self.settings = settings
        self.style_manager = style_manager
        self._settings_handlers = [
            settings.connect_changed("color-scheme", lambda *_: self._on_style()),
            settings.connect_changed("palette", lambda *_: self.emit("changed")),
        ]
        self._style_handlers = [
            style_manager.connect("notify::dark", lambda *_: self.emit("changed")),
        ]
        if hasattr(style_manager, "get_accent_color_rgba"):      # libadwaita >= 1.6
            self._style_handlers.append(
                style_manager.connect("notify::accent-color", lambda *_: self.emit("changed")))
        self._apply_scheme()

    # -- light/dark -----------------------------------------------------------------

    @property
    def dark(self) -> bool:
        return bool(self.style_manager.get_dark())

    @property
    def style(self) -> Style:
        """The ``color-scheme`` preference: Follow System, Light, Dark or a
        tinted style (Sand, Sky, Twilight, Midnight)."""
        return style_by_id(self.settings.get("color-scheme"))

    def _apply_scheme(self) -> None:
        self.style_manager.set_color_scheme(COLOR_SCHEMES[self.style.base])

    def _on_style(self) -> None:
        was_dark = self.dark
        self._apply_scheme()
        if self.dark == was_dark:  # a light/dark switch already said "changed"
            self.emit("changed")   # surfaces change even if light/dark doesn't

    # -- colours ----------------------------------------------------------------------

    @property
    def palette(self) -> Palette:
        return palette_by_id(self.settings.get("palette"))

    def system_accent(self) -> RGB:
        """The desktop's accent colour."""
        if hasattr(self.style_manager, "get_accent_color_rgba"):
            c = self.style_manager.get_accent_color_rgba()
            return (c.red, c.green, c.blue)
        return DEFAULT_ACCENT

    def series_colors(self) -> list[RGB]:
        return series_colors(self.palette, self.dark, self.system_accent())

    def series_rgb(self, index: int) -> RGB:
        colors = self.series_colors()
        return colors[index % len(colors)]

    def entry_rgb(self, index: int, series: int = 0) -> RGB:
        """The colour of the index-th sidebar entry (distinct for every
        entry); ``series`` > 0 is its secondary shade."""
        color = entry_colors(self.series_colors(), index + 1)[index]
        return secondary(color, self.dark) if series else color

    def entry_css(self) -> str:
        """Progress bars in their entry's colour (``.entry-color-<i>``)."""
        colors = entry_colors(self.series_colors(), ENTRY_CSS_COUNT)
        return "".join(f".entry-color-{i} > trough > progress {{ background-color: "
                       f"{rgb_to_hex(c)}; }}\n" for i, c in enumerate(colors))

    def css(self) -> str:
        """Everything ``ThemeCss`` loads: the style's surfaces, the accent,
        the sidebar entry colours."""
        return style_css(self.style) + self.accent_css() + self.entry_css()

    def accent_rgb(self) -> RGB:
        return accent_of(self.palette, self.dark, self.system_accent())

    def accent_css(self) -> str:
        """CSS that recolours libadwaita's accent (switches, progress bars,
        selections) to the palette; empty for System, which keeps the
        desktop's accent."""
        if self.palette.follows_accent:
            return ""
        accent = rgb_to_hex(self.accent_rgb())
        # libadwaita >= 1.6 derives --accent-color (text) from the background
        # colour; older versions read the named colours.
        return (f":root {{ --accent-bg-color: {accent}; }}\n"
                f"@define-color accent_bg_color {accent};\n"
                f"@define-color accent_color {accent};\n")

    def shutdown(self) -> None:
        for h in self._settings_handlers:
            self.settings.disconnect(h)
        for h in self._style_handlers:
            self.style_manager.disconnect(h)
        self._settings_handlers = []
        self._style_handlers = []


def default_theme_colors(dark: bool, accent: RGB = DEFAULT_ACCENT) -> list[RGB]:
    """Series colours without a Theme (widgets outside a themed window)."""
    return series_colors(palette_by_id(DEFAULT_PALETTE), dark, accent)


def theme_of(widget) -> Optional[Theme]:
    """The theme of the window ``widget`` is in, if any."""
    root = widget.get_root() if widget is not None else None
    return getattr(root, "theme", None)
