"""Hiding the sidebar at any width; the main menu (the logo)
stays top left;
the sidebar's Full / Icons Only / Hidden modes in the main menu (Milestones
52 and 54)."""

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
from proccoli.ui.sidebar_style import (MODE_ACTION, MODE_LABELS, SECTION_LABEL,  # noqa: E402
                                       STYLE_SETTING, Mode, SidebarStyle)
from proccoli.ui.sidebar_visibility import (ACTION, SETTING,  # noqa: E402
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
    def test_page_headers_show_the_logo_unless_the_sidebar_is_beside_them(self):
        self.assertFalse(header_controls_visible(show_sidebar=True, collapsed=False))
        self.assertTrue(header_controls_visible(show_sidebar=False, collapsed=False))
        self.assertTrue(header_controls_visible(show_sidebar=True, collapsed=True))   # overlay
        self.assertTrue(header_controls_visible(show_sidebar=False, collapsed=True))


class ControllerTest(unittest.TestCase):
    def make(self, **settings):
        self.settings = Settings.for_tests(settings)
        self.split = FakeSplit()
        self.styles = []                                     # what on_style was told
        self.vis = SidebarVisibility(self.split, self.settings, on_style=self.styles.append)
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
        self.settings.set(STYLE_SETTING, "icons")
        self.assertEqual(self.styles, [SidebarStyle.FULL])     # only the first, at start

    # -- Full / Icons Only / Hidden ---------------------------------------------

    def mode(self):
        return self.vis.mode_action.get_state().get_string()

    def pick(self, mode):
        self.vis.mode_action.activate(GLib.Variant.new_string(mode.value))

    def test_the_style_is_applied_at_start(self):
        self.make(**{STYLE_SETTING: "icons"})
        self.assertEqual(self.styles, [SidebarStyle.ICONS])
        self.assertEqual(self.mode(), "icons")

    def test_mode_action_is_a_radio_group(self):
        self.make()
        self.assertEqual(self.vis.mode_action.get_name(), MODE_ACTION)
        self.assertEqual(self.vis.mode_action.get_parameter_type().dup_string(), "s")
        self.assertEqual(self.mode(), "full")

    def test_picking_icons_only_shows_and_saves_the_style(self):
        self.make(**{SETTING: False})
        self.assertEqual(self.mode(), "hidden")
        self.pick(Mode.ICONS)
        self.assertTrue(self.split.show_sidebar)
        self.assertTrue(self.settings.get(SETTING))
        self.assertEqual(self.settings.get(STYLE_SETTING), "icons")
        self.assertEqual(self.styles[-1], SidebarStyle.ICONS)
        self.assertEqual(self.mode(), "icons")
        self.pick(Mode.FULL)
        self.assertEqual(self.settings.get(STYLE_SETTING), "full")
        self.assertEqual(self.styles[-1], SidebarStyle.FULL)

    def test_hidden_keeps_the_style_and_f9_brings_it_back(self):
        self.make(**{STYLE_SETTING: "icons"})
        self.pick(Mode.HIDDEN)
        self.assertFalse(self.split.show_sidebar)
        self.assertFalse(self.settings.get(SETTING))
        self.assertEqual(self.settings.get(STYLE_SETTING), "icons")   # kept
        self.assertEqual(self.mode(), "hidden")
        self.vis.action.activate(None)                        # F9
        self.assertTrue(self.split.show_sidebar)
        self.assertEqual(self.mode(), "icons")

    def test_mode_follows_changes_from_elsewhere(self):
        self.make()
        self.settings.set(STYLE_SETTING, "icons")              # Preferences → Sidebar
        self.assertEqual(self.mode(), "icons")
        self.assertEqual(self.styles[-1], SidebarStyle.ICONS)
        self.split.set_show_sidebar(False)                    # e.g. a swipe
        self.assertEqual(self.mode(), "hidden")

    def test_narrow_overlay_marks_hidden_until_opened(self):
        self.make(**{STYLE_SETTING: "icons"})
        self.split.set_collapsed(True)
        self.assertEqual(self.mode(), "hidden")
        self.pick(Mode.ICONS)                                  # opens the overlay
        self.assertTrue(self.split.show_sidebar)
        self.assertEqual(self.mode(), "icons")


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

    def assert_corner(self, logo, win):
        """The logo in the top-left corner, nothing after it in the same box
        (the sidebar toggle is a menu item)."""
        from proccoli import APP_ID
        x, y = self.at(logo, win)
        self.assertLess(x, 40, "logo at the left edge")
        self.assertLess(y, 40, "logo at the top")
        self.assertIsNone(logo.get_next_sibling(), "nothing after the logo (no burger)")
        self.assertEqual(logo.get_child().get_icon_name(), APP_ID)
        # the logo is the main menu, About its first item.
        self.assertIsInstance(logo, Gtk.MenuButton)
        self.assertIs(logo.get_menu_model(), win.menu_model)
        self.assertTrue(logo.get_primary())                   # F10
        first = win.menu_model.get_item_link(0, Gio.MENU_LINK_SECTION)
        s = GLib.VariantType("s")
        self.assertEqual([first.get_item_attribute_value(0, a, s).get_string()
                          for a in ("label", "action")], ["About Proccoli", "app.about"])
        self.assertEqual(self.menu_actions(win).count("app.about"), 1)

    def sidebar_buttons(self, widget):
        """Every button under ``widget`` showing the sidebar icon."""
        out, child = [], widget.get_first_child()
        if isinstance(widget, Gtk.Button) and widget.get_icon_name() == "sidebar-show-symbolic":
            out.append(widget)
        while child is not None:
            out += self.sidebar_buttons(child)
            child = child.get_next_sibling()
        return out

    def menu_actions(self, win):
        """Every action in the main menu, sections and submenus included."""
        s, out = GLib.VariantType("s"), []

        def walk(model):
            for i in range(model.get_n_items()):
                action = model.get_item_attribute_value(i, "action", s)
                if action is not None:
                    out.append(action.get_string())
                for link in (Gio.MENU_LINK_SECTION, Gio.MENU_LINK_SUBMENU):
                    child = model.get_item_link(i, link)
                    if child is not None:
                        walk(child)
        walk(win.menu_model)
        return out

    def sidebar_section(self, win):
        """(section index, its label, [(item label, action, target)]) of the
        main menu's Sidebar section."""
        s = GLib.VariantType("s")
        for i in range(win.menu_model.get_n_items()):
            title = win.menu_model.get_item_attribute_value(i, "label", s)
            if title is None or title.get_string() != SECTION_LABEL:
                continue
            section = win.menu_model.get_item_link(i, Gio.MENU_LINK_SECTION)
            items = [tuple(section.get_item_attribute_value(j, attr, s).get_string()
                           for attr in ("label", "action", "target"))
                     for j in range(section.get_n_items())]
            return i, title.get_string(), items
        return None

    def test_logo_is_the_main_menu_in_the_sidebar_header(self):
        win = self.make()
        self.assert_corner(win.menu_button, win)
        self.assertFalse(hasattr(win, "logo_button"))

    def test_no_sidebar_buttons_anywhere(self):
        win = self.make()
        self.at(win.menu_button, win)
        headers = [win.sidebar_header] + [c.header for c in win.containers.values()]
        for header in headers:
            self.assertEqual(self.sidebar_buttons(header), [])

    def test_sidebar_modes_follow_go_to_in_the_main_menu(self):
        win = self.make()
        index, _title, items = self.sidebar_section(win)
        self.assertEqual(index, 2)                    # About, Go To, then Sidebar
        self.assertEqual(items, [(MODE_LABELS[m], f"win.{MODE_ACTION}", m.value)
                                 for m in Mode])
        self.assertEqual(win.get_action_state(MODE_ACTION).get_string(), "full")
        win.split_view.set_show_sidebar(False)
        self.assertEqual(win.get_action_state(MODE_ACTION).get_string(), "hidden")

    def test_hiding_from_the_menu_moves_the_logo_into_the_page_headers(self):
        win = self.make()
        container = win.containers[win.visible_page_id()]
        self.assertFalse(container.start_controls.get_visible())
        win.activate_action(f"win.{MODE_ACTION}",
                            GLib.Variant.new_string("hidden"))   # ≡ → Sidebar → Hidden
        self.assertFalse(win.split_view.get_show_sidebar())
        self.assertTrue(container.start_controls.get_visible())
        self.assert_corner(container.menu_button, win)
        self.assertFalse(self.settings.get(SETTING))
        win.activate_action(f"win.{MODE_ACTION}", GLib.Variant.new_string("full"))
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

    def test_icons_only_narrows_the_sidebar_to_its_header(self):
        from test_ui_shell import pump
        win = self.make()
        full = (win.split_view.get_min_sidebar_width(), win.split_view.get_max_sidebar_width())
        self.at(win.menu_button, win)
        win.activate_action(f"win.{MODE_ACTION}", GLib.Variant.new_string("icons"))
        self.assertEqual(self.settings.get(STYLE_SETTING), "icons")
        width = win.split_view.get_max_sidebar_width()
        self.assertEqual(win.split_view.get_min_sidebar_width(), width)
        self.assertLess(width, full[0])
        pump(lambda: win.sidebar.get_width() <= width + 1, timeout=3)
        # The corner still holds the logo (the main menu), inside the rail.
        self.assert_corner(win.menu_button, win)
        lx, _ = self.at(win.menu_button, win)
        self.assertLessEqual(lx + win.menu_button.get_width(), width + 1)
        # Every row is just its icon, with hover text.
        for item in win.sidebar.items.values():
            self.assertTrue(item.compact)
            self.assertFalse(item.label.get_visible())
            self.assertFalse(item.details.get_visible())
            self.assertTrue(item.get_tooltip_text().startswith(item.page.title))
        win.activate_action(f"win.{MODE_ACTION}", GLib.Variant.new_string("full"))
        self.assertEqual((win.split_view.get_min_sidebar_width(),
                          win.split_view.get_max_sidebar_width()), full)
        for item in win.sidebar.items.values():
            self.assertTrue(item.label.get_visible())
            self.assertIsNone(item.get_tooltip_text())

    def test_starts_as_icons_only_when_left_so(self):
        win = self.make(**{STYLE_SETTING: "icons"})
        self.assertTrue(win.sidebar.compact)
        self.assertTrue(all(i.compact for i in win.sidebar.items.values()))

    def test_removed_page_stops_following(self):
        win = self.make()
        container = win.containers["demo"]
        win.remove_page("demo")
        self.assertEqual(len(container.split_connections), 0)
        win.split_view.set_show_sidebar(False)                # no error from the old one


if __name__ == "__main__":
    unittest.main()
