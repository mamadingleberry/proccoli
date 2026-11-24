import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.gpu.intel_gpu_top.history import History, flatten_sample, to_float  # noqa: E402


class ToFloatTest(unittest.TestCase):
    def test_numbers_and_numeric_strings(self):
        self.assertEqual(to_float(3), 3.0)
        self.assertEqual(to_float("9.87"), 9.87)

    def test_non_numeric(self):
        for v in (None, "abc", {}, [], "") :
            self.assertIsNone(to_float(v), v)


class FlattenSampleTest(unittest.TestCase):
    def test_skips_non_numeric_members_and_empty_groups(self):
        g = flatten_sample({
            "frequency": {"requested": 300, "actual": "n/a", "unit": "MHz"},
            "empty": {"unit": "W"},
            "scalar": 5,
            "list": [1, 2],
        })
        self.assertEqual(g, {"frequency": ("MHz", {"requested": 300.0})})

    def test_engines_without_busy_are_ignored(self):
        g = flatten_sample({"engines": {"A": {"sema": 1}, "B": "x"}})
        self.assertNotIn("engines", g)

    def test_missing_unit_is_empty_string(self):
        self.assertEqual(flatten_sample({"foo": {"x": 1}}), {"foo": ("", {"x": 1.0})})

    def test_unknown_groups_are_kept(self):
        g = flatten_sample({"power-gt0": {"GPU": 1.5, "unit": "W"}})
        self.assertEqual(g["power-gt0"], ("W", {"GPU": 1.5}))


def sample(**groups):
    return {k: dict(v) for k, v in groups.items()}


class HistoryTest(unittest.TestCase):
    def test_group_order_is_first_seen(self):
        h = History(max_points=10)
        h.add(sample(rc6={"value": 1, "unit": "%"}), 1)
        h.add(sample(power={"GPU": 1, "unit": "W"}, rc6={"value": 2, "unit": "%"}), 2)
        self.assertEqual(h.group_order, ["rc6", "power"])

    def test_new_series_is_back_filled(self):
        h = History(max_points=10)
        h.add(sample(rc6={"value": 1}), 1)
        h.add(sample(rc6={"value": 2}), 2)
        h.add(sample(rc6={"value": 3}, power={"GPU": 4}), 3)
        self.assertEqual(list(h.series[("power", "GPU")].values), [None, None, 4.0])

    def test_back_fill_capped_by_max_points(self):
        h = History(max_points=3)
        for t in range(5):
            h.add(sample(rc6={"value": t}), t)
        h.add(sample(power={"GPU": 1}), 5)
        self.assertEqual(list(h.series[("power", "GPU")].values), [None, None, 1.0])

    def test_unit_follows_latest_sample(self):
        h = History()
        h.add(sample(x={"a": 1, "unit": "MHz"}), 1)
        h.add(sample(x={"a": 1, "unit": "GHz"}), 2)
        self.assertEqual(h.series[("x", "a")].unit, "GHz")

    def test_default_timestamp_and_latest_sample(self):
        h = History()
        s = sample(rc6={"value": 1})
        h.add(s)
        self.assertGreater(h.times[0], 1e9)
        self.assertIs(h.latest_sample, s)

    def test_add_gap_on_empty_history_does_nothing(self):
        h = History()
        h.add_gap(1.0)
        self.assertEqual(len(h.times), 0)

    def test_set_max_points_shrinks_keeping_newest(self):
        h = History(max_points=5)
        for t in range(5):
            h.add(sample(rc6={"value": t}), t)
        h.set_max_points(2)
        self.assertEqual(list(h.times), [3, 4])
        self.assertEqual(list(h.series[("rc6", "value")].values), [3.0, 4.0])
        h.add(sample(rc6={"value": 9}), 9)
        self.assertEqual(list(h.times), [4, 9])

    def test_set_max_points_grows(self):
        h = History(max_points=2)
        for t in range(4):
            h.add(sample(rc6={"value": t}), t)
        h.set_max_points(4)
        h.add(sample(rc6={"value": 4}), 4)
        self.assertEqual(list(h.times), [2, 3, 4])

    def test_clear_keeps_series_but_empties_them(self):
        h = History()
        h.add(sample(rc6={"value": 1}), 1)
        h.clear()
        self.assertEqual(len(h.times), 0)
        self.assertIsNone(h.latest_sample)
        self.assertEqual(len(h.series[("rc6", "value")].values), 0)
        h.add(sample(rc6={"value": 2}), 2)
        self.assertEqual(list(h.series[("rc6", "value")].values), [2.0])

    def test_group_series(self):
        h = History()
        h.add(sample(power={"GPU": 1, "Package": 2}, rc6={"value": 3}), 1)
        self.assertEqual({s.name for s in h.group_series("power")}, {"GPU", "Package"})
        self.assertEqual(h.group_series("nope"), [])

    def test_csv_contents(self):
        h = History()
        h.add(sample(power={"GPU": 1.23456, "unit": "W"}), 10.0)
        h.add(sample(rc6={"value": 50, "unit": "%"}), 11.5)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.csv")
            h.write_csv(path)
            with open(path) as fh:
                lines = fh.read().splitlines()
        self.assertEqual(lines, [
            "timestamp,power/GPU (W),rc6/value (%)",
            "10.000,1.235,",
            "11.500,,50.000",
        ])

    def test_csv_empty_history(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.csv")
            History().write_csv(path)
            with open(path) as fh:
                self.assertEqual(fh.read().splitlines(), ["timestamp"])


if __name__ == "__main__":
    unittest.main()
