"""ui.hover and the shared axis gutter / value ticks in ui.axes (Idea 3:
what the Intel Details tab's own graphs had, now shared by every graph)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.ui.axes import AxisGutter, value_divisions, value_ticks  # noqa: E402
from proccoli.ui.hover import ago_text, box_origin, hover_point  # noqa: E402


class HoverPointTest(unittest.TestCase):
    # 11 points across a 100 px plot: one every 10 px, newest at x = 100.

    def test_right_edge_is_the_newest_point(self):
        self.assertEqual(hover_point(100, 100, 11, 11), (10, 0, 100.0))

    def test_snaps_to_the_nearest_point(self):
        self.assertEqual(hover_point(76, 100, 11, 11), (8, 2, 80.0))
        self.assertEqual(hover_point(74, 100, 11, 11), (7, 3, 70.0))

    def test_pointer_outside_the_plot_is_clamped(self):
        self.assertEqual(hover_point(-30, 100, 11, 11), (0, 10, 0.0))
        self.assertEqual(hover_point(500, 100, 11, 11).back, 0)

    def test_no_data_left_of_a_partial_history(self):
        # Only 4 points so far: they fill the right edge.
        self.assertEqual(hover_point(70, 100, 11, 4), (0, 3, 70.0))
        self.assertIsNone(hover_point(50, 100, 11, 4))

    def test_degenerate_inputs(self):
        self.assertIsNone(hover_point(10, 100, 1, 1))
        self.assertIsNone(hover_point(10, 100, 11, 0))
        self.assertIsNone(hover_point(10, 0, 11, 11))


class AgoTextTest(unittest.TestCase):
    def test_now_and_seconds(self):
        self.assertEqual(ago_text(0, 61, 60), "now")
        self.assertEqual(ago_text(12, 61, 60), "12 s ago")    # 1 s per point

    def test_minutes(self):
        self.assertEqual(ago_text(90, 121, 120 * 2), "3 min ago")

    def test_without_a_time_span(self):
        self.assertEqual(ago_text(3, 61, None), "3 samples ago")


class BoxOriginTest(unittest.TestCase):
    def test_right_of_the_crosshair_when_it_fits(self):
        self.assertEqual(box_origin(50, 80, 40, 300, 150, 10), (62, 14))

    def test_left_of_it_near_the_right_edge(self):
        self.assertEqual(box_origin(280, 80, 40, 300, 150, 10), (188, 14))

    def test_short_graphs_keep_the_box_inside(self):
        self.assertEqual(box_origin(50, 80, 60, 300, 50, 10), (62, 0))


class ValueTicksTest(unittest.TestCase):
    def test_divisions_fit_the_height(self):
        self.assertEqual(value_divisions(200, 14), 4)
        self.assertEqual(value_divisions(70, 14), 2)
        self.assertEqual(value_divisions(30, 14), 1)
        self.assertEqual(value_divisions(120, 28), 2)       # large text: fewer labels

    def test_ticks_from_zero_to_the_maximum(self):
        self.assertEqual(value_ticks(1000, 200, 14), [0, 250, 500, 750, 1000])
        self.assertEqual(value_ticks(5, 30, 14), [0, 5])


class _Graph:
    def __init__(self):
        self.draws = 0

    def queue_draw(self):
        self.draws += 1


class AxisGutterTest(unittest.TestCase):
    def setUp(self):
        self.scheduled = []
        self.gutter = AxisGutter(schedule=self.scheduled.append)

    def test_widest_wins(self):
        a, b = _Graph(), _Graph()
        self.assertTrue(self.gutter.report(a, 30))
        self.assertTrue(self.gutter.report(b, 44))
        self.assertFalse(self.gutter.report(a, 36))
        self.assertEqual(self.gutter.width, 44)

    def test_growth_redraws_every_graph_once(self):
        a, b = _Graph(), _Graph()
        self.gutter.report(a, 30)
        self.assertEqual(self.scheduled, [])                # the first sets it
        self.gutter.report(b, 44)
        self.gutter.report(b, 50)
        self.assertEqual(len(self.scheduled), 1)            # one pending redraw
        self.assertFalse(self.scheduled[0]())
        self.assertEqual((a.draws, b.draws), (1, 1))

    def test_forget(self):
        a, b = _Graph(), _Graph()
        self.gutter.report(a, 30)
        self.gutter.report(b, 44)
        self.gutter.forget(b)
        self.assertEqual(self.gutter.width, 30)


if __name__ == "__main__":
    unittest.main()
