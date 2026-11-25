import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.history import History, Series, offline_runs, regroup  # noqa: E402


def aligned(h: History) -> bool:
    return all(len(s.values) == len(h.times) for s in h)


class HistoryTest(unittest.TestCase):
    def test_add_creates_series_with_units(self):
        h = History(10)
        h.add(1.0, {"read": 5.0, "write": 2.0}, {"read": "B/s"})
        self.assertEqual(h.names(), ["read", "write"])
        self.assertEqual(h.series("read").unit, "B/s")
        self.assertEqual(h.series("write").unit, "")
        self.assertEqual(h.series("read").latest(), 5.0)

    def test_new_series_is_back_filled(self):
        h = History(10)
        h.add(1.0, {"a": 1.0})
        h.add(2.0, {"a": 2.0, "b": 9.0})
        self.assertEqual(list(h.series("b").values), [None, 9.0])
        self.assertTrue(aligned(h))

    def test_missing_values_become_none(self):
        h = History(10)
        h.add(1.0, {"a": 1.0, "b": 1.0})
        h.add(2.0, {"a": 2.0})
        self.assertEqual(list(h.series("b").values), [1.0, None])
        self.assertIsNone(h.series("b").latest())

    def test_define_before_data(self):
        h = History(10)
        s = h.define("usage", "%")
        self.assertIsInstance(s, Series)
        self.assertIs(h.define("usage"), s)          # idempotent
        h.add(1.0, {"usage": 50.0})
        self.assertEqual(list(s.values), [50.0])

    def test_define_late_is_aligned(self):
        h = History(10)
        h.add(1.0, {"a": 1.0})
        h.define("b")
        self.assertTrue(aligned(h))

    def test_capacity_drops_oldest(self):
        h = History(3)
        for t in range(5):
            h.add(float(t), {"a": float(t)})
        self.assertEqual(list(h.times), [2.0, 3.0, 4.0])
        self.assertEqual(list(h.series("a").values), [2.0, 3.0, 4.0])
        self.assertEqual(h.series("a").capacity, 3)

    def test_set_max_points_keeps_newest(self):
        h = History(5)
        for t in range(5):
            h.add(float(t), {"a": float(t)})
        h.set_max_points(2)
        self.assertEqual(list(h.series("a").values), [3.0, 4.0])
        h.set_max_points(10)
        self.assertEqual(h.series("a").capacity, 10)
        self.assertEqual(len(h), 2)

    def test_too_small_is_rejected(self):
        with self.assertRaises(ValueError):
            History(1)
        with self.assertRaises(ValueError):
            History(5).set_max_points(1)

    def test_gap(self):
        h = History(10)
        h.add_gap(0.0)                      # nothing to break yet: ignored
        self.assertEqual(len(h), 0)
        h.add(1.0, {"a": 1.0})
        h.add_gap(2.0)
        self.assertEqual(list(h.series("a").values), [1.0, None])

    def test_peak(self):
        h = History(10)
        self.assertIsNone(h.define("a").peak())
        h.add(1.0, {"a": 3.0})
        h.add(2.0, {})
        h.add(3.0, {"a": 7.0})
        self.assertEqual(h.series("a").peak(), 7.0)

    def test_clear(self):
        h = History(10)
        h.add(1.0, {"a": 1.0})
        h.clear()
        self.assertEqual(len(h), 0)
        self.assertEqual(h.names(), ["a"])  # series survive, data doesn't
        self.assertTrue(aligned(h))

    def test_csv(self):
        h = History(10)
        h.add(1.0, {"read": 1.5}, {"read": "B/s"})
        h.add(2.0, {"write": 2.25})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "h.csv")
            h.write_csv(path)
            with open(path, newline="") as fh:
                rows = list(csv.reader(fh))
        self.assertEqual(rows[0], ["timestamp", "read (B/s)", "write"])
        self.assertEqual(rows[1], ["1.000", "1.500", ""])
        self.assertEqual(rows[2], ["2.000", "", "2.250"])


class RegroupTest(unittest.TestCase):
    """Points into a new step's slots."""

    def test_averages_into_longer_slots(self):
        times = [float(t) for t in range(8)]
        out_t, (col,), off = regroup(times, [[float(t) for t in range(8)]], [False] * 8, 4.0, 10)
        self.assertEqual(out_t, [-1.0, 3.0, 7.0])           # back from the newest
        self.assertEqual(col, [0.5, 3.5, 6.5])              # {0,1} {2..5} {6,7}
        self.assertEqual(off, [False] * 3)

    def test_missing_values_and_empty_slots_are_gaps(self):
        out_t, (col,), off = regroup([0.0, 10.0], [[None, 2.0]], [False, False], 5.0, 10)
        self.assertEqual(out_t, [0.0, 5.0, 10.0])
        self.assertEqual(col, [None, None, 2.0])
        self.assertEqual(off, [False, False, False])

    def test_offline_only_when_every_point_was(self):
        _t, _c, off = regroup([0.0, 1.0, 2.0, 3.0], [[None] * 4], [True, True, True, False],
                              2.0, 10)
        self.assertEqual(off, [True, True, False])           # {0} {1,2} {3}

    def test_keeps_the_newest_that_fit(self):
        out_t, _c, _o = regroup([float(t) for t in range(10)], [[1.0] * 10], [False] * 10,
                                1.0, 4)
        self.assertEqual(out_t, [6.0, 7.0, 8.0, 9.0])

    def test_nothing_in_nothing_out(self):
        self.assertEqual(regroup([], [[]], [], 1.0, 5), ([], [[]], []))


class OfflineRunsTest(unittest.TestCase):
    def test_runs(self):
        self.assertEqual(offline_runs([]), [])
        self.assertEqual(offline_runs([False, True, True, False, True]), [(1, 2), (4, 4)])
        self.assertEqual(offline_runs([True, True]), [(0, 1)])


class SetPlanTest(unittest.TestCase):
    """A new time range or update interval: points held are never
    drawn at a spacing they weren't taken at."""

    def filled(self, n=60, step=1.0):
        h = History(n)
        h.set_plan(n, 1, step)
        for i in range(n):
            h.add(i * step, {"usage": float(i)})
        return h

    def test_a_longer_step_averages_what_is_held(self):
        h = self.filled()
        h.set_plan(901, 4, 4.0)
        times = list(h.times)
        self.assertEqual(len(times), 16)                     # 60 s at 4 s: 15 slots + the edge
        self.assertTrue(all(b - a == 4.0 for a, b in zip(times, times[1:])))
        self.assertEqual(times[-1], 59.0)
        self.assertEqual(h.series("usage").values[-1], 58.5)  # 58 and 59: within half a step

    def test_a_shorter_step_drops_what_is_held(self):
        h = self.filled(step=4.0)
        h.set_plan(61, 1, 1.0)
        self.assertEqual(len(h), 0)
        self.assertEqual(len(h.series("usage").values), 0)

    def test_the_same_step_keeps_everything(self):
        h = self.filled()
        h.set_plan(121, 1, 1.0)
        self.assertEqual(len(h), 60)

    def test_offline_flags_stay_aligned(self):
        h = History(10)
        h.set_plan(10, 1, 1.0)
        h.add(5.0, {"usage": 1.0})
        h.backfill([2.0, 3.0, 4.0], {"usage": [None, None, 3.0]}, [True, True, False])
        self.assertEqual(list(h.offline), [True, True, False, False])
        s = h.series("usage")
        self.assertIs(s.offline, h.offline)                  # shared with every series
        h.set_max_points(3)
        self.assertIs(s.offline, h.offline)
        self.assertEqual(list(h.offline), [True, False, False])
        h.add_gap(6.0)
        self.assertEqual(list(h.offline), [False, False, False])  # live points never are
        h.clear()
        self.assertEqual(len(h.offline), 0)

    def test_a_series_defined_later_shares_them(self):
        h = History(10)
        h.add(1.0, {"a": 1.0})
        self.assertIs(h.define("b").offline, h.offline)


if __name__ == "__main__":
    unittest.main()
