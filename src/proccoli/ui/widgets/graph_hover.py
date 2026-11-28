"""A graph's hover readout: a crosshair at the pointer, a dot on each
shown line, and a box with the time and each line's name and value there
(or, over a stretch Proccoli wasn't running, how long that was).

``Graph`` owns one and draws it last; the arithmetic (which point, where
the box goes, the texts) is in the display-free ``ui/hover.py``.
"""

from __future__ import annotations

import math
from typing import Callable, Optional, Sequence

from gi.repository import Adw, Gtk, PangoCairo

from ...core.units import format_reading
from ..hover import ago_text, box_origin, hover_point, offline_text

ValueFormat = Callable[[int, Optional[float]], str]


class GraphHover:
    def __init__(self, graph, on: bool) -> None:
        self.graph = graph
        self.on = on
        self.x: Optional[float] = None           # the pointer, while over the graph
        self.names: list[str] = []
        self.value_format: Optional[ValueFormat] = None
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        graph.add_controller(motion)

    def set(self, on: bool, value_format: Optional[ValueFormat] = None) -> None:
        self.on = on
        if value_format is not None:
            self.value_format = value_format
        if not on and self.x is not None:
            self.x = None
            self.graph.queue_draw()

    def set_names(self, names: Sequence[str]) -> None:
        self.names = list(names)

    def _on_motion(self, _ctrl, x, _y) -> None:
        if self.on:
            self.x = x
            self.graph.queue_draw()

    def _on_leave(self, _ctrl) -> None:
        if self.x is not None:
            self.x = None
            self.graph.queue_draw()

    # -- what it says ---------------------------------------------------------------

    def name_for(self, index: int) -> str:
        series = self.graph.series
        if index < len(self.names):
            return self.names[index]
        return series[index].name if index < len(series) else ""

    def format_for(self, index: int, value: Optional[float]) -> str:
        if self.value_format is not None:
            return self.value_format(index, value)
        series = self.graph.series
        unit = series[index].unit if index < len(series) else ""
        return format_reading(value, unit)

    def lines(self, plot_x: float, plot_w: float) -> Optional[tuple]:
        """(point, [(index, text)], heading) under the pointer, or None."""
        graph = self.graph
        if not self.on or self.x is None:
            return None
        shown = [(i, s) for i, s in enumerate(graph.series) if i not in graph.hidden]
        if not shown:
            return None
        capacity = max(s.capacity for _, s in shown)
        n = max(len(s.values) for _, s in shown)
        point = hover_point(self.x - plot_x, plot_w, capacity, n)
        if point is None:
            return None
        flags = graph.offline_flags()
        if flags is not None and len(flags) == n:
            off = offline_text(flags, point.index, capacity, graph.time_span_s)
            if off is not None:
                return point, [], off
        rows = []
        for i, s in shown:
            k = point.index - (n - len(s.values))
            value = s.values[k] if 0 <= k < len(s.values) else None
            rows.append((i, f"{self.name_for(i)}   {self.format_for(i, value)}"
                         if len(shown) > 1 or self.name_for(i) else self.format_for(i, value)))
        return point, rows, ago_text(point.back, capacity, graph.time_span_s)

    # -- drawing ---------------------------------------------------------------------

    def draw(self, cr, rect, width: int, height: int, snap, rounded_rect) -> None:
        """The crosshair, the dots and the box, over the plot at ``rect``.
        ``snap`` and ``rounded_rect`` are the graph's pixel helpers."""
        graph = self.graph
        found = self.lines(rect[0], rect[2])
        if found is None:
            return
        point, rows, heading = found
        x0, y0, w, h = rect
        fg = graph.get_color()
        scale = graph._device_scale()
        hair_dev = max(1, round(scale))
        x = x0 + point.x
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.45)
        cr.set_line_width(hair_dev / scale)
        cr.move_to(snap(x, scale, hair_dev), y0)
        cr.line_to(snap(x, scale, hair_dev), y0 + h)
        cr.stroke()
        dark = Adw.StyleManager.get_default().get_dark()
        y_max = graph.y_max()
        for i, _text in rows:
            s = graph.series[i]
            k = point.index - (max(len(t.values) for t in graph.series) - len(s.values))
            v = s.values[k] if 0 <= k < len(s.values) else None
            if v is None:
                continue
            y = y0 + h - h * min(max(v / y_max, 0.0), 1.0)
            cr.arc(x, y, 5, 0, 2 * math.pi)
            cr.set_source_rgb(*((0.12, 0.12, 0.12) if dark else (1, 1, 1)))
            cr.fill()
            cr.arc(x, y, 3.5, 0, 2 * math.pi)
            cr.set_source_rgb(*graph.color_for(i))
            cr.fill()
        # The box: the time, then a swatch, name and value per line.
        swatch = 12 if len(rows) > 1 else 0
        layouts = [(None, graph._layout(heading))]
        layouts += [(i, graph._layout(text)) for i, text in rows]
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
                cr.set_source_rgb(*graph.color_for(i))
                cr.fill()
                cx += swatch
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 1.0)
            cr.move_to(cx, cy)
            PangoCairo.show_layout(cr, layout)
            cy += sh + 2
