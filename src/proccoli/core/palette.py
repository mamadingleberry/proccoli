"""Colour palettes for graphs, meters and the accent colour (DESIGN.md §9.3).

Eight palettes after GNOME Terminal's built-in schemes (and Nord). Each
has a light variant (the terminal's normal colours, for light surfaces) and
a dark variant (its bright colours, for dark surfaces), in series order:
blue, red, green, yellow, magenta, cyan. *System* keeps the desktop's
accent colour as the first series, followed by colour-blind-friendly steps.

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
    light: tuple[str, ...]        # series colours on light surfaces
    dark: tuple[str, ...]         # series colours on dark surfaces
    follows_accent: bool = False  # first series = the desktop's accent colour

    def colors(self, dark: bool) -> tuple[str, ...]:
        return self.dark if dark else self.light


PALETTES: tuple[Palette, ...] = (
    Palette("system", "System",
            ("#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"),
            ("#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"),
            follows_accent=True),
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
    """Palette colours, minus those too similar to the accent colour (with
    an orange accent, an orange second series would be indistinguishable)."""
    colours = [hex_to_rgb(h) for h in palette]
    kept = [c for c in colours if math.dist(c, accent) >= min_distance]
    return kept or colours


def series_colors(palette: Palette, dark: bool, accent: RGB) -> list[RGB]:
    """Series colours in order: for System the accent first, then the
    steps that don't clash with it; otherwise the palette as it is."""
    if palette.follows_accent:
        return [accent] + palette_without(accent, palette.colors(dark))
    return [hex_to_rgb(h) for h in palette.colors(dark)]


def accent_of(palette: Palette, dark: bool, accent: RGB) -> RGB:
    """The accent colour the app uses: the desktop's for System, else the
    palette's first colour."""
    return series_colors(palette, dark, accent)[0]


def mix(a: RGB, b: RGB, t: float) -> RGB:
    """``a`` moved a fraction ``t`` (0..1) towards ``b``."""
    return tuple(x + (y - x) * t for x, y in zip(a, b))  # type: ignore


WHITE: RGB = (1.0, 1.0, 1.0)
BLACK: RGB = (0.0, 0.0, 0.0)
# Shades for entries past the palette's length: (towards, amount), in order.
_SHADES = ((WHITE, 0.45), (BLACK, 0.35), (WHITE, 0.7), (BLACK, 0.6))


def entry_colors(colors: Sequence[RGB], n: int) -> list[RGB]:
    """``n`` distinct colours for sidebar entries: the palette's colours,
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
    """A second series in an entry's colour (network: send, under receive):
    the same hue moved towards the surface, so it reads as secondary."""
    return mix(color, BLACK if dark else WHITE, 0.45)
