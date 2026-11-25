"""ui.time_range: a custom graph time range as a number and a unit; the axis labels for long ranges and Lightweight Mode's cap."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.profile import Profile, profile_settings  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.ticker import time_range_s  # noqa: E402
from proccoli.ui.axes import format_span, span_unit, time_ticks  # noqa: E402
from proccoli.ui.time_range import describe, limit_note, split, to_seconds  # noqa: E402


class NumberAndUnitTest(unittest.TestCase):
    def test_split_uses_the_largest_unit_that_divides(self):
        self.assertEqual(split(5400), (90, 1))          # 90 minutes
        self.assertEqual(split(7200), (2, 2))           # 2 hours
        self.assertEqual(split(2 * 86400), (2, 3))      # 2 days
        self.assertEqual(split(45), (45, 0))

    def test_typed_values_come_back_as_typed(self):
        for number, unit in ((90, 1), (3, 2), (10, 0), (30, 3)):
            self.assertEqual(split(to_seconds(number, unit)), (number, unit))

    def test_describe(self):
        self.assertEqual(describe(7200), "2 Hours")
        self.assertEqual(describe(86400), "1 Day")
        self.assertEqual(describe(60), "1 Minute")
        self.assertEqual(describe(5400), "90 Minutes")

    def test_limit_note(self):
        self.assertEqual(limit_note(7200), "")
        self.assertEqual(limit_note(40 * 86400), "At most 30 Days")
        self.assertEqual(limit_note(5), "At least 10 Seconds")
        self.assertEqual(limit_note(10, 10_000),
                         "At least two update intervals (20 Seconds)")


class LongAxesTest(unittest.TestCase):
    def test_days_above_two_days(self):
        self.assertEqual(span_unit(2 * 86400), "h")
        self.assertEqual(span_unit(3 * 86400), "d")
        self.assertEqual(format_span(3 * 86400), "3 d")

    def test_round_labels_for_long_ranges(self):
        labels = [label for _, label in time_ticks(3 * 3600, 600)]
        self.assertEqual(labels[0], "3 h")
        labels = [label for _, label in time_ticks(2 * 86400, 600)]
        self.assertEqual(labels, ["48 h", "36 h", "24 h", "12 h", "now"])
        labels = [label for _, label in time_ticks(30 * 86400, 600)]
        self.assertEqual(labels, ["28 d", "21 d", "14 d", "7 d", "now"])


class LightweightCapTest(unittest.TestCase):
    def test_a_custom_range_reads_as_a_minute_and_comes_back(self):
        base = Settings.for_tests({"graph-time-range": "custom",
                                   "graph-time-range-custom": 7200})
        self.assertEqual(time_range_s(profile_settings(base, Profile.lightweight())), 60)
        self.assertEqual(time_range_s(base), 7200)                  # the user's choice kept
        base.set("graph-time-range-custom", 30)                     # short enough already
        self.assertEqual(time_range_s(profile_settings(base, Profile.lightweight())), 30)


if __name__ == "__main__":
    unittest.main()
