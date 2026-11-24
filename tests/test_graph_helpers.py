import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.history import History  # noqa: E402
from proccoli.ui.widgets.graph import (  # noqa: E402
    auto_max, graph_runs, nice_ceiling, snap_to_device)


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


if __name__ == "__main__":
    unittest.main()
