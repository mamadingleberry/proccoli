"""Smoke tests for the widgets. They run only on the private headless
display (``make ui-test``); a plain ``make test`` skips them."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
from helpers import descendants  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
import cairo  # noqa: E402
from gi.repository import Adw, Gtk  # noqa: E402

from proccoli.core.history import History  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402

# Only on the private headless display (tests/run-headless.sh sets this),
# never on the desktop, where these tests would open real windows.
HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
    from proccoli.devices.demo import SineMonitor
    from proccoli.ui.pages.demo import DemoPage
    from proccoli.ui.widgets.double_graph_box import DoubleGraphBox
    from proccoli.ui.widgets.graph import Graph, GraphStyle, accent_rgb
    from proccoli.ui.widgets.graph_box import GraphBox
    from proccoli.ui.widgets.info_row import InfoRow
    from proccoli.ui.widgets.meter import Meter, MeterType


def render(graph, w=200, h=100):
    """Run a graph's draw function into an image; return a pixel reader."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)
    graph._draw(graph, cr, w, h)
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()

    def pixel(x, y):  # (r, g, b, a) premultiplied, 0..255
        i = y * stride + x * 4
        b, g, r, a = data[i:i + 4]
        return r, g, b, a
    return pixel


def flat_history(value, n=10, capacity=10):
    h = History(capacity)
    for t in range(n):
        h.add(float(t), {"v": value})
    return h


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GraphDrawTest(unittest.TestCase):
    def test_empty_graph_draws_background(self):
        px = render(Graph())
        self.assertGreater(px(100, 50)[3], 0)      # tinted
        self.assertEqual(px(0, 0)[3], 0)           # rounded corner left clear

    def test_line_and_fill_in_accent_colour(self):
        g = Graph(max_value=100)                       # no unit: no axes, full plot
        g.set_series([flat_history(50.0).series("v")])
        px = render(g)
        above, line, below = px(150, 20), px(150, 50), px(150, 80)
        self.assertLess(above[3], below[3])        # area under the line is filled
        r, gg, b = accent_rgb()
        lr, lg, lb, la = line
        # The line pixel is (close to) the accent colour.
        self.assertLess(abs(lr - r * la) + abs(lg - gg * la) + abs(lb - b * la), 60)

    def test_auto_scaling(self):
        g = Graph(max_value=None)
        g.set_series([flat_history(3.0).series("v")])
        self.assertEqual(g.y_max(), 5.0)

    def test_grid_toggle_changes_pixels(self):
        g = Graph(max_value=100)
        plain = render(g)(100, 25)
        g.set_show_grid(True)
        self.assertNotEqual(render(g)(100, 25), plain)

    def test_small_style(self):
        g = Graph(GraphStyle.SMALL)
        self.assertEqual(g.get_content_height(), 36)
        self.assertTrue(g.has_css_class("small-graph"))

    def test_graph_in_a_themed_window_uses_the_palette(self):
        from helpers import FakeStyleManager
        from proccoli.core.palette import hex_to_rgb
        from proccoli.core.settings import Settings
        from proccoli.ui.theme import Theme
        settings = Settings.for_tests({"palette": "tango"})
        win = Gtk.Window()
        win.theme = Theme(settings, FakeStyleManager())
        self.addCleanup(win.theme.shutdown)
        self.addCleanup(win.destroy)
        g = Graph(max_value=100)
        g.set_series([flat_history(50.0).series("v")])
        win.set_child(g)
        self.assertEqual(g.color_for(0), hex_to_rgb("#3465a4"))
        r, gg, b = hex_to_rgb("#3465a4")
        lr, lg, lb, la = render(g)(150, 50)
        self.assertLess(abs(lr - r * la) + abs(lg - gg * la) + abs(lb - b * la), 60)
        settings.set("palette", "nord")
        self.assertEqual(g.color_for(0), hex_to_rgb("#5e81ac"))

    def test_axes_on_percentage_graphs(self):
        g = Graph(max_value=100)
        g.set_series([flat_history(50.0).series("v")])        # unit "" : no axes
        g.set_show_axes(True)
        self.assertEqual(g.plot_rect(300, 150), (0.0, 0.0, 300.0, 150.0))
        h = History(10)
        h.define("u", "%")
        for t in range(10):
            h.add(float(t), {"u": 50.0})
        g.set_series([h.series("u")])
        g.set_time_span(60)
        x, y, w, hh = g.plot_rect(300, 150)
        self.assertGreater(x, 10)                               # room for "100 %"
        self.assertLess(hh, 150 - 10)                          # room for the time labels
        px = render(g, 300, 150)
        mid = int(y + hh / 2)                                   # the "50 %" label's row
        self.assertTrue(any(px(i, j)[3] for i in range(int(x) - 4)
                            for j in range(mid - 4, mid + 4)))
        g.set_show_axes(False)
        self.assertEqual(g.plot_rect(300, 150), (0.0, 0.0, 300.0, 150.0))

    def test_small_graphs_get_compact_axes(self):
        h = History(10)
        h.define("u", "%")
        g = Graph(GraphStyle.SMALL)
        g.set_series([h.series("u")])
        g.set_show_axes(True)
        small = g.plot_rect(200, 48)
        big = Graph(max_value=100)
        big.set_series([h.series("u")])
        big.set_show_axes(True)
        self.assertLess(small[0], big.plot_rect(200, 48)[0])   # smaller font, narrower gutter

    def test_hover_crosshair_and_values(self):
        # Idea 3: page graphs show every line's value at the pointer.
        h = History(11)
        h.define("u", "%")
        for t in range(11):
            h.add(float(t), {"u": float(t * 10)})
        g = Graph(max_value=100)
        self.assertTrue(g.hover)                                 # on for page graphs
        self.assertFalse(Graph(GraphStyle.SMALL).hover)          # not for sidebar meters
        g.set_series([h.series("u")])
        g.set_names(["Usage"])
        g.set_time_span(10)
        self.assertIsNone(g.hover_lines(100))                    # pointer elsewhere
        before = render(g, 100, 60)
        g._on_motion(None, 79, 0)
        point, rows, heading = g.hover_lines(100)
        self.assertEqual((point.index, heading), (8, "2 s ago"))
        self.assertEqual(rows, [(0, "Usage   80 %")])           # core.units.format_percent
        after = render(g, 100, 60)
        self.assertNotEqual([after(80, y) for y in range(60)],    # the crosshair
                            [before(80, y) for y in range(60)])
        g._on_leave(None)
        self.assertIsNone(g.hover_lines(100))
        g.set_hover(False)
        g._on_motion(None, 79, 0)
        self.assertIsNone(g.hover_lines(100))

    def test_hover_skips_hidden_lines_and_uses_the_formatter(self):
        h = History(5)
        for t in range(5):
            h.add(float(t), {"a": 1.0, "b": 2.0})
        g = Graph(max_value=None)
        g.set_series([h.series("a"), h.series("b")])
        g.set_hover(True, lambda i, v: f"{v:g} W")
        g.set_series_shown(0, False)
        g._on_motion(None, 100, 0)
        _point, rows, heading = g.hover_lines(100)
        self.assertEqual(heading, "now")
        self.assertEqual(rows, [(1, "b   2 W")])

    def test_value_axes_and_shared_gutter(self):
        from proccoli.ui.axes import AxisGutter
        h = flat_history(1500.0)
        g = Graph(max_value=None)
        g.set_series([h.series("v")])
        g.set_show_axes(True)
        self.assertFalse(g.has_axes())                           # not a percentage
        gutter = AxisGutter()
        g.set_axis_format(lambda v: f"{v:g} MHz", gutter)
        self.assertTrue(g.has_axes())
        labels = [t for _f, t in g.y_tick_labels(200, 12)]
        self.assertEqual(labels[0], "0 MHz")
        self.assertEqual(labels[-1], "2000 MHz")                 # nice_ceiling(1500)
        x = g.plot_rect(300, 150)[0]
        other = Graph(max_value=100)
        other.set_series([flat_history(1.0).series("v")])
        other.set_show_axes(True)
        other.set_axis_format(lambda v: f"{v:g}", gutter)
        self.assertEqual(other.plot_rect(300, 150)[0], x)        # lined up with the wider one

    def test_color_offset_skips_accent(self):
        g = Graph()
        g.set_series([flat_history(1.0).series("v")], color_offset=1)
        self.assertNotEqual(g.color_for(0), accent_rgb())


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class RowsTest(unittest.TestCase):
    def test_graph_box(self):
        box = GraphBox("Usage")
        box.set_info("42 %")
        self.assertEqual(box.pane.title_label.get_label(), "Usage")
        self.assertEqual(box.pane.info_label.get_label(), "42 %")
        self.assertEqual(box.get_title(), "Usage")

    def test_double_graph_box(self):
        box = DoubleGraphBox("Encode", "Decode")
        self.assertEqual(box.start.title_label.get_label(), "Encode")
        self.assertEqual(box.end.title_label.get_label(), "Decode")

    def test_info_row_hides_without_value(self):
        row = InfoRow("Link")
        self.assertFalse(row.get_visible())
        row.set_value("PCIe 4.0 x4")
        self.assertTrue(row.get_visible())
        self.assertEqual(row.get_value(), "PCIe 4.0 x4")
        row.set_value(None)
        self.assertFalse(row.get_visible())
        self.assertTrue(row.has_css_class("property"))

    def test_info_row_escapes_markup(self):
        row = InfoRow("Name", "Tom & Jerry <GPU>")
        self.assertEqual(row.get_value(), "Tom & Jerry <GPU>")
        # What's on screen: the subtitle label shows the text as given.
        shown = [w.get_text() for w in descendants(row)
                 if isinstance(w, Gtk.Label) and w.get_text() != "Name"]
        self.assertIn("Tom & Jerry <GPU>", shown)

    def test_info_row_sets_the_subtitle_only_on_change(self):
        row = InfoRow("Name", "a & b")
        calls = []
        row.connect("notify::subtitle", lambda *_: calls.append(1))
        row.set_value("a & b")
        self.assertEqual(calls, [])
        row.set_value("c")
        self.assertEqual(calls, [1])


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class MeterTest(unittest.TestCase):
    def test_modes_and_fraction(self):
        m = Meter()
        self.assertIs(m.meter_type, MeterType.GRAPH)             # area chart by default
        m.set_meter_type("progress-bar")
        self.assertIs(m.meter_type, MeterType.PROGRESS_BAR)
        m.set_fraction(1.7)
        self.assertEqual(m.progress.get_fraction(), 1.0)
        m.set_fraction(None)
        self.assertEqual(m.progress.get_fraction(), 0.0)

    def test_area_chart_spans_the_row_and_has_no_grid(self):
        m = Meter()
        h = flat_history(40.0)
        m.set_series([h.series("v")])
        self.assertTrue(m.graph.get_hexpand())
        self.assertFalse(m.graph.show_grid)
        px = render(m.graph, 200, 36)
        self.assertLess(px(100, 5)[3], px(100, 30)[3])          # filled under the line


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class DemoPageTest(unittest.TestCase):
    def test_updates_from_monitor_and_settings(self):
        settings = Settings.for_tests()
        monitor = SineMonitor(history_points=60)
        page = DemoPage(monitor, settings)
        for t in range(5):
            monitor.refresh(float(t))
        self.assertEqual(page.samples.get_value(), "5")
        self.assertTrue(page.usage.pane.info_label.get_label().endswith("%"))
        summary = page.sidebar_summary()
        self.assertEqual(summary.usage, monitor.latest.usage)
        self.assertEqual(summary.series, [monitor.history.series("usage")])

        settings.set("show-graph-grids", True)
        self.assertTrue(page.usage.graph.show_grid)
        settings.set("base", "binary")
        self.assertIn("iB/s", page.io.start.info_label.get_label())
        # The hover box follows the same unit preferences (M61).
        read = page.io.start.graph
        self.assertTrue(read.hover)
        self.assertEqual(read.format_for(0, 2048.0), "2.0 KiB/s")
        settings.set("network-bits", True)                # not a network page
        self.assertEqual(read.format_for(0, 2048.0), "2.0 KiB/s")
        self.assertEqual(page.usage.graph.format_for(0, 42.0), "42 %")


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class LegendChartTest(unittest.TestCase):
    """The reusable many-line chart (M59), on its own, outside any page."""

    def make(self, n=4):
        from proccoli.ui.widgets.legend_chart import LegendChart
        from proccoli.ui.widgets.graph_box import GraphBox
        history = History(30)
        series = [history.define(f"s{i}", "%") for i in range(n)]
        chart = LegendChart("Lines")
        chart.set_lines(series, [f"Line {i}" for i in range(n)])
        self.assertIs(chart.legend.get_ancestor(GraphBox), chart)    # inside the card
        return chart, series

    def test_lines_colours_values(self):
        chart, series = self.make()
        self.assertEqual(chart.graph.series, series)
        self.assertFalse(chart.graph.fill)
        self.assertEqual(len({chart.graph.color_for(i) for i in range(4)}), 4)
        chart.set_values(["1 %", "2 %", "3 %", "4 %"])
        self.assertEqual(chart.legend.items[2].value_label.get_label(), "3 %")
        items = chart.legend.items
        chart.set_lines(series, [f"Line {i}" for i in range(4)])          # unchanged: kept
        self.assertIs(chart.legend.items[0], items[0])

    def test_never_shows_nothing(self):
        chart, _ = self.make()
        legend, graph = chart.legend, chart.graph
        legend.items[1].solo()
        self.assertEqual(legend.shown(), [False, True, False, False])
        legend.items[1].emit("clicked")                    # deselect the only one
        self.assertEqual(legend.shown(), [True] * 4)
        self.assertTrue(all(graph.series_shown(i) for i in range(4)))

    def test_lines_without_data(self):
        chart, _ = self.make(3)
        legend, graph = chart.legend, chart.graph
        legend.set_available(2, False)
        self.assertFalse(legend.items[2].get_parent().get_visible())
        self.assertFalse(graph.series_shown(2))
        legend.items[0].emit("clicked")
        legend.items[1].emit("clicked")                    # the last line with data
        self.assertTrue(graph.series_shown(0) and graph.series_shown(1))
        self.assertFalse(graph.series_shown(2))            # still nothing to draw

    def test_standalone_legend_keeps_its_values(self):
        chart, _ = self.make()
        self.assertFalse(chart.fit_legend())               # not on screen: nothing to fit
        self.assertFalse(chart.legend.compact)
        self.assertGreater(chart.legend_height(0), 0)        # measurable for any page


if __name__ == "__main__":
    unittest.main()
