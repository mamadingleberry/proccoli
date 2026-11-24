"""Milestone 1: pages, sidebar and the main window shell.

Runs only on the private headless display (``make ui-test``); a plain
``make test`` skips the display-dependent tests."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.ui.page import PageKind, sidebar_rank  # noqa: E402

# Only on the private headless display (tests/run-headless.sh sets this),
# never on the desktop, where these tests would open real windows.
HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
    from proccoli.ui.page import (PageContainer, PlaceholderPage, ScrollingPage,
                                 SidebarSummary)
    from proccoli.ui.sidebar import StackSidebar
    from proccoli.ui.window import MainWindow


def pump(until=lambda: False, timeout=2.0):
    """Run the main loop until ``until()`` is true or ``timeout`` passes."""
    ctx = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while ctx.pending():
            ctx.iteration(False)
        if until():
            return True
        time.sleep(0.01)
    return until()


class SidebarRankTest(unittest.TestCase):
    def test_kinds_sort_in_resources_order(self):
        kinds = [PageKind.BATTERY, PageKind.GPU, PageKind.APPS, PageKind.NETWORK,
                 PageKind.MEMORY, PageKind.DRIVE, PageKind.PROCESSES, PageKind.CPU,
                 PageKind.OVERVIEW]
        ordered = sorted(kinds, key=sidebar_rank)
        self.assertEqual(ordered, [PageKind.OVERVIEW, PageKind.APPS, PageKind.PROCESSES, PageKind.CPU,
                                   PageKind.MEMORY, PageKind.GPU, PageKind.DRIVE,
                                   PageKind.NETWORK, PageKind.BATTERY])

    def test_name_orders_within_a_kind(self):
        self.assertLess(sidebar_rank("drive", "nvme0n1"), sidebar_rank("drive", "sda"))
        self.assertLess(sidebar_rank("gpu", "zzz"), sidebar_rank("drive", "aaa"))


if HAVE_DISPLAY:
    class FakeDevicePage(ScrollingPage):
        def __init__(self, page_id="dev", title="Device", usage=None, kind=PageKind.DRIVE,
                     buttons=()):
            super().__init__(page_id, kind, title, "drive-harddisk-symbolic",
                             description="sda", sort_name=page_id)
            self.usage = usage
            self.buttons = list(buttons)
            self.shut_down = False

        def sidebar_summary(self):
            return SidebarSummary(self.usage, detail="1 of 2 GB") \
                if self.usage is not None else None

        def header_widgets(self):
            return self.buttons

        def shutdown(self):
            self.shut_down = True
            super().shutdown()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class PageTest(unittest.TestCase):
    def test_scrolling_page_groups(self):
        page = FakeDevicePage()
        group = page.add_group("Usage", "desc")
        self.assertIsInstance(group, Adw.PreferencesGroup)
        self.assertEqual(group.get_title(), "Usage")

    def test_track_and_shutdown(self):
        settings = Settings.for_tests()
        page = FakeDevicePage()
        seen = []
        page.track(settings, settings.connect_changed("base", lambda *_: seen.append(1)))
        settings.set("base", "binary")
        page.shutdown()
        settings.set("base", "decimal")
        self.assertEqual(seen, [1])

    def test_container_title_and_header_buttons(self):
        b1 = Gtk.Button(label="one")
        page = FakeDevicePage(title="Drive", buttons=[b1])
        c = PageContainer(page)
        self.assertEqual(c.window_title.get_title(), "Drive")
        self.assertEqual(c.window_title.get_subtitle(), "sda")
        self.assertIs(b1.get_ancestor(Adw.HeaderBar), c.header)
        b2 = Gtk.Button(label="two")
        c.set_page(FakeDevicePage(title="Drive 2", buttons=[b2]))
        self.assertIsNone(b1.get_parent())
        self.assertIs(b2.get_ancestor(Adw.HeaderBar), c.header)
        self.assertEqual(c.window_title.get_title(), "Drive 2")
        with self.assertRaises(ValueError):
            c.set_page(FakeDevicePage(page_id="other"))

    def test_corner_controls_hidden_without_split_view(self):
        self.assertFalse(PageContainer(FakeDevicePage()).start_controls.get_visible())


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class SidebarTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings.for_tests()
        self.sidebar = StackSidebar(self.settings)
        self.stack = Gtk.Stack()
        self.sidebar.bind_stack(self.stack)
        for page in (FakeDevicePage("sdb", usage=10.0), FakeDevicePage("cpu-x", kind=PageKind.CPU),
                     FakeDevicePage("sda", usage=50.0)):
            self.stack.add_named(Gtk.Label(), page.page_id)
            self.sidebar.add_item(page)

    def test_rows_are_sorted(self):
        self.assertEqual(self.sidebar.order(), ["cpu-x", "sda", "sdb"])

    def test_duplicate_page_is_rejected(self):
        with self.assertRaises(ValueError):
            self.sidebar.add_item(FakeDevicePage("sda"))

    def test_selection_follows_both_ways(self):
        selected = []
        self.sidebar.connect("page-selected", lambda _s, pid: selected.append(pid))
        self.sidebar.select("sdb")
        self.assertEqual(self.stack.get_visible_child_name(), "sdb")
        self.assertEqual(selected, ["sdb"])
        self.stack.set_visible_child_name("cpu-x")
        self.assertEqual(self.sidebar.selected_id(), "cpu-x")

    def test_item_shows_summary(self):
        item = self.sidebar.items["sda"]
        self.assertEqual(item.usage_label.get_label(), "50 % · 1 of 2 GB")
        self.assertAlmostEqual(item.meter.progress.get_fraction(), 0.5)
        self.assertTrue(item.meter.get_visible())
        no_summary = self.sidebar.items["cpu-x"]
        self.assertFalse(no_summary.meter.get_visible())
        self.assertFalse(no_summary.usage_label.get_visible())

    def test_summary_changed_updates_item(self):
        page = self.sidebar.items["sda"].page
        page.usage = 75.0
        page.summary_changed()
        self.assertTrue(self.sidebar.items["sda"].usage_label.get_label().startswith("75 %"))

    def test_settings_restyle_items(self):
        item = self.sidebar.items["sda"]
        self.settings.set("sidebar-details", False)
        self.assertFalse(item.usage_label.get_visible())
        self.assertFalse(item.meter.get_visible())
        self.settings.set("sidebar-description", False)
        self.assertFalse(item.detail_label.get_visible())
        self.settings.set("sidebar-details", True)
        self.assertEqual(item.meter.meter_type.value, "graph")      # the default
        self.settings.set("sidebar-meter-type", "progress-bar")
        self.assertEqual(item.meter.meter_type.value, "progress-bar")

    def test_replace_and_remove(self):
        self.sidebar.replace_page(FakeDevicePage("sda", title="Renamed", usage=5.0))
        self.assertEqual(self.sidebar.items["sda"].label.get_label(), "Renamed")
        self.sidebar.remove_item("sdb")
        self.assertEqual(self.sidebar.order(), ["cpu-x", "sda"])


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class SidebarArrangeTest(unittest.TestCase):
    """Milestone 28: reorder and minimise; Apps and Processes stay on top."""

    def make(self, settings=None):
        self.settings = settings or Settings.for_tests()
        sidebar = StackSidebar(self.settings)
        for page in (FakeDevicePage("apps", kind=PageKind.APPS),
                     FakeDevicePage("processes", kind=PageKind.PROCESSES),
                     FakeDevicePage("cpu", kind=PageKind.CPU),
                     FakeDevicePage("memory", kind=PageKind.MEMORY),
                     FakeDevicePage("sda", usage=10.0), FakeDevicePage("sdb", usage=20.0)):
            sidebar.add_item(page)
        return sidebar

    def test_move_persist_and_restore(self):
        sidebar = self.make()
        sidebar.move("sdb", -3)
        self.assertEqual(sidebar.order(), ["apps", "processes", "sdb", "cpu", "memory", "sda"])
        self.assertEqual(self.settings.get("sidebar-order"), ["sdb", "cpu", "memory", "sda"])
        again = self.make(self.settings)                     # next start
        self.assertEqual(again.order(), sidebar.order())

    def test_pinned_entries_stay_on_top(self):
        sidebar = self.make()
        sidebar.move("cpu", -5)
        sidebar.move("apps", 4)
        self.assertEqual(sidebar.order()[:3], ["apps", "processes", "cpu"])
        self.assertFalse(sidebar.items["apps"].movable)
        self.assertFalse(sidebar.items["apps"].minimize_button.get_visible())
        self.assertIsNone(sidebar.popup_menu(sidebar.items["processes"]))
        self.assertFalse(sidebar._on_drop("apps", "sdb"))    # can't drag them either
        sidebar.set_minimized("apps", True)
        self.assertNotIn("apps", self.settings.get("sidebar-minimized"))

    def test_minimize_hides_details_and_persists(self):
        sidebar = self.make()
        item = sidebar.items["sda"]
        self.assertTrue(item.minimize_button.get_visible())
        item.minimize_button.emit("clicked")
        self.assertTrue(item.minimized)
        self.assertFalse(item.details.get_visible())          # description, usage, chart
        self.assertTrue(item.label.get_visible())             # icon and name stay
        self.assertEqual(self.settings.get("sidebar-minimized"), ["sda"])
        self.assertTrue(self.make(self.settings).items["sda"].minimized)
        item.minimize_button.emit("clicked")
        self.assertTrue(item.details.get_visible())

    def test_icons_only_shows_just_the_icon_with_hover_text(self):
        # Milestone 54: the compact style, for every row (pinned ones too).
        sidebar = self.make()
        sidebar.set_compact(True)
        for page_id, item in sidebar.items.items():
            self.assertTrue(item.image.get_visible())
            self.assertFalse(item.label.get_visible(), page_id)
            self.assertFalse(item.details.get_visible(), page_id)
            self.assertFalse(item.minimize_button.get_visible(), page_id)
            self.assertEqual(item.get_tooltip_text().split("\n")[0], item.page.title)
        self.assertIn("10", sidebar.items["sda"].get_tooltip_text())   # its usage line
        added = FakeDevicePage("sdc", usage=30.0)
        sidebar.add_item(added)                                # later rows follow
        self.assertTrue(sidebar.items["sdc"].compact)
        sidebar.set_compact(False)
        item = sidebar.items["sda"]
        self.assertTrue(item.label.get_visible())
        self.assertTrue(item.details.get_visible())
        self.assertTrue(item.minimize_button.get_visible())
        self.assertIsNone(item.get_tooltip_text())

    def test_icons_only_keeps_the_entries_own_choices(self):
        sidebar = self.make()
        sidebar.set_minimized("sda", True)
        sidebar.set_compact(True)
        sidebar.set_compact(False)
        self.assertTrue(sidebar.items["sda"].minimized)        # still minimised
        self.assertFalse(sidebar.items["sda"].details.get_visible())

    def test_row_menu(self):
        sidebar = self.make()

        def labels(page_id):
            menu = sidebar.row_menu(page_id)
            return [menu.get_item_link(s, "section").get_item_attribute_value(
                        i, "label").get_string()
                    for s in range(menu.get_n_items())
                    for i in range(menu.get_item_link(s, "section").get_n_items())]
        show = ["Show Name", "Show Description", "Show Usage Details", "Show Chart"]
        self.assertEqual(labels("cpu"), ["Move Down", "Minimize"] + show + ["Reset Order"])
        self.assertEqual(labels("memory"),
                         ["Move Up", "Move Down", "Minimize"] + show + ["Reset Order"])
        self.assertEqual(labels("sdb"), ["Move Up", "Minimize"] + show + ["Reset Order"])
        sidebar.actions.activate_action("move-up", GLib.Variant.new_string("sdb"))
        self.assertEqual(sidebar.order()[-1], "sda")
        sidebar.actions.activate_action("toggle-minimized", GLib.Variant.new_string("cpu"))
        self.assertIn("Expand", labels("cpu"))
        sidebar.actions.activate_action("reset", None)
        self.assertEqual(sidebar.order(), ["apps", "processes", "cpu", "memory", "sda", "sdb"])
        self.assertFalse(sidebar.items["cpu"].minimized)
        self.assertIsNotNone(sidebar.popup_menu(sidebar.items["memory"]))

    def test_hide_and_show_parts_per_entry(self):
        from proccoli.ui.sidebar_fields import Field
        sidebar = self.make()
        sda, sdb = sidebar.items["sda"], sidebar.items["sdb"]
        sidebar.set_field_shown("sda", Field.CHART, False)
        sidebar.set_field_shown("sda", Field.DESCRIPTION, False)
        self.assertFalse(sda.meter.get_visible())
        self.assertFalse(sda.detail_label.get_visible())
        self.assertTrue(sda.usage_label.get_visible())
        self.assertTrue(sdb.meter.get_visible())                    # other entries unchanged
        self.assertEqual(self.settings.get("sidebar-hidden-fields"),
                         {"sda": ["chart", "description"]})
        again = self.make(self.settings)                            # next start
        self.assertFalse(again.items["sda"].meter.get_visible())
        sidebar.set_field_shown("sda", Field.USAGE, False)
        self.assertFalse(sda.details.get_visible())                 # nothing left under it
        sidebar.set_field_shown("sda", Field.NAME, False)
        self.assertFalse(sda.label.get_visible())
        self.assertTrue(sda.image.get_visible())                    # the icon always stays
        sidebar.reset_order()
        self.assertEqual(self.settings.get("sidebar-hidden-fields"), {})
        self.assertTrue(sda.meter.get_visible() and sda.label.get_visible())

    def test_menu_check_items_toggle_parts(self):
        sidebar = self.make()
        actions = sidebar.row_actions("memory")
        self.assertTrue(actions.get_action_state("show-chart").get_boolean())
        actions.change_action_state("show-chart", GLib.Variant.new_boolean(False))
        self.assertFalse(sidebar.items["memory"].meter.get_visible())
        self.assertFalse(sidebar.row_actions("memory").get_action_state(
            "show-chart").get_boolean())

    def test_pinned_entries_always_show_everything(self):
        sidebar = self.make()
        self.settings.set("sidebar-hidden-fields", {"apps": ["name"]})
        self.assertTrue(sidebar.items["apps"].label.get_visible())

    def test_global_preferences_still_apply(self):
        sidebar = self.make()
        self.settings.set("sidebar-description", False)
        self.assertFalse(sidebar.items["sda"].detail_label.get_visible())
        self.settings.set("sidebar-details", False)
        self.assertFalse(sidebar.items["sda"].meter.get_visible())
        self.assertTrue(sidebar.items["sda"].label.get_visible())

    def test_drag_and_drop(self):
        sidebar = self.make()
        self.assertTrue(sidebar._on_drop("sdb", "cpu"))
        self.assertEqual(sidebar.order()[2:4], ["sdb", "cpu"])
        self.assertFalse(sidebar._on_drop("nope", "cpu"))

    def test_moving_keeps_each_entrys_colour(self):
        sidebar = self.make()
        before = {i: sidebar.items[i].meter.graph.entry_index for i in ("cpu", "sda", "sdb")}
        sidebar.move("sdb", -3)
        after = {i: sidebar.items[i].meter.graph.entry_index for i in ("cpu", "sda", "sdb")}
        self.assertEqual(before, after)

    def test_without_settings(self):
        sidebar = StackSidebar()
        for page in (FakeDevicePage("a", kind=PageKind.CPU), FakeDevicePage("b", usage=1.0)):
            sidebar.add_item(page)
        sidebar.move("b", -1)
        self.assertEqual(sidebar.order(), ["b", "a"])
        sidebar.set_minimized("a", True)
        self.assertTrue(sidebar.items["a"].minimized)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class WindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def make(self, demo=True, **overrides):
        from helpers import make_context
        self.settings = Settings.for_tests(overrides)
        ctx = make_context(self, demo=True, settings=self.settings)
        self.ticker = ctx.ticker
        if demo:
            ctx.start()
        else:
            ctx.devices = None            # no providers: placeholders only
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        return win

    def test_injected_theme_is_used(self):
        from helpers import FakeStyleManager, make_context
        from proccoli.ui.theme import Theme
        settings = Settings.for_tests({"color-scheme": "dark"})
        ctx = make_context(self, demo=True, settings=settings)
        sm = FakeStyleManager()
        ctx.theme = Theme(settings, sm)
        self.addCleanup(ctx.theme.shutdown)
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        self.assertIs(win.theme, ctx.theme)
        self.assertTrue(sm.get_dark())

    def test_charts_for_devices_but_not_for_apps_and_processes(self):
        from helpers import make_context
        from proccoli.devices.base import DeviceKind
        ctx = make_context(self, settings=Settings.for_tests())
        ctx.start()
        ctx.devices.refresh(1.0)
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        for page_id, item in win.sidebar.items.items():
            has_chart = item.meter.get_visible() and item.meter.meter_type.value == "graph"
            self.assertEqual(has_chart, page_id not in ("overview", "apps", "processes"), page_id)
        self.assertTrue(ctx.devices.monitors(DeviceKind.NETWORK))

    def test_every_sidebar_entry_has_its_own_icon(self):
        from helpers import make_context
        from proccoli import GPU_ICON, MEMORY_ICON, PROCESSOR_ICON
        from proccoli.ui.sidebar import ICON_SIZE, ICON_SPACING
        from proccoli.ui.style import add_source_icons
        add_source_icons()                       # data/icons, as the app does
        ctx = make_context(self, settings=Settings.for_tests())
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        icons = {pid: item.image.get_icon_name() for pid, item in win.sidebar.items.items()}
        self.assertEqual(icons["cpu"], PROCESSOR_ICON)
        self.assertEqual(icons["memory"], MEMORY_ICON)
        self.assertEqual(icons["gpu-0000:00:02.0"], GPU_ICON)
        self.assertEqual(icons["drive-sda"], "drive-harddisk-solidstate-symbolic")
        self.assertEqual(icons["net-eno1"], "network-wired-symbolic")
        self.assertEqual(icons["net-wlp43s0"], "network-wireless-symbolic")
        self.assertEqual(icons["apps"], "view-app-grid-symbolic")
        self.assertEqual(icons["processes"], "view-list-bullet-symbolic")
        self.assertEqual(len(set(icons.values())), len(icons))       # all different
        theme = Gtk.IconTheme.get_for_display(win.get_display())
        for pid, name in icons.items():
            self.assertTrue(theme.has_icon(name), (pid, name))
        item = win.sidebar.items["cpu"]
        self.assertEqual(item.image.get_pixel_size(), ICON_SIZE)
        self.assertEqual(item.details.get_margin_start(), ICON_SIZE + ICON_SPACING)

    def test_each_chart_entry_has_its_own_colour(self):
        from helpers import FakeStyleManager, make_context
        from proccoli.core.palette import hex_to_rgb
        from proccoli.ui.theme import Theme
        settings = Settings.for_tests({"palette": "tango"})
        ctx = make_context(self, settings=settings)
        ctx.theme = Theme(settings, FakeStyleManager())
        self.addCleanup(ctx.theme.shutdown)
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        charted = [i for i in win.sidebar.order() if i not in ("overview", "apps", "processes")]
        indexes = [win.sidebar.items[i].meter.graph.entry_index for i in charted]
        self.assertEqual(indexes, list(range(len(charted))))           # display order
        self.assertIsNone(win.sidebar.items["apps"].meter.graph.entry_index)
        colors = [win.sidebar.items[i].meter.graph.color_for(0) for i in charted]
        self.assertEqual(len(set(colors)), len(colors))                 # all distinct
        self.assertEqual(colors[0], hex_to_rgb("#3465a4"))
        cpu = win.sidebar.items["cpu"].meter
        self.assertIn("entry-color-0", cpu.progress.get_css_classes())
        memory = win.page("memory")                       # the page matches its entry
        self.assertEqual(memory.memory.graph.color_for(0), colors[charted.index("memory")])
        self.assertNotEqual(memory.swap.graph.color_for(0), memory.memory.graph.color_for(0))
        net = win.sidebar.items["net-eno1"].meter.graph
        self.assertNotEqual(net.color_for(0), net.color_for(1))         # send: a shade
        settings.set("palette", "nord")
        self.assertEqual(win.sidebar.items["cpu"].meter.graph.color_for(0),
                         hex_to_rgb("#5e81ac"))

    def test_theme_changes_redraw_every_graph(self):
        from proccoli.ui import window as window_module
        win = self.make()
        real = window_module.redraw_tree
        self.assertGreater(real(win), 3)             # sidebar meters and page graphs
        seen = []
        window_module.redraw_tree = lambda w: seen.append(w) or real(w)
        self.addCleanup(setattr, window_module, "redraw_tree", real)
        self.settings.set("palette", "xterm")
        self.assertIn(win, seen)

    def test_sidebar_order_and_default_page(self):
        win = self.make()
        self.assertEqual(win.sidebar.order(),
                         ["overview", "apps", "processes", "cpu", "memory", "gpu-demo",
                          "demo"])
        self.assertEqual(win.visible_page_id(), "overview")         # Milestone 39
        self.assertEqual(win.sidebar.selected_id(), "overview")

    def test_without_demo(self):
        win = self.make(demo=False)
        self.assertEqual(win.sidebar.order(), ["overview", "apps", "processes", "cpu", "memory"])

    def test_always_opens_on_the_overview(self):
        # M55: whatever was shown when the app closed.
        win = self.make()
        self.assertEqual(win.visible_page_id(), "overview")
        win.sidebar.select("cpu")
        again = self.make()
        self.assertEqual(again.visible_page_id(), "overview")
        self.assertEqual(again.sidebar.selected_id(), "overview")

    def test_show_overview_from_any_page(self):
        win = self.make()
        win.select_page("memory")
        win.show_overview()                      # what a second launch does
        self.assertEqual(win.visible_page_id(), "overview")

    def test_without_an_overview_the_first_entry(self):
        win = self.make()
        win.remove_page("overview")
        win.select_page("memory")
        win.show_overview()
        self.assertEqual(win.visible_page_id(), win.sidebar.order()[0])

    def test_replace_page_in_place(self):
        win = self.make()
        win.select_page("cpu")
        old = win.page("cpu")
        container = win.containers["cpu"]
        new = PlaceholderPage("cpu", PageKind.CPU, "Processor 2", "computer-symbolic")
        win.replace_page(new)
        self.assertIs(win.stack.get_child_by_name("cpu"), container)
        self.assertIs(win.page("cpu"), new)
        self.assertEqual(win.visible_page_id(), "cpu")
        self.assertEqual(win.sidebar.selected_id(), "cpu")
        self.assertEqual(win.sidebar.items["cpu"].label.get_label(), "Processor 2")
        self.assertEqual(old._connections, [])

    def test_remove_visible_page_selects_neighbour(self):
        win = self.make()
        page = FakeDevicePage("drive-sda", usage=1.0)
        win.add_page(page)
        win.select_page("drive-sda")
        win.remove_page("drive-sda")
        self.assertTrue(page.shut_down)
        self.assertEqual(win.visible_page_id(), "demo")      # next in order
        win.remove_page("demo")
        self.assertEqual(win.visible_page_id(), "gpu-demo")  # previous at the end

    def test_demo_updates_sidebar_on_tick(self):
        win = self.make()
        self.ticker.tick_now()
        item = win.sidebar.items["demo"]
        self.assertTrue(item.usage_label.get_label().split(" · ")[0].endswith("%"))
        self.assertGreater(item.meter.progress.get_fraction(), 0)

    def _sized(self, width, height):
        win = self.make()
        win.set_default_size(width, height)
        win.present()
        pump(lambda: win.get_width() == width, timeout=3)
        pump(timeout=0.2)  # let breakpoints settle
        return win

    def test_wide_window_shows_sidebar_beside_content(self):
        win = self._sized(1000, 700)
        self.assertFalse(win.split_view.get_collapsed())
        self.assertFalse(win.containers["apps"].start_controls.get_visible())

    def test_narrow_window_collapses(self):
        win = self._sized(700, 600)
        self.assertTrue(win.split_view.get_collapsed())
        self.assertTrue(win.containers["apps"].start_controls.get_visible())   # the logo (main menu)
        win.activate_action("win.toggle-sidebar", None)        # ≡ → Show Sidebar
        self.assertTrue(win.split_view.get_show_sidebar())    # the overlay opens
        self.assertTrue(win.get_action_state("toggle-sidebar").get_boolean())
        win.sidebar.select("cpu")                     # picking a page...
        self.assertFalse(win.split_view.get_show_sidebar())  # ...closes the overlay


if __name__ == "__main__":
    unittest.main()
