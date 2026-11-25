"""ui.toolbar_items: what the graph toolbar can hold."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.toolbar_items import (BY_ID, DEFAULT_ORDER, FIXED, ITEMS, SETTING, applies,  # noqa: E402
                                       set_shown, shown)


class ItemsTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings.for_tests()

    def test_every_item_changes_a_real_setting(self):
        for item in ITEMS:
            with self.subTest(item.id):
                spec = self.settings.spec.keys[item.key]
                self.assertEqual(spec.type, "s" if item.kind == "menu" else "b")

    def test_every_menu_choice_is_a_schema_nick_with_a_label(self):
        for item in (i for i in ITEMS if i.kind == "menu"):
            with self.subTest(item.id):
                nicks = [n for n, _ in item.choices]
                schema = set(self.settings.spec.keys[item.key].choices)
                # The time range's "custom" is *Custom…*, a section of its own.
                self.assertEqual(set(nicks) | ({"custom"} if item.custom_key else set()),
                                 schema)
                self.assertTrue(all(label for _, label in item.choices))

    def test_preferences_offers_the_same_choices(self):
        from proccoli.ui.dialogs import preferences
        self.assertIs(preferences.GRAPH_TIME_RANGES, BY_ID["time-range"].choices)
        self.assertNotIn("update-interval", BY_ID)    # Preferences only: it isn't a view

    def test_every_item_has_a_title(self):
        titles = [item.title for item in ITEMS]
        self.assertTrue(all(titles))
        self.assertEqual(len(set(titles)), len(titles))

    def test_choice_label(self):
        self.assertEqual(BY_ID["time-range"].choice_label("1-hour"), "1 Hour")
        self.assertEqual(BY_ID["time-range"].choice_label("odd"), "odd")
        custom = Settings.for_tests({"graph-time-range": "custom",
                                     "graph-time-range-custom": 5400})
        self.assertEqual(BY_ID["time-range"].choice_label("custom", custom), "90 Minutes")

    def test_default_setting_lists_known_items(self):
        self.assertEqual(shown(self.settings.get(SETTING)), ["time-range", "axes", "grids"])


class ShownTest(unittest.TestCase):
    def test_unknown_and_repeated_ids_are_dropped(self):
        self.assertEqual(shown(["grids", "nope", "grids", "axes"]), ["grids", "axes"])

    def test_hiding(self):
        self.assertEqual(set_shown(["time-range", "axes"], "axes", False), ["time-range"])

    def test_showing_goes_to_the_default_place(self):
        # axes comes after time-range and before grids by default.
        self.assertEqual(set_shown(["time-range", "grids"], "axes", True),
                         ["time-range", "axes", "grids"])
        self.assertEqual(set_shown(["axes"], "time-range", True), ["time-range", "axes"])

    def test_showing_twice_or_unknown_changes_nothing(self):
        self.assertEqual(set_shown(["axes"], "axes", True), ["axes"])
        self.assertEqual(set_shown(["axes"], "nope", True), ["axes"])

    def test_default_order_is_the_items_table(self):
        self.assertEqual(DEFAULT_ORDER, [i.id for i in ITEMS if not i.fixed])
        self.assertEqual(FIXED, ["logical-cpus"])

    def test_fixed_items_are_never_stored_or_shown_by_the_user(self):
        self.assertEqual(shown(["logical-cpus", "axes"]), ["axes"])
        self.assertEqual(set_shown(["axes"], "logical-cpus", True), ["axes"])


class AppliesTest(unittest.TestCase):
    def test_graph_items_only_on_pages_with_graphs(self):
        self.assertTrue(applies(BY_ID["grids"], "drive", True))
        self.assertFalse(applies(BY_ID["grids"], "processes", False))

    def test_nothing_applies_without_graphs(self):
        self.assertFalse(any(applies(item, "processes", False) for item in ITEMS))

    def test_logical_cpus_only_on_the_processor_page(self):
        self.assertTrue(applies(BY_ID["logical-cpus"], "cpu", True))
        self.assertFalse(applies(BY_ID["logical-cpus"], "memory", True))


class ToolbarShownTest(unittest.TestCase):
    """Pages show their own copy of a toolbar control only without it."""

    def test_shown_unless_turned_off_or_lightweight(self):
        from proccoli.core.profile import Profile, profile_settings
        from proccoli.ui.toolbar_items import toolbar_shown
        settings = Settings.for_tests()
        self.assertTrue(toolbar_shown(settings))
        settings.set("show-toolbar", False)
        self.assertFalse(toolbar_shown(settings))
        self.assertFalse(toolbar_shown(profile_settings(Settings.for_tests(),
                                                        Profile.lightweight())))


if __name__ == "__main__":
    unittest.main()
