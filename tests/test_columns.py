"""A table's columns, without a display."""

from __future__ import annotations

import unittest

from proccoli.core.settings import Settings
from proccoli.ui.columns import Column, ColumnSet, compare

COLUMNS = [Column("name", "Name", lambda d: d, str, numeric=False),
           Column("memory", "Memory", lambda d: d, str, setting="processes-show-memory"),
           Column("cpu", "Processor", lambda d: d, str),
           Column("gpu", "GPU", lambda d: d, str, setting="processes-show-gpu")]


class ColumnSetTest(unittest.TestCase):
    def setUp(self):
        self.set = ColumnSet(COLUMNS, "processes")

    def test_the_settings_that_show_columns(self):
        self.assertEqual(self.set.setting_keys(), ["processes-show-memory", "processes-show-gpu"])

    def test_visibility_follows_the_settings(self):
        settings = Settings.for_tests({"processes-show-memory": True, "processes-show-gpu": False})
        self.assertEqual(self.set.visibility(settings), {"memory": True, "gpu": False})

    def test_the_saved_sort(self):
        settings = Settings.for_tests({"processes-sort-by": 3,
                                       "processes-sort-by-ascending": True})
        self.assertEqual(self.set.sort_choice(settings), ("gpu", True))

    def test_an_unusable_saved_sort_means_the_processor(self):
        for index in (0, 99):
            settings = Settings.for_tests({"processes-sort-by": index})
            with self.subTest(index=index):
                self.assertEqual(self.set.sort_choice(settings)[0], "cpu")

    def test_what_a_sort_saves(self):
        self.assertEqual(self.set.sort_settings("memory", False),
                         {"processes-sort-by": 1, "processes-sort-by-ascending": False})

    def test_saved_and_restored_agree(self):
        settings = Settings.for_tests()
        for key, value in self.set.sort_settings("gpu", True).items():
            settings.set(key, value)
        self.assertEqual(self.set.sort_choice(settings), ("gpu", True))


class CompareTest(unittest.TestCase):
    def test_missing_values_sort_first(self):
        self.assertEqual([compare(None, 1), compare(1, None), compare(None, None)], [-1, 1, 0])
        self.assertEqual([compare(1, 2), compare(2, 1), compare(2, 2)], [-1, 1, 0])


if __name__ == "__main__":
    unittest.main()
