"""Sidebar groups in the window: a group entry and page per kind, its
devices beneath it, collapsing and moving."""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(__file__))
import helpers  # noqa: E402,F401 (sets sys.path)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.units import Base  # noqa: E402
from proccoli.ui.pages.group import TOTALS, total_text  # noqa: E402
from proccoli.ui.page import PageKind  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()


@dataclass
class Net:
    rx_bps: float
    tx_bps: float


class TotalTextTest(unittest.TestCase):
    def test_network_adds_up_download_and_upload(self):
        text = total_text([Net(1000, 200), Net(500, 300)], TOTALS[PageKind.NETWORK])
        self.assertEqual(text, "↓ 1.5 kB/s · ↑ 500 B/s")

    def test_binary_units(self):
        text = total_text([Net(2048, 0)], TOTALS[PageKind.NETWORK], Base.BINARY)
        self.assertTrue(text.startswith("↓ 2.0 KiB/s"), text)

    def test_nothing_to_add(self):
        self.assertEqual(total_text([], TOTALS[PageKind.NETWORK]), "")

    def test_percentages_are_never_added(self):
        self.assertNotIn(PageKind.GPU, TOTALS)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class WindowGroupsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Adw.init()
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def make(self):
        from helpers import make_context
        from proccoli.ui.window import MainWindow
        self.settings = Settings.for_tests()
        ctx = make_context(self, demo=True, settings=self.settings)
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        return win

    def test_two_gpus_are_one_group_with_its_own_page(self):
        win = self.make()
        sidebar = win.sidebar
        self.assertEqual(sidebar.group_of(), {"gpu-demo": "group-gpu",
                                              "gpu-demo-amd": "group-gpu"})
        group = win.page("group-gpu")
        self.assertTrue(group.is_group)
        self.assertEqual(group.order(), ["gpu-demo", "gpu-demo-amd"])  # a card per GPU
        self.assertEqual(group.description, "2 GPUs")
        self.assertTrue(sidebar.items["gpu-demo"].nested)
        self.assertGreater(sidebar.items["gpu-demo"].get_child().get_margin_start(), 0)
        self.assertFalse(sidebar.items["cpu"].nested)

    def test_the_overview_keeps_a_card_per_device(self):
        win = self.make()
        self.assertNotIn("group-gpu", win.overview.order())
        self.assertIn("gpu-demo", win.overview.order())

    def test_collapsing_hides_the_devices_and_is_remembered(self):
        win = self.make()
        sidebar = win.sidebar
        sidebar.items["group-gpu"].expander.emit("clicked")
        self.assertEqual(list(self.settings.get("sidebar-collapsed-groups")), ["group-gpu"])
        self.assertFalse(sidebar.items["gpu-demo"].get_visible())
        self.assertFalse(sidebar.items["group-gpu"].expanded)
        sidebar.toggle_group("group-gpu")
        self.assertTrue(sidebar.items["gpu-demo-amd"].get_visible())

    def test_a_device_moves_only_within_its_group(self):
        win = self.make()
        sidebar = win.sidebar
        sidebar.move("gpu-demo-amd", -1)
        order = sidebar.order()
        self.assertEqual(order[order.index("group-gpu"):][:3],
                         ["group-gpu", "gpu-demo-amd", "gpu-demo"])
        sidebar.move("gpu-demo-amd", -1)                     # already first
        self.assertEqual(sidebar.order(), order)

    def test_a_group_moves_with_its_devices(self):
        win = self.make()
        win.sidebar.move("group-gpu", -1)                    # above Memory
        order = win.sidebar.order()
        self.assertEqual(order[3:8], ["cpu", "group-gpu", "gpu-demo", "gpu-demo-amd", "memory"])

    def test_go_to_indents_a_groups_devices(self):
        from proccoli.ui.navigation import menu_targets
        win = self.make()
        labels = dict((target, label) for label, target in menu_targets(win.navigation.goto_menu))
        self.assertTrue(labels["gpu-demo"].startswith(" "))
        self.assertFalse(labels["group-gpu"].startswith(" "))

    def test_the_group_goes_with_its_last_device(self):
        win = self.make()
        win._on_device_removed("gpu-demo")
        self.assertIn("group-gpu", win.containers)
        win._on_device_removed("gpu-demo-amd")
        self.assertNotIn("group-gpu", win.containers)


if __name__ == "__main__":
    unittest.main()
