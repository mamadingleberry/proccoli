"""Apps and Processes pages (Milestones 10-11). Headless display only."""

import os
import signal
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import FakeRoot, FakeSystem, make_context  # noqa: E402
from test_processes import TERMINAL, add_proc  # noqa: E402
from test_ui_shell import pump  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.system import AppInfo  # noqa: E402
from proccoli.processes.actions import Action, ProcessActions  # noqa: E402
from proccoli.processes.apps import AppGrouper  # noqa: E402
from proccoli.processes.monitor import ProcessMonitor  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
    from proccoli.ui.pages.apps import AppsPage
    from proccoli.ui.pages.processes import ProcessesPage, nice_name
    from proccoli.ui.window import MainWindow


def setup_procs(test):
    root = FakeRoot(test, {"/proc/stat": "cpu 1\ncpu0 1\nbtime 0\n"})
    add_proc(root, 10, "firefox", utime=0, cgroup=TERMINAL, rss_kb=5000)
    add_proc(root, 20, "bash", utime=0, cgroup=TERMINAL, rss_kb=100)
    add_proc(root, 30, "systemd", utime=0, cgroup="/init.scope", rss_kb=50, nice=-10)
    settings = Settings.for_tests({"normalize-cpu-usage": False})
    monitor = ProcessMonitor(root.sysroot, settings, FakeSystem())
    monitor.refresh(1.0)
    add_proc(root, 10, "firefox", utime=80, cgroup=TERMINAL, rss_kb=5000)
    add_proc(root, 20, "bash", utime=10, cgroup=TERMINAL, rss_kb=100)
    monitor.refresh(2.0)
    return root, settings, monitor


def visible_order(page):
    return [page.sorted.get_item(i).key for i in range(page.sorted.get_n_items())]


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class AppIconTest(unittest.TestCase):
    def test_missing_or_unknown_icons_become_the_puzzle_piece(self):
        from proccoli import MISSING_APP_ICON
        from proccoli.ui.widgets.app_icon import set_app_icon
        image = Gtk.Image()
        set_app_icon(image, None)
        self.assertEqual(image.get_icon_name(), MISSING_APP_ICON)
        set_app_icon(image, Gio.ThemedIcon.new("no-such-icon-anywhere"))
        self.assertEqual(image.get_icon_name(), MISSING_APP_ICON)
        known = Gio.ThemedIcon.new("utilities-terminal-symbolic")
        set_app_icon(image, known)
        self.assertEqual(image.get_storage_type(), Gtk.ImageType.GICON)
        self.assertIs(image.get_gicon(), known)

    def test_processes_show_their_apps_icon(self):
        _, settings, monitor = setup_procs(self)
        icon = Gio.ThemedIcon.new("utilities-terminal-symbolic")
        grouper = AppGrouper(lambda i: AppInfo("Terminal", icon)
                             if i == "org.gnome.Terminal" else None)
        system = FakeSystem()
        page = ProcessesPage(monitor, settings, ProcessActions(system), system,
                             grouper=grouper)
        name = page.COLUMNS[0]
        self.assertIs(name.icon(monitor.processes[10]), icon)     # in the Terminal app
        self.assertIsNone(name.icon(monitor.processes[30]))      # systemd: puzzle piece
        bare = ProcessesPage(monitor, settings, ProcessActions(system), system)
        self.assertIsNone(bare.COLUMNS[0].icon(monitor.processes[10]))

    def test_apps_show_their_icon(self):
        _, settings, monitor = setup_procs(self)
        icon = Gio.ThemedIcon.new("utilities-terminal-symbolic")
        grouper = AppGrouper(lambda i: AppInfo("Terminal", icon)
                             if i == "org.gnome.Terminal" else None)
        page = AppsPage(monitor, settings, grouper, ProcessActions(FakeSystem()))
        name = page.COLUMNS[0]
        self.assertIs(name.icon(page.rows["org.gnome.Terminal"].data), icon)
        self.assertIsNone(name.icon(page.rows["system"].data))   # puzzle piece

    def test_window_gives_the_processes_page_the_grouper(self):
        ctx = make_context(self)
        app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        app.register(None)
        win = MainWindow(app, ctx)
        self.addCleanup(win.destroy)
        self.assertIs(win.page("processes").grouper, ctx.grouper)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class ContextMenuTest(unittest.TestCase):
    """Milestone 32: right-click menus; Switch To on Apps."""

    def apps_page(self, switchable=None):
        _, settings, self.monitor = setup_procs(self)
        icon = Gio.ThemedIcon.new("utilities-terminal-symbolic")
        grouper = AppGrouper(lambda i: AppInfo("Terminal", icon)
                             if i == "org.gnome.Terminal" else None)
        self.system = FakeSystem()
        self.system.switchable = switchable or {}
        return AppsPage(self.monitor, settings, grouper, ProcessActions(self.system),
                        self.system)

    def labels(self, menu):
        return [menu.get_item_link(s, "section").get_item_attribute_value(i, "label")
                .get_string()
                for s in range(menu.get_n_items())
                for i in range(menu.get_item_link(s, "section").get_n_items())]

    def select(self, page, key):
        pos = visible_order(page).index(key)
        page.select_position(pos)
        return pos

    def test_switch_to_a_dbus_app(self):
        page = self.apps_page({"org.gnome.Terminal": "dbus"})
        self.assertIsNone(page.popup_context_menu(page.view))      # nothing selected
        self.select(page, "org.gnome.Terminal")
        self.assertEqual(self.labels(page.context_menu()),
                         ["Switch To", "Information", "End App", "Kill App", "Halt App",
                          "Continue App"])
        page.action_group.activate_action("switch-to", None)
        self.assertEqual(self.system.activated, ["org.gnome.Terminal"])

    def test_unreachable_apps_offer_window_switching(self):
        # Idea 5: Switch To is there for every app; one Proccoli can't reach
        # says how to set up window switching instead.
        page = self.apps_page({})                                    # e.g. Firefox
        self.select(page, "org.gnome.Terminal")
        self.assertIn("Switch To", self.labels(page.context_menu()))
        page.switch_to()
        self.assertEqual(self.system.activated, [])
        self.assertIn("window switching", page.last_message)

    def test_the_extension_raises_any_app(self):
        page = self.apps_page({})
        key = "org.gnome.Terminal"
        pids = next(a for a in page.items().values() if a.id == key).pids
        self.system.windows = [(41, pids[0], key, "Terminal", 7)]
        self.select(page, key)
        page.switch_to()
        self.assertEqual(self.system.raised, [41])
        self.assertEqual(self.system.activated, [])

    def test_system_processes_and_multiple_rows_cant_switch(self):
        page = self.apps_page({"org.gnome.Terminal": "dbus", "system": "dbus"})
        self.select(page, "system")
        self.assertNotIn("Switch To", self.labels(page.context_menu()))
        page.selection.select_all()
        self.assertNotIn("Switch To", self.labels(page.context_menu()))

    def test_right_click_selects_the_row_and_keeps_a_selection(self):
        page = self.apps_page()
        first = self.select(page, "org.gnome.Terminal")
        self.assertTrue(page.selection.is_selected(first))
        page.selection.select_all()
        page.select_position(first)                                  # already selected
        self.assertEqual(len(page.selected()), 2)
        other = visible_order(page).index("system")
        page.selection.unselect_all()
        page.select_position(first)
        page.select_position(other)
        self.assertEqual([a.id for a in page.selected()], ["system"])  # only the new one

    def test_menu_actions_reach_the_processes(self):
        page = self.apps_page()
        self.select(page, "org.gnome.Terminal")
        page.action_group.activate_action("halt", None)
        self.assertEqual(sorted(p for p, _sig in self.system.killed), [10, 20])

    def test_processes_menu_has_options(self):
        _, settings, monitor = setup_procs(self)
        system = FakeSystem()
        page = ProcessesPage(monitor, settings, ProcessActions(system), system)
        page.select_position(0)
        self.assertEqual(self.labels(page.context_menu()),
                         ["Information", "Options", "End Process", "Kill Process",
                          "Halt Process", "Continue Process"])
        self.assertTrue(page.options_action.get_enabled())
        self.assertIsNotNone(page.popup_context_menu(page.view))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class ContextMenuPopupTest(unittest.TestCase):
    """The right-click menu froze the window on Wayland: the click is now
    claimed before the popup, and one popover hangs off a stable box
    instead of a recycled table cell."""

    class FakeGesture:
        def __init__(self):
            self.states = []

        def set_state(self, state):
            self.states.append(state)

    class FakeItem:
        def __init__(self, position):
            self.position = position

        def get_position(self):
            return self.position

    def setUp(self):
        _, settings, monitor = setup_procs(self)
        self.page = ProcessesPage(monitor, settings, ProcessActions(FakeSystem()), FakeSystem())
        self.addCleanup(self.page.shutdown)
        self.win = Gtk.Window(child=self.page, default_width=800, default_height=500)
        self.addCleanup(self.win.destroy)
        self.win.present()
        pump(timeout=0.5)

    def cell(self):
        """A real cell widget with the right-click gesture."""
        stack = [self.page.view]
        while stack:
            w = stack.pop()
            ctrls = w.observe_controllers()
            for i in range(ctrls.get_n_items()):
                c = ctrls.get_item(i)
                if isinstance(c, Gtk.GestureClick) and c.get_button() == 3:
                    return w
            child = w.get_first_child()
            while child is not None:
                stack.append(child)
                child = child.get_next_sibling()
        self.fail("no cell with a context menu")

    def test_click_is_claimed_before_the_menu_opens(self):
        gesture = self.FakeGesture()
        popover = self.page.open_cell_menu(gesture, self.FakeItem(1), self.cell(), 4, 4)
        self.assertEqual(gesture.states, [Gtk.EventSequenceState.CLAIMED])
        self.assertIsNotNone(popover)
        self.assertEqual(len(self.page.selected()), 1)
        self.assertEqual(self.page.selection.get_selection().get_nth(0), 1)

    def test_one_popover_on_a_stable_parent(self):
        cell = self.cell()
        first = self.page.open_cell_menu(self.FakeGesture(), self.FakeItem(0), cell, 4, 4)
        self.assertIs(first.get_parent(), self.page.menu_parent)
        self.assertTrue(first.get_visible())
        first.popdown()
        second = self.page.open_cell_menu(self.FakeGesture(), self.FakeItem(0), cell, 6, 6)
        self.assertIs(second, first)                                  # reused
        # Kept across table refreshes, which rebind the cells.
        self.page.monitor.emit("updated")
        pump(timeout=0.3)
        self.assertIs(second.get_parent(), self.page.menu_parent)

    def test_points_at_the_click_in_the_parents_coordinates(self):
        cell = self.cell()
        popover = self.page.open_cell_menu(self.FakeGesture(), self.FakeItem(0), cell, 4, 5)
        ok, rect = popover.get_pointing_to()
        expected = self.page.menu_point(cell, 4, 5)
        self.assertEqual((rect.x, rect.y), expected)
        ok, origin = cell.compute_point(self.page.menu_parent, __import__(
            "gi.repository.Graphene", fromlist=["Point"]).Point().init(0, 0))
        self.assertEqual(expected, (int(origin.x + 4), int(origin.y + 5)))

    def test_keyboard_menu_points_at_the_table(self):
        self.page.select_position(0)
        popover = self.page.popup_context_menu(self.page.view)
        self.assertIs(popover.get_parent(), self.page.menu_parent)

    def test_shutdown_removes_the_popover(self):
        popover = self.page.open_cell_menu(self.FakeGesture(), self.FakeItem(0), self.cell(), 1, 1)
        self.page.shutdown()
        self.assertIsNone(popover.get_parent())
        self.assertIsNone(self.page.context_popover)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class ProcessesPageTest(unittest.TestCase):
    def setUp(self):
        self.root, self.settings, self.monitor = setup_procs(self)
        self.system = FakeSystem()
        self.page = ProcessesPage(self.monitor, self.settings, ProcessActions(self.system),
                                  self.system, cpu_count=4)

    def test_rows_sorted_by_processor_descending(self):
        self.assertEqual(visible_order(self.page), [10, 20, 30])
        self.assertEqual(self.settings.get("processes-sort-by"), 4)  # the cpu column
        self.assertFalse(self.settings.get("processes-sort-by-ascending"))

    def test_update_keeps_row_objects(self):
        row = self.page.rows[10]
        self.root.remove("/proc/30")
        self.monitor.refresh(3.0)
        self.assertIs(self.page.rows[10], row)
        self.assertNotIn(30, self.page.rows)
        self.assertEqual(self.page.store.get_n_items(), 2)

    def test_reordering_reaches_the_view(self):
        """A refresh that changes the ranking re-sorts the model the view
        shows and tells it so (items-changed); GTK re-binds visible rows from
        that on the next frame."""
        model = self.page.view.get_model()          # what the ColumnView displays
        self.assertEqual(model.get_item(0).key, 10)  # firefox was busiest
        changes = []
        model.connect("items-changed", lambda *a: changes.append(a[1:]))
        add_proc(self.root, 20, "bash", utime=500, cgroup=TERMINAL)   # bash takes over
        add_proc(self.root, 10, "firefox", utime=80, cgroup=TERMINAL)
        self.monitor.refresh(3.0)
        self.assertTrue(changes)
        self.assertEqual([model.get_item(i).key for i in range(3)], [20, 10, 30])

    def test_column_visibility_follows_settings(self):
        col = self.page.columns["commandline"]
        self.assertFalse(col.get_visible())
        self.settings.set("processes-show-commandline", True)
        self.assertTrue(col.get_visible())
        self.assertTrue(self.page.columns["name"].get_visible())   # always shown

    def test_search(self):
        self.page.search_entry.set_text("bash")
        self.page.filter.changed(Gtk.FilterChange.DIFFERENT)
        self.assertEqual(visible_order(self.page), [20])
        self.page.search_entry.set_text("30")                       # by pid
        self.page.filter.changed(Gtk.FilterChange.DIFFERENT)
        self.assertEqual(visible_order(self.page), [30])

    def test_actions_need_a_selection(self):
        self.assertFalse(self.page.end_button.get_sensitive())
        self.page.selection.select_item(0, True)
        self.assertTrue(self.page.end_button.get_sensitive())

    def test_end_and_kill(self):
        self.page.selection.select_item(0, True)           # firefox (pid 10)
        self.page.run_action(Action.END)
        self.assertEqual(self.system.killed, [(10, signal.SIGTERM)])
        self.assertEqual(self.page.last_message, "Ended firefox")
        self.system.denied_pids.add(10)                    # not ours, no helper
        self.page.run_action(Action.KILL)
        self.assertEqual(self.page.last_message,
                         "Could not kill the process: Operation not permitted")

    def test_priority_names(self):
        self.assertEqual([nice_name(n) for n in (-20, -5, 0, 5, 19)],
                         ["Very High", "High", "Normal", "Low", "Very Low"])

    def test_scan_demand_follows_visibility(self):
        self.assertEqual(self.monitor.users, 0)
        win = Gtk.Window(child=self.page)
        win.present()
        self.assertEqual(self.monitor.users, 1)
        win.set_child(None)
        win.destroy()
        self.assertEqual(self.monitor.users, 0)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class AppsPageTest(unittest.TestCase):
    def test_grouped_rows_and_actions(self):
        _, settings, monitor = setup_procs(self)
        grouper = AppGrouper(lambda i: AppInfo("Terminal") if i == "org.gnome.Terminal"
                             else None)
        system = FakeSystem()
        page = AppsPage(monitor, settings, grouper, ProcessActions(system))
        self.assertEqual(visible_order(page), ["org.gnome.Terminal", "system"])
        term = page.rows["org.gnome.Terminal"].data
        self.assertEqual(sorted(term.pids), [10, 20])
        self.assertAlmostEqual(term.cpu, 90.0)
        page.selection.select_item(0, True)
        page.run_action(Action.HALT)
        self.assertEqual(sorted(system.killed), [(10, signal.SIGSTOP), (20, signal.SIGSTOP)])
        self.assertEqual(page.last_message, "Halted Terminal")   # one name per app


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class WindowTablesTest(unittest.TestCase):
    def test_real_pages_replace_placeholders(self):
        app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        app.register(None)
        _, settings, monitor = setup_procs(self)
        ctx = make_context(self, demo=True, settings=settings)
        ctx.processes = monitor
        win = MainWindow(app, ctx)
        self.addCleanup(win.destroy)
        self.assertIsInstance(win.page("apps"), AppsPage)
        self.assertIsInstance(win.page("processes"), ProcessesPage)
        self.assertEqual(win.sidebar.order()[:3], ["overview", "apps", "processes"])


if __name__ == "__main__":
    unittest.main()
