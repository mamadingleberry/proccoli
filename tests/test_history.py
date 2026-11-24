import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.history import History, Series  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
