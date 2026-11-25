"""Lightweight Mode in the window: pages built on first visit and
dropped after, the Overview as a list with small charts and an icons-only
sidebar, one graph per page, Preferences, and the app's
--lightweight."""

import argparse
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import make_context  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from proccoli.core.profile import Profile, profile_settings  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()


def menu_labels(menu) -> list:
    """Every item label in a Gio.MenuModel, sections and submenus included."""
    out = []
    for i in range(menu.get_n_items()):
        label = menu.get_item_attribute_value(i, "label", None)
        if label is not None:
            out.append(label.get_string())
        for link in ("section", "submenu"):
            child = menu.get_item_link(i, link)
            if child is not None:
                out += menu_labels(child)
    return out


def descendants(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from descendants(child)
        child = child.get_next_sibling()


def light_settings(**overrides):
    return profile_settings(Settings.for_tests(overrides), Profile.lightweight())


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class LightweightWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def window(self, settings):
        from proccoli.ui.window import MainWindow
        ctx = make_context(self, demo=True, settings=settings)
        ctx.start()
        self.addCleanup(ctx.stop)
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        ctx.ticker.tick_now()
        ctx.ticker.tick_now()
        return win

    def test_pages_are_built_on_visit_and_dropped_after(self):
        from proccoli.ui.lazy import StubPage
        from proccoli.ui.pages.demo import DemoPage
        win = self.window(light_settings())
        timers = []
        win.lazy.schedule = lambda seconds, cb: timers.append((seconds, cb))
        self.assertIsInstance(win.page("demo"), StubPage)
        summary = win.page("demo").sidebar_summary()             # works unbuilt
        self.assertIsNotNone(summary.usage)
        win.select_page("demo")
        self.assertIsInstance(win.page("demo"), DemoPage)
        win.show_overview()
        self.assertEqual(timers[0][0], 60)
        timers[0][1]()
        self.assertIsInstance(win.page("demo"), StubPage)          # dropped
        self.assertIn("demo", win.sidebar.colors)                  # entry and color stay

    def test_overview_small_charts_and_icons_only_sidebar(self):
        """the trend is on the Overview, the sidebar is icons only."""
        from proccoli.ui.chart_settings import ChartKind
        from proccoli.ui.widgets.graph import GraphStyle
        win = self.window(light_settings(**{"sidebar-style": "full"}))
        cards = win.overview.cards
        self.assertTrue(cards)
        for card in cards.values():
            self.assertEqual(card.graph.style, GraphStyle.SMALL)
            self.assertFalse(card.graph.has_axes())
            self.assertEqual(win.overview.charts._bound[card.graph].kind, ChartKind.METER)
        card = cards["demo"]
        self.assertTrue(card.graph.get_visible())
        self.assertEqual(card.graph.entry_index, win.sidebar.colors["demo"])
        self.assertNotEqual(card.usage_label.get_label(), "")
        self.assertTrue(win.sidebar.compact)                     # the user's Full is pinned
        self.assertFalse(any(item.has_meter for item in win.sidebar.items.values()))
        self.assertIsNone(win.overview.tops)                     # demo: no process monitor

    def test_sidebar_menu_offers_icons_only_and_hidden(self):
        from proccoli.ui.sidebar_style import MODE_ACTION
        from gi.repository import GLib
        win = self.window(light_settings())
        labels = menu_labels(win.menu_model)
        self.assertIn("Icons Only", labels)
        self.assertIn("Hidden", labels)
        self.assertNotIn("Full", labels)
        action = win.lookup_action(MODE_ACTION)
        action.change_state(GLib.Variant.new_string("full"))     # a stale target
        self.assertTrue(win.sidebar.compact)
        self.assertEqual(action.get_state().get_string(), "icons")
        action.change_state(GLib.Variant.new_string("hidden"))
        self.assertFalse(win.split_view.get_show_sidebar())
        win.sidebar_visibility.toggle()                          # F9 brings back icons
        self.assertTrue(win.split_view.get_show_sidebar())
        self.assertTrue(win.sidebar.compact)

    def test_one_graph_per_page_without_axes(self):
        win = self.window(light_settings())
        win.select_page("demo")
        page = win.page("demo")
        self.assertEqual(len(page.graphs), 1)
        self.assertTrue(page.text_only)
        self.assertFalse(any(g.get_visible() for g in page.text_only))
        self.assertFalse(page.graphs[0].has_axes())

    def test_full_profile_is_unchanged(self):
        from proccoli.ui.pages.demo import DemoPage
        win = self.window(Settings.for_tests())
        self.assertIsNone(win.lazy)
        self.assertIsInstance(win.page("demo"), DemoPage)
        self.assertTrue(all(c.graph is not None for c in win.overview.cards.values()))
        self.assertIn("Full", menu_labels(win.menu_model))
        self.assertTrue(any(item.has_meter for item in win.sidebar.items.values()))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class LightweightPreferencesTest(unittest.TestCase):
    def test_pinned_rows_and_restart(self):
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        restarts = []
        settings = light_settings(lightweight=True)
        dialog = PreferencesDialog(settings, restart=lambda: restarts.append(1))
        self.assertFalse(dialog.rows["show-graph-axes"].get_sensitive())
        self.assertFalse(dialog.rows["graph-time-range"].get_sensitive())
        self.assertTrue(dialog.rows["update-interval"].get_sensitive())
        self.assertFalse(dialog.restart_row.get_visible())          # as running
        dialog.rows["lightweight"].set_active(False)
        self.assertTrue(dialog.restart_row.get_visible())
        dialog.restart_button.emit("clicked")
        self.assertEqual(restarts, [1])

    def test_fixed_settings_have_a_padlock_and_pages_a_notice(self):
        from gi.repository import Adw, Gtk
        from proccoli.ui.dialogs.preferences import FIXED_ICON, FIXED_TIP, PreferencesDialog
        dialog = PreferencesDialog(light_settings(lightweight=True), restart=lambda: None)
        row = dialog.rows["palette"]
        self.assertFalse(row.get_sensitive())
        icons = [w for w in descendants(row) if isinstance(w, Gtk.Image)
                 and w.get_icon_name() == FIXED_ICON]
        self.assertEqual(len(icons), 1)
        self.assertEqual(icons[0].get_tooltip_text(), FIXED_TIP)
        self.assertIsNone(row.get_tooltip_text())                 # the padlock says it
        free = dialog.rows["update-interval"]
        self.assertFalse(any(isinstance(w, Gtk.Image) and w.get_icon_name() == FIXED_ICON
                             for w in descendants(free)))
        general = row.get_ancestor(Adw.PreferencesPage)
        self.assertTrue(dialog._notices[general].get_visible())
        # A page with nothing fixed has no notice showing.
        quiet = [page for page, notice in dialog._notices.items() if not notice.get_visible()]
        self.assertTrue(quiet)
        for page in quiet:
            self.assertFalse(any(dialog.rows[k].get_ancestor(Adw.PreferencesPage) is page
                                 and not dialog.rows[k].get_sensitive()
                                 for k in dialog.rows))

    def test_no_notice_or_padlocks_in_the_full_window(self):
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        dialog = PreferencesDialog(Settings.for_tests(), restart=lambda: None)
        self.assertEqual(dialog._notices, {})

    def test_the_switch_shows_the_mode_running_now(self):
        # Started with --lightweight: the setting is off, the mode is on.
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        settings = light_settings(lightweight=False)
        dialog = PreferencesDialog(settings, restart=lambda: None)
        self.assertTrue(dialog.rows["lightweight"].get_active())
        self.assertTrue(dialog.restart_row.get_visible())          # off at the next start
        self.assertIn("turns off", dialog.restart_row.get_subtitle())
        # Running in it with the setting on: on, nothing to restart.
        dialog = PreferencesDialog(light_settings(lightweight=True), restart=lambda: None)
        self.assertTrue(dialog.rows["lightweight"].get_active())
        self.assertFalse(dialog.restart_row.get_visible())

    def test_a_pending_change_says_what_happens_next(self):
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        settings = Settings.for_tests({"lightweight": True})     # chosen, not restarted
        dialog = PreferencesDialog(settings, restart=lambda: None)
        self.assertFalse(dialog.rows["lightweight"].get_active())  # the full window runs
        self.assertTrue(dialog.restart_row.get_visible())
        self.assertIn("turns on at the next start", dialog.restart_row.get_subtitle())
        dialog.rows["lightweight"].set_active(True)
        self.assertTrue(settings.get("lightweight"))
        dialog.rows["lightweight"].set_active(False)             # back to how it runs
        self.assertFalse(settings.get("lightweight"))
        self.assertFalse(dialog.restart_row.get_visible())

    def test_full_mode_offers_it(self):
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        settings = Settings.for_tests()
        dialog = PreferencesDialog(settings, restart=lambda: None)
        self.assertTrue(dialog.rows["show-graph-axes"].get_sensitive())
        self.assertFalse(dialog.restart_row.get_visible())
        settings.set("lightweight", True)
        self.assertTrue(dialog.restart_row.get_visible())


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class LightweightAppTest(unittest.TestCase):
    def test_flag_chooses_the_profile(self):
        import tempfile
        from proccoli.app import Application, parse_args
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.assertTrue(parse_args(["--lightweight"]).lightweight)
        built = []

        def factory(settings, demo):
            ctx = make_context(self, demo=demo, settings=settings)
            built.append(ctx)
            return ctx
        app = Application(argparse.Namespace(demo=True, debug=False, lightweight=True),
                          context_factory=factory,
                          log_file=os.path.join(tmp.name, "p.log"))
        app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        app.register(None)
        try:
            self.assertTrue(app.profile.is_lightweight)
            self.assertTrue(built[0].profile.is_lightweight)
            self.assertIsNone(app.theme_css)                         # no palette CSS
            app.quit = lambda: None
            app.restart()
            self.assertTrue(app.restart_requested)
        finally:
            app.ctx.stop()
            app.file_log.shutdown()


if __name__ == "__main__":
    unittest.main()
