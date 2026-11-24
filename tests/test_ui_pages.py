"""Device pages (Milestones 4-9). Headless display only (``make ui-test``)."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, LAPTOP, FakeRoot, FakeSystem, make_context  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from proccoli.core import pciids  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()
    from proccoli.ui.pages.factory import standard_page_factory
    from proccoli.ui.window import MainWindow

PCI = pciids.load(os.path.join(FIXTURES, "pci", "pci.ids"))


class _RealStreams(FakeSystem):
    """Fake OS, but real (threaded) stream readers: the demo GPU's generator."""

    def stream_reader(self):
        from proccoli.core.runner import StreamReader
        return StreamReader()


def pump(until=lambda: False, timeout=2.0):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while ctx.pending():
            ctx.iteration(False)
        if until():
            return True
        time.sleep(0.01)
    return until()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class LaptopPagesTest(unittest.TestCase):
    """Pages built from the laptop fixture, ticked twice so deltas exist."""

    def setUp(self):
        self.settings = Settings.for_tests()
        ctx = make_context(self, settings=self.settings, sysroot=SysRoot(LAPTOP))
        self.devices = ctx.devices
        self.devices.start()
        factory = standard_page_factory(ctx)
        self.pages = {m.info.id: factory.create(m) for m in self.devices.monitors()}
        self.devices.refresh(1.0)
        self.devices.refresh(2.0)   # fixture files don't change: zero rates

    def test_all_pages_built(self):
        self.assertEqual(set(self.pages), {"cpu", "memory", "gpu-0000:00:02.0", "drive-sda",
                                           "net-eno1", "net-wlp43s0"})

    def test_every_device_page_has_a_sidebar_chart(self):
        for page_id, page in self.pages.items():
            summary = page.sidebar_summary()
            self.assertTrue(summary.series, page_id)
            for series in summary.series:
                self.assertTrue(series.values, page_id)              # filled by the ticks
        net = self.pages["net-eno1"].sidebar_summary()
        self.assertEqual([s.name for s in net.series], ["rx", "tx"])  # receive and send
        self.assertIsNone(net.max_value)                              # auto-scaled
        self.assertEqual(self.pages["cpu"].sidebar_summary().max_value, 100.0)

    def test_cpu_page(self):
        page = self.pages["cpu"]
        self.assertEqual(page.title, "Processor")
        self.assertEqual(page.description, "12th Gen Intel(R) Core(TM) i5-12450H")
        self.assertEqual(len(page.cells), 12)             # one per logical CPU
        self.assertTrue(page.sensors.get_visible())        # coretemp present
        self.assertEqual(page.property_rows["Physical Cores"].get_value(), "8")
        self.settings.set("show-logical-cpus", True)
        self.assertEqual(page.usage_stack.get_visible_child_name(), "logical")
        self.assertTrue(page.logical_switch.get_active())
        self.settings.set("temperature-unit", "fahrenheit")
        self.assertTrue(page.temperature.pane.info_label.get_label().endswith("°F"))

    def test_memory_page_shows_udev_properties_without_a_password(self):
        page = self.pages["memory"]
        self.assertIn(" of ", page.memory.pane.info_label.get_label())
        self.assertFalse(page.banner.get_revealed())
        self.assertTrue(page.properties.get_visible())
        self.assertEqual(page.property_rows["Type"].get_value(), "DDR4")
        self.assertTrue(page.description.endswith("DDR4 @ 2667 MT/s"))

    def test_memory_page_without_udev_offers_authentication(self):
        from proccoli.ui.pages.memory import MemoryPage
        monitor = self.devices.monitor("memory")
        monitor.modules = None
        page = MemoryPage(monitor, self.settings)
        self.addCleanup(page.shutdown)
        self.assertTrue(page.banner.get_revealed())
        self.assertFalse(page.properties.get_visible())

    def test_drive_and_network_pages(self):
        drive = self.pages["drive-sda"]
        self.assertEqual(drive.read.pane.info_label.get_label(), "0 B/s")
        self.assertEqual(drive.property_rows["Capacity"].get_value(), "512.1 GB")
        wifi = self.pages["net-wlp43s0"]
        self.assertEqual(wifi.title, "Wi-Fi Connection")
        self.settings.set("network-bits", True)
        self.assertEqual(wifi.receiving.pane.info_label.get_label(), "0 bit/s")
        summary = wifi.sidebar_summary()
        self.assertIsNone(summary.usage)
        self.assertIsNone(summary.max_value)

    def test_sort_order(self):
        pages = sorted(self.pages.values(), key=lambda p: p.sort_key())
        self.assertEqual([p.page_id for p in pages],
                         ["cpu", "memory", "gpu-0000:00:02.0", "drive-sda", "net-eno1",
                          "net-wlp43s0"])


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GpuPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def setUp(self):
        self.settings = Settings.for_tests({"refresh-speed": "very-fast"})
        ctx = make_context(self, demo=True, settings=self.settings, system=_RealStreams())
        ctx.start()
        self.ticker = ctx.ticker
        self.devices = ctx.devices
        self.win = MainWindow(self.app, ctx)
        self.addCleanup(self.win.destroy)
        self.controller = self.devices.monitor("gpu-demo")

    def test_detailed_tabs_fill_from_the_stream(self):
        from proccoli.gpu.intel_gpu_top.views import IntelClientsView, IntelGraphsView
        from proccoli.ui.pages.gpu import GpuPage
        page = self.win.page("gpu-demo")
        self.assertIsInstance(page, GpuPage)
        self.assertEqual(list(page.hosts), ["details", "processes"])
        container = self.win.containers["gpu-demo"]
        self.assertIs(container.header.get_title_widget(), page.switcher)
        self.win.select_page("gpu-demo")
        self.win.present()
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None, timeout=3))
        graphs = page.hosts["details"].view.widget
        self.assertIsInstance(graphs, IntelGraphsView)
        self.assertIsInstance(page.hosts["processes"].view.widget, IntelClientsView)
        self.assertFalse(page.detail_header.get_visible())     # Overview tab
        page.show_tab("details")
        self.assertEqual(self.settings.get("gpu-view"), "details")
        self.assertTrue(page.detail_header.get_visible())
        tips = [w.get_tooltip_text() for w in page.detail_header]
        self.assertEqual(tips, ["Pause Graphs", "Detailed Statistics Menu"])   # shared once
        self.assertTrue(pump(lambda: "engines" in graphs.sections, timeout=3))

    def test_gpu_processes_tab_gets_app_icons(self):
        ctx_icons = self.win.ctx.app_icons
        page = self.win.page("gpu-demo")
        self.assertEqual(page.services.app_icon, ctx_icons.icon_for_pid)
        self.assertTrue(pump(lambda: page.hosts["processes"].view is not None, timeout=3))
        clients = page.hosts["processes"].view.widget
        self.assertEqual(clients.table.app_icon, ctx_icons.icon_for_pid)
        self.assertIsNone(clients.table.app_icon(2190))   # demo PIDs: puzzle piece

    def test_turning_details_off_keeps_the_page_and_tabs(self):
        from proccoli.gpu.controller import DetailState
        self.win.select_page("gpu-demo")
        page = self.win.page("gpu-demo")
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None, timeout=3))
        page.show_tab("details")
        self.controller.set_details_enabled(False)
        self.assertIs(self.win.page("gpu-demo"), page)           # never replaced
        host = page.hosts["details"]
        self.assertIsNone(host.view)
        self.assertEqual(host.get_visible_child_name(), "status")
        self.assertEqual(host.button.get_label(), "Turn On")
        self.assertFalse(page.detail_header.get_visible())
        self.assertEqual(page._view_handlers, None)              # views disconnected
        host.button.emit("clicked")
        self.assertEqual(self.controller.detail_state, DetailState.STARTING)
        self.assertTrue(pump(lambda: host.view is not None, timeout=3))

    def test_failure_shows_retry_and_overview_keeps_working(self):
        self.win.select_page("gpu-demo")
        page = self.win.page("gpu-demo")
        self.controller.detail_backend.emit("failed", "no counters", True)
        host = page.hosts["processes"]
        self.assertEqual(host.status.get_description(), "no counters")
        self.assertEqual(host.button.get_label(), "Try Again")
        self.assertEqual(page.details_row.get_subtitle(), "no counters")
        self.controller.refresh(5.0)
        self.assertNotEqual(page.usage.pane.info_label.get_label(), "")
        host.button.emit("clicked")
        self.assertIsNotNone(self.controller.detail_backend)
        self.assertTrue(self.controller.detail_backend.elevated)    # can_elevate was set

    def test_last_tab_is_restored(self):
        self.settings.set("gpu-view", "processes")
        from proccoli.ui.pages.gpu import GpuPage
        page = GpuPage(self.controller, self.settings)
        self.addCleanup(page.shutdown)
        self.assertEqual(page.current_tab(), "processes")
        self.settings.set("gpu-view", "no-such-tab")
        other = GpuPage(self.controller, self.settings)
        self.addCleanup(other.shutdown)
        self.assertEqual(other.current_tab(), "overview")

    def test_sidebar_follows_the_gpu_summary(self):
        self.win.select_page("gpu-demo")
        self.win.present()
        item = self.win.sidebar.items["gpu-demo"]
        self.ticker.start()
        self.assertTrue(pump(lambda: "%" in item.usage_label.get_label(), timeout=3))
        self.ticker.stop()


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GraphsFillThePageTest(unittest.TestCase):
    """Milestone 22: graphs resize with the window, both ways."""

    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def window(self, page_id, demo=False, **settings):
        self.settings = Settings.for_tests(settings)
        ctx = make_context(self, demo=demo, settings=self.settings, system=_RealStreams())
        ctx.start()
        ctx.devices.refresh(1.0)
        ctx.devices.refresh(2.0)          # two samples: CPU deltas exist
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        win.set_default_size(1024, 768)
        win.select_page(page_id)
        win.present()
        pump(timeout=1.5)
        return win, win.page(page_id)

    def resize(self, win, w, h):
        win.set_default_size(w, h)
        pump(timeout=1.5)

    def test_page_graphs_share_the_height(self):
        win, page = self.window("memory")
        tall = [g.get_content_height() for g in page.graphs]
        self.assertGreater(tall[0], 120)
        self.assertEqual(len(set(tall)), 1)                   # rows share it equally
        self.resize(win, 1024, 450)
        short = page.graphs[0].get_content_height()
        self.assertLess(short, tall[0])
        self.assertGreaterEqual(short, 120)                   # never below the minimum
        self.resize(win, 1024, 768)
        self.assertEqual(page.graphs[0].get_content_height(), tall[0])

    def test_axes_follow_settings(self):
        win, page = self.window("memory")
        g = page.memory.graph
        self.assertTrue(g.has_axes())                            # on by default
        self.assertEqual(g.time_span_s, 60.0)
        self.settings.set("refresh-speed", "slow")
        self.assertEqual(g.time_span_s, 120.0)
        self.settings.set("show-graph-axes", False)
        self.assertFalse(g.has_axes())
        cpu_chart = win.sidebar.items["cpu"].meter.graph
        self.assertFalse(cpu_chart.show_axes)
        self.settings.set("show-graph-axes", True)
        self.assertTrue(cpu_chart.has_axes())
        net = win.page("net-eno1").receiving.graph
        self.assertFalse(net.has_axes())                        # speeds, not percentages

    def test_column_uses_the_width(self):
        win, page = self.window("memory")
        margins = page.box.get_margin_start() + page.box.get_margin_end()
        self.assertEqual(page.box.get_width(), page.scroller.get_width() - margins)
        self.assertGreaterEqual(page.clamp.get_maximum_size(), 1600)   # was 800

    def test_per_thread_graphs_grow_with_their_width(self):
        from proccoli.ui.pages.cpu import THREAD_CELL_MIN_WIDTH
        win, page = self.window("cpu", **{"show-logical-cpus": True})
        page.update_labels(page.monitor.latest)
        pump(timeout=1.0)
        cell = page.cells[0]
        self.assertGreaterEqual(cell.get_width(), THREAD_CELL_MIN_WIDTH)
        wide = cell.graph.get_height()
        self.assertAlmostEqual(wide, cell.graph.get_width() * 0.6, delta=2)
        self.resize(win, 820, 768)
        self.assertLessEqual(cell.graph.get_height(), wide)

    def test_portrait_window_caps_graphs_by_width(self):
        # Milestone 36: a portrait monitor makes the window tall and narrow;
        # graphs stop at half their width instead of growing into towers.
        win, page = self.window("memory")
        self.resize(win, 700, 1800)
        for g in page.graphs:
            self.assertLessEqual(g.get_content_height(), g.get_width() * 0.5 + 1)
            self.assertGreater(g.get_content_height(), 120)
        self.resize(win, 1024, 768)
        self.assertGreater(page.graphs[0].get_content_height(), 120)

    def test_pairs_stack_on_portrait_and_narrow_windows(self):
        win, page = self.window("demo", demo=True)
        pair = page.io
        self.assertFalse(pair.stacked)                         # landscape: side by side
        start, end = (g.compute_bounds(page.box)[1] for g in pair.graphs)
        self.assertEqual(start.get_y(), end.get_y())
        self.resize(win, 800, 1600)
        self.assertTrue(pump(lambda: pair.stacked, timeout=2))
        pump(timeout=1.0)
        start, end = (g.compute_bounds(page.box)[1] for g in pair.graphs)
        self.assertLess(start.get_y(), end.get_y())            # one above the other
        self.assertAlmostEqual(start.get_width(), page.graphs[0].get_width(), delta=2)
        self.resize(win, 1024, 768)
        self.assertTrue(pump(lambda: not pair.stacked, timeout=2))

    def test_gpu_details_fill_the_height(self):
        self.settings = Settings.for_tests({"refresh-speed": "very-fast", "gpu-view": "details"})
        ctx = make_context(self, demo=True, settings=self.settings, system=_RealStreams())
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        win.set_default_size(1024, 768)
        win.select_page("gpu-demo")
        win.present()
        page = win.page("gpu-demo")
        self.assertTrue(pump(lambda: page.hosts["details"].view is not None
                             and page.hosts["details"].view.widget.grid.get_visible(),
                             timeout=3))
        grid = page.hosts["details"].view.widget.grid
        self.assertTrue(pump(lambda: grid.get_height() > 0, timeout=3))   # ~1 frame/s
        tall = grid.get_height()
        win.set_default_size(1024, 500)
        self.assertTrue(pump(lambda: 0 < grid.get_height() < tall, timeout=3))
        # Portrait (Milestone 36): one tall column, graphs capped by width.
        from proccoli.gpu.intel_gpu_top.grid import graph_cap
        win.set_default_size(700, 1800)
        pump(timeout=2.0)
        for section in grid.sections:
            if section.get_visible():
                self.assertLessEqual(section.graph.get_height(),
                                     graph_cap(section.get_width()) + 1)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GenericGpuPageTest(unittest.TestCase):
    def test_amd_style_values(self):
        from proccoli.devices.base import DeviceInfo, DeviceKind
        from proccoli.gpu.controller import GpuController
        from proccoli.gpu.generic_drm import GenericDrmBackend
        from proccoli.gpu.info import GpuInfo, GpuVendor
        from proccoli.gpu.registry import GpuBackendRegistry
        dev = "/sys/class/drm/card0/device"
        root = FakeRoot(self, {
            f"{dev}/gpu_busy_percent": "37\n", f"{dev}/mem_info_vram_used": "1073741824\n",
            f"{dev}/mem_info_vram_total": "8589934592\n",
            f"{dev}/hwmon/hwmon5/power1_average": "45000000\n",
            f"{dev}/hwmon/hwmon5/power1_cap": "200000000\n",
            f"{dev}/hwmon/hwmon5/temp1_input": "61000\n"})
        from proccoli.gpu.backend import GpuDeps
        gpu = GpuInfo("card0", "0000:03:00.0", GpuVendor.AMD, 0x1002, 0x744c, "amdgpu",
                      "AMD Radeon", False, None, {"PCI Slot": "0000:03:00.0"})
        registry = GpuBackendRegistry((GenericDrmBackend,))
        settings = Settings.for_tests()
        c = GpuController(DeviceInfo("gpu-0000:03:00.0", DeviceKind.GPU, "GPU", "AMD Radeon"),
                          gpu, registry, GpuDeps(root.sysroot, settings, FakeSystem()))
        c.start()
        from proccoli.ui.pages.gpu import GpuPage
        page = GpuPage(c, settings)
        c.refresh(1.0)
        self.assertEqual(page.usage.pane.info_label.get_label(), "37 %")
        self.assertTrue(page.video.get_visible())            # separate enc/dec engines
        self.assertFalse(page.video_combined.get_visible())
        self.assertTrue(page.vram.get_visible())
        self.assertEqual(page.power.get_value(), "45.0 W / 200 W")
        self.assertTrue(page.sensors.get_visible())
        self.assertEqual(page.property_rows["Max Power Cap"].get_value(), "200 W")
        self.assertEqual(page.header_widgets(), [])           # no detail source:
        self.assertIsNone(page.title_widget())                # no tabs either
        self.assertEqual(page.hosts, {})
        self.assertIsNone(page.details_row)


if __name__ == "__main__":
    unittest.main()
