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
        self.assertEqual(g, {"frequency": ("Hz", {"requested": 300e6})})   # base units

    def test_readings_are_kept_in_base_units(self):
        # Idea 4: so charts format them in the user's units.
        g = flatten_sample({"imc-bandwidth": {"reads": 2, "unit": "MiB/s"},
                            "power": {"GPU": 1.5, "unit": "W"}})
        self.assertEqual(g, {"imc-bandwidth": ("B/s", {"reads": 2 * 2**20}),
                             "power": ("W", {"GPU": 1.5})})

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
        self.assertEqual(list(h.series[("x", "a")].values), [1e6, 1.0])

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


class HistoryFollowUpsTest(unittest.TestCase):
    """Averaged points, and filling from the history database."""

    def test_points_average_samples(self):
        h = History(10)
        h.set_plan(10, 2, 0.5)
        h.add({"rc6": {"value": 10, "unit": "%"}}, 1.0)
        self.assertEqual(len(h.times), 0)
        h.add({"rc6": {"value": 30, "unit": "%"}}, 2.0)
        self.assertEqual(list(h.series[("rc6", "value")].values), [20.0])
        self.assertEqual(list(h.times), [2.0])

    def test_readings_and_backfill(self):
        h = History(5)
        h.add({"rc6": {"value": 10, "unit": "%"}, "imc-bandwidth": {"reads": 1, "unit": "MiB/s"}},
              10.0)
        values, units = h.readings()
        self.assertEqual(values, {"rc6/value": 10.0, "imc-bandwidth/reads": 2**20})
        self.assertEqual(units["imc-bandwidth/reads"], "B/s")
        self.assertEqual(sorted(h.keys()), [("imc-bandwidth/reads", "B/s"), ("rc6/value", "%")])
        self.assertTrue(History.WALL_TIMES)
        self.assertEqual(h.room(), 4)
        added = h.backfill([7.0, 8.0, 9.0, 11.0], {"rc6/value": [1.0, None, 3.0, 4.0]})
        self.assertEqual(added, 3)
        self.assertEqual(list(h.times), [7.0, 8.0, 9.0, 10.0])
        self.assertEqual(list(h.series[("rc6", "value")].values), [1.0, None, 3.0, 10.0])
        self.assertEqual(list(h.series[("imc-bandwidth", "reads")].values)[:3],
                         [None, None, None])
        self.assertEqual(History(3).readings(), ({}, {}))


class SnapshotDetailTest(unittest.TestCase):
    def test_details_readings_are_recorded_with_a_prefix(self):
        from proccoli.gpu.backend import GpuSummary
        from proccoli.gpu.controller import GpuSnapshot
        snap = GpuSnapshot(0.0, summary=GpuSummary(usage=5.0),
                           detail={"rc6/value": 30.0}, detail_units={"rc6/value": "%"})
        self.assertEqual(snap.stats_values()["detail/rc6/value"], 30.0)
        self.assertEqual(snap.stats_units()["detail/rc6/value"], "%")
        self.assertNotIn("detail/rc6/value", snap.history_values())     # not graphed twice


if __name__ == "__main__":
    unittest.main()
