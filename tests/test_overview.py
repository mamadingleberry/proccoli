"""The Overview page (41 and 50)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from proccoli.core.history import History  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.page import PageKind, SidebarSummary  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
    from proccoli.ui.page import ScrollingPage
    from proccoli.ui.pages.overview import CARD_SPACING, OverviewCard, OverviewPage
    from proccoli.ui.layout import GRID_MIN_CHART
    from test_ui_shell import pump


class SummaryTextTest(unittest.TestCase):
    """The usage line both the sidebar and the cards show."""

    def test_usage_then_detail(self):
        self.assertEqual(SidebarSummary(42.0, detail="3.1 of 16.0 GB").text(),
                         "42 % · 3.1 of 16.0 GB")
        self.assertEqual(SidebarSummary(None, "1.2 MB/s", "eno1").text(), "1.2 MB/s · eno1")
        self.assertEqual(SidebarSummary(None, detail="idle").text(), "idle")
        self.assertEqual(SidebarSummary().text(), "")

    def test_has_chart(self):
        self.assertFalse(SidebarSummary(5.0).has_chart())
        history = History(10)
        series = history.define("usage", "%")
        self.assertFalse(SidebarSummary(series=[series]).has_chart())      # no points
        history.add(1.0, {"usage": None})
        history.add(2.0, {"usage": None})
        self.assertFalse(SidebarSummary(series=[series]).has_chart())      # only gaps
        history.add(3.0, {"usage": 0.0})
        self.assertTrue(SidebarSummary(series=[series]).has_chart())       # 0 % is a reading
        self.assertFalse(SidebarSummary(series=[None]).has_chart())        # a missing series
        self.assertTrue(SidebarSummary(series=[None, series]).has_chart())

    def test_series_has_values(self):
        history = History(3)
        series = history.define("usage", "%")
        self.assertFalse(series.has_values())
        history.add(1.0, {"usage": 5.0})
        self.assertTrue(series.has_values())
        for t in (2.0, 3.0, 4.0):                       # the reading ages out
            history.add(t, {"usage": None})
        self.assertFalse(series.has_values())
        history.add(5.0, {"usage": 1.0})
        self.assertTrue(series.has_values())


if HAVE_DISPLAY:
    class FakePage(ScrollingPage):
        """A device-like page with a settable summary."""

        def __init__(self, page_id, title="Device", usage=10.0, summary=True, facts=()):
            super().__init__(page_id, PageKind.DRIVE, title, "drive-harddisk-symbolic",
                             description=f"{page_id} model")
            self.history = History(30)
            self.series = [self.history.define("usage", "%")]
            self.history.add(0.0, {"usage": usage})
            self.usage = usage
            self.summary = summary
            self.facts = list(facts)

        def sidebar_summary(self):
            if not self.summary:
                return None
            return SidebarSummary(self.usage, detail="1 of 2 GB", series=self.series,
                                  facts=list(self.facts))

        def set_usage(self, usage):
            self.usage = usage
            self.history.add(float(len(self.history)), {"usage": usage})
            self.summary_changed()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class OverviewPageTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings.for_tests()
        self.went = []
        self.page = OverviewPage(self.settings, self.went.append)
        self.addCleanup(self.page.shutdown)

    def test_cards_follow_the_entries_in_order(self):
        a, b, c = FakePage("a", "A"), FakePage("b", "B"), FakePage("c", "C")
        self.page.sync([(a, 0), (b, 1), (c, 2)])
        self.assertEqual(self.page.order(), ["a", "b", "c"])
        self.page.sync([(c, 2), (a, 0), (b, 1)])            # the user reordered
        self.assertEqual(self.page.order(), ["c", "a", "b"])
        self.page.sync([(c, 2), (a, 0)])                    # b unplugged
        self.assertEqual(self.page.order(), ["c", "a"])
        self.assertNotIn("b", self.page.cards)

    def test_card_color_is_the_entrys(self):
        a = FakePage("a")
        self.page.sync([(a, 3)])
        self.assertEqual(self.page.cards["a"].graph.entry_index, 3)
        self.page.sync([(a, 5)])
        self.assertEqual(self.page.cards["a"].graph.entry_index, 5)

    def test_card_shows_usage_and_follows_updates(self):
        a = FakePage("a", "Drive A", usage=10.0)
        self.page.sync([(a, 0)])
        card = self.page.cards["a"]
        self.assertEqual(card.title_label.get_label(), "Drive A")
        self.assertEqual(card.usage_label.get_label(), "10 %")
        self.assertEqual(card.detail_label.get_label(), "1 of 2 GB · a model")
        self.assertTrue(card.graph.get_visible())
        self.assertEqual(card.graph.series, a.series)
        a.set_usage(55.0)
        self.assertEqual(card.usage_label.get_label(), "55 %")

    def test_a_device_without_readings_says_no_data(self):
        a = FakePage("a", usage=None)
        self.page.sync([(a, 0)])
        card = self.page.cards["a"]
        self.assertFalse(card.graph.get_visible())          # not an empty frame
        self.assertTrue(card.empty_label.get_visible())
        a.set_usage(0.0)                                    # its first reading
        self.assertTrue(card.graph.get_visible())
        self.assertFalse(card.empty_label.get_visible())

    def test_pages_without_a_summary_get_no_card(self):
        self.page.sync([(FakePage("ph", summary=False), 0), (FakePage("a"), 1)])
        self.assertEqual(self.page.order(), ["a"])

    def test_empty_state(self):
        self.page.sync([])
        self.assertTrue(self.page.empty.get_visible())
        self.page.sync([(FakePage("a"), 0)])
        self.assertFalse(self.page.empty.get_visible())

    def test_clicking_a_card_opens_its_page(self):
        a = FakePage("a")
        self.page.sync([(a, 0)])
        self.page.flow.emit("child-activated", self.page.cards["a"].get_parent())
        self.assertEqual(self.went, ["a"])

    def test_replaced_page_and_shutdown_disconnect(self):
        old, new = FakePage("a", "Old"), FakePage("a", "New")
        self.page.sync([(old, 0)])
        card = self.page.cards["a"]
        self.page.sync([(new, 0)])                          # swapped in place
        self.assertIs(self.page.cards["a"], card)
        self.assertEqual(card.title_label.get_label(), "New")
        old.set_usage(99.0)                                 # no longer followed
        self.assertNotEqual(card.usage_label.get_label(), "99 %")
        self.page.shutdown()
        new.set_usage(77.0)
        self.assertNotEqual(card.usage_label.get_label(), "77 %")

    def test_axes_follow_settings(self):
        self.page.sync([(FakePage("a"), 0)])
        graph = self.page.cards["a"].graph
        self.assertTrue(graph.show_axes)
        self.settings.set("show-graph-axes", False)
        self.assertFalse(graph.show_axes)
        self.settings.set("update-interval", "2-seconds")
        self.assertEqual(graph.time_span_s, 60.0)      # the time range holds
        self.settings.set("graph-time-range", "2-minutes")
        self.assertEqual(graph.time_span_s, 120.0)

    def test_overview_is_a_pinned_uncharted_page(self):
        from proccoli import OVERVIEW_ICON
        self.assertEqual(self.page.kind, PageKind.OVERVIEW)
        self.assertEqual(self.page.icon_name, OVERVIEW_ICON)
        self.assertIsNone(self.page.sidebar_summary())


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class OverviewWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def make(self):
        from helpers import make_context
        from proccoli.ui.window import MainWindow
        self.settings = Settings.for_tests()
        ctx = make_context(self, settings=self.settings)
        ctx.start()
        ctx.devices.refresh(1.0)
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        return win

    def test_one_card_per_charted_entry_in_sidebar_order_and_color(self):
        win = self.make()
        overview = win.page("overview")
        charted = [i for i in win.sidebar.order() if i not in ("overview", "apps", "processes")]
        self.assertEqual(overview.order(), charted)
        for page_id in charted:
            self.assertEqual(overview.cards[page_id].graph.entry_index,
                             win.sidebar.items[page_id].meter.graph.entry_index)
        self.assertIs(overview.cards["cpu"].page, win.page("cpu"))

    def test_moving_an_entry_moves_its_card(self):
        win = self.make()
        overview = win.page("overview")
        win.sidebar.move("memory", -1)                      # above Processor
        self.assertLess(overview.order().index("memory"), overview.order().index("cpu"))
        self.assertEqual(overview.cards["memory"].graph.entry_index,
                         win.sidebar.items["memory"].meter.graph.entry_index)

    def test_overview_is_pinned_first_and_has_no_preferences_entry(self):
        win = self.make()
        self.assertEqual(win.sidebar.order()[0], "overview")
        self.assertIn("overview", win.sidebar.pinned_ids())
        self.assertFalse(win.sidebar.items["overview"].movable)
        win.sidebar.move("cpu", -10)                        # can't go above it
        self.assertEqual(win.sidebar.order()[:3], ["overview", "apps", "processes"])
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        prefs = PreferencesDialog(self.settings, sidebar=win.sidebar)
        self.assertNotIn("overview", prefs.entry_rows)
        self.assertIn("cpu", prefs.entry_rows)

    def test_removed_device_loses_its_card(self):
        win = self.make()
        overview = win.page("overview")
        net = next(i for i in overview.order() if i.startswith("net-"))
        win.remove_page(net)
        self.assertNotIn(net, overview.cards)

    def test_card_opens_the_page(self):
        win = self.make()
        overview = win.page("overview")
        overview.flow.emit("child-activated", overview.cards["memory"].get_parent())
        self.assertEqual(win.visible_page_id(), "memory")
        self.assertEqual(win.sidebar.selected_id(), "memory")

    def test_cards_update_on_tick(self):
        win = self.make()
        overview = win.page("overview")
        win.ctx.devices.refresh(2.0)
        pump(timeout=0.2)
        summary = win.page("memory").sidebar_summary()
        card = overview.cards["memory"]
        self.assertEqual(card.usage_label.get_label(), summary.usage_text)
        self.assertIn("%", card.usage_label.get_label())
        self.assertEqual(card.graph.series, summary.series)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GridFillsThePageTest(unittest.TestCase):
    """The cards form an N × M grid that tries to fill
    the page, each chart shorter than wide.

    The headless display is at most 1024 × 768, so "portrait" here is a
    narrow window of full height."""

    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    # -- helpers ------------------------------------------------------------------

    def standalone(self, count, width, height):
        """An Overview of ``count`` fake entries, alone in a window."""
        page = OverviewPage(Settings.for_tests(), lambda _id: None)
        self.addCleanup(page.shutdown)
        page.sync([(FakePage(f"p{i}", f"Page {i}"), i) for i in range(count)])
        win = Gtk.Window(child=page, default_width=width, default_height=height)
        self.addCleanup(win.destroy)
        win.present()
        self.settle(page)
        return win, page

    def in_window(self, width, height):
        """The real window's Overview, with its tables."""
        from helpers import make_context
        from proccoli.ui.window import MainWindow
        # The geometry below is measured without the graph toolbar's row
        # (WindowToolbarTest checks the page gets that room back).
        ctx = make_context(self, settings=Settings.for_tests({"show-toolbar": False}))
        ctx.start()
        ctx.devices.refresh(1.0)
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        win.set_default_size(width, height)
        win.select_page("overview")
        win.present()
        self.settle(win.page("overview"))
        return win, win.page("overview")

    def resize(self, win, width, height):
        page = win.get_child() if isinstance(win.get_child(), OverviewPage) \
            else win.page("overview")
        before = page.viewport_size()
        from helpers import resize_or_skip
        resize_or_skip(self, win, width, height)
        self.assertTrue(pump(lambda: page.viewport_size() != before, timeout=5.0))
        self.settle(page)

    def settle(self, page):
        """Wait until the last fit is laid out (headless frames are slow)."""
        def done():
            if page._fit_source or page.fit_key() != page._fitted_for:
                return False
            rows, _ = self.grid(page, check=False)
            return (len(rows) == page.plan.rows
                    and all(c.graph.get_height() == c.graph.get_content_height()
                            for c in page.cards.values() if c.graph.get_visible()))
        self.assertTrue(pump(done, timeout=5.0), "the Overview never settled")

    def grid(self, page, check=True):
        """``(card page IDs per row, by top edge; the grid's bottom)``, in
        the column's coordinates."""
        tops, bottom = {}, 0.0
        for page_id, card in page.cards.items():
            ok, b = card.cell().compute_bounds(page.box)
            if check:
                self.assertTrue(ok)
            tops.setdefault(round(b.get_y()), []).append(page_id)
            bottom = max(bottom, b.get_y() + b.get_height())
        return [tops[y] for y in sorted(tops)], bottom

    def assertFills(self, page, with_tables):
        rows, bottom = self.grid(page)
        area = page.grid_area(page.scroller.get_height(), with_tables)
        slack = 3 * len(rows)                           # rounding and hysteresis
        self.assertLessEqual(bottom, area + slack)
        self.assertGreaterEqual(bottom, area - slack)
        self.assertEqual(len(rows), page.plan.rows)
        self.assertEqual(max(len(r) for r in rows), page.plan.columns)

    # -- tests ----------------------------------------------------------------------

    def test_portrait_window_fills_the_height(self):
        win, page = self.standalone(2, 480, 768)
        self.assertEqual((page.plan.columns, page.plan.rows), (1, 2))
        self.assertFills(page, with_tables=False)
        for card in page.cards.values():
            # Before, the chart's height was 0.4 × its width, at most 240 px.
            self.assertGreater(card.graph.get_content_height(),
                               0.4 * card.graph.get_width() + 50)

    def test_wide_window_uses_columns(self):
        win, page = self.standalone(4, 1024, 520)
        self.assertEqual((page.plan.columns, page.plan.rows), (2, 2))
        self.assertEqual(page.flow.get_max_children_per_line(), page.plan.columns)
        self.assertEqual(page.flow.get_min_children_per_line(), 1)   # can still narrow
        self.assertFills(page, with_tables=False)

    def test_resizing_refits(self):
        win, page = self.standalone(4, 480, 768)
        tall = (page.plan.columns, page.plan.chart_height)
        self.resize(win, 1024, 520)
        self.assertNotEqual((page.plan.columns, page.plan.chart_height), tall)
        self.assertFills(page, with_tables=False)
        self.resize(win, 480, 768)
        self.assertEqual(page.plan.columns, tall[0])
        self.assertAlmostEqual(page.plan.chart_height, tall[1], delta=3)
        self.assertFills(page, with_tables=False)

    def test_cards_come_and_go(self):
        win, page = self.standalone(2, 480, 768)
        two = page.plan.chart_height
        page.sync([(FakePage(f"p{i}", f"Page {i}"), i) for i in range(3)])
        pump(timeout=0.3)
        self.settle(page)
        self.assertLess(page.plan.chart_height, two)
        self.assertFills(page, with_tables=False)

    def test_every_card_has_the_planned_height(self):
        win, page = self.standalone(5, 1000, 700)
        heights = {c.graph.get_content_height() for c in page.cards.values()}
        self.assertEqual(len(heights), 1)
        self.assertAlmostEqual(heights.pop(), page.plan.chart_height, delta=2)

    def assertShorterThanWide(self, page):
        for card in page.cards.values():
            if card.graph.get_visible():
                self.assertLess(card.graph.get_height(), card.graph.get_width(),
                                card.page_id)

    def test_charts_are_shorter_than_wide(self):
        # at portrait, landscape and in-between sizes.
        for count, width, height in ((1, 480, 768), (2, 480, 768), (2, 1024, 768),
                                     (3, 700, 768), (4, 1024, 520), (6, 1024, 768)):
            with self.subTest(count=count, width=width, height=height):
                win, page = self.standalone(count, width, height)
                self.assertShorterThanWide(page)
                win.destroy()

    def test_one_card_on_a_portrait_window_stops_short(self):
        win, page = self.standalone(1, 480, 768)
        graph = page.cards["p0"].graph
        self.assertEqual(graph.get_height(), graph.get_width() - 1)   # as tall as allowed
        rows, bottom = self.grid(page)
        self.assertLess(bottom, page.grid_area(page.scroller.get_height(), False) - 100)
        ok, b = page.cards["p0"].cell().compute_bounds(page.box)
        self.assertEqual(b.get_y(), 0)                                # at the top
        adj = page.scroller.get_vadjustment()
        self.assertLessEqual(adj.get_upper(), adj.get_page_size())    # no scrolling

    def test_real_window_charts_are_shorter_than_wide(self):
        win, page = self.in_window(1024, 768)
        self.assertShorterThanWide(page)
        self.resize(win, 600, 768)                    # sidebar folds away: narrow
        self.assertShorterThanWide(page)

    def test_tables_keep_their_room_below_the_grid(self):
        win, page = self.in_window(1024, 768)
        self.assertIsNotNone(page.tops)
        self.assertGreater(page.plan.chart_height, GRID_MIN_CHART)
        self.assertFills(page, with_tables=True)
        ok, b = page.tops.compute_bounds(page.box)
        self.assertTrue(ok)
        bottom = (page.box.get_margin_top() + b.get_y() + b.get_height()
                  + page.box.get_margin_bottom())
        self.assertAlmostEqual(bottom, page.scroller.get_height(), delta=3 * page.plan.rows)

    def test_cramped_window_puts_the_tables_below_the_fold(self):
        win, page = self.in_window(1024, 620)
        # With the tables on screen the charts would be under the minimum ...
        with_tables = page.grid_area(page.scroller.get_height(), with_tables=True)
        self.assertLess((with_tables - 2 * CARD_SPACING) / 3 - page._chrome(300),
                        GRID_MIN_CHART)
        # ... so the cards take the page.
        self.assertGreater(page.plan.chart_height, GRID_MIN_CHART)
        self.assertFills(page, with_tables=False)
        adj = page.scroller.get_vadjustment()
        self.assertGreater(adj.get_upper(), adj.get_page_size() + 50)   # tables scroll in


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class CardFactsTest(unittest.TestCase):
    """processor and GPU cards show their current readings."""

    def test_readings_line(self):
        page = FakePage("gpu", "GPU", facts=["Temperature 39 °C",
                                              "Memory 598.7 MB / 8.5 GB"])
        card = OverviewCard(page, 0, None)
        self.assertTrue(card.facts_label.get_visible())
        self.assertEqual(card.facts_label.get_label(),
                         "Temperature 39 °C · Memory 598.7 MB / 8.5 GB")
        page.facts = []                                    # e.g. no sensor
        card.update()
        self.assertFalse(card.facts_label.get_visible())
        card.shutdown()

    def test_no_line_without_readings(self):
        card = OverviewCard(FakePage("sda"), 0, None)
        self.assertFalse(card.facts_label.get_visible())
        card.shutdown()


if __name__ == "__main__":
    unittest.main()
