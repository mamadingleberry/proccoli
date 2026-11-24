"""Resources-style graph: a rounded area plot of one or more series.

The look (rounded corners, tinted background, filled area under a line in
the accent colour, optional grid) follows Resources' observable design; the
code is our own, with pixel-snapping and palette helpers ported from
intel_gpu_top_gui.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Optional, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gtk, Pango, PangoCairo  # noqa: E402

from ...core.history import Series  # noqa: E402
from ...core.palette import RGB, entry_colors, hex_to_rgb, secondary  # noqa: E402,F401
from ..axes import is_percent_graph, percent_ticks, time_ticks  # noqa: E402
from ..layout import aspect_height  # noqa: E402
from ..theme import DEFAULT_ACCENT, default_theme_colors, theme_of  # noqa: E402


class GraphStyle(str, Enum):
    NORMAL = "normal"   # page graphs
    SMALL = "small"     # sidebar meters and per-thread CPU graphs


STYLE_METRICS = {
    # style: (min height, corner radius, line width)
    GraphStyle.NORMAL: (120, 8.0, 2.0),
    GraphStyle.SMALL: (36, 6.0, 1.5),
}


# -- pure helpers (unit-tested) ---------------------------------------------------

def nice_ceiling(v: float) -> float:
    """Round up to 1, 2, 2.5 or 5 times a power of ten (axis maximum)."""
    if v <= 0:
        return 1.0
    exp = math.floor(math.log10(v))
    base = 10 ** exp
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * base * (1 + 1e-9):
            return m * base
    return 10 * base


def snap_to_device(v: float, scale: float, line_dev_px: int = 1) -> float:
    """Position a line of ``line_dev_px`` device pixels on the pixel grid,
    so hairlines stay sharp at any (fractional) display scale."""
    d = round(v * scale)
    if line_dev_px % 2:
        d += 0.5
    return d / scale


def graph_runs(values: Sequence[Optional[float]], capacity: int, width: float,
               height: float, y_max: float) -> list[list[tuple[float, float]]]:
    """Map values to points, newest at the right edge, oldest scrolling off
    the left. ``None`` breaks the line, so the result is a list of runs."""
    if capacity < 2 or y_max <= 0 or not values:
        return []
    step = width / (capacity - 1)
    n = len(values)
    runs: list[list[tuple[float, float]]] = []
    run: list[tuple[float, float]] = []
    for i, v in enumerate(values):
        if v is None:
            if run:
                runs.append(run)
            run = []
            continue
        x = width - (n - 1 - i) * step
        frac = min(max(v / y_max, 0.0), 1.0)
        run.append((x, height - frac * height))
    if run:
        runs.append(run)
    return runs


def auto_max(series: Sequence[Series], floor: float = 0.0) -> float:
    peak = max((s.peak() or 0.0 for s in series), default=0.0)
    return nice_ceiling(max(peak, floor))


def rounded_rect(cr, x, y, w, h, r) -> None:
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def accent_rgb() -> RGB:
    """The desktop's accent colour (for widgets outside a themed window)."""
    sm = Adw.StyleManager.get_default()
    if hasattr(sm, "get_accent_color_rgba"):  # libadwaita >= 1.6
        c = sm.get_accent_color_rgba()
        return (c.red, c.green, c.blue)
    return DEFAULT_ACCENT


def entry_rgb(index: int, series: int, widget=None) -> RGB:
    """A sidebar entry's colour (``Theme.entry_rgb``), or the default
    palette's without a theme."""
    theme = theme_of(widget)
    if theme is not None:
        return theme.entry_rgb(index, series)
    dark = Adw.StyleManager.get_default().get_dark()
    color = entry_colors(default_theme_colors(dark, accent_rgb()), index + 1)[index]
    return secondary(color, dark) if series else color


def series_rgb(index: int, widget=None) -> RGB:
    """Colour of the index-th series: from the theme of ``widget``'s
    window, or the default palette (accent first) without one."""
    theme = theme_of(widget)
    if theme is not None:
        return theme.series_rgb(index)
    colors = default_theme_colors(Adw.StyleManager.get_default().get_dark(), accent_rgb())
    return colors[index % len(colors)]


# -- widget ---------------------------------------------------------------------------

class Graph(Gtk.DrawingArea):
    """Plots ``Series`` objects against a fixed or automatic maximum.

    ``max_value=None`` scales to the data (rounded up to a nice value);
    ``min_max`` keeps automatic scaling from zooming into noise.
    """

    GRID_ROWS = 4

    def __init__(self, style: GraphStyle = GraphStyle.NORMAL,
                 max_value: Optional[float] = 100.0, min_max: float = 0.0) -> None:
        super().__init__()
        self.style = GraphStyle(style)
        self.max_value = max_value
        self.min_max = min_max
        self.show_grid = False
        self.show_axes = False
        self.time_span_s: Optional[float] = None
        self.series: list[Series] = []
        self.colors: list[Optional[RGB]] = []
        self.aspect: Optional[tuple[float, int, int]] = None
        # A sidebar entry's colour index (all series in that colour), or None.
        self.entry_index: Optional[int] = None
        # On a device page: its entry's index, so the page's colours start at
        # the colour its sidebar entry has.
        self.entry_base: Optional[int] = None
        # Palette slot of the first series; 1 skips the accent colour (for a
        # graph that sits next to another, like Write next to Read).
        self.color_offset = 0
        height, self.radius, self.line_width = STYLE_METRICS[self.style]
        self.set_content_height(height)
        self.set_hexpand(True)
        self.add_css_class("graph" if self.style == GraphStyle.NORMAL else "small-graph")
        # Colours come from the window's Theme, which redraws its graphs when
        # the palette or the light/dark style changes (ui/window.py).
        self.set_draw_func(self._draw)

    def set_series(self, series: Sequence[Series],
                   colors: Optional[Sequence[Optional[RGB]]] = None,
                   color_offset: int = 0) -> None:
        self.series = list(series)
        self.colors = list(colors) if colors else []
        self.color_offset = color_offset
        self.queue_draw()

    def set_aspect(self, ratio: Optional[float], minimum: int = 32,
                   maximum: int = 400) -> None:
        """Height follows width (``ratio`` = height/width, within
        ``minimum``..``maximum``), e.g. for a grid of per-CPU graphs that
        should grow with the window. None: fixed content height."""
        self.aspect = (ratio, minimum, maximum) if ratio else None
        self.queue_resize()

    def do_get_request_mode(self) -> Gtk.SizeRequestMode:
        if getattr(self, "aspect", None):
            return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH
        return Gtk.SizeRequestMode.CONSTANT_SIZE

    def do_measure(self, orientation, for_size):
        # As GtkDrawingArea does (content size), plus the aspect mode; no
        # baselines (-1).
        aspect = getattr(self, "aspect", None)
        if orientation == Gtk.Orientation.HORIZONTAL:
            w = self.get_content_width()
            return w, w, -1, -1
        if aspect is None:
            h = self.get_content_height()
            return h, h, -1, -1
        ratio, minimum, maximum = aspect
        if for_size < 0:
            return minimum, minimum, -1, -1
        # Also the minimum: a scrolled page gives its content only its
        # minimum height once it's taller than the window.
        h = aspect_height(for_size, ratio, minimum, maximum)
        return h, h, -1, -1

    def set_max(self, max_value: Optional[float]) -> None:
        self.max_value = max_value
        self.queue_draw()

    def set_show_grid(self, show: bool) -> None:
        if show != self.show_grid:
            self.show_grid = show
            self.queue_draw()

    def y_max(self) -> float:
        if self.max_value is not None:
            return self.max_value
        return auto_max(self.series, self.min_max)

    def set_entry_base(self, index: Optional[int]) -> None:
        """Start this graph's colours at sidebar entry ``index``'s colour."""
        if index != self.entry_base:
            self.entry_base = index
            self.queue_draw()

    def set_entry_color(self, index: Optional[int]) -> None:
        """Draw in the colour of sidebar entry ``index`` (series after the
        first in its secondary shade); None: the palette's series colours."""
        if index != self.entry_index:
            self.entry_index = index
            self.queue_draw()

    def color_for(self, index: int) -> RGB:
        if index < len(self.colors) and self.colors[index] is not None:
            return self.colors[index]
        if self.entry_index is not None:
            return entry_rgb(self.entry_index, index, self)
        if self.entry_base is not None:
            return entry_rgb(self.entry_base + self.color_offset + index, 0, self)
        return series_rgb(index + self.color_offset, self)

    def _device_scale(self) -> float:
        native = self.get_native()
        surface = native.get_surface() if native is not None else None
        if surface is not None and hasattr(surface, "get_scale"):  # GTK >= 4.12
            return surface.get_scale() or 1.0
        return float(self.get_scale_factor() or 1)

    # -- axes (DESIGN.md §9.1) -----------------------------------------------------

    def set_show_axes(self, show: bool) -> None:
        """Axis labels and ticks, for percentage graphs only."""
        if show != self.show_axes:
            self.show_axes = show
            self.queue_draw()

    def set_time_span(self, seconds: Optional[float]) -> None:
        """How much time the full width shows (history length × interval)."""
        if seconds != self.time_span_s:
            self.time_span_s = seconds
            self.queue_draw()

    def has_axes(self) -> bool:
        return self.show_axes and is_percent_graph([s.unit for s in self.series],
                                                   self.max_value)

    def _layout(self, text: str):
        layout = self.create_pango_layout(text)
        font = Pango.FontDescription.from_string(
            "Sans 7" if self.style == GraphStyle.SMALL else "Sans 8")
        layout.set_font_description(font)
        return layout

    def plot_rect(self, width: int, height: int) -> tuple[float, float, float, float]:
        """(x, y, w, h) of the plot inside the widget: the whole widget, or
        what's left beside the y labels and above the time labels."""
        if not self.has_axes():
            return 0.0, 0.0, float(width), float(height)
        label_w, label_h = self._layout("100 %").get_pixel_size()
        left = label_w + 2 * self.TICK
        bottom = label_h + self.TICK
        return left, label_h / 2, max(1.0, width - left), max(1.0, height - bottom - label_h / 2)

    TICK = 4

    def _draw_axes(self, cr, fg, rect, hair) -> None:
        x0, y0, w, h = rect
        _, label_h = self._layout("0").get_pixel_size()
        cr.set_line_width(hair)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.45)
        ticks = percent_ticks(h, label_h)
        for value, _label in ticks:
            y = y0 + h - h * value / 100.0
            cr.move_to(x0 - self.TICK, y)
            cr.line_to(x0, y)
        span = self.time_span_s or 0.0
        xticks = time_ticks(span, w) if span else [(1.0, "now")]
        for frac, _label in xticks:
            x = x0 + w * frac
            cr.move_to(x, y0 + h)
            cr.line_to(x, y0 + h + self.TICK)
        cr.stroke()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.7)
        for value, label in ticks:
            if label:
                layout = self._layout(label)
                lw, lh = layout.get_pixel_size()
                cr.move_to(x0 - self.TICK - 2 - lw, y0 + h - h * value / 100.0 - lh / 2)
                PangoCairo.show_layout(cr, layout)
        for frac, label in xticks:
            layout = self._layout(label)
            lw, _ = layout.get_pixel_size()
            x = x0 + w * frac - lw / 2
            x = min(max(x, x0), x0 + w - lw)      # keep the end labels inside
            cr.move_to(x, y0 + h + self.TICK)
            PangoCairo.show_layout(cr, layout)

    def _draw(self, _area, cr, width: int, height: int) -> None:
        if width <= 2 or height <= 2:
            return
        rect = self.plot_rect(width, height)
        if rect[2] < 4 or rect[3] < 4:
            return
        if rect[:2] != (0.0, 0.0) or rect[2:] != (width, height):
            fg = self.get_color()
            scale = self._device_scale()
            hair = max(1, round(scale)) / scale
            self._draw_axes(cr, fg, rect, hair)
            cr.save()
            cr.translate(rect[0], rect[1])
            self._draw_plot(cr, rect[2], rect[3])
            cr.restore()
        else:
            self._draw_plot(cr, width, height)

    def _draw_plot(self, cr, width: float, height: float) -> None:
        fg = self.get_color()
        scale = self._device_scale()
        hair_dev = max(1, round(scale))
        hair = hair_dev / scale

        cr.save()
        rounded_rect(cr, 0, 0, width, height, self.radius)
        cr.clip()

        # Background tint, so an empty graph still reads as a graph.
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.06)
        cr.paint()

        if self.show_grid:
            cr.set_line_width(hair)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.12)
            for i in range(1, self.GRID_ROWS):
                y = snap_to_device(height * i / self.GRID_ROWS, scale, hair_dev)
                cr.move_to(0, y)
                cr.line_to(width, y)
            columns = 6 if self.style == GraphStyle.NORMAL else 3
            for i in range(1, columns):
                x = snap_to_device(width * i / columns, scale, hair_dev)
                cr.move_to(x, 0)
                cr.line_to(x, height)
            cr.stroke()

        y_max = self.y_max()
        cr.set_line_width(self.line_width)
        cr.set_line_join(1)  # cairo.LINE_JOIN_ROUND
        for index, s in enumerate(self.series):
            r, g, b = self.color_for(index)
            for run in graph_runs(list(s.values), s.capacity, width, height, y_max):
                # Filled area under the line.
                cr.move_to(run[0][0], height)
                for x, y in run:
                    cr.line_to(x, y)
                cr.line_to(run[-1][0], height)
                cr.close_path()
                cr.set_source_rgba(r, g, b, 0.22)
                cr.fill()
                # The line itself.
                cr.move_to(*run[0])
                for p in run[1:]:
                    cr.line_to(*p)
                cr.set_source_rgb(r, g, b)
                cr.stroke()
        cr.restore()
