"""ui.axes: ticks and labels for percentage graphs (Milestone 29)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.axes import (format_span, history_span_s, is_percent_graph,  # noqa: E402
                             percent_ticks, time_ticks)


class PercentTicksTest(unittest.TestCase):
    def test_every_step_has_a_tick(self):
        self.assertEqual([v for v, _ in percent_ticks(100, 12)], [0, 25, 50, 75, 100])

    def test_labels_fit_the_height(self):
        labels = lambda h: [lab for _, lab in percent_ticks(h, 12) if lab]  # noqa: E731
        self.assertEqual(labels(200), ["0 %", "25 %", "50 %", "75 %", "100 %"])
        self.assertEqual(labels(40), ["0 %", "50 %", "100 %"])
        self.assertEqual(labels(20), ["0 %", "100 %"])           # always both ends


class TimeTicksTest(unittest.TestCase):
    def test_round_steps_back_from_now(self):
        ticks = time_ticks(60, 300, min_label_width=56)        # room for 5 intervals
        self.assertEqual([lab for _, lab in ticks], ["60 s", "45 s", "30 s", "15 s", "now"])
        self.assertEqual(ticks[0][0], 0.0)
        self.assertEqual(ticks[-1], (1.0, "now"))
        ticks = time_ticks(40, 300)
        self.assertEqual([lab for _, lab in ticks], ["40 s", "30 s", "20 s", "10 s", "now"])

    def test_narrow_and_empty(self):
        self.assertEqual([lab for _, lab in time_ticks(60, 40)], ["60 s", "now"])
        self.assertEqual(time_ticks(0, 300), [(1.0, "now")])
        self.assertLessEqual(len(time_ticks(60, 5000)), 7)          # at most 6 intervals

    def test_oldest_tick_may_be_inside_the_plot(self):
        ticks = time_ticks(50, 120)                              # step 30 s
        self.assertEqual([lab for _, lab in ticks], ["30 s", "now"])
        self.assertAlmostEqual(ticks[0][0], 0.4)

    def test_one_unit_per_axis(self):
        self.assertEqual([lab for _, lab in time_ticks(600, 300)],
                         ["10 min", "8 min", "6 min", "4 min", "2 min", "now"])
        self.assertEqual([lab for _, lab in time_ticks(14400, 120)], ["4 h", "2 h", "now"])

    def test_format_span(self):
        self.assertEqual([format_span(s) for s in (0, 45, 60, 90, 600, 5400)],
                         ["0 s", "45 s", "1 min", "1.5 min", "10 min", "1.5 h"])

    def test_span_follows_settings(self):
        s = Settings.for_tests({"graph-time-range": "1-minute", "refresh-speed": "normal"})
        self.assertEqual(history_span_s(s), 60.0)
        s.set("refresh-speed", "very-fast")
        self.assertEqual(history_span_s(s), 60.0)        # M58: the time range holds
        s.set("graph-time-range", "10-minutes")
        self.assertEqual(history_span_s(s), 600.0)


class WhichGraphsTest(unittest.TestCase):
    def test_only_fixed_percentage_graphs(self):
        self.assertTrue(is_percent_graph(["%"], 100.0))
        self.assertTrue(is_percent_graph(["%", "%"], 100.0))
        self.assertFalse(is_percent_graph(["%", "B/s"], 100.0))
        self.assertFalse(is_percent_graph(["°C"], None))
        self.assertFalse(is_percent_graph(["%"], None))
        self.assertFalse(is_percent_graph([], 100.0))


if __name__ == "__main__":
    unittest.main()
