"""The app's styles: light/dark plus tinted styles.

*Follow System*, plain *Light* and *Dark*, then tinted styles: the light
ones (Sand, Sky, Mint, Rose, Lavender, Paper, Solarized Light, Gruvbox
Light, Catppuccin Latte, High Contrast Light), then the dark ones
(Twilight, Midnight, Nord, Dracula, Gruvbox Dark, Solarized Dark,
Catppuccin Mocha, Tokyo Night, Forest, Ember, Black, High Contrast Dark).
The editor-theme styles take their backgrounds from those themes, with
text darkened or lightened where needed so every surface reads at 7:1 or
better. A style has a base (which ``Adw.ColorScheme`` to use) and, for
the tinted ones, colors for libadwaita's surfaces. Pure data, no GTK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .palette import hex_to_rgb, relative_luminance

# libadwaita color variables a style may set (``--<name>``, and the
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
    Style("mint", "Mint", "light",
          _surfaces("#e8f4ee", "#f6fbf8", "#d9ece2", "#d2e7dc", "#fbfefc", "#1c3328")),
    Style("rose", "Rose", "light",
          _surfaces("#f8eaee", "#fdf6f8", "#f1dbe2", "#eed3dc", "#fffbfc", "#3d2229")),
    Style("lavender", "Lavender", "light",
          _surfaces("#efebf8", "#f9f7fd", "#e3dcf3", "#ddd5f0", "#fdfcff", "#2a2340")),
    Style("paper", "Paper", "light",
          _surfaces("#f4f1ea", "#fcfbf7", "#ebe6da", "#e7e1d3", "#fffefb", "#2b2a27")),
    Style("solarized-light", "Solarized Light", "light",
          _surfaces("#fdf6e3", "#fffbf0", "#eee8d5", "#e9e2cc", "#fffdf6", "#073642")),
    Style("gruvbox-light", "Gruvbox Light", "light",
          _surfaces("#fbf1c7", "#fdf7dd", "#f2e5bc", "#ebdbb2", "#fffaea", "#3c3836")),
    Style("latte", "Catppuccin Latte", "light",
          _surfaces("#eff1f5", "#f8f9fb", "#e6e9ef", "#dce0e8", "#ffffff", "#2b2d42")),
    Style("high-contrast-light", "High Contrast Light", "light",
          _surfaces("#ffffff", "#ffffff", "#f0f0f0", "#f0f0f0", "#ffffff", "#000000")),
    Style("twilight", "Twilight", "dark",
          _surfaces("#2a2438", "#221d2f", "#332a45", "#2d2640", "#372f4b", "#ece6f6")),
    Style("midnight", "Midnight", "dark",
          _surfaces("#0f1420", "#0a0e18", "#151b2b", "#111726", "#1a2133", "#dde4f0")),
    Style("nord", "Nord", "dark",
          _surfaces("#2e3440", "#272c36", "#3b4252", "#353b49", "#3b4252", "#eceff4")),
    Style("dracula", "Dracula", "dark",
          _surfaces("#282a36", "#21222c", "#343746", "#2d2f3d", "#343746", "#f8f8f2")),
    Style("gruvbox-dark", "Gruvbox Dark", "dark",
          _surfaces("#282828", "#1d2021", "#32302f", "#2c2a29", "#3c3836", "#fbf1c7")),
    Style("solarized-dark", "Solarized Dark", "dark",
          _surfaces("#002b36", "#00222b", "#073642", "#05303b", "#073642", "#eee8d5")),
    Style("mocha", "Catppuccin Mocha", "dark",
          _surfaces("#1e1e2e", "#181825", "#272739", "#232334", "#313244", "#cdd6f4")),
    Style("tokyo-night", "Tokyo Night", "dark",
          _surfaces("#1a1b26", "#16161e", "#24283b", "#1f2133", "#24283b", "#c0caf5")),
    Style("forest", "Forest", "dark",
          _surfaces("#1b2620", "#151e19", "#22312a", "#1f2c25", "#263830", "#dcebe1")),
    Style("ember", "Ember", "dark",
          _surfaces("#2a1f1c", "#221917", "#352723", "#30231f", "#3b2c27", "#f3e4dc")),
    Style("oled", "Black", "dark",
          _surfaces("#000000", "#000000", "#0d0d0d", "#080808", "#121212", "#e6e6e6")),
    Style("high-contrast-dark", "High Contrast Dark", "dark",
          _surfaces("#000000", "#000000", "#1a1a1a", "#141414", "#1a1a1a", "#ffffff")),
)


def style_by_id(style_id: str) -> Style:
    """The style with that id, or Follow System for an unknown one."""
    return next((s for s in STYLES if s.id == style_id), STYLES[0])


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio of two hex colors (1 to 21)."""
    la, lb = sorted((relative_luminance(hex_to_rgb(a)), relative_luminance(hex_to_rgb(b))),
                    reverse=True)
    return (la + 0.05) / (lb + 0.05)


def style_css(style: Style) -> str:
    """CSS setting libadwaita's surface colors (empty for untinted styles)."""
    if not style.tinted:
        return ""
    variables = "".join(f" --{k}: {v};" for k, v in style.colors.items())
    legacy = "".join(f"@define-color {k.replace('-color', '').replace('-', '_')}_color {v};\n"
                     for k, v in style.colors.items())
    return f":root {{{variables} }}\n{legacy}"
