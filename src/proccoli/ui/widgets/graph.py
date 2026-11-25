"""Resources-style graph: a rounded area plot of one or more series.

The look (rounded corners, tinted background, filled area under a line in
the accent color, optional grid) follows Resources' observable design; the
code is our own, with pixel-snapping and palette helpers ported from
intel_gpu_top_gui.

Stretches filled from the history for a time Proccoli wasn't running
(``Series.offline``) get a dithered bar under the lines (M68).
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Callable, Optional, Sequence

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gtk, Pango, PangoCairo  # noqa: E402

from ...core.history import Series, offline_runs  # noqa: E402
from ...core.units import format_reading, nice_ceiling  # noqa: E402,F401
from ...core.palette import (RGB, entry_colors, hex_to_rgb, offline_rgba,  # noqa: E402,F401
                             secondary)
from ..axes import (AxisGutter, is_percent_graph, percent_ticks, time_ticks,  # noqa: E402
                    value_ticks)
from ..hover import ago_text, box_origin, hover_point, offline_text  # noqa: E402
from ..layout import aspect_height  # noqa: E402
from ..theme import DEFAULT_ACCENT, default_theme_colors, theme_of  # noqa: E402


class GraphStyle(str, Enum):
    NORMAL = "normal"   # page graphs
    SMALL = "small"     # sidebar meters and Overview cards


STYLE_METRICS = {
    # style: (min height, corner radius, line width)
    GraphStyle.NORMAL: (120, 8.0, 2.0),
    GraphStyle.SMALL: (36, 6.0, 1.5),
}


# -- pure helpers (unit-tested) ---------------------------------------------------

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


def offline_spans(flags: Sequence[bool], capacity: int,
                  width: float) -> list[tuple[float, float]]:
    """``(x0, x1)`` of each offline run, placed like ``graph_runs`` places
    points (newest at the right edge), widened by half a point each side
    so neighbouring runs and lines meet, clamped to the plot."""
    if capacity < 2 or width <= 0 or not flags:
        return []
    step = width / (capacity - 1)
    n = len(flags)
    spans = []
    for first, last in offline_runs(flags):
        x0 = width - (n - 1 - first) * step - step / 2
        x1 = width - (n - 1 - last) * step + step / 2
        if x1 > 0:
            spans.append((max(0.0, x0), min(width, x1)))
    return spans


def dither_pattern(rgba: tuple[float, float, float, float], scale: float):
    """A 2×2 checker of ``rgba`` and clear, one pattern pixel per device
    pixel at ``scale``, repeating."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 2, 2)
    c = cairo.Context(surface)
    c.set_source_rgba(*rgba)
    c.rectangle(0, 0, 1, 1)
    c.rectangle(1, 1, 1, 1)
    c.fill()
    pattern = cairo.SurfacePattern(surface)
    pattern.set_extend(cairo.EXTEND_REPEAT)
    pattern.set_filter(cairo.FILTER_NEAREST)
    pattern.set_matrix(cairo.Matrix(xx=scale, yy=scale))   # user space → pattern pixels
    return pattern


def offline_color(widget=None) -> tuple[float, float, float, float]:
    """The dither color from ``widget``'s window theme (``Theme.
    offline_rgba``), or from the default palette without one."""
    theme = theme_of(widget)
    if theme is not None:
        return theme.offline_rgba()
    return offline_rgba(accent_rgb(), Adw.StyleManager.get_default().get_dark())


def auto_max(series: Sequence[Series], floor: float = 0.0,
             nice: Callable[[float], float] = None) -> float:
    """The automatic scale: the peak (at least ``floor``) rounded up by
    ``nice`` (default ``nice_ceiling``)."""
    peak = max((s.peak() or 0.0 for s in series), default=0.0)
    return (nice or nice_ceiling)(max(peak, floor))


def rounded_rect(cr, x, y, w, h, r) -> None:
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def accent_rgb() -> RGB:
    """The desktop's accent color (for widgets outside a themed window)."""
    sm = Adw.StyleManager.get_default()
    if hasattr(sm, "get_accent_color_rgba"):  # libadwaita >= 1.6
        c = sm.get_accent_color_rgba()
        return (c.red, c.green, c.blue)
    return DEFAULT_ACCENT


def entry_rgb(index: int, series: int, widget=None) -> RGB:
    """A sidebar entry's color (``Theme.entry_rgb``), or the default
    palette's without a theme."""
    theme = theme_of(widget)
    if theme is not None:
        return theme.entry_rgb(index, series)
    dark = Adw.StyleManager.get_default().get_dark()
    color = entry_colors(default_theme_colors(dark, accent_rgb()), index + 1)[index]
    return secondary(color, dark) if series else color


def series_rgb(index: int, widget=None) -> RGB:
    """Color of the index-th series: from the theme of ``widget``'s
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
        # A sidebar entry's color index (all series in that color), or None.
        self.entry_index: Optional[int] = None
        # On a device page: its entry's index, so the page's colors start at
        # the color its sidebar entry has.
        self.entry_base: Optional[int] = None
        # Palette slot of the first series; 1 skips the accent color (for a
        # graph that sits next to another, like Write next to Read).
        self.color_offset = 0
        # Many lines in one graph (the per-CPU chart, M55): no fill, which
        # would muddy them; a distinct color each (entry_colors makes as
        # many as needed); lines the legend switched off.
        self.fill = True
        self.distinct = False
        self.hidden: set[int] = set()
        # Value axes (Idea 3): a label for a tick value turns axes on for a
        # graph that isn't a percentage (MHz, W, ...); a shared gutter lines
        # up the plots of several graphs.
        self.axis_format: Optional[Callable[[float], str]] = None
        self.axis_gutter: Optional[AxisGutter] = None
        # Rounds the automatic maximum (default nice_ceiling); a graph whose
        # labels switch unit (MiB/s to GiB/s) rounds in the shown unit.
        self.nice_max: Optional[Callable[[float], float]] = None
        # Hover crosshair (Idea 3): each line's name and value at the pointer.
        self.names: list[str] = []
        self.value_format: Optional[Callable[[int, Optional[float]], str]] = None
        self.hover = False
        self.hover_x: Optional[float] = None
        height, self.radius, self.line_width = STYLE_METRICS[self.style]
        self.set_content_height(height)
        self.set_hexpand(True)
        self.add_css_class("graph" if self.style == GraphStyle.NORMAL else "small-graph")
        # Colors come from the window's Theme, which redraws its graphs when
        # the palette or the light/dark style changes (ui/window.py).
        self.set_draw_func(self._draw)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)
        self.set_hover(self.style == GraphStyle.NORMAL)

    # -- hover (Idea 3) ------------------------------------------------------------

    def set_hover(self, on: bool,
                  value_format: Optional[Callable[[int, Optional[float]], str]] = None) -> None:
        """A crosshair at the pointer with every shown line's value there
        (on by default for page graphs and Overview cards). ``value_format(
        index, value)`` formats them; without it, by unit."""
        self.hover = on
        if value_format is not None:
            self.value_format = value_format
        if not on and self.hover_x is not None:
            self.hover_x = None
            self.queue_draw()

    def set_names(self, names: Sequence[str]) -> None:
        """The lines' names in the hover box (default: the series' names)."""
        self.names = list(names)

    def _on_motion(self, _ctrl, x, _y) -> None:
        if self.hover:
            self.hover_x = x
            self.queue_draw()

    def _on_leave(self, _ctrl) -> None:
        if self.hover_x is not None:
            self.hover_x = None
            self.queue_draw()

    def name_for(self, index: int) -> str:
        if index < len(self.names):
            return self.names[index]
        return self.series[index].name if index < len(self.series) else ""

    def format_for(self, index: int, value: Optional[float]) -> str:
        if self.value_format is not None:
            return self.value_format(index, value)
        unit = self.series[index].unit if index < len(self.series) else ""
        return format_reading(value, unit)

    def hover_lines(self, plot_w: float) -> Optional[tuple]:
        """(point, [(index, text)], heading) under the pointer, or None."""
        if not self.hover or self.hover_x is None:
            return None
        shown = [(i, s) for i, s in enumerate(self.series) if i not in self.hidden]
        if not shown:
            return None
        capacity = max(s.capacity for _, s in shown)
        n = max(len(s.values) for _, s in shown)
        point = hover_point(self.hover_x - self._plot_x, plot_w, capacity, n)
        if point is None:
            return None
        flags = self.offline_flags()
        if flags is not None and len(flags) == n:
            off = offline_text(flags, point.index, capacity, self.time_span_s)
            if off is not None:
                return point, [], off
        rows = []
        for i, s in shown:
            k = point.index - (n - len(s.values))
            value = s.values[k] if 0 <= k < len(s.values) else None
            rows.append((i, f"{self.name_for(i)}   {self.format_for(i, value)}"
                         if len(shown) > 1 or self.name_for(i) else self.format_for(i, value)))
        return point, rows, ago_text(point.back, capacity, self.time_span_s)

    def offline_flags(self):
        """The shown series' offline flags (shared by a history's series),
        or None."""
        return next((s.offline for s in self.series if s.offline is not None), None)

    def set_series(self, series: Sequence[Series],
                   colors: Optional[Sequence[Optional[RGB]]] = None,
                   color_offset: int = 0) -> None:
        self.series = list(series)
        self.colors = list(colors) if colors else []
        self.color_offset = color_offset
        self.queue_draw()

    def set_fill(self, fill: bool) -> None:
        """Shade the area under each line (on by default)."""
        if fill != self.fill:
            self.fill = fill
            self.queue_draw()

    def set_distinct_colors(self, distinct: bool) -> None:
        """A different color for every series, however many (palettes
        have only 6–8 colors, which would repeat)."""
        if distinct != self.distinct:
            self.distinct = distinct
            self.queue_draw()

    def set_series_shown(self, index: int, shown: bool) -> None:
        """Draw series ``index`` or leave it out (its legend item's toggle)."""
        if shown == (index not in self.hidden):
            return
        if shown:
            self.hidden.discard(index)
        else:
            self.hidden.add(index)
        self.queue_draw()

    def series_shown(self, index: int) -> bool:
        return index not in self.hidden

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
        return auto_max(self.series, self.min_max, self.nice_max)

    def set_entry_base(self, index: Optional[int]) -> None:
        """Start this graph's colors at sidebar entry ``index``'s color."""
        if index != self.entry_base:
            self.entry_base = index
            self.queue_draw()

    def set_entry_color(self, index: Optional[int]) -> None:
        """Draw in the color of sidebar entry ``index`` (series after the
        first in its secondary shade); None: the palette's series colors."""
        if index != self.entry_index:
            self.entry_index = index
            self.queue_draw()

    def color_for(self, index: int) -> RGB:
        if index < len(self.colors) and self.colors[index] is not None:
            return self.colors[index]
        if self.entry_index is not None:
            return entry_rgb(self.entry_index, index, self)
        if self.distinct:
            return entry_rgb((self.entry_base or 0) + self.color_offset + index, 0, self)
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

    def is_percent(self) -> bool:
        return is_percent_graph([s.unit for s in self.series], self.max_value)

    def has_axes(self) -> bool:
        """Axes when *Show Graph Axes* is on, for percentage graphs and for
        graphs given an ``axis_format``."""
        return self.show_axes and (self.is_percent() or self.axis_format is not None)

    def set_axis_format(self, fmt: Optional[Callable[[float], str]],
                        gutter: Optional[AxisGutter] = None) -> None:
        """Label a value axis with ``fmt(value)`` (a graph that isn't a
        percentage); ``gutter`` shares the label width with other graphs."""
        self.axis_format = fmt
        self.axis_gutter = gutter
        self.queue_draw()

    def y_tick_labels(self, plot_h: float, label_h: float) -> list[tuple[float, Optional[str]]]:
        """(fraction of the plot height from the bottom, label or None)."""
        if self.is_percent() or self.axis_format is None:
            return [(v / 100.0, label) for v, label in percent_ticks(plot_h, label_h)]
        y_max = self.y_max()
        return [(v / y_max, self.axis_format(v)) for v in value_ticks(y_max, plot_h, label_h)]

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
        if not self.is_percent():
            # The same plot height _draw_axes uses, so the same ticks.
            plot_h = max(1.0, height - label_h - self.TICK - label_h / 2)
            label_w = max((self._layout(t).get_pixel_size()[0]
                           for _f, t in self.y_tick_labels(plot_h, label_h) if t), default=0)
        left = label_w + 2 * self.TICK
        if self.axis_gutter is not None:
            self.axis_gutter.report(self, left)
            left = max(left, self.axis_gutter.width)
        bottom = label_h + self.TICK
        return left, label_h / 2, max(1.0, width - left), max(1.0, height - bottom - label_h / 2)

    TICK = 4

    def _draw_axes(self, cr, fg, rect, hair) -> None:
        x0, y0, w, h = rect
        _, label_h = self._layout("0").get_pixel_size()
        cr.set_line_width(hair)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.45)
        ticks = self.y_tick_labels(h, label_h)
        for frac, _label in ticks:
            y = y0 + h - h * frac
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
        for frac, label in ticks:
            if label:
                layout = self._layout(label)
                lw, lh = layout.get_pixel_size()
                cr.move_to(x0 - self.TICK - 2 - lw, y0 + h - h * frac - lh / 2)
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
        self._plot_x = rect[0]
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
        self._draw_hover(cr, rect, width, height)

    _plot_x = 0.0

    def _draw_hover(self, cr, rect, width: int, height: int) -> None:
        found = self.hover_lines(rect[2])
        if found is None:
            return
        point, rows, heading = found
        x0, y0, w, h = rect
        fg = self.get_color()
        scale = self._device_scale()
        hair_dev = max(1, round(scale))
        x = x0 + point.x
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.45)
        cr.set_line_width(hair_dev / scale)
        cr.move_to(snap_to_device(x, scale, hair_dev), y0)
        cr.line_to(snap_to_device(x, scale, hair_dev), y0 + h)
        cr.stroke()
        dark = Adw.StyleManager.get_default().get_dark()
        y_max = self.y_max()
        for i, _text in rows:
            s = self.series[i]
            k = point.index - (max(len(t.values) for t in self.series) - len(s.values))
            v = s.values[k] if 0 <= k < len(s.values) else None
            if v is None:
                continue
            y = y0 + h - h * min(max(v / y_max, 0.0), 1.0)
            cr.arc(x, y, 5, 0, 2 * math.pi)
            cr.set_source_rgb(*((0.12, 0.12, 0.12) if dark else (1, 1, 1)))
            cr.fill()
            cr.arc(x, y, 3.5, 0, 2 * math.pi)
            cr.set_source_rgb(*self.color_for(i))
            cr.fill()
        # The box: the time, then a swatch, name and value per line.
        swatch = 12 if len(rows) > 1 else 0
        layouts = [(None, self._layout(heading))]
        layouts += [(i, self._layout(text)) for i, text in rows]
        sizes = [lay.get_pixel_size() for _i, lay in layouts]
        pad = 6
        box_w = max(sw + (swatch if i is not None else 0)
                    for (i, _l), (sw, _h) in zip(layouts, sizes)) + 2 * pad
        box_h = sum(sh + 2 for _w, sh in sizes) + 2 * pad - 2
        bx, by = box_origin(x, box_w, box_h, width, height, y0)
        rounded_rect(cr, bx, by, box_w, box_h, 6)
        cr.set_source_rgba(*((0.16, 0.16, 0.17, 0.96) if dark else (1, 1, 1, 0.97)))
        cr.fill_preserve()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.18)
        cr.set_line_width(hair_dev / scale)
        cr.stroke()
        cy = by + pad
        for (i, layout), (_sw, sh) in zip(layouts, sizes):
            cx = bx + pad
            if i is not None and swatch:
                rounded_rect(cr, cx, cy + sh / 2 - 4, 8, 8, 2)
                cr.set_source_rgb(*self.color_for(i))
                cr.fill()
                cx += swatch
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 1.0)
            cr.move_to(cx, cy)
            PangoCairo.show_layout(cr, layout)
            cy += sh + 2

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

        flags = self.offline_flags()
        if flags:
            capacity = max((s.capacity for s in self.series), default=0)
            spans = offline_spans(list(flags), capacity, width)
            if spans:
                cr.set_source(dither_pattern(offline_color(self), scale))
                for x0, x1 in spans:
                    x0, x1 = round(x0 * scale) / scale, round(x1 * scale) / scale
                    cr.rectangle(x0, 0, x1 - x0, height)
                cr.fill()

        y_max = self.y_max()
        cr.set_line_width(self.line_width)
        cr.set_line_join(1)  # cairo.LINE_JOIN_ROUND
        for index, s in enumerate(self.series):
            if index in self.hidden:
                continue
            r, g, b = self.color_for(index)
            for run in graph_runs(list(s.values), s.capacity, width, height, y_max):
                if self.fill:                    # shaded area under the line
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
