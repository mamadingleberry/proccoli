"""Dialogs (13, 15). Headless display only (``make ui-test``)."""

import argparse
import os
import signal
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeRoot, FakeSystem, make_context  # noqa: E402
from test_actions import FakeHelper  # noqa: E402
from test_processes import TERMINAL, add_proc  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from proccoli.core.privileged import HelperResult  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.system import AppInfo  # noqa: E402
from proccoli.processes.actions import ProcessActions  # noqa: E402
from proccoli.processes.apps import AppGrouper  # noqa: E402
from proccoli.processes.monitor import ProcessMonitor  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
    from proccoli.ui.dialogs.about import SHORTCUTS, about_dialog, shortcuts_dialog
    from proccoli.ui.dialogs.info import AppInfoDialog, ProcessInfoDialog
    from proccoli.ui.dialogs.preferences import (APP_COLUMNS, PROCESS_COLUMNS,
                                                PreferencesDialog)
    from proccoli.ui.dialogs.process_options import (PRIORITIES, ProcessOptionsDialog,
                                                    priority_index)


def procs(test):
    root = FakeRoot(test, {"/proc/stat": "cpu 1\ncpu0 1\ncpu1 1\nbtime 1000\n"})
    add_proc(root, 10, "firefox", utime=0, cgroup=TERMINAL, rss_kb=5000, read=100,
             cmdline="firefox --new-window")
    add_proc(root, 20, "bash", utime=0, cgroup=TERMINAL, rss_kb=100)
    settings = Settings.for_tests({"normalize-cpu-usage": False})
    monitor = ProcessMonitor(root.sysroot, settings, FakeSystem())
    monitor.refresh(1.0)
    add_proc(root, 10, "firefox", utime=50, cgroup=TERMINAL, rss_kb=5000, read=100,
             cmdline="firefox --new-window")
    monitor.refresh(2.0)
    return root, settings, monitor


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class InfoDialogsTest(unittest.TestCase):
    def test_process_info_is_live_and_notices_the_end(self):
        root, settings, monitor = procs(self)
        d = ProcessInfoDialog(monitor, settings, 10)
        self.assertEqual(d.name_label.get_label(), "firefox")
        self.assertEqual(d.rows["Processor"].get_value(), "50 %")
        self.assertEqual(d.rows["Commandline"].get_value(), "firefox --new-window")
        self.assertEqual(d.rows["User"].get_value(), "user")
        self.assertEqual(d.rows["Containerized"].get_value(), "No")
        self.assertEqual(monitor.users, 1)                 # keeps the scan running
        root.remove("/proc/10")
        monitor.refresh(3.0)
        self.assertTrue(d.ended)
        self.assertTrue(d.name_label.get_label().endswith("(ended)"))
        d.close()
        d.emit("closed")
        self.assertEqual(monitor.users, 0)

    def test_app_info(self):
        _, settings, monitor = procs(self)
        grouper = AppGrouper(lambda i: AppInfo("Terminal", None, "Use the command line")
                             if i == "org.gnome.Terminal" else None)
        d = AppInfoDialog(monitor, settings, grouper, "org.gnome.Terminal")
        self.assertEqual(d.name_label.get_label(), "Terminal")
        self.assertEqual(d.description.get_label(), "Use the command line")
        self.assertEqual(d.rows["Running Processes"].get_value(), "2")
        self.assertEqual(d.rows["ID"].get_value(), "org.gnome.Terminal")


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class ProcessOptionsTest(unittest.TestCase):
    def setUp(self):
        _, self.settings, monitor = procs(self)
        self.proc = monitor.processes[10]
        self.system = FakeSystem()
        self.system.priorities[10] = 0
        self.system.affinities[10] = {0, 1, 2, 3}
        self.messages = []

    def dialog(self):
        return ProcessOptionsDialog(self.proc, self.system, ProcessActions(self.system),
                                    self.settings, 4, report=self.messages.append)

    def test_priority_names_map_to_niceness(self):
        self.assertEqual([priority_index(n) for n in (-20, -15, -6, 0, 3, 19)],
                         [0, 0, 1, 2, 3, 4])

    def test_apply_priority_and_affinity(self):
        d = self.dialog()
        self.assertIsNone(d.nice_row)
        self.assertEqual(d.priority_row.get_selected(), 2)        # Normal
        d.priority_row.set_selected(3)                            # Low (+5)
        d.cpu_checks[3].set_active(False)
        d.apply()
        self.assertEqual(self.system.priorities[10], PRIORITIES[3][1])
        self.assertEqual(self.system.affinities[10], {0, 1, 2})
        self.assertEqual(self.messages, ["Priority changed", "Processor affinity changed"])

    def test_unchanged_applies_nothing(self):
        self.dialog().apply()
        self.assertEqual(self.messages, [])

    def test_niceness_mode(self):
        self.settings.set("detailed-priority", True)
        d = self.dialog()
        self.assertIsNone(d.priority_row)
        d.nice_row.set_value(12)
        d.apply()
        self.assertEqual(self.system.priorities[10], 12)

    def test_no_cpus_cannot_be_applied(self):
        d = self.dialog()
        for c in d.cpu_checks:
            c.set_active(False)
        self.assertFalse(d.apply_button.get_sensitive())


class FakeHistory:
    """What the dialog and the export use of a HistoryStore."""

    def __init__(self, size=0, session=1795470085154, path=None):
        self.size, self.deleted, self.commits = size, 0, 0
        self.session, self.path, self.db = session, path, object()
        self.wall_clock = lambda: 1795470095.154

    def size_on_disk(self):
        return self.size

    def delete(self):
        self.deleted += 1
        self.size = 0

    def commit(self):
        self.commits += 1

    def session_start(self):
        return self.session

    writer = True

    def writer_info(self):
        return None


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class PreferencesTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings.for_tests()
        self.dialog = PreferencesDialog(self.settings)

    def test_every_switch_works_both_ways(self):
        from proccoli.ui import preferences_layout as layout
        switches = {k: r for k, r in self.dialog.rows.items() if isinstance(r, Adw.SwitchRow)}
        # Every on/off setting the layout places, but the one that needs an
        # export (none given here).
        booleans = {k for k in layout.placed_keys()
                    if isinstance(self.settings.spec.keys[k].default, bool)}
        self.assertEqual(set(switches), booleans - {"export-hardware-addresses"})
        self.assertGreaterEqual(len(switches), len(APP_COLUMNS) + len(PROCESS_COLUMNS))
        for key, row in switches.items():
            if key == "lightweight":
                continue      # shows the running mode, not the setting (its own tests)
            before = self.settings.get(key)
            self.assertEqual(row.get_active(), before, key)
            row.set_active(not before)
            self.assertEqual(self.settings.get(key), not before, key)
            self.settings.set(key, before)
            self.assertEqual(row.get_active(), before, key)

    def test_style_combo(self):
        from proccoli.core.styles import STYLES, style_by_id
        ids = [s.id for s in STYLES]
        row = self.dialog.rows["color-scheme"]
        self.assertEqual(row.get_model().get_n_items(), len(STYLES))
        self.assertEqual(row.get_selected(), 0)                 # Follow System
        row.set_selected(ids.index("dark"))
        self.assertEqual(self.settings.get("color-scheme"), "dark")
        row.set_selected(ids.index("high-contrast-dark"))
        self.assertEqual(self.settings.get("color-scheme"), "high-contrast-dark")
        self.settings.set("color-scheme", "sand")
        self.assertEqual(row.get_selected(), ids.index("sand"))
        self.assertEqual(self.dialog.style_swatch_colors(style_by_id("sky")),
                         ("#ecf3fb", "#1d2b3c"))
        import cairo
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 28, 16)
        self.dialog._draw_style_swatch(None, cairo.Context(surface), 28, 16,
                                       style_by_id("midnight"))
        surface.flush()
        b, g, r, _a = surface.get_data()[0:4]
        self.assertEqual((r, g, b), (0x0f, 0x14, 0x20))

    def test_palette_combo_lists_every_palette_with_swatches(self):
        from proccoli.core.palette import PALETTES
        row = self.dialog.rows["palette"]
        self.assertEqual(row.get_model().get_n_items(), len(PALETTES))
        self.assertEqual(row.get_selected(), 0)                 # System
        ids = [p.id for p in PALETTES]
        row.set_selected(ids.index("nord"))
        self.assertEqual(self.settings.get("palette"), "nord")
        self.settings.set("palette", "tango")
        self.assertEqual(row.get_selected(), ids.index("tango"))
        self.assertIsNotNone(row.get_factory())
        import cairo
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 84, 12)
        self.dialog._draw_swatch(None, cairo.Context(surface), 84, 12,
                                 PALETTES[ids.index("tango")])
        surface.flush()
        i = 6 * surface.get_stride() + 6 * 4                  # centre of the first dot
        b, g, r, a = surface.get_data()[i:i + 4]               # Tango blue
        self.assertEqual((r, g, b, a), (0x34, 0x65, 0xa4, 255))

    def test_diagnostics(self):
        rows = self.dialog.rows
        self.assertEqual(rows["log-level"].get_selected(), 4)          # Everything (Debug)
        rows["log-level"].set_selected(0)
        self.assertEqual(self.settings.get("log-level"), "off")
        rows["log-max-size"].set_value(2048)
        self.assertEqual(self.settings.get("log-max-size"), 2048)
        self.assertFalse(hasattr(self.dialog, "log_button"))           # no file given
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        opened = []
        dialog = PreferencesDialog(self.settings, log_file=Path(tmp.name) / "x" / "c.log",
                                   launcher=opened.append)
        dialog.log_button.emit("clicked")
        self.assertEqual(opened, [Path(tmp.name) / "x"])
        self.assertTrue(opened[0].is_dir())

    def test_history_group(self):
        # on by default, its limits, and no size or export rows
        # without a store.
        rows = self.dialog.rows
        self.assertTrue(rows["history"].get_active())
        rows["history-max-size"].set_value(1024)
        self.assertEqual(self.settings.get("history-max-size"), 1024)
        rows["history-detail-hours"].set_value(48)
        self.assertEqual(self.settings.get("history-detail-hours"), 48)
        self.assertFalse(hasattr(self.dialog, "delete_button"))
        self.assertFalse(hasattr(self.dialog, "export_button"))
        rows["history"].set_active(False)                          # nothing to delete
        self.assertIsNone(self.dialog.delete_alert)

    def test_history_size_delete_and_export(self):
        store = FakeHistory(1536 * 1024)
        exported = []
        dialog = PreferencesDialog(self.settings, history=store,
                                   export=lambda: exported.append(1))
        self.assertEqual(dialog.size_row.get_subtitle(), "1.5 MiB")
        dialog.export_button.emit("clicked")
        self.assertEqual(exported, [1])
        dialog.delete_button.emit("clicked")
        dialog.delete_alert.emit("response", "keep")
        self.assertEqual(store.deleted, 0)
        self.settings.set("history", False)                        # offers to delete
        dialog.delete_alert.emit("response", "delete")
        self.assertEqual(store.deleted, 1)
        self.assertEqual(dialog.size_row.get_subtitle(), "Empty")

    def test_window_switching_row(self):
        # the extension's state, Install from a checkout, Turn On.
        from proccoli.core.windows import WindowSwitcher
        system = FakeSystem()
        system.extension_info = {}
        dialog = PreferencesDialog(self.settings, windows=WindowSwitcher(system),
                                   extension_source="/src/ext")
        self.assertIn("Not installed", dialog.switching_row.get_subtitle())
        self.assertEqual(dialog.switching_button.get_label(), "Install")
        dialog.switching_button.emit("clicked")
        self.assertEqual(system.installed_from, "/src/ext")
        self.assertIn("log out", dialog.switching_row.get_subtitle())
        self.assertFalse(dialog.switching_button.get_visible())
        system.extension_info = {"state": 2.0, "enabled": False}
        dialog.show_window_switching()
        self.assertEqual(dialog.switching_button.get_label(), "Turn On")
        dialog.switching_button.emit("clicked")
        self.assertTrue(dialog.switching_row.get_subtitle().startswith("On"))
        self.assertFalse(dialog.switching_button.get_visible())
        none = PreferencesDialog(self.settings, windows=WindowSwitcher(FakeSystem()))
        self.assertIn("GNOME Shell", none.switching_row.get_subtitle())
        self.assertFalse(hasattr(PreferencesDialog(self.settings), "switching_row"))

    def test_combos_and_spin(self):
        rows = self.dialog.rows
        rows["update-interval"].set_selected(4)
        self.assertEqual(self.settings.get("update-interval"), "10-seconds")
        self.assertNotIn("refresh-speed", rows)                    # replaced
        self.settings.set("temperature-unit", "kelvin")
        self.assertEqual(rows["temperature-unit"].get_selected(), 2)
        rows["intel-gpu-top-interval"].set_selected(0)
        self.assertEqual(self.settings.get("intel-gpu-top-interval"), "")
        rows["graph-time-range"].set_selected(3)                    # 5 Minutes
        self.assertEqual(self.settings.get("graph-time-range"), "5-minutes")
        self.settings.set("graph-time-range", "30-seconds")
        self.assertEqual(rows["graph-time-range"].get_selected(), 0)

    def test_closing_disconnects(self):
        self.dialog.emit("closed")
        self.settings.set("show-graph-grids", True)
        self.assertFalse(self.dialog.rows["show-graph-grids"].get_active())

    def test_gpu_detail_switch_turns_details_off_and_on(self):
        from proccoli.gpu.controller import DetailState
        ctx = make_context(self, demo=True)
        ctx.devices.start()
        controller = ctx.devices.monitor("gpu-demo")
        dialog = PreferencesDialog(ctx.settings, [controller])
        row = dialog.gpu_rows["0000:00:02.0"]
        self.assertTrue(row.get_active())
        self.assertIsNotNone(controller.detail_backend)
        row.set_active(False)
        self.assertEqual(controller.detail_state, DetailState.OFF)
        self.assertEqual(ctx.settings.get("gpu-details-disabled"), ["0000:00:02.0"])
        row.set_active(True)
        self.assertEqual(controller.detail_state, DetailState.STARTING)
        self.assertEqual(ctx.settings.get("gpu-details-disabled"), [])
        self.assertNotIn("intel-gpu-top-history", dialog.rows)   # Graph Time Range now
        ctx.devices.stop()

    def test_without_gpus(self):
        self.assertEqual(self.dialog.gpu_rows, {})

    def test_six_pages_in_order(self):
        child = self.dialog.get_visible_page()
        self.assertEqual([p.get_title() for p in self.dialog.pages.values()],
                         ["Appearance", "Sidebar", "Tables", "Recording", "Devices", "System"])
        self.assertIs(child, self.dialog.pages["appearance"])       # opens on the first

    def test_every_row_is_on_its_page(self):
        from proccoli.ui import preferences_layout as layout
        for key, row in self.dialog.rows.items():
            page = row.get_ancestor(Adw.PreferencesPage)
            self.assertIs(page, self.dialog.pages[layout.page_of(key)], key)
        self.assertEqual(set(self.dialog._builders()), set(layout.items()))

    def test_column_lists_open_in_place(self):
        row = self.dialog.rows["processes-show-commandline"]
        expander = row.get_ancestor(Adw.ExpanderRow)
        self.assertIsNotNone(expander)
        self.assertEqual(expander.get_title(), "Processes")
        self.assertEqual(self.dialog.rows["apps-show-cpu"].get_ancestor(Adw.ExpanderRow)
                         .get_title(), "Apps")

    def test_groups_without_their_service_are_hidden(self):
        groups = self.dialog.groups
        for gid in ("status", "exports", "background", "window-switching"):
            self.assertFalse(groups[gid].get_visible(), gid)
        self.assertTrue(groups["history"].get_visible())
        self.assertTrue(groups["entries"].get_visible())            # keeps its note
        full = PreferencesDialog(self.settings, history=FakeHistory(0), export=lambda: None)
        self.assertTrue(full.groups["status"].get_visible())
        self.assertTrue(full.groups["exports"].get_visible())


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class SidebarPreferencesTest(unittest.TestCase):
    """a Preferences sub-page per sidebar entry."""

    def setUp(self):
        from test_ui_shell import FakeDevicePage
        from proccoli.ui.page import PageKind
        from proccoli.ui.sidebar import StackSidebar
        self.settings = Settings.for_tests()
        self.sidebar = StackSidebar(self.settings)
        for page in (FakeDevicePage("apps", title="Apps", kind=PageKind.APPS),
                     FakeDevicePage("cpu", title="Processor", kind=PageKind.CPU),
                     FakeDevicePage("sda", title="Solid State Drive", usage=10.0),
                     FakeDevicePage("sdb", title="Hard Disk Drive", usage=20.0)):
            self.sidebar.add_item(page)
        self.dialog = PreferencesDialog(self.settings, sidebar=self.sidebar)

    def test_one_row_per_movable_entry_in_sidebar_order(self):
        self.assertEqual(list(self.dialog.entry_rows), ["cpu", "sda", "sdb"])
        self.assertEqual(self.dialog.entry_rows["sda"].get_subtitle(), "sda")  # its device ID
        self.assertIn("sidebar-details", self.dialog.rows)                   # global switches
        self.assertIn("sidebar-meter-type", self.dialog.rows)
        self.assertEqual(PreferencesDialog(self.settings).entry_rows, {})    # no sidebar given

    def test_one_entry_can_have_its_own_graph_type(self):
        page = self.dialog.open_entry("sda")
        self.assertEqual(page.graph_type.get_selected(), 0)                 # Default
        self.assertEqual(page.graph_type.get_model().get_string(0), "Default (Graph)")
        page.graph_type.set_selected(2)                                     # Progress Bar
        self.assertEqual(dict(self.settings.get("sidebar-graph-types")), {"sda": "progress-bar"})
        self.assertEqual(self.sidebar.items["sda"].meter_type.value, "progress-bar")
        self.assertEqual(self.sidebar.items["sdb"].meter_type.value, "graph")   # the rest
        self.settings.set("sidebar-meter-type", "progress-bar")             # the default
        self.assertEqual(self.sidebar.items["sdb"].meter_type.value, "progress-bar")
        self.assertEqual(page.graph_type.get_model().get_string(0), "Default (Progress Bar)")
        page.graph_type.set_selected(0)                                     # back to Default
        self.assertEqual(dict(self.settings.get("sidebar-graph-types")), {})

    def test_the_default_is_named_graph_type(self):
        self.assertEqual(self.dialog.rows["sidebar-meter-type"].get_title(), "Graph Type")

    def test_style_row_is_bound_both_ways(self):
        row = self.dialog.rows["sidebar-style"]
        self.assertEqual(row.get_selected(), 0)               # Full
        row.set_selected(1)
        self.assertEqual(self.settings.get("sidebar-style"), "icons")
        self.settings.set("sidebar-style", "full")            # from the main menu
        self.assertEqual(row.get_selected(), 0)

    def test_parts_switches_reach_the_sidebar_and_back(self):
        from proccoli.ui.sidebar_fields import Field
        sub = self.dialog.open_entry("sda")
        self.assertEqual(sub.get_title(), "Solid State Drive")
        self.assertEqual(sub.switches[Field.DESCRIPTION].get_subtitle(), "sda")
        sub.switches[Field.CHART].set_active(False)
        self.assertFalse(self.sidebar.items["sda"].meter.get_visible())
        self.assertEqual(self.settings.get("sidebar-hidden-fields"), {"sda": ["chart"]})
        self.sidebar.set_field_shown("sda", Field.NAME, False)   # from the row menu
        self.assertFalse(sub.switches[Field.NAME].get_active())
        sub.minimized.set_active(True)
        self.assertTrue(self.sidebar.items["sda"].minimized)

    def test_move_buttons(self):
        sub = self.dialog.open_entry("cpu")
        self.assertFalse(sub.up.get_sensitive())                  # first below the pinned
        self.assertEqual(sub.position.get_subtitle(), "1 of 3")
        sub.down.emit("clicked")
        self.assertEqual(self.sidebar.order(), ["apps", "sda", "cpu", "sdb"])
        self.assertEqual(sub.position.get_subtitle(), "2 of 3")
        self.assertTrue(sub.up.get_sensitive())

    def test_closing_disconnects_sub_pages(self):
        from proccoli.ui.sidebar_fields import Field
        sub = self.dialog.open_entry("sdb")
        self.dialog.emit("closed")
        self.sidebar.set_field_shown("sdb", Field.CHART, False)
        self.assertTrue(sub.switches[Field.CHART].get_active())   # no longer followed


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class LaunchAuthTest(unittest.TestCase):
    """an optional prompt at start-up; every button stays."""

    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def gpu_needing_rights(self, **settings):
        """A window whose GPU's details need administrator rights."""
        from test_gpu import FakeDetail, FakeSummary
        from proccoli.gpu.registry import GpuBackendRegistry
        from proccoli.ui.window import MainWindow
        FakeDetail.elevation = True
        self.addCleanup(setattr, FakeDetail, "elevation", False)
        self.settings = Settings.for_tests(settings)
        ctx = make_context(self, settings=self.settings,
                           gpu_registry=GpuBackendRegistry((FakeSummary, FakeDetail)))
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        return win, ctx.devices.monitor("gpu-0000:00:02.0")

    def test_offered_after_the_window_appears(self):
        win, _ = self.gpu_needing_rights()
        self.assertTrue(win.auth_action.get_enabled())
        self.assertEqual([o.id for o in win.elevation_offers()], ["gpu-0000:00:02.0"])
        self.assertIsNone(getattr(win, "auth_dialog", None))
        win.present()
        import time
        end = time.monotonic() + 3
        while getattr(win, "auth_dialog", None) is None and time.monotonic() < end:
            GLib.MainContext.default().iteration(False)
        self.assertIsNotNone(win.auth_dialog)

    def test_not_asked_when_turned_off_or_nothing_to_unlock(self):
        win, _ = self.gpu_needing_rights(**{"auth-at-launch": False})
        self.assertEqual(getattr(win, "_launch_auth_source", 0), 0)
        self.assertTrue(win.auth_action.get_enabled())           # the menu still offers it
        from proccoli.ui.window import MainWindow
        plain = MainWindow(self.app, make_context(self))
        self.addCleanup(plain.destroy)
        self.assertFalse(plain.auth_action.get_enabled())
        self.assertIsNone(plain.offer_authentication())

    def test_authenticate_runs_the_chosen_offers(self):
        from proccoli.gpu.controller import DetailState
        win, gpu = self.gpu_needing_rights()
        dialog = win.offer_authentication()
        self.assertEqual(list(dialog.switches), ["gpu-0000:00:02.0"])
        dialog.respond("authenticate")
        self.assertEqual(gpu.detail_state, DetailState.STARTING)
        self.assertTrue(gpu.detail_backend.elevated)             # through pkexec
        gpu.detail_backend.deliver()
        self.assertEqual(dialog.runner.results, {"gpu-0000:00:02.0": True})
        self.assertTrue(dialog.runner.done)
        self.assertFalse(win.auth_action.get_enabled())          # nothing left to unlock

    def test_not_now_changes_nothing_and_buttons_stay(self):
        from proccoli.gpu.controller import DetailState
        win, gpu = self.gpu_needing_rights()
        dialog = win.offer_authentication()
        dialog.dont_ask.set_active(True)
        dialog.respond("not-now")
        self.assertEqual(gpu.detail_state, DetailState.NEEDS_AUTH)
        self.assertFalse(self.settings.get("auth-at-launch"))    # don't ask again
        host = win.page("gpu-0000:00:02.0").hosts["details"]
        self.assertTrue(host.button.get_visible())               # its own button remains
        self.assertEqual(host.button.get_label(), "Show Detailed Statistics")

    def test_unchecking_skips_an_offer(self):
        win, gpu = self.gpu_needing_rights()
        dialog = win.offer_authentication()
        dialog.switches["gpu-0000:00:02.0"].set_active(False)
        self.assertEqual(dialog.chosen(), [])
        self.assertFalse(dialog.get_response_enabled("authenticate"))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class RecordFromBootTest(unittest.TestCase):
    """Asked once, after start-up, whether to record from boot."""

    def setUp(self):
        from proccoli.core.background import BackgroundService
        self.settings = Settings.for_tests()
        self.system = FakeSystem(programs={"systemctl": "/usr/bin/systemctl",
                                           "loginctl": "/usr/bin/loginctl"})
        self.background = BackgroundService(self.system)

    def answers(self, linger="no"):
        # is-enabled, is-active, Linger
        self.system.run_results = [(0, "enabled\n", ""), (0, "active\n", ""),
                                   (0, f"{linger}\n", "")]

    def app_and_window(self):
        from types import SimpleNamespace
        from proccoli.app import Application
        app = Application.__new__(Application)        # only the offer is used
        app.ctx = SimpleNamespace(settings=self.settings)
        window = Adw.ApplicationWindow()
        self.addCleanup(window.destroy)
        window.present()
        return app, window

    def test_turn_on(self):
        from proccoli.ui.dialogs.record_from_boot import TURN_ON, RecordFromBootDialog
        done = []
        dialog = RecordFromBootDialog(self.settings, self.background, finished=done.append)
        self.answers("yes")                                     # the refresh after it
        dialog.emit("response", TURN_ON)
        self.assertTrue(self.settings.get("linger-offered"))
        self.assertEqual(self.system.runs[0], ["loginctl", "enable-linger", "1000"])
        self.assertEqual(done, [TURN_ON])

    def test_not_now(self):
        from proccoli.ui.dialogs.record_from_boot import NOT_NOW, RecordFromBootDialog
        dialog = RecordFromBootDialog(self.settings, self.background)
        dialog.emit("response", NOT_NOW)
        self.assertTrue(self.settings.get("linger-offered"))   # not asked again
        self.assertEqual(self.system.runs, [])

    def test_offered_once_when_it_would_help(self):
        app, window = self.app_and_window()
        self.answers("no")
        app.offer_record_from_boot(window, self.background)
        self.assertIsNotNone(window.get_visible_dialog())
        app.record_from_boot.emit("response", "not-now")
        app.record_from_boot.close()
        self.system.runs.clear()
        app.offer_record_from_boot(window, self.background)    # answered: never again
        self.assertEqual(self.system.runs, [])

    def test_not_offered_with_lingering_on_or_another_dialog_up(self):
        app, window = self.app_and_window()
        self.answers("yes")
        app.offer_record_from_boot(window, self.background)
        self.assertIsNone(window.get_visible_dialog())
        self.assertFalse(self.settings.get("linger-offered"))  # still asks next time
        other = Adw.AlertDialog(heading="Show All Details?")
        other.present(window)
        self.answers("no")
        app.offer_record_from_boot(window, self.background)
        self.assertIs(window.get_visible_dialog(), other)       # not on top of it
        self.assertFalse(self.settings.get("linger-offered"))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class AboutTest(unittest.TestCase):
    def test_about(self):
        from proccoli import APP_ID, __version__
        d = about_dialog()
        self.assertEqual((d.get_application_icon(), d.get_version()), (APP_ID, __version__))
        self.assertIn("Zero-Clause BSD", d.get_license())

    def test_shortcuts_dialog_and_accelerators_agree(self):
        self.assertIsNotNone(shortcuts_dialog())
        accels = {a for _, items in SHORTCUTS for _, a in items}
        for accel in (one for many in accels for one in many.split()):
            ok, key, mods = Gtk.accelerator_parse(accel)
            self.assertTrue(ok and key, accel)

    def test_the_app_sets_f2_and_f1(self):
        from proccoli.app import Application
        app = Application(argparse.Namespace(demo=True, debug=False))
        self.assertEqual(app.get_accels_for_action("app.preferences"), ["F2", "<Control>comma"])
        self.assertEqual(app.get_accels_for_action("app.shortcuts"), ["F1", "<Control>question"])
        self.assertEqual(app.get_accels_for_action("app.quit"), ["<Control>q"])


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class ApplicationTest(unittest.TestCase):
    def test_app_with_injected_context(self):
        from proccoli.app import Application
        built = []

        def factory(settings, demo):
            ctx = make_context(self, demo=demo, settings=Settings.for_tests())
            built.append(ctx)
            return ctx
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log_file = os.path.join(tmp.name, "proccoli.log")
        app = Application(argparse.Namespace(demo=True, debug=False), context_factory=factory,
                          log_file=log_file)
        app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        app.register(None)                         # runs do_startup
        self.assertEqual(len(built), 1)
        self.assertTrue(built[0].demo)
        for name in ("quit", "preferences", "shortcuts", "about", "export-statistics"):
            self.assertIsNotNone(app.lookup_action(name), name)
        self.assertIsNone(app.history)                             # never in --demo
        self.assertFalse(app.lookup_action("export-statistics").get_enabled())
        self.assertEqual(app.get_accels_for_action("app.preferences"), ["F2", "<Control>comma"])
        app.activate()
        win = app.get_active_window()
        self.assertIn("gpu-demo", win.containers)
        self.assertTrue(win.menu_button.is_sensitive())     # the logo opens the main menu
        shown = []
        app._present = shown.append
        app.show_preferences()
        app.show_about()
        app.show_shortcuts()
        self.assertEqual(len(shown), 3)
        self.assertEqual(list(shown[0].gpu_rows), ["0000:00:02.0", "0000:04:00.0"])
        self.assertEqual(str(app.file_log.path), log_file)          # never the real home
        win.close()
        app.ctx.stop()
        app.file_log.shutdown()

    def test_history_store_outside_the_demo(self):
        from proccoli.app import Application
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = Application(argparse.Namespace(demo=False, debug=False),
                          context_factory=lambda s, d: make_context(
                              self, settings=Settings.for_tests()),
                          log_file=os.path.join(tmp.name, "p.log"),
                          history_path=Path(tmp.name) / "history.sqlite3",
                          import_dir=Path(tmp.name) / "stats")
        app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        app.register(None)
        try:
            self.assertEqual(app.history.path, Path(tmp.name) / "history.sqlite3")
            action = app.lookup_action("export-statistics")
            self.assertEqual(action.get_enabled(), app.settings.get("history"))
            app.settings.set("history", False)
            self.assertFalse(action.get_enabled())
        finally:
            app.history.shutdown()
            app.ctx.stop()
            app.file_log.shutdown()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class ExportFlowTest(unittest.TestCase):
    def setUp(self):
        from proccoli.ui.export import StatisticsExport
        self.window = Adw.ApplicationWindow()
        self.window.toast_overlay = Adw.ToastOverlay()
        self.chosen, self.runs, self.opened = [], [], []
        self.store = FakeHistory(path="/nowhere/history.sqlite3")
        self.export = StatisticsExport(self.store, "9.9",
                                       choose_folder=lambda w, cb: self.chosen.append(cb),
                                       run=lambda work, done: self.runs.append((work, done)),
                                       launcher=self.opened.append)

    def test_cancelled(self):
        self.export.start(self.window)
        self.chosen[0](None)
        self.assertEqual(self.runs, [])

    def test_exports_off_the_main_loop_then_offers_the_folder(self):
        from pathlib import Path
        from proccoli.core.history_export import ExportResult
        self.export.start(self.window)
        self.chosen[0](Path("/tmp/out"))
        self.assertEqual(self.store.commits, 1)                  # buffered rows go too
        self.assertTrue(self.export.busy)
        self.assertEqual(self.export.toast.get_title(), "Exporting statistics…")
        self.export.start(self.window)                           # one at a time
        self.assertEqual(len(self.chosen), 1)
        _work, done = self.runs[0]
        self.export._progress(2, 5)
        self.assertEqual(self.export.toast.get_title(), "Exporting statistics… 2 of 5 devices")
        done(ExportResult(Path("/tmp/out/proccoli-statistics-x")))
        self.assertFalse(self.export.busy)
        toast = self.export.toast
        self.assertEqual(toast.get_title(), "Statistics exported to proccoli-statistics-x")
        toast.emit("button-clicked")
        self.assertEqual(self.opened, [Path("/tmp/out/proccoli-statistics-x")])

    def test_failure_and_nothing_recorded(self):
        from pathlib import Path
        self.export.start(self.window)
        self.chosen[0](Path("/tmp/out"))
        with self.assertLogs("proccoli.ui.export", "WARNING"):
            self.runs[0][1](OSError("disk full"))
        self.assertEqual(self.export.toast.get_title(), "Couldn't export statistics: disk full")
        self.store.session = None
        self.export.start(self.window)
        self.chosen[1](Path("/tmp/out"))
        self.assertEqual(self.export.toast.get_title(), "Nothing has been recorded yet")
        self.assertEqual(len(self.runs), 1)


    def test_the_export_says_what_the_machine_and_devices_are(self):
        from pathlib import Path
        from unittest import mock
        from proccoli.ui.export import StatisticsExport
        settings = Settings.for_tests({"export-hardware-addresses": True})
        export = StatisticsExport(self.store, "9.9",
                                  choose_folder=lambda w, cb: cb(Path("/tmp/out")),
                                  run=lambda work, done: self.runs.append(work),
                                  describe=lambda: ({"kernel": "6.8"}, {"cpu": {}}),
                                  settings=settings)
        export.start(self.window)
        with mock.patch("proccoli.ui.export.export_session") as export_session:
            self.runs[0]()
        kwargs = export_session.call_args.kwargs
        self.assertEqual(kwargs["machine"], {"kernel": "6.8"})
        self.assertEqual(kwargs["current"], {"cpu": {}})
        self.assertTrue(kwargs["include_addresses"])

    def test_export_details_from_the_context(self):
        from proccoli.ui.export import export_details
        ctx = make_context(self)
        ctx.start()
        machine, current = export_details(ctx)
        self.assertIn("architecture", machine)
        self.assertNotIn("hostname", machine)
        self.assertIn("cpu", current)
        self.assertIn("Logical Cores", current["cpu"]["properties"])

    def test_record_in_the_background(self):
        from helpers import FakeSystem
        from proccoli.core.background import BackgroundService
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        system = FakeSystem(programs={"systemctl": "/usr/bin/systemctl",
                                      "loginctl": "/usr/bin/loginctl"})
        system.run_results = [(1, "disabled\n", ""), (3, "inactive\n", ""), (0, "no\n", "")]
        dialog = PreferencesDialog(Settings.for_tests(), history=FakeHistory(),
                                   background=BackgroundService(system))
        self.assertFalse(dialog.background_row.get_active())
        self.assertTrue(dialog.background_row.get_sensitive())
        self.assertFalse(dialog.linger_row.get_sensitive())        # needs the first on
        self.assertEqual(dialog.recording_row.get_subtitle(), "Recording while Proccoli is open")
        system.run_results = [(0, "", ""), (0, "enabled\n", ""), (0, "active\n", ""),
                              (0, "no\n", "")]
        dialog.background_row.set_active(True)
        self.assertIn(["systemctl", "--user", "enable", "--now", "proccoli.service"],
                      system.runs)
        self.assertTrue(dialog.linger_row.get_sensitive())
        system.run_results = [(0, "", ""), (0, "enabled\n", ""), (0, "active\n", ""),
                              (0, "yes\n", "")]
        dialog.linger_row.set_active(True)
        self.assertIn(["loginctl", "enable-linger", "1000"], system.runs)
        self.assertTrue(dialog.linger_row.get_active())

    def test_record_in_the_background_without_the_unit(self):
        from helpers import FakeSystem
        from proccoli.core.background import BackgroundService
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        system = FakeSystem(programs={"systemctl": "/usr/bin/systemctl"})
        system.run_results = [(1, "", "No such file or directory")]
        dialog = PreferencesDialog(Settings.for_tests(), history=FakeHistory(),
                                   background=BackgroundService(system))
        self.assertFalse(dialog.background_row.get_sensitive())
        self.assertEqual(dialog.background_row.get_subtitle(), "proccoli isn't installed")

    def test_custom_time_range_in_preferences(self):
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        settings = Settings.for_tests()
        dialog = PreferencesDialog(settings)
        combo, row = dialog.rows["graph-time-range"], dialog.rows["graph-time-range-custom"]
        self.assertFalse(row.get_visible())                    # only for Custom…
        combo.set_selected(combo.get_model().get_n_items() - 1)
        self.assertEqual(settings.get("graph-time-range"), "custom")
        self.assertTrue(row.get_visible())
        dialog.range_editor.number.set_value(90)
        dialog.range_editor.unit.set_selected(1)               # minutes
        self.assertEqual(settings.get("graph-time-range-custom"), 5400)
        dialog.range_editor.unit.set_selected(3)               # 90 days: too long
        self.assertEqual(settings.get("graph-time-range-custom"), 30 * 86400)
        self.assertEqual(row.get_subtitle(), "At most 30 Days")
        combo.set_selected(0)
        self.assertFalse(row.get_visible())

    def test_custom_time_range_is_greyed_out_in_lightweight_mode(self):
        from proccoli.core.profile import Profile, profile_settings
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        settings = profile_settings(Settings.for_tests(), Profile.lightweight())
        dialog = PreferencesDialog(settings)
        self.assertFalse(dialog.rows["graph-time-range-custom"].get_sensitive())

    def test_preferences_offers_hardware_addresses_with_export(self):
        from proccoli.ui.dialogs.preferences import PreferencesDialog
        dialog = PreferencesDialog(Settings.for_tests(), export=lambda: None)
        row = dialog.rows["export-hardware-addresses"]
        self.assertFalse(row.get_active())
        row.set_active(True)
        self.assertTrue(dialog.settings.get("export-hardware-addresses"))


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class PrivilegedUiTest(unittest.TestCase):
    def test_info_buttons_need_exactly_one_row(self):
        from proccoli.ui.pages.processes import ProcessesPage
        _, settings, monitor = procs(self)
        page = ProcessesPage(monitor, settings, ProcessActions(FakeSystem()), FakeSystem(),
                             cpu_count=2)
        self.assertFalse(page.info_button.get_sensitive())
        page.selection.select_item(0, True)
        self.assertTrue(page.info_button.get_sensitive())
        self.assertTrue(page.options_button.get_sensitive())
        page.selection.select_all()
        self.assertFalse(page.info_button.get_sensitive())
        self.assertFalse(page.io_button.get_visible())        # no helper

    def test_elevated_io_fills_unreadable_processes(self):
        from proccoli.core.privileged import PrivilegedHelper
        from proccoli.ui.pages.processes import ProcessesPage
        root = FakeRoot(self, {"/proc/stat": "cpu 1\ncpu0 1\nbtime 0\n"})
        add_proc(root, 30, "sshd", uid=0, io=False)
        settings = Settings.for_tests()
        system = FakeSystem()
        monitor = ProcessMonitor(root.sysroot, settings, system)
        helper = PrivilegedHelper(system, ["/x/proccoli-helper"])
        page = ProcessesPage(monitor, settings, ProcessActions(system, helper), system, helper)
        self.assertTrue(page.io_button.get_visible())
        page.io_button.set_active(True)
        reader = system.readers[-1]
        self.assertEqual(reader.started[0][-3:], ["processes", "--interval", "1000"])
        self.assertTrue(monitor.elevated)
        reader.feed({"io": {"30": [1000, 0]}})
        monitor.refresh(1.0)
        reader.feed({"io": {"30": [5000, 0]}})
        monitor.refresh(2.0)
        self.assertEqual(monitor.processes[30].read_bps, 4000.0)
        reader.exit(126)                                    # prompt dismissed / helper gone
        self.assertFalse(monitor.elevated)
        self.assertFalse(page.io_button.get_active())
        self.assertIn("Stopped", page.last_message)

    def test_kill_other_users_process_through_helper(self):
        from proccoli.processes.actions import Action
        from proccoli.ui.pages.processes import ProcessesPage
        _, settings, monitor = procs(self)
        system = FakeSystem()
        system.denied_pids = {10}
        helper = FakeHelper(HelperResult(True, {"ok": [10], "failed": []}))
        page = ProcessesPage(monitor, settings, ProcessActions(system, helper), system, helper)
        page.selection.select_item(0, True)                  # firefox, pid 10
        page.run_action(Action.KILL)
        self.assertEqual(helper.calls, [("signal", "KILL", [10])])
        self.assertEqual(page.last_message, "Killed firefox")

    def test_processes_offer_all_drive_io(self):
        from proccoli.core.privileged import PrivilegedHelper
        from proccoli.ui.pages.processes import ProcessesPage
        _, settings, monitor = procs(self)
        system = FakeSystem()
        bare = ProcessesPage(monitor, settings, ProcessActions(system), system)
        self.assertIsNone(bare.elevation_offer())                 # no helper: nothing
        helper = PrivilegedHelper(system, ["/x/proccoli-helper"])
        page = ProcessesPage(monitor, settings, ProcessActions(system, helper), system, helper)
        offer = page.elevation_offer()
        self.assertEqual(offer.id, "processes")
        results = []
        offer.run(results.append)
        self.assertTrue(monitor.elevated)
        self.assertTrue(page.io_button.get_active())             # its own button agrees
        self.assertEqual(results, [])                             # waiting for the prompt
        system.readers[-1].feed({"io": {}})
        self.assertEqual(results, [True])
        system.readers[-1].feed({"io": {}})
        self.assertEqual(results, [True])                         # reported once
        self.assertIsNone(page.elevation_offer())                 # already elevated

    def test_memory_offer_only_without_udev_data(self):
        from proccoli.ui.pages.memory import MemoryPage
        from test_memory import DMIDECODE, MEMINFO
        from proccoli.devices.base import DeviceInfo, DeviceKind
        from proccoli.devices.memory import MemoryMonitor
        from proccoli.ui.pages.factory import memory_authenticator
        root = FakeRoot(self, {"/proc/meminfo": MEMINFO})
        monitor = MemoryMonitor(DeviceInfo("memory", DeviceKind.MEMORY, "Memory"), root.sysroot)

        class Helper:
            def dmidecode(self, callback):
                callback(HelperResult(True, {"output": DMIDECODE}))
        page = MemoryPage(monitor, Settings.for_tests(), memory_authenticator(Helper()))
        self.assertIsNone(MemoryPage(monitor, Settings.for_tests()).elevation_offer())
        results = []
        page.elevation_offer().run(results.append)
        self.assertEqual(results, [True])
        self.assertTrue(page.properties.get_visible())
        self.assertIsNone(page.elevation_offer())                 # modules known now

    def test_memory_authentication(self):
        from proccoli.ui.pages.factory import memory_authenticator
        from proccoli.ui.pages.memory import MemoryPage
        from test_memory import DMIDECODE, MEMINFO
        from proccoli.devices.base import DeviceInfo, DeviceKind
        from proccoli.devices.memory import MemoryMonitor
        root = FakeRoot(self, {"/proc/meminfo": MEMINFO})
        monitor = MemoryMonitor(DeviceInfo("memory", DeviceKind.MEMORY, "Memory"), root.sysroot)

        class Helper:
            result = HelperResult(True, {"output": DMIDECODE})

            def dmidecode(self, callback):
                callback(self.result)
        helper = Helper()
        page = MemoryPage(monitor, Settings.for_tests(), memory_authenticator(helper))
        page.banner.emit("button-clicked")
        self.assertFalse(page.banner.get_revealed())
        self.assertTrue(page.properties.get_visible())
        self.assertEqual(page.property_rows["Slots Used"].get_value(), "2 of 3")
        # Cancelling keeps the banner, without an error message.
        page2 = MemoryPage(monitor.__class__(monitor.info, root.sysroot), Settings.for_tests(),
                           memory_authenticator(helper))
        helper.result = HelperResult(False, error="cancelled", cancelled=True)
        page2.banner.emit("button-clicked")
        self.assertTrue(page2.banner.get_revealed())
        self.assertIsNone(memory_authenticator(None))


if __name__ == "__main__":
    unittest.main()
