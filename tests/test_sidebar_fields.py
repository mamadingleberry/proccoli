"""ui.sidebar_fields: per-entry parts."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.ui.sidebar_fields import Field, hidden, set_shown, visible  # noqa: E402


class FieldsTest(unittest.TestCase):
    def test_hidden_ignores_unknown_names(self):
        self.assertEqual(hidden({"sda": ["chart", "bogus"]}, "sda"), {Field.CHART})
        self.assertEqual(hidden({}, "sda"), set())

    def test_set_shown_keeps_the_setting_small(self):
        m = set_shown({}, "sda", Field.CHART, False)
        m = set_shown(m, "sda", Field.NAME, False)
        self.assertEqual(m, {"sda": ["chart", "name"]})
        m = set_shown(m, "sda", Field.CHART, True)
        m = set_shown(m, "sda", Field.NAME, True)
        self.assertEqual(m, {})
        original = {"cpu": ["usage"]}
        set_shown(original, "cpu", Field.USAGE, True)
        self.assertEqual(original, {"cpu": ["usage"]})             # not mutated

    def test_visibility_rules(self):
        self.assertTrue(visible(Field.CHART, set()))
        self.assertFalse(visible(Field.CHART, {Field.CHART}))
        self.assertFalse(visible(Field.USAGE, set(), show_details=False))   # global switch
        self.assertFalse(visible(Field.DESCRIPTION, set(), show_description=False))
        self.assertTrue(visible(Field.NAME, set(), show_details=False, minimized=True))
        self.assertFalse(visible(Field.DESCRIPTION, set(), minimized=True))
        self.assertFalse(visible(Field.NAME, {Field.NAME}))


if __name__ == "__main__":
    unittest.main()
