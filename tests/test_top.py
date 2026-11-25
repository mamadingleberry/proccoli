"""The Overview's top apps and processes."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.processes.apps import SYSTEM_ID, App  # noqa: E402
from proccoli.processes.model import ProcessInfo  # noqa: E402
from proccoli.processes.top import (TOP_COUNT, TopMetric, rank_key, top,  # noqa: E402
                                    top_apps, top_processes)

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()


def proc(pid, name, cpu=0.0, memory=0):
    return ProcessInfo(pid=pid, ppid=1, name=name, commandline=name, user="u", uid=1000,
                       state="S", nice=0, cpu=cpu, memory=memory, swap=0, read_bps=None,
                       write_bps=None, read_total=None, write_total=None, cpu_time_user=0,
                       cpu_time_system=0, started=0, cgroup="", containerized=None,
                       app_id=None)


class RankingTest(unittest.TestCase):
    def test_by_processor_then_memory_then_name(self):
        ps = [proc(1, "b", 5, 10), proc(2, "a", 5, 10), proc(3, "c", 5, 99), proc(4, "d", 50)]
        self.assertEqual([p.name for p in top_processes(ps, TopMetric.CPU)],
                         ["d", "c", "a", "b"])

    def test_by_memory_then_processor(self):
        ps = [proc(1, "low", 90, 1), proc(2, "big", 0, 500), proc(3, "busy-big", 9, 500)]
        self.assertEqual([p.name for p in top_processes(ps, "memory")],
                         ["busy-big", "big", "low"])

    def test_at_most_ten(self):
        ps = [proc(i, f"p{i}", cpu=i) for i in range(30)]
        best = top_processes(ps, TopMetric.CPU)
        self.assertEqual(len(best), TOP_COUNT)
        self.assertEqual(best[0].name, "p29")
        self.assertEqual(top(ps, TopMetric.CPU, 0), [])
        self.assertEqual(len(top(ps[:3], TopMetric.CPU)), 3)

    def test_system_processes_are_not_a_top_app(self):
        apps = [App(SYSTEM_ID, "System Processes", cpu=99, memory=10 ** 9),
                App("org.gnome.Terminal", "Terminal", cpu=3)]
        self.assertEqual([a.name for a in top_apps(apps, TopMetric.CPU)], ["Terminal"])

    def test_case_insensitive_name_tie_break(self):
        self.assertLess(rank_key(proc(1, "alpha"), TopMetric.CPU),
                        rank_key(proc(2, "Beta"), TopMetric.CPU))

    def test_metric_nicks_match_the_schema(self):
        nicks = Settings.for_tests().spec.keys["overview-top-by"].choices
        self.assertEqual(sorted(nicks), sorted(m.value for m in TopMetric))
        self.assertEqual(Settings.for_tests().get("overview-top-by"), "cpu")


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class TopTablesTest(unittest.TestCase):
    def make(self, profile=None):
        from gi.repository import Gio
        from proccoli.core.system import AppInfo
        from proccoli.processes.apps import AppGrouper
        from proccoli.ui.pages.overview import OverviewPage
        from test_ui_tables import setup_procs
        _, self.settings, self.monitor = setup_procs(self)
        icon = Gio.ThemedIcon.new("utilities-terminal-symbolic")
        grouper = AppGrouper(lambda i: AppInfo("Terminal", icon)
                             if i == "org.gnome.Terminal" else None)
        self.went = []
        page = OverviewPage(self.settings, self.went.append, self.monitor, grouper,
                            profile=profile)
        self.addCleanup(page.shutdown)
        return page

    def test_lightweight_tables_are_short_and_without_icons(self):
        """the busiest tables stay, five rows each, no icon images."""
        from proccoli.core.profile import Profile
        page = self.make(Profile.lightweight())
        tops = page.tops
        self.assertIsNotNone(tops)
        self.assertEqual((len(tops.apps.rows), len(tops.processes.rows)), (5, 5))
        self.assertTrue(all(row.icon is None for row in tops.apps.rows + tops.processes.rows))
        tops.refresh()
        self.assertEqual(tops.processes.shown()[:2], ["firefox", "bash"])
        self.assertEqual(tops.apps.shown(), ["Terminal"])
        tops.processes.list.emit("row-activated", tops.processes.rows[0])
        self.assertEqual(self.went, ["processes"])
        users = self.monitor.users
        tops.start()
        tops.stop()                                        # scans only while shown
        self.assertEqual(self.monitor.users, users)

    def test_full_tables_have_ten_rows_with_icons(self):
        page = self.make()
        self.assertEqual(len(page.tops.apps.rows), TOP_COUNT)
        self.assertTrue(all(row.icon is not None for row in page.tops.apps.rows))

    def test_tables_rank_the_monitors_processes(self):
        page = self.make()
        page.tops.refresh()
        shown = page.tops.processes.shown()
        self.assertEqual(shown[:2], ["firefox", "bash"])                 # 80 vs 10 ticks
        self.assertEqual(page.tops.apps.shown(), ["Terminal"])
        row = page.tops.processes.rows[0]
        self.assertEqual(row.rank_label.get_label(), "1")
        self.assertTrue(row.cpu_label.get_label().endswith("%"))
        self.assertEqual(row.memory_label.get_label(), "5.1 MB")
        self.assertFalse(page.tops.processes.rows[len(shown)].get_visible())   # unused rows

    def test_metric_toggle_follows_and_sets_the_setting(self):
        page = self.make()
        tops = page.tops
        self.assertTrue(tops.by_buttons[TopMetric.CPU].get_active())
        tops.by_buttons[TopMetric.MEMORY].set_active(True)
        self.assertEqual(self.settings.get("overview-top-by"), "memory")
        self.assertIn("heading", tops.processes.memory_header.get_css_classes())
        self.settings.set("overview-top-by", "cpu")
        self.assertTrue(tops.by_buttons[TopMetric.CPU].get_active())
        self.assertIn("heading", tops.apps.cpu_header.get_css_classes())

    def test_samples_only_while_shown(self):
        page = self.make()
        users = self.monitor.users
        page.tops.start()
        page.tops.start()                                  # once only
        self.assertEqual(self.monitor.users, users + 1)
        page.tops.stop()
        self.assertEqual(self.monitor.users, users)
        page.tops.start()
        page.shutdown()                                    # releases too
        self.assertEqual(self.monitor.users, users)

    def test_updates_follow_the_monitor(self):
        page = self.make()
        self.monitor.processes = {}
        self.monitor.emit("updated")
        self.assertEqual(page.tops.processes.shown(), [])
        self.assertTrue(page.tops.processes.empty.get_visible())

    def test_rows_open_the_full_page(self):
        page = self.make()
        page.tops.refresh()
        page.tops.apps.list.emit("row-activated", page.tops.apps.rows[0])
        page.tops.processes.list.emit("row-activated", page.tops.processes.rows[0])
        self.assertEqual(self.went, ["apps", "processes"])

    def test_no_tables_without_a_process_monitor(self):
        from proccoli.ui.pages.overview import OverviewPage
        page = OverviewPage(Settings.for_tests(), lambda _i: None)
        self.addCleanup(page.shutdown)
        self.assertIsNone(page.tops)



@unittest.skipUnless(HAVE_DISPLAY, "no display")
class StableTableSizeTest(unittest.TestCase):
    """The Overview's tables keep their size whatever they show, so the
    page doesn't shift as the busiest apps change."""

    def natural(self, table):
        return (table.measure(Gtk.Orientation.HORIZONTAL, -1)[1],
                table.measure(Gtk.Orientation.VERTICAL, -1)[1])

    def test_long_names_and_values_dont_change_its_size(self):
        from proccoli.ui.widgets.top_table import TopTable
        table = TopTable("Processes", 5, icons=False)
        table.set_rows([(f"p{i}", None, "0.1 %", "1.0 MB") for i in range(5)])
        before = self.natural(table)
        table.set_rows([("a-really-long-process-name-from-somewhere --with --args", None,
                         "100.0 %", "1023.9 MB")] + [(f"p{i}", None, "9.9 %", "12.3 GB")
                                                    for i in range(4)])
        self.assertEqual(self.natural(table), before)
        row = table.rows[0]
        self.assertEqual(row.name_label.get_tooltip_text(),
                         "a-really-long-process-name-from-somewhere --with --args")


if __name__ == "__main__":
    unittest.main()
