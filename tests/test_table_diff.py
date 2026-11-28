"""One splice per table refresh."""

from __future__ import annotations

import random
import unittest

from proccoli.ui.table_diff import Splice, apply_splice, plan_splice


class PlanSpliceTest(unittest.TestCase):

    def test_nothing_changed(self):
        self.assertTrue(plan_splice([1, 2, 3], set(), []).empty)

    def test_only_new_rows_are_appended(self):
        self.assertEqual(plan_splice([1, 2], set(), [3, 4]), Splice(2, 0, [3, 4]))

    def test_removals_start_at_the_first_gone_row(self):
        self.assertEqual(plan_splice([1, 2, 3, 4, 5], {2, 4}, [6]), Splice(1, 4, [3, 5, 6]))

    def test_rows_before_the_first_change_are_untouched(self):
        splice = plan_splice(list(range(100)), {98}, [])
        self.assertEqual((splice.position, splice.removed, splice.added), (98, 2, [99]))

    def test_the_result_is_the_kept_rows_then_the_new_ones(self):
        rng = random.Random(7)
        for _ in range(200):
            order = rng.sample(range(1000), rng.randint(0, 60))
            gone = set(rng.sample(order, rng.randint(0, len(order))))
            new = [k for k in rng.sample(range(1000, 2000), rng.randint(0, 20))]
            result = apply_splice(order, plan_splice(order, gone, new))
            self.assertEqual(result, [k for k in order if k not in gone] + new)


if __name__ == "__main__":
    unittest.main()
