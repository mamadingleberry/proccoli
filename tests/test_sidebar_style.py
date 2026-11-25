"""The sidebar's Full / Icons Only / Hidden modes (``ui/sidebar_style.py``): pure rules, no display."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.sidebar_style import (MIN_RAIL_WIDTH, MODE_LABELS, STYLE_SETTING,  # noqa: E402
                                       Mode, SidebarStyle, choose, compact_tooltip,
                                       menu_modes, mode_of, parse_style, rail_width)


class ModeTest(unittest.TestCase):
    def test_mode_of(self):
        for shown, style, mode in ((True, "full", Mode.FULL), (True, "icons", Mode.ICONS),
                                   (False, "full", Mode.HIDDEN), (False, "icons", Mode.HIDDEN),
                                   (True, SidebarStyle.ICONS, Mode.ICONS)):
            with self.subTest(shown=shown, style=style):
                self.assertEqual(mode_of(shown, style), mode)

    def test_choose(self):
        self.assertEqual(choose("full", "icons"), (True, SidebarStyle.FULL))
        self.assertEqual(choose(Mode.ICONS, "full"), (True, SidebarStyle.ICONS))
        # Hidden keeps whatever style was in use.
        self.assertEqual(choose("hidden", "icons"), (False, SidebarStyle.ICONS))
        self.assertEqual(choose("hidden", "full"), (False, SidebarStyle.FULL))

    def test_lightweight_offers_no_full(self):
        """the style is pinned to icons only."""
        self.assertEqual(menu_modes(), (Mode.FULL, Mode.ICONS, Mode.HIDDEN))
        self.assertEqual(menu_modes(False), (Mode.ICONS, Mode.HIDDEN))
        self.assertEqual(choose("full", "icons", full_allowed=False), (True, SidebarStyle.ICONS))
        self.assertEqual(choose("hidden", "icons", full_allowed=False),
                         (False, SidebarStyle.ICONS))

    def test_round_trip(self):
        for mode in Mode:
            for style in SidebarStyle:
                self.assertEqual(mode_of(*choose(mode, style)), mode)

    def test_unknown_style_is_full(self):
        self.assertEqual(parse_style("tiny"), SidebarStyle.FULL)
        with self.assertRaises(ValueError):
            choose("tiny", "full")

    def test_three_labelled_modes_in_order(self):
        self.assertEqual([MODE_LABELS[m] for m in Mode], ["Full", "Icons Only", "Hidden"])

    def test_styles_match_the_schema(self):
        settings = Settings.for_tests()
        self.assertEqual(settings.get(STYLE_SETTING), "full")
        for style in SidebarStyle:
            settings.set(STYLE_SETTING, style.value)          # rejected if not in the enum
            self.assertEqual(settings.get(STYLE_SETTING), style.value)


class RailTest(unittest.TestCase):
    def test_rail_fits_its_header(self):
        self.assertEqual(rail_width(0), MIN_RAIL_WIDTH)
        self.assertEqual(rail_width(90), 90)


class TooltipTest(unittest.TestCase):
    def test_name_description_and_usage(self):
        self.assertEqual(compact_tooltip("Processor", "Intel Core i7", "12 %"),
                         "Processor\nIntel Core i7\n12 %")

    def test_missing_parts_are_left_out(self):
        self.assertEqual(compact_tooltip("Apps"), "Apps")
        self.assertEqual(compact_tooltip("Memory", "", "4.0 / 16.0 GB"), "Memory\n4.0 / 16.0 GB")
        self.assertEqual(compact_tooltip("Drive", "NVMe", None), "Drive\nNVMe")


if __name__ == "__main__":
    unittest.main()
