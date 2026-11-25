"""the window on proccoli' readings. A
collector on a private bus and the real window built on the
RemoteDeviceManager: its pages, the GPU's AMD Details tab, the banner.

Runs only on the private headless display (``make ui-test``)."""

import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from helpers import (FIXTURES, LAPTOP, RENOIR, FakeSystem, PrivateBus, make_context,  # noqa: E402
                     pump_until)
from proccoli import metrics  # noqa: E402
from proccoli.context import build_metrics_context  # noqa: E402
from proccoli.core import pciids  # noqa: E402
from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.core.ticker import Ticker  # noqa: E402
from proccoli.metrics_service import MetricsService  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()


@unittest.skipUnless(HAVE_DISPLAY and shutil.which("dbus-daemon"), "no display or dbus-daemon")
class RemoteWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bus = PrivateBus()
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    @classmethod
    def tearDownClass(cls):
        cls.bus.stop()

    def setUp(self):
        self.settings = Settings.for_tests()
        ticker = Ticker(timeout_add=lambda ms, cb: 1, source_remove=lambda _s: None,
                        clock=iter(range(100, 100_000)).__next__)
        self.collector = build_metrics_context(
            metrics.metrics_settings(self.settings), system=FakeSystem(),
            sysroot=SysRoot(RENOIR), pci=pciids.load(os.path.join(FIXTURES, "pci", "pci.ids")),
            connection_name=None, ticker=ticker)
        self.collector.start()
        self.addCleanup(self.collector.stop)
        self.service = MetricsService(self.collector.devices, ticker, settings=self.settings)
        self.service.start(self.bus.connect(self))
        self.addCleanup(self.service.stop)

    def window(self):
        from proccoli.ui.window import MainWindow
        ctx = make_context(self, settings=self.settings, sysroot=SysRoot(LAPTOP),
                           remote=self.bus.connect(self))
        ctx.devices.auto_start = False
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        self.assertTrue(pump_until(lambda: ctx.devices.connected))
        self.ctx = ctx
        return win

    def tick(self, n=1):
        before = self.ctx.devices.readings
        for _ in range(n):
            self.collector.ticker.tick_now()
        self.assertTrue(pump_until(lambda: self.ctx.devices.readings >= before + n))

    def test_the_window_builds_pages_from_the_collector(self):
        from proccoli.ui.pages.gpu import GpuPage
        win = self.window()
        self.assertTrue(pump_until(lambda: "gpu-0000:03:00.0" in win.containers))
        page = win.page("gpu-0000:03:00.0")
        self.assertIsInstance(page, GpuPage)
        self.assertEqual(sorted(page.hosts), ["details"])        # the AMD Details tab
        self.tick(2)
        self.assertTrue(pump_until(lambda: page._views_from is not None))
        self.assertEqual(type(page.hosts["details"].view.widget).__name__, "AmdgpuDetailsView")
        self.assertIn("amdgpu", page.property_rows["Detailed Statistics"].get_value())

    def test_the_window_reads_no_devices_of_its_own(self):
        from proccoli.devices.manager import DeviceManager
        win = self.window()
        self.assertNotIsInstance(win.ctx.devices, DeviceManager)
        self.assertEqual(win.ctx.devices.monitors()[0].__class__.__module__,
                         "proccoli.devices.remote")

    def test_lightweight_overview_before_any_reading(self):
        # Lightweight Mode's Overview charts every device at once;
        # with no reading yet, a missing line crashed every draw.
        from proccoli.core.profile import Profile, profile_settings
        from proccoli.ui.window import MainWindow
        settings = profile_settings(self.settings, Profile.lightweight())
        ctx = make_context(self, settings=settings, sysroot=SysRoot(LAPTOP),
                           remote=self.bus.connect(self))
        ctx.devices.auto_start = False
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        win.set_default_size(1024, 768)
        win.present()
        self.assertTrue(pump_until(lambda: ctx.devices.connected))
        self.assertTrue(pump_until(lambda: len(win.overview.cards) >= 3))
        graphs = [c.graph for c in win.overview.cards.values() if c.graph is not None]
        graphs += [i.meter.graph for i in win.sidebar.items.values() if i.has_meter]
        self.assertTrue(graphs)
        for g in graphs:
            self.assertNotIn(None, g.series)
        errors = []
        import sys as _sys
        old = _sys.excepthook
        _sys.excepthook = lambda *a: errors.append(a)
        self.addCleanup(setattr, _sys, "excepthook", old)
        for g in graphs:
            g.queue_draw()
        pump_until(lambda: False, 0.5)                     # draws happen
        self.assertEqual(errors, [])

    def test_lightweight_pages_that_replace_placeholders_are_built(self):
        # The window opens before the collector's devices arrive, so the
        # Processor and Memory start as placeholders; visiting them must
        # build the real pages, not leave the stand-ins.
        from proccoli.core.profile import Profile, profile_settings
        from proccoli.ui.pages.memory import MemoryPage
        from proccoli.ui.window import MainWindow
        settings = profile_settings(self.settings, Profile.lightweight())
        ctx = make_context(self, settings=settings, sysroot=SysRoot(LAPTOP),
                           remote=self.bus.connect(self))
        ctx.devices.auto_start = False
        ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        self.assertTrue(pump_until(lambda: ctx.devices.connected))
        self.assertTrue(pump_until(lambda: "memory" in ctx.devices._monitors))
        win.select_page("memory")
        self.assertTrue(pump_until(lambda: isinstance(win.page("memory"), MemoryPage)))

    def test_the_banner_when_readings_stop(self):
        win = self.window()
        self.tick()
        self.assertFalse(win.collector_banner.get_revealed())
        self.service.stop()
        self.assertTrue(pump_until(lambda: win.collector_banner.get_revealed()))
        self.assertIn("isn't running", win.collector_banner.get_title())
        self.service.start(self.bus.connect(self))
        self.assertTrue(pump_until(lambda: not win.collector_banner.get_revealed()))


if __name__ == "__main__":
    unittest.main()
