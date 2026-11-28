"""The keyboard shortcuts table: what it sets and what the dialog lists."""

from __future__ import annotations

import unittest

from proccoli.ui import shortcuts


class ShortcutsTableTest(unittest.TestCase):

    def test_preferences_is_f2_and_keeps_ctrl_comma(self):
        self.assertEqual(shortcuts.accels_for("app.preferences"), ["F2", "<Control>comma"])

    def test_keyboard_shortcuts_is_f1_and_keeps_ctrl_question(self):
        self.assertEqual(shortcuts.accels_for("app.shortcuts"), ["F1", "<Control>question"])

    def test_the_single_keys_are_offered_first_so_menus_show_them(self):
        self.assertEqual(shortcuts.accels_for("app.preferences")[0], "F2")
        self.assertEqual(shortcuts.accels_for("app.shortcuts")[0], "F1")

    def test_no_accelerator_is_given_to_two_actions(self):
        seen = {}
        for action, accels in shortcuts.ACCELS.items():
            for accel in accels:
                self.assertNotIn(accel, seen, f"{accel}: {seen.get(accel)} and {action}")
                seen[accel] = action
        table = {a for _, a in shortcuts.TABLE_SHORTCUTS}
        self.assertEqual(table & set(seen), set())

    def test_f10_stays_free_for_the_main_menu(self):
        every = {a for accels in shortcuts.ACCELS.values() for a in accels}
        self.assertNotIn("F10", every)

    def test_the_dialog_lists_every_accelerator_of_each_action(self):
        general = dict(shortcuts.SHORTCUTS[0][1])
        self.assertEqual(general["Preferences"], "F2 <Control>comma")
        self.assertEqual(general["Keyboard Shortcuts"], "F1 <Control>question")
        self.assertEqual(general["Show or Hide the Sidebar"], "F9")

    def test_an_unknown_action_has_none(self):
        self.assertEqual(shortcuts.accels_for("app.about"), [])

    def test_the_sidebar_action_name_matches_the_window(self):
        from proccoli.ui.sidebar_visibility import ACTION
        self.assertEqual(shortcuts.SIDEBAR_ACTION, ACTION)


if __name__ == "__main__":
    unittest.main()
