"""Where each preference goes: every setting placed once (or set somewhere
else on purpose), short pages, actions after settings. No display needed."""

import collections
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui import preferences_layout as layout  # noqa: E402


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.schema = set(Settings.for_tests().spec.keys)

    def test_every_setting_is_placed_once_or_set_elsewhere(self):
        placed = layout.placed_keys()
        repeats = [k for k, n in collections.Counter(placed).items() if n > 1]
        self.assertEqual(repeats, [])
        self.assertEqual(set(placed) & set(layout.ELSEWHERE), set())
        self.assertEqual(self.schema - set(placed) - set(layout.ELSEWHERE), set(),
                         "a new setting needs a place in Preferences, or in ELSEWHERE")
        self.assertEqual((set(placed) | set(layout.ELSEWHERE)) - self.schema, set(),
                         "a placed key that isn't a setting")

    def test_items_are_settings_or_special(self):
        for item in layout.items():
            self.assertTrue(item in self.schema or item in layout.SPECIAL, item)
        self.assertEqual(len(layout.items()), len(set(layout.items())))
        self.assertEqual(set(layout.SPECIAL) - set(layout.items()), set())   # all used

    def test_six_named_pages(self):
        self.assertEqual([p.title for p in layout.PAGES],
                         ["Appearance", "Sidebar", "Tables", "Recording", "Devices", "System"])
        ids = [g.id for p in layout.PAGES for g in p.groups]
        self.assertEqual(len(ids), len(set(ids)))

    def test_pages_stay_short(self):
        for page in layout.PAGES:
            rows = sum(len(g.items) for g in page.groups)
            self.assertLessEqual(rows, layout.MAX_ROWS, page.id)

    def test_graph_options_are_with_the_appearance(self):
        for key in ("show-graph-axes", "show-graph-grids", "graph-time-range",
                    "graph-time-range-custom", "base", "temperature-unit"):
            self.assertEqual(layout.page_of(key), "appearance", key)
        self.assertEqual(layout.page_of("apps-show-cpu"), "tables")
        self.assertEqual(layout.page_of("lightweight"), "system")
        with self.assertRaises(KeyError):
            layout.page_of("window-width")

    def test_actions_and_status_come_after_the_settings(self):
        recording = next(p for p in layout.PAGES if p.id == "recording")
        self.assertEqual(recording.groups[-1].items, ("recording", "history-size", "export"))
        for group in recording.groups[:-1]:
            self.assertFalse({"recording", "history-size", "export"} & set(group.items))


if __name__ == "__main__":
    unittest.main()
