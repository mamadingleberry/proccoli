"""Time-series graph widget and its legend, drawn with Cairo."""

from __future__ import annotations

import math
import weakref
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")
import cairo  # noqa: E402
from gi.repository import Adw, GLib, Gtk, Pango, PangoCairo  # noqa: E402

from .history import History, Series  # noqa: E402

# Categorical palette (fixed order; a series keeps its slot for its lifetime).
# Separate steps for light and dark surfaces, validated for colour-vision
# deficiencies on adjacent pairs.
PALETTE_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                 "#e87ba4", "#008300", "#6250d6", "#e34948"]
PALETTE_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500",
                "#d55181", "#0ca30c", "#9085e9", "#e66767"]


def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore


def is_dark() -> bool:
    return Adw.StyleManager.get_default().get_dark()


def series_color(slot: int, widget=None) -> tuple[float, float, float]:
    """The slot's colour: from the window's theme when the user picked a
    palette (``widget.get_root().theme``), else intel_gpu_top_gui's own."""
    root = widget.get_root() if widget is not None else None
    theme = getattr(root, "theme", None)
    if theme is not None and not theme.palette.follows_accent:
        return theme.series_rgb(slot)
    pal = PALETTE_DARK if is_dark() else PALETTE_LIGHT
    return hex_to_rgb(pal[slot % len(pal)])


def format_value(v: Optional[float], unit: str) -> str:
    if v is None:
        return "–"
    if unit == "%":
        return f"{v:.1f} %"
    if unit == "MHz":
        return f"{v:.0f} MHz"
    if unit == "W":
        return f"{v:.2f} W"
    if unit in ("MiB/s",):
        if v >= 1024:
            return f"{v / 1024:.2f} GiB/s"
        return f"{v:.0f} MiB/s"
    if unit == "irq/s":
        return f"{v:.0f} irq/s"
    if abs(v) >= 100:
        return f"{v:.0f} {unit}".strip()
    return f"{v:.2f} {unit}".strip()


DISPLAY_NAMES = {
    "value": "Residency", "count": "Rate", "requested": "Requested",
    "actual": "Actual", "reads": "Reads", "writes": "Writes",
}


def display_name(name: str) -> str:
    return DISPLAY_NAMES.get(name, name)


def format_axis(v: float, unit: str) -> str:
    if unit == "%":
        return f"{v:.0f} %"
    if unit == "MiB/s" and v >= 1024:
        return f"{v / 1024:g} GiB/s"
    if v >= 1000:
        return f"{v / 1000:g}k {unit}"
    if v and abs(v) < 10 and v != int(v):
        return f"{v:.1f} {unit}"
    return f"{v:.0f} {unit}"


def nice_ceiling(v: float) -> float:
    """Round up to 1, 2, 2.5 or 5 times a power of ten."""
    if v <= 0:
        return 1.0
    exp = math.floor(math.log10(v))
    base = 10 ** exp
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * base + 1e-9:
            return m * base
    return 10 * base


class AxisGroup:
    """Shares one y-axis label width between graphs, so their plot areas
    line up vertically whatever their units are."""

    def __init__(self) -> None:
        self._widths: "weakref.WeakKeyDictionary[GraphView, int]" = \
            weakref.WeakKeyDictionary()
        self._pending = False

    @property
    def width(self) -> int:
        return max(self._widths.values(), default=0)

    def report(self, graph: "GraphView", width: int) -> None:
        if self._widths.get(graph) == width:
            return
        before = self.width
        self._widths[graph] = width
        if self.width != before and not self._pending:
            self._pending = True
            GLib.idle_add(self._redraw)

    def _redraw(self) -> bool:
        self._pending = False
        for g in list(self._widths):
            g.queue_draw()
        return False


class GraphView(Gtk.DrawingArea):
    """Plots every series of one history group against time.

    The graph adapts to its allocation: its natural height is ``height``, but
    it shrinks down to a small floor so that all graphs fit in a small or
    snapped window, and grows to share any spare height of a large one.  Axis margins follow the measured label sizes, so large
    text settings never clip, and grid lines are snapped to device pixels so
    they stay sharp at any (fractional) display scale.
    """

    MIN_MARGIN_LEFT = 36
    MARGIN_RIGHT = 8
    MIN_MARGIN_TOP = 8
    LABEL_GAP = 6          # between the axis labels and the plot area
    TIME_LABEL_SPACING = 110  # target pixels between time ticks
    FLOOR = 64             # smallest graph height (room for a 1-interval plot)
    FLOOR_COMPACT = 40
    MIN_PLOT_FOR_TIME_LABELS = 40  # shorter plots drop the time axis labels

    def __init__(self, history: History, group: str, unit: str,
                 fixed_max: Optional[float], height: int = 150,
                 axis_group: Optional[AxisGroup] = None) -> None:
        super().__init__()
        self.axis_group = axis_group
        self.history = history
        self.group = group
        self.unit = unit
        self.fixed_max = fixed_max
        self.interval_s = 1.0
        self.hidden: set[str] = set()
        self.slots: dict[str, int] = {}
        self._hover_x: Optional[float] = None
        self._smoothed_max: Optional[float] = None

        self.natural_height = height
        self.floor = self.FLOOR
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_draw_func(self._draw)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    def slot_for(self, name: str) -> int:
        if name not in self.slots:
            self.slots[name] = len(self.slots)
        return self.slots[name]

    def set_compact(self, compact: bool) -> None:
        floor = self.FLOOR_COMPACT if compact else self.FLOOR
        if floor != self.floor:
            self.floor = floor
            self.queue_resize()

    def do_measure(self, orientation, _for_size):
        if orientation == Gtk.Orientation.VERTICAL:
            return self.floor, max(self.floor, self.natural_height), -1, -1
        return 160, 160, -1, -1

    # -- events -----------------------------------------------------------

    def _on_motion(self, _ctrl, x, _y) -> None:
        self._hover_x = x
        self.queue_draw()

    def _on_leave(self, _ctrl) -> None:
        self._hover_x = None
        self.queue_draw()

    # -- drawing ----------------------------------------------------------

    def _visible_series(self) -> list[Series]:
        out = []
        for s in self.history.group_series(self.group):
            self.slot_for(s.name)
            if s.name not in self.hidden:
                out.append(s)
        return out

    def _y_max(self, series: list[Series]) -> float:
        if self.fixed_max is not None:
            return self.fixed_max
        peak = 0.0
        for s in series:
            for v in s.values:
                if v is not None and v > peak:
                    peak = v
        peak = peak * 1.1 if peak > 0 else 1.0
        if self.unit == "MiB/s" and peak > 1024:
            return nice_ceiling(peak / 1024) * 1024
        return nice_ceiling(peak)

    def _layout(self, cr, text: str, scale: float = 0.85):
        layout = PangoCairo.create_layout(cr)
        desc = self.get_pango_context().get_font_description().copy()
        size = desc.get_size() or 10 * Pango.SCALE
        desc.set_size(int(size * scale))
        layout.set_font_description(desc)
        layout.set_text(text, -1)
        return layout

    def _device_scale(self) -> float:
        """Logical-to-device pixel ratio, including fractional scaling."""
        native = self.get_native()
        surface = native.get_surface() if native is not None else None
        if surface is not None and hasattr(surface, "get_scale"):  # GTK >= 4.12
            scale = surface.get_scale()
        else:
            scale = self.get_scale_factor()
        return scale if scale and scale > 0 else 1.0

    def _draw(self, _area, cr, width: int, height: int) -> None:
        fg = self.get_color()  # theme text colour (GTK >= 4.10)
        fr, fg_, fb = fg.red, fg.green, fg.blue
        dark = is_dark()
        scale = self._device_scale()
        hair_dev = max(1, round(scale))      # hairline: whole device pixels
        hair = hair_dev / scale

        def crisp(v: float) -> float:
            return snap_to_device(v, scale, hair_dev)

        series = self._visible_series()
        ymax = self._y_max(series)

        # Measure the axis labels first: they decide the margins.
        probe = self._layout(cr, "now")
        _, text_h = probe.get_pixel_size()
        margin_top = max(self.MIN_MARGIN_TOP, math.ceil(text_h / 2) + 1)
        margin_bottom = text_h + self.LABEL_GAP
        show_time = height - margin_top - margin_bottom >= self.MIN_PLOT_FOR_TIME_LABELS
        if not show_time:
            margin_bottom = margin_top
        y0 = margin_top
        y1 = height - margin_bottom
        ph = y1 - y0
        divisions = y_divisions(ph, text_h)
        if ph <= 10:
            return
        y_layouts = [self._layout(cr, format_axis(ymax * i / divisions, self.unit))
                     for i in range(divisions + 1)]
        label_w = max(lay.get_pixel_size()[0] for lay in y_layouts)
        x0 = max(self.MIN_MARGIN_LEFT, label_w + self.LABEL_GAP + 4)
        if self.axis_group is not None:
            self.axis_group.report(self, x0)
            x0 = max(x0, self.axis_group.width)
        x1 = width - self.MARGIN_RIGHT
        pw = x1 - x0
        if pw <= 10 or ph <= 10:
            return

        # Plot background, slightly offset from the window surface.
        cr.set_source_rgba(fr, fg_, fb, 0.035 if not dark else 0.05)
        cr.rectangle(x0, y0, pw, ph)
        cr.fill()

        # Horizontal grid + y labels.
        cr.set_line_width(hair)
        for i, layout in enumerate(y_layouts):
            y = crisp(y1 - ph * i / divisions)
            cr.set_source_rgba(fr, fg_, fb, 0.10 if i else 0.25)
            cr.move_to(x0, y)
            cr.line_to(x1, y)
            cr.stroke()
            tw, th = layout.get_pixel_size()
            cr.set_source_rgba(fr, fg_, fb, 0.65)
            cr.move_to(x0 - tw - self.LABEL_GAP, y - th / 2)
            PangoCairo.show_layout(cr, layout)

        # Vertical grid + time labels; tick spacing follows the plot width.
        n_max = max(self.history.max_points, 2)
        span_s = (n_max - 1) * self.interval_s
        step = pw / (n_max - 1)
        tick_s = time_tick(span_s, pw / self.TIME_LABEL_SPACING)
        last_label_x = None
        t = 0.0
        while t <= span_s + 1e-6:
            x = crisp(x1 - pw * t / span_s)
            cr.set_source_rgba(fr, fg_, fb, 0.10)
            cr.move_to(x, y0)
            cr.line_to(x, y1)
            cr.stroke()
            label = "now" if t == 0 else _fmt_duration(t)
            layout = self._layout(cr, label)
            tw, th = layout.get_pixel_size()
            lx = min(max(x - tw / 2, x0), x1 - tw)
            # Labels run right to left; skip one that would overlap.
            if show_time and (last_label_x is None or lx + tw + 4 <= last_label_x):
                cr.set_source_rgba(fr, fg_, fb, 0.65)
                cr.move_to(lx, y1 + self.LABEL_GAP // 2)
                PangoCairo.show_layout(cr, layout)
                last_label_x = lx
            t += tick_s

        # Series.
        cr.save()
        cr.rectangle(x0, y0 - 2, pw, ph + 4)
        cr.clip()
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        line_w = 2 if ph >= 60 else 1.5
        n = len(self.history.times)
        for s in series:
            r, g, b = series_color(self.slot_for(s.name), self)
            vals = list(s.values)
            pts = []
            for i, v in enumerate(vals):
                x = x1 - (n - 1 - i) * step
                if v is None:
                    pts.append(None)
                else:
                    pts.append((x, y1 - ph * min(v, ymax) / ymax))
            for run in _runs(pts):
                if self.fixed_max is not None and len(series) <= 4:
                    cr.move_to(run[0][0], y1)
                    for px, py in run:
                        cr.line_to(px, py)
                    cr.line_to(run[-1][0], y1)
                    cr.close_path()
                    cr.set_source_rgba(r, g, b, 0.10)
                    cr.fill()
                cr.move_to(*run[0])
                for p in run[1:]:
                    cr.line_to(*p)
                cr.set_source_rgb(r, g, b)
                cr.set_line_width(line_w)
                cr.stroke()
        cr.restore()

        if self._hover_x is not None and n:
            self._draw_hover(cr, series, x0, x1, y0, y1, step, ymax,
                             (fr, fg_, fb), dark, width, height, crisp, hair)

    def _draw_hover(self, cr, series, x0, x1, y0, y1, step, ymax, fg, dark,
                    width, height, crisp, hair) -> None:
        n = len(self.history.times)
        hx = min(max(self._hover_x, x0), x1)
        back = round((x1 - hx) / step)
        idx = n - 1 - back
        if idx < 0 or idx >= n:
            return
        x = x1 - back * step
        ph = y1 - y0
        cr.set_source_rgba(*fg, 0.45)
        cr.set_line_width(hair)
        cr.move_to(crisp(x), y0)
        cr.line_to(crisp(x), y1)
        cr.stroke()

        lines = [("", f"{_fmt_duration(back * self.interval_s)} ago" if back else "now")]
        for s in series:
            v = s.values[idx] if idx < len(s.values) else None
            if v is not None:
                r, g, b = series_color(self.slot_for(s.name), self)
                y = y1 - ph * min(v, ymax) / ymax
                # Marker with a surface ring.
                cr.arc(x, y, 5, 0, 2 * math.pi)
                cr.set_source_rgb(*((0.12, 0.12, 0.12) if dark else (1, 1, 1)))
                cr.fill()
                cr.arc(x, y, 3.5, 0, 2 * math.pi)
                cr.set_source_rgb(r, g, b)
                cr.fill()
            lines.append((s.name, format_value(v, s.unit)))

        # Tooltip box.
        layouts = []
        tw = th = 0
        for i, (name, val) in enumerate(lines):
            text = val if not name else f"{display_name(name)}   {val}"
            lay = self._layout(cr, text, 0.9)
            if i == 0:
                lay.set_attributes(_bold_attrs())
            w, h = lay.get_pixel_size()
            layouts.append((name, lay, h))
            tw = max(tw, w + (16 if name else 0))
            th += h + 2
        pad = 8
        bw, bh = tw + 2 * pad, th + 2 * pad - 2
        bx = x + 12 if x + 12 + bw < width else x - 12 - bw
        bx = max(bx, 0)
        # Short graphs: keep as much of the box inside the widget as possible.
        by = max(0, min(y0 + 4, height - bh))
        _rounded_rect(cr, bx, by, bw, bh, 6)
        if dark:
            cr.set_source_rgba(0.16, 0.16, 0.17, 0.96)
        else:
            cr.set_source_rgba(1, 1, 1, 0.97)
        cr.fill_preserve()
        cr.set_source_rgba(*fg, 0.18)
        cr.set_line_width(hair)
        cr.stroke()
        cy = by + pad
        for name, lay, h in layouts:
            cx = bx + pad
            if name:
                r, g, b = series_color(self.slot_for(name), self)
                _rounded_rect(cr, cx, cy + h / 2 - 4, 8, 8, 2)
                cr.set_source_rgb(r, g, b)
                cr.fill()
                cx += 16
            cr.set_source_rgba(*fg, 1.0)
            cr.move_to(cx, cy)
            PangoCairo.show_layout(cr, lay)
            cy += h + 2



def time_tick(span_s: float, max_ticks: float = 6) -> float:
    """Smallest round tick interval giving at most ``max_ticks`` intervals."""
    target = span_s / max(2.0, max_ticks)
    for t in (1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1800, 3600):
        if t >= target:
            return float(t)
    return 3600.0


def y_divisions(plot_h: float, text_h: float) -> int:
    """Number of horizontal grid intervals that fit without crowding labels."""
    for d in (4, 2):
        if plot_h / d >= max(text_h * 1.6, 24):
            return d
    return 1


def snap_to_device(v: float, scale: float, line_dev_px: int = 1) -> float:
    """Position a line of ``line_dev_px`` device pixels on the pixel grid."""
    d = round(v * scale)
    if line_dev_px % 2:
        d += 0.5
    return d / scale


def _bold_attrs():
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_weight_new(Pango.Weight.BOLD))
    return attrs


def _runs(pts):
    run = []
    for p in pts:
        if p is None:
            if run:
                yield run
            run = []
        else:
            run.append(p)
    if run:
        yield run


def _fmt_duration(s: float) -> str:
    s = int(round(s))
    if s < 60:
        return f"{s} s"
    if s % 60 == 0:
        return f"{s // 60} min"
    return f"{s // 60}:{s % 60:02d}"


def _rounded_rect(cr, x, y, w, h, r) -> None:
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class Swatch(Gtk.DrawingArea):
    def __init__(self, graph: GraphView, name: str) -> None:
        super().__init__()
        self.graph = graph
        self.name = name
        self.set_content_width(14)
        self.set_content_height(14)
        self.set_valign(Gtk.Align.CENTER)
        self.set_draw_func(self._draw)

    def _draw(self, _a, cr, w, h) -> None:
        r, g, b = series_color(self.graph.slot_for(self.name), self)
        _rounded_rect(cr, 1, 1, w - 2, h - 2, 3)
        if self.name in self.graph.hidden:
            cr.set_source_rgb(r, g, b)
            cr.set_line_width(2)
            cr.stroke()
        else:
            cr.set_source_rgb(r, g, b)
            cr.fill()


class LegendItem(Gtk.ToggleButton):
    """Swatch + name + current value.  Click to show/hide the series."""

    def __init__(self, graph: GraphView, name: str) -> None:
        super().__init__()
        self.graph = graph
        self.name = name
        self.add_css_class("flat")
        self.add_css_class("legend-item")
        self.set_active(True)
        self.set_tooltip_text(f"Show or hide {display_name(name)}")
        self.set_focus_on_click(False)

        box = Gtk.Box(spacing=8)
        self.swatch = Swatch(graph, name)
        box.append(self.swatch)
        self.labels = labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.name_label = Gtk.Label(label=display_name(name), xalign=0)
        self.name_label.add_css_class("caption")
        self.name_label.add_css_class("dim-label")
        self.value_label = Gtk.Label(label="–", xalign=0)
        self.value_label.add_css_class("numeric")
        self.value_label.set_width_chars(10)
        labels.append(self.name_label)
        labels.append(self.value_label)
        box.append(labels)
        self.set_child(box)
        self.connect("toggled", self._on_toggled)

    def set_compact(self, compact: bool) -> None:
        """One line (name and value side by side) instead of two."""
        self.labels.set_orientation(Gtk.Orientation.HORIZONTAL if compact
                                    else Gtk.Orientation.VERTICAL)
        self.labels.set_spacing(6 if compact else 0)
        self.value_label.set_width_chars(8 if compact else 10)

    def _on_toggled(self, _btn) -> None:
        if self.get_active():
            self.graph.hidden.discard(self.name)
            self.remove_css_class("legend-off")
        else:
            self.graph.hidden.add(self.name)
            self.add_css_class("legend-off")
        self.swatch.queue_draw()
        self.graph.queue_draw()

    def set_value(self, text: str) -> None:
        self.value_label.set_label(text)


class GraphSection(Gtk.Box):
    """Title, graph and legend for one metric group."""

    def __init__(self, history: History, group: str, title: str, unit: str,
                 fixed_max: Optional[float], height: int,
                 subtitle: str = "", axis_group: Optional[AxisGroup] = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.group = group
        self.history = history
        self.add_css_class("graph-section")

        header = Gtk.Box(spacing=8)
        tl = Gtk.Label(label=title, xalign=0)
        tl.add_css_class("heading")
        header.append(tl)
        self.subtitle = Gtk.Label(label=subtitle, xalign=0, hexpand=True)
        self.subtitle.add_css_class("dim-label")
        self.subtitle.add_css_class("caption")
        self.subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        header.append(self.subtitle)
        self.append(header)

        self.min_height = height  # relative size, used to share out space
        self.compact = False
        self.graph = GraphView(history, group, unit, fixed_max, height,
                               axis_group)
        self.append(self.graph)

        self.legend = Gtk.FlowBox()
        self.legend.set_selection_mode(Gtk.SelectionMode.NONE)
        self.legend.set_max_children_per_line(8)
        self.legend.set_min_children_per_line(1)
        self.legend.set_column_spacing(4)
        self.legend.set_row_spacing(2)
        self.legend.set_homogeneous(False)
        self.append(self.legend)
        self.items: dict[str, LegendItem] = {}

    def set_compact(self, compact: bool) -> None:
        """Denser layout for short (tiled or small-screen) windows."""
        self.compact = compact
        self.set_spacing(2 if compact else 6)
        self.subtitle.set_visible(not compact)
        self.graph.set_compact(compact)
        for item in self.items.values():
            item.set_compact(compact)

    def set_interval(self, seconds: float) -> None:
        self.graph.interval_s = seconds

    def refresh(self) -> None:
        for s in self.history.group_series(self.group):
            item = self.items.get(s.name)
            if item is None:
                item = LegendItem(self.graph, s.name)
                item.set_compact(self.compact)
                self.items[s.name] = item
                self.legend.append(item)
            v = s.values[-1] if s.values else None
            item.set_value(format_value(v, s.unit))
        self.graph.queue_draw()

    def redraw_colors(self) -> None:
        for item in self.items.values():
            item.swatch.queue_draw()
        self.graph.queue_draw()

