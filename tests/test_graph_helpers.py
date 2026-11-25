import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.history import History  # noqa: E402
from proccoli.ui.widgets.graph import (  # noqa: E402
    auto_max, dither_pattern, graph_runs, nice_ceiling, offline_spans, snap_to_device)


class HelpersTest(unittest.TestCase):
    def test_nice_ceiling(self):
        cases = [(0, 1), (-5, 1), (0.7, 1), (1, 1), (1.1, 2), (2.2, 2.5), (3, 5),
                 (7, 10), (42, 50), (100, 100), (101, 200), (1.3e6, 2e6)]
        for v, expected in cases:
            self.assertAlmostEqual(nice_ceiling(v), expected, msg=v)

    def test_snap_to_device(self):
        self.assertEqual(snap_to_device(10.2, 1.0, 1), 10.5)
        self.assertEqual(snap_to_device(10.2, 2.0, 2), 10.0)
        self.assertAlmostEqual((snap_to_device(10.0, 1.25, 1) * 1.25) % 1, 0.5)


class GraphRunsTest(unittest.TestCase):
    def test_newest_point_is_at_the_right_edge(self):
        runs = graph_runs([0.0, 50.0, 100.0], capacity=3, width=200, height=100,
                          y_max=100)
        self.assertEqual(runs, [[(0.0, 100.0), (100.0, 50.0), (200.0, 0.0)]])

    def test_partial_history_scrolls_in_from_the_right(self):
        runs = graph_runs([50.0, 50.0], capacity=5, width=400, height=100, y_max=100)
        self.assertEqual([x for x, _ in runs[0]], [300.0, 400.0])

    def test_none_breaks_the_line(self):
        runs = graph_runs([1.0, None, 2.0, 3.0], 4, 300, 100, 10)
        self.assertEqual([len(r) for r in runs], [1, 2])

    def test_values_are_clamped(self):
        runs = graph_runs([-5.0, 500.0], 2, 100, 100, 100)
        self.assertEqual([y for _, y in runs[0]], [100.0, 0.0])

    def test_degenerate_inputs(self):
        self.assertEqual(graph_runs([], 10, 100, 100, 100), [])
        self.assertEqual(graph_runs([1.0], 1, 100, 100, 100), [])
        self.assertEqual(graph_runs([1.0], 10, 100, 100, 0), [])

    def test_auto_max(self):
        h = History(10)
        h.add(1.0, {"a": 3.2e6, "b": 1e6})
        self.assertEqual(auto_max([h.series("a"), h.series("b")]), 5e6)
        self.assertEqual(auto_max([h.define("empty")], floor=1e6), 1e6)
        self.assertEqual(auto_max([]), 1.0)



class OfflineSpansTest(unittest.TestCase):
    """Where the "wasn't running" bars go (M68): under the same points
    ``graph_runs`` places, half a point wider each side."""

    def test_a_run_in_the_middle(self):
        # 5 points over 4 steps of 25 px: points at 0, 25, 50, 75, 100.
        self.assertEqual(offline_spans([False, True, True, False, False], 5, 100.0),
                         [(12.5, 62.5)])

    def test_clamped_to_the_plot(self):
        self.assertEqual(offline_spans([True, False, True], 3, 100.0),
                         [(0.0, 25.0), (75.0, 100.0)])

    def test_partial_history_sits_at_the_right(self):
        self.assertEqual(offline_spans([True, False], 5, 100.0), [(62.5, 87.5)])

    def test_nothing_to_shade(self):
        self.assertEqual(offline_spans([], 5, 100.0), [])
        self.assertEqual(offline_spans([False, False], 5, 100.0), [])
        self.assertEqual(offline_spans([True], 1, 100.0), [])


class DitherPatternTest(unittest.TestCase):
    def test_a_checker_of_the_color_and_clear(self):
        import cairo
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 2)
        cr = cairo.Context(surface)
        cr.set_source(dither_pattern((0.0, 0.0, 0.0, 1.0), 1.0))
        cr.paint()
        surface.flush()
        data = surface.get_data()
        stride = surface.get_stride()
        alpha = [[data[y * stride + x * 4 + 3] for x in range(4)] for y in range(2)]
        self.assertEqual(alpha, [[255, 0, 255, 0], [0, 255, 0, 255]])

    def test_one_pattern_pixel_per_device_pixel(self):
        import cairo
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 2)
        surface.set_device_scale(2, 2)                          # 2 device px per unit
        cr = cairo.Context(surface)
        cr.set_source(dither_pattern((0.0, 0.0, 0.0, 1.0), 2.0))
        cr.paint()
        surface.flush()
        data = surface.get_data()
        stride = surface.get_stride()
        self.assertEqual([data[x * 4 + 3] for x in range(4)], [255, 0, 255, 0])


if __name__ == "__main__":
    unittest.main()
