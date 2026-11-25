"""Lightweight Mode in the window (Idea 1): pages built on first visit and
dropped after, the Overview as a list, one graph per page, progress-bar
meters, Preferences, and the app's --lightweight."""

import argparse
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import make_context, pump  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from proccoli.core.profile import Profile, profile_settings  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()


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

    def test_overview_list_and_progress_bar_meters(self):
        from proccoli.ui.widgets.meter import MeterType
        win = self.window(light_settings())
        cards = win.overview.cards
        self.assertTrue(cards)
        self.assertTrue(all(c.graph is None for c in cards.values()))
        self.assertIsNone(win.overview.tops)
        card = cards["demo"]
        self.assertNotEqual(card.usage_label.get_label(), "")
        self.assertEqual(win.sidebar.items["demo"].meter.meter_type, MeterType.PROGRESS_BAR)

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
