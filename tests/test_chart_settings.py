"""ui.chart_settings.ChartSettings: the one place graphs get their
preferences (Idea 4). Fake graphs, so no display is needed."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.history import Series  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.chart_settings import ChartKind, ChartSettings  # noqa: E402


class FakeGraph:
    """What ChartSettings uses of ui.widgets.graph.Graph."""

    def __init__(self, unit="%", hover=True):
        self.series = [Series("x", unit)]
        self.hover = hover
        self.show_axes = self.show_grid = False
        self.time_span_s = None
        self.entry_base = None
        self.value_format = self.axis_format = self.axis_gutter = self.nice_max = None
        self.draws = 0

    def set_hover(self, on, value_format=None):
        self.hover, self.value_format = on, value_format

    def set_axis_format(self, fmt, gutter=None):
        self.axis_format, self.axis_gutter = fmt, gutter

    def set_entry_base(self, index):
        self.entry_base = index

    def set_show_axes(self, show):
        self.show_axes = show

    def set_show_grid(self, show):
        self.show_grid = show

    def set_time_span(self, seconds):
        self.time_span_s = seconds

    def queue_draw(self):
        self.draws += 1


class ChartSettingsTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings.for_tests({"show-graph-axes": True,
                                            "show-graph-grids": True})
        self.charts = ChartSettings(self.settings)
        self.addCleanup(self.charts.release)

    def test_each_kind_gets_its_preferences(self):
        page, card, meter = FakeGraph(), FakeGraph(), FakeGraph(hover=False)
        self.charts.bind(page, ChartKind.PAGE)
        self.charts.bind(card, ChartKind.CARD)
        self.charts.bind(meter, ChartKind.METER)
        for g in (page, card, meter):
            self.assertTrue(g.show_axes)
            self.assertEqual(g.time_span_s, 60.0)
        self.assertTrue(page.show_grid)
        self.assertFalse(card.show_grid)                  # only page graphs
        self.assertIsNotNone(page.axis_format)            # value axes on page graphs
        self.assertIsNone(card.axis_format)
        self.assertIsNotNone(card.value_format)           # hover in the user's units
        self.assertIsNone(meter.value_format)             # no hover on meters

    def test_live_changes(self):
        page, meter = FakeGraph(), FakeGraph()
        axes = []
        self.charts.bind(page)
        self.charts.bind(meter, ChartKind.METER, show_axes=axes.append)
        self.settings.set("show-graph-axes", False)
        self.settings.set("show-graph-grids", False)
        self.settings.set("graph-time-range", "5-minutes")
        self.assertFalse(page.show_axes)
        self.assertFalse(page.show_grid)
        self.assertEqual(page.time_span_s, 300.0)
        self.assertEqual(axes[-1], False)                 # the meter's own handler
        self.assertFalse(meter.show_axes)
        draws = page.draws
        self.settings.set("base", "binary")               # units: redraw
        self.assertGreater(page.draws, draws)

    def test_units_follow_the_preferences(self):
        rate = FakeGraph("B/s")
        self.charts.bind(rate, rates_in_bits=True)
        self.assertEqual(rate.value_format(0, 2e6), "2.0 MB/s")
        self.assertEqual(rate.axis_format(2e9), "2 GB/s")
        self.settings.set("network-bits", True)
        self.assertEqual(rate.value_format(0, 2e6), "16.0 Mb/s")
        self.settings.set("base", "binary")
        self.assertEqual(rate.axis_format(2 * 2**30), "16 Gib/s")
        self.assertEqual(rate.nice_max(0.6 * 2**30), 5 * 2**30 / 8)   # 4.8 -> "5 Gib/s"
        drive = FakeGraph("B/s")
        self.charts.bind(drive)                           # bits only where they apply
        self.assertEqual(drive.value_format(0, 2 * 2**20), "2.0 MiB/s")
        self.assertEqual(self.charts.format_value(21.5, "°C"), "22 °C")
        self.settings.set("temperature-unit", "kelvin")
        self.assertEqual(self.charts.format_value(21.5, "°C"), "295 K")

    def test_entry_colour_for_page_graphs(self):
        page, card = FakeGraph(), FakeGraph()
        self.charts.set_entry_base(3)
        self.charts.bind(page)
        self.charts.bind(card, ChartKind.CARD)
        self.assertEqual(page.entry_base, 3)
        self.charts.set_entry_base(5)
        self.assertEqual(page.entry_base, 5)
        self.assertIsNone(card.entry_base)

    def test_unbind_and_release(self):
        g = FakeGraph()
        self.charts.bind(g)
        self.charts.unbind(g)
        self.settings.set("show-graph-axes", False)
        self.assertTrue(g.show_axes)                      # no longer followed
        g2 = FakeGraph()
        self.charts.bind(g2)
        self.charts.release()
        self.settings.set("show-graph-grids", False)
        self.assertTrue(g2.show_grid)
        self.assertEqual(self.charts.bound(), [])


if __name__ == "__main__":
    unittest.main()
