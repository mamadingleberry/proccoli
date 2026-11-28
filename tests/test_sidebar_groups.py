"""Sidebar groups, without a display."""

from __future__ import annotations

import unittest

from proccoli.ui import sidebar_groups as sg
from proccoli.ui.page import PageKind

# Overview, Apps, Processes pinned; a GPU group with two GPUs, a drive
# group with one drive, the processor and memory top-level.
ORDER = ["overview", "apps", "processes", "cpu", "memory",
         "group-gpu", "gpu-a", "gpu-b", "group-drive", "sda"]
GROUP_OF = {"gpu-a": "group-gpu", "gpu-b": "group-gpu", "sda": "group-drive"}
PINNED = ["overview", "apps", "processes"]


class GroupForTest(unittest.TestCase):
    def test_devices_of_four_kinds_group(self):
        for kind in (PageKind.GPU, PageKind.DRIVE, PageKind.NETWORK, PageKind.BATTERY):
            self.assertIsNotNone(sg.group_for(kind), kind)

    def test_processor_memory_and_the_rest_stay_top_level(self):
        for kind in (PageKind.CPU, PageKind.MEMORY, PageKind.OVERVIEW, PageKind.APPS,
                     PageKind.PROCESSES, PageKind.DEMO):
            self.assertIsNone(sg.group_for(kind), kind)

    def test_counts(self):
        spec = sg.group_for(PageKind.DRIVE)
        self.assertEqual(sg.count_text(spec, 1), "1 drive")
        self.assertEqual(sg.count_text(spec, 3), "3 drives")


class NestTest(unittest.TestCase):
    def test_devices_follow_their_group(self):
        scattered = ["group-gpu", "sda", "cpu", "gpu-b", "group-drive", "gpu-a"]
        self.assertEqual(sg.nest(scattered, GROUP_OF),
                         ["group-gpu", "gpu-b", "gpu-a", "cpu", "group-drive", "sda"])

    def test_a_device_without_its_group_keeps_its_place(self):
        self.assertEqual(sg.nest(["cpu", "gpu-a"], GROUP_OF), ["cpu", "gpu-a"])


class MoveTest(unittest.TestCase):
    def test_a_device_moves_within_its_group(self):
        moved = sg.move(ORDER, "gpu-b", -1, PINNED, GROUP_OF)
        self.assertEqual(moved[5:8], ["group-gpu", "gpu-b", "gpu-a"])
        self.assertEqual(sg.move(ORDER, "gpu-a", -1, PINNED, GROUP_OF), ORDER)  # first already

    def test_a_group_moves_with_its_devices(self):
        moved = sg.move(ORDER, "group-drive", -1, PINNED, GROUP_OF)
        self.assertEqual(moved[5:], ["group-drive", "sda", "group-gpu", "gpu-a", "gpu-b"])

    def test_a_top_level_entry_moves_past_a_whole_group(self):
        moved = sg.move(ORDER, "memory", 1, PINNED, GROUP_OF)
        self.assertEqual(moved[4:], ["group-gpu", "gpu-a", "gpu-b", "memory",
                                     "group-drive", "sda"])

    def test_nothing_moves_above_the_pinned(self):
        self.assertEqual(sg.move(ORDER, "cpu", -5, PINNED, GROUP_OF), ORDER)


class MoveBeforeTest(unittest.TestCase):
    def test_a_device_dropped_on_its_sibling(self):
        moved = sg.move_before(ORDER, "gpu-b", "gpu-a", PINNED, GROUP_OF)
        self.assertEqual(moved[6:8], ["gpu-b", "gpu-a"])

    def test_a_device_never_leaves_its_group(self):
        self.assertEqual(sg.move_before(ORDER, "gpu-a", "sda", PINNED, GROUP_OF), ORDER)
        self.assertEqual(sg.move_before(ORDER, "gpu-a", "cpu", PINNED, GROUP_OF), ORDER)

    def test_an_entry_dropped_on_a_device_lands_at_its_group(self):
        # as for a flat list: moving down, it takes the target's place
        # and the target (the drive group) shifts up
        moved = sg.move_before(ORDER, "cpu", "sda", PINNED, GROUP_OF)
        self.assertEqual(moved[3:], ["memory", "group-gpu", "gpu-a", "gpu-b",
                                     "group-drive", "sda", "cpu"])


class HiddenTest(unittest.TestCase):
    def test_collapsed_groups_hide_their_devices(self):
        self.assertEqual(sg.hidden_children(GROUP_OF, ["group-gpu"]), {"gpu-a", "gpu-b"})
        self.assertEqual(sg.hidden_children(GROUP_OF, []), set())


if __name__ == "__main__":
    unittest.main()
