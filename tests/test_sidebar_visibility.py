"""Hiding the sidebar at any width; the burger stays top left (Milestone 46);
the sidebar toggle is a main-menu item (Milestone 52)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.sidebar_visibility import (ACTION, LABEL, SETTING,  # noqa: E402
                                            SidebarVisibility, header_controls_visible)

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()


class FakeSplit(GObject.Object):
    """The two Adw.OverlaySplitView properties the controller uses."""
    collapsed = GObject.Property(type=bool, default=False)
    show_sidebar = GObject.Property(type=bool, default=True, nick="show-sidebar")

    def get_collapsed(self):
        return self.collapsed

    def set_collapsed(self, v):
        self.collapsed = v

    def get_show_sidebar(self):
        return self.show_sidebar

    def set_show_sidebar(self, v):
        self.show_sidebar = v


class RulesTest(unittest.TestCase):
    def test_page_headers_show_the_burger_unless_the_sidebar_is_beside_them(self):
        self.assertFalse(header_controls_visible(show_sidebar=True, collapsed=False))
        self.assertTrue(header_controls_visible(show_sidebar=False, collapsed=False))
        self.assertTrue(header_controls_visible(show_sidebar=True, collapsed=True))   # overlay
        self.assertTrue(header_controls_visible(show_sidebar=False, collapsed=True))


class ControllerTest(unittest.TestCase):
    def make(self, **settings):
        self.settings = Settings.for_tests(settings)
        self.split = FakeSplit()
        self.vis = SidebarVisibility(self.split, self.settings)
        self.addCleanup(self.vis.shutdown)

    def test_wide_window_follows_and_saves_the_users_choice(self):
        self.make(**{SETTING: False})
        self.assertFalse(self.split.show_sidebar)           # restored at start
        self.vis.toggle()
        self.assertTrue(self.split.show_sidebar)
        self.assertTrue(self.settings.get(SETTING))
        self.split.set_show_sidebar(False)                    # e.g. the header button
        self.assertFalse(self.settings.get(SETTING))

    def test_narrow_window_overlay_leaves_the_choice_alone(self):
        self.make()
        self.split.set_collapsed(True)
        self.assertFalse(self.split.show_sidebar)             # folded away
        self.vis.toggle()                                     # open the overlay
        self.assertTrue(self.split.show_sidebar)
        self.vis.page_selected()                              # picking a page closes it
        self.assertFalse(self.split.show_sidebar)
        self.assertTrue(self.settings.get(SETTING))           # wide choice unchanged
        self.split.set_collapsed(False)                       # widen again
        self.assertTrue(self.split.show_sidebar)

    def test_hidden_stays_hidden_after_a_narrow_spell(self):
        self.make(**{SETTING: False})
        self.split.set_collapsed(True)
        self.vis.toggle()
        self.split.set_collapsed(False)
        self.assertFalse(self.split.show_sidebar)

    def test_page_selected_on_a_wide_window_changes_nothing(self):
        self.make()
        self.vis.page_selected()
        self.assertTrue(self.split.show_sidebar)

    def state(self):
        return self.vis.action.get_state().get_boolean()

    def test_action_state_follows_the_sidebar(self):
        self.make(**{SETTING: False})
        self.assertEqual(self.vis.action.get_name(), ACTION)
        self.assertIsNone(self.vis.action.get_parameter_type())   # a check item
        self.assertFalse(self.state())
        self.split.set_show_sidebar(True)                     # e.g. a swipe
        self.assertTrue(self.state())
        self.split.set_collapsed(True)                        # folds away
        self.assertFalse(self.state())

    def test_activating_the_action_toggles_and_saves(self):
        self.make()
        self.vis.action.activate(None)                        # the menu item, or F9
        self.assertFalse(self.split.show_sidebar)
        self.assertFalse(self.state())
        self.assertFalse(self.settings.get(SETTING))
        self.vis.action.activate(None)
        self.assertTrue(self.split.show_sidebar)
        self.assertTrue(self.settings.get(SETTING))

    def test_change_state_sets(self):
        self.make()
        self.vis.action.change_state(GLib.Variant.new_boolean(False))
        self.assertFalse(self.split.show_sidebar)
        self.vis.action.change_state(GLib.Variant.new_boolean(False))   # idempotent
        self.assertFalse(self.split.show_sidebar)

    def test_shutdown_stops_following(self):
        self.make()
        self.vis.shutdown()
        self.split.set_show_sidebar(False)
        self.assertTrue(self.settings.get(SETTING))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class WindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def make(self, **settings):
        from helpers import make_context
        from proccoli.ui.window import MainWindow
        self.settings = Settings.for_tests(settings)
        ctx = make_context(self, settings=self.settings, demo=True)
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        win.set_default_size(1024, 768)
        return win

    def at(self, widget, win):
        """(x, y) of ``widget`` in the window, once laid out."""
        from test_ui_shell import pump
        win.present()
        pump(lambda: widget.compute_bounds(win)[0] and widget.get_mapped(), timeout=3)
        pump(timeout=0.3)
        ok, b = widget.compute_bounds(win)
        self.assertTrue(ok)
        return b.get_x(), b.get_y()

    def assert_corner(self, logo, burger, win):
        """Logo in the top-left corner, the burger beside it, nothing after
        it in the same box (the sidebar toggle is a menu item, M52)."""
        from proccoli import APP_ID
        x, y = self.at(logo, win)
        self.assertLess(x, 40, "logo at the left edge")
        self.assertLess(y, 40, "logo at the top")
        bx, by = self.at(burger, win)
        self.assertLess(x, bx, "burger right of the logo")
        self.assertLess(bx - x, 60, "burger next to the logo")
        self.assertLess(by, 40)
        self.assertIsNone(burger.get_next_sibling(), "nothing after the burger")
        self.assertEqual(logo.get_child().get_icon_name(), APP_ID)
        self.assertEqual(logo.get_action_name(), "app.about")

    def sidebar_buttons(self, widget):
        """Every button under ``widget`` showing the sidebar icon."""
        out, child = [], widget.get_first_child()
        if isinstance(widget, Gtk.Button) and widget.get_icon_name() == "sidebar-show-symbolic":
            out.append(widget)
        while child is not None:
            out += self.sidebar_buttons(child)
            child = child.get_next_sibling()
        return out

    def menu_item(self, win):
        """(label, action) of the main menu's Show Sidebar item."""
        for i in range(win.menu_model.get_n_items()):
            section = win.menu_model.get_item_link(i, Gio.MENU_LINK_SECTION)
            for j in range(section.get_n_items()):
                label = section.get_item_attribute_value(j, "label", GLib.VariantType("s"))
                action = section.get_item_attribute_value(j, "action", GLib.VariantType("s"))
                if label and label.get_string() == LABEL:
                    return label.get_string(), action.get_string(), (i, j)
        return None

    def test_logo_then_burger_in_the_sidebar_header(self):
        win = self.make()
        self.assert_corner(win.logo_button, win.menu_button, win)
        self.assertIs(win.menu_button.get_menu_model(), win.menu_model)

    def test_no_sidebar_buttons_anywhere(self):
        win = self.make()
        self.at(win.logo_button, win)
        headers = [win.sidebar_header] + [c.header for c in win.containers.values()]
        for header in headers:
            self.assertEqual(self.sidebar_buttons(header), [])

    def test_show_sidebar_is_a_main_menu_item_after_go_to(self):
        win = self.make()
        label, action, (section, index) = self.menu_item(win)
        self.assertEqual(action, f"win.{ACTION}")
        self.assertEqual((section, index), (0, 1))          # Go To, then Show Sidebar
        self.assertTrue(win.get_action_state(ACTION).get_boolean())     # checked
        win.split_view.set_show_sidebar(False)
        self.assertFalse(win.get_action_state(ACTION).get_boolean())

    def test_hiding_from_the_menu_moves_the_burger_into_the_page_headers(self):
        win = self.make()
        container = win.containers[win.visible_page_id()]
        self.assertFalse(container.start_controls.get_visible())
        win.activate_action(f"win.{ACTION}", None)            # ≡ → Show Sidebar (uncheck)
        self.assertFalse(win.split_view.get_show_sidebar())
        self.assertTrue(container.start_controls.get_visible())
        self.assert_corner(container.logo_button, container.menu_button, win)
        self.assertIs(container.menu_button.get_menu_model(), win.menu_model)
        self.assertFalse(self.settings.get(SETTING))
        win.activate_action(f"win.{ACTION}", None)            # and back
        self.assertTrue(win.split_view.get_show_sidebar())
        self.assertFalse(container.start_controls.get_visible())

    def test_f9_toggles(self):
        win = self.make()
        self.assertEqual(self.app.get_accels_for_action(f"win.{ACTION}"), ["F9"])
        win.activate_action(f"win.{ACTION}", None)
        self.assertFalse(win.split_view.get_show_sidebar())
        win.activate_action(f"win.{ACTION}", None)
        self.assertTrue(win.split_view.get_show_sidebar())

    def test_starts_hidden_when_left_hidden(self):
        win = self.make(**{SETTING: False})
        self.assertFalse(win.split_view.get_show_sidebar())
        for container in win.containers.values():
            self.assertTrue(container.start_controls.get_visible())

    def test_removed_page_stops_following(self):
        win = self.make()
        container = win.containers["demo"]
        win.remove_page("demo")
        self.assertEqual(container._split_handlers, [])
        win.split_view.set_show_sidebar(False)                # no error from the old one


if __name__ == "__main__":
    unittest.main()
