"""Moving between panes without the sidebar: Go To (Milestone 48)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.navigation import (GOTO_LABEL, MOUSE_BACK, MOUSE_FORWARD,  # noqa: E402
                                    NavigationHistory, fill_goto_menu, goto_labels,
                                    menu_targets, mouse_direction)

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()


class GotoMenuTest(unittest.TestCase):
    def test_labels_are_titles_unless_two_panes_share_one(self):
        entries = [("cpu", "Processor", "Intel i5"),
                   ("drive-sda", "Solid State Drive", "Samsung 870"),
                   ("drive-sdb", "Solid State Drive", "Samsung 870 EVO"),
                   ("drive-sdc", "Hard Disk", ""),
                   ("drive-sdd", "Hard Disk", "")]
        self.assertEqual(goto_labels(entries), [
            ("cpu", "Processor"),
            ("drive-sda", "Solid State Drive (Samsung 870)"),
            ("drive-sdb", "Solid State Drive (Samsung 870 EVO)"),
            ("drive-sdc", "Hard Disk (drive-sdc)"),          # no description: the ID
            ("drive-sdd", "Hard Disk (drive-sdd)")])

    def test_menu_is_refilled_in_place_in_order(self):
        menu = Gio.Menu()
        fill_goto_menu(menu, [("overview", "Overview", ""), ("cpu", "Processor", "")])
        self.assertEqual(menu_targets(menu), [("Overview", "overview"), ("Processor", "cpu")])
        fill_goto_menu(menu, [("cpu", "Processor", "")])
        self.assertEqual(menu_targets(menu), [("Processor", "cpu")])
        action = menu.get_item_attribute_value(0, "action", GLib.VariantType("s"))
        self.assertEqual(action.get_string(), "win.go-to")


class HistoryTest(unittest.TestCase):
    """Back and forward (Milestone 49), browser-style."""

    def walk(self, *pages):
        h = NavigationHistory()
        for p in pages:
            h.visit(p)
        return h

    def test_back_and_forward(self):
        h = self.walk("overview", "cpu", "memory")
        self.assertFalse(h.can_go_forward())
        self.assertEqual(h.back(), "cpu")
        self.assertEqual(h.back(), "overview")
        self.assertIsNone(h.back())                          # nothing before the first
        self.assertEqual(h.current, "overview")
        self.assertEqual(h.forward(), "cpu")
        self.assertEqual(h.forward(), "memory")
        self.assertIsNone(h.forward())

    def test_a_new_visit_drops_forward(self):
        h = self.walk("a", "b", "c")
        h.back()
        h.visit("d")
        self.assertFalse(h.can_go_forward())
        self.assertEqual(h.back(), "b")

    def test_revisiting_the_current_page_adds_nothing(self):
        h = self.walk("a", "a", "b", "b")
        self.assertEqual(h.back_stack, ["a"])

    def test_limit(self):
        h = NavigationHistory(limit=3)
        for p in "abcdefg":
            h.visit(p)
        self.assertEqual(h.back_stack, ["d", "e", "f"])

    def test_removed_pages_are_forgotten_and_neighbours_merge(self):
        h = self.walk("a", "drive", "a", "b")
        h.remove("drive")
        self.assertEqual(h.back_stack, ["a"])                # a, a → a
        self.assertEqual(h.back(), "a")
        h = self.walk("a", "b", "drive")
        h.remove("drive")                                    # the current one
        self.assertIsNone(h.current)
        h.visit("b")                                         # the neighbour the window shows
        self.assertEqual(h.back_stack, ["a"])                # ...not b twice
        h = self.walk("a", "b", "c")
        h.back()
        h.back()
        h.remove("b")
        self.assertEqual(h.forward(), "c")

    def test_mouse_buttons(self):
        self.assertEqual((MOUSE_BACK, MOUSE_FORWARD), (8, 9))
        self.assertEqual(mouse_direction(8), "back")
        self.assertEqual(mouse_direction(9), "forward")
        self.assertEqual(mouse_direction(11), "back")      # BTN_BACK on some mice
        self.assertEqual(mouse_direction(10), "forward")   # BTN_FORWARD
        for other in (1, 2, 3, 4, 5, 12):
            self.assertIsNone(mouse_direction(other))


class FakeGesture:
    def __init__(self, button):
        self.button = button
        self.states = []

    def get_current_button(self):
        return self.button

    def set_state(self, state):
        self.states.append(state)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class BackForwardWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def make(self, demo=True):
        from helpers import make_context
        from proccoli.ui.window import MainWindow
        ctx = make_context(self, settings=Settings.for_tests(), demo=demo)
        ctx.start()
        if not demo:
            ctx.devices.refresh(1.0)
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        return win

    def test_mouse_buttons_go_back_and_forward(self):
        win = self.make()
        first = win.visible_page_id()
        win.sidebar.select("cpu")                            # by the sidebar
        win.activate_action("win.go-to", GLib.Variant("s", "memory"))   # by Go To
        back = FakeGesture(MOUSE_BACK)
        self.assertTrue(win.on_mouse_button(back))
        self.assertEqual(back.states, [Gtk.EventSequenceState.CLAIMED])
        self.assertEqual(win.visible_page_id(), "cpu")
        self.assertEqual(win.sidebar.selected_id(), "cpu")
        win.on_mouse_button(FakeGesture(MOUSE_BACK))
        self.assertEqual(win.visible_page_id(), first)
        win.on_mouse_button(FakeGesture(MOUSE_FORWARD))
        win.on_mouse_button(FakeGesture(MOUSE_FORWARD))
        self.assertEqual(win.visible_page_id(), "memory")

    def test_other_buttons_are_left_to_their_widgets(self):
        win = self.make()
        win.sidebar.select("cpu")
        for button in (1, 2, 3):
            g = FakeGesture(button)
            self.assertFalse(win.on_mouse_button(g))
            self.assertEqual(g.states, [Gtk.EventSequenceState.DENIED])
        self.assertEqual(win.visible_page_id(), "cpu")

    def test_the_gesture_listens_to_every_button_first(self):
        win = self.make()
        self.assertEqual(win.mouse_nav.get_button(), 0)
        self.assertEqual(win.mouse_nav.get_propagation_phase(), Gtk.PropagationPhase.CAPTURE)

    def test_keyboard_and_action_state(self):
        win = self.make()
        self.assertEqual(self.app.get_accels_for_action("win.back"), ["<Alt>Left"])
        self.assertEqual(self.app.get_accels_for_action("win.forward"), ["<Alt>Right"])
        self.assertFalse(win.nav_actions["back"].get_enabled())   # nowhere to go yet
        win.sidebar.select("cpu")
        self.assertTrue(win.nav_actions["back"].get_enabled())
        win.activate_action("win.back", None)
        self.assertTrue(win.nav_actions["forward"].get_enabled())
        win.activate_action("win.forward", None)
        self.assertEqual(win.visible_page_id(), "cpu")

    def test_going_back_doesnt_record_a_visit(self):
        win = self.make()
        win.sidebar.select("cpu")
        win.sidebar.select("memory")
        win.go_back()
        self.assertEqual(win.history.forward_stack, ["memory"])

    def test_unplugged_page_is_skipped(self):
        win = self.make(demo=False)
        net = next(i for i in win.sidebar.order() if i.startswith("net-"))
        win.sidebar.select("cpu")
        win.sidebar.select(net)
        win.sidebar.select("memory")
        win.remove_page(net)
        win.go_back()
        self.assertEqual(win.visible_page_id(), "cpu")


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GotoWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def make(self, demo=True):
        from helpers import make_context
        from proccoli.ui.window import MainWindow
        self.settings = Settings.for_tests()
        ctx = make_context(self, settings=self.settings, demo=demo)
        ctx.start()
        if not demo:
            ctx.devices.refresh(1.0)
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        return win

    def goto_submenu(self, win):
        menu = win.menu_model
        section = menu.get_item_link(0, Gio.MENU_LINK_SECTION)
        label = section.get_item_attribute_value(0, "label", GLib.VariantType("s"))
        self.assertEqual(label.get_string(), GOTO_LABEL)
        return section.get_item_link(0, Gio.MENU_LINK_SUBMENU)

    def test_go_to_lists_every_pane_in_sidebar_order(self):
        win = self.make(demo=False)
        targets = [t for _, t in menu_targets(self.goto_submenu(win))]
        self.assertEqual(targets, win.sidebar.order())
        self.assertIs(self.goto_submenu(win), win.goto_menu)    # the menu shown is filled

    def test_choosing_an_item_switches_pane_and_marks_it(self):
        win = self.make()
        win.activate_action("win.go-to", GLib.Variant("s", "memory"))
        self.assertEqual(win.visible_page_id(), "memory")
        self.assertEqual(win.sidebar.selected_id(), "memory")
        self.assertEqual(win.goto_action.get_state().get_string(), "memory")
        win.select_page("cpu")                                  # by any other way
        self.assertEqual(win.goto_action.get_state().get_string(), "cpu")

    def test_first_page_is_marked_from_the_start(self):
        win = self.make()
        self.assertEqual(win.goto_action.get_state().get_string(), win.visible_page_id())

    def test_menu_follows_moves_and_removals(self):
        win = self.make(demo=False)
        win.sidebar.move("memory", -1)
        targets = [t for _, t in menu_targets(win.goto_menu)]
        self.assertLess(targets.index("memory"), targets.index("cpu"))
        net = next(i for i in targets if i.startswith("net-"))
        win.remove_page(net)
        self.assertNotIn(net, [t for _, t in menu_targets(win.goto_menu)])

    def test_placeholders_say_nothing_about_the_project(self):
        from proccoli.ui.window import placeholder_reason
        win = self.make()                                       # demo: CPU is a placeholder
        self.assertEqual(win.page("cpu").reason, "Not available in demo mode.")
        self.assertEqual(placeholder_reason(False), "Not available on this system.")
        for reason in (placeholder_reason(True), placeholder_reason(False)):
            self.assertNotIn("Milestone", reason)
            self.assertNotIn("PLAN", reason)


if __name__ == "__main__":
    unittest.main()
