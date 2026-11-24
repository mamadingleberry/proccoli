"""The app's styles (DESIGN.md §9.3): light/dark plus tinted styles.

ExpressVPN's apps offer *System Default*, *Sand*, *Sky*, *Twilight* and
*Midnight*; Proccoli offers the same names, with its own colours, next to
plain Light and Dark. A style has a base (which ``Adw.ColorScheme`` to
use) and, for the tinted ones, colours for libadwaita's surfaces. Pure
data, no GTK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .palette import hex_to_rgb, relative_luminance

# libadwaita colour variables a style may set (``--<name>``, and the
# pre-1.6 ``@define-color <name with underscores>``).
SURFACES = ("window-bg-color", "window-fg-color", "view-bg-color", "view-fg-color",
            "headerbar-bg-color", "headerbar-fg-color", "sidebar-bg-color",
            "sidebar-fg-color", "card-bg-color", "card-fg-color", "popover-bg-color",
            "popover-fg-color", "dialog-bg-color", "dialog-fg-color")


@dataclass(frozen=True)
class Style:
    id: str                       # settings nick (color-scheme)
    name: str                     # shown in Preferences
    base: str                     # "system", "light" or "dark"
    colors: Mapping[str, str] = field(default_factory=dict)   # SURFACES -> hex

    @property
    def tinted(self) -> bool:
        return bool(self.colors)


def _surfaces(window, view, header, sidebar, card, fg) -> dict[str, str]:
    return {"window-bg-color": window, "window-fg-color": fg,
            "view-bg-color": view, "view-fg-color": fg,
            "headerbar-bg-color": header, "headerbar-fg-color": fg,
            "sidebar-bg-color": sidebar, "sidebar-fg-color": fg,
            "card-bg-color": card, "card-fg-color": fg,
            "popover-bg-color": view, "popover-fg-color": fg,
            "dialog-bg-color": window, "dialog-fg-color": fg}


STYLES: tuple[Style, ...] = (
    Style("system", "Follow System", "system"),
    Style("light", "Light", "light"),
    Style("dark", "Dark", "dark"),
    Style("sand", "Sand", "light",
          _surfaces("#f3ede2", "#fbf8f2", "#ebe2d2", "#e6dcc9", "#fffdf8", "#3b3226")),
    Style("sky", "Sky", "light",
          _surfaces("#ecf3fb", "#f8fbff", "#dfeaf7", "#d8e5f4", "#ffffff", "#1d2b3c")),
    Style("twilight", "Twilight", "dark",
          _surfaces("#2a2438", "#221d2f", "#332a45", "#2d2640", "#372f4b", "#ece6f6")),
    Style("midnight", "Midnight", "dark",
          _surfaces("#0f1420", "#0a0e18", "#151b2b", "#111726", "#1a2133", "#dde4f0")),
)


def style_by_id(style_id: str) -> Style:
    """The style with that id, or Follow System for an unknown one."""
    return next((s for s in STYLES if s.id == style_id), STYLES[0])


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio of two hex colours (1 to 21)."""
    la, lb = sorted((relative_luminance(hex_to_rgb(a)), relative_luminance(hex_to_rgb(b))),
                    reverse=True)
    return (la + 0.05) / (lb + 0.05)


def style_css(style: Style) -> str:
    """CSS setting libadwaita's surface colours (empty for untinted styles)."""
    if not style.tinted:
        return ""
    variables = "".join(f" --{k}: {v};" for k, v in style.colors.items())
    legacy = "".join(f"@define-color {k.replace('-color', '').replace('-', '_')}_color {v};\n"
                     for k, v in style.colors.items())
    return f":root {{{variables} }}\n{legacy}"
