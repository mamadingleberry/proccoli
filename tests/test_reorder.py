"""ui.reorder: the user's sidebar and toolbar order."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.ui.reorder import arrange, can_move, move, move_before  # noqa: E402

PINNED = ["apps", "processes"]
DEFAULT = ["apps", "processes", "cpu", "memory", "gpu", "sda", "eth"]


class ArrangeTest(unittest.TestCase):
    def test_nothing_saved_is_the_default_order(self):
        self.assertEqual(arrange(DEFAULT, [], PINNED), DEFAULT)

    def test_saved_order_with_pinned_always_first(self):
        saved = ["eth", "gpu", "cpu", "memory", "sda"]
        self.assertEqual(arrange(DEFAULT, saved, PINNED), PINNED + saved)
        # A saved order that (wrongly) contains pinned IDs can't move them.
        self.assertEqual(arrange(DEFAULT, ["cpu", "apps"], PINNED)[:2], PINNED)

    def test_new_entries_go_after_their_default_predecessor(self):
        saved = ["eth", "cpu", "gpu"]                 # memory and sda are new
        self.assertEqual(arrange(DEFAULT, saved, PINNED),
                         PINNED + ["eth", "cpu", "memory", "gpu", "sda"])
        self.assertEqual(arrange(["apps", "new", "cpu"], ["cpu"], ["apps"]),
                         ["apps", "new", "cpu"])          # no predecessor: at the start

    def test_removed_and_duplicate_ids_are_ignored(self):
        self.assertEqual(arrange(DEFAULT, ["usb", "cpu", "cpu", "memory"], PINNED), DEFAULT)

    def test_without_pinned_pages_present(self):
        self.assertEqual(arrange(["cpu", "memory"], ["memory", "cpu"], PINNED),
                         ["memory", "cpu"])
        # cpu isn't saved and has no default predecessor: it goes first.
        self.assertEqual(arrange(["cpu", "memory"], ["memory"], PINNED), ["cpu", "memory"])


class MoveTest(unittest.TestCase):
    def test_up_and_down(self):
        self.assertEqual(move(DEFAULT, "memory", -1, PINNED)[2:4], ["memory", "cpu"])
        self.assertEqual(move(DEFAULT, "memory", 1, PINNED)[3:5], ["gpu", "memory"])

    def test_never_into_or_above_the_pinned_entries(self):
        self.assertEqual(move(DEFAULT, "cpu", -1, PINNED), DEFAULT)
        self.assertEqual(move(DEFAULT, "gpu", -10, PINNED)[:3], PINNED + ["gpu"])
        self.assertFalse(can_move(DEFAULT, "cpu", -1, PINNED))
        self.assertTrue(can_move(DEFAULT, "cpu", 1, PINNED))

    def test_pinned_entries_dont_move(self):
        self.assertEqual(move(DEFAULT, "apps", 3, PINNED), DEFAULT)
        self.assertEqual(move(DEFAULT, "processes", 1, PINNED), DEFAULT)

    def test_past_the_end_and_unknown(self):
        self.assertEqual(move(DEFAULT, "sda", 5, PINNED)[-1], "sda")
        self.assertEqual(move(DEFAULT, "nope", 1, PINNED), DEFAULT)

    def test_drag_and_drop(self):
        self.assertEqual(move_before(DEFAULT, "eth", "cpu", PINNED)[2:4], ["eth", "cpu"])
        self.assertEqual(move_before(DEFAULT, "cpu", "gpu", PINNED)[2:5],
                         ["memory", "gpu", "cpu"])
        self.assertEqual(move_before(DEFAULT, "eth", "apps", PINNED)[:3], PINNED + ["eth"])
        self.assertEqual(move_before(DEFAULT, "eth", "gone", PINNED), DEFAULT)


if __name__ == "__main__":
    unittest.main()
