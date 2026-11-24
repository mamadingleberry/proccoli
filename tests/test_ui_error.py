"""The error page and GPU detection in the window (Milestone 55), and the
NVIDIA Details tab. Headless display only (``make ui-test``)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import FIXTURES, FakeSystem, descendants, make_context, pump, read_file  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from proccoli.core.settings import Settings  # noqa: E402
from proccoli.core.sysroot import SysRoot  # noqa: E402
from proccoli.devices.base import DeviceInfo, DeviceKind, FailedMonitor, Monitor  # noqa: E402
from proccoli.devices.manager import Discoverer  # noqa: E402

HAVE_DISPLAY = os.environ.get("PROCCOLI_UI_TESTS") == "1" and Gtk.init_check()
if HAVE_DISPLAY:
    Adw.init()


class Flaky(Discoverer):
    """A demo device whose monitor can't be built until ``fixed``."""
    kind = DeviceKind.DEMO

    def __init__(self):
        self.fixed = False

    def discover(self, sysroot, settings):
        return [DeviceInfo("sdz", DeviceKind.DEMO, "Drive", "Broken Disk")]

    def create_monitor(self, info, sysroot, settings):
        if not self.fixed:
            raise OSError("permission denied reading /sys/block/sdz/stat")
        from proccoli.devices.demo import SineMonitor
        monitor = SineMonitor()
        monitor.info = info
        return monitor


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class ErrorPageTest(unittest.TestCase):
    def info(self):
        return DeviceInfo("gpu-0000:02:00.0", DeviceKind.GPU, "GPU", "NVIDIA GPU", "gpu")

    def test_failed_monitor_gets_an_error_page(self):
        from proccoli.ui.pages.error import ERROR_ICON, ErrorPage
        from proccoli.ui.pages.factory import PageFactory
        monitor = FailedMonitor(self.info(), "No statistics source can read this GPU.",
                                "Traceback …\nRuntimeError: …")
        page = PageFactory().create(monitor)
        self.assertIsInstance(page, ErrorPage)
        self.assertEqual((page.page_id, page.title), ("gpu-0000:02:00.0", "GPU"))
        self.assertEqual(page.status.get_icon_name(), ERROR_ICON)
        self.assertEqual(page.status.get_description(), "No statistics source can read this GPU.")
        buffer = page.details_view.get_buffer()
        self.assertIn("RuntimeError", buffer.get_text(buffer.get_start_iter(),
                                                      buffer.get_end_iter(), False))
        self.assertIsNone(page.sidebar_summary())          # an entry, but no chart
        retried = []
        page.connect("retry", lambda _p: retried.append(True))
        page.retry_button.emit("clicked")
        self.assertEqual(retried, [True])

    def test_a_page_that_raises_becomes_an_error_page(self):
        from proccoli.ui.pages.error import ErrorPage
        from proccoli.ui.pages.factory import PageFactory

        class M(Monitor):
            def sample(self, now):
                return None
        factory = PageFactory()

        def broken(_m):
            raise KeyError("Max Power Cap")
        factory.register(DeviceKind.GPU, broken)
        with self.assertLogs("proccoli.ui.pages.factory"):
            page = factory.create(M(self.info()))
        self.assertIsInstance(page, ErrorPage)
        self.assertIn("Max Power Cap", page.message)
        self.assertIn("KeyError", page.details)

    def test_without_details_no_expander(self):
        from proccoli.ui.pages.error import ErrorPage
        page = ErrorPage(FailedMonitor(self.info(), "Gone."), "Gone.")
        self.assertIsNone(page.details_view)


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class WindowRetryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def test_failed_device_is_listed_and_try_again_fixes_it(self):
        from proccoli.ui.pages.error import ErrorPage
        from proccoli.ui.window import MainWindow
        ctx = make_context(self, demo=True, settings=Settings.for_tests())
        flaky = Flaky()
        ctx.devices.register(flaky)
        with self.assertLogs("proccoli.devices.manager"):
            ctx.start()
        win = MainWindow(self.app, ctx)
        self.addCleanup(win.destroy)
        self.assertIn("sdz", win.sidebar.items)                 # still in the sidebar
        page = win.page("sdz")
        self.assertIsInstance(page, ErrorPage)
        self.assertIn("permission denied", page.message)
        win.select_page("sdz")
        with self.assertLogs("proccoli.devices.manager"):       # still broken
            page.retry_button.emit("clicked")
        self.assertIsInstance(win.page("sdz"), ErrorPage)
        self.assertEqual(win.visible_page_id(), "sdz")            # stays on it
        flaky.fixed = True
        win.page("sdz").retry_button.emit("clicked")
        self.assertNotIsInstance(win.page("sdz"), ErrorPage)
        self.assertEqual(win.visible_page_id(), "sdz")


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class GpuDetectionPageTest(unittest.TestCase):
    def test_gpu_page_says_what_detection_chose(self):
        ctx = make_context(self, demo=True, settings=Settings.for_tests())
        ctx.start()
        from proccoli.ui.pages.factory import standard_page_factory
        gpu = next(m for m in ctx.devices.monitors() if m.info.kind == DeviceKind.GPU)
        page = standard_page_factory(ctx).create(gpu)
        self.addCleanup(page.shutdown)
        self.assertEqual(page.property_rows["Detailed Statistics"].get_value(),
                         gpu.plan.detail_text())
        self.assertTrue(page.property_rows["Detailed Statistics"].get_value())


@unittest.skipUnless(HAVE_DISPLAY, "no display")
class NvidiaViewTest(unittest.TestCase):
    def make(self, fixture, programs):
        from proccoli.gpu.backend import DetailServices, GpuDeps
        from proccoli.gpu.info import GpuInfo, GpuVendor
        from proccoli.gpu.nvidia.backend import NvidiaBackend
        settings = Settings.for_tests()
        system = FakeSystem(programs=programs)
        system.run_results = [(0, read_file(os.path.join(FIXTURES, "nvidia", f)), "")
                              for f in fixture]
        gpu = GpuInfo("card1", "0000:02:00.0", GpuVendor.NVIDIA, 0x10de, 1, "nvidia",
                      "NVIDIA GPU", False, None)
        backend = NvidiaBackend(gpu, GpuDeps(SysRoot("/nonexistent"), settings, system))
        views = backend.create_views(None, DetailServices(settings))
        self.addCleanup(lambda: [backend.disconnect(h) for h in views.handlers])
        return backend, views.views[0].widget

    def test_nvidia_smi_view(self):
        backend, view = self.make(["smi-rtx5060-laptop.csv"],
                                  {"nvidia-smi": "/usr/bin/nvidia-smi"})
        with self.assertLogs("proccoli.gpu.nvidia.backend", "INFO"):
            backend.start()
        self.assertIn("NVIDIA GeForce RTX 5060 Laptop GPU", view.caption.get_label())
        self.assertIn("driver 580.178.04", view.caption.get_label())
        self.assertIn("from nvidia-smi", view.caption.get_label())
        self.assertFalse(view.groups["Fan"].get_visible())          # [N/A] on a laptop
        self.assertTrue(view.groups["Power"].get_visible())
        legend = view.legends["GPU Utilization"]
        self.assertFalse(legend.items[2].get_parent().get_visible())   # no PCIe from smi
        self.assertFalse(view.boxes["GPU Utilization"].graph.series_shown(2))
        self.assertEqual(view.boxes["Video Memory"].pane.info_label.get_label(),
                         "598.7 MB of 8.5 GB")
        self.assertTrue(view.boxes["Clocks"].pane.info_label.get_label().endswith("P5"))
        texts = [w.get_label() for w in descendants(legend) if isinstance(w, Gtk.Label)]
        self.assertIn("19 %", texts)

    def test_nvidia_gpu_card_readings(self):
        # M57: the Overview card of an NVIDIA GPU: temperature and memory.
        from proccoli.gpu.backend import GpuDeps
        from proccoli.gpu.controller import GpuController
        from proccoli.gpu.info import GpuInfo, GpuVendor
        from proccoli.gpu.registry import standard_registry
        from proccoli.ui.pages.gpu import GpuPage
        settings = Settings.for_tests()
        system = FakeSystem(programs={"nvidia-smi": "/usr/bin/nvidia-smi"})
        system.run_results = [(0, read_file(os.path.join(FIXTURES, "nvidia",
                                                         "smi-rtx5060-laptop.csv")), "")] * 3
        gpu = GpuInfo("card1", "0000:02:00.0", GpuVendor.NVIDIA, 0x10de, 1, "nvidia",
                      "NVIDIA GPU", False, None)
        info = DeviceInfo("gpu-0000:02:00.0", DeviceKind.GPU, "GPU", "NVIDIA GPU", "gpu")
        with self.assertLogs("proccoli.gpu", "INFO"):
            c = GpuController(info, gpu, standard_registry(),
                              GpuDeps(SysRoot("/nonexistent"), settings, system))
            c.start()
        c.refresh(1.0)
        page = GpuPage(c, settings)
        self.addCleanup(page.shutdown)
        self.assertEqual(page.sidebar_summary().facts,
                         ["Temperature 39 °C", "Memory 598.7 MB / 8.5 GB"])

    def test_nvidia_settings_view(self):
        backend, view = self.make(["settings-targets.txt", "settings-readings.txt"],
                                  {"nvidia-settings": "/usr/bin/nvidia-settings"})
        backend.start()
        self.assertIn("from nvidia-settings, GPU 1", view.caption.get_label())
        self.assertFalse(view.groups["Power"].get_visible())        # not reported
        self.assertTrue(view.legends["GPU Utilization"].items[2].get_parent().get_visible())
        self.assertEqual(view.boxes["Video Engines"].pane.info_label.get_label(), "4.0 %")


if __name__ == "__main__":
    unittest.main()
