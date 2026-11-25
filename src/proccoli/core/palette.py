"""Color palettes for graphs, meters and the accent color.

Each palette has a light variant (for light surfaces) and a dark variant
(for dark surfaces), in series order, starting with a blue:

- *System* keeps the desktop's accent color as the first series, followed
  by color-blind-friendly steps.
- **Color-blind safe:** Okabe–Ito, Paul Tol's Bright, Vibrant and Muted,
  and Viridis: told apart with the common forms of color blindness.
- **Data visualization:** Tableau 10, Matplotlib's default, ColorBrewer's
  Set 1 and Dark 2.
- **Editor themes** with their own light and dark variants: Catppuccin
  (Latte and Mocha), Gruvbox, One (Light and Dark), Tokyo Night (Day and
  Night).
- **Terminal schemes** after GNOME Terminal's built-in ones (and Nord):
  normal colors on light surfaces, bright ones on dark.

Colors are the published ones; a palette's order may differ from its
source so it starts with a blue, and a color too pale for a light surface
(or too dark for a dark one) is left out of that variant.

Pure data and arithmetic: no GTK, so it's testable anywhere.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

RGB = tuple[float, float, float]


@dataclass(frozen=True)
class Palette:
    id: str                       # settings nick
    name: str                     # shown in Preferences
    light: tuple[str, ...]        # series colors on light surfaces
    dark: tuple[str, ...]         # series colors on dark surfaces
    follows_accent: bool = False  # first series = the desktop's accent color

    def colors(self, dark: bool) -> tuple[str, ...]:
        return self.dark if dark else self.light


PALETTES: tuple[Palette, ...] = (
    Palette("system", "System",
            ("#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"),
            ("#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"),
            follows_accent=True),
    # Color-blind safe.
    Palette("okabe-ito", "Okabe–Ito (Color-Blind Safe)",
            ("#0072b2", "#d55e00", "#009e73", "#e69f00", "#cc79a7", "#56b4e9"),
            ("#56b4e9", "#e69f00", "#009e73", "#f0e442", "#cc79a7", "#d55e00")),
    Palette("tol-bright", "Tol Bright (Color-Blind Safe)",
            ("#4477aa", "#ee6677", "#228833", "#ccbb44", "#aa3377", "#66ccee"),
            ("#4477aa", "#ee6677", "#228833", "#ccbb44", "#aa3377", "#66ccee")),
    Palette("tol-vibrant", "Tol Vibrant (Color-Blind Safe)",
            ("#0077bb", "#ee7733", "#009988", "#ee3377", "#33bbee", "#cc3311"),
            ("#0077bb", "#ee7733", "#009988", "#ee3377", "#33bbee", "#cc3311")),
    Palette("tol-muted", "Tol Muted (Color-Blind Safe)",
            ("#332288", "#cc6677", "#117733", "#ddcc77", "#882255", "#88ccee",
             "#44aa99", "#999933", "#aa4499"),
            ("#88ccee", "#cc6677", "#44aa99", "#ddcc77", "#aa4499", "#999933",
             "#117733", "#882255", "#6699cc")),
    Palette("viridis", "Viridis (Color-Blind Safe)",
            ("#3b528b", "#21918c", "#5ec962", "#fde725", "#440154", "#2c728e"),
            ("#31688e", "#35b779", "#fde725", "#90d743", "#21918c", "#3e4989")),
    # Data visualization.
    Palette("tableau", "Tableau 10",
            ("#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948",
             "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"),
            ("#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948",
             "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac")),
    Palette("matplotlib", "Matplotlib",
            ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
             "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"),
            ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
             "#e377c2", "#7f7f7f", "#bcbd22", "#17becf")),
    Palette("brewer-set1", "ColorBrewer Set 1",
            ("#377eb8", "#e41a1c", "#4daf4a", "#984ea3", "#ff7f00", "#a65628", "#f781bf"),
            ("#377eb8", "#e41a1c", "#4daf4a", "#984ea3", "#ff7f00", "#a65628", "#f781bf")),
    Palette("brewer-dark2", "ColorBrewer Dark 2",
            ("#7570b3", "#d95f02", "#1b9e77", "#e7298a", "#66a61e", "#e6ab02", "#a6761d"),
            ("#7570b3", "#d95f02", "#1b9e77", "#e7298a", "#66a61e", "#e6ab02", "#a6761d")),
    # Editor themes.
    Palette("catppuccin", "Catppuccin",
            ("#1e66f5", "#d20f39", "#40a02b", "#df8e1d", "#8839ef", "#179299"),
            ("#89b4fa", "#f38ba8", "#a6e3a1", "#f9e2af", "#cba6f7", "#94e2d5")),
    Palette("gruvbox", "Gruvbox",
            ("#076678", "#9d0006", "#79740e", "#b57614", "#8f3f71", "#427b58"),
            ("#83a598", "#fb4934", "#b8bb26", "#fabd2f", "#d3869b", "#8ec07c")),
    Palette("one", "One",
            ("#4078f2", "#e45649", "#50a14f", "#c18401", "#a626a4", "#0184bc"),
            ("#61afef", "#e06c75", "#98c379", "#e5c07b", "#c678dd", "#56b6c2")),
    Palette("tokyo-night", "Tokyo Night",
            ("#2e7de9", "#f52a65", "#587539", "#8c6c3e", "#9854f1", "#007197"),
            ("#7aa2f7", "#f7768e", "#9ece6a", "#e0af68", "#bb9af7", "#7dcfff")),
    # Terminal schemes.
    Palette("gnome", "GNOME",
            ("#12488b", "#c01c28", "#26a269", "#a2734c", "#a347ba", "#2aa1b3"),
            ("#2a7bde", "#f66151", "#33da7a", "#e9ad0c", "#c061cb", "#33c7de")),
    Palette("tango", "Tango",
            ("#3465a4", "#cc0000", "#4e9a06", "#c4a000", "#75507b", "#06989a"),
            ("#729fcf", "#ef2929", "#8ae234", "#fce94f", "#ad7fa8", "#34e2e2")),
    Palette("solarized", "Solarized",
            ("#268bd2", "#dc322f", "#859900", "#b58900", "#d33682", "#2aa198"),
            ("#268bd2", "#dc322f", "#859900", "#b58900", "#d33682", "#2aa198")),
    Palette("linux", "Linux Console",
            ("#0000aa", "#aa0000", "#00aa00", "#aa5500", "#aa00aa", "#00aaaa"),
            ("#5555ff", "#ff5555", "#55ff55", "#ffff55", "#ff55ff", "#55ffff")),
    Palette("xterm", "XTerm",
            ("#0000ee", "#cd0000", "#00cd00", "#cdcd00", "#cd00cd", "#00cdcd"),
            ("#5c5cff", "#ff0000", "#00ff00", "#ffff00", "#ff00ff", "#00ffff")),
    Palette("rxvt", "Rxvt",
            ("#0000cd", "#cd0000", "#00cd00", "#cdcd00", "#cd00cd", "#00cdcd"),
            ("#4040ff", "#ff0000", "#00ff00", "#ffff00", "#ff00ff", "#00ffff")),
    Palette("nord", "Nord",
            ("#5e81ac", "#bf616a", "#a3be8c", "#d08770", "#b48ead", "#8fbcbb"),
            ("#88c0d0", "#bf616a", "#a3be8c", "#ebcb8b", "#b48ead", "#8fbcbb")),
)
DEFAULT_PALETTE = "system"


def palette_by_id(palette_id: str) -> Palette:
    """The palette with that id, or System for an unknown one."""
    return next((p for p in PALETTES if p.id == palette_id), PALETTES[0])


def hex_to_rgb(h: str) -> RGB:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore


def rgb_to_hex(rgb: RGB) -> str:
    return "#" + "".join(f"{round(min(max(c, 0.0), 1.0) * 255):02x}" for c in rgb)


def relative_luminance(rgb: RGB) -> float:
    """WCAG relative luminance, 0 (black) to 1 (white)."""
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def palette_without(accent: RGB, palette: Sequence[str],
                    min_distance: float = 0.3) -> list[RGB]:
    """Palette colors, minus those too similar to the accent color (with
    an orange accent, an orange second series would be indistinguishable)."""
    colors = [hex_to_rgb(h) for h in palette]
    kept = [c for c in colors if math.dist(c, accent) >= min_distance]
    return kept or colors


def series_colors(palette: Palette, dark: bool, accent: RGB) -> list[RGB]:
    """Series colors in order: for System the accent first, then the
    steps that don't clash with it; otherwise the palette as it is."""
    if palette.follows_accent:
        return [accent] + palette_without(accent, palette.colors(dark))
    return [hex_to_rgb(h) for h in palette.colors(dark)]


def accent_of(palette: Palette, dark: bool, accent: RGB) -> RGB:
    """The accent color the app uses: the desktop's for System, else the
    palette's first color."""
    return series_colors(palette, dark, accent)[0]


def mix(a: RGB, b: RGB, t: float) -> RGB:
    """``a`` moved a fraction ``t`` (0..1) towards ``b``."""
    return tuple(x + (y - x) * t for x, y in zip(a, b))  # type: ignore


WHITE: RGB = (1.0, 1.0, 1.0)
BLACK: RGB = (0.0, 0.0, 0.0)
# Shades for entries past the palette's length: (towards, amount), in order.
_SHADES = ((WHITE, 0.45), (BLACK, 0.35), (WHITE, 0.7), (BLACK, 0.6))


def entry_colors(colors: Sequence[RGB], n: int) -> list[RGB]:
    """``n`` distinct colors for sidebar entries: the palette's colors,
    then lighter and darker shades of them (a palette has only 6–8)."""
    out: list[RGB] = []
    base = list(colors)
    for i in range(n):
        cycle, j = divmod(i, len(base))
        c = base[j]
        if cycle:
            target, amount = _SHADES[(cycle - 1) % len(_SHADES)]
            c = mix(c, target, min(amount + 0.1 * ((cycle - 1) // len(_SHADES)), 0.95))
        out.append(c)
    return out


def secondary(color: RGB, dark: bool) -> RGB:
    """A second series in an entry's color (network: send, under receive):
    the same hue moved towards the surface, so it reads as secondary."""
    return mix(color, BLACK if dark else WHITE, 0.45)


# Time Proccoli wasn't running, on graphs filled from the history: a
# dithered bar in a near-black shade of the palette's accent. Not a series
# color, so it never reads as data; tinted, so it belongs to the palette.
# Dark surfaces need it denser to show at all.
OFFLINE_TOWARDS_BLACK = 0.8
OFFLINE_ALPHA = {False: 0.4, True: 0.75}          # light, dark


def offline_rgba(accent: RGB, dark: bool) -> tuple[float, float, float, float]:
    """The dither color for "not recording" (each lit pixel of a 2×2
    checker): the accent moved most of the way to black, with an alpha
    for the surface."""
    r, g, b = mix(accent, BLACK, OFFLINE_TOWARDS_BLACK)
    return r, g, b, OFFLINE_ALPHA[dark]

