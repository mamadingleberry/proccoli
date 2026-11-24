import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from proccoli.ui.layout import split_columns  # noqa: E402
from proccoli.gpu.intel_gpu_top.views import GROUPS  # noqa: E402
from proccoli.gpu.intel_gpu_top.views import group_meta as _group_meta  # noqa: E402


class GroupMetaTest(unittest.TestCase):
    def test_known_group(self):
        self.assertEqual(_group_meta("rc6", "%"), GROUPS["rc6"])

    def test_per_gt_group(self):
        title, sub, h, fixed = _group_meta("frequency-gt1", "MHz")
        self.assertEqual(title, "Frequency (GT1)")
        self.assertEqual((sub, h, fixed), GROUPS["frequency"][1:])

    def test_unknown_percent_group_is_fixed_to_100(self):
        self.assertEqual(_group_meta("media_busy", "%"), ("Media Busy", "", 130, 100.0))

    def test_unknown_other_group_autoscales(self):
        self.assertEqual(_group_meta("fan-speed", "rpm"), ("Fan Speed", "", 130, None))

    def test_unknown_gt_group(self):
        title, _, _, fixed = _group_meta("thing-gt0", "W")
        self.assertEqual(title, "Thing Gt0")
        self.assertIsNone(fixed)


class IntervalMenuTest(unittest.TestCase):
    def test_nothing_faster_than_a_second(self):
        # Idea 6: the Update Interval menu has the app's choices.
        from proccoli.core.ticker import UPDATE_INTERVALS_MS
        from proccoli.gpu.intel_gpu_top.views import INTERVALS
        nicks = [n for n, _ in INTERVALS]
        self.assertEqual(sorted(n for n in nicks if n), sorted(UPDATE_INTERVALS_MS))
        self.assertIn("", nicks)                                  # follow the app


class SplitColumnsTest(unittest.TestCase):
    def test_single_column(self):
        self.assertEqual(split_columns([200, 140, 140], 1), [[0, 1, 2]])

    def test_default_groups_balance(self):
        heights = [g[2] for g in GROUPS.values()]  # 200 140 140 110 140 110
        cols = split_columns(heights, 2)
        self.assertEqual(cols, [[0, 1, 2], [3, 4, 5]])
        # Order is preserved and nothing is lost.
        self.assertEqual(sum(cols, []), list(range(len(heights))))

    def test_never_leaves_a_column_empty(self):
        self.assertEqual(split_columns([500, 10], 2), [[0], [1]])
        self.assertEqual(split_columns([10, 500], 2), [[0], [1]])

    def test_fewer_items_than_columns(self):
        self.assertEqual(split_columns([100], 2), [[0]])
        self.assertEqual(split_columns([], 2), [[]])


if __name__ == "__main__":
    unittest.main()
