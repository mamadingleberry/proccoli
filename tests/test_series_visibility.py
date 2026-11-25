"""Left-click hides or shows a line; right-click shows only it."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.ui.series_visibility import never_empty, solo, toggle  # noqa: E402


class SeriesVisibilityTest(unittest.TestCase):
    def test_toggle(self):
        self.assertEqual(toggle([True, True, True], 1), [True, False, True])
        self.assertEqual(toggle([True, False, True], 1), [True, True, True])

    def test_deselecting_the_only_line_shows_every_line(self):
        # a single core selected (right-click), then deselected.
        only = solo([True] * 4, 2)
        self.assertEqual(toggle(only, 2), [True] * 4)
        # Or hidden one by one: the last one brings them all back.
        self.assertEqual(toggle([False, False, False, True], 3), [True] * 4)

    def test_never_empty(self):
        self.assertEqual(never_empty([False, False]), [True, True])
        self.assertEqual(never_empty([False, True]), [False, True])
        self.assertEqual(never_empty([]), [])

    def test_lines_without_data_dont_count(self):
        # A measure the tool doesn't report (NVIDIA's PCIe via nvidia-smi).
        available = [True, True, False]
        self.assertEqual(never_empty([False, False, True], available), [True, True, True])
        self.assertEqual(toggle([True, False, True], 0, available), [True, True, True])
        self.assertEqual(never_empty([False, False], [False, False]), [False, False])

    def test_solo_then_back_to_all(self):
        only = solo([True, True, True], 2)
        self.assertEqual(only, [False, False, True])
        self.assertEqual(solo(only, 2), [True, True, True])     # again: every line

    def test_solo_another_line_moves_the_solo(self):
        self.assertEqual(solo([False, False, True], 0), [True, False, False])

    def test_solo_from_a_partial_selection(self):
        self.assertEqual(solo([True, False, True], 1), [False, True, False])


if __name__ == "__main__":
    unittest.main()
