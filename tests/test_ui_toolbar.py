"""The graph toolbar: view settings under the page header,
reorderable, shown or hidden per item, following the settings both ways.

Runs only on the private headless display (``make ui-test``)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from helpers import make_context  # noqa: E402
from proccoli.core.profile import Profile, profile_settings  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.toolbar_items import BY_ID, DEFAULT_ORDER  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
    from proccoli.ui.widgets.graph_toolbar import GraphToolbar


class ReorderKeysTest(unittest.TestCase):
    """The keys that move an item (no display needed)."""

    def press(self, keyval, state, keys, modifiers):
        from proccoli.ui.widgets.reorderable import _on_key
        moves = []
        handled = _on_key("x", keyval, state, keys, modifiers,
                          lambda i, d: moves.append(d), lambda: True)
        return handled, moves

    def test_sidebar_alt_up_and_down(self):
        from gi.repository import Gdk
        from proccoli.ui.widgets.reorderable import ALT, VERTICAL
        self.assertEqual(self.press(Gdk.KEY_Up, ALT, VERTICAL, ALT), (True, [-1]))
        self.assertEqual(self.press(Gdk.KEY_Down, ALT, VERTICAL, ALT), (True, [1]))
        self.assertEqual(self.press(Gdk.KEY_Up, 0, VERTICAL, ALT), (False, []))

    def test_toolbar_ctrl_shift_left_and_right_leave_alt_for_back_and_forward(self):
        from gi.repository import Gdk
        from proccoli.ui.widgets.reorderable import ALT, CTRL_SHIFT, HORIZONTAL
        self.assertEqual(self.press(Gdk.KEY_Left, CTRL_SHIFT, HORIZONTAL, CTRL_SHIFT),
                         (True, [-1]))
        self.assertEqual(self.press(Gdk.KEY_Left, ALT, HORIZONTAL, CTRL_SHIFT), (False, []))
        lock = Gdk.ModifierType.LOCK_MASK                       # Caps Lock doesn't matter
        self.assertEqual(self.press(Gdk.KEY_Right, CTRL_SHIFT | lock, HORIZONTAL, CTRL_SHIFT),
                         (True, [1]))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GraphToolbarTest(unittest.TestCase):
    def make(self, settings=None):
        self.settings = settings or Settings.for_tests()
        bar = GraphToolbar(self.settings)
        self.addCleanup(bar.release)
        bar.set_page("cpu", True)
        return bar

    def test_default_items_in_order_then_logical_cpus_on_the_processor_pane(self):
        bar = self.make()
        self.assertEqual(bar.visible_items(), ["time-range", "axes", "grids", "logical-cpus"])
        self.assertEqual([bar.text(i) for i in bar.visible_items()],
                         ["Time Range 1 Minute", "Graph Axes", "Graph Grid", "Logical CPUs"])

    def test_every_item_has_its_title_above_it(self):
        bar = self.make(Settings.for_tests({"toolbar-items": list(DEFAULT_ORDER)}))
        for item_id, cell in bar.cells.items():
            with self.subTest(item_id):
                title, control = cell.get_first_child(), cell.get_last_child()
                self.assertIsInstance(title, Gtk.Label)
                self.assertEqual(title.get_label(), BY_ID[item_id].title)
                self.assertIs(control, bar.buttons[item_id])
                self.assertEqual(cell.get_orientation(), Gtk.Orientation.VERTICAL)

    def test_toggles_are_switches_without_text(self):
        bar = self.make()
        for item_id in ("axes", "grids", "logical-cpus"):
            with self.subTest(item_id):
                self.assertIsInstance(bar.buttons[item_id], Gtk.Switch)
        self.assertFalse(bar.buttons["grids"].get_active())
        bar.buttons["grids"].set_active(True)                    # slides on
        self.assertTrue(self.settings.get("show-graph-grids"))
        self.assertIsInstance(bar.buttons["time-range"], Gtk.MenuButton)

    def test_a_toggle_sets_its_setting_and_follows_it(self):
        bar = self.make()
        bar.buttons["grids"].set_active(True)
        self.assertTrue(self.settings.get("show-graph-grids"))
        self.settings.set("show-graph-axes", False)
        self.assertFalse(bar.buttons["axes"].get_active())

    def test_a_menu_choice_sets_the_range(self):
        bar = self.make()
        bar.actions.activate_action("time-range", GLib.Variant("s", "1-hour"))
        self.assertEqual(self.settings.get("graph-time-range"), "1-hour")
        self.assertEqual(bar.text("time-range"), "Time Range 1 Hour")
        self.settings.set("graph-time-range", "5-minutes")       # e.g. from Preferences
        self.assertEqual(bar.text("time-range"), "Time Range 5 Minutes")
        self.assertEqual(bar.actions.get_action_state("time-range").get_string(), "5-minutes")

    def test_custom_range_from_the_toolbar(self):
        from proccoli.ui.widgets.graph_toolbar import choices_menu
        from test_ui_lightweight import menu_labels
        bar = self.make()
        self.assertIn("Custom…", menu_labels(choices_menu(BY_ID["time-range"])))
        bar.actions.activate_action("custom-range", None)
        dialog = bar.custom_dialog
        self.assertEqual(dialog.editor.seconds(), 7200)                # the stored one
        dialog.editor.set_seconds(5400)
        dialog.emit("response", "set")
        self.assertEqual(self.settings.get("graph-time-range"), "custom")
        self.assertEqual(self.settings.get("graph-time-range-custom"), 5400)
        self.assertEqual(bar.text("time-range"), "Time Range 90 Minutes")
        self.settings.set("graph-time-range-custom", 2 * 86400)        # from Preferences
        self.assertEqual(bar.text("time-range"), "Time Range 2 Days")

    def test_custom_range_dialog_clamps_and_cancels(self):
        bar = self.make()
        dialog = bar.edit_custom_range()
        dialog.editor.number.set_value(40)
        dialog.editor.unit.set_selected(3)                              # 40 days
        self.assertEqual(dialog.get_body(), "At most 30 Days")
        dialog.emit("response", "set")
        self.assertEqual(self.settings.get("graph-time-range-custom"), 30 * 86400)
        dialog = bar.edit_custom_range()
        dialog.editor.set_seconds(60)
        dialog.emit("response", "cancel")
        self.assertEqual(self.settings.get("graph-time-range-custom"), 30 * 86400)

    def test_dragging_and_alt_arrows_store_the_order(self):
        bar = self.make()
        self.assertTrue(bar.move_before("grids", "time-range"))
        self.assertEqual(self.settings.get("toolbar-items"), ["grids", "time-range", "axes"])
        self.assertEqual(bar.visible_items(), ["grids", "time-range", "axes", "logical-cpus"])
        bar.move("grids", 1)
        self.assertEqual(self.settings.get("toolbar-items"), ["time-range", "grids", "axes"])
        bar.set_item_shown("axes", False)
        self.assertFalse(bar.move_before("axes", "grids"))              # not shown
        self.assertFalse(bar.move_before("logical-cpus", "axes"))       # fixed

    def test_showing_hiding_and_reset(self):
        bar = self.make()
        bar.actions.activate_action("show-axes", None)
        self.assertNotIn("axes", bar.buttons)
        self.assertFalse(bar.actions.get_action_state("show-axes").get_boolean())
        bar.actions.activate_action("show-axes", None)                 # back in its place
        self.assertEqual(bar.order(), ["time-range", "axes", "grids"])
        bar.set_item_shown("time-range", False)
        bar.actions.activate_action("reset", None)
        self.assertEqual(bar.order(), ["time-range", "axes", "grids"])

    def test_logical_cpus_cant_be_shown_hidden_or_stored(self):
        from proccoli.ui.widgets.graph_toolbar import customize_menu
        from test_ui_lightweight import menu_labels
        bar = self.make(Settings.for_tests({"toolbar-items": ["logical-cpus", "axes"]}))
        self.assertEqual(bar.order(), ["axes"])                          # an old saved entry
        self.assertIsNone(bar.actions.lookup_action("show-logical-cpus"))
        self.assertNotIn("Show Each Logical CPU", menu_labels(customize_menu()))
        bar.set_item_shown("logical-cpus", True)
        self.assertEqual(self.settings.get("toolbar-items"), ["axes"])

    def test_items_follow_the_page(self):
        bar = self.make()
        self.assertEqual(bar.visible_items(), ["time-range", "axes", "grids", "logical-cpus"])
        bar.set_page("memory", True)
        self.assertEqual(bar.visible_items(), ["time-range", "axes", "grids"])
        bar.set_page("processes", False)
        self.assertEqual(bar.visible_items(), [])
        self.assertFalse(bar.get_visible())

    def test_update_interval_isnt_a_toolbar_item(self):
        from proccoli.ui.widgets.graph_toolbar import customize_menu
        from test_ui_lightweight import menu_labels
        bar = self.make(Settings.for_tests({"toolbar-items": ["update-interval", "axes"]}))
        self.assertEqual(bar.order(), ["axes"])                     # an old saved entry
        self.assertNotIn("update-interval", bar.buttons)
        self.assertFalse(any("Interval" in label for label in menu_labels(customize_menu())))

    def test_hidden_on_pages_without_graphs_when_nothing_applies(self):
        bar = self.make()
        bar.set_page("processes", False)
        self.assertFalse(bar.get_visible())
        bar.set_page("drive", True)
        self.assertTrue(bar.get_visible())

    def test_an_empty_toolbar_stays_on_graph_pages_to_be_customized(self):
        bar = self.make(Settings.for_tests({"toolbar-items": []}))
        bar.set_page("memory", True)
        self.assertEqual(bar.visible_items(), [])
        self.assertTrue(bar.get_visible())

    def test_pinned_settings_show_greyed_out(self):
        settings = profile_settings(Settings.for_tests({"show-graph-grids": True}),
                                    Profile.lightweight())
        bar = self.make(settings)
        self.assertFalse(bar.buttons["grids"].get_sensitive())
        self.assertFalse(bar.buttons["grids"].get_active())           # the pinned value
        self.assertFalse(bar.actions.get_action_enabled("time-range"))
        bar.choose(BY_ID["time-range"], "1-day")
        self.assertEqual(settings.base.get("graph-time-range"), "1-minute")


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class WindowToolbarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def window(self, settings=None):
        from proccoli.ui.window import MainWindow
        ctx = make_context(self, demo=True, settings=settings or Settings.for_tests())
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        ctx.ticker.tick_now()
        return win

    def test_one_toolbar_moves_under_the_shown_page(self):
        win = self.window()
        bar = win.graph_toolbar
        self.assertTrue(win.containers["overview"].has_toolbar(bar))
        win.select_page("demo")
        self.assertTrue(win.containers["demo"].has_toolbar(bar))
        self.assertFalse(win.containers["overview"].has_toolbar(bar))
        self.assertTrue(bar.get_visible())
        win.select_page("processes")
        self.assertFalse(bar.get_visible())

    def test_toggling_grids_reaches_the_page_graphs(self):
        win = self.window()
        win.select_page("demo")
        win.graph_toolbar.buttons["grids"].set_active(True)
        graphs = win.page("demo").charts.bound()
        self.assertTrue(graphs)
        self.assertTrue(all(g.show_grid for g in graphs))

    def test_grid_reaches_every_pane_chart_but_not_the_sidebar(self):
        # The Overview's cards have the grid; the sidebar's charts never do.
        win = self.window()
        win.graph_toolbar.buttons["grids"].set_active(True)
        cards = [c.graph for c in win.overview.cards.values() if c.graph is not None]
        meters = [i.meter.graph for i in win.sidebar.items.values() if i.has_meter]
        self.assertTrue(cards)
        self.assertTrue(meters)
        self.assertTrue(all(g.show_grid for g in cards))
        self.assertFalse(any(g.show_grid for g in meters))
        win.graph_toolbar.buttons["grids"].set_active(False)
        self.assertFalse(any(g.show_grid for g in cards))

    def test_removing_the_shown_page_keeps_the_toolbar(self):
        win = self.window()
        win.select_page("demo")
        win.remove_page("demo")                 # its neighbour is shown instead
        shown = win.containers[win.visible_page_id()]
        self.assertTrue(shown.has_toolbar(win.graph_toolbar))
        win.select_page("overview")
        self.assertTrue(win.containers["overview"].has_toolbar(win.graph_toolbar))

    def test_show_toolbar_hides_it_and_gives_the_page_the_room(self):
        from proccoli.ui.window import TOOLBAR_ACTION
        settings = Settings.for_tests()
        win = self.window(settings)
        win.select_page("demo")
        self.assertTrue(win.graph_toolbar.get_visible())
        win.activate_action(f"win.{TOOLBAR_ACTION}", None)
        self.assertFalse(settings.get("show-toolbar"))
        self.assertFalse(win.graph_toolbar.get_visible())
        self.assertFalse(win.lookup_action(TOOLBAR_ACTION).get_state().get_boolean())
        settings.set("show-toolbar", True)                     # e.g. another window
        self.assertTrue(win.graph_toolbar.get_visible())
        self.assertTrue(win.lookup_action(TOOLBAR_ACTION).get_state().get_boolean())

    def test_main_menu_has_show_toolbar(self):
        from proccoli.ui.window import primary_menu
        from test_ui_lightweight import menu_labels
        self.assertIn("Show Toolbar", menu_labels(primary_menu()))
        self.assertNotIn("Show Toolbar", menu_labels(primary_menu(toolbar=False)))

    def test_no_toolbar_in_lightweight_mode(self):
        settings = profile_settings(Settings.for_tests(), Profile.lightweight())
        win = self.window(settings)
        self.assertIsNone(win.graph_toolbar)
        self.assertIsNone(win.lookup_action("show-toolbar"))


if __name__ == "__main__":
    unittest.main()
